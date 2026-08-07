"""Generate a data-quality report for the REBA-labeled training dataset.

Writes reports/dataset_health_report.md covering per-feature NaN rates and
value ranges, REBA band distribution, rule-risk distribution, and how many
samples have full landmark visibility.

Usage:
    python scripts/report_dataset_health.py [--data data/processed/reba_features.csv] [--out reports/dataset_health_report.md]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.features import FEATURE_COLUMNS  # noqa: E402

# Same feature-exclusion policy as the training scripts (features always NaN
# on COCO-derived keypoints — no finger/feet landmarks). FEATURE_COLUMNS
# already includes the full 17-feature set (core + head/wrist/stance extras).
_ALWAYS_NA_ON_COCO = {"wrist_deviation_angle", "hand_reach_ratio", "finger_spread_ratio", "stance_width_ratio"}
_TRAIN_FEATURES = [c for c in FEATURE_COLUMNS if c not in _ALWAYS_NA_ON_COCO]


def generate(data_path: Path, out_path: Path) -> dict:
    df = pd.read_csv(data_path)
    lines: list[str] = []
    lines.append("# ErgoVigilance — Training Dataset Health Report")
    lines.append("")
    try:
        rel = data_path.resolve().relative_to(ROOT.resolve())
        shown = str(rel)
    except ValueError:
        shown = str(data_path)
    lines.append(f"_Generated {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')} from `{shown}`._")
    lines.append("")

    lines.append("## Overview")
    lines.append("")
    lines.append(f"- **Samples:** {len(df):,}")
    lines.append(f"- **Columns:** {len(df.columns)} ({len([c for c in df.columns if c not in ('source', 'sample_id')])} features + labels)")
    src = df["source"]
    lines.append(f"- **Sources:** {src.nunique():,} distinct H3.6M subjects/sequences, "
                 f"{src.value_counts().iloc[0]:,} max samples per source")
    lines.append("")

    all_feats = [c for c in FEATURE_COLUMNS if c in df.columns and c not in _ALWAYS_NA_ON_COCO]
    lines.append("## Per-feature quality")
    lines.append("")
    lines.append("| feature | NaN rate | min | p25 | median | p75 | max |")
    lines.append("|---|---|---|---|---|---|---|")
    for c in all_feats:
        s = df[c]
        nan_pct = s.isna().mean() * 100
        q = s.quantile([0.25, 0.5, 0.75])
        lines.append(
            f"| {c} | {nan_pct:.1f}% | {np.nanmin(s):.1f} | {q[0.25]:.1f} | {q[0.5]:.1f} | {q[0.75]:.1f} | {np.nanmax(s):.1f} |"
        )
    lines.append("")

    lines.append("## Labels")
    lines.append("")
    lines.append("| band | count | share |")
    lines.append("|---|---|---|")
    for band, count in df["reba_risk_band"].value_counts().sort_index().items():
        lines.append(f"| {band} | {count:,} | {count / len(df) * 100:.1f}% |")
    lines.append("")

    lines.append("## Rule-based risk (for comparison)")
    lines.append("")
    lines.append("| rule_risk | count | share |")
    lines.append("|---|---|---|")
    for risk, count in df["rule_risk"].value_counts().sort_index().items():
        lines.append(f"| {risk} | {count:,} | {count / len(df) * 100:.1f}% |")
    lines.append("")

    core = [c for c in _TRAIN_FEATURES if c in df.columns]
    full_vis = df.dropna(subset=core).shape[0]
    lines.append("## Landmark visibility")
    lines.append("")
    lines.append(f"- **Full trainable-feature visibility** (no NaN across all {len(core)} trainable features): **{full_vis:,}** ({full_vis / len(df) * 100:.1f}%)")
    lines.append(f"- **Partial visibility** (≥1 trainable feature NaN): {len(df) - full_vis:,} ({(len(df) - full_vis) / len(df) * 100:.1f}%)")
    always_na = [c for c in _ALWAYS_NA_ON_COCO if c in df.columns and df[c].isna().mean() == 1.0]
    if always_na:
        lines.append(f"- **Always NaN on COCO-derived keypoints:** {', '.join(always_na)} (no finger/foot landmarks in source data)")
    lines.append("")

    lines.append("## Trainability")
    lines.append("")
    usable = df.dropna(subset=core).shape[0]
    lines.append(f"- **Dropna-safe training rows** (trainable features complete): {usable:,}")
    classes = df["reba_risk_band"].nunique()
    lines.append(f"- **Target classes:** {classes} in the raw REBA band (LOW absent because the dataset's minimum REBA score is 2); the 3-class LOW/MEDIUM/HIGH target used for training is derived in `scripts/train_svm.py::reba_score_to_band` (2-3 LOW, 4-7 MEDIUM, 8+ HIGH) → LOW {sum(df['reba_score'] <= 3):,}, MEDIUM {sum((df['reba_score'] > 3) & (df['reba_score'] <= 7)):,}, HIGH {sum(df['reba_score'] > 7):,}")
    lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"report written: {out_path}")

    return {
        "samples": int(len(df)),
        "full_visibility": int(full_vis),
        "full_visibility_pct": float(full_vis / len(df) * 100),
        "reba_band_counts": {str(k): int(v) for k, v in df["reba_risk_band"].value_counts().items()},
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=ROOT / "data/processed/reba_features.csv")
    ap.add_argument("--out", type=Path, default=ROOT / "reports/dataset_health_report.md")
    args = ap.parse_args()
    summary = generate(args.data, args.out)
    print(summary)
