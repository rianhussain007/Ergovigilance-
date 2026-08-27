#!/usr/bin/env python3
"""Extract training frames from diverse factory videos.

This script:
1. Scans all downloaded videos (HuggingFace + YouTube)
2. Extracts frames at 2 FPS (fast, sufficient for pose analysis)
3. Runs MediaPipe Pose Landmarker on each frame
4. Computes ergonomic features from landmarks
5. Saves frames + features as a training dataset CSV
6. Extracts sample frames for human labeling

Usage:
    python scripts/extract_training_frames.py --output data/diverse_training_data
"""

import argparse
import csv
import json
import os
import sys
from pathlib import Path

# Fix Windows encoding for unicode output
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import cv2
import numpy as np

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def get_landmark_array(landmarks, image_w, image_h):
    """Convert normalized landmarks to pixel coordinates."""
    return np.array([[lm.x * image_w, lm.y * image_h] for lm in landmarks])


def compute_distance(p1, p2):
    """Euclidean distance between two points."""
    return float(np.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2))


def compute_angle(p1, vertex, p2):
    """Angle at vertex between p1 and p2 (degrees)."""
    v1 = p1 - vertex
    v2 = p2 - vertex
    cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-8)
    return float(np.degrees(np.arccos(np.clip(cos_angle, -1.0, 1.0))))


def extract_features_from_landmarks(landmarks, w, h):
    """Extract ergonomic features from MediaPipe landmarks."""
    pts = get_landmark_array(landmarks, w, h)

    # Key landmarks
    nose = pts[0]
    left_shoulder = pts[11]
    right_shoulder = pts[12]
    left_elbow = pts[13]
    right_elbow = pts[14]
    left_wrist = pts[15]
    right_wrist = pts[16]
    left_hip = pts[23]
    right_hip = pts[24]
    left_knee = pts[25]
    right_knee = pts[26]
    left_ankle = pts[27]
    right_ankle = pts[28]

    mid_shoulder = (left_shoulder + right_shoulder) / 2
    mid_hip = (left_hip + right_hip) / 2

    # Neck flexion: angle from vertical at the neck
    neck_vertical = np.array([0, -1])  # up
    neck_vec = nose - mid_shoulder
    neck_angle = compute_angle(
        nose,
        mid_shoulder,
        mid_shoulder + neck_vertical * 100
    )
    neck_flexion = 180.0 - neck_angle

    # Trunk flexion: angle of trunk from vertical
    trunk_vec = mid_shoulder - mid_hip
    trunk_vertical = np.array([0, -1])
    trunk_angle = compute_angle(
        mid_shoulder,
        mid_hip,
        mid_hip + trunk_vertical * 100
    )
    trunk_flexion = 180.0 - trunk_angle

    # Shoulder elevation
    left_shoulder_elev = compute_angle(
        left_elbow,
        left_shoulder,
        left_shoulder + np.array([1, 0]) * 100
    )
    right_shoulder_elev = compute_angle(
        right_elbow,
        right_shoulder,
        right_shoulder + np.array([1, 0]) * 100
    )

    # Shoulder symmetry
    shoulder_symmetry = abs(left_shoulder[1] - right_shoulder[1])

    # Knee angle
    left_knee_angle = compute_angle(left_hip, left_knee, left_ankle)
    right_knee_angle = compute_angle(right_hip, right_knee, right_ankle)
    knee_angle = (left_knee_angle + right_knee_angle) / 2

    # Alignment deviation
    alignment_dev = compute_distance(mid_shoulder, mid_hip) * 0.05  # rough

    # Forward head posture
    forward_head = abs(nose[0] - mid_shoulder[0])

    # Head tilt
    head_tilt = abs(nose[0] - mid_shoulder[0])

    # Wrist deviation
    left_wrist_dev = abs(left_wrist[0] - left_elbow[0])
    right_wrist_dev = abs(right_wrist[0] - right_elbow[0])
    wrist_deviation = (left_wrist_dev + right_wrist_dev) / 2

    # Torso height (for scale normalization)
    torso_height = compute_distance(mid_shoulder, mid_hip)

    # Body visibility ratio
    lower_body_visible = all(
        not np.isnan(pts[i]).any()
        for i in [23, 24, 25, 26, 27, 28]
    )
    upper_body_visible = all(
        not np.isnan(pts[i]).any()
        for i in [11, 12, 13, 14, 15, 16]
    )
    body_visibility = (1.0 if lower_body_visible else 0.0) + \
                      (1.0 if upper_body_visible else 0.0)

    return {
        "neck_flexion": round(float(neck_flexion), 2),
        "trunk_flexion": round(float(trunk_flexion), 2),
        "left_shoulder_elev": round(float(left_shoulder_elev), 2),
        "right_shoulder_elev": round(float(right_shoulder_elev), 2),
        "shoulder_symmetry": round(float(shoulder_symmetry), 2),
        "alignment_deviation": round(float(alignment_dev), 2),
        "knee_angle": round(float(knee_angle), 2),
        "forward_head_posture": round(float(forward_head), 2),
        "head_tilt_angle": round(float(head_tilt), 2),
        "wrist_deviation_angle": round(float(wrist_deviation), 2),
        "stance_stability": 0.7 if lower_body_visible else 0.0,
        "weight_shift_offset": 5.0 if not lower_body_visible else round(
            abs(mid_hip[0] - mid_shoulder[0]) * 0.1, 2
        ),
        "torso_height": round(float(torso_height), 2),
        "body_visibility": round(float(body_visibility), 2),
        "lower_body_visible": lower_body_visible,
        "upper_body_visible": upper_body_visible,
    }


def infer_task_from_filename(filename):
    """Infer task class from video filename (rough heuristic for initial labels)."""
    fn = filename.lower()
    if "lift" in fn or "box" in fn or "carry" in fn:
        return "Lifting / Picking"
    elif "assembl" in fn or "screw" in fn or "part" in fn:
        return "Assembly Work"
    elif "inspect" in fn or "test" in fn or "defect" in fn:
        return "Inspection"
    elif "walk" in fn or "move" in fn or "transit" in fn:
        return "Walking / Moving"
    elif "reaching" in fn or "reach" in fn:
        return "Reaching"
    elif "seated" in fn or "sit" in fn:
        return "Seated Work"
    elif "standing" in fn or "station" in fn:
        return "Neutral Standing"
    elif "ergonomic" in fn or "design" in fn:
        return "Neutral Standing"  # generic
    else:
        return "Neutral Standing"  # default


def extract_frames_from_video(video_path, output_dir, sample_rate=0.5,
                               pose_model=None, source_name=""):
    """Extract frames from a video and compute features."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"  WARNING: Could not open {video_path}")
        return []

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0

    # Extract 1 frame per N seconds
    frame_interval = max(1, int(fps * sample_rate))

    print(f"  {video_path.name}: {duration:.1f}s, {fps:.0f}fps, "
          f"extracting every {frame_interval} frames")

    task_label = infer_task_from_filename(video_path.name)

    frames_data = []
    frame_idx = 0
    extracted = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % frame_interval == 0:
            h, w = frame.shape[:2]

            # Run pose estimation
            if pose_model is not None:
                try:
                    import mediapipe as mp
                    # Convert to RGB for MediaPipe
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                    result = pose_model.detect(mp_image)

                    if result.pose_landmarks and len(result.pose_landmarks) > 0:
                        landmarks = result.pose_landmarks[0]
                        features = extract_features_from_landmarks(landmarks, w, h)

                        # Save frame image
                        frame_name = f"{source_name}_frame_{frame_idx:06d}.jpg"
                        frame_path = output_dir / "frames" / frame_name
                        cv2.imwrite(str(frame_path), frame)

                        features["frame_name"] = frame_name
                        features["source_video"] = video_path.name
                        features["frame_idx"] = frame_idx
                        features["task_label"] = task_label
                        features["timestamp_sec"] = round(frame_idx / fps, 2)
                        frames_data.append(features)
                        extracted += 1
                except Exception as e:
                    pass  # Skip frames with errors
            else:
                # No pose model, just save the frame
                frame_name = f"{source_name}_frame_{frame_idx:06d}.jpg"
                frame_path = output_dir / "frames" / frame_name
                cv2.imwrite(str(frame_path), frame)

                # Create dummy features
                features = {k: 0.0 for k in [
                    "neck_flexion", "trunk_flexion",
                    "left_shoulder_elev", "right_shoulder_elev",
                    "shoulder_symmetry", "alignment_deviation",
                    "knee_angle", "forward_head_posture", "head_tilt_angle",
                    "wrist_deviation_angle", "stance_stability", "weight_shift_offset",
                    "torso_height", "body_visibility"
                ]}
                features["lower_body_visible"] = False
                features["upper_body_visible"] = True
                features["frame_name"] = frame_name
                features["source_video"] = video_path.name
                features["frame_idx"] = frame_idx
                features["task_label"] = task_label
                features["timestamp_sec"] = round(frame_idx / fps, 2)
                frames_data.append(features)
                extracted += 1

        frame_idx += 1

    cap.release()
    print(f"    Extracted {extracted} frames")
    return frames_data


def main():
    parser = argparse.ArgumentParser(description="Extract training frames from videos")
    parser.add_argument("--data-dir", default=str(ROOT / "data" / "datasets" / "diverse_training"),
                        help="Root directory containing huggingface/ and youtube/ subdirs")
    parser.add_argument("--output", default=str(ROOT / "data" / "diverse_training_data"),
                        help="Output directory for extracted frames and CSV")
    parser.add_argument("--sample-rate", type=float, default=1.0,
                        help="Extract 1 frame per N seconds (default: 1.0)")
    parser.add_argument("--max-videos", type=int, default=15,
                        help="Maximum number of videos to process")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    output_dir = Path(args.output)
    frames_dir = output_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    print(f"=== Extracting training frames ===")
    print(f"Data dir: {data_dir}")
    print(f"Output: {output_dir}")

    # Initialize MediaPipe Pose Landmarker
    print("\nLoading MediaPipe Pose Landmarker...")
    try:
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        # Find the model file
        model_path = ROOT / "models" / "pose_landmarker_heavy.task"
        if not model_path.exists():
            # Try downloading
            print("  Downloading pose_landmarker_heavy.task...")
            import urllib.request
            url = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/latest/pose_landmarker_heavy.task"
            urllib.request.urlretrieve(str(model_path), str(model_path))

        base_options = mp_python.BaseOptions(model_asset_path=str(model_path))
        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=0.3,
            min_pose_presence_confidence=0.3,
            min_tracking_confidence=0.3,
        )
        pose_model = vision.PoseLandmarker.create_from_options(options)
        print("  OK Pose Landmarker loaded")
    except Exception as e:
        print(f"  FAIL Could not load MediaPipe: {e}")
        print("  Continuing without pose estimation (frames only)")
        pose_model = None

    # Find all videos
    videos = []
    for subdir in ["huggingface", "youtube"]:
        sub = data_dir / subdir
        if sub.exists():
            for f in sorted(sub.glob("*.mp4")):
                videos.append(f)

    # Also check for videos in root data dir
    for f in sorted(data_dir.glob("*.mp4")):
        videos.append(f)

    print(f"\nFound {len(videos)} videos to process")
    if args.max_videos:
        videos = videos[:args.max_videos]
        print(f"Processing first {len(videos)} videos")

    # Process each video
    all_frames = []
    for i, video in enumerate(videos):
        source_name = f"src{i:02d}"
        print(f"\n[{i+1}/{len(videos)}] Processing {video.name}...")
        frames = extract_frames_from_video(
            video, output_dir,
            sample_rate=args.sample_rate,
            pose_model=pose_model,
            source_name=source_name,
        )
        all_frames.extend(frames)

    # Save CSV
    csv_path = output_dir / "training_data.csv"
    if all_frames:
        fieldnames = list(all_frames[0].keys())
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_frames)

    # Save metadata
    meta = {
        "total_frames": len(all_frames),
        "total_videos": len(videos),
        "video_sources": [str(v.name) for v in videos],
        "task_distribution": {},
        "source_distribution": {},
        "sample_rate": args.sample_rate,
    }

    for frame in all_frames:
        task = frame.get("task_label", "Unknown")
        source = frame.get("source_video", "Unknown")
        meta["task_distribution"][task] = meta["task_distribution"].get(task, 0) + 1
        meta["source_distribution"][source] = meta["source_distribution"].get(source, 0) + 1

    meta_path = output_dir / "metadata.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    # Summary
    print(f"\n=== Summary ===")
    print(f"Total frames extracted: {len(all_frames)}")
    print(f"CSV saved to: {csv_path}")
    print(f"Metadata saved to: {meta_path}")
    print(f"\nTask distribution:")
    for task, count in sorted(meta["task_distribution"].items()):
        print(f"  {task}: {count}")
    print(f"\nSource distribution:")
    for source, count in sorted(meta["source_distribution"].items()):
        print(f"  {source}: {count}")

    # Save sample frames for labeling
    sample_dir = output_dir / "sample_frames"
    sample_dir.mkdir(exist_ok=True)
    import shutil
    # Copy every 5th frame for quick labeling
    sample_frames = all_frames[::5] if len(all_frames) > 5 else all_frames
    for frame in sample_frames[:50]:  # Max 50 samples
        src = frames_dir / frame["frame_name"]
        if src.exists():
            shutil.copy2(str(src), str(sample_dir / frame["frame_name"]))

    print(f"\nSample frames for labeling: {sample_dir} ({len(sample_frames[:50])} frames)")
    print(f"\nNext steps:")
    print(f"  1. Run labeling tool: python scripts/label_tool.py --data {output_dir}/sample_frames")
    print(f"  2. Label the diverse frames (Assembly, Lifting, Walking, etc.)")
    print(f"  3. Retrain model: python scripts/train_upper_body_v2.py --data {csv_path}")


if __name__ == "__main__":
    main()
