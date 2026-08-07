from __future__ import annotations

import sys
import time
from collections import deque
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.features import (
    RISK_COLORS_BGR,
    risk_breakdown,
    compute_rula_informed_score,
)
from backend.services.camera_manager import get_camera_from_args
from backend.services.issue_detection import summarize_issues
from backend.services.recommendation_engine import format_recommendations_text
from backend.services.session_analytics import SessionAnalytics, save_session_summary
from backend.services.pose_engine import PoseEngine, RISK_LEVELS

MODEL_PATH = str(ROOT / "models" / "pose_landmarker_lite.task")
SCREENSHOT_DIR = ROOT / "outputs" / "screenshots"

RISK_LABELS = {"LOW": "Good Posture", "MEDIUM": "Moderate Risk", "HIGH": "High Risk"}

STATUS_COLORS_BGR = {
    "LOW": (50, 180, 50),
    "MEDIUM": (30, 150, 220),
    "HIGH": (40, 40, 200),
}

SAMPLE_INTERVAL = 5

FEATURE_DISPLAY = [
    ("neck_flexion", "Neck Flexion", "deg"),
    ("trunk_flexion", "Trunk Flexion", "deg"),
    ("left_shoulder_elev", "L Shoulder Elev", "deg"),
    ("right_shoulder_elev", "R Shoulder Elev", "deg"),
    ("shoulder_symmetry", "Shoulder Sym", "%"),
    ("alignment_deviation", "Alignment Dev", "%"),
    ("knee_angle", "Knee Angle", "deg"),
    ("elbow_flexion_angle", "Elbow Flexion", "deg"),
    ("upper_arm_angle_from_vertical", "Upper Arm Angle", "deg"),
    ("movement_velocity", "Movement Vel", "deg/s"),
]

# Info panel section heights (must be >= each section's content height)
_H_HEADER   = 70
_H_SESSION  = 50
_H_STATUS   = 52
_H_TASK     = 80
_H_FEATURES = 310
_H_RULA     = 65
_H_ISSUES   = 85
_H_GUIDANCE = 115
_H_STATS    = 75
_H_RISK     = 120
_H_FOOTER   = 50
_G          = 4


def _posture_status_text(risk_level: str) -> str:
    return RISK_LABELS.get(risk_level, "Unknown")


def _draw_section_header(frame, x, y, w, text, color=(230, 230, 250)):
    cv2.putText(
        frame, text, (x + 10, y),
        cv2.FONT_HERSHEY_SIMPLEX, 0.72, color, 2, lineType=cv2.LINE_AA,
    )
    return y + 24


def _draw_separator(frame, x, y, w):
    cv2.line(frame, (x + 10, y), (x + w - 10, y), (60, 60, 80), 1)


def _draw_text_with_bg(
    frame: np.ndarray,
    text: str,
    x: int, y: int,
    font_scale: float,
    color: tuple[int, int, int],
    thickness: int,
    bg_color: tuple[int, int, int] | None = None,
    pad: int = 3,
):
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
    if bg_color is not None:
        cv2.rectangle(
            frame,
            (x - pad, y - th - pad),
            (x + tw + pad, y + pad),
            bg_color, -1,
        )
    cv2.putText(
        frame, text, (x, y),
        cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness,
        lineType=cv2.LINE_AA,
    )


def _wrap_text(text: str, max_w: int, font_scale: float, thickness: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for word in words:
        test = f"{cur} {word}" if cur else word
        (tw, _), _ = cv2.getTextSize(test, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
        if tw > max_w and cur:
            lines.append(cur)
            cur = word
        else:
            cur = test
    if cur:
        lines.append(cur)
    return lines


MEDIAPIPE_POSE_CONNECTIONS = [
    (0, 7), (0, 8), (7, 11), (8, 12),
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
    (11, 23), (12, 24), (23, 24),
    (23, 25), (25, 27), (24, 26), (26, 28),
]


def draw_skeleton(frame: np.ndarray, keypoints: list[list[float]], features: dict[str, float]) -> np.ndarray:
    green = RISK_COLORS_BGR["LOW"]
    red = RISK_COLORS_BGR["HIGH"]

    def _seg_color(feat_name: str, high_thresh: float) -> tuple[int, int, int]:
        return red if features.get(feat_name, 0) > high_thresh else green

    neck_c = _seg_color("neck_flexion", 30)
    trunk_c = _seg_color("trunk_flexion", 60)
    shoulder_c = _seg_color("left_shoulder_elev", 60)

    seg_colors: dict[tuple[int, int], tuple[int, int, int]] = {}
    for a, b in MEDIAPIPE_POSE_CONNECTIONS:
        seg_colors[(a, b)] = green
    for a, b in [(0, 7), (0, 8), (7, 11), (8, 12)]:
        seg_colors[(a, b)] = neck_c
    for a, b in [(11, 12), (11, 13), (13, 15), (12, 14), (14, 16)]:
        seg_colors[(a, b)] = shoulder_c
    for a, b in [(11, 23), (12, 24), (23, 24), (23, 25), (25, 27), (24, 26), (26, 28)]:
        seg_colors[(a, b)] = trunk_c

    for (a, b), color in seg_colors.items():
        if a >= len(keypoints) or b >= len(keypoints):
            continue
        p1 = tuple(np.round(keypoints[a][:2]).astype(int))
        p2 = tuple(np.round(keypoints[b][:2]).astype(int))
        cv2.line(frame, p1, p2, color, 3, lineType=cv2.LINE_AA)

    for idx, kp in enumerate(keypoints):
        if idx >= 33:
            continue
        color = green
        if idx in {7, 8}:
            color = neck_c
        elif idx in {11, 12, 13, 14, 15, 16}:
            color = shoulder_c
        elif idx in {23, 24, 25, 26, 27, 28}:
            color = trunk_c
        pt = tuple(np.round(kp[:2]).astype(int))
        cv2.circle(frame, pt, 5, color, -1, lineType=cv2.LINE_AA)

    return frame


def draw_panel(
    frame: np.ndarray,
    features: dict[str, float],
    risk_level: str,
    fps: float,
    confidence: float,
    risk_history: deque,
    session_stats: dict,
    timestamp_str: str,
    screenshot_count: int,
    issues: list[dict] | None = None,
    recommendations: list[dict] | None = None,
    task_info: dict | None = None,
    panel_width: int = 360,
    scroll_offset: int = 0,
    max_scroll_out: list[int] | None = None,
    rula_score: int | None = None,
    session_duration: float = 0.0,
    session_id: str = "",
    unavailable_features: list[str] | None = None,
) -> np.ndarray:
    h, w = frame.shape[:2]
    px = w - panel_width
    cw = panel_width - 20

    STATUS_SZ = 0.72
    MAIN_HDR = 0.80
    MED_SZ = 0.52
    SML_SZ = 0.42
    FEAT_SZ = 0.43

    max_issues = 3

    CARD_BG = (28, 28, 42)
    CARD_BORDER = (55, 55, 70)
    TXT_BG = (18, 18, 30)

    overlay = frame.copy()
    cv2.rectangle(overlay, (px, 0), (w, h), (18, 18, 28), -1)
    frame = cv2.addWeighted(overlay, 0.88, frame, 0.12, 0)

    x = px + 12

    G = _G
    panel_top = 28

    # Running cursor — each section starts here and advances past its own height
    _cursor = panel_top

    # ===================================================================
    # HEADER  –  70 px
    # ===================================================================
    cy = _cursor - scroll_offset
    cv2.putText(frame, "POSTURE ANALYSIS", (x + 10, cy),
                cv2.FONT_HERSHEY_SIMPLEX, MAIN_HDR, (230, 230, 250), 2,
                lineType=cv2.LINE_AA)
    cy += 26
    cv2.putText(frame, timestamp_str, (x + 10, cy),
                cv2.FONT_HERSHEY_SIMPLEX, SML_SZ, (140, 140, 170), 1,
                lineType=cv2.LINE_AA)
    _cursor += _H_HEADER + G

    # ===================================================================
    # SESSION  –  50 px
    # ===================================================================
    cy0 = _cursor - scroll_offset
    cv2.rectangle(frame, (x, cy0), (x + cw, cy0 + _H_SESSION), CARD_BG, -1)
    cv2.rectangle(frame, (x, cy0), (x + cw, cy0 + _H_SESSION), CARD_BORDER, 1)
    cy = cy0 + 8
    cy = _draw_section_header(frame, x, cy, cw, "SESSION")
    cy += 4
    dur_m = int(session_duration // 60)
    dur_s = int(session_duration % 60)
    dur_str = f"{dur_m:02d}:{dur_s:02d}"
    _draw_text_with_bg(frame, f"Duration: {dur_str}", x + 14, cy + 9,
                       SML_SZ, (180, 180, 220), 1, TXT_BG)
    if session_id:
        sid_short = session_id[-8:] if len(session_id) > 8 else session_id
        (sidw, _), _ = cv2.getTextSize(sid_short, cv2.FONT_HERSHEY_SIMPLEX, SML_SZ, 1)
        _draw_text_with_bg(frame, sid_short, x + cw - sidw - 10, cy + 9,
                           SML_SZ, (120, 120, 150), 1, TXT_BG)
    _cursor += _H_SESSION + G

    # ===================================================================
    # STATUS BADGE  –  52 px
    # ===================================================================
    cy0 = _cursor - scroll_offset
    status = _posture_status_text(risk_level)
    status_color = STATUS_COLORS_BGR[risk_level]
    bw2 = cw - 20
    bh2 = 40
    bx2 = x + 10
    by2 = cy0 + (52 - bh2) // 2
    cv2.rectangle(frame, (bx2, by2), (bx2 + bw2, by2 + bh2), status_color, -1)
    cv2.rectangle(frame, (bx2, by2), (bx2 + bw2, by2 + bh2), (255, 255, 255), 1)
    (tw_, th_), _ = cv2.getTextSize(status, cv2.FONT_HERSHEY_SIMPLEX, STATUS_SZ, 2)
    tx2 = bx2 + (bw2 - tw_) // 2
    ty2 = by2 + (bh2 + th_) // 2
    text_color = (20, 20, 30) if risk_level == "MEDIUM" else (255, 255, 255)
    cv2.putText(frame, status, (tx2, ty2), cv2.FONT_HERSHEY_SIMPLEX, STATUS_SZ, text_color, 2,
                lineType=cv2.LINE_AA)
    conf_color = (50, 200, 50) if confidence > 80 else (30, 150, 220) if confidence > 50 else (40, 40, 200)
    conf_str = f"Conf: {confidence:.0f}%"
    (cw_, _), _ = cv2.getTextSize(conf_str, cv2.FONT_HERSHEY_SIMPLEX, SML_SZ, 1)
    _draw_text_with_bg(frame, conf_str, bx2 + bw2 - cw_ - 12, ty2,
                       SML_SZ, conf_color, 1, TXT_BG, 4)
    _cursor += _H_STATUS + G

    # ===================================================================
    # CURRENT TASK  –  80 px  (improved: task name + confidence only)
    # ===================================================================
    if task_info:
        cy0 = _cursor - scroll_offset
        cv2.rectangle(frame, (x, cy0), (x + cw, cy0 + 80), CARD_BG, -1)
        cv2.rectangle(frame, (x, cy0), (x + cw, cy0 + 80), CARD_BORDER, 1)

        cy = cy0 + 8
        cy = _draw_section_header(frame, x, cy, cw, "CURRENT TASK")
        cy += 8

        task_name = task_info.get("task", "Unknown")
        task_conf = task_info.get("confidence", 0.0)
        task_color = (100, 180, 255)

        _draw_text_with_bg(frame, task_name, x + 14, cy + 10,
                           MED_SZ, task_color, 2, TXT_BG)
        (_, tnh), _ = cv2.getTextSize(task_name, cv2.FONT_HERSHEY_SIMPLEX, MED_SZ, 2)
        cy += tnh + 4

        conf_s = f"Confidence: {task_conf:.0f}%"
        _draw_text_with_bg(frame, conf_s, x + 14, cy + 10,
                           SML_SZ, (200, 200, 220), 1, TXT_BG)
        _cursor += _H_TASK + G

    # ===================================================================
    # FEATURES  –  310 px
    # ===================================================================
    cy0 = _cursor - scroll_offset
    cv2.rectangle(frame, (x, cy0), (x + cw, cy0 + 310), CARD_BG, -1)
    cv2.rectangle(frame, (x, cy0), (x + cw, cy0 + 310), CARD_BORDER, 1)

    cy = cy0 + 8
    cy = _draw_section_header(frame, x, cy, cw, "FEATURES")
    cy += 8

    bar_max_w = cw - 40
    bar_h = 7
    breakdown = risk_breakdown(features)
    BAR_COLORS = {"LOW": (50, 180, 50), "MEDIUM": (0, 165, 255), "HIGH": (40, 40, 200), "UNKNOWN": (128, 128, 128)}
    for feat_key, feat_label, unit in FEATURE_DISPLAY:
        val = features.get(feat_key, 0.0)
        br = breakdown.get(feat_key)
        frisk = br.level if br else "LOW"
        bar_color = BAR_COLORS[frisk]

        _draw_text_with_bg(frame, feat_label, x + 10, cy + 9,
                           FEAT_SZ, (200, 200, 220), 2, TXT_BG)
        val_str = f"{val:.1f}{unit}"
        (vw, _), _ = cv2.getTextSize(val_str, cv2.FONT_HERSHEY_SIMPLEX, FEAT_SZ, 2)
        _draw_text_with_bg(frame, val_str, x + cw - vw - 10, cy + 9,
                           FEAT_SZ, bar_color, 2, TXT_BG)
        cy += 9

        bar_y = cy
        cv2.rectangle(frame, (x + 10, bar_y), (x + 10 + bar_max_w, bar_y + bar_h),
                      (55, 55, 75), -1)
        if feat_key == "knee_angle":
            norm = max(0.0, min(1.0, (val - 80) / 100.0))
        elif feat_key == "shoulder_symmetry":
            norm = max(0.0, min(1.0, val / 20.0))
        else:
            norm = max(0.0, min(1.0, val / 50.0))
        fill_w = int(bar_max_w * norm)
        if fill_w > 0:
            cv2.rectangle(frame, (x + 10, bar_y),
                          (x + 10 + fill_w, bar_y + bar_h), bar_color, -1)
        cy += bar_h + 2
    _cursor += _H_FEATURES + G

    # ===================================================================
    # RULA SCORE  –  65 px
    # ===================================================================
    if rula_score is not None:
        cy0 = _cursor - scroll_offset
        cv2.rectangle(frame, (x, cy0), (x + cw, cy0 + _H_RULA), CARD_BG, -1)
        cv2.rectangle(frame, (x, cy0), (x + cw, cy0 + _H_RULA), CARD_BORDER, 1)
        cy = cy0 + 8
        cy = _draw_section_header(frame, x, cy, cw, "RULA SCORE")
        cy += 4
        if rula_score <= 2:
            rula_color = (50, 180, 50)
        elif rula_score <= 4:
            rula_color = (0, 200, 220)
        elif rula_score <= 6:
            rula_color = (0, 165, 255)
        else:
            rula_color = (40, 40, 220)
        rula_str = f"{rula_score}/7"
        (rw_, rh_), _ = cv2.getTextSize(rula_str, cv2.FONT_HERSHEY_SIMPLEX, 0.80, 2)
        rx = x + 14
        ry = cy + rh_ + 2
        cv2.rectangle(frame, (rx - 4, ry - rh_ - 4), (rx + rw_ + 4, ry + 4), rula_color, -1)
        cv2.putText(frame, rula_str, (rx, ry),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.80, (255, 255, 255), 2, lineType=cv2.LINE_AA)
        if rula_score <= 2:
            rula_label = "Low Risk"
        elif rula_score <= 4:
            rula_label = "Medium Risk"
        elif rula_score <= 6:
            rula_label = "High Risk"
        else:
            rula_label = "Very High Risk"
        _draw_text_with_bg(frame, rula_label, rx + rw_ + 16, ry,
                           SML_SZ, rula_color, 1, TXT_BG)
        _cursor += _H_RULA + G

    # ===================================================================
    # VISIBILITY WARNING  –  shown when lower body landmarks unavailable
    # ===================================================================
    if unavailable_features:
        lower_body_missing = {"trunk_flexion", "knee_angle", "neck_flexion"} & set(unavailable_features)
        if lower_body_missing:
            warn_h = 58
            cy0 = _cursor - scroll_offset
            cv2.rectangle(frame, (x, cy0), (x + cw, cy0 + warn_h), (20, 30, 60), -1)
            cv2.rectangle(frame, (x, cy0), (x + cw, cy0 + warn_h), (0, 165, 255), 1)
            cy = cy0 + 8
            cy = _draw_section_header(frame, x, cy, cw, "⚠ CAMERA FRAMING")
            cy += 2
            _draw_text_with_bg(frame, "Lower body out of frame", x + 10, cy,
                               SML_SZ, (0, 200, 255), 1, TXT_BG)
            cy += 16
            _draw_text_with_bg(frame, "Reposition camera: head to mid-thigh",
                               x + 10, cy, SML_SZ, (0, 180, 230), 1, TXT_BG)
            cy += 16
            _draw_text_with_bg(frame, f"Missing: {', '.join(sorted(lower_body_missing))}",
                               x + 10, cy, SML_SZ, (0, 160, 210), 1, TXT_BG)
            _cursor += warn_h + G

    # ===================================================================
    # ISSUES  –  85 px  (max 3, then "+N more...")
    # ===================================================================
    if issues:
        cy0 = _cursor - scroll_offset
        cv2.rectangle(frame, (x, cy0), (x + cw, cy0 + 85), CARD_BG, -1)
        cv2.rectangle(frame, (x, cy0), (x + cw, cy0 + 85), CARD_BORDER, 1)

        cy = cy0 + 8
        cy = _draw_section_header(frame, x, cy, cw, "ISSUES DETECTED")
        cy += 4

        shown = issues[:max_issues]
        remaining = len(issues) - max_issues

        for issue in shown:
            severity = issue["severity"]
            sev_color = RISK_COLORS_BGR.get(severity, (180, 180, 200))
            badge_text = "[MED]" if severity == "MEDIUM" else f"[{severity[:4]}]"

            card_h = 14
            cv2.rectangle(frame, (x + 10, cy), (x + cw - 10, cy + card_h),
                          (30, 30, 45), -1)
            cv2.rectangle(frame, (x + 10, cy), (x + cw - 10, cy + card_h),
                          (55, 55, 75), 1)

            (bw_, bh_), _ = cv2.getTextSize(badge_text, cv2.FONT_HERSHEY_SIMPLEX, MED_SZ, 2)
            badge_x = x + 14
            pad_h = 4
            cv2.rectangle(frame, (badge_x, cy + 2),
                          (badge_x + bw_ + pad_h * 2, cy + card_h - 2), sev_color, -1)
            cv2.putText(frame, badge_text, (badge_x + pad_h, cy + 11),
                        cv2.FONT_HERSHEY_SIMPLEX, MED_SZ, (255, 255, 255), 2,
                        lineType=cv2.LINE_AA)

            issue_label = issue["issue"]
            label_x = badge_x + bw_ + pad_h * 2 + 8
            max_lw = (x + cw - 10) - label_x - 4
            if max_lw > 0:
                orig_len = len(issue_label)
                (lw_, _), _ = cv2.getTextSize(issue_label, cv2.FONT_HERSHEY_SIMPLEX, MED_SZ, 2)
                while lw_ > max_lw and len(issue_label) > 3:
                    issue_label = issue_label[:-1]
                    (lw_, _), _ = cv2.getTextSize(issue_label + "..", cv2.FONT_HERSHEY_SIMPLEX, MED_SZ, 2)
                if lw_ > max_lw:
                    issue_label = issue_label[:2] + ".."
                elif len(issue["issue"]) > len(issue_label):
                    issue_label += ".."
                _draw_text_with_bg(frame, issue_label, label_x, cy + 11,
                                   MED_SZ, (210, 210, 230), 2, TXT_BG)
            cy += card_h + 1

        if remaining > 0:
            more_text = f"+{remaining} more..."
            _draw_text_with_bg(frame, more_text, x + 14, cy + 12,
                               MED_SZ, (180, 180, 200), 1, TXT_BG)
        _cursor += _H_ISSUES + G

    # ===================================================================
    # GUIDANCE  –  115 px  (max 1 wrapped line, truncate)
    # ===================================================================
    if recommendations:
        cy0 = _cursor - scroll_offset
        cv2.rectangle(frame, (x, cy0), (x + cw, cy0 + 115), CARD_BG, -1)
        cv2.rectangle(frame, (x, cy0), (x + cw, cy0 + 115), CARD_BORDER, 1)

        cy = cy0 + 8
        cy = _draw_section_header(frame, x, cy, cw, "GUIDANCE")
        cy += 6

        rec = recommendations[0]
        rcolor = RISK_COLORS_BGR.get(rec["severity"], (180, 180, 200))
        max_tw = cw - 30

        action = rec["worker_actions"][0] if rec["worker_actions"] else ""
        _draw_text_with_bg(frame, "Worker:", x + 14, cy + 10,
                           MED_SZ, rcolor, 2, TXT_BG)
        cy += 13
        if action:
            lines = _wrap_text(action, max_tw, SML_SZ, 1)
            line = lines[0] if lines else ""
            if len(lines) > 1:
                while len(line) > 1:
                    line = line[:-1]
                    (lw_, _), _ = cv2.getTextSize(line + "...", cv2.FONT_HERSHEY_SIMPLEX, SML_SZ, 1)
                    if lw_ <= max_tw:
                        break
                line += "..."
            _draw_text_with_bg(frame, line, x + 20, cy + 9, SML_SZ, rcolor, 1, TXT_BG)
        else:
            _draw_text_with_bg(frame, "N/A", x + 20, cy + 9, SML_SZ, rcolor, 1, TXT_BG)
        cy += 11 + 4

        sup_text = rec["supervisor_actions"][0] if rec["supervisor_actions"] else ""
        _draw_text_with_bg(frame, "Supervisor:", x + 14, cy + 10,
                           MED_SZ, (180, 180, 220), 2, TXT_BG)
        cy += 13
        if sup_text:
            lines = _wrap_text(sup_text, max_tw, SML_SZ, 1)
            line = lines[0] if lines else ""
            if len(lines) > 1:
                while len(line) > 1:
                    line = line[:-1]
                    (lw_, _), _ = cv2.getTextSize(line + "...", cv2.FONT_HERSHEY_SIMPLEX, SML_SZ, 1)
                    if lw_ <= max_tw:
                        break
                line += "..."
            _draw_text_with_bg(frame, line, x + 20, cy + 9, SML_SZ, (180, 180, 220), 1, TXT_BG)
        else:
            _draw_text_with_bg(frame, "N/A", x + 20, cy + 9, SML_SZ, (180, 180, 220), 1, TXT_BG)
        _cursor += _H_GUIDANCE + G

    # ===================================================================
    # SESSION STATS  –  75 px  (4 items, 2 rows)
    # ===================================================================
    cy0 = _cursor - scroll_offset
    cv2.rectangle(frame, (x, cy0), (x + cw, cy0 + _H_STATS), CARD_BG, -1)
    cv2.rectangle(frame, (x, cy0), (x + cw, cy0 + _H_STATS), CARD_BORDER, 1)

    cy = cy0 + 8
    cy = _draw_section_header(frame, x, cy, cw, "SESSION STATS")
    cy += 6

    STATS_SZ = 0.45
    mid_x = x + cw // 2
    stat_rows = [
        ("Avg Neck :", f'{session_stats["avg_neck"]:.1f}\u00b0', "Max Risk :", session_stats["max_risk"]),
        ("Avg Trunk:", f'{session_stats["avg_trunk"]:.1f}\u00b0', "FPS :", f"{fps:.0f}"),
    ]
    for c1_label, c1_val, c2_label, c2_val in stat_rows:
        _draw_text_with_bg(frame, c1_label, x + 10, cy + 9,
                           STATS_SZ, (180, 180, 200), 1, TXT_BG)
        (v1w, _), _ = cv2.getTextSize(c1_val, cv2.FONT_HERSHEY_SIMPLEX, STATS_SZ, 1)
        _draw_text_with_bg(frame, c1_val, mid_x - v1w - 6, cy + 9,
                           STATS_SZ, (210, 210, 230), 1, TXT_BG)
        _draw_text_with_bg(frame, c2_label, mid_x + 10, cy + 9,
                           STATS_SZ, (180, 180, 200), 1, TXT_BG)
        (v2w, _), _ = cv2.getTextSize(c2_val, cv2.FONT_HERSHEY_SIMPLEX, STATS_SZ, 1)
        v2color = RISK_COLORS_BGR.get(session_stats["max_risk"], (210, 210, 230))
        _draw_text_with_bg(frame, c2_val, x + cw - v2w - 10, cy + 9,
                           STATS_SZ, v2color, 1, TXT_BG)
        cy += 13
    _cursor += _H_STATS + G

    # ===================================================================
    # RISK HISTORY  –  120 px
    # ===================================================================
    cy0 = _cursor - scroll_offset
    cv2.rectangle(frame, (x, cy0), (x + cw, cy0 + _H_RISK), CARD_BG, -1)
    cv2.rectangle(frame, (x, cy0), (x + cw, cy0 + _H_RISK), CARD_BORDER, 1)

    cy = cy0 + 8
    cy = _draw_section_header(frame, x, cy, cw, "RISK HISTORY (30s)")
    cy += 5

    chart_h = 110 - (cy - cy0) - 8
    chart_x = x + 10
    chart_y = cy
    chart_w = cw - 20
    cv2.rectangle(frame, (chart_x, chart_y), (chart_x + chart_w, chart_y + chart_h),
                  (25, 25, 40), -1)
    cv2.rectangle(frame, (chart_x, chart_y), (chart_x + chart_w, chart_y + chart_h),
                  (55, 55, 75), 1)

    if risk_history:
        n = len(risk_history)
        for i in range(n - 1):
            t0, v0 = risk_history[i]
            t1, v1 = risk_history[i + 1]
            x0 = chart_x + int((t0 - risk_history[0][0]) / (risk_history[-1][0] - risk_history[0][0] + 1e-6) * chart_w)
            x1 = chart_x + int((t1 - risk_history[0][0]) / (risk_history[-1][0] - risk_history[0][0] + 1e-6) * chart_w)
            y0 = chart_y + chart_h - int((v0 / 2.0) * (chart_h - 4)) - 2
            y1 = chart_y + chart_h - int((v1 / 2.0) * (chart_h - 4)) - 2
            level = "HIGH" if v0 > 1.5 else "MEDIUM" if v0 > 0.5 else "LOW"
            cv2.line(frame, (x0, y0), (x1, y1), STATUS_COLORS_BGR[level], 2, cv2.LINE_AA)

    for rl, rv in [("HIGH", 2), ("MEDIUM", 1), ("LOW", 0)]:
        yy = chart_y + chart_h - int((rv / 2.0) * (chart_h - 4)) - 2
        (rlw, _), _ = cv2.getTextSize(rl[:3], cv2.FONT_HERSHEY_SIMPLEX, SML_SZ, 1)
        cv2.putText(frame, rl[:3], (chart_x + chart_w - rlw - 4, yy + 4),
                    cv2.FONT_HERSHEY_SIMPLEX, SML_SZ, (120, 120, 150), 1,
                    lineType=cv2.LINE_AA)
    _cursor += _H_RISK + G

    # ===================================================================
    # FOOTER  –  50 px
    # ===================================================================
    cy0 = _cursor - scroll_offset
    cv2.putText(frame, "Q = Quit", (x + 10, cy0 + 12),
                cv2.FONT_HERSHEY_SIMPLEX, SML_SZ, (120, 120, 140), 1,
                lineType=cv2.LINE_AA)
    cv2.putText(frame, "S = Screenshot", (x + 10, cy0 + 28),
                cv2.FONT_HERSHEY_SIMPLEX, SML_SZ, (120, 120, 140), 1,
                lineType=cv2.LINE_AA)
    if screenshot_count > 0:
        ss_str = f"({screenshot_count})"
        (ssw, _), _ = cv2.getTextSize(ss_str, cv2.FONT_HERSHEY_SIMPLEX, SML_SZ, 1)
        cv2.putText(frame, ss_str, (x + cw - ssw - 10, cy0 + 28),
                    cv2.FONT_HERSHEY_SIMPLEX, SML_SZ, (100, 100, 130), 1,
                    lineType=cv2.LINE_AA)
    _cursor += _H_FOOTER + G

    total_panel_h = _cursor - panel_top
    if max_scroll_out is not None:
        max_scroll_out[0] = max(0, total_panel_h - h)
    if total_panel_h > h:
        if scroll_offset > 0:
            cv2.putText(frame, "^", (x + cw // 2 - 6, 12),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 200), 2,
                        lineType=cv2.LINE_AA)
        if scroll_offset + h < total_panel_h:
            cv2.putText(frame, "v", (x + cw // 2 - 6, h - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 200), 2,
                        lineType=cv2.LINE_AA)

    return frame


def main() -> None:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    cap, cam_info = get_camera_from_args()

    preferred = [(1920, 1080), (1280, 720), (960, 720), (640, 480)]
    for pw, ph in preferred:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, pw)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, ph)
        aw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        ah = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if aw == pw and ah == ph:
            break

    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Self-sizing canvas: panel height = sum of all section heights + gaps.
    # Output canvas is at least camera height, but never smaller than panel needs.
    _MIN_PANEL_HEIGHT = (
        _H_HEADER + _H_STATUS + _H_TASK + _H_FEATURES
        + _H_ISSUES + _H_GUIDANCE + _H_STATS + _H_RISK + _H_FOOTER
        + 9 * _G       # one gap between each of the 9 sections
        + 20           # bottom margin
    )
    output_h = max(actual_h, _MIN_PANEL_HEIGHT)
    output_w = actual_w
    left_w = int(output_w * 0.70)
    right_w = output_w - left_w

    print(f"\nSelected Camera: {cam_info.index} ({cam_info.name})")
    print(f"  Name: {cam_info.name}")
    print(f"  Resolution: {actual_w}x{actual_h}")
    print(f"  Output canvas: {output_w}x{output_h}")
    print(f"  Panel height: {_MIN_PANEL_HEIGHT}px (camera: {actual_h}px)")
    print(f"  Layout: {left_w} feed + {right_w} panel (70/30 split)")

    analytics = SessionAnalytics()
    engine = PoseEngine(MODEL_PATH)
    engine.initialize()
    risk_order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}

    scroll_offset: list[int] = [0]
    max_scroll: list[int] = [0]

    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_MOUSEWHEEL:
            if flags > 0:
                scroll_offset[0] = max(0, scroll_offset[0] - 40)
            else:
                scroll_offset[0] = min(max_scroll[0], scroll_offset[0] + 40)

    fps = 0.0
    frame_count = 0
    fps_start = time.perf_counter()

    risk_history: deque = deque(maxlen=600)
    sample_counter = 0

    session_neck: deque = deque(maxlen=900)
    session_trunk: deque = deque(maxlen=900)
    max_risk = "LOW"

    screenshot_count = 0
    last_screenshot_time = 0.0
    screenshot_cooldown = 0.5
    session_start = time.perf_counter()

    print("Live Posture Analysis Demo")
    print("Q = Quit  |  S = Screenshot  |  Scroll: Mouse wheel")
    print(f"Screenshots saved to: {SCREENSHOT_DIR}")

    cv2.namedWindow("Live Posture Analysis - Demo Mode", cv2.WINDOW_NORMAL)
    cv2.setMouseCallback("Live Posture Analysis - Demo Mode", on_mouse)

    while True:
        ret, frame = cap.read()
        if not ret:
            print("ERROR: Failed to read frame.")
            break

        frame = cv2.flip(frame, 1)
        result = engine.process_frame(frame)

        features = result.features
        risk_level = result.risk_level
        confidence = result.confidence
        person_detected = result.person_detected
        task_info = result.task_info

        # Compute RULA score from features
        rula_score_val = None
        if person_detected and any(v > 0 for v in features.values()):
            try:
                rula_result = compute_rula_informed_score(features)
                rula_score_val = rula_result["rula_informed_score"]
            except Exception:
                rula_score_val = None

        output = np.zeros((output_h, output_w, 3), dtype=np.uint8)

        # Camera feed uses original actual_h (not output_h) so it's framed in
        # the top portion of the canvas; the panel below extends freely.
        cam_h, cam_w = frame.shape[:2]
        feed_scale = max(left_w / cam_w, actual_h / cam_h)
        dw = int(cam_w * feed_scale)
        dh = int(cam_h * feed_scale)
        fx = (left_w - dw) // 2
        fy = (actual_h - dh) // 2

        feed = cv2.resize(frame, (dw, dh))
        src_x1 = max(0, -fx)
        src_y1 = max(0, -fy)
        src_x2 = min(dw, left_w - fx)
        src_y2 = min(dh, actual_h - fy)
        dst_x1 = max(0, fx)
        dst_y1 = max(0, fy)
        cw_seg = src_x2 - src_x1
        ch_seg = src_y2 - src_y1
        if cw_seg > 0 and ch_seg > 0:
            output[dst_y1:dst_y1 + ch_seg, dst_x1:dst_x1 + cw_seg] = feed[src_y1:src_y1 + ch_seg, src_x1:src_x1 + cw_seg]

        if person_detected:
            adj_kps = [[kp[0] * feed_scale + fx, kp[1] * feed_scale + fy] for kp in result.keypoints]
            draw_skeleton(output, adj_kps, features)

            session_neck.append(features.get("neck_flexion", 0.0))
            session_trunk.append(features.get("trunk_flexion", 0.0))
            if risk_order.get(risk_level, 0) > risk_order.get(max_risk, 0):
                max_risk = risk_level
        else:
            label = "No person detected"
            (lw_t, lh_t), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 2)
            cx = left_w // 2
            cy = actual_h // 2
            cv2.putText(
                output, label, (cx - lw_t // 2, cy),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (120, 120, 160), 2,
            )

        now = time.perf_counter()
        frame_count += 1
        elapsed = now - fps_start
        if elapsed >= 0.5:
            fps = frame_count / elapsed
            frame_count = 0
            fps_start = now

        sample_counter += 1
        if sample_counter >= SAMPLE_INTERVAL and person_detected:
            sample_counter = 0
            risk_history.append((time.monotonic(), RISK_LEVELS.get(risk_level, 0)))

        risk_history_now = risk_history.copy()
        if risk_history_now:
            cutoff = time.monotonic() - 30.0
            while risk_history_now and risk_history_now[0][0] < cutoff:
                risk_history_now.popleft()

        avg_neck = float(np.mean(session_neck)) if session_neck else 0.0
        avg_trunk = float(np.mean(session_trunk)) if session_trunk else 0.0
        session_stats = {
            "avg_neck": avg_neck,
            "avg_trunk": avg_trunk,
            "max_risk": max_risk,
        }

        # --- Session info bar in left column below camera feed ---
        if output_h > actual_h:
            info_y = actual_h
            pad = 20
            line_h = 24
            elapsed_total = time.perf_counter() - session_start
            dur_str = f"{int(elapsed_total // 60):02d}:{int(elapsed_total % 60):02d}"

            cv2.rectangle(output, (0, info_y), (left_w, output_h), (18, 18, 28), -1)

            y = info_y + pad + 16
            left_lines = [f"Session: {dur_str}", f"Status: {_posture_status_text(risk_level)}"]
            right_lines = [f"FPS: {fps:.0f}", f"Screen: {screenshot_count}"]
            for i in range(max(len(left_lines), len(right_lines))):
                if i < len(left_lines):
                    cv2.putText(output, left_lines[i],
                                (pad, y + i * line_h),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180, 180, 200), 1, cv2.LINE_AA)
                if i < len(right_lines):
                    txt = right_lines[i]
                    (rw, _), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
                    cv2.putText(output, txt,
                                (left_w - rw - pad, y + i * line_h),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180, 180, 200), 1, cv2.LINE_AA)

            cv2.line(output, (0, info_y), (left_w, info_y), (50, 50, 70), 1)

        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        analytics.update(features, risk_level, result.issues, person_detected, timestamp_str)

        session_duration_val = time.perf_counter() - session_start

        output = draw_panel(
            output, features, risk_level, fps, confidence,
            risk_history_now, session_stats, timestamp_str, screenshot_count,
            issues=result.issues,
            recommendations=result.recommendations,
            task_info=task_info,
            panel_width=right_w,
            scroll_offset=scroll_offset[0],
            max_scroll_out=max_scroll,
            rula_score=rula_score_val,
            session_duration=session_duration_val,
            unavailable_features=result.unavailable_features,
        )

        cv2.imshow("Live Posture Analysis - Demo Mode", output)
        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):
            break
        elif key == ord("s"):
            ct = time.monotonic()
            if ct - last_screenshot_time >= screenshot_cooldown:
                last_screenshot_time = ct
                fname = f"posture_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                fpath = str(SCREENSHOT_DIR / fname)
                cv2.imwrite(fpath, output)
                screenshot_count += 1
                print(f"Screenshot saved: {fpath}")

    engine.release()
    summary = analytics.get_summary()
    saved_path = save_session_summary(summary, ROOT / "outputs" / "sessions")
    print(f"\n{'=' * 50}")
    print("SESSION ANALYTICS SUMMARY")
    print(f"{'=' * 50}")
    print(f"  Duration:          {summary['session_duration_seconds']}s")
    print(f"  Total Frames:      {summary['total_frames']}")
    print(f"  Risk Breakdown:")
    for rl in ("LOW", "MEDIUM", "HIGH"):
        print(f"    {rl:>8}: {summary['risk_percentages'].get(rl, 0):.1f}%")
    print(f"  Most Frequent:     {summary['most_frequent_issue'] or 'N/A'}")
    print(f"  Highest Risk:      {summary['highest_risk_level']}")
    print(f"  Risk Timestamp:    {summary['highest_risk_timestamp'] or 'N/A'}")
    print(f"  Avg Neck Flexion:  {summary['avg_neck_flexion']:.1f} deg")
    print(f"  Avg Trunk Flexion: {summary['avg_trunk_flexion']:.1f} deg")
    print(f"  Avg Shoulder Sym:  {summary['avg_shoulder_symmetry']:.1f} %")
    print(f"  Avg Knee Angle:    {summary['avg_knee_angle']:.1f} deg")
    print(f"{'=' * 50}")
    if saved_path:
        print(f"  Session saved: {saved_path}")

    cap.release()
    cv2.destroyAllWindows()
    print(f"\nSession ended. Screenshots captured: {screenshot_count}")


if __name__ == "__main__":
    main()
