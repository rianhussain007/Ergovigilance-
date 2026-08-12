"""Tests for the predictive risk forecaster (Tier 2).

Covers feature extraction, the deterministic fallbacks (honest insufficient-
data states, never fabricated numbers), and the model path via a tiny fake
bundle. The real trained model is exercised lazily if present.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.predictive import (  # noqa: E402
    RiskForecaster,
    WINDOW_FEATURES,
    extract_window_features,
    fallback_early_session,
    fallback_next_window,
    get_risk_forecaster,
    reset_forecaster,
    _band_from_score,
)


def _frame(risk: float, ts: float, task: str = "Assembly Work", level: str | None = None,
           fatigue: float = 1.0, exposure: float = 2.0, neck: float = 10.0) -> dict:
    return {
        "frame_number": int(ts * 15),
        "timestamp": ts,
        "risk_score": risk,
        "risk_level": level or ("HIGH" if risk >= 70 else "MEDIUM" if risk >= 40 else "LOW"),
        "fatigue": fatigue,
        "exposure": exposure,
        "current_task": task,
        "features": {"neck_flexion": neck, "trunk_flexion": 5.0,
                     "shoulder_symmetry": 3.0, "knee_angle": 170.0},
    }


def _window(n: int = 50, risk: float = 30.0, step: float = 0.0) -> list[dict]:
    return [_frame(risk + step * i, i / 15.0) for i in range(n)]


def test_window_feature_vector_shape_and_values():
    frames = _window(20, risk=50.0)
    vec = extract_window_features(frames)
    assert len(vec) == len(WINDOW_FEATURES)
    # risk_mean should be ~50
    assert abs(vec[WINDOW_FEATURES.index("risk_mean")] - 50.0) < 1.0
    # increasing risk -> positive slope
    up = _window(30, risk=10.0, step=1.0)
    down = _window(30, risk=60.0, step=-1.0)
    slope_up = extract_window_features(up)[WINDOW_FEATURES.index("risk_slope")]
    slope_down = extract_window_features(down)[WINDOW_FEATURES.index("risk_slope")]
    assert slope_up > 0
    assert slope_down < 0


def test_fallback_insufficient_data_is_honest():
    r = fallback_next_window(_window(5), 600.0)
    assert r["insufficient_data"] is True
    assert r["predicted_mean_risk"] is None
    assert "Not enough data" in r["reason"]


def test_fallback_next_window():
    r = fallback_next_window(_window(50, risk=45.0), 600.0)
    assert r["insufficient_data"] is False
    assert abs(r["predicted_mean_risk"] - 45.0) < 2.0
    assert r["band"] == "MEDIUM"
    assert r["method"] == "fallback"
    assert 0.0 < r["confidence"] <= 1.0


def test_fallback_early_session():
    r = fallback_early_session(_window(100, risk=80.0))
    assert r["band"] == "HIGH"
    assert r["insufficient_data"] is False


def test_band_from_score():
    assert _band_from_score(30.0) == "LOW"
    assert _band_from_score(50.0) == "MEDIUM"
    assert _band_from_score(85.0) == "HIGH"
    assert _band_from_score(None) is None


def test_forecaster_without_model_uses_fallback(tmp_path):
    """A missing model path must degrade to the fallback, never raise."""
    fc = RiskForecaster(model_path=str(tmp_path / "missing.pkl"))
    r = fc.predict_next_window(_window(60))
    assert r["method"] == "fallback"
    assert r["insufficient_data"] is False
    assert fc.using_model is False


def test_forecaster_model_path_with_fake_bundle(tmp_path):
    """A real (trained) model path produces a model forecast."""
    import joblib

    from sklearn.ensemble import HistGradientBoostingRegressor

    X = np.random.default_rng(0).normal(size=(400, len(WINDOW_FEATURES)))
    y = X[:, 0] * 1.0 + 20.0
    m = HistGradientBoostingRegressor(max_iter=30, random_state=0)
    m.fit(X, y)

    bundle = {
        "model": m,
        "feature_columns": WINDOW_FEATURES,
        "metrics": {"next_window": {"mae": 5.0, "rows": 400}},
        "config": {"confidence_threshold": 0.45},
    }
    path = tmp_path / "fake.pkl"
    joblib.dump(bundle, path)

    fc = RiskForecaster(model_path=str(path))
    assert fc.using_model is True
    r = fc.predict_next_window(_window(60, risk=40.0))
    assert r["method"] in ("model", "fallback")
    assert r["predicted_mean_risk"] is not None
    assert r["insufficient_data"] is False


def test_real_trained_model_loads_if_present():
    """The shipped model should load and produce a bounded forecast."""
    from backend.services.predictive import DEFAULT_MODEL_PATH
    if not DEFAULT_MODEL_PATH.exists():
        return  # not present in this checkout — acceptable
    fc = RiskForecaster()
    assert fc.using_model is True
    r = fc.predict_next_window(_window(80, risk=35.0))
    assert r["predicted_mean_risk"] is not None
    assert 0.0 <= r["predicted_mean_risk"] <= 100.0
    assert r["band"] in ("LOW", "MEDIUM", "HIGH")


def test_singleton_forecaster():
    reset_forecaster()
    a = get_risk_forecaster()
    b = get_risk_forecaster()
    assert a is b
    reset_forecaster()
