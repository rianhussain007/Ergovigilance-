from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np


class ContextSnapshot:
    pass


@dataclass
class ProcessedFrame:
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


@dataclass
class LiveState:
    session_active: bool = False
    session_id: Optional[str] = None
    session_start: Optional[float] = None

    current_frame: Optional[np.ndarray] = None
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

    context_snapshot: Optional[ContextSnapshot] = None
