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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from yolo_cloud.config import settings

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


@dataclass
class ProcessedCloudFrame:
    """Result of processing one frame through the cloud pipeline."""
    frame_width: int
    frame_height: int
    tracked_poses: list[TrackedPose]
    person_count: int
    inference_ms: float
    timestamp: float


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
        self._tracker = None
        self._risk_model = None
        self._task_model = None
        self._initialized = False

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

        try:
            from ultralytics.trackers import ByteTrack
            self._tracker = ByteTrack(
                track_thresh=settings.TRACK_THRESH,
                track_buffer=settings.TRACK_BUFFER,
                match_thresh=settings.MATCH_THRESH,
                min_hits=settings.MIN_HITS,
            )
            logger.info("ByteTrack tracker initialized")
        except ImportError:
            logger.warning("ByteTrack not available — tracking disabled")
            self._tracker = None

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

    def process_frame(
        self, frame: np.ndarray
    ) -> ProcessedCloudFrame:
        """Process a single frame through YOLOv8-pose + ByteTrack.

        Returns ProcessedCloudFrame with tracked poses, angles, and risk scores.
        """
        if not self._initialized:
            self.initialize()

        t_start = time.perf_counter()
        h, w = frame.shape[:2]

        # Run YOLOv8-pose inference
        results = self._model(
            frame,
            conf=settings.YOLO_CONFIDENCE,
            device=settings.YOLO_DEVICE,
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

                # Run ByteTrack
                if self._tracker is not None and len(det_boxes) > 0:
                    # ByteTrack expects [x1, y1, x2, y2, conf]
                    det_input = np.column_stack([det_boxes, det_confs])
                    online_targets = self._tracker.update(det_input, frame, frame)

                    for target in online_targets:
                        tid = target.track_id
                        tlwh = target.tlwh
                        # Convert tlwh to xyxy
                        x1, y1, bw, bh = tlwh
                        x2, y2 = x1 + bw, y1 + bh

                        # Find the original detection closest to this tracked target
                        kps_data = self._find_closest_keypoints(
                            det_boxes, det_confs, kps, x1, y1, x2, y2
                        )

                        if kps_data is not None:
                            pose = self._process_tracked_pose(
                                tid, [x1, y1, x2, y2], kps_data, w, h, frame
                            )
                            poses.append(pose)
                else:
                    # No tracker — just process each detection
                    for i, box in enumerate(det_boxes):
                        conf = float(det_confs[i])
                        kps_data = kps[i] if kps is not None else None
                        if kps_data is not None:
                            pose = self._process_tracked_pose(
                                i, box.tolist(), kps_data, w, h, frame
                            )
                            pose.confidence = conf
                            poses.append(pose)

        inference_ms = (time.perf_counter() - t_start) * 1000

        return ProcessedCloudFrame(
            frame_width=w,
            frame_height=h,
            tracked_poses=poses,
            person_count=len(poses),
            inference_ms=inference_ms,
            timestamp=time.time(),
        )

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

            # Task classification via ML model
            if self._task_model is not None:
                feat_vec = np.array(
                    [features.get(c, float("nan")) for c in FEATURE_COLUMNS],
                    dtype=float,
                ).reshape(1, -1)
                task = str(self._task_model.predict(feat_vec)[0])
            else:
                # Heuristic fallback
                angles = self._calculate_angles(keypoints)
                task = self._classify_task(angles)

            # Risk scoring via ML model
            if self._risk_model is not None:
                feat_vec = np.array(
                    [features.get(c, float("nan")) for c in FEATURE_COLUMNS],
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
            angles = self._calculate_angles(keypoints)

            return TrackedPose(
                track_id=track_id,
                bbox=norm_bbox,
                keypoints=keypoints,
                angles={**angles, **{k: v for k, v in features.items() if not np.isnan(v)}},
                risk_level=risk_level,
                risk_score=round(risk_score, 1),
                confidence=confidence,
                task=task,
            )

        # ── Heuristic fallback (no feature extractor available) ──────────
        angles = self._calculate_angles(keypoints)
        task = self._classify_task(angles)
        risk_score, risk_level = self._calculate_risk(angles, task)

        return TrackedPose(
            track_id=track_id,
            bbox=norm_bbox,
            keypoints=keypoints,
            angles=angles,
            risk_level=risk_level,
            risk_score=risk_score,
            confidence=confidence,
            task=task,
        )

    def _calculate_angles(self, keypoints: list[list[float]]) -> dict[str, float]:
        """Calculate ergonomic joint angles from 17 COCO keypoints.

        Returns a dict of named angles in degrees.
        """
        angles = {}

        def _angle(p1, p2, p3) -> float:
            """Angle at p2 formed by p1-p2-p3, in degrees."""
            v1 = np.array([p1[0] - p2[0], p1[1] - p2[1]])
            v2 = np.array([p3[0] - p2[0], p3[1] - p2[1]])
            cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-6)
            return float(np.degrees(np.arccos(np.clip(cos_angle, -1.0, 1.0))))

        def _valid(i):
            return i < len(keypoints) and keypoints[i][2] > 0.3

        # Neck angle (nose → midpoint shoulders → vertical)
        if _valid(NOSE) and _valid(LEFT_SHOULDER) and _valid(RIGHT_SHOULDER):
            mid_shoulder = [
                (keypoints[LEFT_SHOULDER][0] + keypoints[RIGHT_SHOULDER][0]) / 2,
                (keypoints[LEFT_SHOULDER][1] + keypoints[RIGHT_SHOULDER][1]) / 2,
                1.0,
            ]
            vertical_up = [mid_shoulder[0], mid_shoulder[1] - 0.1, 1.0]
            angles["neck"] = _angle(keypoints[NOSE], mid_shoulder, vertical_up)

        # Trunk angle (mid-shoulder → mid-hip → vertical)
        if _valid(LEFT_SHOULDER) and _valid(RIGHT_SHOULDER) and _valid(LEFT_HIP) and _valid(RIGHT_HIP):
            mid_shoulder = [
                (keypoints[LEFT_SHOULDER][0] + keypoints[RIGHT_SHOULDER][0]) / 2,
                (keypoints[LEFT_SHOULDER][1] + keypoints[RIGHT_SHOULDER][1]) / 2,
                1.0,
            ]
            mid_hip = [
                (keypoints[LEFT_HIP][0] + keypoints[RIGHT_HIP][0]) / 2,
                (keypoints[LEFT_HIP][1] + keypoints[RIGHT_HIP][1]) / 2,
                1.0,
            ]
            vertical_up = [mid_hip[0], mid_hip[1] - 0.1, 1.0]
            angles["trunk"] = _angle(mid_shoulder, mid_hip, vertical_up)

        # Shoulder elevation (arm vs torso)
        if _valid(LEFT_SHOULDER) and _valid(LEFT_ELBOW) and _valid(LEFT_HIP):
            mid_shoulder = [
                (keypoints[LEFT_SHOULDER][0] + keypoints[RIGHT_SHOULDER][0]) / 2
                if _valid(RIGHT_SHOULDER) else keypoints[LEFT_SHOULDER][0],
                (keypoints[LEFT_SHOULDER][1] + keypoints[RIGHT_SHOULDER][1]) / 2
                if _valid(RIGHT_SHOULDER) else keypoints[LEFT_SHOULDER][1],
                1.0,
            ]
            angles["left_shoulder"] = _angle(
                keypoints[LEFT_HIP], keypoints[LEFT_SHOULDER], keypoints[LEFT_ELBOW]
            )

        if _valid(RIGHT_SHOULDER) and _valid(RIGHT_ELBOW) and _valid(RIGHT_HIP):
            angles["right_shoulder"] = _angle(
                keypoints[RIGHT_HIP], keypoints[RIGHT_SHOULDER], keypoints[RIGHT_ELBOW]
            )

        # Elbow angles
        if _valid(LEFT_SHOULDER) and _valid(LEFT_ELBOW) and _valid(LEFT_WRIST):
            angles["left_elbow"] = _angle(
                keypoints[LEFT_SHOULDER], keypoints[LEFT_ELBOW], keypoints[LEFT_WRIST]
            )
        if _valid(RIGHT_SHOULDER) and _valid(RIGHT_ELBOW) and _valid(RIGHT_WRIST):
            angles["right_elbow"] = _angle(
                keypoints[RIGHT_SHOULDER], keypoints[RIGHT_ELBOW], keypoints[RIGHT_WRIST]
            )

        # Hip angle
        if _valid(LEFT_SHOULDER) and _valid(LEFT_HIP) and _valid(LEFT_KNEE):
            angles["left_hip"] = _angle(
                keypoints[LEFT_SHOULDER], keypoints[LEFT_HIP], keypoints[LEFT_KNEE]
            )
        if _valid(RIGHT_SHOULDER) and _valid(RIGHT_HIP) and _valid(RIGHT_KNEE):
            angles["right_hip"] = _angle(
                keypoints[RIGHT_SHOULDER], keypoints[RIGHT_HIP], keypoints[RIGHT_KNEE]
            )

        # Knee angles
        if _valid(LEFT_HIP) and _valid(LEFT_KNEE) and _valid(LEFT_ANKLE):
            angles["left_knee"] = _angle(
                keypoints[LEFT_HIP], keypoints[LEFT_KNEE], keypoints[LEFT_ANKLE]
            )
        if _valid(RIGHT_HIP) and _valid(RIGHT_KNEE) and _valid(RIGHT_ANKLE):
            angles["right_knee"] = _angle(
                keypoints[RIGHT_HIP], keypoints[RIGHT_KNEE], keypoints[RIGHT_ANKLE]
            )

        # Wrist deviation
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
