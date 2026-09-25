"""YOLO Cloud Pose Engine — YOLOv8-pose inference + ByteTrack worker tracking.

Processes frames from RTSP streams through:
1. YOLOv8-pose: detects persons + 17-keypoint pose
2. ByteTrack: tracks individual workers across frames
3. Feature extraction: uses the SAME extract_features_from_keypoints()
   as the MediaPipe core, with COCO_17 index map
4. ML inference: trained task + risk classifiers (HistGradientBoosting)
   replace hardcoded heuristics with data-driven predictions

YOLOv8-pose keypoints (COCO format, 17 points):
  0: nose, 1: left_eye, 2: right_eye, 3: left_ear, 4: right_ear,
  5: left_shoulder, 6: right_shoulder, 7: left_elbow, 8: right_elbow,
  9: left_wrist, 10: right_wrist, 11: left_hip, 12: right_hip,
  13: left_knee, 14: right_knee, 15: left_ankle, 16: right_ankle

Trained models (in models/ directory):
  - yolo_risk_model.pkl: risk classifier (LOW/MEDIUM/HIGH)
  - yolo_task_model.pkl: task classifier (7 task classes)
  - Trained on COCO_17 features from REBA dataset (30K+ samples)
  - Falls back to heuristic scoring if models are unavailable
"""

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from yolo_cloud.config import settings
from yolo_cloud.stations import get_station_store

# Shared feature extraction from the MediaPipe core (works for COCO_17 too)
try:
    from backend.core.constants import COCO_17, FEATURE_COLUMNS
    from backend.services.features import (
        extract_features_from_keypoints,
        risk_from_features,
    )
    _HAS_FEATURE_EXTRACTOR = True
except ImportError:
    _HAS_FEATURE_EXTRACTOR = False
    COCO_17 = None
    FEATURE_COLUMNS = []

# Shared task recognition engine (temporal smoothing, geometric gate, ML model)
try:
    from shared.task_recognition import TaskRecognitionEngine, extract_features_from_landmarks
    _HAS_SHARED_ENGINE = True
except ImportError:
    _HAS_SHARED_ENGINE = False

logger = logging.getLogger(__name__)


# ── COCO Keypoint indices ───────────────────────────────────────────────────
NOSE = 0
LEFT_EYE = 1
RIGHT_EIGHT = 2
LEFT_EAR = 3
RIGHT_EAR = 4
LEFT_SHOULDER = 5
RIGHT_SHOULDER = 6
LEFT_ELBOW = 7
RIGHT_ELBOW = 8
LEFT_WRIST = 9
RIGHT_WRIST = 10
LEFT_HIP = 11
RIGHT_HIP = 12
LEFT_KNEE = 13
RIGHT_KNEE = 14
LEFT_ANKLE = 15
RIGHT_ANKLE = 16

# Exponential moving average applied to each track's own risk series, so one
# noisy frame cannot swing a worker's tile score. With alpha=0.6 a new sample
# contributes 60% and the running value 40%.
RISK_EMA_ALPHA = 0.6


def _per_hour(count: int, elapsed_seconds: float) -> float:
    """Rate per hour, so a short run and a four-hour run are comparable."""
    if elapsed_seconds <= 0:
        return 0.0
    return round(count * 3600.0 / elapsed_seconds, 1)


@dataclass
class TrackedPose:
    """A tracked worker's pose with angles and risk."""
    track_id: int
    bbox: list[float]          # [x1, y1, x2, y2] normalized
    keypoints: list[list[float]]  # [[x, y, confidence], ...] × 17
    angles: dict[str, float]   # computed joint angles
    risk_level: str            # LOW, MEDIUM, HIGH
    risk_score: float          # 0-100
    confidence: float          # overall detection confidence
    task: str                  # inferred task type
    # Pure geometric joint angles (neck/trunk/...) in degrees. Kept apart from
    # ``angles`` because the ML path merges the feature vector into that dict;
    # this is the dict the live ``persons[]`` payload publishes.
    joint_angles: dict[str, float] = field(default_factory=dict)
    # Station ROI this track's bbox centroid falls inside (None when unmapped).
    station_id: Optional[str] = None
    station_name: Optional[str] = None
    # Per-tile capture-quality flags for the UI banner. Informational only —
    # these are NEVER inputs to task or risk scoring.
    quality: dict = field(default_factory=dict)


@dataclass
class ProcessedCloudFrame:
    """Result of processing one frame through the cloud pipeline."""
    frame_width: int
    frame_height: int
    tracked_poses: list[TrackedPose]
    person_count: int
    inference_ms: float
    timestamp: float


class _SimpleTracker:
    """Dependency-free IoU tracker used when the ultralytics ByteTrack
    instance is unavailable.

    Greedy IoU association with a lost-track buffer, so a worker that is briefly
    occluded keeps the same ``track_id`` when re-detected. IDs are monotonically
    increasing and never reused, which makes an ID switch always visible (a new
    id appears rather than one worker silently absorbing another's id).
    """

    def __init__(self, iou_thresh: float = 0.3, max_lost: Optional[int] = None):
        self.iou_thresh = float(iou_thresh)
        self.max_lost = int(
            max_lost if max_lost is not None else getattr(settings, "TRACK_BUFFER", 30)
        )
        self._tracks: dict[int, dict] = {}
        self._next_id = 1
        self._frame = 0
        # Tracking audit (QA). A fresh id landing where a recently expired track
        # sat is the tracker losing and re-acquiring the same worker, i.e. the
        # occlusion / cross-over artifact this metric exists to expose.
        self.new_tracks = 0
        self.expired_tracks = 0
        self.reacquisitions = 0
        self._expired: deque = deque(maxlen=max(4, self.max_lost * 2))

    @staticmethod
    def _iou(a, b) -> float:
        ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
        ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
        inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
        if inter <= 0:
            return 0.0
        area = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
        return inter / area if area > 0 else 0.0

    def update(self, det_boxes, det_confs, kps) -> list[dict]:
        """Associate detections to tracks; returns emitted tracks for this frame."""
        self._frame += 1
        det_boxes = [list(map(float, b)) for b in det_boxes]
        results: list[dict] = []
        claimed_dets: set[int] = set()
        claimed_tracks: set[int] = set()

        # Best-first greedy match against live (incl. briefly lost) tracks.
        candidates = []
        for di, dbox in enumerate(det_boxes):
            for tid, tr in self._tracks.items():
                iou = self._iou(dbox, tr["bbox"])
                if iou >= self.iou_thresh:
                    candidates.append((iou, di, tid))
        candidates.sort(key=lambda c: c[0], reverse=True)
        for _iou, di, tid in candidates:
            if di in claimed_dets or tid in claimed_tracks:
                continue
            claimed_dets.add(di)
            claimed_tracks.add(tid)
            tr = self._tracks[tid]
            tr["bbox"] = det_boxes[di]
            tr["last_seen"] = self._frame
            tr["hits"] = tr.get("hits", 0) + 1
            results.append({
                "track_id": tid,
                "bbox": list(det_boxes[di]),
                "conf": float(det_confs[di]),
                "kps": kps[di] if kps is not None else None,
            })

        # Unmatched detections become new tracks (IDs are never reused).
        for di, dbox in enumerate(det_boxes):
            if di in claimed_dets:
                continue
            if self._is_reacquisition(dbox):
                self.reacquisitions += 1
            self.new_tracks += 1
            tid = self._next_id
            self._next_id += 1
            self._tracks[tid] = {"bbox": dbox, "last_seen": self._frame, "hits": 1}
            results.append({
                "track_id": tid,
                "bbox": list(dbox),
                "conf": float(det_confs[di]),
                "kps": kps[di] if kps is not None else None,
            })

        # Drop tracks missing for longer than the occlusion buffer, remembering
        # where they were so a fresh id in the same place can be spotted.
        for tid in [
            t for t, tr in self._tracks.items()
            if self._frame - tr["last_seen"] > self.max_lost
        ]:
            self._expired.append((self._tracks[tid]["bbox"], self._frame))
            self.expired_tracks += 1
            del self._tracks[tid]
        return results

    # Overlap that counts as "same place" when checking for a re-acquisition.
    # Deliberately loose: the tracker already failed to associate, so the box has
    # usually moved and strict IoU would miss exactly the case being measured.
    REACQUISITION_IOU = 0.2

    def _is_reacquisition(self, box) -> bool:
        """Did this new id appear where a just-expired track used to be?

        Counts the tracker losing and re-acquiring one worker (occlusion or a
        cross-over). A genuinely different worker arriving at the same spot also
        trips it, so the count is an upper bound, not a ground-truth flip rate.
        """
        for expired_box, expired_frame in self._expired:
            if self._frame - expired_frame > self.max_lost:
                continue
            if self._iou(box, expired_box) >= self.REACQUISITION_IOU:
                return True
        return False

    def audit_snapshot(self) -> dict:
        """Tracker counters for the tracking audit."""
        return {
            "new_tracks": self.new_tracks,
            "expired_tracks": self.expired_tracks,
            "reacquisitions": self.reacquisitions,
            "live_tracks": len(self._tracks),
            "frames": self._frame,
        }


class YOLOPoseEngine:
    """YOLOv8-pose inference with ByteTrack worker tracking."""

    # Heuristic fallback thresholds (used only when ML models unavailable)
    TASK_THRESHOLDS = {
        "lifting": {"knee_angle_max": 120, "trunk_angle_min": 20},
        "reaching": {"shoulder_angle_min": 60},
        "assembly": {"elbow_angle_min": 90, "elbow_angle_max": 150},
        "standing": {"knee_angle_min": 160, "trunk_angle_max": 15},
        "sitting": {"hip_angle_max": 100},
    }



    def __init__(self):
        self._model = None
        # Trackers are PER CAMERA. A single shared tracker would put boxes from
        # different cameras into one id space and could hand the same track_id two
        # different workers on two different cameras.
        self._simple_trackers: dict[str, _SimpleTracker] = {}
        self._camera_trackers: dict[str, object] = {}
        self._bytetrack_cls = None
        self._risk_model = None
        self._task_model = None
        self._initialized = False
        # Per-(camera, worker) task engines (smoothing + geometric gate)
        self._task_engines: dict[tuple[str, int], 'TaskRecognitionEngine'] = {}
        # Per-track EMA state and last-seen marks, keyed the same way. Track ids
        # are never reused, so this state is evicted (see _prune_track_state)
        # instead of accumulating one entry per worker who ever appeared.
        self._risk_ema: dict[tuple[str, int], float] = {}
        self._track_last_seen: dict[tuple[str, int], int] = {}
        self._frame_index = 0
        self._shared_engine_class = TaskRecognitionEngine if _HAS_SHARED_ENGINE else None
        # Feature column order expected by the trained risk/task models. The
        # shipped YOLO models were trained on their own 13-column subset, so the
        # bundle's list wins; FEATURE_COLUMNS is only a fallback.
        self._risk_features: list[str] = list(FEATURE_COLUMNS)
        self._task_features: list[str] = list(FEATURE_COLUMNS)

    def initialize(self) -> None:
        """Load YOLOv8-pose model and ByteTrack tracker."""
        if self._initialized:
            return

        try:
            from ultralytics import YOLO
            self._model = YOLO(settings.YOLO_MODEL)
            logger.info("YOLO model loaded: %s", settings.YOLO_MODEL)
        except Exception as exc:
            logger.error("Failed to load YOLO model: %s", exc)
            raise

        # Tracker capability probe only — instances are created lazily per camera
        # by _tracker_for() so tracker state is never shared across cameras.
        self._bytetrack_cls = None
        try:
            from ultralytics.trackers import ByteTrack
            self._bytetrack_cls = ByteTrack
            logger.info("ByteTrack available — per-camera tracker instances")
        except Exception as exc:  # noqa: BLE001 - any tracker failure degrades
            logger.warning(
                "ByteTrack unavailable (%s) — using built-in IoU tracker", exc
            )

        # Load trained ML models
        self._load_ml_models()

        self._initialized = True

    def _load_ml_models(self) -> None:
        """Load trained risk and task classifiers for COCO_17 features."""
        risk_path = Path(settings.YOLO_RISK_MODEL)
        task_path = Path(settings.YOLO_TASK_MODEL)
        try:
            import joblib
            if risk_path.exists():
                bundle = joblib.load(risk_path)
                self._risk_model = bundle["model"] if isinstance(bundle, dict) and "model" in bundle else bundle
                if isinstance(bundle, dict) and bundle.get("features"):
                    self._risk_features = list(bundle["features"])
                logger.info("YOLO risk model loaded: %s", risk_path.name)
            else:
                logger.warning(
                    "YOLO risk model not found at %s — using heuristic fallback. "
                    "Run: python -m yolo_cloud.training.train_yolo_risk_model",
                    risk_path,
                )
            if task_path.exists():
                bundle = joblib.load(task_path)
                self._task_model = bundle["model"] if isinstance(bundle, dict) and "model" in bundle else bundle
                if isinstance(bundle, dict) and bundle.get("features"):
                    self._task_features = list(bundle["features"])
                logger.info("YOLO task model loaded: %s", task_path.name)
            else:
                logger.warning(
                    "YOLO task model not found at %s — using heuristic fallback. "
                    "Run: python -m yolo_cloud.training.train_yolo_task_model",
                    task_path,
                )
        except Exception as exc:
            logger.warning("Failed to load ML models: %s — using heuristic fallback", exc)
            self._risk_model = None
            self._task_model = None

    def _tracker_for(self, camera_key: str):
        """Per-camera tracker instance (ByteTrack when usable, else IoU)."""
        inst = self._camera_trackers.get(camera_key)
        if inst is not None:
            return inst
        if self._bytetrack_cls is not None:
            try:
                inst = self._bytetrack_cls(
                    track_thresh=settings.TRACK_THRESH,
                    track_buffer=settings.TRACK_BUFFER,
                    match_thresh=settings.MATCH_THRESH,
                    min_hits=settings.MIN_HITS,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("ByteTrack construction failed (%s) — IoU tracker", exc)
                inst = None
        if inst is None:
            inst = self._simple_trackers.get(camera_key)
            if inst is None:
                inst = _SimpleTracker()
                self._simple_trackers[camera_key] = inst
        self._camera_trackers[camera_key] = inst
        return inst

    def process_frame(
        self, frame: np.ndarray, camera_id: Optional[str] = None,
    ) -> ProcessedCloudFrame:
        """Process a single frame through YOLOv8-pose + tracking.

        ``camera_id`` scopes tracker + task-engine state per camera; omitting it
        keeps the legacy single-stream behaviour (one shared "" bucket).
        """
        if not self._initialized:
            self.initialize()

        t_start = time.perf_counter()
        h, w = frame.shape[:2]
        # Per-camera bucket for the tracker and all per-track state (the empty
        # string preserves the legacy single-stream behaviour).
        camera_key = str(camera_id or "")
        self._frame_index += 1

        # Run YOLOv8-pose inference
        results = self._model(
            frame,
            conf=settings.YOLO_CONFIDENCE,
            device=settings.YOLO_DEVICE,
            imgsz=settings.YOLO_IMGSZ,
            verbose=False,
        )

        # Extract detections
        poses = []
        if results and len(results) > 0:
            result = results[0]
            boxes = result.boxes
            keypoints = result.keypoints

            if boxes is not None and len(boxes) > 0:
                # Prepare for ByteTrack
                det_boxes = boxes.xyxy.cpu().numpy()
                det_confs = boxes.conf.cpu().numpy()
                kps = keypoints.data.cpu().numpy() if keypoints is not None else None

                # Association — ultralytics ByteTrack when usable, otherwise the
                # built-in IoU tracker. Both yield stable track_ids that survive
                # brief occlusions, and both are per camera.
                if len(det_boxes) == 0:
                    tracked = []
                else:
                    tracker = self._tracker_for(camera_key)
                    if isinstance(tracker, _SimpleTracker):
                        tracked = tracker.update(det_boxes, det_confs, kps)
                    else:
                        # ByteTrack expects [x1, y1, x2, y2, conf]
                        det_input = np.column_stack([det_boxes, det_confs])
                        online_targets = tracker.update(det_input, frame, frame)
                        tracked = []
                        for target in online_targets:
                            x1, y1, bw, bh = target.tlwh
                            x2, y2 = x1 + bw, y1 + bh
                            tracked.append({
                                "track_id": int(target.track_id),
                                "bbox": [x1, y1, x2, y2],
                                "conf": None,
                                "kps": self._find_closest_keypoints(
                                    det_boxes, det_confs, kps, x1, y1, x2, y2
                                ),
                            })

                for t in tracked:
                    if t["kps"] is None:
                        continue
                    pose = self._process_tracked_pose(
                        t["track_id"], t["bbox"], t["kps"], w, h, frame, camera_key
                    )
                    if t.get("conf") is not None:
                        pose.confidence = float(t["conf"])
                    poses.append(pose)

        # Evict per-track state for workers this camera no longer reports.
        self._prune_track_state(camera_key, {int(p.track_id) for p in poses})

        inference_ms = (time.perf_counter() - t_start) * 1000

        return ProcessedCloudFrame(
            frame_width=w,
            frame_height=h,
            tracked_poses=poses,
            person_count=len(poses),
            inference_ms=inference_ms,
            timestamp=time.time(),
        )

    # Frames a track may be absent before its state is dropped. Track ids are
    # never reused, so state can only be released this way.
    TRACK_STATE_TTL_FRAMES = 300

    def _station_for(self, camera_key: str, cx: float, cy: float) -> Optional[dict]:
        """Station ROI whose polygon contains this track's centroid.

        Keyed by camera, so the same track id on another camera never resolves to
        this camera's workstation. Best-effort: station geometry must never break
        pose processing, so any store failure degrades to "unmapped".
        """
        if not camera_key:
            return None
        try:
            return get_station_store().station_for_point(camera_key, cx, cy)
        except Exception as exc:  # noqa: BLE001 - never break a frame for a polygon
            logger.debug("Station lookup failed for camera %s: %s", camera_key, exc)
            return None

    def _smooth_risk(self, key: tuple[str, int], risk_score: float) -> float:
        """EMA over one track's own risk series (see RISK_EMA_ALPHA).

        State is keyed by ``(camera_key, track_id)`` so two workers in the same
        frame never share a filter. A track's first sample passes through
        unchanged — there is no warm-up penalty.
        """
        self._track_last_seen[key] = self._frame_index
        prev = self._risk_ema.get(key)
        if prev is None:
            self._risk_ema[key] = float(risk_score)
            return float(risk_score)
        smoothed = RISK_EMA_ALPHA * float(risk_score) + (1.0 - RISK_EMA_ALPHA) * float(prev)
        self._risk_ema[key] = smoothed
        return smoothed

    def tracking_audit(self, elapsed_seconds: float = 0.0) -> dict:
        """Per-camera tracking audit for cross-over / occlusion review.

        ByteTrack is NOT usable in this build (``from ultralytics.trackers import
        ByteTrack`` fails), so these counters come from the built-in IoU tracker
        that is actually running — instrumenting ByteTrack here would instrument
        dead code. Definitions:

        * ``new_tracks`` — every fresh id issued. Ids are never reused, so this
          is the honest identity-churn counter, not a flip rate.
        * ``reacquisitions`` — a fresh id issued where a track that expired within
          the occlusion buffer used to be: the tracker lost and re-acquired one
          worker. An upper bound on true flips (a different worker arriving at the
          same spot also counts).
        * ``expired_tracks`` — ids retired after the lost-track buffer elapsed.

        Distinct from ``TrackIdentityRegistry.switch_count``, which counts a
        *bound* track changing worker (a badge/id mismatch), not tracker churn.
        """
        per_camera: dict = {}
        totals = {
            "new_tracks": 0,
            "expired_tracks": 0,
            "reacquisitions": 0,
            "live_tracks": 0,
        }
        for camera_key, tracker in self._simple_trackers.items():
            snapshot = tracker.audit_snapshot()
            per_camera[camera_key or "(default)"] = snapshot
            for key in totals:
                totals[key] += int(snapshot.get(key, 0))

        return {
            "active_tracker": "_SimpleTracker (IoU)",
            "bytetrack_available": bool(self._bytetrack_cls),
            "per_camera": per_camera,
            "totals": totals,
            "per_hour": {
                key: _per_hour(totals[key], elapsed_seconds)
                for key in ("new_tracks", "expired_tracks", "reacquisitions")
            },
            "elapsed_seconds": round(elapsed_seconds, 1),
        }

    def _prune_track_state(self, camera_key: str, active_ids: set[int]) -> None:
        """Drop per-track state for tracks this camera is no longer reporting.

        Task engines, EMA filters and last-seen marks are keyed by
        ``(camera_key, track_id)``; without eviction every worker who ever walked
        past would keep an engine and its smoothing deques alive for the life of
        the process. The TTL keeps a brief occlusion from resetting smoothing.
        """
        for key in list(self._track_last_seen):
            cam, track_id = key
            if cam != camera_key:
                continue
            if track_id in active_ids:
                continue
            if self._frame_index - self._track_last_seen[key] > self.TRACK_STATE_TTL_FRAMES:
                self._track_last_seen.pop(key, None)
                self._task_engines.pop(key, None)
                self._risk_ema.pop(key, None)

    def _find_closest_keypoints(
        self, boxes, confs, kps, tx1, ty1, tx2, ty2
    ) -> Optional[np.ndarray]:
        """Find the original detection keypoints closest to a tracked target box."""
        if kps is None:
            return None
        best_iou = 0
        best_idx = 0
        for i, box in enumerate(boxes):
            bx1, by1, bx2, by2 = box
            # IoU calculation
            ix1 = max(tx1, bx1)
            iy1 = max(ty1, by1)
            ix2 = min(tx2, bx2)
            iy2 = min(ty2, by2)
            inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
            area_a = (tx2 - tx1) * (ty2 - ty1)
            area_b = (bx2 - bx1) * (by2 - by1)
            union = area_a + area_b - inter
            iou = inter / union if union > 0 else 0
            if iou > best_iou:
                best_iou = iou
                best_idx = i
        return kps[best_idx] if best_iou > 0.3 else kps[best_idx]

    def _process_tracked_pose(
        self,
        track_id: int,
        bbox: list,
        kps_data: np.ndarray,
        frame_w: int,
        frame_h: int,
        frame: np.ndarray,
        camera_key: str = "",
    ) -> TrackedPose:
        """Process a single tracked person's pose.

        Uses the same feature extraction as the MediaPipe core
        (extract_features_from_keypoints with COCO_17) and trained ML
        classifiers for task + risk prediction.
        """
        # Normalize bbox
        norm_bbox = [
            bbox[0] / frame_w,
            bbox[1] / frame_h,
            bbox[2] / frame_w,
            bbox[3] / frame_h,
        ]

        # Station mapping from the bbox centroid: which workstation is this
        # person standing at? Normalized, matching the polygon coordinate space.
        centroid = (
            (norm_bbox[0] + norm_bbox[2]) / 2.0,
            (norm_bbox[1] + norm_bbox[3]) / 2.0,
        )
        station = self._station_for(camera_key, centroid[0], centroid[1])

        # Normalize keypoints (x, y, confidence)
        keypoints = []
        for kp in kps_data:
            if len(kp) >= 3:
                keypoints.append([kp[0] / frame_w, kp[1] / frame_h, float(kp[2])])
            else:
                keypoints.append([0, 0, 0])

        # Overall confidence from keypoint visibility
        valid_confs = [kp[2] for kp in keypoints if kp[2] > 0]
        confidence = sum(valid_confs) / len(valid_confs) if valid_confs else 0.0

        # Per-tile capture-quality flags (display-only; never used in scoring).
        quality = self._assess_tile_quality(frame, norm_bbox, keypoints)

        # ── ML-based path (preferred) ──────────────────────────────────
        if _HAS_FEATURE_EXTRACTOR and COCO_17 is not None:
            # Convert to array with visibility channel for the shared extractor
            kps_arr = np.zeros((17, 4), dtype=float)
            for i, kp in enumerate(keypoints[:17]):
                if len(kp) >= 3 and kp[2] > 0:
                    kps_arr[i, 0] = kp[0] * frame_w  # denormalize for extractor
                    kps_arr[i, 1] = kp[1] * frame_h
                    kps_arr[i, 3] = kp[2]  # visibility
                else:
                    kps_arr[i] = float("nan")

            features, unavailable, _ = extract_features_from_keypoints(kps_arr, COCO_17)

            # Task classification via shared engine (temporal smoothing + geometric gate + ML)
            if _HAS_SHARED_ENGINE:
                # Get or create the per-(camera, worker) task recognition engine
                engine_key = (camera_key, int(track_id))
                if engine_key not in self._task_engines:
                    task_path = Path(settings.YOLO_TASK_MODEL)
                    model_path = str(task_path) if task_path.exists() else None
                    self._task_engines[engine_key] = TaskRecognitionEngine(model_path=model_path)
                engine = self._task_engines[engine_key]
                # Convert COCO_17 keypoints to 33-landmark format for the shared engine
                kps_33 = np.zeros((33, 4))
                kps_33[:, 3] = 0.5  # default visibility
                # COCO_17 -> MediaPipe mapping
                coco_to_mp = {0: 0, 5: 11, 6: 12, 7: 13, 8: 14, 9: 15, 10: 16,
                              11: 23, 12: 24, 13: 25, 14: 26, 15: 27, 16: 28}
                for coco_idx, mp_idx in coco_to_mp.items():
                    if coco_idx < len(keypoints) and keypoints[coco_idx][2] > 0:
                        kps_33[mp_idx, 0] = keypoints[coco_idx][0]
                        kps_33[mp_idx, 1] = keypoints[coco_idx][1]
                        kps_33[mp_idx, 3] = keypoints[coco_idx][2]
                result = engine.detect(
                    keypoints=kps_33,
                    features={k: v for k, v in features.items() if not np.isnan(v)},
                    image_width=frame_w,
                    image_height=frame_h,
                )
                task = result["task"]
                task_confidence = result["confidence"]
            elif self._task_model is not None:
                feat_vec = np.array(
                    [features.get(c, float("nan")) for c in self._task_features],
                    dtype=float,
                ).reshape(1, -1)
                task = str(self._task_model.predict(feat_vec)[0])
                task_confidence = 75.0
            else:
                # Heuristic fallback
                angles = self._calculate_angles(keypoints, frame_w, frame_h)
                task = self._classify_task(angles)
                task_confidence = 50.0

            # Risk scoring via ML model
            if self._risk_model is not None:
                feat_vec = np.array(
                    [features.get(c, float("nan")) for c in self._risk_features],
                    dtype=float,
                ).reshape(1, -1)
                risk_level = str(self._risk_model.predict(feat_vec)[0])
                # Get probability for a continuous score
                try:
                    probs = self._risk_model.predict_proba(feat_vec)[0]
                    classes = self._risk_model.classes_ if hasattr(self._risk_model, "classes_") else ["LOW", "MEDIUM", "HIGH"]
                    # Weighted score: LOW=20, MEDIUM=55, HIGH=85
                    weights = {"LOW": 20.0, "MEDIUM": 55.0, "HIGH": 85.0}
                    risk_score = sum(
                        p * weights.get(str(c), 50.0) for p, c in zip(probs, classes)
                    )
                except Exception:
                    risk_score = {"LOW": 20.0, "MEDIUM": 55.0, "HIGH": 85.0}.get(risk_level, 50.0)
            else:
                # Fallback to risk_from_features (rule-based from shared engine)
                risk_level = risk_from_features(features, unavailable)
                risk_score = {"LOW": 20.0, "MEDIUM": 55.0, "HIGH": 85.0}.get(risk_level, 50.0)

            # Build angles dict for legacy compatibility
            angles = self._calculate_angles(keypoints, frame_w, frame_h)
            risk_score = self._smooth_risk((camera_key, int(track_id)), risk_score)

            return TrackedPose(
                track_id=track_id,
                bbox=norm_bbox,
                keypoints=keypoints,
                angles={**angles, **{k: v for k, v in features.items() if not np.isnan(v)}},
                joint_angles=angles,
                station_id=station["station_id"] if station else None,
                station_name=station["station_name"] if station else None,
                risk_level=risk_level,
                risk_score=round(risk_score, 1),
                confidence=confidence,
                task=task,
                quality=quality,
            )

        # ── Heuristic fallback (no feature extractor available) ──────────
        angles = self._calculate_angles(keypoints, frame_w, frame_h)
        task = self._classify_task(angles)
        risk_score, risk_level = self._calculate_risk(angles, task)
        risk_score = self._smooth_risk((camera_key, int(track_id)), risk_score)

        return TrackedPose(
            track_id=track_id,
            bbox=norm_bbox,
            keypoints=keypoints,
            angles=angles,
            joint_angles=angles,
            station_id=station["station_id"] if station else None,
            station_name=station["station_name"] if station else None,
            risk_level=risk_level,
            risk_score=risk_score,
            confidence=confidence,
            task=task,
            quality=quality,
        )

    def _assess_tile_quality(
        self, frame: np.ndarray, norm_bbox: list[float], keypoints: list[list[float]],
    ) -> dict:
        """Per-tile capture-quality flags for the UI banner.

        Informational ONLY: none of these values feed task or risk scoring.
        Flags:
          * ``low_light``   — tile luma below LOW_LIGHT_LUMA (dark capture).
          * ``occluded``    — > half of the 4 torso keypoints missing below
            KEYPOINT_CONF.
          * ``too_small``   — tile height under QUALITY_MIN_TILE_H_PX (framing:
            person occupies too little of the frame for readable tiles).
          * ``luma``        — mean tile luma 0-255 (for the UI to show raw).
        """
        h, w = frame.shape[:2]
        try:
            x1 = max(0, int(norm_bbox[0] * w))
            y1 = max(0, int(norm_bbox[1] * h))
            x2 = min(w, int(norm_bbox[2] * w))
            y2 = min(h, int(norm_bbox[3] * h))
            quality: dict = {"low_light": False, "occluded": False, "too_small": False}
            if x2 - x1 < 4 or y2 - y1 < 4:
                quality["too_small"] = True
                return quality
            tile = frame[y1:y2, x1:x2]
            luma = float(tile.mean()) if tile.size else 0.0
            quality["luma"] = round(luma, 1)
            if luma < settings.LOW_LIGHT_LUMA:
                quality["low_light"] = True
            if (y2 - y1) < settings.QUALITY_MIN_TILE_H_PX:
                quality["too_small"] = True
            torso = (LEFT_SHOULDER, RIGHT_SHOULDER, LEFT_HIP, RIGHT_HIP)
            missing = sum(
                1 for i in torso
                if i >= len(keypoints) or keypoints[i][2] < settings.QUALITY_KEYPOINT_CONF
            )
            if missing > 2:
                quality["occluded"] = True
            return quality
        except Exception:  # noqa: BLE001 - display metadata must never break scoring
            return {"low_light": False, "occluded": False, "too_small": False}

    def _calculate_angles(
        self,
        keypoints: list[list[float]],
        frame_w: Optional[float] = None,
        frame_h: Optional[float] = None,
    ) -> dict[str, float]:
        """Calculate ergonomic joint angles from 17 COCO keypoints.

        ``keypoints`` are NORMALIZED (x/W, y/H), and angles must NOT be measured
        in that space: x and y are divided by different frame dimensions, so one
        physical posture yields a different angle per aspect ratio. A true 60 deg
        trunk bend measured 44 deg on 1280x720 because
        ``tan(angle_computed) = (H/W) * tan(angle_true)``.

        The keypoints are therefore scaled back to PIXELS before any angle is
        measured, and the vertical reference is a pixel offset, so no frame scale
        leaks into the result. Passing ``frame_w``/``frame_h`` selects that
        behaviour; omit them only when the input is already in one common (pixel
        or isotropic) space.

        Returns a dict of named angles in degrees.
        """
        angles = {}

        if frame_w and frame_h and frame_w > 0 and frame_h > 0:
            # Pixel space. The vertical reference only needs a direction, so a
            # 1 px offset is exactly as good as 10% of the frame height.
            kps = [[kp[0] * frame_w, kp[1] * frame_h, kp[2]] for kp in keypoints]
            vertical = 1.0
        else:
            kps = keypoints
            vertical = 0.1

        def _angle(p1, p2, p3) -> float:
            """Angle at p2 formed by p1-p2-p3, in degrees."""
            v1 = np.array([p1[0] - p2[0], p1[1] - p2[1]])
            v2 = np.array([p3[0] - p2[0], p3[1] - p2[1]])
            cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-6)
            return float(np.degrees(np.arccos(np.clip(cos_angle, -1.0, 1.0))))

        def _valid(i):
            return i < len(kps) and kps[i][2] > 0.3

        # Neck angle (nose → midpoint shoulders → vertical)
        if _valid(NOSE) and _valid(LEFT_SHOULDER) and _valid(RIGHT_SHOULDER):
            mid_shoulder = [
                (kps[LEFT_SHOULDER][0] + kps[RIGHT_SHOULDER][0]) / 2,
                (kps[LEFT_SHOULDER][1] + kps[RIGHT_SHOULDER][1]) / 2,
                1.0,
            ]
            vertical_up = [mid_shoulder[0], mid_shoulder[1] - vertical, 1.0]
            angles["neck"] = _angle(kps[NOSE], mid_shoulder, vertical_up)

        # Trunk angle (mid-shoulder → mid-hip → vertical)
        if _valid(LEFT_SHOULDER) and _valid(RIGHT_SHOULDER) and _valid(LEFT_HIP) and _valid(RIGHT_HIP):
            mid_shoulder = [
                (kps[LEFT_SHOULDER][0] + kps[RIGHT_SHOULDER][0]) / 2,
                (kps[LEFT_SHOULDER][1] + kps[RIGHT_SHOULDER][1]) / 2,
                1.0,
            ]
            mid_hip = [
                (kps[LEFT_HIP][0] + kps[RIGHT_HIP][0]) / 2,
                (kps[LEFT_HIP][1] + kps[RIGHT_HIP][1]) / 2,
                1.0,
            ]
            vertical_up = [mid_hip[0], mid_hip[1] - vertical, 1.0]
            angles["trunk"] = _angle(mid_shoulder, mid_hip, vertical_up)

        # Shoulder elevation (arm vs torso)
        if _valid(LEFT_SHOULDER) and _valid(LEFT_ELBOW) and _valid(LEFT_HIP):
            mid_shoulder = [
                (kps[LEFT_SHOULDER][0] + kps[RIGHT_SHOULDER][0]) / 2
                if _valid(RIGHT_SHOULDER) else kps[LEFT_SHOULDER][0],
                (kps[LEFT_SHOULDER][1] + kps[RIGHT_SHOULDER][1]) / 2
                if _valid(RIGHT_SHOULDER) else kps[LEFT_SHOULDER][1],
                1.0,
            ]
            angles["left_shoulder"] = _angle(
                kps[LEFT_HIP], kps[LEFT_SHOULDER], kps[LEFT_ELBOW]
            )

        if _valid(RIGHT_SHOULDER) and _valid(RIGHT_ELBOW) and _valid(RIGHT_HIP):
            angles["right_shoulder"] = _angle(
                kps[RIGHT_HIP], kps[RIGHT_SHOULDER], kps[RIGHT_ELBOW]
            )

        # Elbow angles
        if _valid(LEFT_SHOULDER) and _valid(LEFT_ELBOW) and _valid(LEFT_WRIST):
            angles["left_elbow"] = _angle(
                kps[LEFT_SHOULDER], kps[LEFT_ELBOW], kps[LEFT_WRIST]
            )
        if _valid(RIGHT_SHOULDER) and _valid(RIGHT_ELBOW) and _valid(RIGHT_WRIST):
            angles["right_elbow"] = _angle(
                kps[RIGHT_SHOULDER], kps[RIGHT_ELBOW], kps[RIGHT_WRIST]
            )

        # Hip angle
        if _valid(LEFT_SHOULDER) and _valid(LEFT_HIP) and _valid(LEFT_KNEE):
            angles["left_hip"] = _angle(
                kps[LEFT_SHOULDER], kps[LEFT_HIP], kps[LEFT_KNEE]
            )
        if _valid(RIGHT_SHOULDER) and _valid(RIGHT_HIP) and _valid(RIGHT_KNEE):
            angles["right_hip"] = _angle(
                kps[RIGHT_SHOULDER], kps[RIGHT_HIP], kps[RIGHT_KNEE]
            )

        # Knee angles
        if _valid(LEFT_HIP) and _valid(LEFT_KNEE) and _valid(LEFT_ANKLE):
            angles["left_knee"] = _angle(
                kps[LEFT_HIP], kps[LEFT_KNEE], kps[LEFT_ANKLE]
            )
        if _valid(RIGHT_HIP) and _valid(RIGHT_KNEE) and _valid(RIGHT_ANKLE):
            angles["right_knee"] = _angle(
                kps[RIGHT_HIP], kps[RIGHT_KNEE], kps[RIGHT_ANKLE]
            )

        # Wrist deviation. NOT an angle: a normalized horizontal offset, so it is
        # deliberately computed from the normalized input and is unchanged by the
        # pixel-space conversion above.
        if _valid(LEFT_ELBOW) and _valid(LEFT_WRIST):
            angles["left_wrist_dev"] = abs(
                keypoints[LEFT_WRIST][0] - keypoints[LEFT_ELBOW][0]
            ) * 100  # normalized deviation
        if _valid(RIGHT_ELBOW) and _valid(RIGHT_WRIST):
            angles["right_wrist_dev"] = abs(
                keypoints[RIGHT_WRIST][0] - keypoints[RIGHT_ELBOW][0]
            ) * 100

        # Shoulder symmetry (difference between left and right elevation)
        if "left_shoulder" in angles and "right_shoulder" in angles:
            angles["shoulder_symmetry"] = abs(
                angles["left_shoulder"] - angles["right_shoulder"]
            )

        return angles

    def _classify_task(self, angles: dict[str, float]) -> str:
        """Classify the current task based on joint angles."""
        trunk = angles.get("trunk", 90)
        left_knee = angles.get("left_knee", 180)
        right_knee = angles.get("right_knee", 180)
        knee = min(left_knee, right_knee)
        left_shoulder = angles.get("left_shoulder", 180)
        right_shoulder = angles.get("right_shoulder", 180)
        shoulder = min(left_shoulder, right_shoulder) if left_shoulder and right_shoulder else 180
        left_elbow = angles.get("left_elbow", 180)
        right_elbow = angles.get("right_elbow", 180)

        # Lifting: knees bent + trunk leaned
        if knee < 130 and trunk > 15:
            return "lifting"

        # Reaching: arms elevated above shoulder
        if shoulder < 120:
            return "reaching"

        # Sitting: hip angle < 100
        left_hip = angles.get("left_hip", 180)
        right_hip = angles.get("right_hip", 180)
        if min(left_hip, right_hip) < 100:
            return "sitting"

        # Assembly: elbows in working range, upright trunk
        if 70 < left_elbow < 160 and 70 < right_elbow < 160 and trunk < 20:
            return "assembly"

        # Standing: upright trunk, knees straight
        if trunk < 15 and knee > 160:
            return "standing"

        # Walking: knee angles alternating (hard to detect from single frame)
        if left_knee != right_knee and abs(left_knee - right_knee) > 20:
            return "walking"

        return "unknown"

    def _calculate_risk(
        self, angles: dict[str, float], task: str
    ) -> tuple[float, str]:
        """Calculate ergonomic risk score (0-100) using adapted RULA/REBA for 17 keypoints.

        Adapted from the 33-keypoint MediaPipe version. Key differences:
        - No wrist rotation (YOLO doesn't track it)
        - Coarser trunk angle resolution
        - Task-aware thresholds (same logic as MediaPipe core)
        """
        score = 0.0

        # ── Trunk assessment (RULA Column B) ────────────────────────────────
        trunk = angles.get("trunk", 0)
        if trunk > 60:
            score += 40
        elif trunk > 40:
            score += 30
        elif trunk > 20:
            score += 20
        elif trunk > 10:
            score += 10
        else:
            score += 0

        # ── Neck assessment (RULA Column A) ─────────────────────────────────
        neck = angles.get("neck", 0)
        if neck > 30:
            score += 20
        elif neck > 20:
            score += 15
        elif neck > 10:
            score += 10
        else:
            score += 0

        # ── Shoulder elevation ──────────────────────────────────────────────
        left_shoulder = angles.get("left_shoulder", 180)
        right_shoulder = angles.get("right_shoulder", 180)
        shoulder = min(
            left_shoulder if left_shoulder else 180,
            right_shoulder if right_shoulder else 180,
        )
        if shoulder < 90:
            score += 25
        elif shoulder < 120:
            score += 15
        elif shoulder < 150:
            score += 5

        # ── Elbow flexion ──────────────────────────────────────────────────
        left_elbow = angles.get("left_elbow", 180)
        right_elbow = angles.get("right_elbow", 180)
        elbow = min(
            left_elbow if left_elbow else 180,
            right_elbow if right_elbow else 180,
        )
        if elbow < 70 or elbow > 160:
            score += 10
        elif elbow < 90 or elbow > 140:
            score += 5

        # ── Knee assessment (REBA special) ─────────────────────────────────
        left_knee = angles.get("left_knee", 180)
        right_knee = angles.get("right_knee", 180)
        knee = min(
            left_knee if left_knee else 180,
            right_knee if right_knee else 180,
        )
        if knee < 100:
            score += 15  # Deep squat
        elif knee < 130:
            score += 10  # Partial squat
        elif knee < 160:
            score += 5   # Slight bend

        # ── Shoulder symmetry penalty ──────────────────────────────────────
        symmetry = angles.get("shoulder_symmetry", 0)
        if symmetry > 20:
            score += 10
        elif symmetry > 10:
            score += 5

        # ── Task-aware adjustments ──────────────────────────────────────────
        task_adjustments = {
            "lifting": 1.3,      # Lifting amplifies trunk/knee risk
            "reaching": 1.2,     # Sustained reaching is worse than momentary
            "sitting": 0.9,      # Sitting is generally lower risk for upper body
            "assembly": 1.0,     # Baseline
            "standing": 0.8,     # Standing is generally lower risk
            "walking": 0.7,      # Dynamic movement reduces static load
            "unknown": 1.0,
        }
        multiplier = task_adjustments.get(task, 1.0)
        score = min(100, score * multiplier)

        # ── Risk level classification ───────────────────────────────────────
        if score >= 60:
            level = "HIGH"
        elif score >= 35:
            level = "MEDIUM"
        else:
            level = "LOW"

        return round(score, 1), level


# Global singleton
_engine: Optional[YOLOPoseEngine] = None


def get_pose_engine() -> YOLOPoseEngine:
    global _engine
    if _engine is None:
        _engine = YOLOPoseEngine()
    return _engine
