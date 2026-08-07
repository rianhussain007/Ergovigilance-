"""Fatigue Model — estimates worker fatigue from session data.

Uses an exponential fatigue curve with recovery decay.
Purely deterministic — no ML, no biometric data.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class FatigueState:
    """Current fatigue assessment."""
    score: float = 0.0          # 0-100 (0 = fresh, 100 = exhausted)
    level: str = "fresh"        # fresh | mild | moderate | severe
    recovery_events: int = 0    # number of low-risk recovery periods


class FatigueModel:
    """Estimates worker fatigue based on session duration and exposure.

    Fatigue increases with:
    - Session duration (exponential curve)
    - Cumulative high-risk exposure
    - Repetitive task performance

    Fatigue decreases with:
    - Low-risk periods (recovery)
    - Dynamic movement tasks
    """

    # Fatigue accumulation rate per minute of session time.
    # At 60 minutes: fatigue ≈ 25 (mild)
    # At 120 minutes: fatigue ≈ 50 (moderate)
    # At 240 minutes: fatigue ≈ 75 (severe)
    _BASE_RATE = 0.42  # per minute

    # Additional fatigue per minute of high-risk exposure.
    _EXPOSURE_RATE = 0.8  # per minute of high-risk time

    # Recovery rate per minute of low-risk activity.
    _RECOVERY_RATE = 1.2  # per minute

    # Fatigue thresholds for level classification.
    _MILD_THRESHOLD = 20.0
    _MODERATE_THRESHOLD = 50.0
    _SEVERE_THRESHOLD = 75.0

    def __init__(self) -> None:
        self._state = FatigueState()
        self._low_risk_minutes: float = 0.0
        self._last_recovery_check: float = 0.0

    @property
    def state(self) -> FatigueState:
        return self._state

    def update(
        self,
        session_duration_seconds: float,
        high_risk_seconds: float,
        task_name: str,
        delta_seconds: float,
    ) -> None:
        """Update fatigue estimation for one frame.

        Args:
            session_duration_seconds: Total session time.
            high_risk_seconds: Cumulative high-risk exposure time.
            task_name: Current task classification.
            delta_seconds: Time since last update.
        """
        if delta_seconds <= 0:
            return

        delta_minutes = delta_seconds / 60.0

        # 1. Base fatigue from session duration (exponential curve)
        session_minutes = session_duration_seconds / 60.0
        base_fatigue = 100.0 * (1.0 - math.exp(-self._BASE_RATE * session_minutes / 30.0))

        # 2. Exposure penalty
        exposure_minutes = high_risk_seconds / 60.0
        exposure_fatigue = exposure_minutes * self._EXPOSURE_RATE

        # 3. Task modifier
        task_modifier = self._task_fatigue_modifier(task_name)

        # 4. Recovery from low-risk periods
        is_low_risk = self._is_low_risk_state(task_name)
        if is_low_risk:
            self._low_risk_minutes += delta_minutes
            recovery = self._low_risk_minutes * self._RECOVERY_RATE
        else:
            self._low_risk_minutes = max(0.0, self._low_risk_minutes - delta_minutes * 0.5)
            recovery = self._low_risk_minutes * self._RECOVERY_RATE * 0.3

        # Combine
        raw_fatigue = base_fatigue + exposure_fatigue + task_modifier - recovery
        self._state.score = max(0.0, min(100.0, raw_fatigue))

        # Classify level
        if self._state.score < self._MILD_THRESHOLD:
            self._state.level = "fresh"
        elif self._state.score < self._MODERATE_THRESHOLD:
            self._state.level = "mild"
        elif self._state.score < self._SEVERE_THRESHOLD:
            self._state.level = "moderate"
        else:
            self._state.level = "severe"

    def reset(self) -> None:
        """Reset fatigue state (e.g., on session restart)."""
        self._state = FatigueState()
        self._low_risk_minutes = 0.0
        self._last_recovery_check = 0.0

    def fatigue_modifier(self) -> float:
        """Compute the fatigue modifier (0-20) for risk scoring.

        Returns:
            Modifier from 0 (fresh) to 20 (severely fatigued).
        """
        return self._state.score * 0.2

    @staticmethod
    def _task_fatigue_modifier(task_name: str) -> float:
        """Additional fatigue based on task type (per minute)."""
        modifiers = {
            "Neutral Standing": 0.0,
            "Assembly Work": 0.3,
            "Reaching": 0.4,
            "Lifting / Picking": 0.6,
            "Inspection": 0.2,
        }
        return modifiers.get(task_name, 0.1) * 1.0

    @staticmethod
    def _is_low_risk_state(task_name: str) -> bool:
        """Whether the current task represents a low-risk recovery period."""
        return task_name in ("Neutral Standing", "Walking")
