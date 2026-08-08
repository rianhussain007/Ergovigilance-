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
    # Phase-A additions (2026-08) — use nose, fingers, heels/feet
    "forward_head_posture": ["left_ear", "right_ear", "left_shoulder", "right_shoulder", "nose"],
    "head_tilt_angle": ["left_ear", "right_ear", "nose"],
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
    torso_len = _safe_distance(neck, hip, default=shoulder_width)

    vertical_up_from_hip = np.array([hip[0], hip[1] - torso_len])
    vertical_down_left = np.array([left_shoulder[0], left_shoulder[1] + shoulder_width])
    vertical_down_right = np.array([right_shoulder[0], right_shoulder[1] + shoulder_width])

    raw_neck = angle_between_three_points(ear, neck, hip)
    neck_flexion = abs(180.0 - raw_neck)
    trunk_flexion = angle_between_three_points(neck, hip, vertical_up_from_hip)
    left_shoulder_elev = angle_between_three_points(left_elbow, left_shoulder, vertical_down_left)
    right_shoulder_elev = angle_between_three_points(right_elbow, right_shoulder, vertical_down_right)
    shoulder_symmetry = abs(left_shoulder[1] - right_shoulder[1]) / shoulder_width * 100.0
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

    # forward_head_posture: horizontal protrusion of the head (nose + ear-mid
    # average as a head-centre proxy) ahead of the neck, in % of shoulder width.
    head_refs = [ear]
    if nose is not None and np.isfinite(nose).all():
        head_refs.append(nose)
    if head_refs:
        head_centre_x = float(np.mean([p[0] for p in head_refs]))
        forward_head_posture = abs(head_centre_x - neck[0]) / shoulder_width * 100.0
    else:
        forward_head_posture = float("nan")

    # head_tilt_angle: deviation of the ear→nose vector from image vertical.
    # A level head (nose straight above ear) yields 0 deg; 180-raw converts
    # the at-ear angle to an off-vertical deviation.
    if nose is not None and np.isfinite(nose).all() and np.isfinite(ear).all():
        below = np.array([ear[0], ear[1] + 1.0])
        raw_tilt = angle_between_three_points(below, ear, nose)
        head_tilt_angle = abs(180.0 - raw_tilt) if raw_tilt == raw_tilt else float("nan")
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
    """
    unavailable = set(unavailable_features or ())
    m = float(threshold_multiplier)
    t = dict(thresholds) if thresholds is not None else dict(RISK_THRESHOLDS)
    unk = _UNKNOWN_VALUES

    def _get(name: str, default: float) -> float:
        """Get a feature value, treating NaN and explicitly unavailable as unknown."""
        if name in unavailable:
            return unk[name]
        val = features.get(name, default)
        if val != val:  # NaN check
            return unk[name]
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


def risk_breakdown(features: Mapping[str, float]) -> Dict[str, RiskBreakdown]:
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

        # Read cutoffs from the single source of truth (RISK_THRESHOLDS) so the
        # per-feature breakdown never disagrees with risk_from_features.
        _key = {
            "left_shoulder_elev": "shoulder_elev",
            "right_shoulder_elev": "shoulder_elev",
        }.get(name, name)
        if _key in RISK_THRESHOLDS:
            medium, high = RISK_THRESHOLDS[_key]
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


def _band(value: float, thresholds: list[float]) -> int:
    """Convert a degree value to a RULA band score (1-4).

    thresholds: list of [low_cutoff, med_cutoff, high_cutoff] boundaries.
    Returns 1 if below first threshold, 2 if between first and second, etc.
    """
    for i, t in enumerate(thresholds):
        if value < t:
            return i + 1
    return len(thresholds) + 1


def compute_rula_informed_score(
    features: Mapping[str, float],
    unavailable_features: list[str] | None = None
) -> Dict[str, int | bool]:
    """Compute an informed RULA-style score (1-7) from extracted features.

    Uses a simplified mapping from ergonomic feature angles to RULA Table A/B/C.
    Returns {"rula_informed_score": int, "is_partial_score": bool}.
    """
    unavailable = set(unavailable_features or [])

    neck = features.get("neck_flexion", 0.0)
    trunk = features.get("trunk_flexion", 0.0)
    head_tilt = features.get("head_tilt_angle", 0.0)
    wrist_dev = features.get("wrist_deviation_angle", 0.0)
    stance = features.get("stance_stability", 1.0)

    # Conservative knee angle default (HIGH risk if knee_angle is unavailable:
    # Assume 90 degrees (which makes legs_b = 3, worst case)
    knee = features.get("knee_angle", 90.0) if "knee_angle" in unavailable else features.get("knee_angle", 180.0)
    # If knee_angle is NaN or unavailable, use 90 as conservative default:
    knee_val = knee if (knee == knee) else 90.0

    # Newly added features may be NaN/partial — treat as neutral (no penalty)
    # unless unavailable is explicitly reported, mirroring the wrist-default gap.
    is_partial = "knee_angle" in unavailable or (knee != knee)
    if wrist_dev != wrist_dev or "wrist_deviation_angle" in unavailable:
        is_partial = True
        wrist_dev = 0.0
    if head_tilt != head_tilt:
        head_tilt = 0.0
    if stance != stance:
        stance = 1.0

    shoulder_l = features.get("left_shoulder_elev", 0.0)
    shoulder_r = features.get("right_shoulder_elev", 0.0)
    shoulder = max(shoulder_l, shoulder_r)
    elbow_l = features.get("elbow_flexion_angle", 90.0)
    elbow_r = features.get("elbow_flexion_angle", 90.0)
    upper_arm = features.get("upper_arm_angle_from_vertical", 0.0)

    # --- Table A: Neck / Trunk / Legs ---
    neck_b = _band(neck, [10, 20, 30])
    # Head tilt off vertical adds to the neck posture band (looking down).
    if head_tilt > 20:
        neck_b = min(neck_b + 1, 4)
    elif head_tilt > 10:
        neck_b = min(neck_b + 1, 4) if neck_b >= 3 else neck_b
    trunk_b = _band(trunk, [20, 40, 60])
    legs_b = 1 if knee_val >= 150 else 2 if knee_val >= 100 else 3
    # Unstable stance (narrow/wide base) adds to the legs posture band.
    if stance < 0.5:
        legs_b = min(legs_b + 1, 3)
    score_a_table = [
        [1, 2, 3, 4],
        [2, 3, 4, 5],
        [3, 4, 5, 6],
    ]
    row_a = min(trunk_b - 1, 2)
    col_a = min(neck_b - 1, 3)
    table_a = score_a_table[row_a][col_a] + (legs_b - 1)

    # --- Table B: Arm / Wrist ---
    arm_b = _band(upper_arm, [20, 45, 90])
    elbow_b_l = _band(elbow_l, [45, 90, 150])
    elbow_b_r = _band(elbow_r, [45, 90, 150])
    elbow_b = max(elbow_b_l, elbow_b_r)
    # RULA Table B wrist deviation: 0 deg = neutral, <=15 deg = +1, >15 deg = +2.
    wrist_bonus = 1 if wrist_dev > 5 else 0
    if wrist_dev > 15:
        wrist_bonus = 2
    score_b_table = [
        [1, 2, 3, 4],
        [2, 3, 4, 5],
        [3, 4, 5, 6],
    ]
    row_b = min(arm_b - 1, 2)
    col_b = min(elbow_b - 1 + wrist_bonus, 3)
    table_b = score_b_table[row_b][col_b]

    # --- Table C: Combined Score ---
    combined_a = max(table_a, 1)
    combined_b = max(table_b, 1)
    score_c_table = [
        [1, 2, 3, 4, 5, 6],
        [2, 3, 4, 5, 6, 7],
        [3, 4, 5, 6, 7, 7],
    ]
    row_c = min(combined_a - 1, 2)
    col_c = min(combined_b - 1, 5)
    final_score = score_c_table[row_c][col_c]

    return {
        "rula_informed_score": final_score,
        "is_partial_score": is_partial
    }


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
