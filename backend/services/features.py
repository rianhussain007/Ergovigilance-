from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Mapping, Sequence

import numpy as np

# Canonical definitions live in backend.core.constants.
# Re-exported here for backward compatibility.
from backend.core.constants import (  # noqa: F401
    COCO_17,
    FEATURE_COLUMNS,
    FEATURE_THRESHOLDS,
    MEDIAPIPE_33,
)

RISK_LEVELS = ["LOW", "MEDIUM", "HIGH"]

# ── Task-Conditional Threshold Tables ────────────────────────────────
# Each task class gets its own (MEDIUM, HIGH) cutoffs per feature,
# grounded in the ergonomic method best suited to that task type:
#
#   • Lifting / Picking   → REBA-style (whole-body, trunk/knee dominant)
#   • Assembly Work       → RULA-style (upper-body, neck/shoulder/wrist)
#   • Reaching            → Blend (shoulder-dominant + weight-shift)
#   • Inspection          → RULA-style (upper-body, repetitive gaze)
#   • Walking / Moving    → Baseline (loose thresholds, movement-heavy)
#   • Seated Work         → RULA-style (upper-body, neck/wrist focus)
#   • Neutral Standing    → Baseline (the existing calibrated defaults)
#
# Thresholds share the same feature names as RISK_THRESHOLDS.  Any feature
# not listed for a task inherits from RISK_THRESHOLDS (the default).

task_thresholds: dict[str, dict[str, tuple[float, float]]] = {
    # ── Lifting / Picking ─ REBA-informed: whole-body, load-bearing ────
    "Lifting / Picking": {
        "neck_flexion":         (10.0, 25.0),   # moderate (REBA Table A)
        "trunk_flexion":        (20.0, 45.0),   # REBA trunk bands: <20 low, 20-45 mod, >45 high
        "shoulder_elev":        (30.0, 55.0),   # slightly relaxed vs baseline (arms carry load)
        "shoulder_symmetry":    (9.0, 18.0),    # same as baseline
        "knee_angle":           (155.0, 120.0), # REBA leg assessment: deep knee bend = high risk
        "forward_head_posture": (12.0, 25.0),   # slightly relaxed (focus is on trunk/legs)
        "head_tilt_angle":      (10.0, 20.0),   # same as baseline
        "wrist_deviation_angle": (5.0, 15.0),   # same as baseline
        "stance_stability":     (0.65, 0.40),   # tighter: balance matters under load
        "weight_shift_offset":  (10.0, 20.0),   # tighter: asymmetric loading is dangerous
    },

    "Assembly Work": {
        # MENDED (assembly worker who also does heavy lifting): normal
        # assembly work now scores on the SAME relaxed bands the standard
        # RULA/REBA gate uses (calibration RELAXED feature_cutoffs), so a
        # routine assembly posture — moderate neck flexion, arms at bench
        # height — no longer over-alarms. Previously this table was stricter
        # than the standard gate itself (neck 8/22, shoulder 25/50, wrist
        # 4/12), which manufactured yellow/red on slight movement. Only
        # sustained strain beyond the relaxed bands scores now; heavy
        # lifting is scored by the REBA-grounded Lifting / Picking table.
        "neck_flexion":         (15.0, 35.0),
        "trunk_flexion":        (30.0, 70.0),
        "shoulder_elev":        (35.0, 60.0),
        "shoulder_symmetry":    (9.0, 18.0),
        "knee_angle":           (140.0, 95.0),
        "forward_head_posture": (15.0, 28.0),
        "head_tilt_angle":      (15.0, 28.0),
        "wrist_deviation_angle": (10.0, 25.0),
        "stance_stability":     (0.6, 0.45),
        "weight_shift_offset":  (15.0, 30.0),
    },

    "Reaching": {
        # Blend: shoulder-dominated with trunk/weight-shift secondary
        "neck_flexion":         (10.0, 28.0),   # slightly relaxed
        "trunk_flexion":        (18.0, 50.0),   # tighter: forward reach = trunk involvement
        "shoulder_elev":        (22.0, 45.0),   # tighter: reaching elevates shoulders
        "shoulder_symmetry":    (7.0, 15.0),    # tighter: one-arm reach = asymmetry
        "knee_angle":           (150.0, 100.0), # same as baseline
        "forward_head_posture": (10.0, 22.0),   # same as baseline
        "head_tilt_angle":      (10.0, 20.0),   # same as baseline
        "wrist_deviation_angle": (5.0, 15.0),   # same as baseline
        "stance_stability":     (0.65, 0.45),   # tighter: balance during reach
        "weight_shift_offset":  (10.0, 20.0),   # tighter: reaching shifts weight
    },

    "Inspection": {
        # RULA-style: upper-body focused, visual task
        "neck_flexion":         (8.0, 25.0),    # tighter: sustained neck flexion looking down
        "trunk_flexion":        (20.0, 60.0),   # same as baseline
        "shoulder_elev":        (28.0, 55.0),   # slightly tighter
        "shoulder_symmetry":    (8.0, 16.0),    # slightly tighter
        "knee_angle":           (150.0, 100.0), # same as baseline
        "forward_head_posture": (8.0, 18.0),    # tighter: inspecting = head forward
        "head_tilt_angle":      (8.0, 18.0),    # tighter: looking at angles
        "wrist_deviation_angle": (5.0, 15.0),   # same as baseline
        "stance_stability":     (0.7, 0.5),     # same as baseline
        "weight_shift_offset":  (12.5, 25.0),   # same as baseline
    },

    "Walking / Moving": {
        # Baseline: dynamic activity, moderate thresholds
        "neck_flexion":         (12.0, 30.0),   # relaxed (movement = transient postures)
        "trunk_flexion":        (22.0, 60.0),   # relaxed
        "shoulder_elev":        (32.0, 60.0),   # relaxed
        "shoulder_symmetry":    (10.0, 20.0),   # relaxed
        "knee_angle":           (148.0, 110.0), # slightly tighter (gait analysis)
        "forward_head_posture": (12.0, 25.0),   # relaxed
        "head_tilt_angle":      (12.0, 22.0),   # relaxed
        "wrist_deviation_angle": (6.0, 16.0),   # relaxed
        "stance_stability":     (0.6, 0.35),    # tighter: walking = dynamic balance
        "weight_shift_offset":  (15.0, 30.0),   # relaxed
    },

    "Seated Work": {
        # RULA-style: upper-body dominant, sustained posture
        "neck_flexion":         (8.0, 22.0),    # tighter: desk/workbench neck strain
        "trunk_flexion":        (18.0, 50.0),   # tighter: seated trunk posture matters
        "shoulder_elev":        (25.0, 50.0),   # tighter: repetitive arm work
        "shoulder_symmetry":    (7.0, 15.0),    # tighter
        "knee_angle":           (100.0, 80.0),  # tighter: seated knee angle critical
        "forward_head_posture": (8.0, 18.0),    # tighter: sustained desk posture
        "head_tilt_angle":      (8.0, 18.0),    # tighter
        "wrist_deviation_angle": (4.0, 12.0),   # tighter: keyboard/tool use
        "stance_stability":     (0.7, 0.5),     # same (seated = stable)
        "weight_shift_offset":  (10.0, 20.0),   # tighter: seated weight distribution
    },
}

# Neutral Standing uses the original baseline thresholds (no task-specific table needed).
_TASK_THRESHOLD_CLASSES = frozenset(task_thresholds.keys())

FEATURE_DEPENDENCIES = {
    "neck_flexion": ["left_ear", "right_ear", "left_shoulder", "right_shoulder", "left_hip", "right_hip"],
    "trunk_flexion": ["left_shoulder", "right_shoulder", "left_hip", "right_hip"],
    "left_shoulder_elev": ["left_shoulder", "left_elbow"],
    "right_shoulder_elev": ["right_shoulder", "right_elbow"],
    "shoulder_symmetry": ["left_shoulder", "right_shoulder"],
    "alignment_deviation": ["left_ear", "right_ear", "left_hip", "right_hip"],
    "knee_angle": ["left_hip", "right_hip", "left_knee", "right_knee", "left_ankle", "right_ankle"],
    "elbow_flexion_angle": ["left_shoulder", "right_shoulder", "left_elbow", "right_elbow", "left_wrist", "right_wrist"],
    "upper_arm_angle_from_vertical": ["left_shoulder", "right_shoulder", "left_wrist", "right_wrist"],
    # Phase-A additions (2026-08) — use nose, fingers, heels/feet        # nose is optional (fallback head reference when ears are occluded),
        # so it is NOT a required dependency.
        "forward_head_posture": ["left_ear", "right_ear", "left_shoulder", "right_shoulder"],
    "head_tilt_angle": ["left_ear", "right_ear"],
    "wrist_deviation_angle": ["left_elbow", "right_elbow", "left_wrist", "right_wrist", "left_index", "right_index"],
    "stance_stability": ["left_hip", "right_hip", "left_ankle", "right_ankle"],
    "weight_shift_offset": ["left_hip", "right_hip", "left_ankle", "right_ankle"],
    "hand_reach_ratio": ["left_shoulder", "right_shoulder", "left_hip", "right_hip", "left_index", "right_index"],
    "finger_spread_ratio": ["left_wrist", "right_wrist", "left_index", "right_index", "left_thumb", "right_thumb"],
    "stance_width_ratio": ["left_hip", "right_hip", "left_ankle", "right_ankle"],
}


@dataclass(frozen=True)
class RiskBreakdown:
    level: str
    color: tuple[int, int, int]


RISK_COLORS_BGR: Mapping[str, tuple[int, int, int]] = {
    "LOW": (40, 170, 70),
    "MEDIUM": (0, 165, 255),
    "HIGH": (40, 40, 220),
}


def angle_between_three_points(p1: Sequence[float], p2: Sequence[float], p3: Sequence[float]) -> float:
    v1 = np.array(p1[:2], dtype=float) - np.array(p2[:2], dtype=float)
    v2 = np.array(p3[:2], dtype=float) - np.array(p2[:2], dtype=float)
    denom = np.linalg.norm(v1) * np.linalg.norm(v2)
    if denom == 0:
        return float("nan")
    cos_angle = np.dot(v1, v2) / denom
    return float(np.degrees(np.arccos(np.clip(cos_angle, -1.0, 1.0))))


def _midpoint(a: Sequence[float], b: Sequence[float]) -> np.ndarray:
    return (np.array(a[:2], dtype=float) + np.array(b[:2], dtype=float)) / 2.0


def _safe_distance(a: Sequence[float], b: Sequence[float], default: float = 1.0) -> float:
    value = float(np.linalg.norm(np.array(a[:2], dtype=float) - np.array(b[:2], dtype=float)))
    return value if value > 1e-9 else default


def _point(kps: np.ndarray, index_map: Mapping[str, int], name: str) -> np.ndarray:
    """Return the 2D point for a landmark.

    Out-of-range indices (short/corrupt keypoint rows) yield a NaN point
    instead of crashing; such features are marked unavailable upstream by
    ``unavailable_features_from_keypoints`` and their NaN flows through as
    "unknown" rather than a bogus number.
    """
    idx = index_map[name]
    if idx >= len(kps):
        return np.array([float("nan"), float("nan")])
    return np.array(kps[idx][:2], dtype=float)


def _safe_point(
    kps: np.ndarray,
    index_map: Mapping[str, int],
    name: str,
) -> np.ndarray | None:
    """Return a 2D point for a landmark, or ``None`` when the landmark is not
    in the index map (e.g. fingers/feet on COCO_17) or out of range."""
    idx = index_map.get(name)
    if idx is None or idx >= len(kps):
        return None
    return np.array(kps[idx][:2], dtype=float)


def extract_features_from_keypoints(
    keypoints: Sequence[Sequence[float]],
    index_map: Mapping[str, int] | None = None,
) -> tuple[Dict[str, float], list[str], list[str]]:
    """Extract ergonomic features from detected keypoints.

    Returns:
        (features, unavailable_features, approximate_features) — features
        dict with float values, a list of feature names that could not be
        reliably computed due to low landmark visibility, and a list of
        feature names computed via a fallback method (e.g. image-vertical
        instead of hip-anchored) and marked as approximate.
    """
    kps = np.asarray(keypoints, dtype=float)
    if index_map is None:
        index_map = MEDIAPIPE_33 if len(kps) >= 25 else COCO_17

    # Determine which features are unavailable due to low visibility
    unavailable = unavailable_features_from_keypoints(keypoints, index_map)

    # Per-feature visibility overrides for angle-sensitive features.
    # Wrists can be partially occluded when arms are at sides or behind body,
    # while the angles are still usable at moderate visibility. Use 0.40 for all
    # angle-sensitive features to avoid false unavailable in normal seated/standing.
    _ANGLE_SENSITIVE_VIS_OVERRIDE = 0.40
    _ANGLE_SENSITIVE_FEATURES = {
        "left_shoulder_elev", "right_shoulder_elev",
        "elbow_flexion_angle", "upper_arm_angle_from_vertical",
    }
    for feature in _ANGLE_SENSITIVE_FEATURES:
        if feature not in unavailable:
            dependencies = FEATURE_DEPENDENCIES[feature]
            for landmark in dependencies:
                idx = index_map[landmark]
                if len(kps) > idx and kps.shape[1] >= 4 and kps[idx][3] < _ANGLE_SENSITIVE_VIS_OVERRIDE:
                    unavailable.append(feature)
                    break

    left_ear = _point(kps, index_map, "left_ear")
    right_ear = _point(kps, index_map, "right_ear")
    left_shoulder = _point(kps, index_map, "left_shoulder")
    right_shoulder = _point(kps, index_map, "right_shoulder")
    left_elbow = _point(kps, index_map, "left_elbow")
    right_elbow = _point(kps, index_map, "right_elbow")
    left_hip = _point(kps, index_map, "left_hip")
    right_hip = _point(kps, index_map, "right_hip")

    ear = _midpoint(left_ear, right_ear)
    neck = _midpoint(left_shoulder, right_shoulder)
    hip = _midpoint(left_hip, right_hip)
    shoulder_width = _safe_distance(left_shoulder, right_shoulder)
    # Minimum shoulder-width guard: prevents division explosion when the
    # person is in profile view and both shoulders project close together.
    # 15 px ≈ < 1% of a 1920-wide frame — only fires on genuinely narrow
    # projections, not on real shoulder widths.
    _min_sw = max(shoulder_width, 15.0)
    torso_len = _safe_distance(neck, hip, default=_min_sw)

    vertical_up_from_hip = np.array([hip[0], hip[1] - torso_len])
    vertical_down_left = np.array([left_shoulder[0], left_shoulder[1] + shoulder_width])
    vertical_down_right = np.array([right_shoulder[0], right_shoulder[1] + shoulder_width])

    raw_neck = angle_between_three_points(ear, neck, hip)
    neck_flexion = abs(180.0 - raw_neck)
    trunk_flexion = angle_between_three_points(neck, hip, vertical_up_from_hip)
    left_shoulder_elev = angle_between_three_points(left_elbow, left_shoulder, vertical_down_left)
    right_shoulder_elev = angle_between_three_points(right_elbow, right_shoulder, vertical_down_right)
    shoulder_symmetry = abs(left_shoulder[1] - right_shoulder[1]) / _min_sw * 100.0
    alignment_deviation = abs(ear[0] - hip[0]) / torso_len * 100.0

    # Knee angle (hip-knee-ankle, averaged L/R)
    left_knee_pt = _point(kps, index_map, "left_knee")
    right_knee_pt = _point(kps, index_map, "right_knee")
    left_ankle_pt = _point(kps, index_map, "left_ankle")
    right_ankle_pt = _point(kps, index_map, "right_ankle")
    left_knee_angle = angle_between_three_points(left_hip, left_knee_pt, left_ankle_pt)
    right_knee_angle = angle_between_three_points(right_hip, right_knee_pt, right_ankle_pt)
    knee_angle = (left_knee_angle + right_knee_angle) / 2.0

    # Elbow flexion angle (shoulder-elbow-wrist, averaged L/R)
    left_wrist_pt = _point(kps, index_map, "left_wrist")
    right_wrist_pt = _point(kps, index_map, "right_wrist")
    left_elbow_angle = angle_between_three_points(left_shoulder, left_elbow, left_wrist_pt)
    right_elbow_angle = angle_between_three_points(right_shoulder, right_elbow, right_wrist_pt)
    elbow_flexion_angle = (left_elbow_angle + right_elbow_angle) / 2.0

    # Upper arm angle from vertical (angle of the shoulder→wrist line away
    # from vertical-DOWN — arms hanging at the sides = 0 deg, matching the
    # RULA Table B upper-arm posture definition).
    vertical_up_left = np.array([left_shoulder[0], left_shoulder[1] - torso_len])
    vertical_up_right = np.array([right_shoulder[0], right_shoulder[1] - torso_len])
    left_upper_arm = abs(180.0 - angle_between_three_points(vertical_up_left, left_shoulder, left_wrist_pt))
    right_upper_arm = abs(180.0 - angle_between_three_points(vertical_up_right, right_shoulder, right_wrist_pt))
    upper_arm_angle_from_vertical = (left_upper_arm + right_upper_arm) / 2.0

    # ── Phase-A additions: head / hand / stance ergonomics ─────────────
    nose = _safe_point(kps, index_map, "nose")
    left_index = _safe_point(kps, index_map, "left_index")
    right_index = _safe_point(kps, index_map, "right_index")
    left_thumb = _safe_point(kps, index_map, "left_thumb")
    right_thumb = _safe_point(kps, index_map, "right_thumb")
    left_ankle_pt = _safe_point(kps, index_map, "left_ankle")
    right_ankle_pt = _safe_point(kps, index_map, "right_ankle")
    left_hip_pt = _safe_point(kps, index_map, "left_hip")
    right_hip_pt = _safe_point(kps, index_map, "right_hip")

    # forward_head_posture: head protrusion as a TRUE ANGLE in degrees — the
    # angle between the vertical axis through the neck and the line from the
    # neck to the head centre (ear midpoint; nose only as a fallback when the
    # ears are occluded). Head directly above the neck = 0 deg; a forward-
    # jutting head reads as a real angle, matching the RULA/REBA neck-posture
    # bands the 10/20 deg thresholds expect. The previous "% of shoulder
    # width" ratio was unbounded and exploded in profile view, where the
    # shoulders project to near-zero width (observed values like 862.3).
    ear_ok = bool(np.isfinite(ear).all())
    nose_ok = nose is not None and bool(np.isfinite(nose).all())
    if ear_ok:
        head_ref = ear
    elif nose_ok:
        head_ref = nose
    else:
        head_ref = None
    if head_ref is not None:
        vertical_up_from_neck = np.array([neck[0], neck[1] - torso_len])
        forward_head_posture = angle_between_three_points(
            vertical_up_from_neck, neck, head_ref
        )
    else:
        forward_head_posture = float("nan")
    if forward_head_posture != forward_head_posture:
        # No head reference visible — mark unavailable explicitly so the value
        # is never serialized as 0.0 (which would read as a safe reading).
        if "forward_head_posture" not in unavailable:
            unavailable.append("forward_head_posture")

    # head_tilt_angle: lateral (roll) tilt of the head relative to the torso,
    # measured as the angle between the ear-to-ear line and the shoulder-to-
    # shoulder line. A level head = 0 deg regardless of camera framing; the
    # head leaning toward a shoulder registers as real degrees (RULA/REBA
    # neck-lateral posture). The previous "ear→nose vs image-vertical"
    # convention assumed a profile view and read 150-173 deg on neutral
    # frontal webcam poses (nose naturally at/below the ear line), which
    # fired HIGH on every frame.
    if (
        np.isfinite(left_ear).all()
        and np.isfinite(right_ear).all()
        and np.isfinite(left_shoulder).all()
        and np.isfinite(right_shoulder).all()
    ):
        v_ear = np.array([right_ear[0] - left_ear[0], right_ear[1] - left_ear[1]], dtype=float)
        v_sh = np.array(
            [right_shoulder[0] - left_shoulder[0], right_shoulder[1] - left_shoulder[1]], dtype=float
        )
        denom = np.linalg.norm(v_ear) * np.linalg.norm(v_sh)
        if denom > 0:
            cos_a = float(np.clip(np.dot(v_ear, v_sh) / denom, -1.0, 1.0))
            raw_tilt = float(np.degrees(np.arccos(cos_a)))
            # Acute angle between the two lines: 0 deg = level, 90 deg = fully
            # sideways. Mirrors shoulder_symmetry's absolute-deviation style.
            head_tilt_angle = min(raw_tilt, 180.0 - raw_tilt)
        else:
            head_tilt_angle = float("nan")
    else:
        head_tilt_angle = float("nan")

    # wrist_deviation_angle: how far the hand direction deviates from the
    # forearm line at the wrist (RULA Table B). Straight = 0 deg.
    def _wrist_dev(elbow_pt, wrist_pt, index_pt):
        if elbow_pt is None or wrist_pt is None or index_pt is None:
            return float("nan")
        angle = angle_between_three_points(elbow_pt, wrist_pt, index_pt)
        if angle != angle:
            return float("nan")
        return abs(180.0 - angle)

    left_wrist_dev = _wrist_dev(left_elbow, left_wrist_pt, left_index)
    right_wrist_dev = _wrist_dev(right_elbow, right_wrist_pt, right_index)
    if left_wrist_dev == left_wrist_dev and right_wrist_dev == right_wrist_dev:
        wrist_deviation_angle = (left_wrist_dev + right_wrist_dev) / 2.0
    else:
        wrist_deviation_angle = left_wrist_dev if left_wrist_dev == left_wrist_dev else right_wrist_dev

    # stance features (heels/foot-index would refine these; ankles+hips are robust)
    if left_ankle_pt is not None and right_ankle_pt is not None \
            and left_hip_pt is not None and right_hip_pt is not None:
        ankle_span = _safe_distance(left_ankle_pt, right_ankle_pt)
        hip_span = _safe_distance(left_hip_pt, right_hip_pt)
        stance_width_ratio = ankle_span / hip_span
        stance_stability = min(stance_width_ratio, 1.0 / stance_width_ratio)
        mid_ankle = _midpoint(left_ankle_pt, right_ankle_pt)
        weight_shift_offset = abs(mid_ankle[0] - hip[0]) / torso_len * 100.0
    else:
        stance_width_ratio = float("nan")
        stance_stability = float("nan")
        weight_shift_offset = float("nan")

    # hand_reach_ratio: how far the fingertips reach from the shoulders
    # (task signal; feeds reaching/tool-use recognition).
    reach_dists = []
    if left_index is not None and np.isfinite(left_index).all():
        reach_dists.append(_safe_distance(left_index, neck))
    if right_index is not None and np.isfinite(right_index).all():
        reach_dists.append(_safe_distance(right_index, neck))
    hand_reach_ratio = float(np.mean(reach_dists)) / torso_len if reach_dists else float("nan")

    # finger_spread_ratio: index-thumb spread relative to wrist-index length
    # (gripping / tool-use proxy).
    def _spread(wrist_pt, index_pt, thumb_pt):
        if wrist_pt is None or index_pt is None or thumb_pt is None:
            return float("nan")
        hand_len = _safe_distance(wrist_pt, index_pt)
        return _safe_distance(index_pt, thumb_pt, default=0.0) / hand_len

    l_spread = _spread(left_wrist_pt, left_index, left_thumb)
    r_spread = _spread(right_wrist_pt, right_index, right_thumb)
    if l_spread == l_spread and r_spread == r_spread:
        finger_spread_ratio = (l_spread + r_spread) / 2.0
    else:
        finger_spread_ratio = l_spread if l_spread == l_spread else r_spread

    # alignment_deviation should be NaN if any of its required landmarks are unavailable
    raw_alignment_deviation = alignment_deviation
    if "alignment_deviation" in unavailable:
        raw_alignment_deviation = float("nan")

    raw_features = {
        "neck_flexion": neck_flexion,
        "trunk_flexion": trunk_flexion,
        "left_shoulder_elev": left_shoulder_elev,
        "right_shoulder_elev": right_shoulder_elev,
        "shoulder_symmetry": shoulder_symmetry,
        "alignment_deviation": raw_alignment_deviation,
        "knee_angle": knee_angle,
        "elbow_flexion_angle": elbow_flexion_angle,
        "upper_arm_angle_from_vertical": upper_arm_angle_from_vertical,
        "forward_head_posture": forward_head_posture,
        "head_tilt_angle": head_tilt_angle,
        "wrist_deviation_angle": wrist_deviation_angle,
        "stance_stability": stance_stability,
        "weight_shift_offset": weight_shift_offset,
        "hand_reach_ratio": hand_reach_ratio,
        "finger_spread_ratio": finger_spread_ratio,
        "stance_width_ratio": stance_width_ratio,
    }

    # For unavailable features, use NaN sentinel (not 0.0 which looks like "safe")
    features = {}
    for name in FEATURE_COLUMNS:
        val = raw_features[name]
        if name in unavailable:
            features[name] = float("nan")
        else:
            features[name] = round(float(np.nan_to_num(val, nan=0.0)), 4)

    # ── Hip-free fallbacks ─────────────────────────────────────────────
    # When hip landmarks are unavailable but ears+shoulders are visible,
    # compute neck_flexion and alignment_deviation using image-vertical
    # reference instead of the hip. Marked with approximate flags so
    # downstream consumers know these are less precise (head-vs-image-
    # vertical rather than head-vs-actual-trunk).
    approximate_features: list[str] = []

    # neck_flexion hip-free fallback
    if "neck_flexion" in unavailable:
        # Verify ear+shoulder data is actually usable (should be since
        # neck_flexion's only missing dependency is hip landmarks)
        if np.isfinite(ear).all() and np.isfinite(neck).all():
            fake_hip = np.array([neck[0], neck[1] + torso_len])
            raw_approx = angle_between_three_points(ear, neck, fake_hip)
            approx_val = abs(180.0 - raw_approx)
            if approx_val == approx_val:
                features["neck_flexion"] = round(float(approx_val), 4)
                unavailable.remove("neck_flexion")
                approximate_features.append("neck_flexion")

    # alignment_deviation hip-free fallback (use neck x as vertical reference instead of image-center)
    if "alignment_deviation" in unavailable:
        if np.isfinite(ear).all() and np.isfinite(neck).all():
            approx_val = abs(ear[0] - neck[0]) / torso_len * 100.0
            if approx_val == approx_val:
                features["alignment_deviation"] = round(float(approx_val), 4)
                unavailable.remove("alignment_deviation")
                approximate_features.append("alignment_deviation")

    return features, unavailable, approximate_features


# Risk-rule thresholds — tuned against the REBA-labeled dataset
# (scripts/tune_risk_thresholds.py, 30698 poses). The tuned set raises the
# weight_shift / shoulder_symmetry cutoffs (the two features causing most
# false-HIGH over-alarm) while keeping **zero** REBA-HIGH poses scored LOW:
#   agreement 34.0% -> 36.9%   kappa 0.085 -> 0.107   ruleHIGH 80.0% -> 73.5%
RISK_THRESHOLDS: dict[str, tuple[float, float]] = {
    # feature -> (MEDIUM cutoff, HIGH cutoff)
    "neck_flexion": (10.0, 30.0),
    "trunk_flexion": (20.0, 60.0),
    "shoulder_elev": (30.0, 60.0),
    "shoulder_symmetry": (9.0, 18.0),
    "knee_angle": (150.0, 100.0),  # inverted: lower = riskier
    "forward_head_posture": (10.0, 20.0),
    "head_tilt_angle": (10.0, 20.0),
    "wrist_deviation_angle": (5.0, 15.0),
    "stance_stability": (0.7, 0.5),  # inverted: lower = riskier
    "weight_shift_offset": (12.5, 25.0),
}

# Unknown-value fallbacks (NaN / unavailable landmarks score as elevated risk).
_UNKNOWN_VALUES: dict[str, float] = {
    "neck_flexion": 10.0,
    "trunk_flexion": 20.0,
    "shoulder_elev": 30.0,
    # Per-side shoulder features share the aggregated shoulder fallback —
    # risk_from_features looks these up directly and they must never KeyError.
    "left_shoulder_elev": 30.0,
    "right_shoulder_elev": 30.0,
    "shoulder_symmetry": 9.0,
    "knee_angle": 140.0,
    "forward_head_posture": 10.0,
    "head_tilt_angle": 10.0,
    "wrist_deviation_angle": 5.0,
    "stance_stability": 0.6,
    "weight_shift_offset": 5.0,
}


def risk_from_features(
    features: Mapping[str, float],
    unavailable_features: list[str] | None = None,
    threshold_multiplier: float = 1.0,
    thresholds: Mapping[str, tuple[float, float]] | None = None,
    task_label: str | None = None,
    task_confidence: float = 100.0,
) -> str:
    """Compute risk level from extracted features.

    When unavailable_features is provided OR features contain NaN values
    (from low-visibility landmarks), features that couldn't be computed
    are treated as "unknown" — scored as elevated risk rather than safe,
    since we can't confirm the posture is fine.

    ``threshold_multiplier`` scales the MEDIUM/HIGH cutoffs (default 1.0 =
    the calibrated RISK_THRESHOLDS). Multipliers < 1 make the rules more
    lenient (fewer HIGH verdicts); > 1 stricter. ``thresholds`` overrides
    RISK_THRESHOLDS entirely (used by the offline tuning sweep and tests).

    ``task_label`` selects a task-specific threshold table when available,
    producing risk scores that account for the biomechanical demands of
    the detected activity.  When task_label is None or confidence is below
    the classifier gate, the baseline RISK_THRESHOLDS are used.
    """
    unavailable = set(unavailable_features or ())
    m = float(threshold_multiplier)
    if thresholds is not None:
        t = dict(thresholds)
    elif task_label and task_label in task_thresholds and task_confidence >= 50.0:
        # Merge task-specific thresholds onto the baseline defaults, so any
        # feature not overridden by the task table inherits the calibrated
        # baseline value.
        t = dict(RISK_THRESHOLDS)
        t.update(task_thresholds[task_label])
    else:
        t = dict(RISK_THRESHOLDS)
    unk = _UNKNOWN_VALUES

    def _unknown_for(name: str) -> float:
        """Unknown-value fallback, never raising for an unexpected feature name."""
        value = unk.get(name)
        if value is not None:
            return value
        # Side-specific shoulder features share the aggregated shoulder fallback.
        return unk.get("shoulder_elev", 30.0)

    # Physically impossible angle bounds for a standing worker. Corrupt pose
    # estimates (person half out of frame, landmarks snapped to furniture) can
    # produce absurd values like trunk flexion 176 deg or neck flexion 130 deg;
    # those must NOT score HIGH - an impossible pose is not an assessment, so
    # the feature falls back to its unknown value (which sits exactly at the
    # MEDIUM cutoff and therefore contributes nothing).
    _IMPLAUSIBLE_MAX = {
        "neck_flexion": 90.0,  # head cannot bend past horizontal from vertical
        "trunk_flexion": 90.0,  # torso cannot go past horizontal from vertical
        "shoulder_symmetry": 150.0,
        "forward_head_posture": 90.0,  # true angle from vertical, bounded 0-90
        "head_tilt_angle": 90.0,
        "wrist_deviation_angle": 180.0,
        "weight_shift_offset": 200.0,
    }

    def _get(name: str, default: float) -> float:
        """Get a feature value, treating NaN, explicitly unavailable, and
        physically impossible values as unknown."""
        if name in unavailable:
            return _unknown_for(name)
        val = features.get(name, default)
        if val != val:  # NaN check
            return _unknown_for(name)
        limit = _IMPLAUSIBLE_MAX.get(name)
        if limit is not None and val > limit:
            return _unknown_for(name)
        return val

    shoulder = max(
        _get("left_shoulder_elev", 0.0),
        _get("right_shoulder_elev", 0.0),
    )
    neck = _get("neck_flexion", 0.0)
    trunk = _get("trunk_flexion", 0.0)
    sym = _get("shoulder_symmetry", 0.0)
    knee = _get("knee_angle", 180.0)
    fhp = _get("forward_head_posture", 0.0)
    head_tilt = _get("head_tilt_angle", 0.0)
    wrist_dev = _get("wrist_deviation_angle", 0.0)
    stance = _get("stance_stability", 1.0)
    weight_shift = _get("weight_shift_offset", 0.0)

    neck_med, neck_high = t["neck_flexion"]
    trunk_med, trunk_high = t["trunk_flexion"]
    sh_med, sh_high = t["shoulder_elev"]
    sym_med, sym_high = t["shoulder_symmetry"]
    knee_med, knee_high = t["knee_angle"]
    fhp_med, fhp_high = t["forward_head_posture"]
    ht_med, ht_high = t["head_tilt_angle"]
    wd_med, wd_high = t["wrist_deviation_angle"]
    st_med, st_high = t["stance_stability"]
    ws_med, ws_high = t["weight_shift_offset"]

    if (
        neck > neck_high * m
        or trunk > trunk_high * m
        or shoulder > sh_high * m
        or sym > sym_high * m
        or knee < knee_high / m
        or fhp > fhp_high * m
        or head_tilt > ht_high * m
        or wrist_dev > wd_high * m
        or stance < st_high / m
        or weight_shift > ws_high * m
    ):
        return "HIGH"
    if (
        neck > neck_med * m
        or trunk > trunk_med * m
        or shoulder > sh_med * m
        or sym > sym_med * m
        or knee < knee_med / m
        or fhp > fhp_med * m
        or head_tilt > ht_med * m
        or wrist_dev > wd_med * m
        or stance < st_med / m
        or weight_shift > ws_med * m
    ):
        return "MEDIUM"

    # If ANY lower-body feature was unavailable (NaN or explicitly marked), don't claim LOW —
    # we can't confirm safety without full visibility.
    nan_features = {name for name in FEATURE_COLUMNS if features.get(name, 0.0) != features.get(name, 0.0)}
    lower_body_missing = (unavailable | nan_features) & {
        "trunk_flexion", "knee_angle", "neck_flexion",
        "stance_stability", "weight_shift_offset",
    }
    if lower_body_missing:
        return "MEDIUM"

    return "LOW"


def risk_breakdown(
    features: Mapping[str, float],
    calibration: "PostureCalibration | None" = None,
) -> Dict[str, RiskBreakdown]:
    """Per-feature risk bands for segment colors and UI feature cards.

    Reads the (MEDIUM, HIGH) cutoffs from the active posture calibration
    (defaults to the ``RISK_CALIBRATION`` profile — relaxed), so the
    overlay only colors a joint yellow/red once its posture actually
    exceeds the operator's chosen strain allowance. ``risk_from_features``
    (the legacy gate) intentionally keeps the pinned RISK_THRESHOLDS.
    """
    if calibration is None:
        from backend.services.calibration import load_calibration
        calibration = load_calibration()
    cutoffs = calibration.feature_cutoffs
    breakdown: Dict[str, RiskBreakdown] = {}
    for name, value in features.items():
        # Treat NaN as "unknown" — show as a distinct color
        if value != value:  # NaN check
            breakdown[name] = RiskBreakdown(level="UNKNOWN", color=(128, 128, 128))
            continue

        # Inverted features: LOWER value = HIGHER risk (knee_angle, stance_stability)
        inverted = name in {"knee_angle", "stance_stability"}
        # Motion/reference signals are not posture-risk features — show LOW.
        if name in {"movement_velocity", "wrist_movement_velocity", "hand_reach_ratio",
                     "finger_spread_ratio", "stance_width_ratio"}:
            breakdown[name] = RiskBreakdown(level="LOW", color=RISK_COLORS_BGR["LOW"])
            continue

        # Read cutoffs from the active calibration so segment colors and the
        # UI feature cards follow the operator's strain allowance.
        if name in cutoffs:
            medium, high = cutoffs[name]
        elif name == "alignment_deviation":
            high, medium = 50.0, 20.0
        else:
            high, medium = 30.0, 10.0

        if inverted:
            level = "HIGH" if value < high else "MEDIUM" if value < medium else "LOW"
        else:
            level = "HIGH" if value > high else "MEDIUM" if value > medium else "LOW"
        breakdown[name] = RiskBreakdown(level=level, color=RISK_COLORS_BGR[level])
    return breakdown


def compute_rula_informed_score(
    features: Mapping[str, float],
    unavailable_features: list[str] | None = None
) -> Dict[str, int | bool]:
    """Compute a faithful RULA grand score (1-7) from extracted features.

    Delegates to :func:`backend.services.standard_assessment.compute_rula_score`
    (the same tables the authoritative RULA/REBA gate uses) so the API's
    informational ``rula_informed_score`` always agrees with the risk engine.
    Returns {"rula_informed_score": int, "is_partial_score": bool, ...}.
    """
    from backend.services.standard_assessment import compute_rula_score

    result = compute_rula_score(
        features, list(unavailable_features or []), legs_visible=True
    )
    return result


def mediapipe_landmarks_to_keypoints(landmarks: Iterable[object], width: int, height: int) -> list[list[float]]:
    keypoints = []
    for landmark in landmarks:
        keypoints.append(
            [
                float(landmark.x) * width,
                float(landmark.y) * height,
                float(getattr(landmark, "z", 0.0)),
                float(getattr(landmark, "visibility", getattr(landmark, "presence", 1.0))),
            ]
        )
    return keypoints


def unavailable_features_from_keypoints(
    keypoints: Sequence[Sequence[float]],
    index_map: Mapping[str, int] | None = None,
    min_visibility: float = 0.35,
) -> list[str]:
    """Determine which features cannot be reliably computed from keypoints.

    Checks per-landmark visibility scores (MediaPipe's confidence per joint).
    Features requiring landmarks with visibility below min_visibility are
    marked as unavailable.
    """
    kps = np.asarray(keypoints, dtype=float)
    if index_map is None:
        index_map = MEDIAPIPE_33 if len(kps) >= 25 else COCO_17

    unavailable = []
    for feature, landmarks in FEATURE_DEPENDENCIES.items():
        for landmark in landmarks:
            # Landmark not present in this index map (e.g. fingers/feet on COCO_17)
            if landmark not in index_map:
                unavailable.append(feature)
                break
            idx = index_map[landmark]
            if idx >= len(kps):
                unavailable.append(feature)
                break
            # If no visibility column (shape[1] < 4), assume visible
            if kps.shape[1] >= 4 and kps[idx][3] < min_visibility:
                unavailable.append(feature)
                break
    return unavailable


def lower_body_confidence(keypoints: Sequence[Sequence[float]], index_map: Mapping[str, int] | None = None) -> float:
    """Compute confidence score (0-100) for lower-body landmarks only."""
    kps = np.asarray(keypoints, dtype=float)
    if index_map is None:
        index_map = MEDIAPIPE_33 if len(kps) >= 25 else COCO_17
    if kps.shape[1] < 4:
        return 0.0

    lower_indices = [index_map[name] for name in ["left_hip", "right_hip", "left_knee", "right_knee", "left_ankle", "right_ankle"]]
    vis_vals = [kps[i][3] for i in lower_indices if i < len(kps)]
    return float(np.mean(vis_vals)) * 100 if vis_vals else 0.0
