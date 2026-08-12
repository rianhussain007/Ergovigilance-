"""Standard ergonomic risk assessment — RULA vs REBA gated by body visibility.

This module is the authoritative posture-risk gate for ErgoVigilance. The
legacy ``risk_from_features`` threshold rules can fire HIGH from a single
loose per-feature cutoff (e.g. shoulder_symmetry > 15%) without any actual
RULA/REBA rule violation. Here, risk is derived from the two standard
observational methods, so a HIGH verdict means a published rule was broken:

- **REBA** (Rapid Entire Body Assessment) — used when the FULL body is
  visible. Requires neck, trunk, arms, wrists AND legs (hips/knees/ankles).
- **RULA** (Rapid Upper Limb Assessment) — used when only the UPPER body is
  visible (legs out of frame, seated behind a desk, workbench close-up).
  RULA scores neck, trunk, arms and wrists; it does NOT require the legs, so
  a worker with their legs out of frame can still be assessed instead of
  being flagged "can't confirm safe".

Method selection is driven by ``lower_body_confidence`` (0-100 = mean
visibility of hips/knees/ankles): at or above ``FULL_BODY_THRESHOLD`` the
whole body is in view and REBA is applied; below it, RULA is applied.

Band mapping (documented, standard action levels):

    REBA Score C:  1-3 -> LOW, 4-7 -> MEDIUM, 8+ -> HIGH  (action 0-1 / 2 / 3-4)
    RULA grand:    1-2 -> LOW, 3-4 -> MEDIUM, 5+ -> HIGH  (action 1-2 / 3-4 / 5-7)

Fidelity note: both methods are computed from 2D projected joint angles
(the same approximation the pipeline's feature extractor uses), so twisting /
side-bending adjuncts that 2D cannot resolve are omitted — matching the
documented convention in ``backend.services.reba_scoring``.
"""

from __future__ import annotations

from typing import Dict, List, Mapping, Optional, Sequence

import numpy as np

from backend.services.calibration import PostureCalibration, load_calibration
from backend.services.features import compute_rula_informed_score
from backend.services.reba_scoring import reba_from_keypoints

# lower_body_confidence (0-100) at/above which the full body is considered
# visible and REBA applies. Below this the legs are out of frame / occluded
# and RULA (upper-limb) applies instead.
FULL_BODY_THRESHOLD = 50.0

# Minimum landmark visibility (MediaPipe 0-1) for a joint to count as present
# when building the REBA point map. Below this the joint is treated as missing
# and REBA scores it as a neutral cell (never a worst-case).
_MIN_VIS = 0.35

# MediaPipe 33 pose-landmark indices used by the REBA adapter.
_MP = {
    "nose": 0,
    "left_eye": 2,
    "right_eye": 5,
    "left_ear": 7,
    "right_ear": 8,
    "left_shoulder": 11,
    "right_shoulder": 12,
    "left_elbow": 13,
    "right_elbow": 14,
    "left_wrist": 15,
    "right_wrist": 16,
    "left_index": 19,
    "right_index": 20,
    "left_hip": 23,
    "right_hip": 24,
    "left_knee": 25,
    "right_knee": 26,
    "left_ankle": 27,
    "right_ankle": 28,
}


# ── RULA tables (McAtamney & Corlett, 1993) ────────────────────────

# Table A: upper arm (rows 1-6) x lower arm (cols 1-2) -> [wrist 1, 2, 3].
_RULA_TABLE_A: Dict[int, Dict[int, List[int]]] = {
    1: {1: [1, 2, 3], 2: [2, 3, 4]},
    2: {1: [2, 3, 4], 2: [3, 4, 5]},
    3: {1: [3, 4, 5], 2: [4, 5, 6]},
    4: {1: [4, 5, 6], 2: [5, 6, 7]},
    5: {1: [5, 6, 7], 2: [6, 7, 8]},
    6: {1: [6, 7, 8], 2: [7, 8, 9]},
}

# Table B: neck (rows 1-6) x trunk (cols 1-6). Legs contributes separately.
_RULA_TABLE_B: List[List[int]] = [
    [1, 2, 3, 4, 5, 6],
    [2, 3, 4, 5, 6, 7],
    [3, 4, 5, 6, 7, 8],
    [4, 5, 6, 7, 8, 9],
    [5, 6, 7, 8, 9, 9],
    [6, 7, 8, 9, 9, 9],
]

# Table C: Score A (rows 1-9) x Score B (cols 1-9) -> grand score 1-7.
_RULA_TABLE_C: List[List[int]] = [
    [1, 2, 3, 3, 4, 5, 5, 6, 7],
    [2, 2, 3, 4, 4, 5, 6, 6, 7],
    [3, 3, 3, 4, 4, 5, 6, 7, 7],
    [3, 3, 3, 4, 5, 6, 6, 7, 7],
    [4, 4, 4, 5, 6, 7, 7, 7, 7],
    [4, 4, 5, 6, 6, 7, 7, 7, 7],
    [5, 5, 6, 6, 7, 7, 7, 7, 7],
    [5, 5, 6, 7, 7, 7, 7, 7, 7],
    [6, 6, 6, 7, 7, 7, 7, 7, 7],
]


def reba_score_to_band(score: int) -> str:
    """Map a REBA Score C (1-15) to the LOW/MEDIUM/HIGH band.

    Standard REBA action levels: 1 = negligible (0), 2-3 = low (1),
    4-7 = medium (2), 8-10 = high (3), 11+ = very high (4).
    """
    if score <= 3:
        return "LOW"
    if score <= 7:
        return "MEDIUM"
    return "HIGH"


def rula_score_to_band(score: int) -> str:
    """Map a RULA grand score (1-7) to the LOW/MEDIUM/HIGH band.

    Standard RULA action levels: 1-2 = acceptable, 3-4 = investigate,
    5-6 = investigate soon, 7 = investigate and change immediately.
    """
    if score <= 2:
        return "LOW"
    if score <= 4:
        return "MEDIUM"
    return "HIGH"


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _rula_upper_arm(upper_arm_angle: float, shoulder_elev: float,
                    cal: PostureCalibration) -> int:
    """RULA upper-arm posture score from angle-from-vertical (+ raised)."""
    angle = 0.0 if upper_arm_angle != upper_arm_angle else upper_arm_angle
    if angle <= cal.upper_arm_neutral_max:
        score = 1
    elif angle <= cal.upper_arm_medium_max:
        score = 2
    elif angle <= cal.upper_arm_high_max:
        score = 3
    else:
        score = 4
    if shoulder_elev == shoulder_elev and shoulder_elev > cal.shoulder_elev_deg:
        score += 1  # shoulder raised
    return min(score, 6)


def _rula_lower_arm(elbow_flexion: float, cal: PostureCalibration) -> int:
    """RULA lower-arm posture score (neutral elbow flexion = 1, else 2)."""
    if elbow_flexion != elbow_flexion:
        return 1  # unavailable -> neutral
    return 1 if cal.elbow_neutral_min <= elbow_flexion <= cal.elbow_neutral_max else 2


def _rula_wrist(wrist_deviation: float, cal: PostureCalibration) -> int:
    """RULA wrist posture score (neutral / medium / deviated bands)."""
    if wrist_deviation != wrist_deviation:
        return 1
    if wrist_deviation <= cal.wrist_neutral_max:
        return 1
    if wrist_deviation <= cal.wrist_medium_max:
        return 2
    return 3


def _rula_neck(neck_flexion: float, head_tilt: float,
               cal: PostureCalibration) -> int:
    """RULA neck posture score (+1 for side-bend via head tilt)."""
    if neck_flexion != neck_flexion:
        score = 1
    elif neck_flexion <= cal.neck_neutral_max:
        score = 1
    elif neck_flexion <= cal.neck_high_max:
        score = 2
    else:
        score = 3
    if head_tilt == head_tilt and head_tilt > cal.neck_side_bend_max:
        score += 1  # lateral side-bend
    return min(score, 6)


def _rula_trunk(trunk_flexion: float, cal: PostureCalibration) -> int:
    """RULA trunk posture score (neutral / medium / high / severe bands)."""
    if trunk_flexion != trunk_flexion:
        return 1
    if trunk_flexion <= cal.trunk_neutral_max:
        return 1
    if trunk_flexion <= cal.trunk_medium_max:
        return 2
    if trunk_flexion <= cal.trunk_high_max:
        return 3
    return 4


def _rula_legs(stance_stability: float, legs_visible: bool,
               cal: PostureCalibration) -> int:
    """RULA legs posture score (1 = bilateral supported, 2 = unsupported).

    When the legs are NOT visible (RULA partial-body path) they default to
    neutral (1) — RULA does not require the legs, and penalizing a worker for
    an out-of-frame lower body would defeat the point of the partial-body
    assessment.
    """
    if not legs_visible:
        return 1
    if stance_stability != stance_stability:
        return 1
    return 2 if stance_stability < cal.stance_stability_neutral else 1


def compute_rula_score(
    features: Mapping[str, float],
    unavailable_features: Optional[List[str]] = None,
    legs_visible: bool = True,
    calibration: Optional[PostureCalibration] = None,
) -> Dict:
    """Compute a faithful RULA grand score (1-7) from pipeline features.

    Args:
        features: extracted ergonomic features (degrees / ratios).
        unavailable_features: feature names that could not be computed.
        legs_visible: whether the lower body is in frame. When False the legs
            score is neutral (RULA does not require legs) and the result is
            NOT flagged partial for a missing lower body.
        calibration: posture calibration (how much bend/strain counts before
            a joint starts scoring). Defaults to the ``RISK_CALIBRATION``
            profile (relaxed).

    Returns a dict with ``rula_informed_score``, ``is_partial_score`` and the
    intermediate posture scores (for reports / explainability).
    """
    cal = calibration or load_calibration()
    unavailable = set(unavailable_features or ())

    def _f(name: str, default: float) -> float:
        val = features.get(name, default)
        return default if val != val else float(val)

    neck = _f("neck_flexion", 0.0)
    trunk = _f("trunk_flexion", 0.0)
    head_tilt = _f("head_tilt_angle", 0.0)
    upper_arm = _f("upper_arm_angle_from_vertical", 0.0)
    shoulder_elev = max(
        _f("left_shoulder_elev", 0.0), _f("right_shoulder_elev", 0.0)
    )
    elbow = _f("elbow_flexion_angle", 180.0)
    wrist = _f("wrist_deviation_angle", 0.0)
    stance = _f("stance_stability", 1.0)

    upper_arm_s = _rula_upper_arm(upper_arm, shoulder_elev, cal)
    lower_arm_s = _rula_lower_arm(elbow, cal)
    wrist_s = _rula_wrist(wrist, cal)
    neck_s = _rula_neck(neck, head_tilt, cal)
    trunk_s = _rula_trunk(trunk, cal)
    legs_s = _rula_legs(stance, legs_visible, cal)

    # Score A = Table A + muscle-use + force. Muscle/force adjuncts are
    # intentionally skipped here (the context engine already adds duration,
    # exposure and fatigue) so posture risk stays method-pure.
    score_a = _RULA_TABLE_A[upper_arm_s][lower_arm_s][wrist_s - 1]

    # Score B = Table B(neck, trunk) + legs contribution.
    table_b = _RULA_TABLE_B[min(neck_s - 1, 5)][min(trunk_s - 1, 5)]
    score_b = table_b + (legs_s - 1)
    score_b = int(_clamp(score_b, 1, 9))

    grand = _RULA_TABLE_C[min(score_a - 1, 8)][min(score_b - 1, 8)]

    # Partial only when UPPER-body features are missing — a missing lower body
    # is exactly when RULA is used and must not flag partial.
    upper_features = [
        "neck_flexion", "trunk_flexion",
        "left_shoulder_elev", "right_shoulder_elev",
        "elbow_flexion_angle", "upper_arm_angle_from_vertical",
        "wrist_deviation_angle",
    ]
    missing_upper = [
        f for f in upper_features
        if f in unavailable or features.get(f, 0.0) != features.get(f, 0.0)
    ]

    return {
        "rula_informed_score": grand,
        "is_partial_score": bool(missing_upper),
        "rula_upper_arm": upper_arm_s,
        "rula_lower_arm": lower_arm_s,
        "rula_wrist": wrist_s,
        "rula_neck": neck_s,
        "rula_trunk": trunk_s,
        "rula_legs": legs_s,
        "rula_score_a": score_a,
        "rula_score_b": score_b,
        "rula_score_c": grand,
        "rula_score_d": grand,
        "calibration": cal.name,
    }


# ── REBA adapter: MediaPipe-33 -> named point map ──────────────────

def mediapipe_to_reba_points(
    keypoints: Sequence[Sequence[float]],
) -> Dict[str, List[float]]:
    """Convert MediaPipe-33 keypoint rows to the named map ``reba_from_keypoints`` expects.

    Each entry is ``[x, y, visibility]``; joints below ``_MIN_VIS`` are emitted
    with visibility 0 so REBA treats them as missing (neutral cell, never a
    worst-case index wrap).
    """
    kps = np.asarray(keypoints, dtype=float)
    if len(kps) < 29:
        return {}

    def _add(name: str, idx: int) -> None:
        if idx >= len(kps):
            return
        x, y = float(kps[idx][0]), float(kps[idx][1])
        vis = float(kps[idx][3]) if kps.shape[1] >= 4 else 1.0
        # Uninitialized landmarks sit at the origin (0,0) even when a stale
        # visibility column says otherwise — never feed those into the scorer.
        if x == 0.0 and y == 0.0:
            vis = 0.0
        points[name] = [x, y, vis if vis >= _MIN_VIS else 0.0]

    points: Dict[str, List[float]] = {}
    _add("nose", _MP["nose"])
    _add("left_eye", _MP["left_eye"])
    _add("right_eye", _MP["right_eye"])
    _add("left_ear", _MP["left_ear"])
    _add("right_ear", _MP["right_ear"])
    _add("left_shoulder", _MP["left_shoulder"])
    _add("right_shoulder", _MP["right_shoulder"])
    _add("left_elbow", _MP["left_elbow"])
    _add("right_elbow", _MP["right_elbow"])
    _add("left_wrist", _MP["left_wrist"])
    _add("right_wrist", _MP["right_wrist"])
    # No hand landmarks in pose-only MediaPipe — index fingertip is the
    # closest hand-direction proxy for the REBA wrist score.
    _add("left_hand", _MP["left_index"])
    _add("right_hand", _MP["right_index"])
    _add("left_hip", _MP["left_hip"])
    _add("right_hip", _MP["right_hip"])
    _add("left_knee", _MP["left_knee"])
    _add("right_knee", _MP["right_knee"])
    _add("left_ankle", _MP["left_ankle"])
    _add("right_ankle", _MP["right_ankle"])

    # Composite joints: neck = shoulder midpoint, center_hip = hip midpoint,
    # forehead = eye midpoint (MediaPipe has no forehead landmark).
    def _mid(a_name: str, b_name: str, out_name: str) -> None:
        a, b = points.get(a_name), points.get(b_name)
        if a is not None and b is not None and a[2] > 0 and b[2] > 0:
            points[out_name] = [
                (a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0, min(a[2], b[2])
            ]

    _mid("left_shoulder", "right_shoulder", "neck")
    _mid("left_hip", "right_hip", "center_hip")
    _mid("left_eye", "right_eye", "forehead")

    return points


def _has_usable_upper_body(points: Mapping[str, Sequence[float]]) -> bool:
    """Whether enough upper-body joints are present for RULA/REBA to mean anything."""
    needed = ("left_shoulder", "right_shoulder", "left_elbow", "right_elbow")
    present = sum(1 for name in needed if _pt_present(points, name))
    return present >= 3


def _pt_present(points: Mapping[str, Sequence[float]], name: str) -> bool:
    pt = points.get(name)
    return pt is not None and len(pt) >= 3 and pt[2] > 0


def assess_standard_risk(
    keypoints: Sequence[Sequence[float]],
    features: Mapping[str, float],
    unavailable_features: Optional[List[str]] = None,
    lower_body_confidence: float = 0.0,
    calibration: Optional[PostureCalibration] = None,
) -> Dict:
    """Assess posture risk using the standard method appropriate for body visibility.

    Args:
        keypoints: raw landmark rows ([[x, y, z, visibility], ...]).
        features: extracted ergonomic features.
        unavailable_features: feature names that could not be computed.
        lower_body_confidence: 0-100 mean visibility of hips/knees/ankles.
        calibration: posture calibration (how much bend/strain counts before
            a joint starts scoring). Defaults to the ``RISK_CALIBRATION``
            profile (relaxed).

    Returns a dict::

        {
            "method": "REBA" | "RULA" | "NONE",
            "score": int | None,          # REBA Score C or RULA grand
            "risk_level": "LOW"|"MEDIUM"|"HIGH" | None,
            "is_partial": bool,
            "reason": str,
            "details": {...},
        }

    ``NONE`` means no person / insufficient landmarks — callers fall back to
    the legacy rule risk (which is LOW when no person is detected).
    """
    cal = calibration or load_calibration()
    unavailable = set(unavailable_features or ())
    method: str
    reason: str = ""

    points = mediapipe_to_reba_points(keypoints)

    if not features or not _has_usable_upper_body(points):
        return {
            "method": "NONE",
            "score": None,
            "risk_level": None,
            "is_partial": True,
            "reason": "Insufficient landmarks for a standard assessment",
            "details": {},
        }

    if lower_body_confidence >= FULL_BODY_THRESHOLD:
        method = "REBA"
        if "neck" in points and "center_hip" in points and "left_ankle" in points:
            reba = reba_from_keypoints(points, calibration=cal)
            score = int(reba["reba_score"])
            band = reba_score_to_band(score)
            reason = f"REBA Score C={score} (action {reba['reba_action_level']})"
            details: Dict = {
                "reba_score": score,
                "reba_risk_level": int(reba["reba_risk_level"]),
                "reba_action_level": int(reba["reba_action_level"]),
                "score_a": int(reba["score_a"]),
                "score_b": int(reba["score_b"]),
                "neck_score": int(reba["neck_score"]),
                "trunk_score": int(reba["trunk_score"]),
                "legs_score": int(reba["legs_score"]),
                "upper_arm_score": int(reba["upper_arm_score"]),
                "lower_arm_score": int(reba["lower_arm_score"]),
                "wrist_score": int(reba["wrist_score"]),
                "calibration": cal.name,
            }
            return {
                "method": method,
                "score": score,
                "risk_level": band,
                "is_partial": False,
                "reason": reason,
                "details": details,
            }
        # Full body requested but keypoints too sparse for REBA tables -> fall
        # through to RULA (still a valid upper-limb assessment).
        reason = "Full body requested but REBA joints incomplete; used RULA"

    method = "RULA"
    rula = compute_rula_score(
        features, list(unavailable), legs_visible=False, calibration=cal
    )
    score = int(rula["rula_informed_score"])
    band = rula_score_to_band(score)
    if not reason:
        reason = f"RULA grand score={score} (upper body only — legs out of frame)"
    return {
        "method": method,
        "score": score,
        "risk_level": band,
        "is_partial": bool(rula["is_partial_score"]),
        "reason": reason,
        "details": {
            "rula_grand": score,
            "rula_upper_arm": int(rula["rula_upper_arm"]),
            "rula_lower_arm": int(rula["rula_lower_arm"]),
            "rula_wrist": int(rula["rula_wrist"]),
            "rula_neck": int(rula["rula_neck"]),
            "rula_trunk": int(rula["rula_trunk"]),
            "rula_legs": int(rula["rula_legs"]),
            "rula_score_a": int(rula["rula_score_a"]),
            "rula_score_b": int(rula["rula_score_b"]),
            "calibration": cal.name,
        },
    }
