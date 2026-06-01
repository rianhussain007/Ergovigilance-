from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import cv2
import joblib
import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile

from backend.services.features import FEATURE_COLUMNS
from backend.services.pose import ImageQualityError, NoPersonDetectedError, detect_pose_from_bgr


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "models" / "best_model.pkl"

app = FastAPI(title="Ergonomic Posture Analysis API", version="1.0.0")
_model_bundle: Dict[str, Any] | None = None


def load_model() -> Dict[str, Any]:
    global _model_bundle
    if _model_bundle is None:
        if not MODEL_PATH.exists():
            raise RuntimeError(f"Model file not found: {MODEL_PATH}")
        _model_bundle = joblib.load(MODEL_PATH)
        make_model_compatible(_model_bundle["model"])
    return _model_bundle


def make_model_compatible(model: Any) -> None:
    if not hasattr(model, "monotonic_cst"):
        model.monotonic_cst = None
    for estimator in getattr(model, "estimators_", []):
        if not hasattr(estimator, "monotonic_cst"):
            estimator.monotonic_cst = None


def normalized_probabilities(raw_probabilities: np.ndarray) -> np.ndarray:
    probabilities = np.asarray(raw_probabilities, dtype=float)
    probabilities = np.nan_to_num(probabilities, nan=0.0, posinf=0.0, neginf=0.0)
    probabilities = np.clip(probabilities, 0.0, None)
    total = float(probabilities.sum())
    if total > 0:
        probabilities = probabilities / total
    return probabilities


def _decode_upload(contents: bytes) -> np.ndarray:
    array = np.frombuffer(contents, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Uploaded file is not a readable image.")
    return image


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/predict")
async def predict(file: UploadFile = File(...)) -> Dict[str, Any]:
    try:
        image = _decode_upload(await file.read())
        pose = detect_pose_from_bgr(image)
        features = pose["features"]
        bundle = load_model()
        model = bundle["model"]
        vector = [[features[name] for name in FEATURE_COLUMNS]]
        probabilities = normalized_probabilities(model.predict_proba(vector)[0])
        class_index = int(np.argmax(probabilities))
        risk_level = str(model.classes_[class_index])
        prob = float(probabilities[class_index])
        confidence = round(prob * 100, 2)
        return {
            "risk_level": risk_level,
            "confidence": confidence,
            "features": features,
            "unavailable_features": pose.get("unavailable_features", []),
        }
    except (ImageQualityError, NoPersonDetectedError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
