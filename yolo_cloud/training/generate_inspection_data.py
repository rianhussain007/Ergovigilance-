"""Generate synthetic Inspection keypoints from REBA data.

Inspection tasks involve:
- Moderate neck flexion (looking down at product)
- Upright to slightly leaned trunk (standing at workbench)
- Arms in front of body (holding/examining item)
- Moderate shoulder elevation (arms raised to eye level)
- Low knee angle (standing, not squatting)

Usage:
    python -m yolo_cloud.training.generate_inspection_data
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


def _synthetic_inspection_keypoints(features: dict, noise: float = 2.0) -> list[list[float]]:
    """Generate COCO_17 keypoints for an inspection posture."""
    rng = np.random.RandomState()

    # Base inspection pose: person standing at workbench, examining item
    base = {
        "nose": (320, 110),
        "left_ear": (305, 108),
        "right_ear": (335, 108),
        "left_shoulder": (285, 190),
        "right_shoulder": (355, 190),
        "left_elbow": (275, 270),    # arms in front, elbows bent
        "right_elbow": (365, 270),
        "left_wrist": (300, 320),    # hands together examining item
        "right_wrist": (340, 320),
        "left_hip": (295, 340),
        "right_hip": (345, 340),
        "left_knee": (290, 430),
        "right_knee": (350, 430),
        "left_ankle": (288, 478),
        "right_ankle": (352, 478),
    }

    # Adjust for neck flexion (looking down at product)
    neck = features.get("neck_flexion", 12)
    if not np.isnan(neck) and neck > 0:
        for name in ["nose", "left_ear", "right_ear"]:
            x, y = base[name]
            base[name] = (x + neck * 0.3, y + neck * 2.5)

    # Adjust for trunk flexion (leaning over workbench)
    trunk = features.get("trunk_flexion", 15)
    if not np.isnan(trunk) and trunk > 0:
        lean = trunk * 1.2
        for name in ["nose", "left_ear", "right_ear", "left_shoulder", "right_shoulder",
                      "left_elbow", "right_elbow", "left_wrist", "right_wrist"]:
            x, y = base[name]
            base[name] = (x + lean * 0.2, y + lean)

    # Adjust for shoulder elevation (arms raised to examine)
    shoulder = features.get("left_shoulder_elev", 35)
    if not np.isnan(shoulder) and shoulder > 25:
        raise_amount = (shoulder - 25) * 0.8
        for name in ["left_elbow", "right_elbow", "left_wrist", "right_wrist"]:
            x, y = base[name]
            base[name] = (x, y - raise_amount)

    # Build COCO_17 array
    arr = np.zeros((17, 3), dtype=float)
    kp_map = {
        "nose": 0, "left_ear": 3, "right_ear": 4,
        "left_shoulder": 5, "right_shoulder": 6,
        "left_elbow": 7, "right_elbow": 8,
        "left_wrist": 9, "right_wrist": 10,
        "left_hip": 11, "right_hip": 12,
        "left_knee": 13, "right_knee": 14,
        "left_ankle": 15, "right_ankle": 16,
    }

    for name, idx in kp_map.items():
        x, y = base.get(name, (320, 240))
        x += rng.normal(0, noise)
        y += rng.normal(0, noise)
        conf = 0.7 + rng.uniform(0, 0.3)
        arr[idx] = [x, y, conf]

    # Eyes
    arr[1] = [base["nose"][0] - 8, base["nose"][1] - 3, 0.8]
    arr[2] = [base["nose"][0] + 8, base["nose"][1] - 3, 0.8]

    return [[float(k[0]), float(k[1]), float(k[2])] for k in arr]


def generate_inspection_keypoints(output_dir: Path, n_samples: int = 500) -> int:
    """Generate synthetic Inspection keypoints from REBA data."""
    output_dir.mkdir(parents=True, exist_ok=True)
    keypoints_dir = output_dir / "keypoints"
    keypoints_dir.mkdir(exist_ok=True)

    reba_path = ROOT / "data" / "processed" / "reba_features.csv"
    if not reba_path.exists():
        print(f"ERROR: {reba_path} not found")
        return 0

    # Find inspection-like samples:
    # - Moderate neck flexion (looking down)
    # - Upright trunk (standing at bench)
    # - Arms in front (moderate shoulder elevation)
    # - Standing (knees relatively straight)
    inspection_samples = []
    with open(reba_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                trunk = float(row.get("trunk_flexion", 999))
                knee = float(row.get("knee_angle", 999))
                neck = float(row.get("neck_flexion", 999))
                shoulder = float(row.get("left_shoulder_elev", 999))

                # Inspection: looking down (neck > 8), moderate trunk, standing
                if 8 < neck < 30 and 5 < trunk < 30 and knee > 140:
                    features = {}
                    for col in FEATURE_COLUMNS:
                        val = row.get(col, "nan")
                        try:
                            features[col] = float(val)
                        except (ValueError, TypeError):
                            features[col] = float("nan")
                    inspection_samples.append(features)
            except (ValueError, TypeError):
                continue

    print(f"Found {len(inspection_samples)} inspection-like samples in REBA data")

    if not inspection_samples:
        print("No inspection samples found")
        return 0

    # Generate keypoints
    count = 0
    rng = np.random.RandomState(42)

    for i in range(min(n_samples, len(inspection_samples) * 3)):
        base = inspection_samples[i % len(inspection_samples)]
        noisy = {}
        for k, v in base.items():
            if not np.isnan(v):
                noisy[k] = v + rng.normal(0, 3.0)
            else:
                noisy[k] = float("nan")

        kps = _synthetic_inspection_keypoints(noisy)

        fn = f"inspection_synthetic_{i:06d}.json"
        with open(keypoints_dir / fn, "w") as f:
            json.dump({
                "source": "synthetic_inspection",
                "task": "Inspection",
                "keypoints": kps,
                "features": {k: round(v, 4) if not np.isnan(v) else None
                             for k, v in noisy.items()},
            }, f)
        count += 1

    print(f"Generated {count} inspection keypoint files in {keypoints_dir}")
    return count


if __name__ == "__main__":
    output = ROOT / "outputs" / "real_data"
    n = generate_inspection_keypoints(output, n_samples=500)
    print(f"\nDone. Run build_yolo_features.py to include in training data.")
