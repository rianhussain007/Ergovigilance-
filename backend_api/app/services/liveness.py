"""Face liveness (anti-photo-spoof) detection.

The face recognizer matches geometry — a printed photo or a phone screen
showing an enrolled worker's face produces the same embedding as the live
person, so recognition alone cannot tell a real worker from a photo.

This module adds the standard single-camera liveness signals:

1. **Blink detection (Eye Aspect Ratio)** — a live person blinks every
   2-10 s; a static photo never blinks. EAR is computed from the MediaPipe
   FaceLandmarker eye landmarks and a blink is counted when EAR dips below
   the closed-eye threshold.
2. **Face-region motion** — a live face has continuous micro-movement (head
   sway, expression, breathing); a held-still photo has near-zero
   frame-to-frame change inside the face crop.

Each detected face is tracked across samples by IoU association, so multiple
people each accumulate their own blink/motion history. A verdict is attached
to every identity:

- ``live``       — blinks observed, or sustained face-region motion.
- ``suspicious`` — face present long enough, but NO blinks and NO motion
                   (consistent with a photo / frozen frame).
- ``unverified`` — not enough samples yet (first few seconds of appearance).

The live pipeline samples liveness at ~2-4 Hz (its own throttle, faster than
the 2 s identity pass) so blinks — which last ~150-400 ms — are not missed.

Design notes:
- FaceLandmarker loads lazily and is optional: if the model is missing, the
  tracker degrades to motion-only verdicts, and if that's also unavailable,
  every face is ``unverified`` (recognition still works — liveness is a
  best-effort gate, never a pipeline blocker).
- The tracker is stateless across service restarts; a fresh ``FaceLivenessTracker``
  should be created per session or kept on the service instance.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Optional

import cv2
import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)

# EAR at or below this counts as a blink sample (closed eye). Measured on the
# real model: open eyes ~0.25, closed ~0.15.
BLINK_EAR_THRESHOLD = float(os.environ.get("BLINK_EAR_THRESHOLD", "0.19"))
# Minimum IoU for two boxes to be the same tracked face.
_TRACK_IOU = 0.5
# A face seen this long with no blinks and no motion is judged suspicious.
SUSPICIOUS_MIN_SECONDS = float(os.environ.get("SUSPICIOUS_MIN_SECONDS", "5.0"))
# Blinks at or above this confirm liveness outright.
LIVE_MIN_BLINKS = int(os.environ.get("LIVE_MIN_BLINKS", "1"))
# Fraction of samples with motion above which the face is considered live
# even without blinks (e.g. a talking worker seen from an angle).
MOTION_LIVE_FRACTION = 0.4
# Mean-abs-diff (8-bit grayscale) above this counts as "motion" in the crop.
MOTION_THRESHOLD = 1.0
# Faces with a larger box area are tracked more reliably; ignore tiny boxes.
_MIN_TRACK_AREA = 0.01

# MediaPipe FaceMesh eye landmark indices used for EAR.
_LEFT_EYE = (33, 160, 158, 133, 153, 144)
_RIGHT_EYE = (362, 385, 387, 263, 373, 380)

_landmarker = None
_landmarker_lock = threading.Lock()


def _load_landmarker():
    """Load the FaceLandmarker once, thread-safely. Returns None on failure."""
    global _landmarker
    with _landmarker_lock:
        if _landmarker is not None:
            return _landmarker
        try:
            from mediapipe.tasks.python import BaseOptions, vision

            model_dir = getattr(settings, "MODEL_DIR", "models") or "models"
            model_path = os.path.join(model_dir, "face_landmarker.task")
            if not os.path.exists(model_path):
                logger.warning("face_landmarker.task not found at %s — liveness blink detection disabled", model_path)
                return None
            opts = vision.FaceLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=model_path),
                running_mode=vision.RunningMode.IMAGE,
                num_faces=1,
                min_face_detection_confidence=0.3,
            )
            _landmarker = vision.FaceLandmarker.create_from_options(opts)
            logger.info("Face landmarker loaded (liveness blink detection active)")
            return _landmarker
        except Exception as exc:
            logger.warning("Face landmarker unavailable (liveness degrades to motion-only): %s", exc)
            return None


def _iou(a: dict, b: dict) -> float:
    """Intersection-over-union of two normalized xyxy boxes."""
    ix1 = max(a["x1"], b["x1"])
    iy1 = max(a["y1"], b["y1"])
    ix2 = min(a["x2"], b["x2"])
    iy2 = min(a["y2"], b["y2"])
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    area_a = max(0.0, (a["x2"] - a["x1"]) * (a["y2"] - a["y1"]))
    area_b = max(0.0, (b["x2"] - b["x1"]) * (b["y2"] - b["y1"]))
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _ear(landmarks, eye_idx: tuple[int, ...]) -> Optional[float]:
    """Eye aspect ratio from FaceMesh landmarks."""
    try:
        p = lambda i: np.array([landmarks[i].x, landmarks[i].y])
        i1, i2, i3, i4, i5, i6 = eye_idx
        a = np.linalg.norm(p(i2) - p(i6))
        b = np.linalg.norm(p(i3) - p(i5))
        c = np.linalg.norm(p(i1) - p(i4))
        if c <= 0:
            return None
        return float((a + b) / (2.0 * c))
    except Exception:
        return None


class _FaceTrack:
    """Blink + motion history for one tracked face."""

    __slots__ = ("box", "ear_samples", "blinks", "motion_samples", "motion_hits",
                 "first_seen", "last_seen", "last_crop")

    def __init__(self, box: dict, now: float):
        self.box = dict(box)
        self.ear_samples: list[float] = []
        self.blinks = 0
        self.motion_samples = 0
        self.motion_hits = 0
        self.first_seen = now
        self.last_seen = now
        self.last_crop: Optional[np.ndarray] = None

    def verdict(self, now: float) -> dict:
        """Return the current liveness verdict for this face."""
        observed = now - self.first_seen
        blinks = self.blinks
        motion_frac = (self.motion_hits / self.motion_samples) if self.motion_samples else 0.0

        if blinks >= LIVE_MIN_BLINKS or motion_frac >= MOTION_LIVE_FRACTION:
            status = "live"
        elif observed >= SUSPICIOUS_MIN_SECONDS:
            status = "suspicious"
        else:
            status = "unverified"
        return {
            "liveness": status,
            "blinks": blinks,
            "observed_seconds": round(observed, 1),
            "motion_fraction": round(motion_frac, 2),
        }


class FaceLivenessTracker:
    """Track multiple faces across samples and attach liveness verdicts.

    Call ``update(frame, boxes)`` on each liveness sample with the (mirrored)
    BGR frame and the current normalized person boxes. The tracker associates
    boxes to tracks by IoU, computes EAR + motion for each, and returns a
    ``{box_key: verdict}`` map plus the per-box verdicts aligned to the input.
    """

    def __init__(self):
        self.tracks: list[_FaceTrack] = []

    def reset(self) -> None:
        self.tracks = []

    def update(self, frame, boxes: list[dict]) -> dict[int, dict]:
        """Process one liveness sample. Returns {box_index: verdict}."""
        landmarker = _load_landmarker()
        now = time.time()
        verdicts: dict[int, dict] = {}

        # Greedy IoU association: newest boxes vs existing tracks.
        used_tracks: set[int] = set()
        for idx, box in enumerate(boxes):
            area = (box["x2"] - box["x1"]) * (box["y2"] - box["y1"])
            if area < _MIN_TRACK_AREA:
                verdicts[idx] = _FaceTrack(box, now).verdict(now)
                continue
            best_t = None
            best_iou = _TRACK_IOU
            for ti, track in enumerate(self.tracks):
                if ti in used_tracks:
                    continue
                iou = _iou(track.box, box)
                if iou >= best_iou:
                    best_iou = iou
                    best_t = ti
            if best_t is None:
                track = _FaceTrack(box, now)
                self.tracks.append(track)
                verdicts[idx] = track.verdict(now)
                continue
            track = self.tracks[best_t]
            used_tracks.add(best_t)
            track.box = dict(box)
            track.last_seen = now
            self._sample_face(frame, box, track, landmarker)
            verdicts[idx] = track.verdict(now)

        # Prune tracks not seen recently (> 4 s) so a person leaving the frame
        # doesn't accumulate stale blink history for a new arrival.
        self.tracks = [t for t in self.tracks if now - t.last_seen < 4.0]
        return verdicts

    def _sample_face(self, frame, box: dict, track: _FaceTrack, landmarker) -> None:
        h, w = frame.shape[:2]
        x1 = max(0, int(box["x1"] * w))
        y1 = max(0, int(box["y1"] * h))
        x2 = min(w, int(box["x2"] * w))
        y2 = min(h, int(box["y2"] * h))
        if x2 - x1 < 24 or y2 - y1 < 24:
            return
        crop = frame[y1:y2, x1:x2]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, (96, 96))

        # ── Motion signal ──
        if track.last_crop is not None:
            diff = float(np.mean(np.abs(gray.astype(np.float32) - track.last_crop.astype(np.float32))))
            track.motion_samples += 1
            if diff >= MOTION_THRESHOLD:
                track.motion_hits += 1
        track.last_crop = gray

        # ── Blink signal (needs the landmarker) ──
        if landmarker is None:
            return
        try:
            import mediapipe as mp

            rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            res = landmarker.detect(mp_img)
            if not res.face_landmarks:
                return
            lm = res.face_landmarks[0]
            left = _ear(lm, _LEFT_EYE)
            right = _ear(lm, _RIGHT_EYE)
            if left is None or right is None:
                return
            ear = (left + right) / 2.0
            track.ear_samples.append(ear)
            # Count a blink: EAR falls below threshold while the previous
            # sample was above (rising edge after a dip). Keep history short.
            if len(track.ear_samples) >= 2:
                prev, cur = track.ear_samples[-2], track.ear_samples[-1]
                if prev > BLINK_EAR_THRESHOLD and cur <= BLINK_EAR_THRESHOLD:
                    track.blinks += 1
                track.ear_samples = track.ear_samples[-3:]
        except Exception as exc:  # noqa: BLE001 - liveness is best-effort
            logger.debug("Liveness EAR sample failed: %s", exc)
