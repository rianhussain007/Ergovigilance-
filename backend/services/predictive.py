"""Predictive risk analytics (Tier 2 of the excluded-scope build).

A ``RiskForecaster`` that answers two questions from real pipeline data:

1. **Next-window forecast** — given the last N frames of a live session, what
   is the mean risk score over the next ``horizon_seconds``? Powers a live
   "risk forecast: next 10 min" gauge on Live Monitoring.

2. **Early-session forecast** — given the first portion of a session, what
   will the full-session mean risk be? Powers the Analytics "Predictive
   Insights" card (the safety-manager pitch: catch a trending-high shift
   early).

Design (same contract as ``TaskRecognition``):
  - Model-primary: a trained HistGradientBoosting regressor
    (``models/risk_forecaster.pkl``, loaded lazily) decides when its
    prediction is available and confident enough.
  - Statistical fallback: recent-window / early-window mean risk with a
    confidence that shrinks with data volume — always honest, never a
    fabricated number.
  - Never raises: a missing/corrupt model degrades to the fallback.

The engine stays rule-based and authoritative; this is an *additional
advisory signal* (the standing ML-scope decision).
"""

from __future__ import annotations

import logging
import math
import os
import time
from pathlib import Path
from typing import Any, Sequence

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "risk_forecaster.pkl"

# Feature columns for one frame window (aggregate stats over the window).
WINDOW_FEATURES = [
    "risk_mean", "risk_std", "risk_min", "risk_max", "risk_last", "risk_slope",
    "risk_high_pct", "risk_medium_pct",
    "fatigue_mean", "fatigue_slope", "exposure_mean", "exposure_slope",
    "neck_mean", "trunk_mean", "shoulder_mean", "knee_mean",
    "task_diversity", "frame_count", "window_seconds",
]

# Minimum number of frames needed for a fallback forecast (else "not enough data").
MIN_FALLBACK_FRAMES = 15
# Confidence below which the fallback is used instead of the model.
MODEL_CONFIDENCE_THRESHOLD = 0.45


def _risk_score(entry: dict) -> float:
    """Extract a numeric risk score from a timeline/frame entry."""
    val = entry.get("risk_score", entry.get("context_score"))
    if val is None:
        level = (entry.get("risk_level") or "LOW").upper()
        return {"LOW": 10.0, "MEDIUM": 50.0, "HIGH": 90.0}.get(level, 10.0)
    try:
        return float(val)
    except (TypeError, ValueError):
        return 10.0


def _feat(entry: dict, name: str) -> float:
    feats = entry.get("features") or {}
    val = feats.get(name)
    try:
        v = float(val)
    except (TypeError, ValueError):
        return float("nan")
    return v


def _slope(y: Sequence[float]) -> float:
    """Linear regression slope over a series (per-frame, ignores time spacing)."""
    n = len(y)
    if n < 2:
        return 0.0
    x = np.arange(n, dtype=float)
    y = np.asarray(y, dtype=float)
    denom = float(n * np.sum(x * x) - np.sum(x) ** 2)
    if abs(denom) < 1e-9:
        return 0.0
    return float((n * np.sum(x * y) - np.sum(x) * np.sum(y)) / denom)


def _safe_mean(values: Sequence[float]) -> float:
    vals = [v for v in values if v == v]  # drop NaN
    return float(np.mean(vals)) if vals else 0.0


def extract_window_features(frames: Sequence[dict]) -> list[float]:
    """Aggregate one window of timeline entries into model feature vector.

    ``frames`` must be in chronological order. Returns a vector aligned with
    ``WINDOW_FEATURES`` (NaN → 0 handled by the caller/model).
    """
    if not frames:
        return [0.0] * len(WINDOW_FEATURES)

    risks = [_risk_score(f) for f in frames]
    levels = [(f.get("risk_level") or "LOW").upper() for f in frames]
    fatigue = [float(f.get("fatigue", 0.0) or 0.0) for f in frames]
    exposure = [float(f.get("exposure", 0.0) or 0.0) for f in frames]

    last_ts = frames[-1].get("timestamp", 0.0)
    first_ts = frames[0].get("timestamp", 0.0)
    window_seconds = max(0.0, float(last_ts or 0.0) - float(first_ts or 0.0))

    high_pct = sum(1 for lv in levels if lv == "HIGH") / len(levels) * 100.0
    med_pct = sum(1 for lv in levels if lv == "MEDIUM") / len(levels) * 100.0

    tasks = {f.get("current_task") for f in frames if f.get("current_task")}

    vec = [
        float(np.mean(risks)),
        float(np.std(risks)),
        float(np.min(risks)),
        float(np.max(risks)),
        risks[-1],
        _slope(risks),
        high_pct,
        med_pct,
        _safe_mean(fatigue),
        _slope(fatigue),
        _safe_mean(exposure),
        _slope(exposure),
        _safe_mean([_feat(f, "neck_flexion") for f in frames]),
        _safe_mean([_feat(f, "trunk_flexion") for f in frames]),
        _safe_mean([_feat(f, "shoulder_symmetry") for f in frames]),
        _safe_mean([_feat(f, "knee_angle") for f in frames]),
        float(len(tasks)),
        float(len(frames)),
        window_seconds,
    ]
    return [0.0 if v != v else v for v in vec]  # NaN-safe


def fallback_next_window(frames: Sequence[dict], horizon_seconds: float) -> dict:
    """Deterministic fallback: recent mean risk + decayed confidence.

    Confidence grows with frame count up to a plateau; below MIN_FALLBACK_FRAMES
    the forecast reports ``insufficient_data`` instead of fabricating a number.
    """
    n = len(frames)
    if n < MIN_FALLBACK_FRAMES:
        return {
            "predicted_mean_risk": None,
            "band": None,
            "confidence": 0.0,
            "insufficient_data": True,
            "reason": f"Not enough data ({n} frames; need {MIN_FALLBACK_FRAMES})",
            "method": "fallback",
        }
    risks = [_risk_score(f) for f in frames]
    mean_risk = round(float(np.mean(risks)), 1)
    confidence = round(min(1.0, 0.4 + 0.6 * min(1.0, n / 200.0)), 2)
    band = _band_from_score(mean_risk)
    return {
        "predicted_mean_risk": mean_risk,
        "band": band,
        "confidence": confidence,
        "insufficient_data": False,
        "reason": f"Recent-window mean over {n} frames (statistical fallback)",
        "method": "fallback",
        "horizon_seconds": horizon_seconds,
    }


def fallback_early_session(frames: Sequence[dict]) -> dict:
    """Fallback for the early-session forecast: first-window mean risk."""
    n = len(frames)
    if n < MIN_FALLBACK_FRAMES:
        return {
            "predicted_mean_risk": None,
            "band": None,
            "confidence": 0.0,
            "insufficient_data": True,
            "reason": f"Not enough data ({n} frames; need {MIN_FALLBACK_FRAMES})",
            "method": "fallback",
        }
    risks = [_risk_score(f) for f in frames]
    mean_risk = round(float(np.mean(risks)), 1)
    confidence = round(min(1.0, 0.35 + 0.5 * min(1.0, n / 150.0)), 2)
    return {
        "predicted_mean_risk": mean_risk,
        "band": _band_from_score(mean_risk),
        "confidence": confidence,
        "insufficient_data": False,
        "reason": f"Early-window mean over {n} frames (statistical fallback)",
        "method": "fallback",
    }


def _band_from_score(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= 70:
        return "HIGH"
    if score >= 40:
        return "MEDIUM"
    return "LOW"


class RiskForecaster:
    """Model-primary predictive risk forecaster with statistical fallback.

    Usage::

        fc = RiskForecaster()            # lazy-loads models/risk_forecaster.pkl
        fc.predict_next_window(frames)   # -> dict forecast
        fc.predict_early_session(frames) # -> dict forecast
    """

    def __init__(self, model_path: str | None = None) -> None:
        env_path = os.environ.get("ERGOVIGILANCE_RISK_MODEL")
        self._model_path = Path(model_path) if model_path else (
            Path(env_path) if env_path else DEFAULT_MODEL_PATH)
        self._bundle: dict | None = None
        self._tried = False
        self._load_error: str | None = None

    # ── Model loading ─────────────────────────────────────────────
    def _get_bundle(self) -> dict | None:
        if self._tried:
            return self._bundle
        self._tried = True
        try:
            import joblib
            if not self._model_path.exists():
                return None
            bundle = joblib.load(self._model_path)
            if not isinstance(bundle, dict) or "model" not in bundle:
                return None
            self._bundle = bundle
        except Exception as exc:
            self._load_error = str(exc)
            logger.warning("RiskForecaster model load failed (%s) — fallback only", exc)
            self._bundle = None
        return self._bundle

    @property
    def using_model(self) -> bool:
        return self._get_bundle() is not None

    @property
    def model_metrics(self) -> dict | None:
        bundle = self._get_bundle()
        return (bundle or {}).get("metrics") if bundle else None

    @property
    def load_error(self) -> str | None:
        return self._load_error

    # ── Predictions ───────────────────────────────────────────────
    def predict_next_window(
        self,
        frames: Sequence[dict],
        horizon_seconds: float = 600.0,
    ) -> dict:
        """Predict mean risk over the next ``horizon_seconds`` from the last
        frames of a live session."""
        bundle = self._get_bundle()
        if bundle is None:
            return fallback_next_window(frames, horizon_seconds)

        features = np.asarray([extract_window_features(frames)], dtype=float)
        model = bundle["model"]
        try:
            pred = float(model.predict(features)[0])
        except Exception as exc:
            logger.warning("RiskForecaster predict failed: %s", exc)
            return fallback_next_window(frames, horizon_seconds)

        # Confidence: model agreement with the deterministic fallback. When
        # both agree, the number is trustworthy; when they disagree strongly,
        # the model is extrapolating beyond its training data — defer to the
        # fallback for honesty.
        fallback = fallback_next_window(frames, horizon_seconds)
        fallback_val = fallback.get("predicted_mean_risk")
        agreement = 1.0
        if fallback_val is not None:
            diff = abs(pred - fallback_val)
            agreement = max(0.0, 1.0 - diff / 50.0)
        confidence = round(min(1.0, agreement * (0.6 + 0.4 * min(1.0, len(frames) / 150.0))), 2)

        if confidence < MODEL_CONFIDENCE_THRESHOLD:
            fb = fallback_next_window(frames, horizon_seconds)
            fb["model_considered"] = True
            fb["reason"] = f"Model disagreed with fallback (conf {confidence:.2f}) — using fallback"
            return fb

        return {
            "predicted_mean_risk": round(pred, 1),
            "band": _band_from_score(pred),
            "confidence": confidence,
            "insufficient_data": False,
            "reason": f"Trained forecaster on {len(frames)} frames (model + fallback agreement)",
            "method": "model",
            "horizon_seconds": horizon_seconds,
            "model_metrics": bundle.get("metrics", {}),
        }

    def predict_early_session(self, frames: Sequence[dict]) -> dict:
        """Predict full-session mean risk from the first frames of a session."""
        bundle = self._get_bundle()
        if bundle is None:
            return fallback_early_session(frames)

        features = np.asarray([extract_window_features(frames)], dtype=float)
        model = bundle["model"]
        try:
            pred = float(model.predict(features)[0])
        except Exception as exc:
            logger.warning("RiskForecaster early predict failed: %s", exc)
            return fallback_early_session(frames)

        fallback = fallback_early_session(frames)
        fallback_val = fallback.get("predicted_mean_risk")
        agreement = 1.0
        if fallback_val is not None:
            agreement = max(0.0, 1.0 - abs(pred - fallback_val) / 50.0)
        confidence = round(min(1.0, agreement * (0.55 + 0.45 * min(1.0, len(frames) / 200.0))), 2)

        if confidence < MODEL_CONFIDENCE_THRESHOLD:
            fb = fallback_early_session(frames)
            fb["model_considered"] = True
            fb["reason"] = f"Model disagreed with fallback (conf {confidence:.2f}) — using fallback"
            return fb

        return {
            "predicted_mean_risk": round(pred, 1),
            "band": _band_from_score(pred),
            "confidence": confidence,
            "insufficient_data": False,
            "reason": f"Trained forecaster on {len(frames)} early frames (model + fallback agreement)",
            "method": "model",
            "model_metrics": bundle.get("metrics", {}),
        }

    def predict_per_joint(self, frames: Sequence[dict], horizon_seconds: float = 600.0) -> dict:
        """Forecast next-window mean angle for each tracked joint.

        Tier 3 per-joint extension: projects each joint's angle forward from
        the recent window using its current mean plus a trend (slope) term,
        damped toward the window mean. Statistical and honest — always
        ``insufficient_data`` below ``MIN_FALLBACK_FRAMES``, never fabricated.
        """
        n = len(frames)
        if n < MIN_FALLBACK_FRAMES:
            return {
                "joints": [],
                "insufficient_data": True,
                "reason": f"Not enough data ({n} frames; need {MIN_FALLBACK_FRAMES})",
                "method": "fallback",
            }

        joints = [
            ("neck_flexion", 0.0, 60.0),
            ("trunk_flexion", 0.0, 90.0),
            ("shoulder_symmetry", 0.0, 40.0),
            ("knee_angle", 80.0, 180.0),
            ("wrist_deviation_angle", 0.0, 40.0),
        ]
        out = []
        for name, lo, hi in joints:
            vals = [_feat(f, name) for f in frames]
            vals = [v for v in vals if v == v]
            if len(vals) < 5:
                out.append({"joint": name, "available": False, "predicted_mean": None})
                continue
            mean = float(np.mean(vals))
            slope = _slope(vals)
            # Project forward but damp the extrapolation so a short noisy trend
            # can't launch an implausible forecast.
            projected = mean + slope * min(horizon_seconds / 60.0, 10.0)
            predicted = round(min(hi, max(lo, projected)), 1)
            risk = "elevated" if predicted >= max(lo, min(hi, 0.7 * (lo + hi))) else "normal"
            out.append({
                "joint": name,
                "available": True,
                "current_mean": round(mean, 1),
                "trend_slope": round(slope, 3),
                "predicted_mean": predicted,
                "band": risk,
            })
        return {
            "joints": out,
            "insufficient_data": False,
            "reason": f"Per-joint trend projection over {n} frames (statistical)",
            "method": "fallback",
            "horizon_seconds": horizon_seconds,
        }

    def reset(self) -> None:
        self._bundle = None
        self._tried = False
        self._load_error = None


_forecaster: RiskForecaster | None = None


def get_risk_forecaster() -> RiskForecaster:
    """Process-wide singleton forecaster (lazy)."""
    global _forecaster
    if _forecaster is None:
        _forecaster = RiskForecaster()
    return _forecaster


def reset_forecaster() -> None:
    global _forecaster
    _forecaster = None
