"""Pose-quality / framing intelligence (Tier 3).

Auto-detects *how well* the camera frames the worker from the same 33
MediaPipe landmarks the rest of the pipeline already uses, and emits:

- **framing_state** — ``full_body`` / ``upper_body`` / ``poor`` (drives the
  RULA-vs-REBA method choice and the "reposition camera" guidance).
- **profile_view** — the worker is turned sideways to the camera, making
  depth-ambiguous joints (trunk flexion, shoulder elevation) unreliable.
- **cropped_edges** / **occluded_joints** — which parts of the body are out
  of frame or below visibility threshold.
- **guidance** — plain-language camera repositioning advice.
- **quality_score** — 0-100 aggregate framing quality (drives confidence).
- **joint_uncertainty** — per-feature angle uncertainty (sigma, degrees),
  computed from landmark visibility × camera angle, so the risk engine can
  score P(rule violated) instead of hard cutoffs — killing boundary-flip
  sensitivity at the root.

Keypoints are ``[x_px, y_px, z, visibility]`` rows (MediaPipe 33 order), the
same space ``extract_features_from_keypoints`` consumes. ``frame_w/h`` are the
raw processing-frame dimensions used to convert the normalized landmarks.
"""

from __future__ import annotations

import math
from typing import Dict, List, Mapping, Sequence

import numpy as np

# ── Landmark indices (MediaPipe 33) ────────────────────────────────
_NOSE = 0
_L_EAR = 7
_R_EAR = 8
_L_SHOULDER = 11
_R_SHOULDER = 12
_L_ELBOW = 13
_R_ELBOW = 14
_L_WRIST = 15
_R_WRIST = 16
_L_HIP = 23
_R_HIP = 24
_L_KNEE = 25
_R_KNEE = 26
_L_ANKLE = 27
_R_ANKLE = 28
_L_HEEL = 29
_R_HEEL = 30

# Visibility below this = the joint is treated as occluded / out of frame.
_OCCLUDED_VIS = 0.35
# Fraction of the frame margin beyond which a landmark counts as cropped.
_CROP_MARGIN = 0.04
# Minimum fraction of the full frame height the worker must span.
_MIN_BODY_SPAN = 0.45

# Feature -> (landmark indices involved, base sigma at full visibility).
# Base sigmas are the 2D-pose angle noise floor from the CV literature
# (~4-7 deg for good visibility); visibility and camera angle scale them.
_FEATURE_JOINTS: Mapping[str, tuple[tuple[int, ...], float]] = {
    "neck_flexion": ((_NOSE, _L_EAR, _R_EAR, _L_SHOULDER, _R_SHOULDER), 5.0),
    "trunk_flexion": ((_L_SHOULDER, _R_SHOULDER, _L_HIP, _R_HIP), 5.0),
    "left_shoulder_elev": ((_L_SHOULDER, _L_ELBOW, _L_WRIST), 5.0),
    "right_shoulder_elev": ((_R_SHOULDER, _R_ELBOW, _R_WRIST), 5.0),
    "shoulder_symmetry": ((_L_SHOULDER, _R_SHOULDER, _L_ELBOW, _R_ELBOW), 4.0),
    "knee_angle": ((_L_HIP, _R_HIP, _L_KNEE, _R_KNEE, _L_ANKLE, _R_ANKLE), 5.0),
    "forward_head_posture": ((_NOSE, _L_EAR, _R_EAR, _L_SHOULDER, _R_SHOULDER), 6.0),
    "head_tilt_angle": ((_NOSE, _L_EAR, _R_EAR), 6.0),
    "wrist_deviation_angle": ((_L_ELBOW, _R_ELBOW, _L_WRIST, _R_WRIST), 6.0),
    "stance_stability": ((_L_HIP, _R_HIP, _L_ANKLE, _R_ANKLE, _L_HEEL, _R_HEEL), 0.08),
    "weight_shift_offset": ((_L_HIP, _R_HIP, _L_ANKLE, _R_ANKLE), 3.0),
    "alignment_deviation": ((_L_SHOULDER, _R_SHOULDER, _L_HIP, _R_HIP), 4.0),
}

# Depth-ambiguous features: their 2D projected angle is unreliable in profile
# view (the joint angle is foreshortened), so profile view widens their sigma.
_PROFILE_DEPTH_SENSITIVE = {
    "trunk_flexion", "left_shoulder_elev", "right_shoulder_elev",
    "shoulder_symmetry", "knee_angle", "alignment_deviation",
}


def _vis(kps: Sequence[Sequence[float]], idx: int) -> float:
    if idx >= len(kps):
        return 0.0
    row = kps[idx]
    return float(row[3]) if len(row) > 3 else 1.0


def _mean_vis(kps: Sequence[Sequence[float]], indices: Sequence[int]) -> float:
    vals = [_vis(kps, i) for i in indices]
    return float(np.mean(vals)) if vals else 0.0


def assess_framing(
    keypoints: Sequence[Sequence[float]],
    frame_w: int,
    frame_h: int,
) -> dict:
    """Assess camera framing quality and per-joint angle uncertainty.

    Args:
        keypoints: 33 (or 17) rows of ``[x_px, y_px, z, visibility]``.
        frame_w: processing-frame width (pixels).
        frame_h: processing-frame height (pixels).

    Returns:
        Dict with ``framing_state``, ``profile_view``, ``cropped_edges``,
        ``occluded_joints``, ``guidance``, ``quality_score``,
        ``joint_uncertainty``, and ``detail``.
    """
    kps = np.asarray(keypoints, dtype=float)
    if kps.size == 0:
        return {
            "framing_state": "poor",
            "profile_view": False,
            "cropped_edges": [],
            "occluded_joints": [],
            "guidance": ["No person detected — adjust camera framing."],
            "quality_score": 0.0,
            "joint_uncertainty": {},
            "detail": "No landmarks",
        }

    w = max(1.0, float(frame_w))
    h = max(1.0, float(frame_h))

    # ── Visible body span (fraction of frame height covered) ────────
    ys = [kps[i][1] for i in range(min(len(kps), 33)) if _vis(kps, i) >= _OCCLUDED_VIS]
    span_frac = (max(ys) - min(ys)) / h if ys else 0.0

    # ── Profile view: shoulder-depth asymmetry + ear occlusion ──────
    # In a front-facing pose the left/right shoulders are roughly equidistant
    # from the camera (small |zL - zR| relative to their x-separation, both
    # in normalized units — MediaPipe's z is ~ the same scale as x). Turned
    # sideways, the far shoulder drops behind AND the projected shoulder
    # width foreshortens, so the depth/x ratio grows large.
    l_sh, r_sh = (_L_SHOULDER, _R_SHOULDER)
    profile_view = False
    if l_sh < len(kps) and r_sh < len(kps):
        xL, zL, vL = kps[l_sh][0], kps[l_sh][2], _vis(kps, l_sh)
        xR, zR, vR = kps[r_sh][0], kps[r_sh][2], _vis(kps, r_sh)
        if vL >= _OCCLUDED_VIS and vR >= _OCCLUDED_VIS:
            dx_norm = abs(xL - xR) / w  # normalized shoulder width
            dz = abs(zL - zR)           # shoulder depth difference
            # Front view: dz/dx_norm is small (shoulders near-symmetric in
            # depth, width ~0.2). Profile: dz ~ full torso depth while the
            # projected width collapses -> ratio climbs well past 1.
            if dx_norm > 1e-3 and dz / dx_norm > 1.2:
                profile_view = True
    # OR: in profile, one ear is typically occluded -> strong visibility
    # asymmetry between left/right ear.
    if not profile_view and _L_EAR < len(kps) and _R_EAR < len(kps):
        v_le, v_re = _vis(kps, _L_EAR), _vis(kps, _R_EAR)
        if (v_le >= _OCCLUDED_VIS) != (v_re >= _OCCLUDED_VIS):
            profile_view = True

    # ── Cropped edges ───────────────────────────────────────────────
    cropped: List[str] = []
    for i in range(min(len(kps), 33)):
        if _vis(kps, i) < _OCCLUDED_VIS:
            continue
        x, y = kps[i][0] / w, kps[i][1] / h
        if x < _CROP_MARGIN:
            cropped.append("left")
        elif x > 1 - _CROP_MARGIN:
            cropped.append("right")
        if y < _CROP_MARGIN:
            cropped.append("top")
        elif y > 1 - _CROP_MARGIN:
            cropped.append("bottom")
    cropped = list(dict.fromkeys(cropped))  # dedupe, keep order

    # ── Occluded joints (below visibility threshold) ────────────────
    occluded: List[str] = []
    lower_visible = _mean_vis(kps, (_L_HIP, _R_HIP, _L_KNEE, _R_KNEE, _L_ANKLE, _R_ANKLE))
    if lower_visible < _OCCLUDED_VIS:
        occluded.append("legs")
    head_vis = _mean_vis(kps, (_NOSE, _L_EAR, _R_EAR))
    if head_vis < _OCCLUDED_VIS:
        occluded.append("head")
    hands_vis = _mean_vis(kps, (_L_WRIST, _R_WRIST))
    if hands_vis < _OCCLUDED_VIS:
        occluded.append("hands")

    # ── Framing state ───────────────────────────────────────────────
    if span_frac < 0.25 or not ys:
        framing_state = "poor"
    elif "bottom" in cropped or "legs" in occluded or span_frac < _MIN_BODY_SPAN:
        framing_state = "upper_body"
    else:
        framing_state = "full_body"

    # ── Guidance (plain language) ───────────────────────────────────
    guidance: List[str] = []
    if framing_state == "poor":
        guidance.append("Reposition camera: full worker (head to feet) should fill most of the frame.")
    elif framing_state == "upper_body":
        guidance.append("Lower body out of frame — reposition camera to head-to-mid-thigh for full-body REBA.")
    if profile_view:
        guidance.append("Worker is turned sideways to camera — depth-based angles (trunk/shoulder) are less reliable.")
    if "left" in cropped and "right" in cropped:
        guidance.append("Worker is too wide for the frame — step the camera back.")
    elif "left" in cropped:
        guidance.append("Worker clipped on the left — shift camera right.")
    elif "right" in cropped:
        guidance.append("Worker clipped on the right — shift camera left.")
    if "top" in cropped:
        guidance.append("Head is clipped at the top — tilt the camera down or step back.")
    if "hands" in occluded:
        guidance.append("Hands are not visible — wrists/fingers may be out of frame or occluded.")
    if not guidance:
        guidance.append("Good framing — full body in view.")

    # ── Quality score (0-100) ───────────────────────────────────────
    score = 100.0
    score -= {"full_body": 0, "upper_body": 15, "poor": 45}[framing_state]
    if profile_view:
        score -= 10
    score -= 8 * len(cropped)
    score -= 6 * len(occluded)
    score = max(0.0, min(100.0, score))

    # ── Per-joint uncertainty (sigma, degrees) ──────────────────────
    # sigma = base * (1 + k1*(1 - vis)) * (k2 if depth-ambiguous in profile).
    uncertainty: Dict[str, float] = {}
    for feature, (joints, base) in _FEATURE_JOINTS.items():
        vis = _mean_vis(kps, joints)
        vis = max(0.1, min(1.0, vis))
        sigma = base * (1.0 + 1.5 * (1.0 - vis))
        if profile_view and feature in _PROFILE_DEPTH_SENSITIVE:
            sigma *= 1.8
        if feature in ("stance_stability",):
            # ratio feature — sigma stays in ratio units
            sigma = base * (1.0 + 1.5 * (1.0 - vis))
            if profile_view:
                sigma *= 1.5
        uncertainty[feature] = round(sigma, 3)

    detail = (
        f"span={span_frac:.0%} profile={profile_view} "
        f"cropped={','.join(cropped) or 'none'} occluded={','.join(occluded) or 'none'}"
    )

    return {
        "framing_state": framing_state,
        "profile_view": profile_view,
        "cropped_edges": cropped,
        "occluded_joints": occluded,
        "guidance": guidance,
        "quality_score": round(score, 1),
        "joint_uncertainty": uncertainty,
        "detail": detail,
    }


def profile_view_from_keypoints(keypoints: Sequence[Sequence[float]], frame_w: int = 640) -> bool:
    """Cheap profile-view check (used by the demo overlay)."""
    return bool(assess_framing(keypoints, frame_w, 480).get("profile_view"))
