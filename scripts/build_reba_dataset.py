"""Build the risk-calibration dataset from rebapose keypoint annotations.

Reads the REBAJsonTrg per-image keypoint JSONs (COCO-derived 2D poses),
maps each pose into the pipeline's COCO-17 keypoint layout, extracts the
17 canonical features via ``extract_features_from_keypoints``, and labels
each sample with the standard REBA score/risk computed from the 2D joints
(``backend/services/reba_scoring.py``).

Output CSV (data/processed/reba_features.csv):
    source, sample_id, <17 features>, reba_score, reba_risk_level,
    reba_risk_band, rule_risk

The CSV is gitignored (data/); the trained model + calibration report
are the committed artifacts. Parallelized with ProcessPoolExecutor.

Usage:
    python scripts/build_reba_dataset.py [--src ...] [--out ...] [--stride 2] [--workers 8]
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import List

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.features import (  # noqa: E402
    COCO_17,
    FEATURE_COLUMNS,
    extract_features_from_keypoints,
    risk_from_features,
)
from backend.services.reba_scoring import reba_from_keypoints, reba_risk_band  # noqa: E402

# rebapose named joints -> COCO_17 index (our COCO_17 map omits eyes,
# which the feature extractor does not use).
_NAMED_TO_COCO = {
    "nose": "nose",
    "left_ear": "left_ear",
    "right_ear": "right_ear",
    "left_shoulder": "left_shoulder",
    "right_shoulder": "right_shoulder",
    "left_elbow": "left_elbow",
    "right_elbow": "right_elbow",
    "left_wrist": "left_wrist",
    "right_wrist": "right_wrist",
    "left_hip": "left_hip",
    "right_hip": "right_hip",
    "left_knee": "left_knee",
    "right_knee": "right_knee",
    "left_ankle": "left_ankle",
    "right_ankle": "right_ankle",
}

_CORE_JOINTS = [
    "left_shoulder", "right_shoulder", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
]

_FIELDNAMES = [
    "source", "sample_id", *FEATURE_COLUMNS,
    "reba_score", "reba_risk_level", "reba_risk_band", "rule_risk",
]


def _to_coco_array(key_points: dict) -> np.ndarray:
    """Convert a named keypoint dict to a 17-row [x, y, z, visibility] array.

    Joints marked absent in the COCO annotation (visibility 0, coordinates
    (0,0)) become NaN coordinates so the feature extractor's finite-guards
    treat them as genuinely unknown instead of computing garbage angles
    from the origin.
    """
    arr = np.full((17, 4), np.nan)
    for named, coco_name in _NAMED_TO_COCO.items():
        pt = key_points.get(named)
        if not pt or len(pt) < 3 or pt[2] <= 0:
            continue
        idx = COCO_17[coco_name]
        arr[idx, 0] = float(pt[0])
        arr[idx, 1] = float(pt[1])
        # COCO visibility: 2 = visible, 1 = labeled but occluded, 0 = absent
        arr[idx, 3] = 1.0 if pt[2] >= 2 else (0.5 if pt[2] == 1 else 0.0)
    return arr


def _usable(points: dict) -> bool:
    for j in _CORE_JOINTS:
        pt = points.get(j)
        if not pt or len(pt) < 3 or pt[2] <= 0:
            return False
    return True


def _process_chunk(paths: List[Path]) -> List[dict]:
    """Worker: convert a chunk of annotation files into feature rows."""
    rows: List[dict] = []
    for path in paths:
        try:
            with open(path) as jf:
                data = json.load(jf)
        except (json.JSONDecodeError, OSError):
            continue
        kp = data.get("key_points", {})
        if not _usable(kp):
            continue
        arr = _to_coco_array(kp)
        feats, unavailable, _ = extract_features_from_keypoints(arr, COCO_17)
        reba = reba_from_keypoints(kp)
        rows.append({
            "source": data.get("image_id", ""),
            "sample_id": data.get("json_name", path.name),
            **{c: feats[c] for c in FEATURE_COLUMNS},
            "reba_score": reba["reba_score"],
            "reba_risk_level": reba["reba_risk_level"],
            "reba_risk_band": reba_risk_band(int(reba["reba_risk_level"])),
            "rule_risk": risk_from_features(feats, unavailable),
        })
    return rows


def build(src: Path, out: Path, stride: int = 2, workers: int = 8) -> dict:
    files = sorted(src.glob("*.json"))
    print(f"found {len(files)} annotation files")
    chunk_paths = [p for i, p in enumerate(files) if i % stride == 0]

    # Split into ~workers chunks for balanced parallel work.
    chunk_size = max(1, len(chunk_paths) // (workers * 4))
    chunks = [chunk_paths[i:i + chunk_size] for i in range(0, len(chunk_paths), chunk_size)]

    rows = 0
    skipped_est = len(chunk_paths)
    with open(out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_FIELDNAMES)
        writer.writeheader()
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for chunk_rows in pool.map(_process_chunk, chunks, chunksize=1):
                for row in chunk_rows:
                    writer.writerow(row)
                    rows += 1
                if rows % 5000 == 0:
                    print(f"  {rows} rows...")
    print(f"done: {rows} rows written to {out} (usable fraction ~{rows / max(len(chunk_paths), 1):.0%})")
    return {"rows": rows, "scanned": len(chunk_paths)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path,
                    default=ROOT / "data/raw/rebapose/REBAJsonTrg/data/ann/COCO_Dataset")
    ap.add_argument("--out", type=Path, default=ROOT / "data/processed/reba_features.csv")
    ap.add_argument("--stride", type=int, default=2)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    build(args.src, args.out, args.stride, args.workers)
