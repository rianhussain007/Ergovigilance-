"""Temporal Risk Pattern Detection — sustained risk, trajectory, and prediction.

Detects:
1. Sustained risk: how long has risk been elevated?
2. Risk trajectory: is risk improving, stable, or worsening?
3. Risk prediction: where will risk be in N seconds?
4. Burst detection: sudden spikes vs gradual increase

This module is stateful — it maintains a sliding window of risk scores
and computes temporal patterns from the history.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class TemporalRiskPattern:
    """Immutable snapshot of temporal risk analysis."""
    
    # Sustained risk
    sustained_risk_seconds: float = 0.0  # How long risk has been above MEDIUM
    sustained_high_seconds: float = 0.0  # How long risk has been HIGH
    
    # Trajectory
    trajectory: str = "stable"  # "improving", "stable", "worsening"
    trajectory_confidence: float = 0.0  # 0-100%
    trajectory_slope: float = 0.0  # risk units per second
    
    # Prediction
    predicted_risk_30s: float = 0.0  # Predicted risk in 30 seconds
    predicted_risk_60s: float = 0.0  # Predicted risk in 60 seconds
    
    # Burst detection
    is_burst: bool = False  # Sudden spike (not gradual)
    burst_magnitude: float = 0.0  # How sudden (risk units / second)
    
    # Window stats
    mean_risk_10s: float = 0.0  # Average risk over last 10 seconds
    mean_risk_30s: float = 0.0  # Average risk over last 30 seconds
    max_risk_30s: float = 0.0  # Peak risk in last 30 seconds
    risk_volatility: float = 0.0  # Std dev of risk in last 30 seconds
    
    def to_dict(self) -> dict:
        return {
            "sustained_risk_seconds": self.sustained_risk_seconds,
            "sustained_high_seconds": self.sustained_high_seconds,
            "trajectory": self.trajectory,
            "trajectory_confidence": self.trajectory_confidence,
            "trajectory_slope": self.trajectory_slope,
            "predicted_risk_30s": self.predicted_risk_30s,
            "predicted_risk_60s": self.predicted_risk_60s,
            "is_burst": self.is_burst,
            "burst_magnitude": self.burst_magnitude,
            "mean_risk_10s": self.mean_risk_10s,
            "mean_risk_30s": self.mean_risk_30s,
            "max_risk_30s": self.max_risk_30s,
            "risk_volatility": self.risk_volatility,
        }


class TemporalRiskTracker:
    """Tracks temporal risk patterns over time.
    
    Maintains a sliding window of risk scores and computes:
    - Sustained risk duration
    - Risk trajectory (linear regression on recent window)
    - Risk prediction (extrapolation)
    - Burst detection (sudden spikes)
    - Window statistics (mean, max, volatility)
    
    Usage:
        tracker = TemporalRiskTracker()
        # In your evaluation loop:
        pattern = tracker.update(final_risk, delta_seconds)
        # pattern contains all temporal analysis
    """
    
    def __init__(self, 
                 window_size: int = 300,  # 300 frames = ~10 seconds at 30fps
                 burst_threshold: float = 15.0,  # risk units per second
                 medium_threshold: float = 40.0,
                 high_threshold: float = 70.0):
        self._window_size = window_size
        self._burst_threshold = burst_threshold
        self._medium_threshold = medium_threshold
        self._high_threshold = high_threshold
        
        # Sliding window: (timestamp_seconds, risk_score)
        self._risk_window: deque[tuple[float, float]] = deque(maxlen=window_size)
        self._total_time: float = 0.0
        
        # Sustained risk tracking
        self._sustained_risk_start: Optional[float] = None
        self._sustained_high_start: Optional[float] = None
        
    def reset(self) -> None:
        """Reset all temporal state."""
        self._risk_window.clear()
        self._total_time = 0.0
        self._sustained_risk_start = None
        self._sustained_high_start = None
    
    def update(self, risk_score: float, delta_seconds: float) -> TemporalRiskPattern:
        """Update with new risk score and compute temporal patterns.
        
        Args:
            risk_score: Current risk score (0-100)
            delta_seconds: Time since last update
            
        Returns:
            TemporalRiskPattern with all temporal analysis
        """
        self._total_time += delta_seconds
        self._risk_window.append((self._total_time, risk_score))
        
        # Compute all patterns
        sustained = self._compute_sustained_risk()
        trajectory = self._compute_trajectory()
        prediction = self._compute_prediction()
        burst = self._compute_burst()
        stats = self._compute_window_stats()
        
        return TemporalRiskPattern(
            sustained_risk_seconds=sustained["risk"],
            sustained_high_seconds=sustained["high"],
            trajectory=trajectory["direction"],
            trajectory_confidence=trajectory["confidence"],
            trajectory_slope=trajectory["slope"],
            predicted_risk_30s=prediction["30s"],
            predicted_risk_60s=prediction["60s"],
            is_burst=burst["is_burst"],
            burst_magnitude=burst["magnitude"],
            mean_risk_10s=stats["mean_10s"],
            mean_risk_30s=stats["mean_30s"],
            max_risk_30s=stats["max_30s"],
            risk_volatility=stats["volatility"],
        )
    
    def _compute_sustained_risk(self) -> dict:
        """Compute how long risk has been sustained above thresholds."""
        if not self._risk_window:
            return {"risk": 0.0, "high": 0.0}
        
        current_time = self._risk_window[-1][0]
        current_risk = self._risk_window[-1][1]
        
        # Sustained MEDIUM+ risk
        if current_risk >= self._medium_threshold:
            if self._sustained_risk_start is None:
                self._sustained_risk_start = current_time
            sustained_risk = current_time - self._sustained_risk_start
        else:
            self._sustained_risk_start = None
            sustained_risk = 0.0
        
        # Sustained HIGH risk
        if current_risk >= self._high_threshold:
            if self._sustained_high_start is None:
                self._sustained_high_start = current_time
            sustained_high = current_time - self._sustained_high_start
        else:
            self._sustained_high_start = None
            sustained_high = 0.0
        
        return {"risk": sustained_risk, "high": sustained_high}
    
    def _compute_trajectory(self) -> dict:
        """Compute risk trajectory using linear regression on recent window.
        
        Returns:
            direction: "improving", "stable", "worsening"
            confidence: 0-100% (based on R²)
            slope: risk units per second
        """
        if len(self._risk_window) < 10:
            return {"direction": "stable", "confidence": 0.0, "slope": 0.0}
        
        # Use last 30 seconds of data for trajectory
        recent = [(t, r) for t, r in self._risk_window 
                  if t >= self._total_time - 30.0]
        
        if len(recent) < 5:
            return {"direction": "stable", "confidence": 0.0, "slope": 0.0}
        
        # Linear regression: risk = slope * time + intercept
        times = [t - recent[0][0] for t, _ in recent]  # normalize to 0
        risks = [r for _, r in recent]
        
        n = len(times)
        sum_t = sum(times)
        sum_r = sum(risks)
        sum_tr = sum(t * r for t, r in zip(times, risks))
        sum_t2 = sum(t * t for t in times)
        
        denominator = n * sum_t2 - sum_t * sum_t
        if abs(denominator) < 1e-10:
            return {"direction": "stable", "confidence": 0.0, "slope": 0.0}
        
        slope = (n * sum_tr - sum_t * sum_r) / denominator
        intercept = (sum_r - slope * sum_t) / n
        
        # R² (coefficient of determination)
        mean_r = sum_r / n
        ss_res = sum((r - (slope * t + intercept)) ** 2 for t, r in zip(times, risks))
        ss_tot = sum((r - mean_r) ** 2 for r in risks)
        r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
        
        # Direction and confidence
        if slope < -0.5:  # improving by more than 0.5 risk units/sec
            direction = "improving"
        elif slope > 0.5:  # worsening by more than 0.5 risk units/sec
            direction = "worsening"
        else:
            direction = "stable"
        
        confidence = max(0.0, min(100.0, r_squared * 100.0))
        
        return {"direction": direction, "confidence": confidence, "slope": slope}
    
    def _compute_prediction(self) -> dict:
        """Predict future risk using trajectory extrapolation.
        
        Returns:
            risk_30s: predicted risk in 30 seconds
            risk_60s: predicted risk in 60 seconds
        """
        if len(self._risk_window) < 10:
            current_risk = self._risk_window[-1][1] if self._risk_window else 0.0
            return {"30s": current_risk, "60s": current_risk}
        
        # Get trajectory
        trajectory = self._compute_trajectory()
        slope = trajectory["slope"]
        current_risk = self._risk_window[-1][1]
        
        # Extrapolate (clamped to 0-100)
        predicted_30s = max(0.0, min(100.0, current_risk + slope * 30.0))
        predicted_60s = max(0.0, min(100.0, current_risk + slope * 60.0))
        
        return {"30s": predicted_30s, "60s": predicted_60s}
    
    def _compute_burst(self) -> dict:
        """Detect sudden spikes (bursts) vs gradual increase.
        
        A burst is defined as:
        - Risk increased by > burst_threshold in < 2 seconds
        - Not part of a gradual trend (trajectory is stable before spike)
        """
        if len(self._risk_window) < 5:
            return {"is_burst": False, "magnitude": 0.0}
        
        # Check last 2 seconds
        recent_2s = [(t, r) for t, r in self._risk_window 
                     if t >= self._total_time - 2.0]
        
        if len(recent_2s) < 2:
            return {"is_burst": False, "magnitude": 0.0}
        
        # Risk change in last 2 seconds
        risk_change = recent_2s[-1][1] - recent_2s[0][1]
        time_span = recent_2s[-1][0] - recent_2s[0][0]
        
        if time_span <= 0:
            return {"is_burst": False, "magnitude": 0.0}
        
        magnitude = risk_change / time_span  # risk units per second
        
        # Is it a burst? (sudden spike, not gradual)
        is_burst = (magnitude > self._burst_threshold and 
                   risk_change > 15.0)  # at least 15 points jump
        
        return {"is_burst": is_burst, "magnitude": magnitude}
    
    def _compute_window_stats(self) -> dict:
        """Compute window statistics (mean, max, volatility)."""
        if not self._risk_window:
            return {"mean_10s": 0.0, "mean_30s": 0.0, "max_30s": 0.0, "volatility": 0.0}
        
        # Last 10 seconds
        recent_10s = [r for t, r in self._risk_window 
                     if t >= self._total_time - 10.0]
        mean_10s = sum(recent_10s) / len(recent_10s) if recent_10s else 0.0
        
        # Last 30 seconds
        recent_30s = [r for t, r in self._risk_window 
                     if t >= self._total_time - 30.0]
        mean_30s = sum(recent_30s) / len(recent_30s) if recent_30s else 0.0
        max_30s = max(recent_30s) if recent_30s else 0.0
        
        # Volatility (standard deviation)
        if len(recent_30s) > 1:
            variance = sum((r - mean_30s) ** 2 for r in recent_30s) / len(recent_30s)
            volatility = math.sqrt(variance)
        else:
            volatility = 0.0
        
        return {"mean_10s": mean_10s, "mean_30s": mean_30s, "max_30s": max_30s, "volatility": volatility}
    
    def get_pattern_summary(self) -> str:
        """Get a human-readable summary of the current temporal pattern."""
        if not self._risk_window:
            return "No data yet"
        
        pattern = self.update(self._risk_window[-1][1], 0.0)
        
        parts = []
        
        # Sustained risk
        if pattern.sustained_risk_seconds > 0:
            parts.append(f"Elevated risk for {pattern.sustained_risk_seconds:.0f}s")
        if pattern.sustained_high_seconds > 0:
            parts.append(f"HIGH risk for {pattern.sustained_high_seconds:.0f}s")
        
        # Trajectory
        if pattern.trajectory != "stable":
            parts.append(f"Risk {pattern.trajectory} ({pattern.trajectory_confidence:.0f}% confident)")
        
        # Burst
        if pattern.is_burst:
            parts.append(f"Sudden spike: +{pattern.burst_magnitude:.1f} risk/sec")
        
        # Prediction
        if pattern.predicted_risk_30s > 70:
            parts.append(f"Predicted HIGH in 30s ({pattern.predicted_risk_30s:.0f})")
        
        return " | ".join(parts) if parts else "Stable, low risk"
