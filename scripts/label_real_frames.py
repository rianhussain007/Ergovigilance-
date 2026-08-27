"""
Labeling Workflow Helper for Real Factory Footage

This script helps humans label extracted frames with:
- Task class (7 classes)
- Risk level (LOW/MEDIUM/HIGH)
- RULA/REBA score (optional)

Usage:
    # Interactive labeling (opens frames in browser)
    python scripts/label_real_frames.py --interactive --output outputs/real_data/labels/
    
    # Label from CSV template
    python scripts/label_real_frames.py --csv outputs/real_data/labeling/labeling_template.csv
    
    # Convert labels to training format
    python scripts/label_real_frames.py --convert --labels outputs/real_data/labels/labels.json
    
    # Validate labels against model predictions
    python scripts/label_real_frames.py --validate --labels outputs/real_data/labels/labels.json
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Task classes
TASK_CLASSES = [
    "Neutral Standing",
    "Assembly Work",
    "Reaching",
    "Lifting / Picking",
    "Inspection",
    "Seated Work",
    "Walking / Moving",
    "Unknown",
]

RISK_LEVELS = ["LOW", "MEDIUM", "HIGH", "Unknown"]


@dataclass
class FrameLabel:
    """Label for a single frame."""
    frame_id: str
    frame_path: str
    source_video: str = ""
    timestamp_sec: float = 0.0
    
    # Labels (to be filled by human)
    task_label: str = "Unknown"
    risk_level: str = "Unknown"
    rula_score: Optional[int] = None
    reba_score: Optional[int] = None
    notes: str = ""
    
    # Metadata
    labeled_by: str = ""
    labeled_at: str = ""
    confirmed: bool = False


class LabelingHelper:
    """Helper for labeling extracted frames."""
    
    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.labels_file = self.output_dir / "labels.json"
        self.labels: Dict[str, FrameLabel] = {}
        
        # Load existing labels
        if self.labels_file.exists():
            self._load_labels()
    
    def _load_labels(self):
        """Load existing labels from JSON file."""
        with open(self.labels_file) as f:
            data = json.load(f)
        
        for frame_id, label_data in data.items():
            self.labels[frame_id] = FrameLabel(**label_data)
        
        print(f"Loaded {len(self.labels)} existing labels")
    
    def _save_labels(self):
        """Save labels to JSON file."""
        data = {}
        for frame_id, label in self.labels.items():
            data[frame_id] = {
                "frame_id": label.frame_id,
                "frame_path": label.frame_path,
                "source_video": label.source_video,
                "timestamp_sec": label.timestamp_sec,
                "task_label": label.task_label,
                "risk_level": label.risk_level,
                "rula_score": label.rula_score,
                "reba_score": label.reba_score,
                "notes": label.notes,
                "labeled_by": label.labeled_by,
                "labeled_at": label.labeled_at,
                "confirmed": label.confirmed,
            }
        
        with open(self.labels_file, "w") as f:
            json.dump(data, f, indent=2)
        
        print(f"Saved {len(self.labels)} labels to {self.labels_file}")
    
    def load_from_csv(self, csv_path: Path):
        """Load frame list from CSV template."""
        with open(csv_path, newline="") as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                frame_id = row.get("frame_id", "")
                if frame_id not in self.labels:
                    self.labels[frame_id] = FrameLabel(
                        frame_id=frame_id,
                        frame_path=row.get("frame_path", ""),
                        source_video=row.get("source_video", ""),
                        timestamp_sec=float(row.get("timestamp_sec", 0) or 0),
                        task_label=row.get("suggested_task", "Unknown"),
                    )
        
        print(f"Loaded {len(self.labels)} frames from CSV")
    
    def label_frame_interactive(self, frame_id: str):
        """Label a single frame interactively."""
        if frame_id not in self.labels:
            print(f"Frame {frame_id} not found")
            return
        
        label = self.labels[frame_id]
        
        print(f"\n{'='*60}")
        print(f"Labeling frame: {frame_id}")
        print(f"Source: {label.source_video}")
        print(f"Timestamp: {label.timestamp_sec:.1f}s")
        print(f"Current task: {label.task_label}")
        print(f"{'='*60}")
        
        # Show frame if possible
        frame_path = ROOT / label.frame_path
        if frame_path.exists():
            print(f"\nFrame path: {frame_path}")
            # Try to open in browser (for web-based labeling)
            try:
                webbrowser.open(str(frame_path))
            except:
                pass
        
        # Get task label
        print("\nAvailable tasks:")
        for i, task in enumerate(TASK_CLASSES, 1):
            print(f"  {i}. {task}")
        
        while True:
            task_input = input(f"\nEnter task number (1-{len(TASK_CLASSES)}) or press Enter to keep '{label.task_label}': ").strip()
            if not task_input:
                break
            try:
                task_idx = int(task_input) - 1
                if 0 <= task_idx < len(TASK_CLASSES):
                    label.task_label = TASK_CLASSES[task_idx]
                    break
            except ValueError:
                pass
            print("Invalid input. Please enter a number.")
        
        # Get risk level
        print("\nRisk levels:")
        for i, risk in enumerate(RISK_LEVELS, 1):
            print(f"  {i}. {risk}")
        
        while True:
            risk_input = input(f"\nEnter risk level number (1-{len(RISK_LEVELS)}) or press Enter to keep '{label.risk_level}': ").strip()
            if not risk_input:
                break
            try:
                risk_idx = int(risk_input) - 1
                if 0 <= risk_idx < len(RISK_LEVELS):
                    label.risk_level = RISK_LEVELS[risk_idx]
                    break
            except ValueError:
                pass
            print("Invalid input. Please enter a number.")
        
        # Get RULA score (optional)
        rula_input = input(f"\nEnter RULA score (1-7) or press Enter to skip: ").strip()
        if rula_input:
            try:
                label.rula_score = int(rula_input)
            except ValueError:
                pass
        
        # Get notes (optional)
        notes_input = input(f"\nEnter notes or press Enter to skip: ").strip()
        if notes_input:
            label.notes = notes_input
        
        # Mark as labeled
        label.labeled_at = datetime.now().isoformat()
        label.confirmed = True
        
        # Save after each label
        self._save_labels()
        
        print(f"\nFrame {frame_id} labeled successfully!")
    
    def label_batch_interactive(self, start_id: Optional[str] = None):
        """Label multiple frames interactively."""
        frame_ids = sorted(self.labels.keys())
        
        if start_id:
            start_idx = frame_ids.index(start_id) if start_id in frame_ids else 0
            frame_ids = frame_ids[start_idx:]
        
        print(f"\nStarting interactive labeling ({len(frame_ids)} frames)")
        print("Press Ctrl+C to stop and save progress")
        
        try:
            for i, frame_id in enumerate(frame_ids):
                label = self.labels[frame_id]
                
                # Skip already labeled frames
                if label.confirmed:
                    continue
                
                print(f"\n[{i+1}/{len(frame_ids)}] Labeling frame {frame_id}")
                self.label_frame_interactive(frame_id)
                
                # Ask to continue
                if i < len(frame_ids) - 1:
                    cont = input("\nContinue to next frame? (y/n): ").strip().lower()
                    if cont != 'y':
                        break
        
        except KeyboardInterrupt:
            print("\n\nLabeling stopped. Progress saved.")
        
        self._save_labels()
    
    def convert_to_training_format(self, output_path: Path):
        """Convert labels to training CSV format."""
        rows = []
        
        for frame_id, label in self.labels.items():
            if not label.confirmed:
                continue
            
            # Load features if available
            features = {}
            feature_path = ROOT / "outputs" / "real_data" / "features" / f"{label.frame_path.split('/')[-1].replace('.jpg', '.json')}"
            if feature_path.exists():
                with open(feature_path) as f:
                    data = json.load(f)
                features = data.get("features", {})
            
            row = {
                "frame_id": frame_id,
                "source_video": label.source_video,
                "timestamp_sec": label.timestamp_sec,
                "task_label": label.task_label,
                "risk_level": label.risk_level,
                "rula_score": label.rula_score or "",
                "reba_score": label.reba_score or "",
            }
            row.update(features)
            rows.append(row)
        
        # Write CSV
        if rows:
            with open(output_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            
            print(f"\nConverted {len(rows)} labels to training format: {output_path}")
        else:
            print("\nNo confirmed labels to convert")
    
    def validate_against_model(self):
        """Validate labels against model predictions."""
        from backend.services.task_recognition import TaskRecognition
        
        recognizer = TaskRecognition()
        
        results = {
            "total": 0,
            "correct": 0,
            "incorrect": 0,
            "per_task": {},
        }
        
        for frame_id, label in self.labels.items():
            if not label.confirmed or label.task_label == "Unknown":
                continue
            
            # Load features
            feature_path = ROOT / "outputs" / "real_data" / "features" / f"{label.frame_path.split('/')[-1].replace('.jpg', '.json')}"
            if not feature_path.exists():
                continue
            
            with open(feature_path) as f:
                data = json.load(f)
            
            features = data.get("features", {})
            keypoints = data.get("keypoints", [])
            
            if not features:
                continue
            
            # Get model prediction
            if keypoints:
                import numpy as np
                kps = np.array(keypoints)
                result = recognizer.detect_task(kps, features)
                predicted_task = result["task"]
                confidence = result["confidence"]
            else:
                continue
            
            # Compare
            results["total"] += 1
            if predicted_task == label.task_label:
                results["correct"] += 1
            else:
                results["incorrect"] += 1
            
            # Per-task stats
            if label.task_label not in results["per_task"]:
                results["per_task"][label.task_label] = {"correct": 0, "incorrect": 0}
            
            if predicted_task == label.task_label:
                results["per_task"][label.task_label]["correct"] += 1
            else:
                results["per_task"][label.task_label]["incorrect"] += 1
        
        # Print results
        print(f"\n{'='*60}")
        print("MODEL VALIDATION RESULTS")
        print(f"{'='*60}")
        print(f"Total labeled frames: {results['total']}")
        print(f"Correct predictions: {results['correct']}")
        print(f"Incorrect predictions: {results['incorrect']}")
        if results["total"] > 0:
            accuracy = results["correct"] / results["total"] * 100
            print(f"Accuracy: {accuracy:.1f}%")
        
        print(f"\nPer-task breakdown:")
        for task, stats in results["per_task"].items():
            total = stats["correct"] + stats["incorrect"]
            if total > 0:
                acc = stats["correct"] / total * 100
                print(f"  {task}: {acc:.1f}% ({stats['correct']}/{total})")
        
        print(f"{'='*60}")
        
        return results
    
    def get_statistics(self):
        """Get labeling statistics."""
        total = len(self.labels)
        confirmed = sum(1 for l in self.labels.values() if l.confirmed)
        
        task_counts = {}
        risk_counts = {}
        
        for label in self.labels.values():
            if label.confirmed:
                task_counts[label.task_label] = task_counts.get(label.task_label, 0) + 1
                risk_counts[label.risk_level] = risk_counts.get(label.risk_level, 0) + 1
        
        print(f"\n{'='*60}")
        print("LABELING STATISTICS")
        print(f"{'='*60}")
        print(f"Total frames: {total}")
        print(f"Confirmed labels: {confirmed}")
        print(f"Pending labels: {total - confirmed}")
        
        if confirmed > 0:
            print(f"\nTask distribution:")
            for task, count in sorted(task_counts.items()):
                pct = count / confirmed * 100
                print(f"  {task}: {count} ({pct:.1f}%)")
            
            print(f"\nRisk distribution:")
            for risk, count in sorted(risk_counts.items()):
                pct = count / confirmed * 100
                print(f"  {risk}: {count} ({pct:.1f}%)")
        
        print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(
        description="Labeling workflow helper for real factory footage",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument("--csv", type=Path, help="Load frames from CSV template")
    parser.add_argument("--interactive", action="store_true", help="Interactive labeling mode")
    parser.add_argument("--start-frame", type=str, help="Start labeling from this frame ID")
    parser.add_argument("--convert", action="store_true", help="Convert labels to training format")
    parser.add_argument("--validate", action="store_true", help="Validate labels against model")
    parser.add_argument("--stats", action="store_true", help="Show labeling statistics")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs" / "real_data" / "labels",
                       help="Output directory for labels")
    
    args = parser.parse_args()
    
    helper = LabelingHelper(args.output)
    
    if args.csv:
        helper.load_from_csv(args.csv)
    
    if args.interactive:
        helper.label_batch_interactive(args.start_frame)
    
    if args.convert:
        output_path = args.output.parent / "training_data.csv"
        helper.convert_to_training_format(output_path)
    
    if args.validate:
        helper.validate_against_model()
    
    if args.stats or (not args.interactive and not args.convert and not args.validate):
        helper.get_statistics()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
