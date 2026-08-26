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

# Cosine-similarity bands (SFace self-match ~1.0; cross-person < 0.35).
# >= MATCH_THRESHOLD : verified identification — the worker's identity may be
#                      attributed to sessions/alerts.
# UNVERIFIED..MATCH  : likely match shown as "EMP4 (?)" on the overlay —
#                      NEVER auto-attributed to alerts or health scores.
# < UNVERIFIED       : unknown face, assigned to nobody.
#
# Historical note: this was briefly dropped to 0.15 to force matches through.
# That made false accepts near-certain — a safety product that guesses names
# is worse than one that says "unknown". Fix recognition by enrolling MORE
# samples (multi-angle), never by lowering this threshold.
FACE_MATCH_THRESHOLD = float(os.environ.get("FACE_MATCH_THRESHOLD", "0.42"))
FACE_UNVERIFIED_THRESHOLD = float(
    os.environ.get("FACE_UNVERIFIED_THRESHOLD", os.environ.get("FACE_UNKNOWN_THRESHOLD", "0.32"))
)
# Embedding samples kept per worker (oldest pruned). More samples of the same
# face across angles/lighting directly raise true-match rates at fixed
# thresholds — that is how recognition accuracy is supposed to be bought.
FACE_MAX_SAMPLES = max(1, int(os.environ.get("FACE_MAX_SAMPLES", "5")))
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
    """Enroll one face sample for a worker. Call repeatedly (different angles,
    distances, lighting) to store up to ``FACE_MAX_SAMPLES`` embeddings.

    Raises ValueError when the image contains no usable face (the API layer
    converts that to a 422).
    """
    emb = embedding_from_image(image_bytes)
    if emb is None:
        raise ValueError("No usable face detected in the uploaded photo")
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        count_row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM worker_face_samples WHERE worker_id = ?",
            (worker_id,),
        ).fetchone()
        sample_index = int(count_row["cnt"]) if count_row else 0
        conn.execute(
            """
            INSERT INTO worker_face_samples (worker_id, embedding, enrolled_at, sample_index)
            VALUES (?, ?, ?, ?)
            """,
            (worker_id, json.dumps(emb.tolist()), now, sample_index),
        )
        # Prune oldest samples beyond the cap so enrollment can be refreshed
        # indefinitely without bloating the table.
        conn.execute(
            """
            DELETE FROM worker_face_samples
            WHERE worker_id = ? AND id NOT IN (
                SELECT id FROM worker_face_samples WHERE worker_id = ?
                ORDER BY id DESC LIMIT ?
            )
            """,
            (worker_id, worker_id, FACE_MAX_SAMPLES),
        )
        conn.commit()
    remaining = get_face_status(worker_id)
    logger.info("Enrolled face sample %d for worker %s", sample_index + 1, worker_id)
    return {
        "worker_id": worker_id,
        "enrolled": True,
        "enrolled_at": now,
        "sample_count": remaining.get("sample_count", 1),
        "max_samples": FACE_MAX_SAMPLES,
    }


def delete_worker_face(worker_id: str) -> bool:
    """Erase ALL biometric samples for a worker. Returns True if any were deleted."""
    with get_connection() as conn:
        cur = conn.execute(
            "DELETE FROM worker_face_samples WHERE worker_id = ?", (worker_id,)
        )
        conn.commit()
        return cur.rowcount > 0


def get_face_status(worker_id: str) -> dict:
    """Return enrollment status for a worker (enrolled / sample count / timestamps)."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT enrolled_at, sample_index FROM worker_face_samples
            WHERE worker_id = ? ORDER BY id
            """,
            (worker_id,),
        ).fetchall()
    if not rows:
        return {"worker_id": worker_id, "enrolled": False, "sample_count": 0}
    return {
        "worker_id": worker_id,
        "enrolled": True,
        "sample_count": len(rows),
        "max_samples": FACE_MAX_SAMPLES,
        "enrolled_at": rows[0]["enrolled_at"],
        "updated_at": rows[-1]["enrolled_at"],
    }


def list_enrolled_embeddings() -> list[dict]:
    """Load all (worker_id, embedding) pairs eligible for matching.

    A worker is excluded from matching when they opted out of face identity
    (``identity_mode`` is ``badge`` or ``off``) or denied consent — face
    recognition must never silently identify someone who chose not to be
    identified by camera.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT s.worker_id, s.embedding
            FROM worker_face_samples s
            JOIN workers w ON w.worker_id = s.worker_id
            WHERE w.identity_mode = 'face' AND w.consent_status != 'denied'
            """
        ).fetchall()
    out = []
    for row in rows:
        try:
            emb = _normalize(json.loads(row["embedding"]))
        except (ValueError, TypeError):
            continue
        out.append({"worker_id": row["worker_id"], "embedding": emb})
    return out


def identify_face(embedding: np.ndarray) -> dict:
    """Match a face embedding against every stored sample of every enrolled worker.

    Scoring takes the BEST similarity across all samples of each worker, so
    one well-captured enrollment angle rescues recognition from harder ones.

    Returns ``{"worker_id": str|None, "confidence": float,
    "matched": bool, "verified": bool, "band": "verified"|"unverified"|"unknown"}``.

    ``matched``/``verified`` are True only at or above FACE_MATCH_THRESHOLD;
    between the unverified floor and the match threshold the candidate is
    reported with ``band="unverified"`` — callers must render it as
    "Name (?)" and must NOT attribute alerts/sessions to it.
    """
    query = _normalize(embedding)
    best_per_worker: dict[str, float] = {}
    for rec in list_enrolled_embeddings():
        score = float(np.dot(query, rec["embedding"]))
        prev = best_per_worker.get(rec["worker_id"], -1.0)
        if score > prev:
            best_per_worker[rec["worker_id"]] = score
    if not best_per_worker:
        return {"worker_id": None, "confidence": 0.0, "matched": False, "verified": False, "band": "unknown"}
    best = max(best_per_worker.items(), key=lambda kv: kv[1])
    best_worker, best_score = best[0], round(float(best[1]), 3)
    if best_score >= FACE_MATCH_THRESHOLD:
        return {"worker_id": best_worker, "confidence": best_score, "matched": True, "verified": True, "band": "verified"}
    if best_score >= FACE_UNVERIFIED_THRESHOLD:
        # Candidate identity: show "Name (?)" — never attribute data to it.
        return {"worker_id": best_worker, "confidence": best_score, "matched": False, "verified": False, "band": "unverified"}
    return {"worker_id": None, "confidence": best_score, "matched": False, "verified": False, "band": "unknown"}


def identify_persons_in_frame(frame, person_boxes: list[dict]) -> list[dict]:
    """Identify the faces of persons detected in a frame.

    For each person box, crop the region, run YuNet inside it, and match the
    largest face. Returns one entry per person box:

        {"box": {"x1", "y1", "x2", "y2", "confidence"},
         "worker_id": str | None, "name": str | None,
         "confidence": float, "matched": bool, "band": str}

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
                if (identity.get("matched") or identity.get("band") == "unverified") and identity.get("worker_id"):
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
