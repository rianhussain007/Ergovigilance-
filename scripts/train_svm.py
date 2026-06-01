from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import GridSearchCV, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.features import FEATURE_COLUMNS, RISK_LEVELS


def _evaluate_model(model: Any, X_test: pd.DataFrame, y_test: pd.Series, labels: list[str]) -> dict:
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
    df = df.dropna(subset=FEATURE_COLUMNS + ["label"]).copy()
    X = df[FEATURE_COLUMNS]
    y = df["label"].str.upper()

    stratify = y if y.value_counts().min() >= 2 else None
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=stratify,
    )

    labels = [label for label in RISK_LEVELS if label in set(y)]
    candidates = {
        "svm": GridSearchCV(
            Pipeline(
                steps=[
                    ("scaler", StandardScaler()),
                    ("svm", SVC(kernel="rbf", probability=True, class_weight="balanced", random_state=42)),
                ]
            ),
            param_grid={"svm__C": [1, 3, 10, 30], "svm__gamma": ["scale", 0.03, 0.1, 0.3]},
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

    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {"model": fitted_models["svm"], "feature_columns": FEATURE_COLUMNS, "labels": labels, "metrics": model_results["svm"]},
        model_path,
    )

    if best_model_path is None:
        best_model_path = ROOT / "models" / "best_model.pkl"
    best_model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {"model": best_model, "feature_columns": FEATURE_COLUMNS, "labels": labels, "metrics": best_metrics},
        best_model_path,
    )

    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "svm_metrics.json").write_text(json.dumps(model_results["svm"], indent=2), encoding="utf-8")
    (results_dir / "best_model_metrics.json").write_text(json.dumps(best_metrics, indent=2), encoding="utf-8")
    pd.DataFrame(best_metrics["confusion_matrix"], index=labels, columns=labels).to_csv(results_dir / "confusion_matrix.csv")
    return best_metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=ROOT / "data" / "processed" / "dataset_final.csv")
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
