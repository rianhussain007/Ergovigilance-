"""Build COCO_17 feature datasets from all available training sources.

Sources:
  1. REBA pose dataset (reba_features.csv) — 30K+ frames from COCO annotations
  2. Multiposture dataset — synthetic + real posture data (converts to COCO_17)
  3. Office posture dataset — desk/workbench postures (converts to COCO_17)
  4. Diverse training videos — extracted frames from factory/ergonomic videos

All sources are merged into a single COCO_17 feature CSV that the YOLO
task and risk classifiers train on.

Usage:
    python -m yolo_cloud.training.build_yolo_features
    python -m yolo_cloud.training.build_yolo_features --output data/processed/yolo_features.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.core.constants import COCO_17, FEATURE_COLUMNS  # noqa: E402
from backend.services.features import extract_features_from_keypoints, risk_from_features  # noqa: E402

# Features that are always NaN on COCO_17 data (no finger/foot landmarks).
_ALWAYS_NA_ON_COCO = {
    "wrist_deviation_angle",
    "hand_reach_ratio",
    "finger_spread_ratio",
    "stance_width_ratio",
}

TRAINABLE_FEATURES = [c for c in FEATURE_COLUMNS if c not in _ALWAYS_NA_ON_COCO]

# All features (including NaN ones — HistGradientBoosting handles NaN natively)
ALL_FEATURES = list(FEATURE_COLUMNS)

# ── REBA Dataset ──────────────────────────────────────────────────────────────

def _load_reba_features(csv_path: Path) -> list[dict]:
    """Load the pre-built REBA feature CSV (already COCO_17 format).

    The CSV has columns: source, sample_id, <17 features>, reba_score,
    reba_risk_level, reba_risk_band, rule_risk
    """
    if not csv_path.exists():
        print(f"  [SKIP] {csv_path} not found")
        return []

    rows = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Use rule_risk as the label (computed from features, not raw REBA score)
            label = row.get("rule_risk", "").strip()
            if not label or label not in ("LOW", "MEDIUM", "HIGH"):
                continue

            features = {}
            for col in ALL_FEATURES:
                val = row.get(col, "nan")
                try:
                    features[col] = float(val)
                except (ValueError, TypeError):
                    features[col] = float("nan")

            rows.append({
                "source": "reba",
                "sample_id": row.get("sample_id", ""),
                **features,
                "risk_label": label,
                "task_label": _risk_to_task_proxy(label, features),
            })

    print(f"  REBA features: {len(rows)} samples")
    return rows


# ── Multiposture Dataset ──────────────────────────────────────────────────────

def _load_multiposture(csv_path: Path) -> list[dict]:
    """Load multiposture data and compute COCO_17-compatible features.

    The multiposture CSV has columns: source, sample_id, <some features>, label
    We re-compute features from the raw angles that ARE available on COCO_17.
    """
    if not csv_path.exists():
        print(f"  [SKIP] {csv_path} not found")
        return []

    rows = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            label = row.get("label", "").strip()
            if not label:
                continue

            # Map multiposture features to COCO_17 feature names
            features = {}
            for col in ALL_FEATURES:
                if col in row:
                    try:
                        features[col] = float(row[col])
                    except (ValueError, TypeError):
                        features[col] = float("nan")
                else:
                    features[col] = float("nan")

            # multiposture has neck_flexion, trunk_flexion, shoulder_elev, etc.
            # Fill in from what's available
            for src, dst in [
                ("neck_flexion", "neck_flexion"),
                ("trunk_flexion", "trunk_flexion"),
                ("left_shoulder_elev", "left_shoulder_elev"),
                ("right_shoulder_elev", "right_shoulder_elev"),
                ("shoulder_symmetry", "shoulder_symmetry"),
                ("alignment_deviation", "alignment_deviation"),
                ("knee_angle", "knee_angle"),
                ("elbow_flexion_angle", "elbow_flexion_angle"),
                ("upper_arm_angle_from_vertical", "upper_arm_angle_from_vertical"),
            ]:
                if src in row and row[src]:
                    try:
                        features[dst] = float(row[src])
                    except (ValueError, TypeError):
                        pass

            # Forward head posture and head tilt not in multiposture
            features["forward_head_posture"] = float("nan")
            features["head_tilt_angle"] = float("nan")

            # Risk label
            risk = label.upper()
            if risk not in ("LOW", "MEDIUM", "HIGH"):
                risk = _score_to_risk(float(row.get("trunk_flexion", 0)))

            rows.append({
                "source": "multiposture",
                "sample_id": row.get("sample_id", ""),
                **features,
                "risk_label": risk,
                "task_label": label,
            })

    print(f"  Multiposture: {len(rows)} samples")
    return rows


# ── Task Clip Data ────────────────────────────────────────────────────────────

def _load_task_clip_features(data_dir: Path) -> list[dict]:
    """Load task clip features from diverse training videos.

    These are frames extracted from factory videos where we know the task.
    We extract COCO_17 features from saved keypoints if available.
    """
    keypoints_dir = data_dir / "keypoints"
    if not keypoints_dir.exists():
        print(f"  [SKIP] {keypoints_dir} not found")
        return []

    rows = []
    for kp_file in sorted(keypoints_dir.glob("*.json")):
        try:
            import json
            with open(kp_file) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        # Keypoints should be in COCO_17 format [x, y, confidence]
        kps = data.get("keypoints")
        task = data.get("task", "Unknown")
        if kps is None or len(kps) < 17:
            continue

        # Convert to array with visibility channel
        kps_arr = np.zeros((17, 4), dtype=float)
        for i, kp in enumerate(kps[:17]):
            if len(kp) >= 3 and kp[2] > 0:
                kps_arr[i, :2] = kp[:2]
                kps_arr[i, 3] = kp[2]
            else:
                kps_arr[i] = float("nan")

        features, unavailable, _ = extract_features_from_keypoints(kps_arr, COCO_17)

        rows.append({
            "source": "task_clip",
            "sample_id": kp_file.stem,
            **{col: features.get(col, float("nan")) for col in ALL_FEATURES},
            "risk_label": risk_from_features(features, unavailable),
            "task_label": task,
        })

    print(f"  Task clips: {len(rows)} samples")
    return rows


# ── Synthetic Data Augmentation ───────────────────────────────────────────────

def _augment_rows(rows: list[dict], noise_std: float = 3.0) -> list[dict]:
    """Add Gaussian noise to numeric features for data augmentation.

    This creates additional training samples by slightly perturbing the
    existing features, improving model generalization.
    """
    augmented = []
    rng = np.random.RandomState(42)

    for row in rows:
        aug = dict(row)
        aug["sample_id"] = row["sample_id"] + "_aug"
        for col in ALL_FEATURES:
            val = row.get(col, float("nan"))
            if not np.isnan(val):
                aug[col] = round(float(val + rng.normal(0, noise_std)), 4)
        augmented.append(aug)

    return augmented


# ── Helpers ───────────────────────────────────────────────────────────────────

def _score_to_risk(trunk_flexion: float) -> str:
    """Simple heuristic to derive risk from available features."""
    if trunk_flexion > 45:
        return "HIGH"
    elif trunk_flexion > 20:
        return "MEDIUM"
    return "LOW"


def _risk_to_task_proxy(label: str, features: dict) -> str:
    """Derive a rough task label from features (for task model pretraining).

    This is approximate — the task model will learn better distinctions
    from the data itself.
    """
    trunk = features.get("trunk_flexion", 0)
    knee = features.get("knee_angle", 180)
    shoulder = features.get("left_shoulder_elev", 180)
    elbow = features.get("elbow_flexion_angle", 180)

    if np.isnan(trunk):
        return "Unknown"

    if trunk > 20 and knee < 150:
        return "Lifting / Picking"
    if shoulder < 120:
        return "Reaching"
    if 70 < elbow < 160 and trunk < 20:
        return "Assembly Work"
    if trunk < 10 and knee > 160:
        return "Neutral Standing"
    if label == "HIGH":
        return "Lifting / Picking"

    return "Assembly Work"


# ── Main ──────────────────────────────────────────────────────────────────────

def build_all(output_path: Path, augment: bool = True) -> dict:
    """Build the merged COCO_17 training dataset."""
    print("Building YOLO COCO_17 training dataset...")
    print()

    all_rows = []

    # Source 1: REBA features (already COCO_17)
    all_rows.extend(_load_reba_features(ROOT / "data/processed/reba_features.csv"))

    # Source 2: Multiposture (remap to COCO_17 feature names)
    all_rows.extend(_load_multiposture(ROOT / "data/processed/dataset_final.csv"))

    # Source 3: Task clip keypoints (if available)
    all_rows.extend(_load_task_clip_features(ROOT / "data/datasets"))

    # Source 4: Diverse training keypoints
    all_rows.extend(_load_task_clip_features(ROOT / "outputs/real_data"))

    # Augmentation
    if augment and all_rows:
        aug = _augment_rows(all_rows, noise_std=2.0)
        all_rows.extend(aug)
        print(f"\n  Augmented: +{len(aug)} samples (noise_std=2.0)")

    if not all_rows:
        raise RuntimeError(
            "No training data found! Run build_reba_dataset.py first, "
            "or ensure data/processed/reba_features.csv exists."
        )

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["source", "sample_id", *ALL_FEATURES, "risk_label", "task_label"]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in all_rows:
            writer.writerow(row)

    # Stats
    from collections import Counter
    risk_dist = Counter(r["risk_label"] for r in all_rows)
    task_dist = Counter(r["task_label"] for r in all_rows)
    source_dist = Counter(r["source"] for r in all_rows)

    print(f"\n{'=' * 60}")
    print(f"Total samples: {len(all_rows)}")
    print(f"Output: {output_path}")
    print(f"\nBy source: {dict(source_dist)}")
    print(f"By risk:   {dict(risk_dist)}")
    print(f"By task:   {dict(task_dist)}")

    # NaN stats
    nan_counts = {col: sum(1 for r in all_rows if np.isnan(r.get(col, float("nan"))))
                  for col in ALL_FEATURES}
    print(f"\nNaN counts per feature:")
    for col, count in sorted(nan_counts.items()):
        pct = count / len(all_rows) * 100
        marker = " *ALWAYS_NA" if col in _ALWAYS_NA_ON_COCO else ""
        print(f"  {col}: {count} ({pct:.1f}%){marker}")

    return {"total": len(all_rows), "risk": dict(risk_dist), "task": dict(task_dist)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Build YOLO COCO_17 training features")
    ap.add_argument("--output", type=Path,
                    default=ROOT / "data/processed/yolo_features.csv")
    ap.add_argument("--no-augment", action="store_true",
                    help="Skip data augmentation")
    args = ap.parse_args()
    build_all(args.output, augment=not args.no_augment)
