"""Train the risk-calibration model and generate the calibration report.

Trains a HistGradientBoosting classifier to predict the REBA-informed risk
band (LOW/MEDIUM/HIGH) from the pipeline's 17 features, using the
rebapose-derived labeled dataset (data/processed/reba_features.csv). The
model is a CROSS-CHECK overlay — the deterministic rule-based
``risk_from_features`` stays authoritative at runtime.

Produces:
  - models/risk_calibration_model.pkl   (bundle: model + feature_columns + metrics)
  - reports/risk_calibration_report.md  (rule-vs-REBA agreement + model eval)

Usage:
    python scripts/train_risk_calibration.py [--data data/processed/reba_features.csv] [--out models/risk_calibration_model.pkl] [--report reports/risk_calibration_report.md]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    cohen_kappa_score,
    confusion_matrix,
)
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.features import FEATURE_COLUMNS  # noqa: E402

# Reference/task-signal features that are unavailable (NaN) on COCO-derived
# keypoints (no fingers/feet) — excluded from dropna and imputed like the rest.
_ALWAYS_NA_ON_COCO = {"wrist_deviation_angle", "hand_reach_ratio", "finger_spread_ratio", "stance_width_ratio"}
_TRAIN_FEATURES = [c for c in FEATURE_COLUMNS if c not in _ALWAYS_NA_ON_COCO]

_BANDS = ["LOW", "MEDIUM", "HIGH"]


def _confusion_table(y_true, y_pred, labels):
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    return pd.DataFrame(cm, index=[f"true_{l}" for l in labels], columns=[f"pred_{l}" for l in labels])


def build_report(df: pd.DataFrame, model_metrics: dict, out: Path) -> None:
    lines: list[str] = []
    lines.append("# ErgoVigilance — Risk Calibration Report")
    lines.append("")
    lines.append(f"_Generated {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')} from "
                 f"{len(df)} REBA-labeled real-world poses (rebapose/COCO-derived)._")
    lines.append("")
    lines.append("## Headline: rule-based risk vs REBA-informed risk")
    lines.append("")
    lines.append("The deterministic `risk_from_features` rule system is compared against the "
                 "REBA-informed risk band computed from the same 2D joints (standard REBA "
                 "methodology, 2D projection approximation).")
    lines.append("")
    cm = _confusion_table(df["reba_risk_band"], df["rule_risk"], _BANDS)
    lines.append("### Rule risk (rows) vs REBA band (columns)")
    lines.append("")
    lines.append("| rule \\ reba | " + " | ".join(_BANDS) + " | total |")
    lines.append("|---|---" * len(_BANDS) + "---|")
    for rule in _BANDS:
        row = cm.loc[f"true_{rule}"]
        vals = [str(row.get(f"pred_{b}", 0)) for b in _BANDS]
        total = int(row.sum())
        pct = [f"{(row.get(f'pred_{b}', 0) / max(total, 1)) * 100:.0f}%" for b in _BANDS]
        lines.append(f"| {rule} | " + " | ".join(f"{v} ({p})" for v, p in zip(vals, pct)) + f" | {total} |")
    lines.append("")
    agree = float((df["rule_risk"] == df["reba_risk_band"]).mean() * 100)
    kappa = float(cohen_kappa_score(df["rule_risk"], df["reba_risk_band"], labels=_BANDS))
    lines.append(f"- **Exact band agreement: {agree:.1f}%** (Cohen's κ = {kappa:.3f})")
    lines.append(f"- Rule system flags **{(df['rule_risk'] == 'HIGH').mean() * 100:.0f}%** of poses HIGH; "
                 f"REBA flags **{(df['reba_risk_band'] == 'HIGH').mean() * 100:.0f}%**.")
    lines.append(f"- Rule LOW on {(df['rule_risk'] == 'LOW').sum()} / REBA LOW on "
                 f"{(df['reba_risk_band'] == 'LOW').sum()} samples — the rules are deliberately "
                 "conservative (unknown/NaN features score as elevated risk).")
    lines.append("")
    lines.append("### Per-rule-verdict REBA distribution")
    lines.append("")
    lines.append("| rule_risk | REBA LOW | REBA MEDIUM | REBA HIGH |")
    lines.append("|---|---|---|---|")
    for rule in _BANDS:
        sub = df[df["rule_risk"] == rule]
        counts = {b: int((sub["reba_risk_band"] == b).sum()) for b in _BANDS}
        lines.append(f"| {rule} | {counts['LOW']} | {counts['MEDIUM']} | {counts['HIGH']} |")
    lines.append("")
    lines.append("## Trained calibration model (cross-check overlay)")
    lines.append("")
    acc = model_metrics["accuracy"]
    lines.append(f"- Model: HistGradientBoosting → REBA band, holdout accuracy **{acc * 100:.1f}%**")
    lines.append(f"- Holdout size: {model_metrics['test_size']} samples")
    lines.append("")
    lines.append("### Holdout per-class report")
    lines.append("")
    lines.append("```")
    lines.append(model_metrics["classification_report"])
    lines.append("```")
    lines.append("")
    lines.append("## Interpretation & recommendation")
    lines.append("")
    lines.append("1. The rule system over-alarms on normal-activity poses relative to the "
                 "REBA-informed band — expected for a safety-first design (unknown → elevated), "
                 "but worth a threshold-tuning pass using this dataset before production claims.")
    lines.append("2. The trained model is a **cross-check only**: runtime risk remains "
                 "rule-based; the model confidence can be surfaced as a UI hint.")
    lines.append("3. Feature columns with no signal on COCO-derived keypoints (wrist deviation, "
                 "hand reach, finger spread, stance width) are absent here; a MediaPipe-33 "
                 "capture session of real workplace tasks would fill that gap (Phase-D Tier 2).")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"report written: {out}")


def train(data_path: Path, model_path: Path, report_path: Path) -> dict:
    df = pd.read_csv(data_path)
    print(f"loaded {len(df)} labeled samples")

    # Drop rows missing core joints, impute sparse NaN with column median.
    train_df = df.dropna(subset=_TRAIN_FEATURES).copy()
    print(f"{len(train_df)} samples with complete core features")
    for c in _TRAIN_FEATURES:
        med = train_df[c].median()
        train_df[c] = train_df[c].fillna(med)

    # Fit on a plain numpy array so the pickled estimator has no feature-name
    # requirement (avoids "X does not have valid feature names" warnings at
    # runtime predict time).
    X = np.asarray(train_df[_TRAIN_FEATURES], dtype=float)
    y = train_df["reba_risk_band"]

    stratify = y if y.value_counts().min() >= 2 else None
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=stratify,
    )

    model = HistGradientBoostingClassifier(
        max_iter=300, learning_rate=0.08, max_depth=6,
        min_samples_leaf=20, random_state=42,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "test_size": int(len(y_test)),
        "classification_report": classification_report(y_test, y_pred, labels=_BANDS, zero_division=0),
        "confusion_matrix": confusion_matrix(y_test, y_pred, labels=_BANDS).tolist(),
        "labels": _BANDS,
    }
    print(f"holdout accuracy: {metrics['accuracy'] * 100:.1f}%")

    bundle = {
        "model": model,
        "feature_columns": _TRAIN_FEATURES,
        "labels": _BANDS,
        "metrics": metrics,
        "trained_on": str(data_path),
        "purpose": "Risk calibration cross-check overlay (REBA-informed band). "
                   "Runtime risk stays rule-based; this model is advisory.",
    }
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, model_path)
    print(f"model saved: {model_path}")

    build_report(train_df, metrics, report_path)
    return metrics


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=ROOT / "data/processed/reba_features.csv")
    ap.add_argument("--out", type=Path, default=ROOT / "models/risk_calibration_model.pkl")
    ap.add_argument("--report", type=Path, default=ROOT / "reports/risk_calibration_report.md")
    args = ap.parse_args()
    train(args.data, args.out, args.report)
