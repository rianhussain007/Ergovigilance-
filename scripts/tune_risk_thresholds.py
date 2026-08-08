"""Tune the deterministic risk-rule thresholds against the REBA-labeled dataset.

The rule-based ``risk_from_features`` over-alarms: it flags ~80% of poses HIGH
while the REBA-informed band says ~18%. This script runs a vectorized Pareto
search over the secondary-feature cutoffs (weight_shift, shoulder_symmetry,
stance_stability) and reports agreement, Cohen's kappa, HIGH over-alarm, and —
the safety-critical constraint — **missed REBA-HIGH** (REBA HIGH scored LOW).

Result of the last run (30,698 poses):

    baseline (RISK_THRESHOLDS pre-tuning):  agree 34.0%  kappa 0.085  ruleHIGH 80.0%
    tuned (current RISK_THRESHOLDS):        agree 36.9%  kappa 0.107  ruleHIGH 73.5%
    constraint held: 0 REBA-HIGH poses ever scored LOW.

Usage:
    python scripts/tune_risk_thresholds.py [--data data/processed/reba_features.csv]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.features import RISK_THRESHOLDS  # noqa: E402

_BAND_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
_INVERTED = {"knee_angle", "stance_stability"}


def _vectorized_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Feature columns with NaN replaced by the conservative unknown defaults."""
    unk = {
        "neck_flexion": 10.0, "trunk_flexion": 20.0, "shoulder_symmetry": 9.0,
        "knee_angle": 140.0, "forward_head_posture": 10.0, "head_tilt_angle": 10.0,
        "wrist_deviation_angle": 5.0, "stance_stability": 0.6, "weight_shift_offset": 5.0,
    }
    f = pd.DataFrame({
        "sh": df[["left_shoulder_elev", "right_shoulder_elev"]].fillna(0).max(axis=1),
        "neck": df["neck_flexion"].fillna(unk["neck_flexion"]),
        "trunk": df["trunk_flexion"].fillna(unk["trunk_flexion"]),
        "sym": df["shoulder_symmetry"].fillna(unk["shoulder_symmetry"]),
        "knee": df["knee_angle"].fillna(unk["knee_angle"]),
        "fhp": df["forward_head_posture"].fillna(unk["forward_head_posture"]),
        "ht": df["head_tilt_angle"].fillna(unk["head_tilt_angle"]),
        "wd": df["wrist_deviation_angle"].fillna(unk["wrist_deviation_angle"]),
        "st": df["stance_stability"].fillna(unk["stance_stability"]),
        "ws": df["weight_shift_offset"].fillna(unk["weight_shift_offset"]),
    })
    return f


def apply_thresholds(df: pd.DataFrame, t: dict) -> pd.Series:
    """Recompute rule_risk with a full threshold dict (see RISK_THRESHOLDS shape)."""
    f = _vectorized_columns(df)
    high = pd.Series(False, index=df.index)
    med = pd.Series(False, index=df.index)
    for feat, (med_cut, high_cut) in t.items():
        col = "sh" if feat == "shoulder_elev" else feat
        if feat in _INVERTED:
            high |= f[col] < high_cut
            med |= f[col] < med_cut
        else:
            high |= f[col] > high_cut
            med |= f[col] > med_cut
    return pd.Series(np.where(high, "HIGH", np.where(med, "MEDIUM", "LOW")), index=df.index)


def evaluate(df: pd.DataFrame, rule_risk: pd.Series) -> dict:
    yt = df["reba_risk_band"].map(_BAND_ORDER).values
    yp = rule_risk.map(_BAND_ORDER).values
    rh_idx = (df["reba_risk_band"] == "HIGH").values
    return {
        "agreement_pct": float((yt == yp).mean() * 100),
        "kappa": float(cohen_kappa_score(yt, yp, labels=[0, 1, 2])),
        "rule_high_pct": float((yp == 2).mean() * 100),
        "missed_reba_high": int(((yp == 0) & rh_idx).sum()),
        "downgraded_reba_high": int(((yp != 2) & rh_idx).sum()),
        "n": int(len(df)),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "data" / "processed" / "reba_features.csv"))
    args = ap.parse_args()

    df = pd.read_csv(args.data)
    df = df.dropna(subset=["reba_risk_band", "rule_risk"])
    print(f"Loaded {len(df)} REBA-labeled poses from {args.data}\n")

    base = evaluate(df, apply_thresholds(df, RISK_THRESHOLDS))
    print("=== CURRENT (tuned) RISK_THRESHOLDS ===")
    print(f"  agreement:      {base['agreement_pct']:.1f}%   kappa: {base['kappa']:.3f}")
    print(f"  rule HIGH:      {base['rule_high_pct']:.1f}%   (REBA HIGH: {df['reba_risk_band'].eq('HIGH').mean() * 100:.1f}%)")
    print(f"  missed REBA-HIGH (scored LOW): {base['missed_reba_high']}   downgraded (not HIGH): {base['downgraded_reba_high']}")

    print("\n=== PARETO SWEEP (weight_shift / symmetry / stance, missed==0) ===")
    print(f"{'agree%':>6} {'kappa':>6} {'ruleHIGH%':>8} {'down':>5} | ws H/M | sym H/M | stance H/M")
    results = []
    for ws_h in [20, 25, 30, 35, 40]:
        for sym_h in [15, 18, 20, 22, 25, 28, 30]:
            for st_h in [0.40, 0.45, 0.50]:
                cand = dict(RISK_THRESHOLDS)
                cand["weight_shift_offset"] = (ws_h / 2, ws_h)
                cand["shoulder_symmetry"] = (max(5.0, sym_h / 2), sym_h)
                cand["stance_stability"] = (st_h + 0.20, st_h)
                m = evaluate(df, apply_thresholds(df, cand))
                results.append((m, ws_h, sym_h, st_h))
    safe = [r for r in results if r[0]["missed_reba_high"] == 0]
    by_down = {}
    for m, ws_h, sym_h, st_h in safe:
        key = (m["downgraded_reba_high"] // 50) * 50
        if key not in by_down or m["agreement_pct"] > by_down[key][0]["agreement_pct"]:
            by_down[key] = (m, ws_h, sym_h, st_h)
    for key in sorted(by_down):
        m, ws_h, sym_h, st_h = by_down[key]
        print(
            f"{m['agreement_pct']:>6.1f} {m['kappa']:>6.3f} {m['rule_high_pct']:>7.1f}% "
            f"{m['downgraded_reba_high']:>5d} | {ws_h:.0f}/{ws_h/2:.0f} | {sym_h:.0f}/{max(5.0, sym_h/2):.0f} | {st_h:.2f}/{st_h+0.20:.2f}"
        )
    if safe:
        best = max(safe, key=lambda r: r[0]["agreement_pct"])
        print(f"\nOverall best safe config: agree {best[0]['agreement_pct']:.1f}% "
              f"ws>{best[1]} sym>{best[2]} stance<{best[3]} (missed HIGH = 0)")


if __name__ == "__main__":
    main()
