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
    angle_between_three_points,
    extract_features_from_keypoints,
    mediapipe_landmarks_to_keypoints,
)

MODEL_PATH = str(ROOT / "models" / "pose_landmarker_lite.task")
SCREENSHOT_DIR = ROOT / "outputs" / "debug_knee"

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

    print("=== Knee Angle Diagnostic ===")
    print("Stand up (knee ~180 deg), then sit (knee ~90 deg).")
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

            left_hip = np.array(kps[23][:2])
            right_hip = np.array(kps[24][:2])
            left_knee = np.array(kps[25][:2])
            right_knee = np.array(kps[26][:2])
            left_ankle = np.array(kps[27][:2])
            right_ankle = np.array(kps[28][:2])

            l_angle = angle_between_three_points(left_hip, left_knee, left_ankle)
            r_angle = angle_between_three_points(right_hip, right_knee, right_ankle)
            avg_angle = (l_angle + r_angle) / 2.0

            # ── Draw leg points ──
            leg_data = [
                (left_hip, "hip L", GREEN),
                (right_hip, "hip R", BLUE),
                (left_knee, "knee L", GREEN),
                (right_knee, "knee R", BLUE),
                (left_ankle, "ankle L", GREEN),
                (right_ankle, "ankle R", BLUE),
            ]
            for pt, label, color in leg_data:
                pt_int = tuple(pt.astype(int))
                cv2.circle(display, pt_int, 7, color, -1, cv2.LINE_AA)
                cv2.circle(display, pt_int, 7, WHITE, 2, cv2.LINE_AA)
                cv2.putText(display, label, (pt_int[0] + 8, pt_int[1] + 4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

            # ── Draw leg segments ──
            for side, color in [("L", GREEN), ("R", BLUE)]:
                hip = left_hip if side == "L" else right_hip
                knee = left_knee if side == "L" else right_knee
                ankle = left_ankle if side == "L" else right_ankle
                cv2.line(display, tuple(hip.astype(int)), tuple(knee.astype(int)),
                         color, 3, cv2.LINE_AA)
                cv2.line(display, tuple(knee.astype(int)), tuple(ankle.astype(int)),
                         color, 3, cv2.LINE_AA)

            # ── Angle arcs ──
            for side, color, knee_pt, hip_pt, ankle_pt, angle_val in [
                ("L", GREEN, left_knee, left_hip, left_ankle, l_angle),
                ("R", BLUE, right_knee, right_hip, right_ankle, r_angle),
            ]:
                r = 45
                v1 = hip_pt.astype(float) - knee_pt.astype(float)
                v2 = ankle_pt.astype(float) - knee_pt.astype(float)
                a1 = np.arctan2(v1[1], v1[0])
                a2 = np.arctan2(v2[1], v2[0])
                delta = a1 - a2
                if delta > np.pi:
                    delta -= 2 * np.pi
                elif delta < -np.pi:
                    delta += 2 * np.pi
                n_pts = max(2, int(abs(np.degrees(delta)) / 2))
                pts = []
                for i in range(n_pts + 1):
                    t = a2 + (delta) * i / max(n_pts, 1)
                    px = int(knee_pt[0] + r * np.cos(t))
                    py = int(knee_pt[1] + r * np.sin(t))
                    pts.append((px, py))
                if len(pts) > 1:
                    cv2.polylines(display, [np.array(pts)], False, YELLOW, 2, cv2.LINE_AA)
                    mid_t = a2 + delta / 2
                    lx = int(knee_pt[0] + (r + 15) * np.cos(mid_t))
                    ly = int(knee_pt[1] + (r + 15) * np.sin(mid_t))
                    cv2.putText(display, f"{angle_val:.0f}deg", (lx - 15, ly + 5),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, YELLOW, 2)

            # ── Panel ──
            panel_x, panel_y = 15, 15
            line_h = 24
            lines = [
                f"knee_angle (reported): {features.get('knee_angle', 0):.1f} deg",
                f"left knee:  {l_angle:.1f} deg",
                f"right knee: {r_angle:.1f} deg",
                f"avg (L+R)/2: {avg_angle:.1f} deg",
                f"",
                f"left_hip:    ({int(left_hip[0]):4d}, {int(left_hip[1]):4d})",
                f"left_knee:   ({int(left_knee[0]):4d}, {int(left_knee[1]):4d})",
                f"left_ankle:  ({int(left_ankle[0]):4d}, {int(left_ankle[1]):4d})",
                f"",
                f"thresholds: HIGH <100  MED 100-150  LOW >=150",
                f"",
                f"S: screenshot  |  Q: quit",
            ]
            panel_w = 460
            panel_h = len(lines) * line_h + 30
            overlay = display.copy()
            cv2.rectangle(overlay, (panel_x, panel_y),
                          (panel_x + panel_w, panel_y + panel_h), (15, 15, 25), -1)
            display = cv2.addWeighted(overlay, 0.9, display, 0.1, 0)
            cv2.rectangle(display, (panel_x, panel_y),
                          (panel_x + panel_w, panel_y + panel_h), (55, 55, 75), 1)

            cy = panel_y + 15
            cv2.putText(display, "KNEE ANGLE DIAGNOSTIC", (panel_x + 10, cy),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, CYAN, 2)
            cy += 28
            for line in lines:
                color = WHITE
                if "knee_angle" in line:
                    color = YELLOW
                elif "left knee" in line:
                    color = GREEN
                elif "right knee" in line:
                    color = BLUE
                elif "avg" in line:
                    color = ORANGE
                elif "threshold" in line:
                    color = MAGENTA
                elif "left_hip" in line:
                    color = GREEN
                elif "left_knee" in line:
                    color = GREEN
                elif "left_ankle" in line:
                    color = GREEN
                cv2.putText(display, line, (panel_x + 10, cy),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
                cy += line_h

            # ── Legend ──
            lx = w - 260
            ly = h - 80
            cv2.rectangle(display, (lx, ly), (lx + 245, ly + 65), (15, 15, 25), -1)
            cv2.rectangle(display, (lx, ly), (lx + 245, ly + 65), (55, 55, 75), 1)
            legend = [
                (GREEN, "Left leg"),
                (BLUE, "Right leg"),
                (YELLOW, "Knee angle"),
            ]
            for i, (c, t) in enumerate(legend):
                yy = ly + 18 + i * 18
                cv2.line(display, (lx + 8, yy), (lx + 28, yy), c, 3)
                cv2.putText(display, t, (lx + 32, yy + 4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, WHITE, 1)

        else:
            cv2.putText(display, "No person detected",
                        (w // 2 - 120, h // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.8, GRAY, 2)

        cv2.imshow("Knee Angle Diagnostic - Q quit, S save", display)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key == ord("s"):
            fname = f"debug_knee_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            fpath = str(SCREENSHOT_DIR / fname)
            cv2.imwrite(fpath, display)
            screenshot_count += 1
            print(f"Saved: {fpath}")

    cap.release()
    cv2.destroyAllWindows()
    print(f"\nScreenshots saved: {screenshot_count}")


if __name__ == "__main__":
    main()
