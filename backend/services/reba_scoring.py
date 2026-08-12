"""Standard REBA scoring from 2D keypoints (calibration ground truth).

Implements the Rapid Entire Body Assessment methodology (Hignett &
McAtamney, 2000) from the 2D joint coordinates produced by pose
estimation. This is a deterministic, interpretable "expert method"
used to LABEL poses for the risk-calibration model and to produce the
calibration report comparing REBA-informed risk against the in-pipeline
rule-based ``risk_from_features`` scoring.

Note on fidelity: the standard REBA method is defined on 3D joint
angles. Here angles are computed from 2D projections (the same
approximation the pipeline's own feature extractor uses), so scores are
an approximation of a full 3D REBA assessment. Twisting/side-bending
adjuncts (+1) are omitted because 2D projection cannot resolve them
reliably. All table values follow the published methodology.

Input keypoint map (rebapose / COCO-style named joints)::

    forehead, nose, left_eye, right_eye, left_ear, right_ear, neck,
    left_shoulder, right_shoulder, left_elbow, right_elbow,
    left_wrist, right_wrist, left_hip, center_hip, right_hip,
    left_knee, right_knee, left_ankle, right_ankle, left_hand, right_hand

Each point is ``[x, y, visibility]`` where visibility follows the COCO
convention (0 = not labeled, >0 = present).
"""

from __future__ import annotations

from typing import Dict, List, Mapping, Sequence

import numpy as np

from backend.services.calibration import PostureCalibration, STANDARD


# ── REBA Table A (neck x trunk) — standard 4x6 matrix ──────────────
# Rows: neck score 1..4; columns: trunk score 1..6 (upright, 0-20,
# 20-60, >60, +twist, +side-bend).
TABLE_A: List[List[int]] = [
    [1, 2, 3, 4, 6, 7],
    [2, 3, 4, 5, 6, 7],
    [3, 4, 5, 6, 7, 8],
    [5, 6, 7, 8, 9, 9],
]

# ── REBA Table B (upper arm x lower arm) — standard 6x2 matrix ─────
# Rows: upper arm score 1..6; columns: lower arm score 1..2.
TABLE_B: List[List[int]] = [
    [1, 2],
    [1, 2],
    [3, 4],
    [4, 5],
    [6, 7],
    [7, 8],
]

# ── REBA Table C (Score A x Score B) — standard 12x12 matrix ───────
TABLE_C: List[List[int]] = [
    [1, 1, 1, 2, 3, 3, 4, 5, 6, 7, 7, 7],
    [1, 2, 2, 3, 4, 4, 5, 6, 7, 7, 8, 8],
    [2, 3, 3, 3, 4, 5, 6, 7, 7, 8, 8, 8],
    [3, 4, 4, 4, 5, 6, 7, 8, 8, 9, 9, 9],
    [4, 4, 4, 5, 6, 7, 8, 8, 9, 9, 9, 9],
    [6, 6, 6, 7, 8, 8, 9, 9, 10, 10, 10, 10],
    [7, 7, 7, 8, 9, 9, 9, 10, 10, 11, 11, 11],
    [8, 8, 8, 9, 10, 10, 10, 10, 10, 11, 11, 11],
    [9, 9, 9, 10, 10, 10, 11, 11, 11, 12, 12, 12],
    [10, 10, 10, 11, 11, 11, 11, 12, 12, 12, 12, 12],
    [11, 11, 11, 11, 12, 12, 12, 12, 12, 12, 12, 12],
    [12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12],
]

# REBA Score C -> risk level (1..5) and action level (0..4).
_RISK_BANDS = [(11, 4), (8, 3), (4, 2), (2, 1), (1, 0)]  # (min_score, action)


def _point(points: Mapping[str, Sequence[float]], name: str) -> np.ndarray | None:
    pt = points.get(name)
    if pt is None or len(pt) < 3 or pt[2] <= 0:
        return None
    return np.array(pt[:2], dtype=float)


def _angle(a: np.ndarray | None, b: np.ndarray | None, c: np.ndarray | None) -> float:
    """Angle at b between a-b and c-b (degrees)."""
    if a is None or b is None or c is None:
        return float("nan")
    v1 = a - b
    v2 = c - b
    denom = np.linalg.norm(v1) * np.linalg.norm(v2)
    if denom < 1e-9:
        return float("nan")
    return float(np.degrees(np.arccos(np.clip(np.dot(v1, v2) / denom, -1.0, 1.0))))


def _signed_deviation(angle: float, straight: float = 180.0) -> float:
    """Signed deviation from a straight reference (negative = forward bend)."""
    if angle != angle:
        return float("nan")
    return angle - straight


def _neck_score(forehead: np.ndarray | None, neck: np.ndarray | None,
                hip: np.ndarray | None, cal: PostureCalibration) -> int:
    """REBA neck posture score (neutral flexion, extension)."""
    if neck is None or hip is None:
        return 0
    if forehead is None:
        return 1  # unknown head -> assume neutral
    angle = _angle(forehead, neck, hip)  # 180 = head straight up
    dev = _signed_deviation(angle)
    if dev != dev:
        return 1
    if dev < -cal.neck_side_bend_max:  # head tilted back (extension)
        return 3
    if dev > cal.neck_high_max:
        return 2
    return 1


def _trunk_score(neck: np.ndarray | None, hip: np.ndarray | None,
                 cal: PostureCalibration) -> int:
    """REBA trunk posture score (neutral / medium / high / severe bands)."""
    if neck is None or hip is None:
        return 0
    # Angle of the neck->hip line from vertical (0 = upright).
    vertical = np.array([hip[0], hip[1] - 1.0])
    angle = _angle(vertical, hip, neck)
    if angle != angle:
        return 1
    if angle <= cal.trunk_neutral_max:
        return 1
    if angle <= cal.trunk_medium_max:
        return 2
    if angle <= cal.trunk_high_max:
        return 3
    return 4


def _legs_score(left_knee: np.ndarray | None, right_knee: np.ndarray | None,
                left_ankle: np.ndarray | None, right_ankle: np.ndarray | None,
                left_hip: np.ndarray | None, right_hip: np.ndarray | None,
                cal: PostureCalibration) -> int:
    """REBA legs score (bilateral=1, knee flexion > medium = +1, > high = +2)."""
    if left_hip is None or right_hip is None or left_ankle is None or right_ankle is None:
        return 0
    base = 1  # bilateral weight bearing / walking / sitting
    flexions = []
    if left_knee is not None and left_ankle is not None:
        a = _angle(left_hip, left_knee, left_ankle)
        if a == a:
            flexions.append(180.0 - a)
    if right_knee is not None and right_ankle is not None:
        a = _angle(right_hip, right_knee, right_ankle)
        if a == a:
            flexions.append(180.0 - a)
    if not flexions:
        return base
    max_flex = max(flexions)
    if max_flex > cal.knee_high_max:
        return base + 2
    if max_flex > cal.knee_medium_max:
        return base + 1
    return base


def _upper_arm_score(shoulder: np.ndarray | None, elbow: np.ndarray | None,
                     neck: np.ndarray | None, hip: np.ndarray | None,
                     cal: PostureCalibration,
                     shoulder_elevated: bool = False,
                     abducted: bool = False) -> int:
    """REBA upper-arm score from angle-from-vertical (neutral ... severe)."""
    if shoulder is None or elbow is None:
        return 0
    vertical_down = np.array([shoulder[0], shoulder[1] + 1.0])
    angle = _angle(vertical_down, shoulder, elbow)  # 0 = arm hanging
    if angle != angle:
        return 1
    if angle <= cal.upper_arm_neutral_max:
        score = 1
    elif angle <= cal.upper_arm_medium_max:
        score = 2
    elif angle <= cal.upper_arm_high_max:
        score = 3
    else:
        score = 4
    if shoulder_elevated:
        score += 1
    if abducted:
        score += 1
    return min(score, 6)


def _lower_arm_score(shoulder: np.ndarray | None, elbow: np.ndarray | None,
                     wrist: np.ndarray | None, cal: PostureCalibration) -> int:
    """REBA lower-arm score (neutral elbow flexion = 1, else 2)."""
    if elbow is None or wrist is None:
        return 1
    angle = _angle(shoulder, elbow, wrist)
    if angle != angle:
        return 1
    return 1 if cal.elbow_neutral_min <= angle <= cal.elbow_neutral_max else 2


def _wrist_score(elbow: np.ndarray | None, wrist: np.ndarray | None,
                 hand: np.ndarray | None, cal: PostureCalibration) -> int:
    """REBA wrist score (neutral / medium / deviated bands)."""
    if wrist is None or hand is None:
        return 1
    angle = _angle(elbow, wrist, hand)
    dev = _signed_deviation(angle)
    if dev != dev:
        return 1
    adev = abs(dev)
    if adev <= cal.wrist_neutral_max:
        return 1
    if adev <= cal.wrist_medium_max:
        return 2
    return 3


def reba_risk_from_level(score_c: int) -> tuple[int, int]:
    """Map REBA Score C to (risk_level 1-5, action_level 0-4)."""
    for min_score, action in _RISK_BANDS:
        if score_c >= min_score:
            return action + 1, action
    return 1, 0


def reba_from_keypoints(points: Mapping[str, Sequence[float]],
                         calibration: PostureCalibration | None = None) -> Dict[str, float | int]:
    """Compute the full REBA score from a named-keypoint dict.

    Args:
        points: mapping of joint name -> [x, y, visibility] (COCO
            visibility convention; >0 means present).
        calibration: posture calibration (how much bend/strain counts
            before a joint starts scoring). Defaults to STANDARD — the
            published REBA breakpoints — so dataset labeling and any
            direct caller keep the reference methodology. The live risk
            gate (``assess_standard_risk``) passes its own profile.

    Returns a dict with keys: reba_score (Score C, 1-15), reba_risk_level
    (1-5), reba_action_level (0-4), plus the partial scores (A, B), and
    the per-segment posture scores used to build the tables.
    """
    cal = calibration if calibration is not None else STANDARD
    forehead = _point(points, "forehead")
    if forehead is None:
        forehead = _point(points, "nose")
    neck = _point(points, "neck")
    center_hip = _point(points, "center_hip")
    mid_hip = center_hip
    if mid_hip is None:
        lh, rh = _point(points, "left_hip"), _point(points, "right_hip")
        if lh is not None and rh is not None:
            mid_hip = (lh + rh) / 2.0

    lsh, rsh = _point(points, "left_shoulder"), _point(points, "right_shoulder")
    lel, rel = _point(points, "left_elbow"), _point(points, "right_elbow")
    lwr, rwr = _point(points, "left_wrist"), _point(points, "right_wrist")
    lha, rha = _point(points, "left_hand"), _point(points, "right_hand")
    lhip, rhip = _point(points, "left_hip"), _point(points, "right_hip")
    lkn, rkn = _point(points, "left_knee"), _point(points, "right_knee")
    lan, ran = _point(points, "left_ankle"), _point(points, "right_ankle")

    # ── Group A: neck, trunk, legs ─────────────────────────────────
    neck_s = _neck_score(forehead, neck, mid_hip, cal)
    trunk_s = _trunk_score(neck, mid_hip, cal)
    legs_s = _legs_score(lkn, rkn, lan, ran, lhip, rhip, cal)
    # Clamp with max(0, ...): posture scores of 0 (missing joints) must
    # stay at the neutral table cell, NOT wrap to the worst-case row/col
    # via a negative index.
    score_a = TABLE_A[max(0, min(neck_s - 1, 3))][max(0, min(trunk_s - 1, 5))] + legs_s

    # ── Group B: upper arm, lower arm, wrist ───────────────────────
    # Shoulder raised proxy: wrist above the shoulder line.
    left_elevated = lwr is not None and lsh is not None and lwr[1] < lsh[1]
    right_elevated = rwr is not None and rsh is not None and rwr[1] < rsh[1]
    # Abduction proxy: elbow x outside the hip span.
    left_abducted = lel is not None and lhip is not None and lel[0] < lhip[0] - 5
    right_abducted = rel is not None and rhip is not None and rel[0] > rhip[0] + 5

    upper_l = _upper_arm_score(lsh, lel, neck, mid_hip, cal, left_elevated, left_abducted)
    upper_r = _upper_arm_score(rsh, rel, neck, mid_hip, cal, right_elevated, right_abducted)
    upper_s = max(upper_l, upper_r)

    lower_l = _lower_arm_score(lsh, lel, lwr, cal)
    lower_r = _lower_arm_score(rsh, rel, rwr, cal)
    lower_s = max(lower_l, lower_r)

    wrist_l = _wrist_score(lel, lwr, lha, cal)
    wrist_r = _wrist_score(rel, rwr, rha, cal)
    wrist_s = max(wrist_l, wrist_r)

    score_b = TABLE_B[max(0, min(upper_s - 1, 5))][max(0, min(lower_s - 1, 1))] + wrist_s

    # ── Table C + risk level ───────────────────────────────────────
    a = min(max(score_a, 1), 12)
    b = min(max(score_b, 1), 12)
    score_c = TABLE_C[a - 1][b - 1]
    risk_level, action_level = reba_risk_from_level(score_c)

    return {
        "reba_score": score_c,
        "reba_risk_level": risk_level,
        "reba_action_level": action_level,
        "score_a": score_a,
        "score_b": score_b,
        "neck_score": neck_s,
        "trunk_score": trunk_s,
        "legs_score": legs_s,
        "upper_arm_score": upper_s,
        "lower_arm_score": lower_s,
        "wrist_score": wrist_s,
    }


def reba_risk_band(risk_level: int) -> str:
    """Map REBA risk level (1-5) to a LOW/MEDIUM/HIGH band for comparison."""
    if risk_level <= 1:
        return "LOW"
    if risk_level <= 3:
        return "MEDIUM"
    return "HIGH"
