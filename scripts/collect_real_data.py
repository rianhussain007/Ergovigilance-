"""
Automated Data Collection Pipeline for Real Factory Footage

This script:
1. Extracts frames from video recordings at configurable intervals
2. Runs pose estimation (MediaPipe) on each frame
3. Extracts ergonomic features (17 biomechanical + 2 motion)
4. Saves frames for human labeling
5. Creates a structured dataset for model training

Usage:
    # Process a single video
    python scripts/collect_real_data.py --video path/to/video.mp4 --task "Assembly Work"
    
    # Process all recordings in a directory
    python scripts/collect_real_data.py --recordings-dir recordings/ --sample-every 30
    
    # Extract frames only (no pose estimation)
    python scripts/collect_real_data.py --video path/to/video.mp4 --extract-only --step 15
    
    # Create labeling template
    python scripts/collect_real_data.py --create-template --output outputs/real_data_labeling/

Output Structure:
    outputs/real_data/
    ├── frames/           # Extracted frames (JPEG)
    ├── features/         # Feature vectors (JSON per frame)
    ├── dataset.csv       # Combined dataset for training
    └── labeling/         # Templates for human labeling
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.features import FEATURE_COLUMNS, MEDIAPIPE_33, extract_features_from_keypoints

# Canonical task classes
TASK_CLASSES = [
    "Neutral Standing",
    "Assembly Work", 
    "Reaching",
    "Lifting / Picking",
    "Inspection",
    "Seated Work",
    "Walking / Moving",
]

MOTION_FEATURES = ["movement_velocity", "wrist_movement_velocity"]
ALL_FEATURES = [*FEATURE_COLUMNS, *MOTION_FEATURES]


@dataclass
class FrameData:
    """Data for a single extracted frame."""
    frame_idx: int
    timestamp_sec: float
    source_video: str
    task_label: str = "Unknown"
    risk_level: str = "Unknown"
    
    # Pose detection results
    person_detected: bool = False
    keypoints: Optional[np.ndarray] = None
    confidence: float = 0.0
    
    # Extracted features
    features: Dict[str, float] = field(default_factory=dict)
    unavailable_features: List[str] = field(default_factory=list)
    
    # Metadata
    frame_path: Optional[str] = None
    feature_path: Optional[str] = None


class DataCollector:
    """Collects and processes real factory footage for model training."""
    
    def __init__(
        self,
        output_dir: Path,
        model_path: Optional[Path] = None,
        sample_every: int = 30,  # Extract every Nth frame
        min_confidence: float = 0.5,
    ):
        self.output_dir = Path(output_dir)
        self.frames_dir = self.output_dir / "frames"
        self.features_dir = self.output_dir / "features"
        self.sample_every = sample_every
        self.min_confidence = min_confidence
        
        # Create directories
        self.frames_dir.mkdir(parents=True, exist_ok=True)
        self.features_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize pose engine (lazy load)
        self._pose_engine = None
        self._model_path = model_path or ROOT / "models" / "pose_landmarker_lite.task"
        
        # Statistics
        self.stats = {
            "total_frames": 0,
            "extracted_frames": 0,
            "person_detected": 0,
            "per_task": {task: 0 for task in TASK_CLASSES},
        }
    
    @property
    def pose_engine(self):
        """Lazy-load the pose engine."""
        if self._pose_engine is None:
            from backend.services.pose_engine import PoseEngine
            self._pose_engine = PoseEngine(str(self._model_path))
            self._pose_engine.initialize()
        return self._pose_engine
    
    def process_video(
        self,
        video_path: Path,
        task_label: str = "Unknown",
        start_frame: int = 0,
        end_frame: Optional[int] = None,
    ) -> List[FrameData]:
        """Process a single video file and extract frames + features."""
        print(f"\nProcessing: {video_path.name}")
        print(f"  Task: {task_label}")
        print(f"  Sample every: {self.sample_every} frames")
        
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            print(f"  ERROR: Could not open video {video_path}")
            return []
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        duration_sec = total_frames / fps
        
        if end_frame is None:
            end_frame = total_frames
        
        print(f"  Total frames: {total_frames}")
        print(f"  Duration: {duration_sec:.1f}s")
        print(f"  FPS: {fps:.1f}")
        
        extracted: List[FrameData] = []
        frame_idx = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            if frame_idx < start_frame:
                frame_idx += 1
                continue
            
            if frame_idx >= end_frame:
                break
            
            # Sample every Nth frame
            if frame_idx % self.sample_every == 0:
                frame_data = self._process_frame(
                    frame, frame_idx, fps, video_path.name, task_label
                )
                if frame_data.person_detected:
                    extracted.append(frame_data)
                    self.stats["person_detected"] += 1
                    self.stats["per_task"][task_label] = self.stats["per_task"].get(task_label, 0) + 1
            
            self.stats["total_frames"] += 1
            frame_idx += 1
        
        cap.release()
        
        print(f"  Extracted: {len(extracted)} frames with person detected")
        self.stats["extracted_frames"] += len(extracted)
        
        return extracted
    
    def _process_frame(
        self,
        frame: np.ndarray,
        frame_idx: int,
        fps: float,
        source_video: str,
        task_label: str,
    ) -> FrameData:
        """Process a single frame: detect pose, extract features."""
        # Run pose estimation
        result = self.pose_engine.process_frame(frame)
        
        frame_data = FrameData(
            frame_idx=frame_idx,
            timestamp_sec=frame_idx / fps,
            source_video=source_video,
            task_label=task_label,
            person_detected=result.person_detected if result else False,
            confidence=result.confidence if result else 0.0,
        )
        
        if not frame_data.person_detected:
            return frame_data
        
        # Save frame as JPEG
        frame_filename = f"{source_video.replace('.mp4', '')}_frame_{frame_idx:06d}.jpg"
        frame_path = self.frames_dir / frame_filename
        cv2.imwrite(str(frame_path), frame)
        frame_data.frame_path = str(frame_path.relative_to(self.output_dir))
        
        # Extract features
        if result and result.keypoints:
            features, unavailable, approximate = extract_features_from_keypoints(result.keypoints)
            
            # Add motion features
            features["movement_velocity"] = getattr(result, "movement_velocity", 0.0)
            features["wrist_movement_velocity"] = getattr(result, "wrist_movement_velocity", 0.0)
            
            frame_data.features = features
            frame_data.unavailable_features = unavailable
            
            # Save features as JSON
            feature_filename = frame_filename.replace(".jpg", ".json")
            feature_path = self.features_dir / feature_filename
            feature_data = {
                "frame_idx": frame_idx,
                "timestamp_sec": frame_idx / fps,
                "source_video": source_video,
                "task_label": task_label,
                "person_detected": True,
                "confidence": frame_data.confidence,
                "features": features,
                "unavailable_features": unavailable,
                "approximate_features": approximate,
                "keypoints_shape": [len(result.keypoints), len(result.keypoints[0])] if result.keypoints else [],
            }
            with open(feature_path, "w") as f:
                json.dump(feature_data, f, indent=2)
            frame_data.feature_path = str(feature_path.relative_to(self.output_dir))
        
        return frame_data
    
    def process_recordings_dir(
        self,
        recordings_dir: Path,
        task_labels: Optional[Dict[str, str]] = None,
    ) -> List[FrameData]:
        """Process all recordings in a directory.
        
        Args:
            recordings_dir: Directory containing video files or subdirectories
            task_labels: Optional mapping of filename patterns to task labels
        """
        if task_labels is None:
            task_labels = {}
        
        all_extracted: List[FrameData] = []
        
        # Find all video files
        video_files = list(recordings_dir.glob("**/*.mp4"))
        video_files.extend(recordings_dir.glob("**/*.avi"))
        video_files.extend(recordings_dir.glob("**/*.mov"))
        
        print(f"\nFound {len(video_files)} video files in {recordings_dir}")
        
        for video_path in sorted(video_files):
            # Determine task label from filename or mapping
            task_label = "Unknown"
            for pattern, label in task_labels.items():
                if pattern.lower() in video_path.name.lower():
                    task_label = label
                    break
            
            # Try to infer from directory structure
            if task_label == "Unknown":
                parent_name = video_path.parent.name.lower()
                for task in TASK_CLASSES:
                    if task.lower().replace(" ", "_") in parent_name or task.lower().replace(" / ", "_") in parent_name:
                        task_label = task
                        break
            
            extracted = self.process_video(video_path, task_label)
            all_extracted.extend(extracted)
        
        return all_extracted
    
    def create_dataset_csv(self, output_path: Optional[Path] = None) -> Path:
        """Create a CSV dataset from all extracted features."""
        if output_path is None:
            output_path = self.output_dir / "dataset.csv"
        
        # Collect all feature files
        feature_files = list(self.features_dir.glob("*.json"))
        
        if not feature_files:
            print("No feature files found. Run process_video() first.")
            return output_path
        
        # Write CSV
        with open(output_path, "w", newline="") as f:
            writer = csv.writer(f)
            
            # Header
            header = ["frame_id", "source_video", "timestamp_sec", "task_label"] + ALL_FEATURES + ["unavailable_count"]
            writer.writerow(header)
            
            # Rows
            for i, feature_file in enumerate(sorted(feature_files)):
                with open(feature_file) as f2:
                    data = json.load(f2)
                
                row = [
                    i,
                    data["source_video"],
                    data["timestamp_sec"],
                    data["task_label"],
                ]
                
                # Add features
                for feat in ALL_FEATURES:
                    val = data["features"].get(feat, 0.0)
                    row.append(val if val == val else "")  # NaN -> empty
                
                # Add unavailable count
                row.append(len(data.get("unavailable_features", [])))
                
                writer.writerow(row)
        
        print(f"\nCreated dataset CSV: {output_path}")
        print(f"  Total rows: {len(feature_files)}")
        
        return output_path
    
    def create_labeling_template(self, output_dir: Path) -> Path:
        """Create a labeling template for human review."""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Collect all frames
        frame_files = sorted(self.frames_dir.glob("*.jpg"))
        
        if not frame_files:
            print("No frames found. Run process_video() first.")
            return output_dir / "labeling_template.csv"
        
        # Create CSV template
        template_path = output_dir / "labeling_template.csv"
        with open(template_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "frame_id", "frame_path", "source_video", "timestamp_sec",
                "suggested_task", "confirmed_task", "risk_level", "rula_score",
                "notes"
            ])
            
            for i, frame_path in enumerate(frame_files):
                # Load feature data if available
                feature_path = self.features_dir / frame_path.name.replace(".jpg", ".json")
                suggested_task = "Unknown"
                if feature_path.exists():
                    with open(feature_path) as f2:
                        data = json.load(f2)
                    suggested_task = data.get("task_label", "Unknown")
                
                writer.writerow([
                    i,
                    str(frame_path.relative_to(output_dir.parent)),
                    "",  # source_video
                    "",  # timestamp_sec
                    suggested_task,
                    "",  # confirmed_task (to be filled by human)
                    "",  # risk_level
                    "",  # rula_score
                    "",  # notes
                ])
        
        print(f"\nCreated labeling template: {template_path}")
        print(f"  Total frames to label: {len(frame_files)}")
        print(f"  Open this CSV in Excel/Google Sheets to label")
        
        return template_path
    
    def print_stats(self):
        """Print collection statistics."""
        print("\n" + "="*60)
        print("DATA COLLECTION STATISTICS")
        print("="*60)
        print(f"Total frames processed: {self.stats['total_frames']}")
        print(f"Frames extracted: {self.stats['extracted_frames']}")
        print(f"Person detected: {self.stats['person_detected']}")
        print(f"\nPer task class:")
        for task, count in self.stats["per_task"].items():
            if count > 0:
                print(f"  {task}: {count}")
        print("="*60)


def main():
    parser = argparse.ArgumentParser(
        description="Collect real factory footage data for model training",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Process a single video
    python scripts/collect_real_data.py --video path/to/video.mp4 --task "Assembly Work"
    
    # Process all recordings
    python scripts/collect_real_data.py --recordings-dir recordings/ --sample-every 30
    
    # Create labeling template
    python scripts/collect_real_data.py --create-template --output outputs/real_data_labeling/
        """
    )
    
    parser.add_argument("--video", type=Path, help="Single video file to process")
    parser.add_argument("--task", type=str, default="Unknown", 
                       help="Task label for the video (e.g., 'Assembly Work')")
    parser.add_argument("--recordings-dir", type=Path, 
                       help="Directory containing video recordings")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs" / "real_data",
                       help="Output directory for extracted data")
    parser.add_argument("--sample-every", type=int, default=30,
                       help="Extract every Nth frame (default: 30)")
    parser.add_argument("--start-frame", type=int, default=0,
                       help="Start processing from this frame")
    parser.add_argument("--end-frame", type=int, default=None,
                       help="Stop processing at this frame")
    parser.add_argument("--create-template", action="store_true",
                       help="Create labeling template for human review")
    parser.add_argument("--create-dataset", action="store_true",
                       help="Create CSV dataset from extracted features")
    parser.add_argument("--model", type=Path, default=None,
                       help="Path to pose estimation model")
    
    args = parser.parse_args()
    
    # Initialize collector
    collector = DataCollector(
        output_dir=args.output,
        model_path=args.model,
        sample_every=args.sample_every,
    )
    
    # Process videos
    if args.video:
        if not args.video.exists():
            print(f"ERROR: Video file not found: {args.video}")
            return 1
        collector.process_video(args.video, args.task, args.start_frame, args.end_frame)
    
    elif args.recordings_dir:
        if not args.recordings_dir.exists():
            print(f"ERROR: Recordings directory not found: {args.recordings_dir}")
            return 1
        collector.process_recordings_dir(args.recordings_dir)
    
    else:
        print("ERROR: Must specify --video or --recordings-dir")
        parser.print_help()
        return 1
    
    # Create outputs
    if args.create_dataset or args.video or args.recordings_dir:
        collector.create_dataset_csv()
    
    if args.create_template:
        collector.create_labeling_template(args.output / "labeling")
    
    # Print statistics
    collector.print_stats()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
