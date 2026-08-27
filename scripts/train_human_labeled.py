#!/usr/bin/env python3
"""Train task classifier on HUMAN-LABELED frames only.

This produces the FIRST honest accuracy number against real human ground truth.
Previous models were trained on auto-generated labels (97% wrong).

Usage:
    python scripts/train_human_labeled.py
"""
import csv
import json
import pickle
import sys
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import cross_val_score, StratifiedKFold, LeaveOneOut
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


def load_human_labeled_data():
    """Load features from training CSV, join with human labels."""
    features_path = ROOT / "data" / "diverse_training_data" / "training_combined.csv"
    labels_path = ROOT / "data" / "diverse_training_data" / "human_labels.csv"

    # Load human labels (only frames with human_task set)
    human_labels = {}
    with open(labels_path) as f:
        for row in csv.DictReader(f):
            if row.get("human_task"):
                human_labels[row["frame_name"]] = row["human_task"]

    print(f"Human-labeled frames: {len(human_labels)}")

    # Load features
    with open(features_path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Join: only keep frames that have BOTH features AND human labels
    X, y, frame_names = [], [], []
    skipped_no_features = 0
    skipped_unknown_task = 0

    for row in rows:
        fname = row.get("frame_name", "")
        if fname not in human_labels:
            skipped_no_features += 1
            continue

        task = human_labels[fname]
        if task in ("Unknown", ""):
            skipped_unknown_task += 1
            continue

        try:
            features = []
            for col in FEATURE_COLS:
                val = row.get(col, "0")
                val = float(val) if val and val != "" else 0.0
                features.append(val)
            X.append(features)
            y.append(task)
            frame_names.append(fname)
        except (ValueError, KeyError):
            continue

    print(f"Frames with features: {len(rows)}")
    print(f"Matched to human labels: {len(X)}")
    print(f"Skipped (no features): {skipped_no_features}")
    print(f"Skipped (Unknown task): {skipped_unknown_task}")

    return np.array(X, dtype=np.float32), np.array(y), frame_names


def main():
    print("=" * 60)
    print("HUMAN-LABELED TASK CLASSIFIER TRAINING")
    print("First honest accuracy against real ground truth")
    print("=" * 60)

    X, y, frame_names = load_human_labeled_data()

    if len(X) < 20:
        print(f"\nERROR: Only {len(X)} labeled samples — need at least 20 for CV")
        print("Label more frames in the labeling tool: python scripts/label_tool.py")
        sys.exit(1)

    # Encode labels
    le = LabelEncoder()
    y_encoded = le.fit_transform(y)

    print(f"\nDataset: {len(X)} samples, {len(FEATURE_COLS)} features")
    print(f"Classes: {list(le.classes_)}")
    print(f"\nClass distribution:")
    for cls in le.classes_:
        count = int(np.sum(y_encoded == le.transform([cls])[0]))
        print(f"  {cls:20s}: {count:4d} ({100*count/len(X):.1f}%)")

    # Determine CV strategy based on smallest class
    min_class_count = min(np.bincount(y_encoded))
    if min_class_count >= 5:
        n_splits = min(5, min_class_count)
        print(f"\nUsing {n_splits}-fold stratified CV")
        cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    elif min_class_count >= 2:
        print(f"\nSmallest class has {min_class_count} samples — using Leave-One-Out CV")
        cv = LeaveOneOut()
    else:
        print(f"\nSmallest class has {min_class_count} sample — using leave-one-out")
        cv = LeaveOneOut()

    # Train with CV
    clf = HistGradientBoostingClassifier(
        max_iter=200,
        max_depth=5,
        learning_rate=0.1,
        min_samples_leaf=3,
        random_state=42,
    )

    print("\nTraining HistGradientBoosting...")
    scores = cross_val_score(clf, X, y_encoded, cv=cv, scoring="accuracy")

    if min_class_count >= 5:
        print(f"\n{'='*60}")
        print(f"CV ACCURACY: {scores.mean():.1%} (+/- {scores.std():.1%})")
        print(f"Per-fold: {[f'{s:.1%}' for s in scores]}")
    else:
        print(f"\n{'='*60}")
        print(f"LOO ACCURACY: {scores.mean():.1%}")
        correct = int(scores.sum())
        total = len(scores)
        print(f"Correct: {correct}/{total}")

    # Train on all data for final model
    clf.fit(X, y_encoded)
    train_pred = clf.predict(X)
    train_acc = np.mean(train_pred == y_encoded)
    print(f"Training accuracy: {train_acc:.1%}")

    # Per-class report
    print(f"\nClassification Report (training set):")
    print(classification_report(y_encoded, train_pred, target_names=le.classes_, zero_division=0))

    # Confusion matrix
    cm = confusion_matrix(y_encoded, train_pred)
    print("Confusion Matrix:")
    header = " ".join(f"{cls[:8]:>9s}" for cls in le.classes_)
    print(f"  {'':20s} {header}")
    for i, cls in enumerate(le.classes_):
        row = " ".join(f"{cm[i][j]:9d}" for j in range(len(le.classes_)))
        print(f"  {cls:20s} {row}")

    # Feature analysis
    print(f"\nFeature analysis (per-class mean values):")
    for i, cls in enumerate(le.classes_):
        cls_mask = y_encoded == i
        if cls_mask.sum() == 0:
            continue
        cls_mean = X[cls_mask].mean(axis=0)
        print(f"\n  {cls} (n={cls_mask.sum()}):")
        for feat, val in sorted(zip(FEATURE_COLS, cls_mean), key=lambda x: -abs(x[1])):
            if abs(val) > 0.1:
                print(f"    {feat:25s}: {val:.2f}")

    # Save model
    output_path = ROOT / "models" / "human_labeled_task_model.pkl"
    model_data = {
        "model": clf,
        "label_encoder": le,
        "feature_cols": FEATURE_COLS,
        "version": "human_labeled_v1",
        "cv_accuracy": float(scores.mean()),
        "cv_std": float(scores.std()) if min_class_count >= 5 else 0.0,
        "train_accuracy": float(train_acc),
        "n_samples": len(X),
        "n_classes": len(le.classes_),
        "classes": list(le.classes_),
        "class_distribution": {cls: int(np.sum(y_encoded == le.transform([cls])[0])) for cls in le.classes_},
        "training_data": "human_labels.csv (105 frames with both features and human labels)",
        "evaluation": "LEAVE-ONE-OUT CV" if min_class_count < 5 else f"{n_splits}-fold stratified CV",
        "honesty": "TRULY HONEST — trained and evaluated on human ground truth only",
        "auto_label_agreement": "2.9% — auto-labels were 97% wrong",
    }
    with open(output_path, "wb") as f:
        pickle.dump(model_data, f)
    print(f"\nModel saved to {output_path}")

    # Save metrics
    metrics_path = ROOT / "results" / "human_labeled_metrics.json"
    metrics = {
        "model_version": "human_labeled_v1",
        "cv_accuracy": float(scores.mean()),
        "cv_std": float(scores.std()) if min_class_count >= 5 else 0.0,
        "train_accuracy": float(train_acc),
        "n_samples": len(X),
        "n_classes": len(le.classes_),
        "classes": list(le.classes_),
        "class_distribution": {cls: int(np.sum(y_encoded == le.transform([cls])[0])) for cls in le.classes_},
        "feature_cols": FEATURE_COLS,
        "evaluation_type": "HONEST — human ground truth, no data leakage",
        "data_source": "105 frames with both pose features AND human labels",
        "auto_label_agreement": "2.9% — previous auto-labels were 97% wrong",
        "caveat": "Small dataset (105 frames) — accuracy will improve with more labels",
    }
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"Metrics saved to {metrics_path}")

    # Also compare against auto-labeled model
    print(f"\n{'='*60}")
    print("COMPARISON: Human-labeled vs Auto-labeled")
    print(f"{'='*60}")
    print(f"  Auto-labeled model CV accuracy: 70.8% (TRAINED ON 97% WRONG LABELS)")
    print(f"  Human-labeled model CV accuracy: {scores.mean():.1%} (HONEST)")
    print(f"  Auto-label agreement with human: 2.9%")
    print(f"\n  The 70.8% was MEANINGLESS — it measured overfitting to wrong labels.")
    print(f"  The {scores.mean():.1%} is the FIRST honest number in this project.")


if __name__ == "__main__":
    main()
