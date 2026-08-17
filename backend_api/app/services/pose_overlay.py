"""Shared pose skeleton overlay rendering.

The live MJPEG feed (``app.api.video_feed``) and the uploaded-video analysis
pipeline (``app.api.video_analysis``) both render the same MediaPipe skeleton
overlay, colored by per-segment risk level, with confidence-dimming and
per-joint angle labels. Keeping the drawing code here means the burned-in
overlay on a downloaded video is pixel-identical to what the operator sees
live.

``keypoints`` are normalized 0-1 coordinates (``[x, y, z, visibility]``) as
produced by ``PoseEngine``.
"""

from __future__ import annotations

import math

import cv2

from backend.services.calibration import load_calibration
from backend.services.features import risk_breakdown

# Risk-level BGR colors matching Video Review (green-400, amber-400, red-400)
RISK_COLORS = {
    "LOW": (128, 222, 74),     # rgb(74, 222, 128) → BGR
    "MEDIUM": (36, 191, 251),  # rgb(251, 191, 36) → BGR
    "HIGH": (113, 113, 248),   # rgb(248, 113, 113) → BGR
}

_RISK_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}

# MediaPipe landmark indices grouped by body region. Each region is colored
# independently so a raised arm turns red while the rest of the skeleton stays
# green — the operator sees exactly which limb is risky.
REGION_JOINTS = {
    "head": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    "torso": [11, 12, 23, 24],
    "left_arm": [11, 13, 15, 17, 19, 21],
    "right_arm": [12, 14, 16, 18, 20, 22],
    "left_leg": [23, 25, 27, 29, 31],
    "right_leg": [24, 26, 28, 30, 32],
}

# Feature names that determine a region's risk band (must exist in
# risk_breakdown's threshold table; motion/reference signals are excluded).
REGION_FEATURES = {
    "head": ["neck_flexion", "forward_head_posture", "head_tilt_angle"],
    "torso": ["trunk_flexion", "shoulder_symmetry", "alignment_deviation"],
    "left_arm": ["left_shoulder_elev", "wrist_deviation_angle"],
    "right_arm": ["right_shoulder_elev", "wrist_deviation_angle"],
    "left_leg": ["knee_angle", "stance_stability", "weight_shift_offset"],
    "right_leg": ["knee_angle", "stance_stability", "weight_shift_offset"],
}

# Which region each connection belongs to (used to color segments).
_CONNECTION_REGION = {
    (11, 12): "torso",
    (11, 13): "left_arm", (13, 15): "left_arm",
    (12, 14): "right_arm", (14, 16): "right_arm",
    (11, 23): "torso", (12, 24): "torso", (23, 24): "torso",
    (23, 25): "left_leg", (25, 27): "left_leg",
    (24, 26): "right_leg", (26, 28): "right_leg",
    (27, 29): "left_leg", (29, 31): "left_leg",
    (28, 30): "right_leg", (30, 32): "right_leg",
    (15, 17): "left_arm", (15, 19): "left_arm", (15, 21): "left_arm",
    (16, 18): "right_arm", (16, 20): "right_arm", (16, 22): "right_arm",
}
# Face connections default to the head region.


def _region_risk_level(region: str, breakdown: dict, overall: str) -> str:
    """Worst risk band among a region's scored features; overall when none."""
    levels = []
    for feat in REGION_FEATURES.get(region, []):
        br = breakdown.get(feat)
        if br is not None and br.level in _RISK_ORDER:
            levels.append(br.level)
    if not levels:
        return overall
    return max(levels, key=lambda level: _RISK_ORDER[level])


def _sub_band(score) -> str | None:
    """Map a RULA/REBA posture sub-score (1 = neutral) to a risk band.

    Score 1 -> LOW, 2 -> MEDIUM, 3+ -> HIGH. Scores <= 0 mean "missing / no
    usable joints" (the scorers emit 0 for unscoreable cells) -> None, so the
    caller falls back to the overall level instead of rendering false green.
    """
    try:
        s = int(score)
    except (TypeError, ValueError):
        return None
    if s <= 0:
        return None
    if s == 1:
        return "LOW"
    if s == 2:
        return "MEDIUM"
    return "HIGH"


def _arm_band(features: dict, side: str, cal, wrist_band: str | None) -> str:
    """Per-side arm band using the same calibration bands the RULA/REBA
    scorer applies to the upper arm.

    ``{side}_shoulder_elev`` is the elbow-based angle of the upper arm from
    vertical (the RULA upper-arm measure), so a raised arm colors red on that
    side only while the other stays green. Merged with the wrist sub-score
    band (worst wins).
    """
    elev = features.get(f"{side}_shoulder_elev")
    if elev is None or elev != elev:  # NaN -> fall back to wrist/overall
        return wrist_band if wrist_band is not None else None
    if elev <= cal.upper_arm_neutral_max:
        band = "LOW"
    elif elev <= cal.upper_arm_medium_max:
        band = "MEDIUM"
    else:
        band = "HIGH"
    if wrist_band is not None and _RISK_ORDER[wrist_band] > _RISK_ORDER[band]:
        return wrist_band
    return band


def compute_region_levels(features, overall: str, standard_assessment=None) -> dict[str, str]:
    """Worst risk band per body region.

    When a standard RULA/REBA assessment is available, region colors derive
    from the method's per-joint posture sub-scores — the same calibration and
    semantics that produced the overall level, so the skeleton and the badge
    can never disagree. Arms are scored per side (a raised left arm turns red
    while the right stays green). Regions with no usable sub-score fall back
    to the overall level so nothing renders as a false safe/green.

    Without a standard assessment the legacy per-feature breakdown is used
    (same behavior as before). Exposed as a pure function so the video-
    analysis pipeline can attach the same region levels to every sampled
    frame — the frontend then colors its replay skeleton exactly like the
    live feed.
    """
    features = features or {}
    std = standard_assessment or {}
    method = std.get("method")
    details = std.get("details") or {}
    cal = load_calibration()

    region_levels: dict[str, str] = {}
    for region in REGION_JOINTS:
        band: str | None = None
        if method == "RULA":
            if region == "head":
                band = _sub_band(details.get("rula_neck"))
            elif region == "torso":
                band = _sub_band(details.get("rula_trunk"))
            elif region in ("left_arm", "right_arm"):
                side = "left" if region == "left_arm" else "right"
                band = _arm_band(features, side, cal, _sub_band(details.get("rula_wrist")))
            elif region in ("left_leg", "right_leg"):
                band = _sub_band(details.get("rula_legs"))
        elif method == "REBA":
            if region == "head":
                band = _sub_band(details.get("neck_score"))
            elif region == "torso":
                band = _sub_band(details.get("trunk_score"))
            elif region in ("left_arm", "right_arm"):
                side = "left" if region == "left_arm" else "right"
                band = _arm_band(features, side, cal, _sub_band(details.get("wrist_score")))
            elif region in ("left_leg", "right_leg"):
                band = _sub_band(details.get("legs_score"))
        region_levels[region] = band if band is not None else overall
    return region_levels


def _region_for_connection(a: int, b: int) -> str:
    region = _CONNECTION_REGION.get((min(a, b), max(a, b)))
    if region is not None:
        return region
    return "head"  # face connections


def _compute_segment_colors(features, overall: str, standard_assessment=None, region_levels=None):
    """Return (connection_color, joint_color) maps keyed by indices.

    Colors each skeleton connection and joint by the risk band of the body
    region it belongs to (see ``compute_region_levels``).
    """
    if region_levels is None:
        region_level = compute_region_levels(features, overall, standard_assessment)
    else:
        region_level = region_levels

    conn_color: dict[tuple[int, int], tuple[int, int, int]] = {}
    joint_regions: dict[int, list[str]] = {}
    for a, b in POSE_CONNECTIONS:
        region = _region_for_connection(a, b)
        # A missing region key (partial/legacy region_risks dict) falls back
        # to the overall color instead of raising KeyError — a single missing
        # region must never blank the whole skeleton silently.
        band = region_level.get(region, overall)
        conn_color[(a, b)] = RISK_COLORS.get(band, RISK_COLORS[overall])
        joint_regions.setdefault(a, []).append(region)
        joint_regions.setdefault(b, []).append(region)

    joint_color: dict[int, tuple[int, int, int]] = {}
    for idx, regions in joint_regions.items():
        worst = max(regions, key=lambda r: _RISK_ORDER.get(region_level.get(r, overall), 0))
        joint_color[idx] = RISK_COLORS.get(region_level.get(worst, overall), RISK_COLORS[overall])
    return conn_color, joint_color

# MediaPipe Pose connections for skeleton drawing
POSE_CONNECTIONS = [
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),  # Arms
    (11, 23), (12, 24), (23, 24),  # Torso
    (23, 25), (25, 27), (24, 26), (26, 28),  # Legs
    (27, 29), (29, 31), (28, 30), (30, 32),  # Lower legs
    (15, 17), (15, 19), (15, 21), (16, 18), (16, 20), (16, 22),  # Hands
    (0, 1), (1, 2), (2, 3), (3, 7),  # Face
    (0, 4), (4, 5), (5, 6), (6, 8),  # Face
    (9, 10),  # Mouth
]

# Label positions: (feature_name, short_label, landmark_index, (dx, dy))
LABEL_CONFIG = [
    ("neck_flexion", "N", 0, (-20, -30)),
    ("trunk_flexion", "T", 23, (15, -10)),
    ("left_shoulder_elev", "LS", 11, (-30, -20)),
    ("right_shoulder_elev", "RS", 12, (10, -20)),
    ("shoulder_symmetry", "Sym", 11, (-55, -35)),
    ("knee_angle", "K", 25, (15, 5)),
]


def draw_skeleton(frame, keypoints, risk_level, features=None, feature_scores=None,
                  standard_assessment=None, region_levels=None):
    """Draw the pose skeleton overlay on a frame, colored per body region.

    Each segment is colored by the risk band of its own body region
    (green LOW / amber MEDIUM / red HIGH), so a raised arm turns red while
    the rest of the skeleton stays green. When a standard RULA/REBA
    assessment is supplied, region colors derive from its per-joint sub-
    scores (same calibration as the level); ``region_levels`` (precomputed
    per-frame levels) can be passed directly to avoid recomputing. Regions
    with no scored feature fall back to the overall risk level. Confidence-
    based dimming and angle labels are preserved; the same scheme as Video
    Review.
    """
    if not keypoints:
        return frame

    features = features or {}

    glow = frame.copy()
    overlay = frame.copy()
    h, w = frame.shape[:2]

    overall_color = RISK_COLORS.get(risk_level, (128, 128, 128))
    conn_color, joint_color = _compute_segment_colors(
        features, risk_level, standard_assessment, region_levels
    )

    def _dimmed(c, visibility):
        if visibility >= 0.75:
            return c
        if visibility >= 0.35:
            factor = 0.5 + 0.5 * (visibility - 0.35) / 0.4
        else:
            factor = max(0.15, visibility / 0.35 * 0.35)
        return tuple(int(v * factor) for v in c)

    # Minimum visibility threshold to draw a keypoint or connection.
    # Below this, the landmark is too unreliable to show — it causes the
    # "black lines to corner" artifact when the pose estimate snaps a
    # partially-occluded joint to an out-of-bounds coordinate.
    _MIN_VIS = 0.35
    # Face landmarks that MediaPipe can snap to frame edges when occluded.
    # These cause diagonal lines across the feed when connected.
    _FACE_INDICES = set(range(0, 11))

    def _kp_valid(idx: int) -> bool:
        """Check if keypoint at *idx* exists, is in-frame, and visible."""
        if idx >= len(keypoints):
            return False
        kp = keypoints[idx]
        if len(kp) < 2:
            return False
        vis = kp[3] if len(kp) > 3 else 1.0
        if vis < _MIN_VIS:
            return False
        x, y = kp[0], kp[1]
        # Tight bounds for body landmarks (5% margin for edge jitter)
        if x < -0.05 or x > 1.05 or y < -0.05 or y > 1.05:
            return False
        # Face landmarks near frame edges are almost certainly MediaPipe
        # snapping an occluded/missing face landmark to (0,0) or (1,0).
        # Real face landmarks inside a visible face sit well within the
        # inner 80% of the frame.  Reject face points in the outer 10%
        # to kill the diagonal lines without losing real face data.
        if idx in _FACE_INDICES:
            if x < 0.10 or x > 0.90 or y < 0.05 or y > 0.90:
                return False
        return True

    # ── 1. Draw connections (each segment colored by its own region) ──
    for start_idx, end_idx in POSE_CONNECTIONS:
        # Skip connections where either endpoint is invalid
        if not _kp_valid(start_idx) or not _kp_valid(end_idx):
            continue

        start_kp = keypoints[start_idx]
        end_kp = keypoints[end_idx]

        x1, y1 = int(start_kp[0] * w), int(start_kp[1] * h)
        x2, y2 = int(end_kp[0] * w), int(end_kp[1] * h)

        vis_start = start_kp[3] if len(start_kp) > 3 else 1.0
        vis_end = end_kp[3] if len(end_kp) > 3 else 1.0
        c = _dimmed(conn_color.get((start_idx, end_idx), overall_color), min(vis_start, vis_end))

        cv2.line(glow, (x1, y1), (x2, y2), c, 8, cv2.LINE_AA)
        cv2.line(overlay, (x1, y1), (x2, y2), c, 3, cv2.LINE_AA)

    # ── 2. Draw keypoints (colored by worst region touching the joint) ──
    for i, kp in enumerate(keypoints):
        if not _kp_valid(i):
            continue
        x, y = int(kp[0] * w), int(kp[1] * h)
        visibility = kp[3] if len(kp) > 3 else 1.0
        c = _dimmed(joint_color.get(i, overall_color), visibility)

        cv2.circle(glow, (x, y), 9, c, -1, cv2.LINE_AA)
        cv2.circle(overlay, (x, y), 5, c, -1, cv2.LINE_AA)
        cv2.circle(overlay, (x, y), 6, _dimmed((235, 255, 245), visibility), 1, cv2.LINE_AA)

    # Blend overlay with original frame
    cv2.addWeighted(glow, 0.28, frame, 0.72, 0, frame)
    cv2.addWeighted(overlay, 0.82, frame, 0.18, 0, frame)

    # ── 3. Per-joint angle labels (colored by their joint's region) ──
    for feat_name, short, kp_idx, (dx, dy) in LABEL_CONFIG:
        if not _kp_valid(kp_idx):
            continue
        value = features.get(feat_name)
        if value is None or (isinstance(value, float) and math.isnan(value)):
            continue
        kp = keypoints[kp_idx]
        kx = int(kp[0] * w)
        ky = int(kp[1] * h)
        lx = kx + dx
        ly = ky + dy
        lx = max(4, min(lx, w - 80))
        ly = max(14, min(ly, h - 4))
        text = f"{short}:{value:.1f}"
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 0.45
        thick = 1
        (tw, th), base = cv2.getTextSize(text, font, scale, thick)
        pad = 4
        label_color = joint_color.get(kp_idx, overall_color)
        cv2.rectangle(frame, (lx - pad, ly - th - pad),
                      (lx + tw + pad, ly + base + pad), (8, 12, 18), -1)
        cv2.rectangle(frame, (lx - pad, ly - th - pad),
                      (lx + tw + pad, ly + base + pad), label_color, 1)
        cv2.putText(frame, text, (lx, ly), font, scale, label_color, thick, cv2.LINE_AA)

    # Add risk level indicator
    cv2.rectangle(frame, (10, h - 46), (180, h - 12), (8, 12, 18), -1)
    cv2.rectangle(frame, (10, h - 46), (180, h - 12), overall_color, 1)
    cv2.putText(frame, f"RISK: {risk_level}", (20, h - 23),
                cv2.FONT_HERSHEY_SIMPLEX, 0.58, overall_color, 2, cv2.LINE_AA)

    return frame


def draw_person_boxes(frame, person_boxes, identified_worker=None):
    """Draw YOLO person bounding boxes with worker identity tags.

    *person_boxes*: list of normalized ``{x1, y1, x2, y2, confidence}`` dicts
    (0-1 xyxy). *identified_worker*: ``{worker_id, name, confidence}`` for the
    primary person (from face recognition), or None/{} when unknown.

    The primary (largest) box is drawn in the worker accent color; secondary
    boxes are dimmed. When the primary person is identified by face, the box
    is tagged with the worker's name + confidence; otherwise the tag reads
    "Unidentified".
    """
    if not person_boxes:
        return frame

    h, w = frame.shape[:2]
    id_conf = float((identified_worker or {}).get("confidence", 0.0))
    id_name = (identified_worker or {}).get("name") or (identified_worker or {}).get("worker_id")
    identified = bool((identified_worker or {}).get("matched")) and bool(id_name)

    # Primary box = largest area (the person the pipeline is monitoring).
    primary = max(person_boxes, key=lambda b: (b["x2"] - b["x1"]) * (b["y2"] - b["y1"]))

    for box in person_boxes:
        x1 = int(box["x1"] * w)
        y1 = int(box["y1"] * h)
        x2 = int(box["x2"] * w)
        y2 = int(box["y2"] * h)
        is_primary = box is primary

        if is_primary and identified:
            color = (64, 224, 120)  # worker green
        elif is_primary:
            color = (80, 170, 255)  # primary amber-blue
        else:
            color = (120, 140, 170)  # dimmed secondary

        thickness = 3 if is_primary else 1
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness, cv2.LINE_AA)

        # Identity tag above the box.
        if is_primary:
            if identified:
                tag = f"{id_name}  ({id_conf:.0%})" if id_conf > 0 else id_name
            else:
                tag = "Unidentified"
            font = cv2.FONT_HERSHEY_SIMPLEX
            scale = 0.5
            thick = 2
            (tw, th), base = cv2.getTextSize(tag, font, scale, thick)
            pad = 6
            tx1 = max(0, min(x1, w - tw - pad * 2))
            ty1 = max(0, y1 - th - pad * 2 - 6)
            cv2.rectangle(frame, (tx1, ty1), (tx1 + tw + pad * 2, ty1 + th + pad * 2),
                          (8, 12, 18), -1)
            cv2.rectangle(frame, (tx1, ty1), (tx1 + tw + pad * 2, ty1 + th + pad * 2),
                          color, 1)
            cv2.putText(frame, tag, (tx1 + pad, ty1 + th + pad - 4),
                        font, scale, color, thick, cv2.LINE_AA)

    return frame
