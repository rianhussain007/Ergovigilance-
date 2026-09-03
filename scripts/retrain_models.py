"""Retrain ErgoVigilance models using all extracted features."""

import json
import pickle
import logging
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from collections import Counter
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import classification_report, confusion_matrix

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_ROOT / "models"
RESULTS_DIR = PROJECT_ROOT / "results"
DATA_DIR = PROJECT_ROOT / "outputs" / "real_data"

# ── Load Data ─────────────────────────────────────────────────────

def load_all_data():
    """Load and combine all available training data."""
    datasets = []
    
    # 1. Balanced training data
    balanced_path = DATA_DIR / "balanced_training_data.csv"
    if balanced_path.exists():
        df = pd.read_csv(balanced_path)
        logger.info("Loaded balanced_data: %d rows", len(df))
        datasets.append(df)
    
    # 2. Diverse extracted features
    diverse_path = DATA_DIR / "diverse_extracted_features.csv"
    if diverse_path.exists():
        df = pd.read_csv(diverse_path)
        logger.info("Loaded diverse_features: %d rows", len(df))
        datasets.append(df)
    
    # 3. Improved features
    improved_path = DATA_DIR / "improved_features.csv"
    if improved_path.exists():
        df = pd.read_csv(improved_path)
        logger.info("Loaded improved_features: %d rows", len(df))
        datasets.append(df)
    
    # 4. All real features
    all_real_path = DATA_DIR / "all_real_features.json"
    if all_real_path.exists():
        with open(all_real_path) as f:
            data = json.load(f)
        if isinstance(data, list) and len(data) > 0:
            df = pd.DataFrame(data)
            logger.info("Loaded all_real_features: %d rows", len(df))
            datasets.append(df)
    
    if not datasets:
        raise ValueError("No training data found!")
    
    # Combine
    combined = pd.concat(datasets, ignore_index=True)
    logger.info("Combined total: %d rows", len(combined))
    return combined


# ── Feature Engineering ────────────────────────────────────────────

FEATURE_COLS = [
    "neck_flexion", "trunk_flexion", "shoulder_symmetry", "knee_angle",
    "left_shoulder_elev", "right_shoulder_elev", "alignment_deviation",
    "forward_head_posture", "head_tilt_angle", "elbow_flexion_angle",
    "upper_arm_angle_from_vertical", "wrist_deviation_angle",
    "stance_stability", "weight_shift_offset", "hand_reach_ratio",
]


def prepare_features(df):
    """Prepare feature matrix, handling missing columns."""
    available = [c for c in FEATURE_COLS if c in df.columns]
    if len(available) < 4:
        raise ValueError(f"Too few features available: {available}")
    
    X = df[available].copy()
    X = X.fillna(0)  # Fill NaN with 0
    return X, available


# ── Risk Model Training ────────────────────────────────────────────

def train_risk_model(df):
    """Train and evaluate risk classification model."""
    logger.info("\n=== Training Risk Model ===")
    
    X, feature_names = prepare_features(df)
    
    # Normalize risk labels
    y_raw = df["risk_level"].str.upper().str.strip()
    y_raw = y_raw.replace({"HIGH RISK": "HIGH", "MEDIUM RISK": "MEDIUM", "LOW RISK": "LOW"})
    
    # Only keep rows with valid risk labels
    valid = y_raw.isin(["LOW", "MEDIUM", "HIGH"])
    X = X[valid]
    y = y_raw[valid]
    
    logger.info("Risk distribution: %s", dict(Counter(y)))
    logger.info("Features used: %s (%d)", feature_names, len(feature_names))
    
    if len(y.unique()) < 2:
        logger.warning("Need at least 2 risk classes, found: %s", y.unique())
        return None
    
    le = LabelEncoder()
    y_encoded = le.fit_transform(y)
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Compare models
    models = {
        "hist_gradient_boosting": HistGradientBoostingClassifier(
            max_depth=8, learning_rate=0.06, min_samples_leaf=10, max_iter=200
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=300, max_depth=16, min_samples_leaf=2, random_state=42
        ),
    }
    
    best_score = 0
    best_name = None
    best_model = None
    
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    
    for name, model in models.items():
        scores = cross_val_score(model, X_scaled, y_encoded, cv=cv, scoring="f1_weighted")
        mean_f1 = scores.mean()
        std_f1 = scores.std()
        logger.info("  %s: F1=%.4f +/- %.4f", name, mean_f1, std_f1)
        
        if mean_f1 > best_score:
            best_score = mean_f1
            best_name = name
            best_model = model
    
    logger.info("Best model: %s (F1=%.4f)", best_name, best_score)
    
    # Train best model on full data
    best_model.fit(X_scaled, y_encoded)
    train_pred = best_model.predict(X_scaled)
    train_acc = (train_pred == y_encoded).mean()
    
    # Confusion matrix
    cm = confusion_matrix(y_encoded, train_pred).tolist()
    report = classification_report(y, le.inverse_transform(train_pred), output_dict=True)
    
    return {
        "model": best_model,
        "scaler": scaler,
        "label_encoder": le,
        "feature_names": feature_names,
        "cv_f1_mean": best_score,
        "cv_f1_std": std_f1,
        "train_accuracy": train_acc,
        "confusion_matrix": cm,
        "classification_report": report,
        "best_algorithm": best_name,
    }


# ── Task Model Training ────────────────────────────────────────────

def train_task_model(df):
    """Train and evaluate task classification model."""
    logger.info("\n=== Training Task Model ===")
    
    X, feature_names = prepare_features(df)
    
    # Normalize task labels
    y_raw = df["task_label"].str.strip()
    y_raw = y_raw.replace({
        "Lifting / Picking": "Lifting/Carrying",
        "Lifting/Picking": "Lifting/Carrying",
        "Neutral Standing": "Neutral Standing",
    })
    
    # Only keep rows with valid task labels
    valid_tasks = ["Assembly Work", "Inspection", "Seated Work", "Lifting/Carrying", "Neutral Standing"]
    valid = y_raw.isin(valid_tasks)
    X = X[valid]
    y = y_raw[valid]
    
    logger.info("Task distribution: %s", dict(Counter(y)))
    logger.info("Features used: %s (%d)", feature_names, len(feature_names))
    
    if len(y.unique()) < 2:
        logger.warning("Need at least 2 task classes, found: %s", y.unique())
        return None
    
    le = LabelEncoder()
    y_encoded = le.fit_transform(y)
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Compare models
    models = {
        "hist_gradient_boosting": HistGradientBoostingClassifier(
            max_depth=6, learning_rate=0.08, min_samples_leaf=5, max_iter=200
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=300, max_depth=12, min_samples_leaf=2, random_state=42
        ),
    }
    
    best_score = 0
    best_name = None
    best_model = None
    
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    
    for name, model in models.items():
        scores = cross_val_score(model, X_scaled, y_encoded, cv=cv, scoring="f1_weighted")
        mean_f1 = scores.mean()
        std_f1 = scores.std()
        logger.info("  %s: F1=%.4f +/- %.4f", name, mean_f1, std_f1)
        
        if mean_f1 > best_score:
            best_score = mean_f1
            best_name = name
            best_model = model
    
    logger.info("Best model: %s (F1=%.4f)", best_name, best_score)
    
    # Train best model on full data
    best_model.fit(X_scaled, y_encoded)
    train_pred = best_model.predict(X_scaled)
    train_acc = (train_pred == y_encoded).mean()
    
    # Confusion matrix
    cm = confusion_matrix(y_encoded, train_pred).tolist()
    report = classification_report(y, le.inverse_transform(train_pred), output_dict=True)
    
    return {
        "model": best_model,
        "scaler": scaler,
        "label_encoder": le,
        "feature_names": feature_names,
        "cv_f1_mean": best_score,
        "cv_f1_std": std_f1,
        "train_accuracy": train_acc,
        "confusion_matrix": cm,
        "classification_report": report,
        "best_algorithm": best_name,
    }


# ── Main ──────────────────────────────────────────────────────────

def main():
    logger.info("=" * 60)
    logger.info("ErgoVigilance Model Retraining Pipeline")
    logger.info("=" * 60)
    
    # Load data
    df = load_all_data()
    
    # Train risk model
    risk_results = train_risk_model(df)
    
    # Train task model
    task_results = train_task_model(df)
    
    # Save models
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if risk_results:
        risk_path = MODELS_DIR / f"risk_model_v3_{timestamp}.pkl"
        with open(risk_path, "wb") as f:
            pickle.dump({
                "model": risk_results["model"],
                "scaler": risk_results["scaler"],
                "label_encoder": risk_results["label_encoder"],
                "feature_names": risk_results["feature_names"],
            }, f)
        logger.info("Risk model saved: %s", risk_path)
    
    if task_results:
        task_path = MODELS_DIR / f"task_model_v4_{timestamp}.pkl"
        with open(task_path, "wb") as f:
            pickle.dump({
                "model": task_results["model"],
                "scaler": task_results["scaler"],
                "label_encoder": task_results["label_encoder"],
                "feature_names": task_results["feature_names"],
            }, f)
        logger.info("Task model saved: %s", task_path)
    
    # Save metrics
    metrics = {
        "timestamp": timestamp,
        "data_stats": {
            "total_rows": len(df),
            "risk_distribution": dict(Counter(df["risk_level"].str.upper())),
            "task_distribution": dict(Counter(df["task_label"])),
        },
    }
    
    if risk_results:
        metrics["risk_model"] = {
            "cv_f1": risk_results["cv_f1_mean"],
            "cv_f1_std": risk_results["cv_f1_std"],
            "train_accuracy": risk_results["train_accuracy"],
            "confusion_matrix": risk_results["confusion_matrix"],
            "classification_report": risk_results["classification_report"],
            "algorithm": risk_results["best_algorithm"],
        }
    
    if task_results:
        metrics["task_model"] = {
            "cv_f1": task_results["cv_f1_mean"],
            "cv_f1_std": task_results["cv_f1_std"],
            "train_accuracy": task_results["train_accuracy"],
            "confusion_matrix": task_results["confusion_matrix"],
            "classification_report": task_results["classification_report"],
            "algorithm": task_results["best_algorithm"],
        }
    
    metrics_path = RESULTS_DIR / f"retrained_model_metrics_{timestamp}.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    logger.info("Metrics saved: %s", metrics_path)
    
    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("RETRAINING RESULTS")
    logger.info("=" * 60)
    
    if risk_results:
        logger.info("\nRisk Model (%s):", risk_results["best_algorithm"])
        logger.info("  CV F1: %.4f +/- %.4f", risk_results["cv_f1_mean"], risk_results["cv_f1_std"])
        logger.info("  Train Accuracy: %.4f", risk_results["train_accuracy"])
        logger.info("  Per-class F1:")
        for cls, metrics_cls in risk_results["classification_report"].items():
            if isinstance(metrics_cls, dict) and "f1-score" in metrics_cls:
                logger.info("    %s: %.3f", cls, metrics_cls["f1-score"])
    
    if task_results:
        logger.info("\nTask Model (%s):", task_results["best_algorithm"])
        logger.info("  CV F1: %.4f +/- %.4f", task_results["cv_f1_mean"], task_results["cv_f1_std"])
        logger.info("  Train Accuracy: %.4f", task_results["train_accuracy"])
        logger.info("  Per-class F1:")
        for cls, metrics_cls in task_results["classification_report"].items():
            if isinstance(metrics_cls, dict) and "f1-score" in metrics_cls:
                logger.info("    %s: %.3f", cls, metrics_cls["f1-score"])
    
    logger.info("\n" + "=" * 60)


if __name__ == "__main__":
    main()
