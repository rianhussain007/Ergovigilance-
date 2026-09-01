"""Extract COCO_17 keypoints from factory training videos using YOLOv8-pose.

Processes all .mp4 videos in data/datasets/diverse_training/ and extracts:
1. Frames at configurable intervals
2. COCO_17 keypoints for each detected person
3. Task labels from the video filename/path
4. Saves as JSON files compatible with the training pipeline

Usage:
    python -m yolo_cloud.training.extract_video_keypoints
    python -m yolo_cloud.training.extract_video_keypoints --sample-rate 1.0 --model yolov8s-pose.pt
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# Task label mapping from video filenames/path
TASK_LABELS = {
    # HuggingFace videos - assembly/manipulation tasks
    "cardboard": "Assembly Work",
    "manipulation": "Assembly Work",
    "assembly": "Assembly Work",
    "plastic": "Assembly Work",
    "plush": "Assembly Work",
    "screw": "Assembly Work",
    "defect": "Inspection",
    "testing": "Inspection",
    # YouTube videos - ergonomic tasks
    "lifting": "Lifting / Picking",
    "ergonomic": "Assembly Work",
    "workplace": "Assembly Work",
    "manual": "Lifting / Picking",
    "handling": "Lifting / Picking",
    "seated": "Seated Work",
    "sitting": "Seated Work",
    "walking": "Walking / Moving",
    "reaching": "Reaching",
    "standing": "Neutral Standing",
}


def _guess_task_from_path(video_path: Path) -> str:
    """Infer task label from video path components."""
    parts = (video_path.parent.name + " " + video_path.stem).lower()
    for keyword, task in TASK_LABELS.items():
        if keyword in parts:
            return task
    return "Unknown"


def extract_keypoints_from_video(
    video_path: Path,
    output_dir: Path,
    model,
    sample_rate: float = 1.0,
    conf_threshold: float = 0.5,
    max_frames_per_video: int = 100,
) -> dict:
    """Extract keypoints from a single video file.
    
    Args:
        video_path: Path to the video file
        output_dir: Directory to save extracted keypoints
        model: YOLO model instance
        sample_rate: Frames to extract per second
        conf_threshold: Confidence threshold for pose detection
        max_frames_per_video: Maximum frames to process per video
    
    Returns:
        dict with extraction stats
    """
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return {"error": f"Cannot open {video_path}", "frames": 0}

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_interval = max(1, int(fps / sample_rate))
    task_label = _guess_task_from_path(video_path)

    video_name = video_path.stem
    extracted = 0
    detected = 0
    frame_idx = 0

    while extracted < max_frames_per_video:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % frame_interval == 0:
            # Run YOLOv8-pose inference
            results = model(
                frame,
                conf=conf_threshold,
                verbose=False,
            )

            if results and len(results) > 0 and results[0].keypoints is not None:
                kps = results[0].keypoints.data.cpu().numpy()
                boxes = results[0].boxes

                for person_idx in range(len(kps)):
                    person_kps = kps[person_idx]
                    conf = float(boxes[person_idx].conf) if boxes is not None else 0.0

                    # Convert to [x, y, confidence] format
                    keypoints = []
                    for kp in person_kps:
                        if len(kp) >= 3:
                            keypoints.append([float(kp[0]), float(kp[1]), float(kp[2])])
                        else:
                            keypoints.append([0.0, 0.0, 0.0])

                    # Save keypoint file
                    kp_filename = f"{video_name}_frame{frame_idx:06d}_person{person_idx}.json"
                    kp_path = output_dir / "keypoints" / kp_filename
                    kp_path.parent.mkdir(parents=True, exist_ok=True)

                    kp_data = {
                        "video": str(video_path.name),
                        "frame_idx": frame_idx,
                        "person_idx": person_idx,
                        "task": task_label,
                        "confidence": conf,
                        "keypoints": keypoints,
                        "source": "factory_video",
                        "timestamp_sec": frame_idx / fps,
                    }

                    with open(kp_path, "w") as f:
                        json.dump(kp_data, f, indent=2)

                    detected += 1

            extracted += 1

        frame_idx += 1

    cap.release()

    return {
        "video": video_path.name,
        "task": task_label,
        "total_frames": total_frames,
        "processed_frames": extracted,
        "detected_persons": detected,
    }


def main(
    videos_dir: Path = ROOT / "data" / "datasets" / "diverse_training",
    output_dir: Path = ROOT / "outputs" / "real_data",
    sample_rate: float = 0.5,
    model_name: str = "yolov8s-pose.pt",
    conf_threshold: float = 0.5,
    max_frames: int = 200,
) -> dict:
    """Extract keypoints from all factory training videos."""
    print(f"Extracting keypoints from factory videos...")
    print(f"  Videos dir: {videos_dir}")
    print(f"  Output dir: {output_dir}")
    print(f"  Sample rate: {sample_rate} fps")
    print(f"  Model: {model_name}")
    print()

    # Load YOLO model
    try:
        from ultralytics import YOLO
        model = YOLO(model_name)
        print(f"  Model loaded: {model_name}")
    except ImportError:
        print("ERROR: ultralytics not installed. Run: pip install ultralytics")
        return {"error": "ultralytics not installed"}
    except Exception as e:
        print(f"ERROR loading model: {e}")
        return {"error": str(e)}

    # Find all videos
    videos = sorted(videos_dir.rglob("*.mp4"))
    print(f"  Found {len(videos)} videos")
    print()

    # Process each video
    all_results = []
    total_detected = 0

    for video_path in videos:
        print(f"  Processing: {video_path.name}...", end=" ", flush=True)
        result = extract_keypoints_from_video(
            video_path=video_path,
            output_dir=output_dir,
            model=model,
            sample_rate=sample_rate,
            conf_threshold=conf_threshold,
            max_frames_per_video=max_frames,
        )
        all_results.append(result)
        total_detected += result.get("detected_persons", 0)

        status = "OK" if "error" not in result else f"ERROR: {result['error']}"
        print(f"{status} ({result.get('detected_persons', 0)} persons)")

    # Summary
    print()
    print("=" * 60)
    print(f"Extraction complete!")
    print(f"  Videos processed: {len(all_results)}")
    print(f"  Total keypoints: {total_detected}")
    print(f"  Output: {output_dir}/keypoints/")

    # Task distribution
    from collections import Counter
    task_counts = Counter(r.get("task", "Unknown") for r in all_results)
    print(f"  Tasks: {dict(task_counts)}")

    # Save extraction manifest
    manifest_path = output_dir / "extraction_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w") as f:
        json.dump({
            "videos_dir": str(videos_dir),
            "sample_rate": sample_rate,
            "model": model_name,
            "results": all_results,
            "total_keypoints": total_detected,
        }, f, indent=2)
    print(f"  Manifest: {manifest_path}")

    return {"total_keypoints": total_detected, "results": all_results}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Extract COCO_17 keypoints from factory videos")
    ap.add_argument("--videos-dir", type=Path,
                    default=ROOT / "data" / "datasets" / "diverse_training")
    ap.add_argument("--output-dir", type=Path,
                    default=ROOT / "outputs" / "real_data")
    ap.add_argument("--sample-rate", type=float, default=0.5,
                    help="Frames per second to extract (default: 0.5)")
    ap.add_argument("--model", default="yolov8s-pose.pt",
                    help="YOLOv8-pose model to use")
    ap.add_argument("--conf", type=float, default=0.5,
                    help="Confidence threshold")
    ap.add_argument("--max-frames", type=int, default=200,
                    help="Max frames per video")
    args = ap.parse_args()

    main(
        videos_dir=args.videos_dir,
        output_dir=args.output_dir,
        sample_rate=args.sample_rate,
        model_name=args.model,
        conf_threshold=args.conf,
        max_frames=args.max_frames,
    )
