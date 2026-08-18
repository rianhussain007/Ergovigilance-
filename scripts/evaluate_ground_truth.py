"""Ground-truth evaluation script (Phase 3 of docs/DATA_COLLECTION_GUIDE.md).

Compares human-assigned labels (``ground_truth_risk.json`` /
``ground_truth_task.json``, produced by ``scripts/label_frames.py``) against the
model's per-frame predictions recorded in a session's ``timeline.json``, and
writes accuracy / precision / recall / confusion-matrix metrics to
``results/ground_truth_evaluation.json``.

Matching strategy
-----------------
The guide's sketch merged on an exact ``frame`` column, but a real
``timeline.json`` does not carry the video frame index: its ``frame_number`` is a
*processed-frame counter* (1, 2, 3, ...) that does not line up with the video
frame indices used by ``label_frames.py --export-frames`` (0, 30, 60, ...).

Instead, each labeled frame index ``f`` is converted to a timestamp
``t = f / fps`` and matched to the timeline entry with the closest
``timestamp``, provided it is within ``--tolerance`` seconds. This is robust to
sparse timelines (a recording where pose was only detected on a handful of
frames) and to the counter/index discrepancy.

For the risk pass the model prediction is the timeline entry's ``risk_level``
(the actual per-frame class the pipeline emitted) rather than re-deriving a
class from ``risk_score`` thresholds, so the comparison reflects what the system
really reported.

Usage:
    venv/Scripts/python.exe scripts/evaluate_ground_truth.py \\
        --labels recordings/worker-001/<ts>/ground_truth_risk.json

    # Multiple sessions, aggregated into one result file:
    venv/Scripts/python.exe scripts/evaluate_ground_truth.py \\
        --labels a/ground_truth_risk.json b/ground_truth_risk.json

    # Task pass (5 classes + Unknown), explicit timeline location:
    venv/Scripts/python.exe scripts/evaluate_ground_truth.py \\
        --labels c/ground_truth_task.json --kind task --timeline c/timeline.json

    # Both passes in one run:
    venv/Scripts/python.exe scripts/evaluate_ground_truth.py \\
        --labels risk/ground_truth_risk.json task/ground_truth_task.json --kind both
"""

from __future__ import annotations

import argparse
import json
import sys
from bisect import bisect_left
from datetime import date
from pathlib import Path

from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "results" / "ground_truth_evaluation.json"
DEFAULT_FPS = 30.0
DEFAULT_TOLERANCE = 1.0  # seconds

RISK_CLASSES = ("LOW", "MEDIUM", "HIGH")


def load_json(path: Path) -> dict | list:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        sys.exit(f"Could not read {path}: {exc}")


def find_timeline(labels_file: Path, explicit: Path | None) -> Path | None:
    """Timeline lives next to the labels file by default (label_frames.py writes
    ground_truth_*.json into the recording dir, which also holds timeline.json)."""
    if explicit is not None:
        return explicit if explicit.exists() else None
    candidate = labels_file.parent / "timeline.json"
    return candidate if candidate.exists() else None


def nearest_timeline_entry(timeline: list[dict], frame_idx: int, fps: float,
                           tolerance: float) -> tuple[dict | None, float]:
    """Return (entry, |target_time - entry.timestamp|) or (None, inf)."""
    target = frame_idx / fps
    times = [e.get("timestamp") for e in timeline]
    if not times or all(t is None for t in times):
        return None, float("inf")
    # Work on a sorted copy of (timestamp, entry)
    pairs = sorted((t, e) for t, e in zip(times, timeline) if t is not None)
    keys = [p[0] for p in pairs]
    pos = bisect_left(keys, target)
    best = None
    best_err = float("inf")
    for cand in (pos - 1, pos, pos + 1):
        if 0 <= cand < len(pairs):
            err = abs(pairs[cand][0] - target)
            if err < best_err:
                best_err = err
                best = pairs[cand][1]
    if best_err > tolerance:
        return None, best_err
    return best, best_err


def normalize_risk(value: str) -> str:
    return str(value).strip().upper()


def build_report(y_true: list[str], y_pred: list[str], classes: list[str]) -> dict:
    """Serialize sklearn's classification_report + confusion_matrix to JSON-safe dicts."""
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "classification_report": classification_report(
            y_true, y_pred, labels=classes, zero_division=0, output_dict=True
        ),
        "confusion_matrix": confusion_matrix(
            y_true, y_pred, labels=classes
        ).tolist(),
        "classes": classes,
        "n_samples": len(y_true),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate ground-truth labels against timeline.json predictions."
    )
    parser.add_argument(
        "--labels", action="append", required=True, metavar="JSON",
        help="ground_truth_*.json file (repeatable for multi-session aggregation)",
    )
    parser.add_argument(
        "--timeline", metavar="JSON",
        help="Explicit timeline.json path (only valid with a single --labels)",
    )
    parser.add_argument(
        "--kind", choices=("risk", "task", "both"), default="risk",
        help="Which label pass to evaluate (default: risk)",
    )
    parser.add_argument("--fps", type=float, default=DEFAULT_FPS,
                        help="Recording framerate for frame→time conversion (default: 30)")
    parser.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE,
                        help="Max |timestamp| match error in seconds (default: 1.0)")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON path")
    args = parser.parse_args()

    if args.timeline and len(args.labels) > 1:
        sys.exit("--timeline can only be used with a single --labels file")

    explicit_timeline = Path(args.timeline) if args.timeline else None
    fps = args.fps if args.fps and args.fps > 0 else DEFAULT_FPS

    data_sources: list[dict] = []
    matched_pairs: list[dict] = []
    risk_true, risk_pred = [], []
    task_true, task_pred = [], []

    for label_path_str in args.labels:
        label_path = Path(label_path_str)
        if not label_path.exists():
            sys.exit(f"Labels file not found: {label_path}")
        labels_data = load_json(label_path)
        labels = labels_data.get("frames", [])
        session_id = labels_data.get("session_id", label_path.parent.name)

        # Infer pass from filename if --kind is 'both'
        fname = label_path.name.lower()
        file_kind = "task" if "task" in fname else "risk"

        timeline_path = find_timeline(label_path, explicit_timeline)
        timeline = load_json(timeline_path) if timeline_path else []
        if not isinstance(timeline, list):
            sys.exit(f"timeline.json at {timeline_path} is not a list of frame records")

        matched, unmatched = 0, 0
        session_pairs: list[dict] = []
        for frame_rec in labels:
            frame_idx = int(frame_rec["frame"])
            label = str(frame_rec["label"]).strip()
            entry, err = nearest_timeline_entry(timeline, frame_idx, fps, args.tolerance)
            if entry is None:
                unmatched += 1
                continue
            matched += 1
            if args.kind in ("risk", "both") and file_kind == "risk":
                risk_true.append(normalize_risk(label))
                risk_pred.append(normalize_risk(entry.get("risk_level", "UNKNOWN")))
            if args.kind in ("task", "both") and file_kind == "task":
                task_true.append(label)
                task_pred.append(str(entry.get("current_task", "Unknown")).strip())
            session_pairs.append({
                "session_id": session_id,
                "frame": frame_idx,
                "label": label,
                "predicted": entry.get("risk_level", entry.get("current_task")),
                "timestamp": entry.get("timestamp"),
                "match_error_s": round(err, 4),
            })

        if not timeline:
            print(f"  ! {label_path}: no timeline.json found next to it — 0 frames matched")
        elif matched == 0:
            print(f"  ! {label_path}: {len(labels)} labels, 0 matched within "
                  f"{args.tolerance}s (timeline has {len(timeline)} entries)")
        matched_pairs.extend(session_pairs)
        data_sources.append({
            "session_id": session_id,
            "labels_file": str(label_path),
            "timeline_file": str(timeline_path) if timeline_path else None,
            "frames_labeled": len(labels),
            "matched": matched,
            "unmatched": unmatched,
        })

    result: dict = {
        "data_sources": data_sources,
        "labeler": " / ".join(sorted({
            str(load_json(Path(p)).get("labeler", "unknown")) for p in args.labels
        })),
        "date": date.today().isoformat(),
        "matching": {
            "method": "nearest-timestamp (frame_idx / fps -> timeline.timestamp)",
            "fps": fps,
            "tolerance_seconds": args.tolerance,
            "note": "timeline.frame_number is a processed-frame counter, not the "
                    "video frame index; timestamps are the join key.",
        },
        "matched_pairs": matched_pairs,
    }

    print("\n=== GROUND-TRUTH EVALUATION ===")
    total_matched = sum(s["matched"] for s in data_sources)
    print(f"Sources: {len(data_sources)} | labeled frames: "
          f"{sum(s['frames_labeled'] for s in data_sources)} | matched: {total_matched}")

    if args.kind in ("risk", "both") and risk_true:
        result["risk_classification"] = build_report(
            risk_true, risk_pred, sorted(set(risk_true) | set(risk_pred))
        )
        # Top-level alias so the /validation page (reads gt.accuracy) works
        # without knowing the internal section name.
        result["accuracy"] = result["risk_classification"]["accuracy"]
        result["n_samples"] = len(risk_true)
        print("\n--- RISK CLASSIFICATION ---")
        print(f"Accuracy: {result['risk_classification']['accuracy']:.4f} "
              f"(n={len(risk_true)})")
        for cls in sorted(set(risk_true) | set(risk_pred)):
            row = result["risk_classification"]["classification_report"].get(cls, {})
            print(f"  {cls:<7} precision={row.get('precision', 0):.3f} "
                  f"recall={row.get('recall', 0):.3f} f1={row.get('f1-score', 0):.3f} "
                  f"support={row.get('support', 0)}")
    if args.kind in ("task", "both") and task_true:
        result["task_recognition"] = build_report(
            task_true, task_pred, sorted(set(task_true) | set(task_pred))
        )
        print("\n--- TASK RECOGNITION ---")
        print(f"Accuracy: {result['task_recognition']['accuracy']:.4f} "
              f"(n={len(task_true)})")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"\nWrote {out}")

    if not risk_true and not task_true:
        print("No frames matched — no metrics computed. Check --fps/--tolerance "
              "and that the recording has a timeline.json with timestamps.")


if __name__ == "__main__":
    main()
