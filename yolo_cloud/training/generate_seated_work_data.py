"""Generate synthetic seated work keypoints from existing REBA data.

The REBA dataset contains many postures that ARE seated work (bent knees,
upright trunk, moderate neck flexion) but aren't labeled as such. This script
identifies those samples and creates proper Seated Work COCO_17 keypoint
annotations by:

1. Finding REBA samples with seated-like joint angles
2. Converting them to COCO_17 keypoint format
3. Saving as JSON files compatible with the training pipeline

Usage:
    python -m yolo_cloud.training.generate_seated_work_data
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.core.constants import COCO_17, FEATURE_COLUMNS  # noqa: E402
from backend.services.features import extract_features_from_keypoints  # noqa: E402


def _synthetic_keypoints_from_features(features: dict, noise: float = 2.0) -> list[list[float]]:
    """Generate synthetic COCO_17 keypoints that would produce the given features.

    This is an approximation - we create keypoints in a seated pose and
    adjust them to match the target feature values.
    """
    rng = np.random.RandomState()

    # Base seated pose (normalized coords, 640x480 frame)
    # Person sitting at a desk, facing forward
    base = {
        "nose": (320, 100),
        "left_ear": (300, 105),
        "right_ear": (340, 105),
        "left_shoulder": (280, 180),
        "right_shoulder": (360, 180),
        "left_elbow": (260, 280),
        "right_elbow": (380, 280),
        "left_wrist": (250, 350),
        "right_wrist": (390, 350),
        "left_hip": (290, 320),
        "right_hip": (350, 320),
        "left_knee": (270, 420),
        "right_knee": (370, 420),
        "left_ankle": (265, 475),
        "right_ankle": (375, 475),
    }

    # Adjust trunk angle
    trunk = features.get("trunk_flexion", 10)
    if not np.isnan(trunk) and trunk > 0:
        # Lean forward slightly
        lean = trunk * 1.5
        for name in ["nose", "left_ear", "right_ear", "left_shoulder", "right_shoulder"]:
            x, y = base[name]
            base[name] = (x, y + lean)

    # Adjust neck flexion
    neck = features.get("neck_flexion", 5)
    if not np.isnan(neck) and neck > 0:
        for name in ["nose", "left_ear", "right_ear"]:
            x, y = base[name]
            base[name] = (x, y + neck * 2)

    # Build keypoint array [x, y, confidence]
    keypoints = []
    kp_names = [
        "nose", "left_ear", "right_ear", "left_shoulder", "right_shoulder",
        "left_elbow", "right_elbow", "left_wrist", "right_wrist",
        "left_hip", "right_hip", "left_knee", "right_knee",
        "left_ankle", "right_ankle",
    ]

    # Map to COCO_17 indices
    coco_names = [
        "nose", "left_ear", "right_ear", "left_shoulder", "right_shoulder",
        "left_elbow", "right_elbow", "left_wrist", "right_wrist",
        "left_hip", "right_hip", "left_knee", "right_knee",
        "left_ankle", "right_ankle",
    ]

    arr = np.zeros((17, 3), dtype=float)
    for name, coco_name in zip(kp_names, coco_names):
        idx = COCO_17[coco_name]
        x, y = base.get(name, (320, 240))
        # Add noise
        x += rng.normal(0, noise)
        y += rng.normal(0, noise)
        conf = 0.7 + rng.uniform(0, 0.3)
        arr[idx] = [x, y, conf]

    # Eyes (indices 1, 2) - not used by features but need to exist
    arr[1] = [base["nose"][0] - 10, base["nose"][1] - 5, 0.8]
    arr[2] = [base["nose"][0] + 10, base["nose"][1] - 5, 0.8]

    return [[float(k[0]), float(k[1]), float(k[2])] for k in arr]


def generate_seated_work_keypoints(output_dir: Path, n_samples: int = 500) -> int:
    """Generate synthetic seated work keypoints from REBA data."""
    output_dir.mkdir(parents=True, exist_ok=True)
    keypoints_dir = output_dir / "keypoints"
    keypoints_dir.mkdir(exist_ok=True)

    # Read REBA features
    reba_path = ROOT / "data" / "processed" / "reba_features.csv"
    if not reba_path.exists():
        print(f"ERROR: {reba_path} not found")
        return 0

    # Find seated-like samples
    seated_samples = []
    with open(reba_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                trunk = float(row.get("trunk_flexion", 999))
                knee = float(row.get("knee_angle", 999))
                neck = float(row.get("neck_flexion", 999))

                # Seated: moderate trunk flexion, bent knees (sitting), upright neck
                if 5 < trunk < 35 and knee < 120 and neck < 25:
                    features = {}
                    for col in FEATURE_COLUMNS:
                        val = row.get(col, "nan")
                        try:
                            features[col] = float(val)
                        except (ValueError, TypeError):
                            features[col] = float("nan")
                    seated_samples.append(features)
            except (ValueError, TypeError):
                continue

    print(f"Found {len(seated_samples)} seated-like samples in REBA data")

    if not seated_samples:
        print("No seated samples found")
        return 0

    # Generate keypoints
    count = 0
    rng = np.random.RandomState(42)

    for i in range(min(n_samples, len(seated_samples) * 3)):
        # Pick a random seated sample and add variation
        base = seated_samples[i % len(seated_samples)]
        noisy_features = {}
        for k, v in base.items():
            if not np.isnan(v):
                noisy_features[k] = v + rng.normal(0, 3.0)
            else:
                noisy_features[k] = float("nan")

        kps = _synthetic_keypoints_from_features(noisy_features)

        fn = f"seated_work_synthetic_{i:06d}.json"
        with open(keypoints_dir / fn, "w") as f:
            json.dump({
                "source": "synthetic_seated",
                "task": "Seated Work",
                "keypoints": kps,
                "features": {k: round(v, 4) if not np.isnan(v) else None
                             for k, v in noisy_features.items()},
            }, f)
        count += 1

    print(f"Generated {count} seated work keypoint files in {keypoints_dir}")
    return count


if __name__ == "__main__":
    output = ROOT / "outputs" / "real_data"
    n = generate_seated_work_keypoints(output, n_samples=500)
    print(f"\nDone. Run build_yolo_features.py to include in training data.")
