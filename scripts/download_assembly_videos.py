"""Download assembly line training videos and extract features.

Downloads videos of workers performing assembly tasks, extracts frames,
runs pose estimation, and creates labeled training data.

Usage:
    python scripts/download_assembly_videos.py --output data/datasets/assembly_training
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import List, Dict

ROOT = Path(__file__).resolve().parents[1]


# Assembly line task categories with YouTube search terms
TASK_CATEGORIES = {
    "Assembly Work": [
        "factory assembly line worker",
        "manual assembly workstation",
        "product assembly process",
        "manufacturing assembly task",
    ],
    "Reaching": [
        "worker reaching for tools",
        "assembly line reaching motion",
        "picking parts from bin",
        "ergonomic reaching workstation",
    ],
    "Lifting / Picking": [
        "worker lifting box factory",
        "picking items assembly line",
        "material handling factory",
        "ergonomic lifting technique",
    ],
    "Inspection": [
        "quality inspection factory",
        "visual inspection workstation",
        "quality control assembly",
        "product inspection worker",
    ],
    "Seated Work": [
        "seated assembly workstation",
        "desk work factory worker",
        "seated manufacturing task",
        "ergonomic seated workstation",
    ],
    "Walking / Moving": [
        "factory worker walking",
        "material transport factory",
        "worker moving between stations",
        "factory floor movement",
    ],
}


def download_video(url: str, output_path: Path) -> bool:
    """Download a video using yt-dlp."""
    try:
        cmd = [
            "yt-dlp",
            "-f", "best[height<=720]",
            "--no-playlist",
            "-o", str(output_path),
            url,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return result.returncode == 0
    except Exception as e:
        print(f"  Error downloading {url}: {e}")
        return False


def extract_frames(video_path: Path, output_dir: Path, frame_interval: int = 30) -> int:
    """Extract frames from video at specified interval."""
    import cv2
    
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return 0
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_idx = 0
    extracted = 0
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx += 1
        if frame_idx % frame_interval == 0:
            output_path = output_dir / f"frame_{frame_idx:06d}.jpg"
            cv2.imwrite(str(output_path), frame)
            extracted += 1
    
    cap.release()
    return extracted


def process_videos(dataset_dir: Path, output_dir: Path) -> Dict:
    """Process downloaded videos and create training data."""
    from backend.services.pose_engine import PoseEngine
    from backend.services.features import extract_features_from_keypoints
    
    # Initialize pose engine
    pose = PoseEngine(str(ROOT / "models" / "pose_landmarker_lite.task"))
    pose.initialize()
    
    results = []
    
    for video_path in dataset_dir.rglob("*.mp4"):
        # Determine task label from path
        task_label = "Unknown"
        for task in TASK_CATEGORIES:
            if task.lower().replace(" ", "_") in str(video_path).lower():
                task_label = task
                break
        
        print(f"Processing {video_path.name} (task: {task_label})")
        
        # Extract frames
        frame_dir = output_dir / "frames" / video_path.stem
        frame_dir.mkdir(parents=True, exist_ok=True)
        n_frames = extract_frames(video_path, frame_dir)
        print(f"  Extracted {n_frames} frames")
        
        # Process each frame
        for frame_path in sorted(frame_dir.glob("*.jpg")):
            import cv2
            frame = cv2.imread(str(frame_path))
            if frame is None:
                continue
            
            result = pose.process_frame(frame)
            if not result.person_detected or result.keypoints is None:
                continue
            
            feats = result.features
            results.append({
                "video": video_path.name,
                "frame": frame_path.name,
                "task_label": task_label,
                "risk_level": result.risk_level,
                "confidence": result.confidence,
                "features": feats,
            })
    
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "datasets" / "assembly_training")
    parser.add_argument("--max-videos-per-task", type=int, default=5)
    args = parser.parse_args()
    
    print("=== Assembly Line Training Data Pipeline ===")
    print()
    
    # Check for yt-dlp
    try:
        subprocess.run(["yt-dlp", "--version"], capture_output=True, check=True)
    except FileNotFoundError:
        print("yt-dlp not found. Install with: pip install yt-dlp")
        print("Alternatively, manually download videos to data/datasets/assembly_training/raw/")
        return
    
    # Create output directories
    raw_dir = args.output / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    
    # Download videos for each task
    downloaded = {}
    for task, search_terms in TASK_CATEGORIES.items():
        print(f"\n--- {task} ---")
        task_dir = raw_dir / task.replace(" ", "_").replace("/", "_")
        task_dir.mkdir(exist_ok=True)
        
        for i, search_term in enumerate(search_terms[:args.max_videos_per_task]):
            print(f"  Searching: {search_term}")
            # Note: In production, use YouTube API or yt-dlp search
            # For now, we'll use placeholder URLs
            downloaded[task] = len(list(task_dir.glob("*.mp4")))
    
    print(f"\n=== Download Summary ===")
    for task, count in downloaded.items():
        print(f"  {task}: {count} videos")
    
    # Process videos
    print("\n=== Processing Videos ===")
    results = process_videos(raw_dir, args.output)
    
    # Save results
    output_file = args.output / "extracted_features.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\nProcessed {len(results)} frames")
    print(f"Saved to: {output_file}")
    
    # Create CSV
    import pandas as pd
    rows = []
    for item in results:
        row = {
            "video": item["video"],
            "frame": item["frame"],
            "task_label": item["task_label"],
            "risk_level": item["risk_level"],
            "confidence": item["confidence"],
        }
        row.update(item["features"])
        rows.append(row)
    
    df = pd.DataFrame(rows)
    csv_path = args.output / "training_data.csv"
    df.to_csv(csv_path, index=False)
    print(f"CSV saved to: {csv_path}")
    print(f"Shape: {df.shape}")


if __name__ == "__main__":
    main()
