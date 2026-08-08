"""Capture short webcam clips per task class — Tier-2 real training data.

Records N-second clips from the default webcam into ``data/tasks/<task>/``.
Each clip is the ground truth the task classifier trains on (see
``scripts/build_task_dataset.py`` and ``scripts/train_task_model_v2.py --data``).

Usage::

    python scripts/capture_task_clips.py --list                    # show the 5 task classes
    python scripts/capture_task_clips.py --task "Lifting / Picking" --seconds 8
    python scripts/capture_task_clips.py --task "Assembly Work" --seconds 6 --fps 15 --out data/tasks

Guidance (matches docs/DATA_COLLECTION_GUIDE.md):
- front-facing camera ~1.5 m away, chest height, bright indoor light
- perform the task naturally for the whole clip; 5-10 s per clip
- capture a few clips per class, ideally 3+ subjects with different builds

Clips are gitignored (large binaries) — only the extracted feature CSV is
committed, plus the retrained model.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CLASSES = [
    "Neutral Standing",
    "Assembly Work",
    "Reaching",
    "Lifting / Picking",
    "Inspection",
]


def _slug(task: str) -> str:
    import re

    return re.sub(r"[^a-z0-9]+", "_", task.lower()).strip("_")


def _countdown(cap, out_path: Path, task: str, seconds: int) -> int:
    import cv2

    fps = cap.get(cv2.CAP_PROP_FPS) or 20.0
    writer = None
    frames = 0
    start = time.monotonic()
    deadline = start + seconds
    while time.monotonic() < deadline:
        ok, frame = cap.read()
        if not ok:
            break
        if writer is None:
            h, w = frame.shape[:2]
            writer = cv2.VideoWriter(
                str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
        writer.write(frame)
        frames += 1
        cv2.putText(frame, f"{task}  [{seconds - int(time.monotonic() - start)}s]",
                    (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
        cv2.imshow("ErgoVigilance capture — press Q to abort", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
    if writer is not None:
        writer.release()
    cv2.destroyAllWindows()
    return frames


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", type=str, default=None,
                    help="Task class label (e.g. 'Lifting / Picking'). Required unless --list.")
    ap.add_argument("--seconds", type=int, default=8, help="Clip length in seconds (default 8)")
    ap.add_argument("--fps", type=int, default=20,
                    help="Target recording framerate; the dataset builder samples frames anyway")
    ap.add_argument("--camera", type=int, default=0, help="Camera index (default 0)")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "tasks",
                    help="Root clips directory (default data/tasks)")
    ap.add_argument("--list", action="store_true", help="Print the task classes and exit")
    args = ap.parse_args()

    if args.list:
        print("Task classes:")
        for i, c in enumerate(CLASSES, 1):
            print(f"  {i}. {c}")
        return

    task = args.task
    if task is None:
        ap.error("--task is required (use --list to see the classes)")
    if task not in CLASSES:
        print(f"WARNING: '{task}' is not one of the standard classes: {CLASSES}")
        print("The dataset builder and trainer accept it, but the Gaussian agreement")
        print("filter may reject it. Proceed anyway.")

    import cv2

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        sys.exit(f"ERROR: no camera at index {args.camera}")
    cap.set(cv2.CAP_PROP_FPS, args.fps)

    task_dir = args.out / _slug(task)
    task_dir.mkdir(parents=True, exist_ok=True)
    out_path = task_dir / f"{_slug(task)}_{time.strftime('%Y%m%d_%H%M%S')}.mp4"

    print(f"Recording {args.seconds}s of '{task}' → {out_path}")
    print("Get into position — recording starts now.")
    frames = _countdown(cap, out_path, task, args.seconds)
    cap.release()

    if frames == 0:
        sys.exit("ERROR: no frames captured — check the camera.")
    print(f"Saved {frames} frames. Capture another clip for this class, or switch "
          f"tasks with --task.")


if __name__ == "__main__":
    main()
