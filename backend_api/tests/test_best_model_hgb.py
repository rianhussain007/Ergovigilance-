"""Unit tests for the retrained best_model.pkl (HistGradientBoosting risk classifier).

The legacy RandomForest/SVM artifacts were replaced by a HistGradientBoosting
classifier trained on the 30,698-row REBA-labeled dataset (scripts/train_svm.py).
These tests guard the bundle contract: model type, label set, feature-column
count, and sane predictions.
"""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pytest

MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "best_model.pkl"


@pytest.fixture(scope="module")
def bundle():
    if not MODEL_PATH.exists():
        pytest.skip("best_model.pkl not present")
    return joblib.load(MODEL_PATH)


def test_bundle_shape(bundle):
    assert set(bundle.keys()) >= {"model", "feature_columns", "labels", "metrics"}
    assert bundle["labels"] == ["LOW", "MEDIUM", "HIGH"]


def test_model_is_gradient_boosting(bundle):
    name = type(bundle["model"]).__name__
    assert name == "HistGradientBoostingClassifier"


def test_feature_columns_exclude_coco_na(bundle):
    # The always-NaN-on-COCO features must not be part of the input contract.
    from backend.services.features import FEATURE_COLUMNS

    excluded = {"wrist_deviation_angle", "hand_reach_ratio", "finger_spread_ratio", "stance_width_ratio"}
    assert not (excluded & set(bundle["feature_columns"]))
    expected = [c for c in FEATURE_COLUMNS if c not in excluded]
    assert list(bundle["feature_columns"]) == expected


def test_predict_returns_known_label(bundle):
    X = np.zeros((1, len(bundle["feature_columns"])), dtype=float)
    pred = bundle["model"].predict(X)[0]
    assert pred in {"LOW", "MEDIUM", "HIGH"}
    proba = bundle["model"].predict_proba(X)[0]
    assert abs(proba.sum() - 1.0) < 1e-6


def test_metrics_recorded(bundle):
    metrics = bundle["metrics"]
    assert metrics["model_name"] == "hist_gradient_boosting"
    assert metrics["accuracy"] > 0.7
    assert "model_comparison" in metrics
    assert "random_forest" in metrics["model_comparison"]
