"""Daily pilot metrics collector (TRL-7 plan §4.4 evidence automation).

Reads the newest soak summary + the identity-audit JSONL (+ host disk
free space) and appends one row per day to a CSV ledger (plus a JSON
sidecar). Missing sources yield ``None`` ("n/a") — the script never
crashes and never invents numbers, the same honesty rule as the
evidence pack. Operator-supplied figures (dismiss reasons, restarts)
enter via flags or stay empty for manual fill-in.

Usage:
    python scripts/pilot_metrics.py --date 2026-10-01 \\
        --soak-dir outputs/soak --audit outputs/audit/identity_audit.jsonl \\
        --out docs/pilot/metrics_ledger.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import date as date_cls
from pathlib import Path
from typing import Any, Optional

COLUMNS = [
    "date",
    "clips_saved",
    "clips_truncated",
    "alerts_total",
    "alerts_with_worker_id",
    "fps_mean",
    "frame_dropped_total",
    "frame_drop_rate",
    "p95_latency_ms",
    "id_switches",
    "identity_binds",
    "identity_reentries",
    "distinct_workers",
    "disk_free_gb",
    "compose_restarts",
    "dismiss_reasons",
    "notes",
]


def _num(value: Any) -> Optional[float]:
    """Best-effort number extraction: scalar, or {"mean": x} wrappers."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        for key in ("mean", "overall_drop_rate", "p95", "value"):
            if key in value:
                return _num(value[key])
        return None
    return None


def newest_summary(soak_dir: str | Path) -> Optional[Path]:
    """Newest ``*_summary.json`` under the soak dir, or None."""
    try:
        paths = sorted(Path(soak_dir).glob("*_summary.json"))
    except OSError:
        return None
    return paths[-1] if paths else None


def parse_soak_summary(path: str | Path) -> dict:
    """Extract the §4.4 automation-friendly fields from a soak summary."""
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(doc, dict):
        return {}
    clips = doc.get("clips") or {}
    fps = doc.get("fps_per_stream") or {}
    drops = doc.get("frame_drops") or {}
    latency = doc.get("latency") or {}
    by_stream = latency.get("by_stream") if isinstance(latency, dict) else None
    p95 = None
    if isinstance(by_stream, dict) and by_stream:
        p95s = [
            _num((stream or {}).get("p95"))
            for stream in by_stream.values()
            if isinstance(stream, dict)
        ]
        p95s = [v for v in p95s if v is not None]
        # Worst-stream p95: recorded, not gamed (plan §4.4).
        p95 = max(p95s) if p95s else None
    return {
        "clips_saved": _num(clips.get("saved_total")) if isinstance(clips, dict) else None,
        "clips_truncated": _num(clips.get("truncated_total")) if isinstance(clips, dict) else None,
        "alerts_total": _num(doc.get("alerts_total")),
        "alerts_with_worker_id": _num(doc.get("alerts_with_worker_id")),
        "fps_mean": _num(fps.get("mean")) if isinstance(fps, dict) else _num(fps),
        "frame_dropped_total": _num(drops.get("dropped_frames_total")) if isinstance(drops, dict) else None,
        "frame_drop_rate": _num(drops.get("overall_drop_rate")) if isinstance(drops, dict) else None,
        "p95_latency_ms": p95,
        "id_switches": _num(doc.get("id_switches")),
    }


def parse_identity_audit(path: str | Path, day: str) -> dict:
    """Count bind/reentry events + distinct workers for one ISO date."""
    binds = 0
    reentries = 0
    workers: set[str] = set()
    try:
        handle = open(path, encoding="utf-8")
    except OSError:
        return {"identity_binds": None, "identity_reentries": None, "distinct_workers": None}
    found = False
    with handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            if str(event.get("ts", ""))[:10] != day:
                continue
            found = True
            kind = str(event.get("event", ""))
            if kind == "bind":
                binds += 1
            elif "reentry" in kind or "rebind" in kind:
                reentries += 1
            worker = event.get("worker_id")
            if worker:
                workers.add(str(worker))
    if not found:
        return {"identity_binds": None, "identity_reentries": None, "distinct_workers": None}
    return {
        "identity_binds": binds,
        "identity_reentries": reentries,
        "distinct_workers": len(workers),
    }


def disk_free_gb(path: str | Path = ".") -> Optional[float]:
    """Free space (GB) for the filesystem holding ``path``."""
    try:
        return round(shutil.disk_usage(str(path)).free / (1024**3), 2)
    except OSError:
        return None


def collect(
    day: str,
    soak_dir: str | Path = "outputs/soak",
    audit_path: str | Path = "outputs/audit/identity_audit.jsonl",
    disk_path: str | Path = ".",
    restarts: Optional[int] = None,
    dismiss_reasons: str = "",
    notes: str = "",
) -> dict:
    """Build one ledger row. Every field may be None (= n/a)."""
    summary_path = newest_summary(soak_dir)
    row: dict[str, Any] = {"date": day}
    row.update(parse_soak_summary(summary_path) if summary_path else {})
    row.update(parse_identity_audit(audit_path, day))
    row["disk_free_gb"] = disk_free_gb(disk_path)
    row["compose_restarts"] = restarts
    row["dismiss_reasons"] = dismiss_reasons
    row["notes"] = notes
    return {column: row.get(column) for column in COLUMNS}


def append_csv(csv_path: str | Path, row: dict) -> None:
    """Append a row, creating the ledger with a header when missing."""
    csv_path = Path(csv_path)
    exists = csv_path.exists()
    with open(csv_path, "a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        if not exists:
            writer.writeheader()
        writer.writerow({k: ("" if row.get(k) is None else row.get(k)) for k in COLUMNS})


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Append one daily pilot-metrics row.")
    parser.add_argument("--date", default=date_cls.today().isoformat(), help="ISO day, e.g. 2026-10-01")
    parser.add_argument("--soak-dir", default="outputs/soak")
    parser.add_argument("--audit", default="outputs/audit/identity_audit.jsonl")
    parser.add_argument("--disk-path", default=".")
    parser.add_argument("--restarts", type=int, default=None, help="compose restart count (manual)")
    parser.add_argument("--dismiss-reasons", default="")
    parser.add_argument("--notes", default="")
    parser.add_argument("--out", required=True, help="ledger CSV path")
    parser.add_argument("--json-out", default=None, help="optional JSON sidecar path")
    args = parser.parse_args(argv)

    row = collect(
        args.date,
        soak_dir=args.soak_dir,
        audit_path=args.audit,
        disk_path=args.disk_path,
        restarts=args.restarts,
        dismiss_reasons=args.dismiss_reasons,
        notes=args.notes,
    )
    append_csv(args.out, row)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(row, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in row.items() if v not in (None, "")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
