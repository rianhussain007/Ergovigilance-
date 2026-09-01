"""Generate synthetic Walking/Moving keypoints from REBA data.

Walking/Moving tasks involve:
- Alternating knee angles (one leg forward, one back)
- Slight trunk lean (forward momentum)
- Arms swinging (alternating shoulder elevation)
- Moderate stride (feet apart)

Usage:
    python -m yolo_cloud.training.generate_walking_data
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


def _synthetic_walking_keypoints(features: dict, phase: float = 0.0, noise: float = 3.0) -> list[list[float]]:
    """Generate COCO_17 keypoints for a walking pose.

    Args:
        features: Target feature values
        phase: Walking phase (0-1, 0=right foot forward, 0.5=left foot forward)
        noise: Noise level for keypoint positions
    """
    rng = np.random.RandomState()

    # Base walking pose - person mid-stride
    # Phase determines which leg is forward
    stride = 30 * np.sin(phase * np.pi * 2)  # Hip offset from center
    knee_bend = 20 + 15 * abs(np.sin(phase * np.pi * 2))  # Knee flexion

    base = {
        "nose": (320, 105),
        "left_ear": (308, 108),
        "right_ear": (332, 108),
        "left_shoulder": (290, 185),
        "right_shoulder": (350, 185),
        "left_elbow": (275, 265 - 10 * np.sin(phase * np.pi * 2)),   # Arms swing
        "right_elbow": (365, 265 + 10 * np.sin(phase * np.pi * 2)),
        "left_wrist": (265, 330 - 15 * np.sin(phase * np.pi * 2)),
        "right_wrist": (375, 330 + 15 * np.sin(phase * np.pi * 2)),
        "left_hip": (300, 335),
        "right_hip": (340, 335),
        "left_knee": (295 - stride * 0.5, 420 - knee_bend * 0.5),   # One leg forward
        "right_knee": (345 + stride * 0.5, 420 + knee_bend * 0.5),  # One leg back
        "left_ankle": (290 - stride * 0.8, 478),
        "right_ankle": (350 + stride * 0.8, 478),
    }

    # Adjust for trunk flexion (walking lean)
    trunk = features.get("trunk_flexion", 10)
    if not np.isnan(trunk) and trunk > 0:
        lean = trunk * 0.8
        for name in ["nose", "left_ear", "right_ear", "left_shoulder", "right_shoulder"]:
            x, y = base[name]
            base[name] = (x + lean * 0.15, y + lean)

    # Adjust for neck flexion
    neck = features.get("neck_flexion", 8)
    if not np.isnan(neck) and neck > 0:
        for name in ["nose", "left_ear", "right_ear"]:
            x, y = base[name]
            base[name] = (x + neck * 0.2, y + neck * 1.5)

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
        conf = 0.65 + rng.uniform(0, 0.35)  # Walking has lower confidence
        arr[idx] = [x, y, conf]

    # Eyes
    arr[1] = [base["nose"][0] - 8, base["nose"][1] - 3, 0.75]
    arr[2] = [base["nose"][0] + 8, base["nose"][1] - 3, 0.75]

    return [[float(k[0]), float(k[1]), float(k[2])] for k in arr]


def generate_walking_keypoints(output_dir: Path, n_samples: int = 500) -> int:
    """Generate synthetic Walking/Moving keypoints."""
    output_dir.mkdir(parents=True, exist_ok=True)
    keypoints_dir = output_dir / "keypoints"
    keypoints_dir.mkdir(exist_ok=True)

    reba_path = ROOT / "data" / "processed" / "reba_features.csv"
    if not reba_path.exists():
        print(f"ERROR: {reba_path} not found")
        return 0

    # Find walking-like samples:
    # - Different left/right knee angles (stride)
    # - Moderate trunk (walking lean)
    # - Standing height (knees not deeply bent)
    walking_samples = []
    with open(reba_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                trunk = float(row.get("trunk_flexion", 999))
                knee = float(row.get("knee_angle", 999))
                neck = float(row.get("neck_flexion", 999))

                # Walking: moderate trunk, straight-ish knees, looking ahead
                if 3 < trunk < 25 and knee > 130 and neck < 20:
                    features = {}
                    for col in FEATURE_COLUMNS:
                        val = row.get(col, "nan")
                        try:
                            features[col] = float(val)
                        except (ValueError, TypeError):
                            features[col] = float("nan")
                    walking_samples.append(features)
            except (ValueError, TypeError):
                continue

    print(f"Found {len(walking_samples)} walking-like samples in REBA data")

    if not walking_samples:
        print("No walking samples found")
        return 0

    # Generate keypoints with multiple walking phases
    count = 0
    rng = np.random.RandomState(42)

    for i in range(n_samples):
        base = walking_samples[i % len(walking_samples)]
        noisy = {}
        for k, v in base.items():
            if not np.isnan(v):
                noisy[k] = v + rng.normal(0, 4.0)
            else:
                noisy[k] = float("nan")

        # Generate multiple phases per sample for variety
        phase = rng.uniform(0, 1)
        kps = _synthetic_walking_keypoints(noisy, phase=phase)

        fn = f"walking_synthetic_{i:06d}.json"
        with open(keypoints_dir / fn, "w") as f:
            json.dump({
                "source": "synthetic_walking",
                "task": "Walking / Moving",
                "keypoints": kps,
                "phase": round(phase, 3),
                "features": {k: round(v, 4) if not np.isnan(v) else None
                             for k, v in noisy.items()},
            }, f)
        count += 1

    print(f"Generated {count} walking keypoint files in {keypoints_dir}")
    return count


if __name__ == "__main__":
    output = ROOT / "outputs" / "real_data"
    n = generate_walking_keypoints(output, n_samples=500)
    print(f"\nDone. Run build_yolo_features.py to include in training data.")
