from __future__ import annotations

import sys
from pathlib import Path

import cv2
import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.features import FEATURE_COLUMNS
from backend.services.pose import annotate_pose, detect_pose_from_bgr


def normalized_probabilities(raw_probabilities: np.ndarray) -> np.ndarray:
    probabilities = np.asarray(raw_probabilities, dtype=float)
    probabilities = np.nan_to_num(probabilities, nan=0.0, posinf=0.0, neginf=0.0)
    probabilities = np.clip(probabilities, 0.0, None)
    total = float(probabilities.sum())
    if total > 0:
        probabilities = probabilities / total
    return probabilities


def load_model_bundle() -> dict:
    loaded = joblib.load(ROOT / "models" / "best_model.pkl")
    if isinstance(loaded, dict) and "model" in loaded:
        loaded.setdefault("feature_columns", FEATURE_COLUMNS)
        return loaded
    return {"model": loaded, "feature_columns": FEATURE_COLUMNS}


def main() -> None:
    bundle = load_model_bundle()
    model = bundle["model"]
    feature_columns = bundle["feature_columns"]
    image_paths = list((ROOT / "data" / "raw" / "kaggle" / "images").glob("**/*.jpg"))
    results_dir = ROOT / "results" / "smoke_tests"
    results_dir.mkdir(parents=True, exist_ok=True)

    found: dict[str, tuple[Path, float]] = {}
    for image_path in image_paths:
        image = cv2.imread(str(image_path))
        if image is None:
            continue
        try:
            pose = detect_pose_from_bgr(image)
            features = pose["features"]
            vector = pd.DataFrame([{name: features[name] for name in feature_columns}], columns=feature_columns)
            probabilities = normalized_probabilities(model.predict_proba(vector)[0])
            idx = int(np.argmax(probabilities))
            risk_level = str(model.classes_[idx])
            confidence = round(float(probabilities[idx]) * 100, 2)
            if not 0 <= confidence <= 100:
                raise RuntimeError(f"Invalid confidence {confidence} for {image_path}")
            if risk_level not in found:
                annotated = annotate_pose(image, pose["keypoints"], features, risk_level)
                output = results_dir / f"{risk_level.lower()}_result.jpg"
                cv2.imwrite(str(output), annotated)
                found[risk_level] = (image_path, confidence)
        except Exception:
            continue
        if {"LOW", "MEDIUM", "HIGH"}.issubset(found):
            break

    print(f"Model type: {type(model).__name__}")
    print(f"Feature order: {feature_columns}")
    for level in ["LOW", "MEDIUM", "HIGH"]:
        if level in found:
            image_path, confidence = found[level]
            print(f"{level}: {confidence:.2f}% from {image_path.name}")
        else:
            print(f"{level}: not found in scanned sample images")

    if not {"LOW", "MEDIUM", "HIGH"}.issubset(found):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
