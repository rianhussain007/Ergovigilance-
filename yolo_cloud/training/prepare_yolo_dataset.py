"""Convert labeled frames + human labels into YOLOv8-pose training format.

Reads frames and human_labels.csv (from the labeling tool), converts
keypoints to YOLOv8-pose format, and creates a data.yaml for training.

Expected input:
  outputs/real_data/frames/         - Frame images
  outputs/real_data/human_labels.csv - Labels with risk + task

Output structure (data/yolo_factory/):
  data.yaml                         - Dataset description
  images/train/*.jpg                - Training images (80%)
  images/val/*.jpg                  - Validation images (20%)
  labels/train/*.txt                - YOLO pose labels
  labels/val/*.txt

Usage:
    python -m yolo_cloud.training.prepare_yolo_dataset
    python -m yolo_cloud.training.prepare_yolo_dataset \\
        --frames outputs/real_data/frames/ \\
        --labels outputs/real_data/human_labels.csv \\
        --output data/yolo_factory/ \\
        --val-split 0.2
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import shutil
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# Risk levels to class indices
RISK_CLASSES = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
TASK_CLASSES = {
    "assembly": 0, "lifting": 1, "reaching": 2, "sitting": 3,
    "standing": 4, "walking": 5, "inspection": 6, "unknown": 7,
}


def _load_keypoints_from_json(frame_path: Path) -> list[list[float]] | None:
    """Load COCO_17 keypoints from a companion JSON file.

    Looks for <frame_name>.json alongside the frame image.
    Format: [[x, y, confidence], ...] × 17
    """
    json_path = frame_path.with_suffix(".json")
    if not json_path.exists():
        # Try in a keypoints/ subdirectory
        json_path = frame_path.parent.parent / "keypoints" / json_path.name
    if not json_path.exists():
        return None

    try:
        with open(json_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    # Accept various formats
    if isinstance(data, dict) and "keypoints" in data:
        kps = data["keypoints"]
    elif isinstance(data, list) and len(data) == 17:
        kps = data
    else:
        return None

    if len(kps) != 17:
        return None

    # Ensure each keypoint is [x, y, confidence]
    result = []
    for kp in kps:
        if isinstance(kp, list) and len(kp) >= 2:
            x, y = kp[0], kp[1]
            conf = kp[2] if len(kp) >= 3 else 0.5
            result.append([float(x), float(y), float(conf)])
        else:
            result.append([0.0, 0.0, 0.0])

    return result


def _load_human_labels(csv_path: Path) -> dict[str, dict]:
    """Load human_labels.csv → {filename: {risk, task, quality}}."""
    labels = {}
    if not csv_path.exists():
        return labels

    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            filename = row.get("filename", row.get("frame", "")).strip()
            if not filename:
                continue
            labels[filename] = {
                "risk": row.get("risk", row.get("risk_level", "MEDIUM")).strip().upper(),
                "task": row.get("task", row.get("task_label", "unknown")).strip().lower(),
                "quality": row.get("quality", "clear").strip(),
            }

    return labels


def _write_yolo_label(
    label_path: Path,
    kps: list[list[float]],
    img_w: int,
    img_h: int,
    risk_class: int = 1,
) -> None:
    """Write a YOLOv8-pose label file.

    Format: class_id x_center y_center w h kx1 ky1 k1 ... kx17 ky17 k17
    All coordinates normalized to [0, 1].
    """
    # Find bounding box from visible keypoints
    visible = [(kp[0], kp[1]) for kp in kps if kp[2] > 0.1]
    if len(visible) < 3:
        return  # Not enough visible keypoints

    xs = [v[0] for v in visible]
    ys = [v[1] for v in visible]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)

    # Add padding (10% of bbox)
    pad_x = (x_max - x_min) * 0.1
    pad_y = (y_max - y_min) * 0.1
    x_min = max(0, x_min - pad_x)
    y_min = max(0, y_min - pad_y)
    x_max = min(img_w, x_max + pad_x)
    y_max = min(img_h, y_max + pad_y)

    # Normalize
    x_center = ((x_min + x_max) / 2) / img_w
    y_center = ((y_min + y_max) / 2) / img_h
    w = (x_max - x_min) / img_w
    h = (y_max - y_min) / img_h

    # Keypoints (normalized, with visibility)
    kps_str = []
    for kp in kps:
        kx = kp[0] / img_w
        ky = kp[1] / img_h
        kc = int(2 if kp[2] > 0.7 else (1 if kp[2] > 0.3 else 0))
        kps_str.extend([f"{kx:.6f}", f"{ky:.6f}", str(kc)])

    label_path.parent.mkdir(parents=True, exist_ok=True)
    with open(label_path, "w") as f:
        f.write(f"{risk_class} {x_center:.6f} {y_center:.6f} {w:.6f} {h:.6f} ")
        f.write(" ".join(kps_str))
        f.write("\n")


def prepare_dataset(
    frames_dir: Path,
    labels_csv: Path,
    output_dir: Path,
    val_split: float = 0.2,
    seed: int = 42,
) -> dict:
    """Prepare YOLOv8-pose training dataset from frames + labels."""
    print(f"Preparing YOLO dataset...")
    print(f"  Frames: {frames_dir}")
    print(f"  Labels: {labels_csv}")
    print(f"  Output: {output_dir}")

    # Load labels
    human_labels = _load_human_labels(labels_csv)
    print(f"  Human labels: {len(human_labels)}")

    # Find all frame images
    frame_files = sorted(
        f for f in frames_dir.glob("*.jpg")
        if not f.name.startswith(".")
    )
    print(f"  Frame images: {len(frame_files)}")

    # Process frames
    random.seed(seed)
    random.shuffle(frame_files)

    split_idx = int(len(frame_files) * (1 - val_split))
    train_frames = frame_files[:split_idx]
    val_frames = frame_files[split_idx:]

    print(f"  Train: {len(train_frames)}, Val: {len(val_frames)}")

    for split_name, split_frames in [("train", train_frames), ("val", val_frames)]:
        count = 0
        for frame_path in split_frames:
            # Get image dimensions (from file or assume 1920x1080)
            try:
                import cv2
                img = cv2.imread(str(frame_path))
                if img is None:
                    continue
                img_h, img_w = img.shape[:2]
            except ImportError:
                img_w, img_h = 1920, 1080

            # Load keypoints
            kps = _load_keypoints_from_json(frame_path)
            if kps is None:
                continue  # Skip frames without keypoints

            # Get label
            label_info = human_labels.get(frame_path.name, {})
            risk = label_info.get("risk", "MEDIUM")
            risk_class = RISK_CLASSES.get(risk, 1)

            # Copy image
            img_out = output_dir / "images" / split_name / frame_path.name
            img_out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(frame_path, img_out)

            # Write label
            lbl_path = output_dir / "labels" / split_name / (frame_path.stem + ".txt")
            _write_yolo_label(lbl_path, kps, img_w, img_h, risk_class)
            count += 1

        print(f"  {split_name}: {count} valid samples")

    # Write data.yaml
    data_yaml = output_dir / "data.yaml"
    with open(data_yaml, "w") as f:
        f.write(f"# YOLOv8-pose factory posture dataset\n")
        f.write(f"# Generated from: {frames_dir}\n")
        f.write(f"# Labels: {labels_csv}\n\n")
        f.write(f"path: {output_dir.resolve()}\n")
        f.write(f"train: images/train\n")
        f.write(f"val: images/val\n\n")
        f.write(f"nc: 3  # LOW=0, MEDIUM=1, HIGH=2\n")
        f.write(f"names: ['LOW', 'MEDIUM', 'HIGH']\n\n")
        f.write(f"# Keypoint config (COCO 17-point)\n")
        f.write(f"kpt_shape: [17, 3]  # 17 keypoints, [x, y, visibility]\n")

    print(f"\nDataset ready: {data_yaml}")
    return {"train": len(train_frames), "val": len(val_frames)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Prepare YOLOv8-pose training dataset")
    ap.add_argument("--frames", type=Path,
                    default=ROOT / "outputs" / "real_data" / "frames")
    ap.add_argument("--labels", type=Path,
                    default=ROOT / "outputs" / "real_data" / "human_labels.csv")
    ap.add_argument("--output", type=Path,
                    default=ROOT / "data" / "yolo_factory")
    ap.add_argument("--val-split", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    prepare_dataset(args.frames, args.labels, args.output, args.val_split, args.seed)
