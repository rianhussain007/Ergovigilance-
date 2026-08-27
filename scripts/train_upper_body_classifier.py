"""Train upper-body task classifier for partial camera views.

When the camera only shows the upper body (common in factory deployments),
lower-body features like knee_angle, stance_stability, etc. are NaN.
This classifier uses only the 6 features that are reliably available:

1. neck_flexion
2. right_shoulder_elev  
3. shoulder_symmetry
4. alignment_deviation
5. forward_head_posture
6. head_tilt_angle

Usage:
    python scripts/train_upper_body_classifier.py --data outputs/real_data/real_features.csv
    python scripts/train_upper_body_classifier.py  # synthetic training
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import StratifiedKFold, train_test_split

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Features available from upper-body-only camera views
UPPER_BODY_FEATURES = [
    "neck_flexion",
    "right_shoulder_elev",
    "shoulder_symmetry",
    "alignment_deviation",
    "forward_head_posture",
    "head_tilt_angle",
    "movement_velocity",
    "wrist_movement_velocity",
]

CLASSES = [
    "Neutral Standing",
    "Assembly Work",
    "Reaching",
    "Lifting / Picking",
    "Inspection",
    "Seated Work",
    "Walking / Moving",
]


def generate_synthetic_upper_body(per_class: int = 3000, seed: int = 42) -> Tuple[np.ndarray, np.ndarray]:
    """Generate synthetic upper-body features for training."""
    rng = np.random.default_rng(seed)
    
    # Task-specific feature distributions (mean, std)
    # Based on what's visible from upper-body camera views
    TASK_DISTRIBUTIONS = {
        "Neutral Standing": {
            "neck_flexion": (5.0, 3.0),
            "right_shoulder_elev": (15.0, 8.0),
            "shoulder_symmetry": (3.0, 2.0),
            "alignment_deviation": (5.0, 3.0),
            "forward_head_posture": (5.0, 3.0),
            "head_tilt_angle": (3.0, 2.0),
            "movement_velocity": (5.0, 5.0),
            "wrist_movement_velocity": (10.0, 10.0),
        },
        "Assembly Work": {
            "neck_flexion": (12.0, 5.0),
            "right_shoulder_elev": (35.0, 10.0),
            "shoulder_symmetry": (8.0, 4.0),
            "alignment_deviation": (8.0, 4.0),
            "forward_head_posture": (12.0, 5.0),
            "head_tilt_angle": (8.0, 4.0),
            "movement_velocity": (15.0, 10.0),
            "wrist_movement_velocity": (30.0, 15.0),
        },
        "Reaching": {
            "neck_flexion": (10.0, 5.0),
            "right_shoulder_elev": (45.0, 12.0),
            "shoulder_symmetry": (12.0, 5.0),
            "alignment_deviation": (10.0, 5.0),
            "forward_head_posture": (10.0, 5.0),
            "head_tilt_angle": (6.0, 3.0),
            "movement_velocity": (40.0, 20.0),
            "wrist_movement_velocity": (80.0, 30.0),
        },
        "Lifting / Picking": {
            "neck_flexion": (15.0, 6.0),
            "right_shoulder_elev": (40.0, 12.0),
            "shoulder_symmetry": (10.0, 5.0),
            "alignment_deviation": (12.0, 5.0),
            "forward_head_posture": (15.0, 6.0),
            "head_tilt_angle": (10.0, 4.0),
            "movement_velocity": (20.0, 15.0),
            "wrist_movement_velocity": (40.0, 20.0),
        },
        "Inspection": {
            "neck_flexion": (20.0, 6.0),
            "right_shoulder_elev": (30.0, 10.0),
            "shoulder_symmetry": (6.0, 3.0),
            "alignment_deviation": (6.0, 3.0),
            "forward_head_posture": (18.0, 5.0),
            "head_tilt_angle": (12.0, 4.0),
            "movement_velocity": (5.0, 5.0),
            "wrist_movement_velocity": (15.0, 10.0),
        },
        "Seated Work": {
            "neck_flexion": (10.0, 4.0),
            "right_shoulder_elev": (30.0, 10.0),
            "shoulder_symmetry": (5.0, 3.0),
            "alignment_deviation": (6.0, 3.0),
            "forward_head_posture": (10.0, 4.0),
            "head_tilt_angle": (6.0, 3.0),
            "movement_velocity": (5.0, 5.0),
            "wrist_movement_velocity": (20.0, 10.0),
        },
        "Walking / Moving": {
            "neck_flexion": (8.0, 4.0),
            "right_shoulder_elev": (20.0, 10.0),
            "shoulder_symmetry": (4.0, 2.0),
            "alignment_deviation": (5.0, 3.0),
            "forward_head_posture": (8.0, 4.0),
            "head_tilt_angle": (4.0, 2.0),
            "movement_velocity": (80.0, 30.0),
            "wrist_movement_velocity": (60.0, 25.0),
        },
    }
    
    X = []
    y = []
    
    for task, dists in TASK_DISTRIBUTIONS.items():
        for _ in range(per_class):
            sample = []
            for feat in UPPER_BODY_FEATURES:
                mean, std = dists[feat]
                sample.append(max(0, rng.normal(mean, std)))
            X.append(sample)
            y.append(task)
    
    return np.array(X), np.array(y)


def load_real_data(csv_path: Path) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """Load real upper-body features from CSV."""
    import pandas as pd
    
    df = pd.read_csv(csv_path)
    
    # Keep only available features
    available_feats = [f for f in UPPER_BODY_FEATURES if f in df.columns]
    print(f"Available features: {available_feats}")
    
    X = df[available_feats].fillna(0.0).values
    y = df["task_label"].values
    
    return X, y, available_feats


def train(X: np.ndarray, y: np.ndarray, features: List[str], out: Path, seed: int = 42) -> dict:
    """Train and evaluate the upper-body classifier."""
    
    print(f"\nTraining on {len(X)} samples, {X.shape[1]} features")
    print(f"Classes: {np.unique(y)}")
    
    # Stratified split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=seed, stratify=y
    )
    
    # Train model
    model = HistGradientBoostingClassifier(
        max_iter=200,
        learning_rate=0.1,
        max_depth=4,
        min_samples_leaf=10,
        random_state=seed,
    )
    model.fit(X_train, y_train)
    
    # Evaluate
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    
    print(f"\n=== HOLDOUT ACCURACY: {accuracy*100:.1f}% ===")
    print(classification_report(y_test, y_pred, zero_division=0))
    
    # Cross-validation
    print("5-Fold Cross-Validation:")
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
    cv_scores = []
    for fold, (train_idx, test_idx) in enumerate(skf.split(X, y)):
        model_cv = HistGradientBoostingClassifier(
            max_iter=200, learning_rate=0.1, max_depth=4,
            min_samples_leaf=10, random_state=seed,
        )
        model_cv.fit(X[train_idx], y[train_idx])
        score = accuracy_score(y[test_idx], model_cv.predict(X[test_idx]))
        cv_scores.append(score)
        print(f"  Fold {fold+1}: {score*100:.1f}%")
    
    cv_mean = np.mean(cv_scores) * 100
    print(f"\nCV Accuracy: {cv_mean:.1f}% (+/- {np.std(cv_scores)*100:.1f}%)")
    
    # Train final model on all data
    final_model = HistGradientBoostingClassifier(
        max_iter=200, learning_rate=0.1, max_depth=4,
        min_samples_leaf=10, random_state=seed,
    )
    final_model.fit(X, y)
    
    # Save bundle
    bundle = {
        "model": final_model,
        "feature_columns": features,
        "labels": list(np.unique(y)),
        "version": "v3_upper_body",
        "purpose": "Upper-body task classifier for partial camera views",
        "metrics": {
            "holdout_accuracy": accuracy,
            "cv_accuracy": cv_mean,
            "n_samples": len(X),
            "features": features,
        },
        "config": {"confidence_threshold": 0.5},
    }
    
    out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, out)
    print(f"\nModel saved: {out}")
    
    return {"holdout": accuracy, "cv": cv_mean}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "models/upper_body_task_model.pkl")
    ap.add_argument("--data", type=Path, default=None, help="Real data CSV")
    ap.add_argument("--per-class", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    
    if args.data and args.data.exists():
        print(f"Loading real data from {args.data}")
        X, y, features = load_real_data(args.data)
    else:
        print("Generating synthetic upper-body data")
        X, y = generate_synthetic_upper_body(args.per_class, args.seed)
        features = UPPER_BODY_FEATURES
    
    metrics = train(X, y, features, args.out, args.seed)
