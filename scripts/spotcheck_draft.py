#!/usr/bin/env python3
"""Draft the TRL-6 alert spot-check sheet from a soak run's jsonl.

Extracts one review frame per sampled HIGH alert clip and writes a CSV for
HUMAN approval. The ``model_prediction`` column is the system's own output
(it is what is being validated); ``agent_label`` is deliberately left as
PENDING — the agent does not eyeball frames (image reading is unreliable in
this environment), the reviewer fills ``human_label`` and ``approved``.

Usage:
    python scripts/spotcheck_draft.py outputs/soak/soak_<ts>.jsonl \
        [--out outputs/tri6_demo/spotcheck] [--per-camera 3]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone

HIGH_FIELDNAMES = [
    "alert_id", "camera_id", "timestamp_utc", "severity", "task", "risk_score",
    "worker_id", "clip", "frame", "model_prediction", "agent_label",
    "human_label", "approved",
]


def load_high_alerts(jsonl_path: str) -> list[dict]:
    alerts = []
    with open(jsonl_path, "r", encoding="utf-8") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("type") != "alert" or rec.get("severity") != "HIGH":
                continue
            if not (rec.get("clip") or {}).get("path"):
                continue
            alerts.append(rec)
    return alerts


def pick_samples(alerts: list[dict], per_camera: int) -> list[dict]:
    by_cam: dict[str, list[dict]] = defaultdict(list)
    for a in alerts:
        by_cam[a.get("camera_id", "?")].append(a)
    picked = []
    for cam in sorted(by_cam):
        rows = by_cam[cam]
        step = max(1, len(rows) // max(1, per_camera))
        picked.extend(rows[::step][:per_camera])
    return picked


def extract_frame(clip_path: str, out_jpg: str) -> bool:
    # Frame ~0.5 s before the alert (clip is pre-alert, ending at the alert).
    # -sseof is an INPUT option: it must precede -i (ffmpeg >= 6 errors otherwise).
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-sseof", "-0.5",
           "-i", clip_path, "-frames:v", "1", out_jpg]
    try:
        return subprocess.run(cmd, capture_output=True, timeout=60).returncode == 0 \
            and os.path.exists(out_jpg) and os.path.getsize(out_jpg) > 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def fmt_ts(value) -> str:
    """ISO-8601 string or epoch seconds -> uniform UTC string.

    Naive datetimes are system-local (the engine writes local wall time).
    """
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value)
            return (dt if dt.tzinfo else dt.astimezone()).astimezone(
                timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
        except ValueError:
            return value
    return datetime.fromtimestamp(
        float(value or 0), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("jsonl", help="soak run jsonl with type=alert rows")
    ap.add_argument("--out", default=os.path.join("outputs", "tri6_demo", "spotcheck"))
    ap.add_argument("--per-camera", type=int, default=3)
    args = ap.parse_args(argv)

    alerts = load_high_alerts(args.jsonl)
    if not alerts:
        print(f"no HIGH alerts with clips in {args.jsonl}", file=sys.stderr)
        return 1
    sample = pick_samples(alerts, args.per_camera)
    os.makedirs(args.out, exist_ok=True)

    csv_path = os.path.join(args.out, "alerts_spotcheck.csv")
    written = 0
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=HIGH_FIELDNAMES)
        w.writeheader()
        for a in sample:
            clip = a["clip"]["path"]
            frame = os.path.join(args.out, f"{a['alert_id']}.jpg")
            ok = extract_frame(clip, frame)
            w.writerow({
                "alert_id": a.get("alert_id"),
                "camera_id": a.get("camera_id"),
                "timestamp_utc": fmt_ts(a.get("timestamp")),
                "severity": a.get("severity"),
                "task": a.get("task"),
                "risk_score": a.get("risk_score"),
                "worker_id": a.get("worker_id") or "",
                "clip": clip,
                "frame": frame if ok else "",
                "model_prediction": f"{a.get('task')} @ {a.get('risk_score')}",
                "agent_label": "PENDING-USER-APPROVAL",
                "human_label": "",
                "approved": "",
            })
            written += 1
    print(f"drafted {written} rows -> {csv_path} "
          f"(from {len(alerts)} HIGH alerts across "
          f"{len({a.get('camera_id') for a in alerts})} cameras)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
