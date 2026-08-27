"""Quick extraction from YouTube videos."""
import sys
import csv
import json
from pathlib import Path
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision


def extract_features(landmarks, w, h):
    pts = np.array([[lm.x * w, lm.y * h] for lm in landmarks])

    def dist(a, b):
        return float(np.sqrt((pts[a][0]-pts[b][0])**2 + (pts[a][1]-pts[b][1])**2))

    def angle(a, v, b):
        p_a = pts[a] if isinstance(a, int) else np.array(a, dtype=float)
        p_v = pts[v] if isinstance(v, int) else np.array(v, dtype=float)
        p_b = pts[b] if isinstance(b, int) else np.array(b, dtype=float)
        v1 = p_a - p_v
        v2 = p_b - p_v
        cos_a = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-8)
        return float(np.degrees(np.arccos(np.clip(cos_a, -1, 1))))

    mid_sh = (pts[11] + pts[12]) / 2
    mid_hip = (pts[23] + pts[24]) / 2

    neck_flexion = 180.0 - angle(0, 11, 11 + np.array([0, -100]))
    trunk_flexion = 180.0 - angle(11, 23, 23 + np.array([0, -100]))
    ls_elev = angle(13, 11, 11 + np.array([100, 0]))
    rs_elev = angle(14, 12, 12 + np.array([100, 0]))
    knee = (angle(23, 25, 27) + angle(24, 26, 28)) / 2

    lower_ok = all(not np.isnan(pts[i]).any() for i in [23,24,25,26,27,28])
    upper_ok = all(not np.isnan(pts[i]).any() for i in [11,12,13,14,15,16])

    return {
        "neck_flexion": round(neck_flexion, 2),
        "trunk_flexion": round(trunk_flexion, 2),
        "left_shoulder_elev": round(ls_elev, 2),
        "right_shoulder_elev": round(rs_elev, 2),
        "shoulder_symmetry": round(abs(pts[11][1] - pts[12][1]), 2),
        "alignment_deviation": round(dist(1, 23) * 0.05, 2),
        "knee_angle": round(knee, 2),
        "forward_head_posture": round(abs(pts[0][0] - mid_sh[0]), 2),
        "head_tilt_angle": round(abs(pts[0][0] - mid_sh[0]), 2),
        "wrist_deviation_angle": round((abs(pts[15][0]-pts[13][0]) + abs(pts[16][0]-pts[14][0]))/2, 2),
        "stance_stability": 0.7 if lower_ok else 0.0,
        "weight_shift_offset": round(abs(mid_hip[0] - mid_sh[0]) * 0.1, 2) if lower_ok else 5.0,
        "lower_body_visible": lower_ok,
        "upper_body_visible": upper_ok,
        "body_visibility": (1.0 if lower_ok else 0.0) + (1.0 if upper_ok else 0.0),
    }


def infer_task(name):
    n = name.lower()
    if "lift" in n or "box" in n or "carry" in n: return "Lifting / Picking"
    if "assembl" in n or "screw" in n: return "Assembly Work"
    if "inspect" in n or "test" in n or "defect" in n: return "Inspection"
    if "walk" in n or "move" in n: return "Walking / Moving"
    if "reach" in n: return "Reaching"
    if "seated" in n or "sit" in n: return "Seated Work"
    return "Neutral Standing"


def main():
    yt_dir = ROOT / "data" / "datasets" / "diverse_training" / "youtube"
    out = ROOT / "data" / "diverse_training_data"
    frames_dir = out / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    print("Loading pose model...")
    mp_model = ROOT / "models" / "pose_landmarker_lite.task"
    base_options = mp_python.BaseOptions(model_asset_path=str(mp_model))
    options = vision.PoseLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=0.3,
        min_pose_presence_confidence=0.3,
        min_tracking_confidence=0.3,
    )
    model = vision.PoseLandmarker.create_from_options(options)
    print("Model loaded")

    all_frames = []
    videos = sorted(yt_dir.glob("*.mp4"))
    for i, vid in enumerate(videos):
        try:
            print(f"[{i+1}/{len(videos)}] {vid.name[:50]}...", end=" ", flush=True)
        except UnicodeEncodeError:
            print(f"[{i+1}/{len(videos)}] video_{i}...", end=" ", flush=True)
        cap = cv2.VideoCapture(str(vid))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        interval = max(1, int(fps * 2.0))
        task = infer_task(vid.name)
        count = 0
        fidx = 0
        # Create fresh model per video to avoid timestamp issues
        model = vision.PoseLandmarker.create_from_options(options)
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret: break
            if fidx % interval == 0:
                h, w = frame.shape[:2]
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                ts_ms = int(fidx / fps * 1000)
                result = model.detect_for_video(mp_img, ts_ms)
                if result.pose_landmarks and len(result.pose_landmarks) > 0:
                    feats = extract_features(result.pose_landmarks[0], w, h)
                    fn = f"yt{i:02d}_{fidx:06d}.jpg"
                    cv2.imwrite(str(frames_dir / fn), frame)
                    feats["frame_name"] = fn
                    feats["source_video"] = vid.name
                    feats["frame_idx"] = fidx
                    feats["task_label"] = task
                    feats["timestamp_sec"] = round(fidx / fps, 2)
                    all_frames.append(feats)
                    count += 1
            fidx += 1
        cap.release()
        model.close()
        print(f"{count} frames")

    # Save
    csv_path = out / "training_data.csv"
    if all_frames:
        with open(csv_path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(all_frames[0].keys()))
            w.writeheader()
            w.writerows(all_frames)

    tasks = {}
    for fr in all_frames:
        t = fr["task_label"]
        tasks[t] = tasks.get(t, 0) + 1

    print(f"\nTotal: {len(all_frames)} frames")
    print("Task distribution:")
    for t, c in sorted(tasks.items()):
        print(f"  {t}: {c}")

    # Copy sample frames for labeling
    import shutil
    sample_dir = out / "sample_frames"
    sample_dir.mkdir(exist_ok=True)
    for fr in all_frames[::3][:80]:
        src = frames_dir / fr["frame_name"]
        if src.exists():
            shutil.copy2(str(src), str(sample_dir / fr["frame_name"]))
    print(f"\nSample frames: {sample_dir} ({min(80, len(all_frames))} frames)")
    print(f"CSV: {csv_path}")


if __name__ == "__main__":
    main()
