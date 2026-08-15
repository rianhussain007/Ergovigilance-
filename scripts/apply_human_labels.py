"""Apply human labels from a template CSV and evaluate against the model.

Bridges ``scripts/label_frames.py --export-frames`` (which produces a
``frames_manifest.json`` + PNGs + this repo's ``label_template.csv``) and
``scripts/evaluate_ground_truth.py``.

The template CSV has columns::

    frame,png,predicted_label,human_label
    0,frame_000000.png,LOW,
    45,frame_000045.png,MEDIUM,
    ...

A human reviews the PNGs (or the contact sheet) and fills ``human_label`` with
LOW / MEDIUM / HIGH. Rows left blank are skipped. This script validates the
values, writes the guide-format ``ground_truth_risk.json`` (with the labeler's
name and a provenance note that prelabels were the model's own predictions),
then runs the evaluation and prints the honest accuracy figure.

Usage::

    # 1. Fill outputs/ground_truth/<session>/label_template.csv (human step)

    # 2. One command -> ground_truth_risk.json + results/ground_truth_evaluation.json
    venv/Scripts/python.exe scripts/apply_human_labels.py \\
        --template outputs/ground_truth/20260814_201348/label_template.csv \\
        --labeler "Your Name" --fps 15
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALID = {"LOW", "MEDIUM", "HIGH"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", required=True, help="label_template.csv path")
    parser.add_argument("--labeler", required=True, help="Annotator name (provenance)")
    parser.add_argument("--out", help="ground_truth_risk.json path (default: next to template)")
    parser.add_argument("--session-id", help="Session id override (default: manifest.session_id)")
    parser.add_argument("--fps", type=float, default=None,
                        help="Recording fps (frame->time). Default: the bundle's "
                             "frames_manifest.json fps.")
    parser.add_argument("--timeline", help="timeline.json path (default: recording dir next to manifest)")
    parser.add_argument("--eval-out", help="Evaluation JSON path (default: results/ground_truth_evaluation.json)")
    parser.add_argument("--skip-eval", action="store_true", help="Only write ground_truth_risk.json")
    args = parser.parse_args()

    tpl = Path(args.template)
    if not tpl.exists():
        sys.exit(f"Template not found: {tpl}")
    bundle = tpl.parent

    # Session metadata from the bundle's manifest
    manifest_path = bundle / "frames_manifest.json"
    session_id = args.session_id
    fps = args.fps
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        session_id = session_id or manifest.get("session_id", "")
        if fps is None:
            fps = float(manifest.get("fps") or 0.0)  # authoritative (BOM-safe JSON)
        if not args.timeline:
            src = Path(manifest.get("source_video", ""))
            cand = src.parent / "timeline.json"
            args.timeline = str(cand) if cand.exists() else None
    if fps is None:
        fps = 15.0  # last-resort fallback if no manifest and no --fps
    if fps <= 0:
        sys.exit(f"Invalid --fps: {fps} — must be > 0")

    rows: list[dict] = []
    try:
        with tpl.open(newline="", encoding="utf-8-sig") as f:  # -sig strips Excel BOM
            for r in csv.DictReader(f):
                rows.append(r)
    except OSError as exc:
        sys.exit(f"Could not read template {tpl}: {exc}")

    required = {"frame", "human_label"}
    if rows and not required.issubset(rows[0].keys()):
        sys.exit(f"Template is missing required columns {sorted(required)} — "
                 f"found {sorted(rows[0].keys())}")

    labeled: dict[int, str] = {}
    skipped_blank = 0
    skipped_nopred = 0
    for r in rows:
        human = (r.get("human_label") or "").strip().upper()
        if not human:
            skipped_blank += 1
            continue
        if not (r.get("predicted_label") or "").strip():
            skipped_nopred += 1  # no model prediction to compare against — keep for GT
        try:
            frame = int(r["frame"])
        except (ValueError, TypeError):
            sys.exit(f"Non-numeric frame value {r.get('frame')!r} in template")
        if human not in VALID:
            sys.exit(f"Invalid label '{human}' on frame {frame} — expected {sorted(VALID)}")
        if frame in labeled:
            print(f"Warning: duplicate frame {frame} in template — keeping the last row")
        labeled[frame] = human

    if not labeled:
        sys.exit("No human labels filled in the template yet — nothing to write.")

    print(f"Rows: {len(rows)} | human-labeled: {len(labeled)} | blank skipped: "
          f"{skipped_blank} | no-prediction (kept): {skipped_nopred}")

    out = Path(args.out) if args.out else bundle / "ground_truth_risk.json"
    gt = {
        "session_id": session_id,
        "labeler": args.labeler,
        "date": date.today().isoformat(),
        "prelabel_source": "label_template.csv predicted_label column "
                           "(model predictions — human reviewed and confirmed/overridden)",
        "frames": [{"frame": int(f), "label": l} for f, l in sorted(labeled.items())],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(gt, indent=2), encoding="utf-8")
    print(f"Wrote {out} — {len(labeled)} human-labeled frames by {args.labeler}")

    if args.skip_eval:
        return

    if not args.timeline or not Path(args.timeline).exists():
        sys.exit("No timeline.json found for evaluation — pass --timeline explicitly.")

    eval_out = args.eval_out or str(ROOT / "results" / "ground_truth_evaluation.json")
    cmd = [
        sys.executable, str(ROOT / "scripts" / "evaluate_ground_truth.py"),
        "--labels", str(out),
        "--timeline", str(args.timeline),
        "--kind", "risk",
        "--fps", str(fps),
        "--out", eval_out,
    ]
    print("Running:", " ".join(cmd), "\n")
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
