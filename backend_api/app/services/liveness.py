"""Face liveness (anti-photo-spoof) detection.

The face recognizer matches geometry — a printed photo or a phone screen
showing an enrolled worker's face produces the same embedding as the live
person, so recognition alone cannot tell a real worker from a photo. Even
motion is not enough: a hand waving a photo moves too.

The decisive signal is **2D vs 3D**. A photo or screen is a flat plane; a
real head has depth. When any planar surface moves, the image motion of its
points is *exactly a homography* (a projective transform). A real 3D head,
rotating or translating, produces **parallax** — points at different depths
move at different rates — which a single homography cannot explain. So:

1. **Planarity test (homography residual)** — fit a homography between two
   consecutive FaceMesh landmark sets with RANSAC. High inlier ratio + low
   residual ⇒ planar ⇒ 2D surface (photo/screen/video). Low inlier ratio ⇒
   parallax ⇒ 3D object (a real person). This defeats *moving* photos and
   video replays, not just held-still ones.
2. **Blink detection (Eye Aspect Ratio)** — a live person blinks every
   2-10 s; a static photo never blinks.
3. **Non-rigid mouth motion** — talking / smiling moves the mouth landmarks
   more than the whole head moves. A rigid photo plane can never do this.
4. **Face-region motion** — distinguishes "no data yet" from "still".

Live signals — a blink, non-rigid mouth motion, or 3D parallax — take
absolute priority: no flat 2D surface can produce any of them, so once one
appears the face is a real person. A real person *walking* also produces
homography-explained (planar) image motion, so the planar → suspicious path
only fires after several seconds of pure planar evidence with zero live
signals. Each detected face is tracked across samples by IoU association, so
multiple people each accumulate their own history. A verdict is attached to
every identity:

- ``live``       — blinks observed, or non-rigid mouth motion, or 3D
                   parallax observed.
- ``suspicious`` — sustained planar (2D) motion with no live signal, or a
                   still face with no blinks (photo / frozen frame / video).
- ``unverified`` — not enough samples yet.

Honest limitation: a rigid, expressionless, blink-less face moving only in
rigid translation is mathematically indistinguishable from a photo of a face
moving the same way with a single monocular camera. The tracker errs toward
``suspicious`` in that genuinely ambiguous case — the SAFE direction —
instead of the old behavior of reporting the face as physically present.

The live pipeline samples liveness at ~2-4 Hz (its own throttle, faster than
the 2 s identity pass) so blinks — which last ~150-400 ms — are not missed.

Design notes:
- FaceLandmarker loads lazily and is optional: if the model is missing, the
  tracker degrades to motion-only verdicts (still photos are caught by the
  no-motion rule; moving photos degrade to ``unverified``), and if the
  landmarker is also unavailable every face is ``unverified``. Liveness is a
  best-effort gate, never a pipeline blocker.
- The tracker is stateless across service restarts; a fresh
  ``FaceLivenessTracker`` should be created per session or kept on the
  service instance.
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
SUSPICIOUS_MIN_SECONDS = float(os.environ.get("SUSPICIOUS_MIN_SECONDS", "6.0"))
# Planar (2D) motion must persist this long (with no live signal appearing)
# before the face flips to suspicious. Deliberately as long as the frozen
# rule: a real person walking produces homography-explained (planar) motion
# too, but virtually every real person blinks or moves their mouth within a
# few seconds — so 6 s of pure planar evidence with zero live signals is a
# high-confidence "this is a flat surface" verdict, not a false positive.
PLANAR_SUSPICIOUS_SECONDS = float(os.environ.get("PLANAR_SUSPICIOUS_SECONDS", "6.0"))
# Blinks at or above this confirm liveness outright.
LIVE_MIN_BLINKS = int(os.environ.get("LIVE_MIN_BLINKS", "1"))
# Mean-abs-diff (8-bit grayscale) above this counts as "motion" in the crop.
MOTION_THRESHOLD = 1.0
# Faces with a larger box area are tracked more reliably; ignore tiny boxes.
_MIN_TRACK_AREA = 0.01

# ── Planarity test thresholds ────────────────────────────────────────────
# RANSAC inlier ratio at or above this means the landmark motion is fully
# explained by a single homography -> a flat 2D surface (photo/screen).
PLANAR_INLIER_RATIO = float(os.environ.get("PLANAR_INLIER_RATIO", "0.92"))
# RANSAC inlier ratio at or below this means the motion has real parallax ->
# a 3D object (a live head). Values between the two are ambiguous.
PARALLAX_INLIER_RATIO = float(os.environ.get("PARALLAX_INLIER_RATIO", "0.72"))
# Homography fit is only meaningful when the face actually moved between
# samples (mean landmark displacement in normalized units).
_MIN_LANDMARK_DISPLACEMENT = 0.004
# Minimum number of landmarks for a homography fit.
_MIN_HOMOGRAPHY_POINTS = 12
# How much planar (2D) evidence (as a fraction of decided samples) is needed
# to call the face suspicious.
PLANAR_DECIDED_FRACTION = float(os.environ.get("PLANAR_DECIDED_FRACTION", "0.6"))
# How much parallax (3D) evidence is needed to call the face live.
PARALLAX_DECIDED_FRACTION = float(os.environ.get("PARALLAX_DECIDED_FRACTION", "0.6"))

# MediaPipe FaceMesh eye landmark indices used for EAR.
_LEFT_EYE = (33, 160, 158, 133, 153, 144)
_RIGHT_EYE = (362, 385, 387, 263, 373, 380)
# Mouth-region landmarks — a talking/expressing face moves these
# NON-RIGIDLY (independent of any global head transform), which a rigid
# photo plane can never do. Used as a live-person signal alongside blinks.
_MOUTH_INDICES = (61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 409, 270, 269, 267, 0, 37, 39, 40, 185)

# Non-rigid (mouth/expression) motion: fraction of samples where the mouth
# region moved significantly beyond what the global homography predicts.
NONRIGID_LIVE_FRACTION = float(os.environ.get("NONRIGID_LIVE_FRACTION", "0.3"))
# A mouth-region displacement above this (normalized units) counts as
# non-rigid motion, provided it exceeds the global rigid prediction.
NONRIGID_MIN_DISPLACEMENT = float(os.environ.get("NONRIGID_MIN_DISPLACEMENT", "0.004"))

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
                logger.warning("face_landmarker.task not found at %s — liveness blink/planarity disabled", model_path)
                return None
            opts = vision.FaceLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=model_path),
                running_mode=vision.RunningMode.IMAGE,
                num_faces=1,
                min_face_detection_confidence=0.3,
            )
            _landmarker = vision.FaceLandmarker.create_from_options(opts)
            logger.info("Face landmarker loaded (liveness blink + planarity active)")
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


def _landmark_points(landmarks) -> Optional[np.ndarray]:
    """Extract all 2D (x, y) landmarks as an Nx2 array, or None."""
    try:
        pts = np.array([[lm.x, lm.y] for lm in landmarks], dtype=np.float32)
        return pts if pts.shape[0] >= _MIN_HOMOGRAPHY_POINTS else None
    except Exception:
        return None


def _planarity(prev: np.ndarray, cur: np.ndarray) -> Optional[tuple[float, float]]:
    """Fit a homography between two landmark sets.

    Returns ``(inlier_ratio, mean_residual)`` or None when the displacement is
    too small to be meaningful. High inlier ratio + low residual means the
    motion is fully explained by a single plane -> 2D surface. Low inlier
    ratio means parallax -> 3D object.
    """
    disp = float(np.mean(np.linalg.norm(cur - prev, axis=1)))
    if disp < _MIN_LANDMARK_DISPLACEMENT:
        return None
    try:
        # RANSAC reprojection threshold must scale with the data: landmarks
        # are normalized 0-1, so a fixed 3.0 (pixel-scale) threshold makes the
        # fit degenerate and findHomography returns None. Use a small
        # normalized threshold — a planar object fits with sub-0.01 residual.
        H, mask = cv2.findHomography(prev, cur, cv2.RANSAC, ransacReprojThreshold=0.015)
        if H is None or mask is None:
            return None
        mask = mask.ravel().astype(bool)
        n = int(mask.sum())
        if n < _MIN_HOMOGRAPHY_POINTS:
            return None
        inlier_ratio = n / float(len(mask))
        # Mean reprojection residual on inliers (normalized units).
        projected = cv2.perspectiveTransform(prev[mask].reshape(-1, 1, 2), H).reshape(-1, 2)
        residual = float(np.mean(np.linalg.norm(projected - cur[mask], axis=1)))
        return inlier_ratio, residual
    except cv2.error:
        return None


class _FaceTrack:
    """Planarity + blink + motion + non-rigid history for one tracked face."""

    __slots__ = ("box", "ear_samples", "blinks", "motion_samples", "motion_hits",
                 "planar_samples", "parallax_samples", "decided_samples",
                 "nonrigid_samples", "nonrigid_total",
                 "first_seen", "last_seen", "last_crop", "last_points")

    def __init__(self, box: dict, now: float):
        self.box = dict(box)
        self.ear_samples: list[float] = []
        self.blinks = 0
        self.motion_samples = 0
        self.motion_hits = 0
        self.planar_samples = 0      # samples classified as 2D (homography fits)
        self.parallax_samples = 0    # samples classified as 3D (parallax)
        self.decided_samples = 0     # samples with a decisive planarity reading
        self.nonrigid_samples = 0    # samples with mouth motion beyond the head transform
        self.nonrigid_total = 0      # samples where mouth motion was measurable
        self.first_seen = now
        self.last_seen = now
        self.last_crop: Optional[np.ndarray] = None
        self.last_points: Optional[np.ndarray] = None

    def verdict(self, now: float) -> dict:
        """Return the current liveness verdict for this face.

        Live signals take ABSOLUTE priority over spoof evidence: a blink, a
        non-rigid mouth/expression movement, or 3D parallax can only come
        from a real person — no flat 2D surface can produce any of them. A
        real person walking produces homography-explained (planar) image
        motion too, so the planar -> suspicious path is only reached when
        NONE of those live signals has ever appeared.
        """
        observed = now - self.first_seen
        blinks = self.blinks
        motion_frac = (self.motion_hits / self.motion_samples) if self.motion_samples else 0.0
        planar_frac = (self.planar_samples / self.decided_samples) if self.decided_samples else 0.0
        parallax_frac = (self.parallax_samples / self.decided_samples) if self.decided_samples else 0.0
        nonrigid_frac = (self.nonrigid_samples / self.nonrigid_total) if self.nonrigid_total else 0.0

        # ── Live signals — no 2D surface can produce these ──
        if blinks >= LIVE_MIN_BLINKS:
            status = "live"
        elif nonrigid_frac >= NONRIGID_LIVE_FRACTION:
            status = "live"
        elif parallax_frac >= PARALLAX_DECIDED_FRACTION:
            # Real 3D head rotation — parallax no flat plane can explain.
            status = "live"
        # ── Spoof evidence — only when no live signal has ever appeared ──
        elif planar_frac >= PLANAR_DECIDED_FRACTION and observed >= PLANAR_SUSPICIOUS_SECONDS:
            # Sustained motion fully explained by a single homography -> a
            # flat 2D surface (a waved photo / phone screen) at the camera.
            status = "suspicious"
        elif observed >= SUSPICIOUS_MIN_SECONDS and motion_frac < 0.05:
            # Face frozen in place, no blinks -> held-still photo / frozen frame.
            status = "suspicious"
        else:
            status = "unverified"
        return {
            "liveness": status,
            "blinks": blinks,
            "observed_seconds": round(observed, 1),
            "motion_fraction": round(motion_frac, 2),
            "planar_fraction": round(planar_frac, 2),
            "parallax_fraction": round(parallax_frac, 2),
            "nonrigid_fraction": round(nonrigid_frac, 2),
        }


class FaceLivenessTracker:
    """Track multiple faces across samples and attach liveness verdicts.

    Call ``update(frame, boxes)`` on each liveness sample with the (mirrored)
    BGR frame and the current normalized person boxes. The tracker associates
    boxes to tracks by IoU, computes planarity + EAR + motion for each, and
    returns a ``{box_key: verdict}`` map aligned to the input boxes.
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
        # doesn't accumulate stale history for a new arrival.
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

        # ── Blink + planarity signals (need the landmarker) ──
        if landmarker is None:
            return
        try:
            import mediapipe as mp

            rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            res = landmarker.detect(mp_img)
            if not res.face_landmarks:
                track.last_points = None
                return
            lm = res.face_landmarks[0]

            # Blink (EAR)
            left = _ear(lm, _LEFT_EYE)
            right = _ear(lm, _RIGHT_EYE)
            if left is not None and right is not None:
                ear = (left + right) / 2.0
                track.ear_samples.append(ear)
                if len(track.ear_samples) >= 2:
                    prev, cur = track.ear_samples[-2], track.ear_samples[-1]
                    if prev > BLINK_EAR_THRESHOLD and cur <= BLINK_EAR_THRESHOLD:
                        track.blinks += 1
                    track.ear_samples = track.ear_samples[-3:]

            # Planarity (2D vs 3D) — the decisive anti-photo test.
            points = _landmark_points(lm)
            if points is None:
                track.last_points = None
                return
            if track.last_points is not None:
                result = _planarity(track.last_points, points)
                if result is not None:
                    inlier_ratio, _residual = result
                    track.decided_samples += 1
                    if inlier_ratio >= PLANAR_INLIER_RATIO:
                        track.planar_samples += 1
                    elif inlier_ratio <= PARALLAX_INLIER_RATIO:
                        track.parallax_samples += 1

                # Non-rigid (mouth/expression) motion — a live-person signal a
                # rigid 2D plane can never produce. If the mouth region moved
                # MORE than the whole face moved, that is an expression
                # change (talk / smile), not the head translating rigidly.
                try:
                    mouth_prev = track.last_points[list(_MOUTH_INDICES)]
                    mouth_cur = points[list(_MOUTH_INDICES)]
                    mouth_disp = float(np.mean(np.linalg.norm(mouth_cur - mouth_prev, axis=1)))
                    global_disp = float(np.mean(np.linalg.norm(points - track.last_points, axis=1)))
                    track.nonrigid_total += 1
                    if mouth_disp > global_disp + NONRIGID_MIN_DISPLACEMENT:
                        track.nonrigid_samples += 1
                except (IndexError, ValueError):
                    pass
            track.last_points = points
        except Exception as exc:  # noqa: BLE001 - liveness is best-effort
            logger.debug("Liveness sample failed: %s", exc)
