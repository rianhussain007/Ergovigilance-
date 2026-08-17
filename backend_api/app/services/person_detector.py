"""Person bounding-box detection via YOLO11n (ultralytics).

Run on the CPU for the factory laptop: yolo11n is the smallest / fastest
production model (5.6 MB, person class trained in). Detection runs every
``PERSON_DETECT_INTERVAL_S`` seconds in the live pipeline — not on every
frame — so the added cost is a few hundred ms every few seconds, never
contending with pose inference frame-to-frame.

Output boxes are normalized (0-1, xyxy) so callers can draw them at any
resolution. On devices without ultralytics installed the detector degrades
to ``None`` (no boxes) rather than crashing the pipeline — person bounding
boxes are an enhancement, not a pipeline dependency.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# YOLO person class id (COCO).
_PERSON_CLASS = 0

# Confidence floor for a person box to be considered real. YOLO11n on a
# low-res factory feed is noisy below ~0.35; 0.30 keeps borderline detections
# while rejecting background false positives.
PERSON_CONF_THRESHOLD = float(os.environ.get("PERSON_CONF_THRESHOLD", "0.30"))

# How often the live pipeline runs a detection pass (seconds).
PERSON_DETECT_INTERVAL_S = float(os.environ.get("PERSON_DETECT_INTERVAL_S", "2.0"))

# Model is loaded lazily on first use (not at app startup) so a missing
# model file never blocks server boot.
_model: Optional[object] = None
_model_lock = threading.Lock()


def _load_model():
    """Load the YOLO11n model once, thread-safely. Returns None on failure."""
    global _model
    with _model_lock:
        if _model is not None:
            return _model
        try:
            from ultralytics import YOLO
            from app.core.config import settings

            path = getattr(settings, "MODEL_DIR", "models") or "models"
            model_path = os.path.join(path, "yolo11n.pt")
            if not os.path.exists(model_path):
                logger.warning("YOLO model not found at %s — person detection disabled", model_path)
                return None
            model = YOLO(model_path)
            # Warm up on a dummy frame so the first real detection doesn't pay
            # the one-time init cost inside the live loop.
            model.predict(np.zeros((480, 640, 3), np.uint8), verbose=False)
            _model = model
            logger.info("Person detector loaded: %s", model_path)
            return model
        except Exception as exc:
            logger.warning("Person detector unavailable (bounding boxes disabled): %s", exc)
            return None


def detect_persons(frame) -> list[dict]:
    """Return normalized person boxes ``[{x1,y1,x2,y2,confidence}]`` (0-1 xyxy).

    ``frame`` is a BGR numpy array. Returns ``[]`` when the model is
    unavailable or no person meets the confidence threshold. This function
    is safe to call from any thread (ultralytics inference is independent
    per call; the model object itself is read-only after load).
    """
    model = _load_model()
    if model is None:
        return []
    try:
        # Downscale very large frames for detection speed — a 1280x720 frame
        # halves detection latency vs native with negligible box drift, and
        # the live pipeline usually feeds a downscaled inference frame anyway.
        img = frame
        if frame.shape[1] > 640:
            scale = 640 / float(frame.shape[1])
            img = cv2.resize(frame, (640, max(1, int(frame.shape[0] * scale))))
        h, w = img.shape[:2]
        results = model.predict(img, verbose=False, conf=PERSON_CONF_THRESHOLD)
        boxes = []
        if results and results[0].boxes is not None:
            for box in results[0].boxes:
                cls = int(box.cls[0]) if box.cls is not None else -1
                if cls != _PERSON_CLASS:
                    continue
                x1, y1, x2, y2 = [float(v) for v in box.xyxy[0].tolist()]
                conf = float(box.conf[0]) if box.conf is not None else 0.0
                boxes.append({
                    "x1": max(0.0, min(1.0, x1 / w)),
                    "y1": max(0.0, min(1.0, y1 / h)),
                    "x2": max(0.0, min(1.0, x2 / w)),
                    "y2": max(0.0, min(1.0, y2 / h)),
                    "confidence": round(conf, 3),
                })
        return boxes
    except Exception as exc:
        logger.warning("Person detection failed (boxes skipped): %s", exc)
        return []


def reset_person_detector() -> None:
    """Drop the cached model (used by tests to simulate unavailability)."""
    global _model
    with _model_lock:
        _model = None
