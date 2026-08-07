from __future__ import annotations

import sys
import time
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python import vision

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.features import (
    extract_features_from_keypoints,
    mediapipe_landmarks_to_keypoints,
    _midpoint,
    _safe_distance,
)

MODEL_PATH = str(ROOT / "models" / "pose_landmarker_lite.task")


def main() -> None:
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: Could not open webcam.")
        return
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    options = vision.PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=MODEL_PATH),
        running_mode=vision.RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    pose_landmarker = vision.PoseLandmarker.create_from_options(options)

    timestamp_ms = 0
    frames_captured = 0

    print("=== Compression Analysis ===")
    print("Slowly transition from upright to deep forward bend.")
    print("Press Q to quit after ~10 seconds of data.")
    print()

    all_data: list[dict] = []

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

        if result.pose_landmarks:
            landmarks = result.pose_landmarks[0]
            h_f, w_f = frame.shape[:2]
            kps = mediapipe_landmarks_to_keypoints(landmarks, w_f, h_f)
            features, _unavail = extract_features_from_keypoints(kps)

            ls = kps[11][:2]
            rs = kps[12][:2]
            lh = kps[23][:2]
            rh = kps[24][:2]
            le = kps[13][:2]
            re_k = kps[14][:2]

            neck = _midpoint(ls, rs)
            hip = _midpoint(lh, rh)
            shoulder_width = _safe_distance(ls, rs)
            torso_len = _safe_distance(neck, hip, default=shoulder_width)

            raw_shoulder_width = np.linalg.norm(np.array(ls) - np.array(rs))
            raw_torso_len = np.linalg.norm(np.array(neck) - np.array(hip))

            compression = raw_torso_len / raw_shoulder_width if raw_shoulder_width > 1e-9 else 0.0

            neck_x, neck_y = neck[0], neck[1]
            hip_x, hip_y = hip[0], hip[1]

            rsh_x, rsh_y = rs[0], rs[1]
            lsh_x, lsh_y = ls[0], ls[1]
            shoulder_dx = rsh_x - lsh_x
            shoulder_dy = rsh_y - lsh_y

            trunk_flexion = features.get("trunk_flexion", 0.0)

            record = {
                "trunk_flexion": trunk_flexion,
                "compression": compression,
                "torso_len_px": raw_torso_len,
                "shoulder_width_px": raw_shoulder_width,
                "neck_y": neck_y,
                "neck_x": neck_x,
                "hip_y": hip_y,
                "shoulder_dx": shoulder_dx,
                "shoulder_dy": shoulder_dy,
            }
            all_data.append(record)
            frames_captured += 1

            # ── Live display ──
            info_lines = [
                f"Frame: {frames_captured}",
                f"trunk_flexion: {trunk_flexion:6.1f} deg",
                f"compression:   {compression:6.3f}  (torso / shoulder)",
                f"torso_len:     {raw_torso_len:6.0f} px",
                f"shoulder_w:    {raw_shoulder_width:6.0f} px",
                f"shoulder_dx:   {shoulder_dx:6.0f}",
                f"shoulder_dy:   {shoulder_dy:6.0f}",
            ]
            for i, line in enumerate(info_lines):
                cv2.putText(display, line, (15, 30 + i * 26),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 220), 1)

            # Color skeleton segments
            pts = [
                (int(ls[0]), int(ls[1])),
                (int(rs[0]), int(rs[1])),
                (int(lh[0]), int(lh[1])),
                (int(rh[0]), int(rh[1])),
                (int(neck[0]), int(neck[1])),
                (int(hip[0]), int(hip[1])),
            ]
            cv2.line(display, pts[0], pts[1], (60, 200, 60), 3)
            cv2.line(display, pts[4], pts[5], (220, 150, 40), 3)
            for pt in pts:
                cv2.circle(display, pt, 6, (240, 240, 240), -1)

            cv2.putText(display, f"frames: {frames_captured}", (15, h_f - 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (120, 120, 140), 1)

        cv2.imshow("Compression Analysis - Q to quit", display)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()

    # ── Analysis ──
    print(f"\nCaptured {len(all_data)} frames.\n")

    if len(all_data) < 5:
        print("Not enough data. Run again and transition through postures.")
        return

    trunk_vals = np.array([r["trunk_flexion"] for r in all_data])
    comp_vals = np.array([r["compression"] for r in all_data])
    torso_vals = np.array([r["torso_len_px"] for r in all_data])
    shoulder_vals = np.array([r["shoulder_width_px"] for r in all_data])
    neck_y_vals = np.array([r["neck_y"] for r in all_data])
    shoulder_dx_vals = np.array([r["shoulder_dx"] for r in all_data])
    shoulder_dy_vals = np.array([r["shoulder_dy"] for r in all_data])

    def r2(x, y):
        return np.corrcoef(x, y)[0, 1] ** 2

    print("=" * 60)
    print("CORRELATION ANALYSIS")
    print("=" * 60)
    print(f"trunk_flexion × compression:        r2 = {r2(trunk_vals, comp_vals):.4f}  (r = {np.corrcoef(trunk_vals, comp_vals)[0,1]:.4f})")
    print(f"trunk_flexion × torso_len:          r2 = {r2(trunk_vals, torso_vals):.4f}  (r = {np.corrcoef(trunk_vals, torso_vals)[0,1]:.4f})")
    print(f"trunk_flexion × shoulder_width:     r2 = {r2(trunk_vals, shoulder_vals):.4f}  (r = {np.corrcoef(trunk_vals, shoulder_vals)[0,1]:.4f})")
    print(f"trunk_flexion × shoulder_dx:        r2 = {r2(trunk_vals, shoulder_dx_vals):.4f}  (r = {np.corrcoef(trunk_vals, shoulder_dx_vals)[0,1]:.4f})")
    print(f"trunk_flexion × shoulder_dy:        r2 = {r2(trunk_vals, shoulder_dy_vals):.4f}  (r = {np.corrcoef(trunk_vals, shoulder_dy_vals)[0,1]:.4f})")
    print(f"compression × shoulder_width:       r2 = {r2(comp_vals, shoulder_vals):.4f}  (r = {np.corrcoef(comp_vals, shoulder_vals)[0,1]:.4f})")
    print(f"compression × torso_len:            r2 = {r2(comp_vals, torso_vals):.4f}  (r = {np.corrcoef(comp_vals, torso_vals)[0,1]:.4f})")

    print()
    print("=" * 60)
    print("RANGE ANALYSIS")
    print("=" * 60)

    bins = [0, 15, 30, 45, 60, 90]
    labels = ["0-15", "15-30", "30-45", "45-60", "60+"]
    print(f"{'trunk range':<15} {'count':>6} {'avg comp':>10} {'avg torso':>10} {'avg shldr':>10} {'avg sh_dx':>10} {'avg sh_dy':>10}")
    print("-" * 75)
    for lo, hi, lbl in zip(bins[:-1], bins[1:], labels):
        mask = (trunk_vals >= lo) & (trunk_vals < hi)
        n = mask.sum()
        if n == 0:
            continue
        ac = comp_vals[mask].mean()
        at = torso_vals[mask].mean()
        as_ = shoulder_vals[mask].mean()
        as_dx = shoulder_dx_vals[mask].mean()
        as_dy = shoulder_dy_vals[mask].mean()
        print(f"{lbl:<15} {n:6d} {ac:10.3f} {at:10.1f} {as_:10.1f} {as_dx:10.1f} {as_dy:10.1f}")

    # Additional check: detect rotation vs forward bend
    print()
    print("=" * 60)
    print("ROTATION DETECTION ANALYSIS")
    print("=" * 60)
    print("If shoulder_dy changes with trunk_flexion, that indicates")
    print("shoulder asymmetry due to rotation during bending.")
    print(f"corr(trunk_flexion, shoulder_dy) = {np.corrcoef(trunk_vals, shoulder_dy_vals)[0,1]:.4f}")
    print(f"corr(trunk_flexion, shoulder_dx) = {np.corrcoef(trunk_vals, shoulder_dx_vals)[0,1]:.4f}")

    # Summary
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  trunk_flexion range:  {trunk_vals.min():.1f}° to {trunk_vals.max():.1f}°")
    print(f"  compression range:    {comp_vals.min():.3f} to {comp_vals.max():.3f}")
    print(f"  torso_len range:     {torso_vals.min():.0f} to {torso_vals.max():.0f} px")
    print(f"  shoulder_width range: {shoulder_vals.min():.0f} to {shoulder_vals.max():.0f} px")


if __name__ == "__main__":
    main()
