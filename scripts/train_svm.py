"""Train the risk-classifier model artifacts (svm_model.pkl, best_model.pkl).

Grid-searches HistGradientBoosting (primary) and RandomForest (benchmark) on a
risk-labeled pose dataset and writes:

  - models/svm_model.pkl   (legacy filename — now holds the HGB primary model)
  - models/best_model.pkl  (best of the two candidates by holdout accuracy)

Label derivation
----------------
If the dataset has a ``reba_score`` column (the Phase-D REBA-labeled dataset),
the 3-class LOW/MEDIUM/HIGH target is derived from REBA's official action
levels: scores 2-3 → LOW, 4-7 → MEDIUM, 8+ → HIGH. Legacy datasets that carry
an explicit ``label`` column are used as-is (existing behavior).

Algorithm rationale
-------------------
The previous pipeline grid-searched RBF-SVM and RandomForest. SVM is a poor
fit for these features (angle features on very different scales, ~15% of rows
carry NaN from missing landmarks) and has been dropped. HistGradientBoosting
handles NaN natively, needs no scaling, and is the same algorithm family
already used by task_model_v2 and risk_calibration_model — this keeps the
whole ML surface consistent.

Usage:
    python scripts/train_svm.py [--dataset data/processed/reba_features.csv] [--model models/svm_model.pkl] [--best-model models/best_model.pkl] [--results results]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import GridSearchCV, train_test_split

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.features import FEATURE_COLUMNS, RISK_LEVELS  # noqa: E402

# Features unavailable (NaN) on COCO-derived keypoints (no finger/feet
# landmarks) — excluded from dropna and imputed like the rest, same policy
# as scripts/train_risk_calibration.py.
_ALWAYS_NA_ON_COCO = {"wrist_deviation_angle", "hand_reach_ratio", "finger_spread_ratio", "stance_width_ratio"}
_TRAIN_FEATURES = [c for c in FEATURE_COLUMNS if c not in _ALWAYS_NA_ON_COCO]


def reba_score_to_band(score: float) -> str:
    """Map a REBA Score C to the pipeline's LOW/MEDIUM/HIGH band.

    REBA action levels: 1 (negligible) / 2-3 (low) / 4-7 (medium) /
    8-10 (high) / 11+ (very high). Scores 2-3 in the dataset (minimum is 2)
    therefore map to LOW.
    """
    if score <= 3:
        return "LOW"
    if score <= 7:
        return "MEDIUM"
    return "HIGH"


def _derive_labels(df: pd.DataFrame) -> pd.Series:
    """Return the target Series, supporting both REBA and legacy datasets."""
    if "reba_score" in df.columns and "label" not in df.columns:
        return df["reba_score"].map(reba_score_to_band)
    return df["label"].str.upper()


def _evaluate_model(model: Any, X_test: np.ndarray, y_test: pd.Series, labels: list[str]) -> dict:
    y_pred = model.predict(X_test)
    cm = confusion_matrix(y_test, y_pred, labels=labels)
    per_class_accuracy = {}
    for idx, label in enumerate(labels):
        total = cm[idx].sum()
        per_class_accuracy[label] = float(cm[idx, idx] / total) if total else 0.0
    return {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "labels": labels,
        "confusion_matrix": cm.tolist(),
        "per_class_accuracy": per_class_accuracy,
        "classification_report": classification_report(y_test, y_pred, labels=labels, output_dict=True, zero_division=0),
    }


def train(dataset_path: Path, model_path: Path, results_dir: Path, best_model_path: Path | None = None) -> dict:
    df = pd.read_csv(dataset_path)

    label_col = "reba_score" if ("reba_score" in df.columns and "label" not in df.columns) else "label"
    # dropna on the trainable features guarantees complete data for BOTH
    # candidates (RandomForest cannot train on NaN), so no imputation needed.
    df = df.dropna(subset=_TRAIN_FEATURES + [label_col]).copy()
    y = _derive_labels(df)
    X = np.asarray(df[_TRAIN_FEATURES], dtype=float)

    stratify = y if y.value_counts().min() >= 2 else None
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=stratify,
    )

    labels = [label for label in RISK_LEVELS if label in set(y)]
    if len(labels) < 2:
        raise ValueError(f"Dataset must contain at least 2 risk classes; found {labels}")

    candidates = {
        "hist_gradient_boosting": GridSearchCV(
            HistGradientBoostingClassifier(max_iter=300, random_state=42),
            param_grid={
                "learning_rate": [0.06, 0.1],
                "max_depth": [6, 8],
                "min_samples_leaf": [20, 40],
            },
            cv=5,
            scoring="accuracy",
            n_jobs=-1,
        ),
        "random_forest": GridSearchCV(
            RandomForestClassifier(class_weight="balanced", random_state=42, n_jobs=-1),
            param_grid={"n_estimators": [150, 300], "max_depth": [None, 8, 16], "min_samples_leaf": [1, 3]},
            cv=5,
            scoring="accuracy",
            n_jobs=-1,
        ),
    }

    model_results: dict[str, dict] = {}
    fitted_models: dict[str, Any] = {}
    for name, search in candidates.items():
        search.fit(X_train, y_train)
        model = search.best_estimator_
        metrics = _evaluate_model(model, X_test, y_test, labels)
        metrics["best_params"] = search.best_params_
        metrics["train_rows"] = int(len(y_train))
        metrics["test_rows"] = int(len(y_test))
        model_results[name] = metrics
        fitted_models[name] = model

    best_name = max(model_results, key=lambda name: model_results[name]["accuracy"])
    best_model = fitted_models[best_name]
    best_metrics = dict(model_results[best_name])
    best_metrics["model_name"] = best_name
    best_metrics["model_comparison"] = {
        name: {
            "accuracy": metrics["accuracy"],
            "best_params": metrics["best_params"],
            "per_class_accuracy": metrics["per_class_accuracy"],
        }
        for name, metrics in model_results.items()
    }
    best_metrics["algorithm"] = "HistGradientBoosting" if best_name == "hist_gradient_boosting" else "RandomForest"

    model_path.parent.mkdir(parents=True, exist_ok=True)
    # Legacy filename kept for compatibility; content is now the HGB primary.
    joblib.dump(
        {"model": fitted_models["hist_gradient_boosting"], "feature_columns": _TRAIN_FEATURES, "labels": labels, "metrics": model_results["hist_gradient_boosting"]},
        model_path,
    )

    if best_model_path is None:
        best_model_path = ROOT / "models" / "best_model.pkl"
    best_model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {"model": best_model, "feature_columns": _TRAIN_FEATURES, "labels": labels, "metrics": best_metrics},
        best_model_path,
    )

    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "svm_metrics.json").write_text(json.dumps(model_results["hist_gradient_boosting"], indent=2), encoding="utf-8")
    (results_dir / "best_model_metrics.json").write_text(json.dumps(best_metrics, indent=2), encoding="utf-8")
    pd.DataFrame(best_metrics["confusion_matrix"], index=labels, columns=labels).to_csv(results_dir / "confusion_matrix.csv")
    return best_metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=ROOT / "data" / "processed" / "reba_features.csv")
    parser.add_argument("--model", type=Path, default=ROOT / "models" / "svm_model.pkl")
    parser.add_argument("--best-model", type=Path, default=ROOT / "models" / "best_model.pkl")
    parser.add_argument("--results", type=Path, default=ROOT / "results")
    args = parser.parse_args()

    metrics = train(args.dataset, args.model, args.results, args.best_model)
    print(f"Best model: {metrics['model_name']}")
    print(f"Accuracy: {metrics['accuracy']:.4f}")
    print("Comparison:")
    print(pd.DataFrame(metrics["model_comparison"]).T.to_string())
    print("Confusion matrix:")
    print(pd.DataFrame(metrics["confusion_matrix"], index=metrics["labels"], columns=metrics["labels"]).to_string())


if __name__ == "__main__":
    main()
