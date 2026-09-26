"""Evaluate the yolo_cloud (YOLO pose) risk path against human labels.

This is the FIRST accuracy measurement for the cloud engine. It is deliberately
scoped: it scores the risk band (LOW / MEDIUM / HIGH) that
``yolo_cloud.pose_engine.YOLOPoseEngine.process_frame`` produces for a still
frame, and compares it with the human label in
``outputs/real_data/human_labels.csv``.

Scope and honesty rules (docs/DEEP_AUDIT_REPORT.md "Safe Claims Sheet"):
  * Ground truth in this file only ever carries LOW and MEDIUM — HIGH is NOT
    validated here, so no HIGH accuracy may be claimed.
  * The 87.6% figure belongs to the on-premise backend engine and is untouched
    by this script; these numbers are reported with engine + profile + date.
  * Rows the labeler marked ``occluded`` are reported both included and
    excluded.

Usage (one process per profile, because yolo_cloud.config reads env at import)::

    python scripts/eval_cloud_accuracy.py                       # default profile
    YOLO_MODEL=yolov8n-pose.pt YOLO_IMGSZ=320 \
        python scripts/eval_cloud_accuracy.py --label capacity-n320

Prints a JSON report on stdout; progress goes to stderr.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

LABELS_CSV = REPO_ROOT / "outputs" / "real_data" / "human_labels.csv"
RISK_CLASSES = ["LOW", "MEDIUM", "HIGH"]
# A prediction of "NO_DETECTION" means the pose engine found no person in the
# frame; it is scored as wrong rather than dropped.
NO_DETECTION = "NO_DETECTION"


def _resolve(raw: str) -> Path | None:
    """CSV paths are written by Windows code with doubled separators."""
    cleaned = (raw or "").strip().replace("\\\\", "/").replace("\\", "/")
    if not cleaned:
        return None
    path = Path(cleaned)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path if path.exists() else None


def load_rows() -> list[dict]:
    with open(LABELS_CSV, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def confusion(truth: list[str], pred: list[str], labels: list[str]) -> dict:
    matrix = {t: {p: 0 for p in labels} for t in labels}
    for t, p in zip(truth, pred):
        matrix[t][p] += 1
    return matrix


def per_class_metrics(truth: list[str], pred: list[str], labels: list[str]) -> dict:
    out = {}
    for cls in labels:
        tp = sum(1 for t, p in zip(truth, pred) if t == cls and p == cls)
        fp = sum(1 for t, p in zip(truth, pred) if t != cls and p == cls)
        fn = sum(1 for t, p in zip(truth, pred) if t == cls and p != cls)
        support = tp + fn
        precision = tp / (tp + fp) if (tp + fp) else None
        recall = tp / (tp + fn) if (tp + fn) else None
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision is not None and recall is not None and (precision + recall))
            else None
        )
        out[cls] = {
            "tp": tp, "fp": fp, "fn": fn, "support": support,
            "precision": round(precision, 4) if precision is not None else None,
            "recall": round(recall, 4) if recall is not None else None,
            "f1": round(f1, 4) if f1 is not None else None,
        }
    return out


def score(truth: list[str], pred: list[str]) -> dict:
    labels = [c for c in RISK_CLASSES if c in set(truth) | set(pred)]
    if NO_DETECTION in pred:
        labels = labels + [NO_DETECTION]
    n = len(truth)
    correct = sum(1 for t, p in zip(truth, pred) if t == p)
    detected = [(t, p) for t, p in zip(truth, pred) if p != NO_DETECTION]
    return {
        "n": n,
        "correct": correct,
        "accuracy": round(correct / n, 4) if n else None,
        "n_no_detection": sum(1 for p in pred if p == NO_DETECTION),
        "n_predicted_high": sum(1 for p in pred if p == "HIGH"),
        "accuracy_detected_only": (
            round(sum(1 for t, p in detected if t == p) / len(detected), 4)
            if detected else None
        ),
        "support": dict(Counter(truth)),
        "predicted": dict(Counter(pred)),
        "confusion_rows_truth_cols_pred": confusion(truth, pred, labels),
        "per_class": per_class_metrics(truth, pred, RISK_CLASSES),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--label", default=os.getenv("EVAL_LABEL", "default"),
                    help="profile name recorded in the report")
    ap.add_argument("--frames-dir", default="outputs/real_data/frames",
                    help="directory the join is reported against")
    ap.add_argument("--limit", type=int, default=0, help="evaluate only N frames (smoke)")
    ap.add_argument("--out", default="", help="optional path to write the JSON report")
    args = ap.parse_args()

    rows = load_rows()
    frames_dir = (REPO_ROOT / args.frames_dir)

    joined, missing, resolved_elsewhere = [], [], {}
    for row in rows:
        resolved = _resolve(row.get("path", ""))
        in_frames_dir = bool(resolved and frames_dir in resolved.parents)
        if in_frames_dir:
            joined.append(row)
        else:
            missing.append(row)
            if resolved is not None:
                parent = str(resolved.parent.relative_to(REPO_ROOT))
                resolved_elsewhere[parent] = resolved_elsewhere.get(parent, 0) + 1

    # Eval set = rows the labeler actually risk-labelled AND whose image exists.
    eval_rows, eval_missing_image = [], 0
    for row in rows:
        if not (row.get("human_risk") or "").strip():
            continue
        if _resolve(row.get("path", "")) is None:
            eval_missing_image += 1
            continue
        eval_rows.append(row)

    if args.limit:
        eval_rows = eval_rows[: args.limit]

    print(
        f"[eval] csv rows={len(rows)} join {args.frames_dir}={len(joined)} "
        f"missing={len(missing)} (elsewhere: {resolved_elsewhere}) | "
        f"labelled eval rows={len(eval_rows)} (labelled w/o image: {eval_missing_image})",
        file=sys.stderr,
    )

    # Import after the join report so a config/import failure still leaves the
    # dataset accounting on stderr.
    import cv2  # noqa: E402
    from yolo_cloud.config import settings  # noqa: E402
    from yolo_cloud.pose_engine import YOLOPoseEngine  # noqa: E402

    engine = YOLOPoseEngine()
    engine.initialize()

    truth, pred, per_row = [], [], []
    t0 = time.perf_counter()
    for idx, row in enumerate(eval_rows):
        image = cv2.imread(str(_resolve(row["path"])))
        if image is None:
            record = {"path": row["path"], "human": row["human_risk"],
                      "predicted": NO_DETECTION, "reason": "unreadable"}
            truth.append(row["human_risk"].strip().upper())
            pred.append(NO_DETECTION)
            per_row.append(record)
            continue
        # Fresh camera_id per frame: tracker / risk-smoothing state must never
        # carry across unrelated stills, so each frame is scored independently.
        processed = engine.process_frame(image, camera_id=f"eval-{idx}")
        best, best_area = None, -1.0
        for pose in processed.tracked_poses:
            x1, y1, x2, y2 = pose.bbox
            area = abs((x2 - x1) * (y2 - y1))
            if area > best_area:
                best, best_area = pose, area
        human = row["human_risk"].strip().upper()
        predicted = best.risk_level if best is not None else NO_DETECTION
        truth.append(human)
        pred.append(predicted)
        per_row.append({
            "path": row["path"],
            "quality": row.get("quality", ""),
            "human": human,
            "predicted": predicted,
            "risk_score": round(best.risk_score, 1) if best is not None else None,
            "task": best.task if best is not None else None,
            "ok": human == predicted,
        })
        if (idx + 1) % 25 == 0:
            print(f"[eval] {idx + 1}/{len(eval_rows)} "
                  f"({(time.perf_counter() - t0):.1f}s)", file=sys.stderr)

    occluded = [i for i, r in enumerate(per_row) if r.get("quality") == "occluded"]

    def subset(indices: list[int]) -> dict:
        return score([truth[i] for i in indices], [pred[i] for i in indices])

    all_idx = list(range(len(truth)))
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "engine": "yolo_cloud (YOLOPoseEngine.process_frame -> yolo_risk_model.pkl)",
        "profile": {
            "label": args.label,
            "yolo_model": settings.YOLO_MODEL,
            "yolo_imgsz": settings.YOLO_IMGSZ,
            "yolo_confidence": settings.YOLO_CONFIDENCE,
            "yolo_device": settings.YOLO_DEVICE,
            "risk_model": os.path.relpath(settings.YOLO_RISK_MODEL, REPO_ROOT),
            "task_model": os.path.relpath(settings.YOLO_TASK_MODEL, REPO_ROOT),
        },
        "dataset": {
            "csv": str(LABELS_CSV.relative_to(REPO_ROOT)),
            "total_rows": len(rows),
            "join_dir": args.frames_dir,
            "joined": len(joined),
            "missing_from_join_dir": len(missing),
            "resolved_elsewhere": resolved_elsewhere,
            "resolvable_total": len(rows) - sum(
                1 for r in missing if _resolve(r.get("path", "")) is None
            ),
            "labelled_rows": sum(1 for r in rows if (r.get("human_risk") or "").strip()),
            "labelled_without_image": eval_missing_image,
            "eval_n": len(truth),
            "label_counts": dict(Counter(truth)),
            "quality_counts": dict(Counter(r.get("quality", "") for r in per_row)),
            "occluded_n": len(occluded),
            "sources": dict(Counter(
                str(_resolve(r["path"]).parent.relative_to(REPO_ROOT))
                for r in per_row if _resolve(r["path"])
            )),
        },
        "metrics": {
            "all": subset(all_idx),
            "occluded_excluded": subset([i for i in all_idx if i not in set(occluded)]),
            "join_dir_only": subset([
                i for i in all_idx
                if per_row[i]["path"].replace(chr(92), "/").startswith(
                    args.frames_dir.replace(chr(92), "/")
                )
            ]),
        },
        "per_row": per_row,
    }
    print("[eval] report follows on stdout (JSON)", file=sys.stderr)
    print(json.dumps(report, indent=2))
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"[eval] wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
