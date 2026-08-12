"""Shared data types for ErgoVigilance.

Dataclasses used across multiple subsystems.
Original modules re-export these for backward compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from backend.context.engine import ContextSnapshot


@dataclass
class ProcessedFrame:
    """Output of the CV pipeline — one per processed frame."""
    keypoints: list = field(default_factory=list)
    features: dict = field(default_factory=dict)
    risk_level: str = "LOW"
    confidence: float = 0.0
    person_detected: bool = False
    task_info: Optional[dict] = None
    issues: list = field(default_factory=list)
    recommendations: list = field(default_factory=list)
    timestamp: float = 0.0
    unavailable_features: list = field(default_factory=list)
    approximate_features: list = field(default_factory=list)
    lower_body_confidence: float = 0.0
    # Authoritative standard-method assessment (RULA vs REBA by body
    # visibility): {"method", "score", "risk_level", "is_partial", "reason", ...}
    standard_assessment: dict = field(default_factory=dict)
    # Tier 3: camera-framing intelligence + per-joint angle uncertainty
    # (sigma, degrees) used for uncertainty-aware scoring.
    framing: dict = field(default_factory=dict)
    # Tier 3: number of people MediaPipe detected in the frame (num_poses>1
    # foundation). The pipeline still scores the PRIMARY person.
    person_count: int = 1


@dataclass
class LiveState:
    """Shared runtime state — always contains the latest processed pipeline output."""
    session_active: bool = False
    session_id: Optional[str] = None
    session_start: Optional[float] = None

    current_frame: Optional[np.ndarray] = None
    overlaid_frame: Optional[np.ndarray] = None
    features: dict = field(default_factory=dict)
    risk_level: str = "LOW"
    risk_score: float = 0.0
    confidence: float = 0.0
    person_detected: bool = False
    keypoints: list = field(default_factory=list)

    task_name: str = "Unknown"
    task_confidence: float = 0.0
    task_duration_seconds: float = 0.0
    issues: list = field(default_factory=list)
    worker_recommendation: str = ""
    supervisor_recommendation: str = ""

    fps: float = 0.0
    inference_latency_ms: float = 0.0
    timestamp: str = ""
    camera_status: str = "disconnected"
    frame_width: int = 0
    frame_height: int = 0

    unavailable_features: list = field(default_factory=list)
    lower_body_confidence: float = 0.0
    # Tier 3 framing intelligence + person count
    framing: dict = field(default_factory=dict)
    person_count: int = 1

    # Monotonic frame counter for the current processed frame — lets stream
    # consumers (e.g. the MJPEG feed) skip re-encoding identical frames.
    frame_number: int = 0

    context_snapshot: Optional[ContextSnapshot] = None
