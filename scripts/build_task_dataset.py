"""Extract task-model features from captured clips → labeled training CSV.

Runs the SAME PoseEngine the live pipeline uses over every sampled frame of
the clips in ``data/tasks/<task>/*.mp4`` (captured with
``scripts/capture_task_clips.py``) and writes the 19 task-model features
(17 biomechanical + movement_velocity + wrist_movement_velocity) plus the
task label to ``data/processed/task_clips_features.csv``.

Usage::

    python scripts/build_task_dataset.py                                # default clips dir
    python scripts/build_task_dataset.py --clips data/tasks --output data/processed/task_clips_features.csv
    python scripts/build_task_dataset.py --sample-every 3 --model models/pose_landmarker_lite.task

The CSV is consumed by ``scripts/train_task_model_v2.py --data <csv>``.
Frames where no person is detected are skipped; only the features are stored,
not the frames.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.features import FEATURE_COLUMNS  # noqa: E402

MOTION_FEATURES = ["movement_velocity", "wrist_movement_velocity"]
TRAIN_FEATURES = [*FEATURE_COLUMNS, *MOTION_FEATURES]

# Canonical classes (kept in sync with scripts/train_task_model_v2.py).
# The clip folders are slugs of these labels (see capture_task_clips.py _slug).
CLASSES = [
    "Neutral Standing",
    "Assembly Work",
    "Reaching",
    "Lifting / Picking",
    "Inspection",
]
def slug_of(task: str) -> str:
    """Mirror of capture_task_clips.py's folder slug (kept local to stay
    import-light — both scripts share this exact regex)."""
    import re

    return re.sub(r"[^a-z0-9]+", "_", task.lower()).strip("_")


_SLUG_TO_LABEL = {slug_of(c): c for c in CLASSES}


def _label_from_dir(name: str) -> str:
    return _SLUG_TO_LABEL.get(name, name.replace("_", " ").title())


def extract_clip(
    clip_path: Path,
    task_label: str,
    engine,
    sample_every: int,
) -> list[dict]:
    """Run PoseEngine over sampled frames of one clip; return feature rows."""
    import cv2

    rows: list[dict] = []
    cap = cv2.VideoCapture(str(clip_path))
    frame_idx = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if frame_idx % sample_every != 0:
                frame_idx += 1
                continue
            try:
                result = engine.process_frame(frame)
            except Exception:
                result = None
            if result is not None and result.person_detected:
                feats = {c: result.features.get(c, 0.0) for c in TRAIN_FEATURES}
                rows.append({
                    "source": "task_clip",
                    "sample_id": f"{clip_path.stem}_{frame_idx}",
                    "task_label": task_label,
                    **feats,
                })
            frame_idx += 1
    finally:
        cap.release()
    return rows


def build_dataset(clips_root: Path, output_path: Path, model_path: Path,
                  sample_every: int) -> pd.DataFrame:
    from backend.services.pose_engine import PoseEngine

    engine = PoseEngine(str(model_path))
    engine.initialize()

    all_rows: list[dict] = []
    counts: Counter = Counter()
    clips = sorted(clips_root.glob("*/**/*.mp4")) if clips_root.exists() else []
    if not clips:
        raise RuntimeError(
            f"No clips found under {clips_root}. Capture some first with:\n"
            f"  python scripts/capture_task_clips.py --task '<class>' --seconds 8")

    for clip in clips:
        task_label = _label_from_dir(clip.parent.name)
        rows = extract_clip(clip, task_label, engine, sample_every)
        all_rows.extend(rows)
        counts[task_label] += len(rows)
        print(f"  {clip.name}: {len(rows)} usable frames (label '{task_label}')")

    engine.release()

    if not all_rows:
        raise RuntimeError("No person-detected frames found in any clip — "
                           "re-shoot with a full-body, front-facing view.")

    df = pd.DataFrame(all_rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"\nWrote {output_path} with {len(df)} rows")
    print("Per task:")
    for task, n in counts.most_common():
        print(f"  {task}: {n}")
    return df


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--clips", type=Path, default=ROOT / "data" / "tasks",
                    help="Directory containing task clip subfolders (default data/tasks)")
    ap.add_argument("--output", type=Path,
                    default=ROOT / "data" / "processed" / "task_clips_features.csv")
    ap.add_argument("--model", type=Path, default=ROOT / "models" / "pose_landmarker_lite.task")
    ap.add_argument("--sample-every", type=int, default=5,
                    help="Process every Nth frame of each clip (default 5)")
    args = ap.parse_args()
    build_dataset(args.clips, args.output, args.model, args.sample_every)


if __name__ == "__main__":
    main()
