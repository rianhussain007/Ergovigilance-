"""Runtime cross-check helper for the REBA-informed risk calibration model.

The calibration model (models/risk_calibration_model.pkl) predicts the
REBA-informed risk band (LOW/MEDIUM/HIGH) from the pipeline's features.
It is an ADVISORY overlay: the deterministic rule-based
``risk_from_features`` remains authoritative for alerting. Use
``predict_risk_band()`` to surface a model-confidence hint in UIs or
reports. Missing/unreadable model files degrade to ``None`` — this
helper never raises at runtime.

See scripts/train_risk_calibration.py and reports/risk_calibration_report.md.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Mapping, Optional

_MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "risk_calibration_model.pkl"
_BUNDLE: Optional[dict] = None
_TRIED = False


def _load() -> Optional[dict]:
    global _BUNDLE, _TRIED
    if _TRIED:
        return _BUNDLE
    _TRIED = True
    try:
        import joblib  # optional runtime dep — returns None if unavailable
        path = Path(os.environ.get("ERGOVIGILANCE_RISK_MODEL", "") or _MODEL_PATH)
        if not path.exists():
            return None
        bundle = joblib.load(path)
        if not isinstance(bundle, dict) or "model" not in bundle:
            return None
        _BUNDLE = bundle
    except Exception:
        _BUNDLE = None
    return _BUNDLE


def predict_risk_band(features: Mapping[str, float]) -> Optional[Dict[str, object]]:
    """Predict the REBA-informed risk band from pipeline features.

    Returns ``None`` when the model is unavailable. Otherwise a dict:
    ``{"band": str, "confidence": float}`` (confidence = 0-1 probability of
    the winning band). Most meaningful on full-visibility frames: sparse
    features are fed as 0.0, so partial-visibility poses understate the
    cross-check.
    """
    bundle = _load()
    if bundle is None:
        return None
    try:
        cols = bundle["feature_columns"]
        row = [features.get(c, 0.0) for c in cols]
        proba = bundle["model"].predict_proba([row])[0]
        best = int(proba.argmax())
        return {
            "band": bundle["labels"][best],
            "confidence": round(float(proba[best]), 3),
        }
    except Exception:
        return None


def band_agrees(band: str | None, risk_level: str | None) -> bool | None:
    """Case-insensitive agreement between the calibrated model band and the
    rule-based risk level. Returns None when either side is missing (no
    comparison possible)."""
    if not band or not risk_level:
        return None
    return str(band).upper() == str(risk_level).upper()


def reset_cache() -> None:
    """Clear the cached bundle (used by tests)."""
    global _BUNDLE, _TRIED
    _BUNDLE = None
    _TRIED = False
