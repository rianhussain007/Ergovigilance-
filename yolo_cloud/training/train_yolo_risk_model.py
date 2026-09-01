"""Train YOLO-specific risk classifier on COCO_17 features.

Uses HistGradientBoostingClassifier (supports NaN natively) to predict
LOW/MEDIUM/HIGH risk from YOLO pose keypoints. This replaces the
hardcoded RULA/REBA thresholds in pose_engine.py with a data-driven model.

Usage:
    python -m yolo_cloud.training.train_yolo_risk_model
    python -m yolo_cloud.training.train_yolo_risk_model --data data/processed/yolo_features.csv
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import StratifiedKFold, train_test_split

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.core.constants import FEATURE_COLUMNS  # noqa: E402

# Features that are always NaN on COCO_17 (no finger landmarks)
_ALWAYS_NA_ON_COCO = {
    "wrist_deviation_angle",
    "hand_reach_ratio",
    "finger_spread_ratio",
    "stance_width_ratio",
}

TRAINABLE_FEATURES = [c for c in FEATURE_COLUMNS if c not in _ALWAYS_NA_ON_COCO]

CLASSES = ["LOW", "MEDIUM", "HIGH"]


def load_data(csv_path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Load features and labels from the YOLO feature CSV."""
    import csv as csv_mod

    features = []
    labels = []

    with open(csv_path) as f:
        reader = csv_mod.DictReader(f)
        for row in reader:
            label = row.get("risk_label", "").strip()
            if label not in CLASSES:
                continue

            feat = []
            for col in TRAINABLE_FEATURES:
                val = row.get(col, "nan")
                try:
                    feat.append(float(val))
                except (ValueError, TypeError):
                    feat.append(float("nan"))
            features.append(feat)
            labels.append(label)

    X = np.array(features, dtype=float)
    y = np.array(labels)

    print(f"Loaded {len(X)} samples from {csv_path}")
    print(f"  Features: {len(TRAINABLE_FEATURES)} (excluded {len(_ALWAYS_NA_ON_COCO)} always-NaN)")
    from collections import Counter
    print(f"  Labels: {dict(Counter(y))}")

    return X, y


def train(
    X: np.ndarray,
    y: np.ndarray,
    output_path: Path,
    n_folds: int = 5,
    seed: int = 42,
) -> dict[str, Any]:
    """Train risk classifier with cross-validation and save the best model."""
    print(f"\nTraining YOLO risk classifier ({n_folds}-fold CV)...")
    print(f"  Samples: {len(X)}")
    print(f"  Features: {X.shape[1]}")

    # Split for final holdout evaluation
    stratify = y if min(np.bincount(np.searchsorted(CLASSES, y))) >= 2 else None
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=seed, stratify=stratify
    )

    # Cross-validation to assess generalization
    skf = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=seed)
    fold_scores = []

    for fold_idx, (train_idx, val_idx) in enumerate(skf.split(X, y)):
        X_fold_train, X_fold_val = X[train_idx], X[val_idx]
        y_fold_train, y_fold_val = y[train_idx], y[val_idx]

        model = HistGradientBoostingClassifier(
            max_iter=200,
            learning_rate=0.1,
            max_depth=6,
            min_samples_leaf=20,
            l2_regularization=1.0,
            random_state=seed + fold_idx,
            class_weight="balanced",
        )
        model.fit(X_fold_train, y_fold_train)
        y_pred = model.predict(X_fold_val)
        score = f1_score(y_fold_val, y_pred, average="weighted")
        fold_scores.append(score)
        print(f"  Fold {fold_idx + 1}: F1={score:.4f}")

    mean_f1 = np.mean(fold_scores)
    std_f1 = np.std(fold_scores)
    print(f"\n  CV F1: {mean_f1:.4f} ± {std_f1:.4f}")

    # Train final model on full training set
    print("\nTraining final model on full dataset...")
    final_model = HistGradientBoostingClassifier(
        max_iter=300,
        learning_rate=0.08,
        max_depth=6,
        min_samples_leaf=15,
        l2_regularization=1.0,
        random_state=seed,
        class_weight="balanced",
    )
    final_model.fit(X, y)

    # Evaluate on holdout
    y_pred = final_model.predict(X_test)
    test_acc = accuracy_score(y_test, y_pred)
    test_f1 = f1_score(y_test, y_pred, average="weighted")

    print(f"\nHoldout test accuracy: {test_acc:.4f}")
    print(f"Holdout test F1:       {test_f1:.4f}")
    print(f"\nClassification report:")
    print(classification_report(y_test, y_pred, labels=CLASSES))

    cm = confusion_matrix(y_test, y_pred, labels=CLASSES)
    print("Confusion matrix:")
    print(f"  {'':>8s}  Pred LOW  Pred MED  Pred HIGH")
    for i, label in enumerate(CLASSES):
        print(f"  {label:>8s}  {cm[i][0]:>7d}  {cm[i][1]:>7d}  {cm[i][2]:>7d}")

    # Feature importance (HistGradientBoosting uses feature_importances_)
    if hasattr(final_model, "feature_importances_"):
        importances = final_model.feature_importances_
        print("\nTop 10 features by importance:")
        sorted_idx = np.argsort(importances)[::-1]
        for i in sorted_idx[:10]:
            print(f"  {TRAINABLE_FEATURES[i]:>30s}: {importances[i]:.4f}")
    else:
        print("\n(Feature importance not available for this model type)")

    # Save model + metadata
    output_path.parent.mkdir(parents=True, exist_ok=True)
    bundle = {
        "model": final_model,
        "features": TRAINABLE_FEATURES,
        "classes": CLASSES,
        "metrics": {
            "cv_f1_mean": round(mean_f1, 4),
            "cv_f1_std": round(std_f1, 4),
            "test_accuracy": round(test_acc, 4),
            "test_f1": round(test_f1, 4),
            "n_samples": len(X),
            "n_features": X.shape[1],
        },
        "confusion_matrix": cm.tolist(),
    }
    joblib.dump(bundle, output_path)
    print(f"\nModel saved to {output_path}")

    return {
        "cv_f1_mean": mean_f1,
        "cv_f1_std": std_f1,
        "test_accuracy": test_acc,
        "test_f1": test_f1,
        "n_samples": len(X),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Train YOLO risk classifier")
    ap.add_argument("--data", type=Path,
                    default=ROOT / "data/processed/yolo_features.csv")
    ap.add_argument("--output", type=Path,
                    default=ROOT / "models/yolo_risk_model.pkl")
    ap.add_argument("--folds", type=int, default=5)
    args = ap.parse_args()

    X, y = load_data(args.data)
    metrics = train(X, y, args.output, n_folds=args.folds)

    # Save metrics summary
    metrics_path = args.output.parent / "yolo_risk_metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"Metrics saved to {metrics_path}")
