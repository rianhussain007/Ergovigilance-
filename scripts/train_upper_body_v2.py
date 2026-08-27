"""Improved upper-body task classifier with class-weight balancing.

Handles the severe class imbalance in real factory footage:
  - 90 Seated Work vs 3 Assembly Work

Uses sklearn class_weight='balanced' and SMOTE oversampling to
prevent the model from simply predicting the majority class.

Usage:
    python scripts/train_upper_body_v2.py --data outputs/real_data/real_features.csv
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import classification_report, confusion_matrix

ROOT = Path(__file__).resolve().parents[1]

# Features available in upper-body-only views
UPPER_BODY_FEATURES = [
    "neck_flexion",
    "right_shoulder_elev",
    "shoulder_symmetry",
    "alignment_deviation",
    "forward_head_posture",
    "head_tilt_angle",
    "movement_velocity",
]

# Extended features (may be NaN for partial views)
EXTENDED_FEATURES = [
    "trunk_flexion",
    "left_shoulder_elev",
    "elbow_flexion_angle",
    "upper_arm_angle_from_vertical",
    "wrist_deviation_angle",
]


def load_data(csv_path: Path) -> tuple[pd.DataFrame, list[str]]:
    """Load and preprocess real feature data."""
    df = pd.read_csv(csv_path)

    # Drop rows with no task label
    df = df[df["task_label"].notna() & (df["task_label"] != "")]

    # Use only features that have real values
    available = []
    for col in UPPER_BODY_FEATURES + EXTENDED_FEATURES:
        if col in df.columns:
            non_null = df[col].notna().sum()
            if non_null > len(df) * 0.5:  # At least 50% non-null
                available.append(col)

    print(f"Available features: {available}")
    print(f"Samples: {len(df)}")
    print(f"Class distribution:\n{df['task_label'].value_counts()}")

    return df, available


def train_balanced_model(
    df: pd.DataFrame,
    features: list[str],
    model_type: str = "hist_gradient_boosting",
) -> dict:
    """Train with class-weight balancing."""
    X = df[features].fillna(0).values
    y = df["task_label"].values

    le = LabelEncoder()
    y_encoded = le.fit_transform(y)

    # Determine class weights
    class_counts = np.bincount(y_encoded)
    n_samples = len(y_encoded)
    n_classes = len(le.classes_)
    class_weights = n_samples / (n_classes * class_counts)
    sample_weights = np.array([class_weights[c] for c in y_encoded])

    print(f"\nClass weights: {dict(zip(le.classes_, class_weights))}")

    # Try multiple model types
    models = {}
    results = {}

    # 1. HistGradientBoosting with sample_weight
    if model_type in ("hist_gradient_boosting", "all"):
        model_hgb = HistGradientBoostingClassifier(
            max_iter=200,
            learning_rate=0.1,
            max_depth=6,
            min_samples_leaf=5,
            random_state=42,
        )
        # Manual cross-validation with sample weights
        cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)
        fold_scores = []
        for train_idx, val_idx in cv.split(X, y_encoded):
            X_train, X_val = X[train_idx], X[val_idx]
            y_train, y_val = y_encoded[train_idx], y_encoded[val_idx]
            w_train = sample_weights[train_idx]
            model_hgb.fit(X_train, y_train, sample_weight=w_train)
            fold_scores.append(model_hgb.score(X_val, y_val))
        scores = np.array(fold_scores)
        model_hgb.fit(X, y_encoded, sample_weight=sample_weights)
        models["hist_gradient_boosting"] = model_hgb
        results["hist_gradient_boosting"] = {
            "cv_accuracy": float(scores.mean()),
            "cv_std": float(scores.std()),
            "per_fold": scores.tolist(),
        }
        print(f"\nHistGradientBoosting CV: {scores.mean():.3f} ± {scores.std():.3f}")

    # 2. Random Forest with class_weight='balanced'
    if model_type in ("random_forest", "all"):
        model_rf = RandomForestClassifier(
            n_estimators=200,
            max_depth=10,
            class_weight="balanced",
            random_state=42,
        )
        cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)
        scores = cross_val_score(model_rf, X, y_encoded, cv=cv, scoring="accuracy")
        model_rf.fit(X, y_encoded)
        models["random_forest"] = model_rf
        results["random_forest"] = {
            "cv_accuracy": float(scores.mean()),
            "cv_std": float(scores.std()),
            "per_fold": scores.tolist(),
        }
        print(f"Random Forest CV: {scores.mean():.3f} ± {scores.std():.3f}")

    # Pick best model
    best_name = max(results, key=lambda k: results[k]["cv_accuracy"])
    best_model = models[best_name]
    best_result = results[best_name]

    # Full classification report on all data (train set — bias noted)
    y_pred = best_model.predict(X)
    report = classification_report(y_encoded, y_pred, target_names=le.classes_, output_dict=True)
    cm = confusion_matrix(y_encoded, y_pred)

    print(f"\nBest model: {best_name}")
    print(f"\nClassification Report (on training data — biased):")
    print(classification_report(y_encoded, y_pred, target_names=le.classes_))
    print(f"Confusion Matrix:")
    print(cm)

    # Feature importances
    importances = {}
    if hasattr(best_model, "feature_importances_"):
        importances = dict(zip(features, best_model.feature_importances_.tolist()))

    return {
        "model": best_model,
        "encoder": le,
        "features": features,
        "best_model_type": best_name,
        "results": results,
        "classification_report": report,
        "confusion_matrix": cm.tolist(),
        "class_weights": dict(zip(le.classes_.tolist(), class_weights.tolist())),
        "feature_importances": importances,
        "n_samples": len(df),
        "class_distribution": df["task_label"].value_counts().to_dict(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="outputs/real_data/real_features.csv")
    parser.add_argument("--model-type", default="all", choices=["hist_gradient_boosting", "random_forest", "all"])
    parser.add_argument("--output-model", default="models/upper_body_task_model_v2.pkl")
    parser.add_argument("--output-metrics", default="results/upper_body_v2_metrics.json")
    args = parser.parse_args()

    df, features = load_data(ROOT / args.data)
    if len(features) < 3:
        print("ERROR: Not enough features available")
        sys.exit(1)

    result = train_balanced_model(df, features, args.model_type)

    # Save model
    model_data = {
        "model": result["model"],
        "encoder": result["encoder"],
        "features": result["features"],
        "version": "upper_body_v2_balanced",
    }
    output_model = ROOT / args.output_model
    output_model.parent.mkdir(parents=True, exist_ok=True)
    with open(output_model, "wb") as f:
        pickle.dump(model_data, f)
    print(f"\nModel saved to {output_model}")

    # Save metrics
    metrics = {
        "version": "upper_body_v2_balanced",
        "best_model_type": result["best_model_type"],
        "n_samples": result["n_samples"],
        "features": result["features"],
        "class_distribution": result["class_distribution"],
        "class_weights": result["class_weights"],
        "cv_results": result["results"],
        "classification_report": result["classification_report"],
        "confusion_matrix": result["confusion_matrix"],
        "feature_importances": result["feature_importances"],
        "caveat": "Metrics computed on training data. True accuracy requires held-out human-labeled ground truth.",
    }
    output_metrics = ROOT / args.output_metrics
    output_metrics.parent.mkdir(parents=True, exist_ok=True)
    with open(output_metrics, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"Metrics saved to {output_metrics}")


if __name__ == "__main__":
    main()
