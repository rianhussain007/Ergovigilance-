"""Reusable pose estimation pipeline.

Extracted from scripts/live_demo.py to be shared by:
- scripts/live_demo.py (desktop demo)
- backend_api/app/services/live_monitor.py (FastAPI server)
"""

import os
import time

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions, vision

from backend.services.features import (
    FEATURE_COLUMNS,
    extract_features_from_keypoints,
    mediapipe_landmarks_to_keypoints,
    risk_from_features,
    unavailable_features_from_keypoints,
    lower_body_confidence,
)
from backend.services.standard_assessment import assess_standard_risk
from backend.services.issue_detection import detect_posture_issues
from backend.services.recommendation_engine import get_recommendations
from backend.services.task_recognition import TaskRecognition
from backend.services.drift_monitor import get_drift_monitor
from backend.services.kalman import LandmarkKalmanSmoother
from backend.services.performance import frame_skipper, feature_cache, performance_monitor

# Canonical definitions live in backend.core.constants and backend.core.types.
# Re-exported here for backward compatibility.
from backend.core.constants import RISK_LEVELS_DICT as RISK_LEVELS  # noqa: F401
from backend.core.constants import CONFIDENCE_LANDMARKS  # noqa: F401
from backend.core.types import ProcessedFrame  # noqa: F401
from backend.core.utils import wrist_movement_velocity_px


def _compute_confidence(landmarks) -> float:
    vals = [
        landmarks[i].visibility
        for i in CONFIDENCE_LANDMARKS
        if i < len(landmarks) and hasattr(landmarks[i], "visibility")
    ]
    return float(np.mean(vals)) * 100 if vals else 0.0


def compute_person_risks(
    pose_landmarks,
    w_f: int,
    h_f: int,
    primary_index: int,
    primary_risk_level: str,
) -> list[dict]:
    """Per-person threshold risk for every detected pose (station view).

    Each MediaPipe pose gets its own features + deterministic risk
    (``risk_from_features``) so all workers at a station are visible, not just
    the biggest. The primary entry (``primary_index``) carries the
    authoritative engine risk (standard-method/context) so the station list
    never disagrees with the main pipeline. Secondary workers are NOT fed into
    the context engine (fatigue/task/alerts stay primary-only) — an honest
    scope boundary documented at the call site.
    """
    person_risks: list[dict] = []
    for pi, pose in enumerate(pose_landmarks):
        kp_p = mediapipe_landmarks_to_keypoints(pose, w_f, h_f)
        feat_p, unav_p, _approx_p = extract_features_from_keypoints(kp_p)
        is_primary = pi == primary_index
        try:
            issues_p = detect_posture_issues(feat_p)
            top_issue = issues_p[0].get("issue") if issues_p else None
        except Exception:  # noqa: BLE001 - station risk is best-effort
            top_issue = None
        vis_vals = [kp[3] for kp in kp_p if len(kp) > 3]
        person_risks.append({
            "person_index": pi,
            "is_primary": is_primary,
            "risk_level": primary_risk_level if is_primary else risk_from_features(feat_p, unav_p),
            "top_issue": top_issue,
            "keypoint_visibility": round(
                sum(vis_vals) / len(vis_vals), 3
            ) if vis_vals else 0.0,
        })
    return person_risks


def _compute_lower_body_confidence(keypoints) -> float:
    """Confidence score for lower-body landmarks (hips, knees, ankles)."""
    if not keypoints or len(keypoints) < 29:
        return 0.0
    lower_indices = [23, 24, 25, 26, 27, 28]
    vis_vals = [keypoints[i][3] for i in lower_indices if i < len(keypoints)]
    return float(np.mean(vis_vals)) * 100 if vis_vals else 0.0


# Feature keys that are pure motion signals — never smoothed (they ARE the
# frame-to-frame delta).
_UNSMOOTHED_FEATURES = {"movement_velocity", "wrist_movement_velocity"}


class PoseEngine:
    """Reusable CV pipeline: frame -> MediaPipe -> features -> issues -> recs -> task."""

    def __init__(self, model_path: str):
        self.model_path = model_path
        self.pose_landmarker = None
        self.task_recognizer = TaskRecognition()
        self.timestamp_ms = 0
        self._initialized = False
        self._prev_features: dict | None = None
        self._prev_timestamp: float = 0.0
        self._smoothed_features: dict | None = None
        # EMA weight for posture features (new sample share). Lower = smoother.
        # Configurable via env so deployments can tune jitter vs. responsiveness.
        try:
            self._smooth_alpha = float(os.environ.get("ERGOVIGILANCE_FEATURE_SMOOTHING", "0.7"))
        except (TypeError, ValueError):
            self._smooth_alpha = 0.7
        self._smooth_alpha = min(1.0, max(0.1, self._smooth_alpha))
        # Landmark-level Kalman smoothing (Tier 0): removes per-frame jitter
        # at the source so features, risk, and the overlay skeleton all read a
        # cleaner signal. Disable with ERGOVIGILANCE_KALMAN=0.
        try:
            kalman_env = os.environ.get("ERGOVIGILANCE_KALMAN", "1").strip().lower()
            self._kalman_enabled = kalman_env not in ("0", "false", "no", "off")
        except AttributeError:
            self._kalman_enabled = True
        self._kalman = LandmarkKalmanSmoother() if self._kalman_enabled else None

    def initialize(self):
        # Tier 3 multi-person foundation: MediaPipe can detect several poses
        # per frame (CPU cost grows roughly linearly). The pipeline still
        # SCORES the primary person (largest bbox) but ``person_count`` lets
        # the UI/reporting know more than one worker is in view. Configure
        # with ERGOVIGILANCE_NUM_POSES (default 1 preserves current behavior).
        try:
            num_poses = max(1, int(os.environ.get("ERGOVIGILANCE_NUM_POSES", "1")))
        except (TypeError, ValueError):
            num_poses = 1
        self._num_poses = min(num_poses, 4)
        options = vision.PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=self.model_path),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=self._num_poses,
            min_pose_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self.pose_landmarker = vision.PoseLandmarker.create_from_options(options)
        self._initialized = True
        self._init_time = time.perf_counter()  # For accurate MediaPipe timestamps

    def process_frame(self, frame: np.ndarray, force_process: bool = False) -> ProcessedFrame:
        """Process one camera frame through the full CV pipeline.

        Performance note: this method is the hot path during live monitoring.
        Each sub-step (MediaPipe inference, feature extraction, context eval)
        is bounded to keep total latency under the POSE_PROCESS_FPS target.

        ``force_process=True`` bypasses the global time-based frame skipper so
        offline consumers (video analysis, timeline generation) can process
        EVERY frame for temporal tracking continuity. Use it only on a
        dedicated engine instance — never on the live engine — because it
        overrides the shared skipper's pacing.
        """
        if not self._initialized or self.pose_landmarker is None:
            raise RuntimeError("PoseEngine not initialized. Call initialize() first.")

        # Performance: skip frames if we're ahead of schedule (unless the
        # caller explicitly needs every frame processed for temporal tracking).
        if not force_process and not frame_skipper.should_process():
            # Return a lightweight result indicating frame was skipped
            return ProcessedFrame(
                keypoints=[],
                features={},
                risk_level="LOW",
                confidence=0.0,
                person_detected=False,
                task_info=None,
                issues=[],
                recommendations=[],
                timestamp=time.time(),
                unavailable_features=[],
                approximate_features=[],
                lower_body_confidence=0.0,
                standard_assessment={},
                framing={},
                person_count=0,
            )
        
        # Start timing
        start_time = time.perf_counter()
        
        # Use actual elapsed time for MediaPipe timestamp, not hardcoded 33ms
        self.timestamp_ms = int((time.perf_counter() - self._init_time) * 1000) if hasattr(self, '_init_time') else self.timestamp_ms + 33
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        # Inference timing
        inference_start = time.perf_counter()
        result = self.pose_landmarker.detect_for_video(mp_image, self.timestamp_ms)
        inference_time = time.perf_counter() - inference_start

        # Initialize defaults — avoided when no person detected (early exit)
        features: dict[str, float] = {}
        risk_level = "LOW"
        confidence = 0.0
        person_detected = False
        task_info = None
        issues: list[dict] = []
        recommendations: list[dict] = []
        keypoints: list[list[float]] = []
        unavailable: list[str] = []
        approximate: list[str] = []
        lb_conf = 0.0
        standard_assessment: dict = {}
        framing: dict = {}
        person_count = 0

        if result.pose_landmarks:
            person_detected = True
            person_count = len(result.pose_landmarks)
            # Primary person: the largest bounding box (most of the worker's
            # body in frame = most reliable angles). Multi-person session
            # isolation (per-worker sessions/analytics) is the follow-up; for
            # now the pipeline scores the primary worker and reports how many
            # people the camera can see.
            primary_index = 0
            landmarks = result.pose_landmarks[0]
            if person_count > 1:
                best_i, best_area = 0, -1.0
                for i, pose in enumerate(result.pose_landmarks):
                    xs = [lm.x for lm in pose]
                    ys = [lm.y for lm in pose]
                    area = (max(xs) - min(xs)) * (max(ys) - min(ys))
                    if area > best_area:
                        best_i, best_area = i, area
                primary_index = best_i
                landmarks = result.pose_landmarks[best_i]
            h_f, w_f = frame.shape[:2]
            keypoints = mediapipe_landmarks_to_keypoints(landmarks, w_f, h_f)
            # Landmark-level Kalman smoothing before feature extraction — the
            # smoothed skeleton feeds features, risk, and the overlay overlay,
            # so all three agree instead of the overlay jittering frame to frame.
            if self._kalman is not None:
                keypoints = self._kalman.smooth(keypoints)
            
            # Feature extraction timing
            feature_start = time.perf_counter()
            # Performance: check cache first to avoid redundant feature extraction
            cached_features = feature_cache.get(keypoints)
            if cached_features is not None:
                features = cached_features.get('features', {})
                unavailable = cached_features.get('unavailable', [])
                approximate = cached_features.get('approximate', [])
            else:
                features, unavailable, approximate = extract_features_from_keypoints(keypoints)
                # Cache the computed features
                feature_cache.set(keypoints, {
                    'features': features,
                    'unavailable': unavailable,
                    'approximate': approximate,
                })
            feature_time = time.perf_counter() - feature_start
            lb_conf = _compute_lower_body_confidence(keypoints)

            current_time = time.time()
            if self._prev_features is not None:
                dt = current_time - self._prev_timestamp
                if dt > 1e-6:
                    neck_val = features["neck_flexion"]
                    trunk_val = features["trunk_flexion"]
                    prev_neck = self._prev_features["neck_flexion"]
                    prev_trunk = self._prev_features["trunk_flexion"]
                    # Skip velocity if either value is NaN (unavailable)
                    if neck_val == neck_val and trunk_val == trunk_val:
                        d_neck = abs(neck_val - prev_neck)
                        d_trunk = abs(trunk_val - prev_trunk)
                        features["movement_velocity"] = round(max(d_neck, d_trunk) / dt, 2)
                    else:
                        features["movement_velocity"] = 0.0
                    # Wrist movement velocity: frame-to-frame wrist position
                    # change in pixels/second — the physical scale the task
                    # classifier's Reaching gaussian expects (~150 px/s).
                    # Helper guards against missing wrists from either frame.
                    if len(keypoints) > 16:
                        features["wrist_movement_velocity"] = wrist_movement_velocity_px(
                            prev_left=self._prev_features.get("left_wrist"),
                            prev_right=self._prev_features.get("right_wrist"),
                            curr_left=keypoints[15],
                            curr_right=keypoints[16],
                            dt=dt,
                            width=w_f,
                            height=h_f,
                        )
                    else:
                        features["wrist_movement_velocity"] = 0.0
                else:
                    features["movement_velocity"] = 0.0
                    features["wrist_movement_velocity"] = 0.0
            else:
                features["movement_velocity"] = 0.0
                features["wrist_movement_velocity"] = 0.0

            self._prev_features = {
                "neck_flexion": features["neck_flexion"],
                "trunk_flexion": features["trunk_flexion"],
                "left_wrist": keypoints[15] if len(keypoints) > 15 else None,
                "right_wrist": keypoints[16] if len(keypoints) > 16 else None,
            }
            self._prev_timestamp = current_time

            # Phase B: EMA-smooth static posture features (kills jitter ->
            # fewer false alerts). Motion signals and NaN pass through.
            features = self._apply_smoothing(features)

            # Tier 3 framing intelligence: profile view / cropped body /
            # occlusion -> camera guidance + per-joint angle uncertainty
            # (sigma) that the context engine uses for uncertainty-aware
            # scoring (P(rule violated) instead of hard cutoffs).
            try:
                from backend.services.framing_quality import assess_framing
                framing = assess_framing(keypoints, w_f, h_f)
            except Exception:
                framing = {}

            # Authoritative standard-method gate: RULA when the full body is
            # NOT visible (legs out of frame), REBA only when it is. Risk
            # triggers only when a published RULA/REBA rule is broken; the
            # legacy threshold rules remain as a fallback when the standard
            # method cannot be computed (e.g. too few landmarks).
            standard_assessment = assess_standard_risk(
                keypoints, features, unavailable, lb_conf
            )
            if standard_assessment.get("risk_level"):
                risk_level = standard_assessment["risk_level"]
            else:
                risk_level = risk_from_features(features, unavailable)
            confidence = _compute_confidence(landmarks)

            # ── Per-person risk (station view) ────────────────────────
            # Every detected pose gets its own features + deterministic risk
            # so the UI can show ALL workers at a station, not just the
            # primary. The primary entry is overridden with the authoritative
            # engine risk (standard-method/context) so the station list never
            # disagrees with the main pipeline. These are lightweight
            # threshold scores — secondary workers are NOT fed into the
            # context engine (fatigue/task/alerts stay primary-only), which is
            # an honest, documented scope boundary for now.
            person_risks = compute_person_risks(
                result.pose_landmarks, w_f, h_f, primary_index, risk_level
            )
            task_info = self.task_recognizer.detect_task(keypoints, features)
            # Drift canary: record whether the trained task classifier decided
            # (model) or the Gaussian fallback did. A rising fallback rate is
            # the earliest signal of classifier drift. Skip degenerate frames
            # ("Unknown" task, zero confidence — no real classification ran,
            # e.g. torso out of frame) so they don't skew the fallback rate.
            try:
                # Skip the drift canary for forced offline processing: an
                # analysis job bursts hundreds of frames in seconds, which
                # would skew the live fallback-rate stats. The canary exists
                # to measure the LIVE pipeline.
                if not force_process and task_info and task_info.get("task") != "Unknown":
                    get_drift_monitor().record(
                        source="model" if self.task_recognizer.using_model else "gaussian",
                        confidence=float(task_info.get("confidence", 0.0)),
                    )
            except Exception:  # pragma: no cover - canary must never break the pipeline
                pass
        else:
            # No person this frame: reset smoothing so a re-detection
            # starts fresh instead of interpolating against a stale pose.
            self._smoothed_features = None
            if self._kalman is not None:
                self._kalman.reset()
            person_risks = []

        if person_detected:
            issues = detect_posture_issues(features)
            recommendations = get_recommendations(issues)

        # Record performance metrics
        end_time = time.perf_counter()
        total_time = end_time - start_time
        performance_monitor.record_frame_time(
            total_time=total_time,
            inference_time=inference_time if 'inference_time' in locals() else 0.0,
            feature_time=feature_time if 'feature_time' in locals() else 0.0,
            context_time=context_time if 'context_time' in locals() else 0.0,
        )
        
        return ProcessedFrame(
            keypoints=keypoints,
            features=features,
            risk_level=risk_level,
            confidence=confidence,
            person_detected=person_detected,
            task_info=task_info,
            issues=issues,
            recommendations=recommendations,
            timestamp=time.time(),
            unavailable_features=unavailable,
            approximate_features=approximate,
            lower_body_confidence=lb_conf,
            standard_assessment=standard_assessment,
            framing=framing,
            person_count=person_count,
            person_risks=person_risks,
        )

    def _apply_smoothing(self, features: dict[str, float]) -> dict[str, float]:
        """Exponentially smooth the static posture features in place.

        Motion features (movement_velocity, wrist_movement_velocity) and NaN
        (unavailable) values are passed through untouched. Smoothing state is
        reset whenever a person is not detected, so a re-detection starts fresh
        instead of interpolating against a stale pose.
        """
        if self._smoothed_features is None:
            self._smoothed_features = dict(features)
            return self._smoothed_features
        alpha = self._smooth_alpha
        for key in FEATURE_COLUMNS:
            if key in _UNSMOOTHED_FEATURES:
                continue
            raw = features.get(key)
            if raw is None:
                continue  # missing key -> keep previous
            if raw != raw:
                # NaN this frame (landmark unavailable): propagate the NaN so
                # downstream consumers (issues, task recognition) see the
                # unavailable state instead of a stale high value that keeps
                # firing false alerts.
                self._smoothed_features[key] = float("nan")
                continue
            prev = self._smoothed_features.get(key)
            self._smoothed_features[key] = round(alpha * raw + (1.0 - alpha) * (prev if prev is not None and prev == prev else raw), 4)
        return self._smoothed_features

    def release(self):
        if self.pose_landmarker:
            self.pose_landmarker.close()
            self.pose_landmarker = None
        self._initialized = False
        self._smoothed_features = None
        if self._kalman is not None:
            self._kalman.reset()
