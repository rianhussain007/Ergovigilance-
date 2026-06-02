from __future__ import annotations

import argparse
import sys
from pathlib import Path

import joblib
from PIL import Image, ImageDraw, ImageFont
import pandas as pd
from sklearn.inspection import permutation_importance
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.features import FEATURE_COLUMNS, RISK_LEVELS


def make_model_compatible(model) -> None:
    if not hasattr(model, "monotonic_cst"):
        model.monotonic_cst = None
    for estimator in getattr(model, "estimators_", []):
        if not hasattr(estimator, "monotonic_cst"):
            estimator.monotonic_cst = None


def evaluate(dataset_path: Path, model_path: Path, output_path: Path) -> dict:
    df = pd.read_csv(dataset_path).dropna(subset=FEATURE_COLUMNS + ["label"])
    X = df[FEATURE_COLUMNS]
    y = df["label"].str.upper()
    stratify = y if y.value_counts().min() >= 2 else None
    _, X_test, _, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=stratify)

    loaded = joblib.load(model_path)
    bundle = loaded if isinstance(loaded, dict) and "model" in loaded else {"model": loaded, "metrics": {}}
    model = bundle["model"]
    make_model_compatible(model)

    labels = [label for label in RISK_LEVELS if label in set(y)]
    y_pred = model.predict(X_test)
    accuracy = float((y_pred == y_test).mean())
    cm = confusion_matrix(y_test, y_pred, labels=labels)
    report = classification_report(y_test, y_pred, labels=labels, output_dict=True, zero_division=0)

    importance = permutation_importance(model, X_test, y_test, n_repeats=8, random_state=42, scoring="accuracy")
    importance_df = pd.DataFrame(
        {
            "feature": FEATURE_COLUMNS,
            "importance_mean": importance.importances_mean,
            "importance_std": importance.importances_std,
        }
    ).sort_values("importance_mean", ascending=True)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    width, height = 1800, 1250
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    title_font = ImageFont.load_default()

    def text(x: int, y: int, value: str, fill: tuple[int, int, int] = (31, 41, 55)) -> None:
        draw.text((x, y), value, fill=fill, font=font)

    summary_lines = [
        "Model Evaluation",
        f"Model: {bundle.get('metrics', {}).get('model_name', 'best_model')}",
        f"Overall accuracy: {accuracy:.4f} ({accuracy * 100:.2f}%)",
        "",
        "Per-class precision / recall / F1",
    ]
    for label in labels:
        metrics = report[label]
        summary_lines.append(
            f"{label}: precision {metrics['precision']:.3f}, "
            f"recall {metrics['recall']:.3f}, F1 {metrics['f1-score']:.3f}"
        )

    y_cursor = 50
    for idx, line in enumerate(summary_lines):
        text(60, y_cursor, line, (17, 24, 39) if idx == 0 else (31, 41, 55))
        y_cursor += 34 if idx == 0 else 28

    cm_x, cm_y = 980, 90
    text(cm_x, 50, "Confusion Matrix", (17, 24, 39))
    cell = 110
    for j, label in enumerate(labels):
        text(cm_x + (j + 1) * cell + 30, cm_y - 30, label)
    for i, label in enumerate(labels):
        text(cm_x - 70, cm_y + i * cell + 42, label)
    max_cm = max(int(cm.max()), 1)
    for i in range(len(labels)):
        for j in range(len(labels)):
            intensity = int(245 - 150 * (cm[i, j] / max_cm))
            fill = (intensity, intensity + 5, 255)
            x1 = cm_x + (j + 1) * cell
            y1 = cm_y + i * cell
            draw.rectangle((x1, y1, x1 + cell, y1 + cell), fill=fill, outline=(148, 163, 184))
            text(x1 + 42, y1 + 44, str(cm[i, j]), (15, 23, 42))

    text(60, 430, "Per-Class Metrics", (17, 24, 39))
    class_df = pd.DataFrame(report).T.loc[labels, ["precision", "recall", "f1-score"]]
    metric_colors = {"precision": (37, 99, 235), "recall": (22, 163, 74), "f1-score": (220, 38, 38)}
    bar_x, bar_y = 60, 490
    bar_w, bar_h = 170, 24
    for row_idx, label in enumerate(labels):
        y = bar_y + row_idx * 105
        text(bar_x, y, label)
        for metric_idx, metric in enumerate(["precision", "recall", "f1-score"]):
            value = float(class_df.loc[label, metric])
            x = bar_x + 120
            yy = y + 28 + metric_idx * 24
            text(x, yy, metric)
            draw.rectangle((x + 90, yy, x + 90 + bar_w, yy + bar_h - 6), outline=(203, 213, 225))
            draw.rectangle((x + 90, yy, x + 90 + int(bar_w * value), yy + bar_h - 6), fill=metric_colors[metric])
            text(x + 275, yy, f"{value:.3f}")

    text(980, 430, "Permutation Feature Importance", (17, 24, 39))
    imp = importance_df.sort_values("importance_mean", ascending=False)
    max_imp = max(float(imp["importance_mean"].max()), 0.001)
    for idx, row in enumerate(imp.itertuples(index=False)):
        y = 490 + idx * 62
        label = str(row.feature).replace("_", " ").title()
        value = max(float(row.importance_mean), 0.0)
        text(980, y, label)
        draw.rectangle((1210, y, 1650, y + 24), outline=(203, 213, 225))
        draw.rectangle((1210, y, 1210 + int(440 * value / max_imp), y + 24), fill=(124, 58, 237))
        text(1665, y, f"{value:.4f}")

    image.save(output_path)

    return {
        "accuracy": accuracy,
        "labels": labels,
        "confusion_matrix": cm.tolist(),
        "classification_report": report,
        "feature_importance": importance_df.sort_values("importance_mean", ascending=False).to_dict("records"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=ROOT / "data" / "processed" / "dataset_final.csv")
    parser.add_argument("--model", type=Path, default=ROOT / "models" / "best_model.pkl")
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "model_evaluation.png")
    args = parser.parse_args()
    metrics = evaluate(args.dataset, args.model, args.output)
    print(f"Overall accuracy: {metrics['accuracy']:.4f}")
    print("Confusion matrix:")
    print(pd.DataFrame(metrics["confusion_matrix"], index=metrics["labels"], columns=metrics["labels"]).to_string())
    print("Per-class precision/recall/F1:")
    print(pd.DataFrame(metrics["classification_report"]).T.loc[metrics["labels"], ["precision", "recall", "f1-score"]].to_string())
    print(f"Saved {args.output}")


if __name__ == "__main__":
    main()
