"""Build the labeling queue covering every extracted frame.

The labeling tool (scripts/label_tool.py) previously only queued frames that
had rows in real_features.csv (~46 usable). This script merges every extracted
frame from outputs/real_data/frames and frames_diverse/ with its auto-predicted
task/risk/confidence (from real_features.csv and diverse_extracted_features.csv)
into a single label_queue.csv, sorted so HIGH-risk frames come first — the
biggest ground-truth gap is the missing HIGH class.

Usage:
    python scripts/build_label_queue.py
Output:
    outputs/real_data/label_queue.csv
"""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "outputs" / "real_data"

RISK_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "Unknown": 3, "": 3}


def load_rows(csv_path: Path) -> dict[str, dict]:
    rows = {}
    if not csv_path.exists():
        return rows
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            frame = (row.get("frame") or "").strip()
            if frame:
                rows[frame] = row
    return rows


def main() -> None:
    frames_csv = load_rows(DATA / "real_features.csv")
    diverse_csv = load_rows(DATA / "diverse_extracted_features.csv")

    queue: list[dict] = []
    seen: set[str] = set()

    for subdir in ("frames", "frames_diverse"):
        d = DATA / subdir
        if not d.is_dir():
            continue
        for img in sorted(d.glob("*.jpg")):
            name = img.name
            if name in seen:
                continue
            seen.add(name)
            src = frames_csv if subdir == "frames" else diverse_csv
            row = src.get(name, {})
            queue.append({
                "subdir": subdir,
                "frame": name,
                "video": (row.get("video") or "").strip(),
                "task_label": (row.get("task_label") or "Unknown").strip() or "Unknown",
                "risk_level": (row.get("risk_level") or "LOW").strip() or "LOW",
                "confidence": float(row.get("confidence", 0) or 0),
            })

    # Sort so the rarest/most valuable labels come first: HIGH risk, then
    # MEDIUM, then LOW, and within a risk tier the most confident frames first.
    queue.sort(key=lambda r: (RISK_ORDER.get(r["risk_level"], 3), -r["confidence"]))

    out = DATA / "label_queue.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["subdir", "frame", "video", "task_label", "risk_level", "confidence"])
        writer.writeheader()
        writer.writerows(queue)

    from collections import Counter
    risks = Counter(r["risk_level"] for r in queue)
    print(f"Wrote {len(queue)} frames to {out}")
    print("Risk breakdown:", dict(risks))


if __name__ == "__main__":
    main()