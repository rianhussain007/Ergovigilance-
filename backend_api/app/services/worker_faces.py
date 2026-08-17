"""Worker face enrollment & recognition.

Enrollment: a supervisor uploads a face photo for a worker → YuNet detects
the face → SFace computes a 128-dim embedding → stored in SQLite
(``worker_faces`` table) keyed by ``worker_id``.

Recognition at runtime: the live pipeline crops faces with YuNet and compares
each embedding against every enrolled worker with cosine similarity. A match
above ``FACE_MATCH_THRESHOLD`` identifies the worker; below it, the face is
"unidentified" (never wrong-assigned). Between ``UNKNOWN_THRESHOLD`` and the
match threshold the identity is reported with lower confidence.

Design notes:
- SFace (OpenCV Zoo) is a 38 MB ONNX model — far lighter than
  insightface/dlib, and it runs on the existing opencv-contrib install.
- The recognizer loads lazily on first use so a missing model never blocks
  app startup; the live pipeline degrades to "no identity" gracefully.
- All DB writes go through ``get_connection`` like the rest of the local
  store, so the same SQLite file stays the single source of truth.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Optional

import cv2
import numpy as np

from app.core.config import settings
from app.core.database import get_connection

logger = logging.getLogger(__name__)

# Cosine similarity at or above this identifies the worker (SFace cosine
# self-match is ~1.0; cross-person matches are typically < 0.35).
FACE_MATCH_THRESHOLD = float(os.environ.get("FACE_MATCH_THRESHOLD", "0.45"))
# Below this, the face is simply unknown (not assigned to anyone).
FACE_UNKNOWN_THRESHOLD = float(os.environ.get("FACE_UNKNOWN_THRESHOLD", "0.25"))
# Minimum face size in pixels for enrollment (tiny crops embed poorly).
_MIN_ENROLL_FACE_SIZE = 40

_detector = None
_recognizer = None
_model_lock = threading.Lock()


def _load_models():
    """Load YuNet + SFace once, thread-safely. Returns (detector, recognizer) or (None, None)."""
    global _detector, _recognizer
    with _model_lock:
        if _detector is not None and _recognizer is not None:
            return _detector, _recognizer
        try:
            model_dir = getattr(settings, "MODEL_DIR", "models") or "models"
            yunet_path = os.path.join(model_dir, "face_detection_yunet_2023mar.onnx")
            sface_path = os.path.join(model_dir, "face_recognition_sface_2021dec.onnx")
            if not os.path.exists(yunet_path) or not os.path.exists(sface_path):
                logger.warning(
                    "Face models missing (%s, %s) — face recognition disabled",
                    yunet_path, sface_path,
                )
                return None, None
            # Detector input size is (w, h); we re-create it per frame size.
            detector = cv2.FaceDetectorYN.create(
                yunet_path, "", (320, 320), 0.6, 0.3, 5000
            )
            recognizer = cv2.FaceRecognizerSF.create(sface_path, "")
            _detector, _recognizer = detector, recognizer
            logger.info("Face detector + recognizer loaded")
            return detector, recognizer
        except Exception as exc:
            logger.warning("Face recognition unavailable: %s", exc)
            return None, None


def _normalize(emb) -> np.ndarray:
    """L2-normalize a (1,128) embedding to a flat (128,) unit vector."""
    v = np.asarray(emb, dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(v))
    if norm < 1e-9:
        return v
    return (v / norm).astype(np.float32)


def embedding_from_image(image_bytes: bytes) -> Optional[np.ndarray]:
    """Compute a normalized SFace embedding from raw image bytes, or None.

    Returns None if no usable face is found (too small, blurred, or the
    models are unavailable) — callers treat that as "could not enroll".
    """
    detector, recognizer = _load_models()
    if detector is None or recognizer is None:
        return None
    img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return None
    h, w = img.shape[:2]
    if h < 1 or w < 1:
        return None
    # Re-create the detector for this frame's size (YuNet needs matching input).
    fd = cv2.FaceDetectorYN.create(
        detector.getModelPath() if hasattr(detector, "getModelPath") else _yunet_path(),
        "",
        (w, h),
        0.6, 0.3, 5000,
    )
    _, faces = fd.detect(img)
    if faces is None or len(faces) == 0:
        return None
    # Pick the largest face (most likely the subject of an enrollment photo).
    face = max(faces, key=lambda f: f[2] * f[3])
    fw, fh = face[2], face[3]
    if fw < _MIN_ENROLL_FACE_SIZE or fh < _MIN_ENROLL_FACE_SIZE:
        logger.info("Face too small for enrollment (%dx%d)", int(fw), int(fh))
        return None
    aligned = recognizer.alignCrop(img, face)
    emb = recognizer.feature(aligned)
    return _normalize(emb)


def _yunet_path() -> str:
    model_dir = getattr(settings, "MODEL_DIR", "models") or "models"
    return os.path.join(model_dir, "face_detection_yunet_2023mar.onnx")


def enroll_worker(worker_id: str, image_bytes: bytes) -> dict:
    """Enroll a worker's face photo. Returns a status dict.

    Raises ValueError when the image contains no usable face (the API layer
    converts that to a 422).
    """
    emb = embedding_from_image(image_bytes)
    if emb is None:
        raise ValueError("No usable face detected in the uploaded photo")
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO worker_faces (worker_id, embedding, enrolled_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(worker_id) DO UPDATE SET
                embedding = excluded.embedding,
                updated_at = excluded.updated_at
            """,
            (worker_id, json.dumps(emb.tolist()), now, now),
        )
        conn.commit()
    logger.info("Enrolled face for worker %s", worker_id)
    return {"worker_id": worker_id, "enrolled": True, "enrolled_at": now}


def delete_worker_face(worker_id: str) -> bool:
    """Remove a worker's face enrollment. Returns True if a row was deleted."""
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM worker_faces WHERE worker_id = ?", (worker_id,))
        conn.commit()
        return cur.rowcount > 0


def get_face_status(worker_id: str) -> dict:
    """Return enrollment status for a worker (enrolled / not)."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT enrolled_at, updated_at FROM worker_faces WHERE worker_id = ?",
            (worker_id,),
        ).fetchone()
    if row is None:
        return {"worker_id": worker_id, "enrolled": False}
    return {
        "worker_id": worker_id,
        "enrolled": True,
        "enrolled_at": row["enrolled_at"],
        "updated_at": row["updated_at"],
    }


def list_enrolled_embeddings() -> list[dict]:
    """Load all (worker_id, embedding) pairs for matching."""
    with get_connection() as conn:
        rows = conn.execute("SELECT worker_id, embedding FROM worker_faces").fetchall()
    out = []
    for row in rows:
        try:
            emb = _normalize(json.loads(row["embedding"]))
        except (ValueError, TypeError):
            continue
        out.append({"worker_id": row["worker_id"], "embedding": emb})
    return out


def identify_face(embedding: np.ndarray) -> dict:
    """Match a face embedding against enrolled workers.

    Returns ``{"worker_id": str|None, "confidence": float, "matched": bool}``.
    ``matched`` is True only when confidence >= FACE_MATCH_THRESHOLD.
    """
    query = _normalize(embedding)
    best = None
    best_score = -1.0
    for rec in list_enrolled_embeddings():
        score = float(np.dot(query, rec["embedding"]))
        if score > best_score:
            best_score = score
            best = rec["worker_id"]
    if best is None:
        return {"worker_id": None, "confidence": 0.0, "matched": False}
    matched = best_score >= FACE_MATCH_THRESHOLD
    if best_score < FACE_UNKNOWN_THRESHOLD:
        return {"worker_id": None, "confidence": round(best_score, 3), "matched": False}
    return {
        "worker_id": best if matched else None,
        "confidence": round(best_score, 3),
        "matched": matched,
    }


def identify_persons_in_frame(frame, person_boxes: list[dict]) -> list[dict]:
    """Identify the faces of persons detected in a frame.

    For each person box, crop the region, run YuNet inside it, and match the
    largest face. Returns one entry per person box:

        {"box": {"x1", "y1", "x2", "y2", "confidence"},
         "worker_id": str | None, "name": str | None,
         "confidence": float, "matched": bool}

    ``worker_id`` is None when the face is unknown, not visible, or below the
    match threshold. ``name`` is resolved from the workers table when matched.

    *frame* is a BGR image (mirrored already if the caller mirrors the feed).
    *person_boxes* are normalized xyxy boxes from ``detect_persons``.
    """
    detector, recognizer = _load_models()
    if detector is None or recognizer is None or not person_boxes:
        return []
    h, w = frame.shape[:2]
    names = enrolled_worker_names()
    employee_ids = enrolled_worker_employee_ids()
    results = []
    for box in person_boxes:
        x1 = int(box["x1"] * w)
        y1 = int(box["y1"] * h)
        x2 = int(box["x2"] * w)
        y2 = int(box["y2"] * h)
        # Pad the crop slightly to catch a face near the box edge.
        pad_x = int((x2 - x1) * 0.10)
        pad_y = int((y2 - y1) * 0.10)
        cx1, cy1 = max(0, x1 - pad_x), max(0, y1 - pad_y)
        cx2, cy2 = min(w, x2 + pad_x), min(h, y2 + pad_y)
        identity = {"worker_id": None, "name": None, "employee_id": None, "confidence": 0.0, "matched": False, "seen": False}
        if cx2 - cx1 >= 16 and cy2 - cy1 >= 16:
            crop = frame[cy1:cy2, cx1:cx2]
            fd = cv2.FaceDetectorYN.create(_yunet_path(), "",
                                           (crop.shape[1], crop.shape[0]), 0.6, 0.3, 5000)
            _, faces = fd.detect(crop)
            if faces is not None and len(faces) > 0:
                face = max(faces, key=lambda f: f[2] * f[3])
                aligned = recognizer.alignCrop(crop, face)
                emb = recognizer.feature(aligned)
                match = identify_face(_normalize(emb))
                identity.update(match)
                # A face was visible in the box — even if it didn't match an
                # enrolled worker, tag the box "Not recognized" rather than
                # leaving it untagged.
                identity["seen"] = True
                if identity.get("matched") and identity.get("worker_id"):
                    identity["name"] = names.get(identity["worker_id"])
                    identity["employee_id"] = employee_ids.get(identity["worker_id"])
        results.append({"box": dict(box), **identity})
    return results


def enrolled_worker_names() -> dict[str, str]:
    """Map worker_id -> name for enrolled workers (for overlay tags)."""
    from app.core.database import get_worker
    out = {}
    for rec in list_enrolled_embeddings():
        row = get_worker(rec["worker_id"])
        if row:
            out[rec["worker_id"]] = row["name"]
    return out


def enrolled_worker_employee_ids() -> dict[str, str]:
    """Map worker_id -> employee_id for enrolled workers (overlay tags)."""
    from app.core.database import get_worker
    out = {}
    for rec in list_enrolled_embeddings():
        row = get_worker(rec["worker_id"])
        if row:
            out[rec["worker_id"]] = row["employee_id"]
    return out
