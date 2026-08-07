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
    _midpoint,
    _safe_distance,
)

MODEL_PATH = str(ROOT / "models" / "pose_landmarker_lite.task")
SCREENSHOT_DIR = ROOT / "outputs" / "debug_neck"

GREEN = (60, 200, 60)
RED = (40, 40, 220)
BLUE = (220, 150, 40)
YELLOW = (40, 220, 220)
CYAN = (220, 220, 60)
MAGENTA = (220, 60, 180)
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

    print("=== Neck Flexion Diagnostic ===")
    print("Look straight ahead, then tilt/lower your head forward.")
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

            left_ear = kps[7][:2]
            right_ear = kps[8][:2]
            left_shoulder = kps[11][:2]
            right_shoulder = kps[12][:2]
            left_hip = kps[23][:2]
            right_hip = kps[24][:2]

            ear = _midpoint(left_ear, right_ear).astype(int)
            neck = _midpoint(left_shoulder, right_shoulder).astype(int)
            hip = _midpoint(left_hip, right_hip).astype(int)

            raw_neck = angle_between_three_points(ear, neck, hip)
            neck_flexion = abs(180.0 - raw_neck)

            # ── Draw points ──
            for pt, color, label, offset in [
                (ear, GREEN, "Ear (mid)", (-45, -15)),
                (neck, RED, "Neck (mid-shoulder)", (-75, -15)),
                (hip, BLUE, "Hip (mid)", (-45, 15)),
            ]:
                cv2.circle(display, tuple(pt), 8, color, -1, cv2.LINE_AA)
                cv2.circle(display, tuple(pt), 8, WHITE, 2, cv2.LINE_AA)
                lx, ly = pt[0] + offset[0], pt[1] + offset[1]
                cv2.putText(display, label, (lx, ly), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

            # ── Draw vectors ──
            cv2.arrowedLine(display, tuple(neck), tuple(ear), GREEN, 3, cv2.LINE_AA, tipLength=0.08)
            cv2.arrowedLine(display, tuple(neck), tuple(hip), BLUE, 3, cv2.LINE_AA, tipLength=0.08)

            # ── Angle arc at neck ──
            r = 60
            v1 = ear.astype(float) - neck.astype(float)
            v2 = hip.astype(float) - neck.astype(float)
            a1 = np.arctan2(v1[1], v1[0])
            a2 = np.arctan2(v2[1], v2[0])
            delta = a1 - a2
            if delta > np.pi:
                delta -= 2 * np.pi
            elif delta < -np.pi:
                delta += 2 * np.pi
            start_a = a2
            end_a = a2 + delta
            n_pts = max(2, int(abs(np.degrees(delta)) / 2))
            pts = []
            for i in range(n_pts + 1):
                t = start_a + (end_a - start_a) * i / max(n_pts, 1)
                px = int(neck[0] + r * np.cos(t))
                py = int(neck[1] + r * np.sin(t))
                pts.append((px, py))
            if len(pts) > 1:
                cv2.polylines(display, [np.array(pts)], False, YELLOW, 2, cv2.LINE_AA)
                mid_angle = start_a + delta / 2
                label_x = int(neck[0] + (r + 18) * np.cos(mid_angle))
                label_y = int(neck[1] + (r + 18) * np.sin(mid_angle))
                cv2.putText(display, f"{raw_neck:.1f}deg", (label_x - 20, label_y + 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, YELLOW, 2)

            # ── Overlay panel ──
            panel_x, panel_y = 15, 15
            line_h = 24
            lines = [
                f"neck_flexion (reported): {features.get('neck_flexion', 0):.1f} deg",
                f"raw angle (ear-neck-hip): {raw_neck:.1f} deg",
                f"neck_flexion = |180 - raw|: {neck_flexion:.1f} deg",
                f"",
                f"ear:     ({ear[0]:4d}, {ear[1]:4d})",
                f"neck:    ({neck[0]:4d}, {neck[1]:4d})",
                f"hip:     ({hip[0]:4d}, {hip[1]:4d})",
                f"",
                f"thresholds: LOW <=10  MED 10-30  HIGH >30",
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
            cv2.putText(display, "NECK FLEXION DIAGNOSTIC", (panel_x + 10, cy),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, CYAN, 2)
            cy += 28
            for line in lines:
                color = WHITE
                if "neck_flexion" in line or "raw" in line:
                    color = YELLOW
                elif "ear:" in line:
                    color = GREEN
                elif "neck:" in line:
                    color = RED
                elif "hip:" in line:
                    color = BLUE
                elif "threshold" in line:
                    color = MAGENTA
                cv2.putText(display, line, (panel_x + 10, cy),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
                cy += line_h

            # ── Legend ──
            lx = w - 260
            ly = h - 80
            cv2.rectangle(display, (lx, ly), (lx + 245, ly + 65), (15, 15, 25), -1)
            cv2.rectangle(display, (lx, ly), (lx + 245, ly + 65), (55, 55, 75), 1)
            legend = [
                (GREEN, "neck -> ear"),
                (BLUE, "neck -> hip"),
                (YELLOW, f"angle at neck = {raw_neck:.1f} deg"),
            ]
            for i, (c, t) in enumerate(legend):
                yy = ly + 18 + i * 18
                cv2.line(display, (lx + 8, yy), (lx + 28, yy), c, 3)
                cv2.putText(display, t, (lx + 32, yy + 4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, WHITE, 1)

        else:
            cv2.putText(display, "No person detected",
                        (w // 2 - 120, h // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.8, GRAY, 2)

        cv2.imshow("Neck Flexion Diagnostic - Q quit, S save", display)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key == ord("s"):
            fname = f"debug_neck_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            fpath = str(SCREENSHOT_DIR / fname)
            cv2.imwrite(fpath, display)
            screenshot_count += 1
            print(f"Saved: {fpath}")

    cap.release()
    cv2.destroyAllWindows()
    print(f"\nScreenshots saved: {screenshot_count}")


if __name__ == "__main__":
    main()
