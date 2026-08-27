#!/usr/bin/env python3
"""Train task classifier on diverse web-sourced factory footage.

Usage:
    python scripts/train_diverse_classifier.py --data data/diverse_training_data/training_combined.csv
"""
import argparse
import csv
import json
import pickle
import sys
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, confusion_matrix

ROOT = Path(__file__).resolve().parent.parent


FEATURE_COLS = [
    "neck_flexion", "trunk_flexion",
    "left_shoulder_elev", "right_shoulder_elev",
    "shoulder_symmetry", "alignment_deviation",
    "knee_angle", "forward_head_posture",
    "head_tilt_angle", "wrist_deviation_angle",
    "stance_stability", "weight_shift_offset",
    "body_visibility",
]


def load_data(csv_path):
    """Load training data from CSV."""
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    X, y = [], []
    for row in rows:
        try:
            features = []
            for col in FEATURE_COLS:
                val = row.get(col, "0")
                val = float(val) if val and val != "" else 0.0
                features.append(val)

            task = row.get("task_label", "Neutral Standing")
            if task and task != "":
                X.append(features)
                y.append(task)
        except (ValueError, KeyError):
            continue

    return np.array(X, dtype=np.float32), np.array(y)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=str(ROOT / "data" / "diverse_training_data" / "training_combined.csv"))
    parser.add_argument("--output", default=str(ROOT / "models" / "diverse_task_model.pkl"))
    args = parser.parse_args()

    print(f"Loading data from {args.data}")
    X, y = load_data(args.data)
    print(f"Loaded {len(X)} samples with {len(FEATURE_COLS)} features")

    # Encode labels
    le = LabelEncoder()
    y_encoded = le.fit_transform(y)

    print(f"\nTask classes: {list(le.classes_)}")
    print(f"Samples per class:")
    for cls in le.classes_:
        count = np.sum(y_encoded == le.transform([cls])[0])
        print(f"  {cls}: {count}")

    # Train with cross-validation
    print(f"\nTraining HistGradientBoosting with 5-fold CV...")
    clf = HistGradientBoostingClassifier(
        max_iter=200,
        max_depth=6,
        learning_rate=0.1,
        min_samples_leaf=5,
        random_state=42,
    )

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    scores = cross_val_score(clf, X, y_encoded, cv=cv, scoring="accuracy")
    print(f"CV Accuracy: {scores.mean():.1%} (+/- {scores.std():.1%})")
    print(f"Per-fold: {[f'{s:.1%}' for s in scores]}")

    # Train on all data
    clf.fit(X, y_encoded)

    # Full training accuracy
    train_pred = clf.predict(X)
    train_acc = np.mean(train_pred == y_encoded)
    print(f"\nTraining accuracy: {train_acc:.1%}")

    # Classification report
    y_pred = clf.predict(X)
    print(f"\nClassification Report (training set):")
    print(classification_report(y_encoded, y_pred, target_names=le.classes_))

    # Confusion matrix
    cm = confusion_matrix(y_encoded, y_pred)
    print("Confusion Matrix:")
    for i, cls in enumerate(le.classes_):
        print(f"  {cls:20s}: {cm[i]}")

    # Feature importances (HistGradientBoosting doesn't expose importances directly)
    print("\nFeature analysis (per-class mean values):")
    for i, cls in enumerate(le.classes_):
        cls_mask = y_encoded == i
        cls_mean = X[cls_mask].mean(axis=0)
        print(f"\n  {cls}:")
        for feat, val in sorted(zip(FEATURE_COLS, cls_mean), key=lambda x: -abs(x[1])):
            if abs(val) > 0.01:
                print(f"    {feat:25s}: {val:.2f}")

    # Save model
    model_data = {
        "model": clf,
        "label_encoder": le,
        "feature_cols": FEATURE_COLS,
        "version": "diverse_v1",
        "cv_accuracy": float(scores.mean()),
        "cv_std": float(scores.std()),
        "train_accuracy": float(train_acc),
        "n_samples": len(X),
        "n_classes": len(le.classes_),
        "classes": list(le.classes_),
        "class_distribution": {cls: int(np.sum(y_encoded == le.transform([cls])[0])) for cls in le.classes_},
        "training_data": args.data,
    }

    with open(args.output, "wb") as f:
        pickle.dump(model_data, f)
    print(f"\nModel saved to {args.output}")

    # Save metrics
    metrics_path = ROOT / "results" / "diverse_model_metrics.json"
    metrics_path.parent.mkdir(exist_ok=True)
    metrics = {
        "model_version": "diverse_v1",
        "cv_accuracy": float(scores.mean()),
        "cv_std": float(scores.std()),
        "train_accuracy": float(train_acc),
        "n_samples": len(X),
        "n_classes": len(le.classes_),
        "classes": list(le.classes_),
        "class_distribution": {cls: int(np.sum(y_encoded == le.transform([cls])[0])) for cls in le.classes_},
        "feature_cols": FEATURE_COLS,
        "evaluation_type": "CROSS_VALIDATION (honest, no data leakage)",
        "data_source": "Web-sourced factory videos (YouTube, HuggingFace)",
        "caveat": "Labels inferred from video content, not human-labeled",
    }
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"Metrics saved to {metrics_path}")


if __name__ == "__main__":
    main()
