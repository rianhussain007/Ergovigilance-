"""Regression tests for the REBA-tuned risk-rule thresholds.

Pins two properties of the tuned RISK_THRESHOLDS against the 30,698-pose
REBA-labeled dataset (data/processed/reba_features.csv):

1. **Safety**: no REBA-HIGH pose may ever be scored LOW by the rules.
2. **Agreement floor**: exact-band agreement >= 36% (baseline pre-tuning 34%),
   so a future threshold "improvement" that secretly reverts to over-alarm
   fails CI.

The CSV ships with the repo, so the checks run deterministically offline —
no MediaPipe or model files required.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest
from sklearn.metrics import cohen_kappa_score

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.services.features import risk_from_features  # noqa: E402

_BAND_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}

_DATA = ROOT / "data" / "processed" / "reba_features.csv"


@pytest.fixture(scope="module")
def dataset() -> pd.DataFrame:
    if not _DATA.exists():
        pytest.skip("REBA-labeled dataset not present (data/processed/reba_features.csv)")
    df = pd.read_csv(_DATA).dropna(subset=["reba_risk_band", "rule_risk"])
    return df


def _apply_rules(df: pd.DataFrame) -> pd.Series:
    rows = []
    for _, r in df.iterrows():
        feats = {
            "neck_flexion": r["neck_flexion"],
            "trunk_flexion": r["trunk_flexion"],
            "left_shoulder_elev": r["left_shoulder_elev"],
            "right_shoulder_elev": r["right_shoulder_elev"],
            "shoulder_symmetry": r["shoulder_symmetry"],
            "knee_angle": r["knee_angle"],
            "forward_head_posture": r["forward_head_posture"],
            "head_tilt_angle": r["head_tilt_angle"],
            "wrist_deviation_angle": r["wrist_deviation_angle"],
            "stance_stability": r["stance_stability"],
            "weight_shift_offset": r["weight_shift_offset"],
        }
        rows.append(risk_from_features(feats))
    return pd.Series(rows)


def test_zero_missed_reba_high(dataset: pd.DataFrame) -> None:
    """The tuned rules must never score a REBA-HIGH pose as LOW."""
    rule = _apply_rules(dataset)
    reba_high = dataset.loc[dataset["reba_risk_band"] == "HIGH", :]
    missed = (rule.loc[reba_high.index] == "LOW").sum()
    assert missed == 0, f"{missed} REBA-HIGH poses were scored LOW by the rules"


def test_agreement_floor(dataset: pd.DataFrame) -> None:
    """Exact-band agreement with the REBA band stays >= 36% (tuned, up from 34%)."""
    rule = _apply_rules(dataset)
    yt = dataset["reba_risk_band"].map(_BAND_ORDER).values
    yp = rule.map(_BAND_ORDER).values
    agree = float((yt == yp).mean() * 100)
    assert agree >= 36.0, f"rule/REBA agreement dropped to {agree:.1f}% (< 36%)"


def test_kappa_floor(dataset: pd.DataFrame) -> None:
    """Cohen's kappa stays >= 0.10 (tuned: 0.107, baseline: 0.085)."""
    rule = _apply_rules(dataset)
    yt = dataset["reba_risk_band"].map(_BAND_ORDER).values
    yp = rule.map(_BAND_ORDER).values
    kappa = float(cohen_kappa_score(yt, yp, labels=[0, 1, 2]))
    assert kappa >= 0.10, f"kappa dropped to {kappa:.3f} (< 0.10)"


def test_threshold_shape() -> None:
    """Every threshold entry has (MEDIUM, HIGH) cutoffs with sane ordering."""
    from backend.services.features import RISK_THRESHOLDS

    for feat, (med, high) in RISK_THRESHOLDS.items():
        if feat in {"knee_angle", "stance_stability"}:
            assert med > high, f"{feat}: inverted feature must have MED > HIGH cutoffs"
        else:
            assert med < high, f"{feat}: MEDIUM cutoff must be below HIGH cutoff"
