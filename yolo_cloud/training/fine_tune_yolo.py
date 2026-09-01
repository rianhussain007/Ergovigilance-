"""Fine-tune YOLOv8-pose on factory-specific posture data.

The default YOLOv8-pose model is trained on COCO (general person poses).
Fine-tuning on factory/ergonomic data improves detection in:
- Workers wearing PPE (helmets, vests, gloves)
- Industrial lighting (harsh shadows, low contrast)
- Typical factory camera angles (overhead, CCTV)
- Specific postures (lifting, reaching, assembly)

Usage:
    python -m yolo_cloud.training.fine_tune_yolo
    python -m yolo_cloud.training.fine_tune_yolo --base-model yolov8s-pose.pt --epochs 50

Data format (YOLOv8-pose training format):
    images/train/*.jpg
    labels/train/*.txt  (one per image, same name)
    Each label line: class x_center y_center w h kx1 ky1 k1 xk2 ky2 k2 ... kx17 ky17 k17

To prepare training data from your labeled frames:
    python -m yolo_cloud.training.prepare_yolo_dataset \\
        --frames outputs/real_data/frames/ \\
        --labels outputs/real_data/human_labels.csv \\
        --output data/yolo_factory/
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def fine_tune(
    base_model: str = "yolov8s-pose.pt",
    data_yaml: Path = ROOT / "data" / "yolo_factory" / "data.yaml",
    output_dir: Path = ROOT / "models",
    epochs: int = 50,
    img_size: int = 640,
    batch: int = 16,
    learning_rate: float = 0.001,
    device: str = "cpu",
    patience: int = 15,
) -> Path:
    """Fine-tune YOLOv8-pose on factory posture data.

    Args:
        base_model: Pre-trained YOLOv8-pose model to start from
        data_yaml: Path to dataset YAML (must exist with train/val splits)
        output_dir: Where to save the fine-tuned model
        epochs: Number of training epochs
        img_size: Input image size
        batch: Batch size
        learning_rate: Initial learning rate
        device: Training device (cpu, cuda, mps)
        patience: Early stopping patience

    Returns:
        Path to the best fine-tuned model
    """
    try:
        from ultralytics import YOLO
    except ImportError:
        raise ImportError(
            "ultralytics is required for YOLO fine-tuning. "
            "Install with: pip install ultralytics"
        )

    if not data_yaml.exists():
        print(f"ERROR: Dataset YAML not found: {data_yaml}")
        print()
        print("To create the training dataset:")
        print("  1. Label 100+ frames using the labeling tool:")
        print("     python scripts/label_tool.py")
        print("  2. Export labels to YOLO format:")
        print("     python -m yolo_cloud.training.prepare_yolo_dataset \\")
        print("         --frames outputs/real_data/frames/ \\")
        print("         --labels outputs/real_data/human_labels.csv \\")
        print("         --output data/yolo_factory/")
        print("  3. This creates data.yaml with train/val splits")
        sys.exit(1)

    print(f"Fine-tuning {base_model} on factory posture data...")
    print(f"  Dataset: {data_yaml}")
    print(f"  Epochs: {epochs}")
    print(f"  Image size: {img_size}")
    print(f"  Batch size: {batch}")
    print(f"  Learning rate: {learning_rate}")
    print(f"  Device: {device}")
    print()

    # Load base model
    model = YOLO(base_model)

    # Fine-tune
    results = model.train(
        data=str(data_yaml),
        epochs=epochs,
        imgsz=img_size,
        batch=batch,
        lr0=learning_rate,
        device=device,
        patience=patience,
        project=str(output_dir),
        name="yolo_factory_pose",
        exist_ok=True,
        verbose=True,
        # Ergonomic-specific augmentations
        hsv_h=0.015,    # slight hue shift (factory lighting)
        hsv_s=0.4,      # saturation (worker uniforms)
        hsv_v=0.3,      # brightness (indoor lighting)
        flipud=0.0,     # no vertical flip (workers are upright)
        fliplr=0.5,     # horizontal flip (camera angles)
        mosaic=0.5,     # reduced mosaic (occlusion handling)
        scale=0.3,      # moderate scale (camera distances)
        perspective=0.001,  # slight perspective (CCTV angles)
    )

    # Find best model
    best_model = output_dir / "yolo_factory_pose" / "weights" / "best.pt"
    if best_model.exists():
        print(f"\nBest model saved to: {best_model}")
        # Copy to models root for easy access
        import shutil
        dest = output_dir / "yolo_factory_pose.pt"
        shutil.copy2(best_model, dest)
        print(f"Copied to: {dest}")
        return dest
    else:
        print(f"\nTraining complete. Model at: {output_dir}/yolo_factory_pose/weights/")
        return output_dir / "yolo_factory_pose" / "weights" / "best.pt"


def validate(model_path: Path, data_yaml: Path, device: str = "cpu") -> dict:
    """Validate a fine-tuned model on the test set."""
    try:
        from ultralytics import YOLO
    except ImportError:
        raise ImportError("ultralytics required: pip install ultralytics")

    model = YOLO(str(model_path))
    results = model.val(data=str(data_yaml), device=device, verbose=True)

    metrics = {
        "mAP50": float(results.box.map50),
        "mAP50-95": float(results.box.map),
        "precision": float(results.box.mp),
        "recall": float(results.box.mr),
    }

    if hasattr(results, "pose"):
        metrics["pose_mAP50"] = float(results.pose.map50)
        metrics["pose_mAP50-95"] = float(results.pose.map)

    print(f"\nValidation results:")
    for k, v in metrics.items():
        print(f"  {k}: {v:.4f}")

    return metrics


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Fine-tune YOLOv8-pose for factory postures")
    ap.add_argument("--base-model", default="yolov8s-pose.pt",
                    help="Pre-trained YOLOv8-pose model")
    ap.add_argument("--data", type=Path,
                    default=ROOT / "data" / "yolo_factory" / "data.yaml")
    ap.add_argument("--output", type=Path, default=ROOT / "models")
    ap.add_argument("--epochs", type=int, default=50)
    ap.add_argument("--img-size", type=int, default=640)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--lr", type=float, default=0.001)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--patience", type=int, default=15)
    args = ap.parse_args()

    best = fine_tune(
        base_model=args.base_model,
        data_yaml=args.data,
        output_dir=args.output,
        epochs=args.epochs,
        img_size=args.img_size,
        batch=args.batch,
        learning_rate=args.lr,
        device=args.device,
        patience=args.patience,
    )

    if best.exists():
        print("\nRunning validation...")
        validate(best, args.data, device=args.device)
