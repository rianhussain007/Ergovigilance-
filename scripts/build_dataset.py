from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Iterable, List

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.features import COCO_17, FEATURE_COLUMNS, extract_features_from_keypoints, risk_from_features


MEDIAPIPE_NAMES = [
    "nose",
    "left_eye_inner",
    "left_eye",
    "left_eye_outer",
    "right_eye_inner",
    "right_eye",
    "right_eye_outer",
    "left_ear",
    "right_ear",
    "mouth_left",
    "mouth_right",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_pinky",
    "right_pinky",
    "left_index",
    "right_index",
    "left_thumb",
    "right_thumb",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
    "left_heel",
    "right_heel",
    "left_foot_index",
    "right_foot_index",
]


def _label_from_source(label: str, features: Dict[str, float]) -> str:
    cleaned = str(label).strip().upper()
    if "CORRECT" in cleaned and "INCORRECT" not in cleaned:
        return "LOW"
    if "INCORRECT" in cleaned:
        return "HIGH" if risk_from_features(features) == "HIGH" else "MEDIUM"
    if cleaned in {"LOW", "MEDIUM", "HIGH"}:
        return cleaned
    return risk_from_features(features)


def _multiposture_rows(path: Path) -> Iterable[Dict[str, object]]:
    if not path.exists():
        return []

    df = pd.read_csv(path)
    rows: List[Dict[str, object]] = []
    for idx, row in df.iterrows():
        keypoints = []
        for name in MEDIAPIPE_NAMES:
            keypoints.append([row[f"{name}_x"], row[f"{name}_y"], row.get(f"{name}_z", 0.0)])
        features, _unavail = extract_features_from_keypoints(keypoints)
        label_hint = row.get("upperbody_label", "")
        label = _label_from_source(label_hint, features)
        rows.append({"source": "multiposture", "sample_id": f"multiposture_{idx}", **features, "label": label})
    return rows


def _office_rows(root: Path) -> Iterable[Dict[str, object]]:
    labels_path = root / "labels" / "labels_for_train.csv"
    keypoints_dir = root / "keypoints"
    augmented_dir = root / "keypoints_augmented"
    if not labels_path.exists():
        return []

    labels = pd.read_csv(labels_path)
    label_map = {Path(row.filename).stem: row.label for row in labels.itertuples(index=False)}
    rows: List[Dict[str, object]] = []
    for directory in [keypoints_dir, augmented_dir]:
        if not directory.exists():
            continue
        for path in directory.glob("*.json"):
            sample_stem = path.stem
            base_stem = sample_stem
            for prefix in ("augmented_nl_", "augmented_rt_", "augmented_vr_"):
                if base_stem.startswith(prefix):
                    base_stem = base_stem.removeprefix(prefix)
                    break
            label_hint = label_map.get(base_stem)
            if label_hint is None:
                continue
            with path.open("r", encoding="utf-8") as f:
                payload = json.load(f)
            if not payload:
                continue
            keypoints = payload[0].get("keypoints", [])
            if len(keypoints) < 17:
                continue
            features, _unavail = extract_features_from_keypoints(keypoints, COCO_17)
            label = _label_from_source(label_hint, features)
            rows.append({"source": "office_posture", "sample_id": sample_stem, **features, "label": label})
    return rows


def _reba_rows(root: Path) -> Iterable[Dict[str, object]]:
    candidates = list(root.glob("**/*.csv"))
    rows: List[Dict[str, object]] = []
    for path in candidates:
        try:
            df = pd.read_csv(path)
        except Exception:
            continue
        score_cols = [c for c in df.columns if c.lower() in {"reba", "reba_score", "score", "risk"}]
        if not score_cols:
            continue
        feature_sets = []
        for _, row in df.iterrows():
            if all(col in row for col in FEATURE_COLUMNS):
                features = {col: float(row[col]) for col in FEATURE_COLUMNS}
                score = float(row[score_cols[0]])
                label = "LOW" if score <= 3 else "MEDIUM" if score <= 7 else "HIGH"
                feature_sets.append({"source": "reba_dataset", "sample_id": f"{path.stem}_{len(feature_sets)}", **features, "label": label})
        rows.extend(feature_sets)
    return rows


def build_dataset(output_path: Path) -> pd.DataFrame:
    rows = []
    rows.extend(_multiposture_rows(ROOT / "data" / "raw" / "multiposture" / "data.csv"))
    rows.extend(_office_rows(ROOT / "data" / "raw" / "office_posture" / "archives_data"))
    rows.extend(_reba_rows(ROOT / "data" / "raw" / "reba_dataset"))
    df = pd.DataFrame(rows)
    if df.empty:
        raise RuntimeError("No usable rows were found in data/raw.")
    df = df[["source", "sample_id", *FEATURE_COLUMNS, "label"]]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return df


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "processed" / "dataset_final.csv")
    args = parser.parse_args()
    df = build_dataset(args.output)
    print(f"Wrote {args.output} with {len(df)} rows")
    print(df["source"].value_counts().to_string())
    print(df["label"].value_counts().to_string())


if __name__ == "__main__":
    main()
