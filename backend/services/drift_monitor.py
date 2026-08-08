"""Drift-monitoring canary for the task classifier.

Tracks how often the trained task model (models/task_model_v2.pkl) is used
vs. how often the pipeline falls back to the deterministic Gaussian scorer.
A rising fallback rate is the earliest signal that the classifier is
drifting (unseen postures, changed camera framing, distribution shift), so
operators can retrain before accuracy visibly degrades.

Design:
- A module-level singleton with a bounded, lock-guarded sample deque.
- ``record(source, confidence)`` is called once per processed frame with a
  person detected (cheap — a dict append under a lock).
- ``summary()`` computes the rolling fallback rate over the configured
  window plus a simple first-half vs second-half trend, so an *increasing*
  fallback rate is distinguishable from a steady one.

Pure stdlib — no FastAPI/mediapipe imports — so it is unit-testable and
safe to import from any layer (pose engine, API, scripts).
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Optional

WINDOW_SECONDS = 300  # rolling 5-minute window by default


class DriftMonitor:
    def __init__(self, window_seconds: int = WINDOW_SECONDS, max_samples: int = 20000) -> None:
        self._window_seconds = max(1, window_seconds)
        self._max_samples = max(100, max_samples)
        self._samples: deque[tuple[float, str, float]] = deque(maxlen=self._max_samples)
        self._lock = threading.Lock()
        self._now = time.time  # injectable clock for deterministic tests

    def record(self, source: str, confidence: float, now: float | None = None) -> None:
        """Record one prediction sample.

        ``source`` is ``"model"`` (trained classifier decided) or
        ``"gaussian"`` (deterministic fallback decided). ``now`` is an
        injectable timestamp for tests.
        """
        with self._lock:
            self._samples.append(((now if now is not None else self._now()), source, float(confidence)))

    def reset(self) -> None:
        with self._lock:
            self._samples.clear()

    def summary(self) -> dict:
        """Rolling drift statistics over the window.

        Returns:
            {
                "samples": int,
                "window_seconds": int,
                "model_samples": int,
                "gaussian_samples": int,
                "fallback_rate": float,        # 0-100, gaussian share
                "avg_confidence": float | None,  # all predictions
                "avg_model_confidence": float | None,
                "trend": "stable" | "rising" | "falling",  # fallback rate
                "trend_delta_pp": float,       # percentage points, +ve = rising
                "healthy": bool,               # fallback_rate <= 50
            }
        """
        with self._lock:
            cutoff = self._now() - self._window_seconds
            recent = [s for s in self._samples if s[0] >= cutoff]
        if not recent:
            return {
                "samples": 0,
                "window_seconds": self._window_seconds,
                "model_samples": 0,
                "gaussian_samples": 0,
                "fallback_rate": 0.0,
                "avg_confidence": None,
                "avg_model_confidence": None,
                "trend": "stable",
                "trend_delta_pp": 0.0,
                "healthy": True,
            }

        model_s = sum(1 for _, src, _ in recent if src == "model")
        gaussian_s = len(recent) - model_s
        fallback_rate = gaussian_s / len(recent) * 100.0

        confs = [c for _, _, c in recent]
        model_confs = [c for _, src, c in recent if src == "model"]

        # Trend: compare the fallback rate of the most recent half of the
        # window against the earlier half. Require a meaningful sample count
        # (>= 20) so a handful of frames can't false-alert on pure jitter.
        trend = "stable"
        delta_pp = 0.0
        if len(recent) >= 20:
            mid = len(recent) // 2
            first_half = recent[:mid]
            second_half = recent[mid:]
            if len(first_half) >= 10 and len(second_half) >= 10:
                fh_rate = sum(1 for _, src, _ in first_half if src == "gaussian") / len(first_half) * 100.0
                sh_rate = sum(1 for _, src, _ in second_half if src == "gaussian") / len(second_half) * 100.0
                delta_pp = round(sh_rate - fh_rate, 1)
                if delta_pp > 10.0:
                    trend = "rising"
                elif delta_pp < -10.0:
                    trend = "falling"

        return {
            "samples": len(recent),
            "window_seconds": self._window_seconds,
            "model_samples": model_s,
            "gaussian_samples": gaussian_s,
            "fallback_rate": round(fallback_rate, 1),
            "avg_confidence": round(sum(confs) / len(confs), 1) if confs else None,
            "avg_model_confidence": round(sum(model_confs) / len(model_confs), 1) if model_confs else None,
            "trend": trend,
            "trend_delta_pp": delta_pp,
            "healthy": fallback_rate <= 50.0,
        }


_monitor: Optional[DriftMonitor] = None
_monitor_lock = threading.Lock()


def get_drift_monitor() -> DriftMonitor:
    """Module-level singleton (process lifetime)."""
    global _monitor
    with _monitor_lock:
        if _monitor is None:
            _monitor = DriftMonitor()
        return _monitor


def reset_drift_monitor() -> None:
    """Clear the singleton (used by tests)."""
    global _monitor
    with _monitor_lock:
        _monitor = None
