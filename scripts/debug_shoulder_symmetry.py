from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python import vision

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.features import (
    _safe_distance,
    extract_features_from_keypoints,
    mediapipe_landmarks_to_keypoints,
)

MODEL_PATH = str(ROOT / "models" / "pose_landmarker_lite.task")
SCREENSHOT_DIR = ROOT / "outputs" / "debug_shoulder"

GREEN = (60, 200, 60)
RED = (40, 40, 220)
BLUE = (220, 150, 40)
YELLOW = (40, 220, 220)
CYAN = (220, 220, 60)
MAGENTA = (220, 60, 180)
ORANGE = (40, 140, 240)
WHITE = (240, 240, 240)
GRAY = (120, 120, 140)


def main() -> None:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    from backend.services.camera_manager import get_camera_from_args
    cap, cam_info = get_camera_from_args()

    options = vision.PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=MODEL_PATH),
        running_mode=vision.RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    pose_landmarker = vision.PoseLandmarker.create_from_options(options)

    timestamp_ms = 0
    screenshot_count = 0

    print("=== Shoulder Symmetry Diagnostic ===")
    print("Sit level, then tilt one shoulder up/down.")
    print("Press S to save screenshot, Q to quit")

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        timestamp_ms += 33
        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = pose_landmarker.detect_for_video(mp_image, timestamp_ms)

        display = frame.copy()
        h, w = display.shape[:2]

        if result.pose_landmarks:
            landmarks = result.pose_landmarks[0]
            kps = mediapipe_landmarks_to_keypoints(landmarks, w, h)
            features, _unavail = extract_features_from_keypoints(kps)

            left_shoulder = np.array(kps[11][:2])
            right_shoulder = np.array(kps[12][:2])
            left_elbow = np.array(kps[13][:2])
            right_elbow = np.array(kps[14][:2])

            shoulder_width = _safe_distance(left_shoulder, right_shoulder)
            ls_y, rs_y = left_shoulder[1], right_shoulder[1]
            y_delta = abs(ls_y - rs_y)
            symmetry = features.get("shoulder_symmetry", 0.0)

            # ── Draw shoulder points ──
            ls_pt = tuple(left_shoulder.astype(int))
            rs_pt = tuple(right_shoulder.astype(int))

            cv2.circle(display, ls_pt, 8, GREEN, -1, cv2.LINE_AA)
            cv2.circle(display, ls_pt, 8, WHITE, 2, cv2.LINE_AA)
            cv2.circle(display, rs_pt, 8, BLUE, -1, cv2.LINE_AA)
            cv2.circle(display, rs_pt, 8, WHITE, 2, cv2.LINE_AA)

            cv2.putText(display, "L", (ls_pt[0] - 20, ls_pt[1] + 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, GREEN, 2)
            cv2.putText(display, "R", (rs_pt[0] + 8, rs_pt[1] + 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, BLUE, 2)

            # ── Shoulder line ──
            cv2.line(display, ls_pt, rs_pt, ORANGE, 3, cv2.LINE_AA)

            # ── Horizontal reference lines ──
            min_x = min(ls_pt[0], rs_pt[0]) - 60
            max_x = max(ls_pt[0], rs_pt[0]) + 60
            cv2.line(display, (min_x, ls_pt[1]), (max_x, ls_pt[1]),
                     GREEN, 1, cv2.LINE_AA)
            cv2.line(display, (min_x, rs_pt[1]), (max_x, rs_pt[1]),
                     BLUE, 1, cv2.LINE_AA)

            # ── Vertical delta bracket ──
            mid_x = (ls_pt[0] + rs_pt[0]) // 2
            top_y = min(ls_pt[1], rs_pt[1])
            bot_y = max(ls_pt[1], rs_pt[1])
            bracket_x = max(ls_pt[0], rs_pt[0]) + 40
            cv2.line(display, (bracket_x, top_y), (bracket_x, bot_y),
                     YELLOW, 2, cv2.LINE_AA)
            cv2.line(display, (bracket_x - 5, top_y), (bracket_x + 5, top_y),
                     YELLOW, 1, cv2.LINE_AA)
            cv2.line(display, (bracket_x - 5, bot_y), (bracket_x + 5, bot_y),
                     YELLOW, 1, cv2.LINE_AA)
            mid_y = (top_y + bot_y) // 2
            cv2.putText(display, f"dy={y_delta:.0f}px", (bracket_x + 8, mid_y + 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, YELLOW, 1)

            # ── Elbow indicators ──
            for pt, label, color in [(left_elbow, "elbow L", GREEN), (right_elbow, "elbow R", BLUE)]:
                e_pt = tuple(pt.astype(int))
                cv2.circle(display, e_pt, 5, color, -1, cv2.LINE_AA)
                cv2.putText(display, label, (e_pt[0] + 8, e_pt[1] + 4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1)

            # ── Panel ──
            panel_x, panel_y = 15, 15
            line_h = 24
            lines = [
                f"shoulder_symmetry (reported): {symmetry:.1f} %",
                f"formula: |L_shoulder_y - R_shoulder_y| / shoulder_width * 100",
                f"",
                f"L_shoulder_y:   {ls_y:.0f} px",
                f"R_shoulder_y:   {rs_y:.0f} px",
                f"Y delta:        {y_delta:.0f} px",
                f"shoulder_width: {shoulder_width:.0f} px",
                f"",
                f"computed: {y_delta:.0f} / {shoulder_width:.0f} * 100 = {symmetry:.1f}%",
                f"",
                f"thresholds: LOW <=5%  MED 5-15%  HIGH >15%",
                f"",
                f"S: screenshot  |  Q: quit",
            ]
            panel_w = 500
            panel_h = len(lines) * line_h + 30
            overlay = display.copy()
            cv2.rectangle(overlay, (panel_x, panel_y),
                          (panel_x + panel_w, panel_y + panel_h), (15, 15, 25), -1)
            display = cv2.addWeighted(overlay, 0.9, display, 0.1, 0)
            cv2.rectangle(display, (panel_x, panel_y),
                          (panel_x + panel_w, panel_y + panel_h), (55, 55, 75), 1)

            cy = panel_y + 15
            cv2.putText(display, "SHOULDER SYMMETRY DIAGNOSTIC", (panel_x + 10, cy),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, CYAN, 2)
            cy += 28
            for line in lines:
                color = WHITE
                if "shoulder_symmetry" in line:
                    color = YELLOW
                elif "computed" in line:
                    color = ORANGE
                elif "threshold" in line:
                    color = MAGENTA
                elif "L_shoulder" in line:
                    color = GREEN
                elif "R_shoulder" in line:
                    color = BLUE
                cv2.putText(display, line, (panel_x + 10, cy),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
                cy += line_h

            # ── Legend ──
            lx = w - 280
            ly = h - 80
            cv2.rectangle(display, (lx, ly), (lx + 265, ly + 65), (15, 15, 25), -1)
            cv2.rectangle(display, (lx, ly), (lx + 265, ly + 65), (55, 55, 75), 1)
            legend = [
                (GREEN, "Left shoulder"),
                (BLUE, "Right shoulder"),
                (ORANGE, "Shoulder line"),
            ]
            for i, (c, t) in enumerate(legend):
                yy = ly + 18 + i * 18
                cv2.line(display, (lx + 8, yy), (lx + 28, yy), c, 3)
                cv2.putText(display, t, (lx + 32, yy + 4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, WHITE, 1)

        else:
            cv2.putText(display, "No person detected",
                        (w // 2 - 120, h // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.8, GRAY, 2)

        cv2.imshow("Shoulder Symmetry Diagnostic - Q quit, S save", display)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key == ord("s"):
            fname = f"debug_shoulder_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            fpath = str(SCREENSHOT_DIR / fname)
            cv2.imwrite(fpath, display)
            screenshot_count += 1
            print(f"Saved: {fpath}")

    cap.release()
    cv2.destroyAllWindows()
    print(f"\nScreenshots saved: {screenshot_count}")


if __name__ == "__main__":
    main()
