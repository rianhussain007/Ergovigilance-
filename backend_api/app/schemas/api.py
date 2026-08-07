"""Pydantic schemas — exact contracts mirroring the React frontend types.

These are the single source of truth for all API responses.
The React frontend's types/api.ts must match these field names and types exactly.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Literal

from pydantic import BaseModel, Field


# --- Enums / Literals ---

RiskLevel = Literal["low", "moderate", "high"]
StatusType = Literal["active", "completed", "interrupted"]
FeatureStatus = Literal["good", "low", "moderate", "high"]
TrendDirection = Literal["improving", "stable", "deteriorating"]


# --- Nested Models ---

class SessionInfo(BaseModel):
    id: str
    workerName: str
    workerId: str
    startTime: str
    currentTime: str
    duration: int
    framesAnalyzed: int
    cameraStatus: str


class LiveStatus(BaseModel):
    riskLevel: RiskLevel
    riskScore: float
    confidence: float
    currentTask: str
    taskDurationSeconds: float = 0.0
    workerStatus: str


class ErgonomicFeature(BaseModel):
    id: str
    name: str
    value: Optional[float] = None
    unit: str
    min: float
    max: float
    status: FeatureStatus


class Issue(BaseModel):
    id: str
    severity: RiskLevel
    name: str
    timestamp: str
    detail: str


class Recommendations(BaseModel):
    worker: str
    supervisor: str


class SessionAnalytics(BaseModel):
    sessionDuration: str
    framesAnalyzed: int
    highestRisk: str
    mostFrequentIssue: str
    averageNeck: float
    averageTrunk: float
    averageKnee: float


class RiskDataPoint(BaseModel):
    time: str
    value: float


class TrendAnalysis(BaseModel):
    trend: TrendDirection
    averageRisk: float
    sessionsAnalyzed: int
    improving: int
    stable: int
    deteriorating: int


# --- Top-level Response Models ---

class DashboardResponse(BaseModel):
    session: SessionInfo
    liveStatus: LiveStatus
    ergonomicFeatures: List[ErgonomicFeature]
    issues: List[Issue]
    recommendations: Recommendations
    sessionAnalytics: SessionAnalytics
    riskHistory: List[RiskDataPoint]
    trendAnalysis: TrendAnalysis
    unavailableFeatures: List[str] = []


class RecentSessionSummary(BaseModel):
    id: str
    date: str
    duration: str
    highestRisk: str
    task: str
    status: StatusType
    worker_id: Optional[str] = None


class RecentAlertSummary(BaseModel):
    id: str
    title: str
    severity: str
    state: str
    created_at: str
    session_id: str


class SupervisorDashboardSummary(BaseModel):
    worker_count: int
    sessions_today: int
    open_alerts: int
    average_risk: Optional[float] = None
    recent_sessions: List[RecentSessionSummary]
    recent_alerts: List[RecentAlertSummary]


class AdminDashboardSummary(SupervisorDashboardSummary):
    total_users: int
    total_sessions: int
    backend_status: str
    database_status: str
    connected_camera_status: str
    role_distribution: dict[str, int]


class SessionRecord(BaseModel):
    id: str
    date: str
    duration: str
    highestRisk: str
    task: str
    status: StatusType
    worker_id: Optional[str] = None
    created_by_user_id: Optional[int] = None
    camera_id: Optional[str] = None


class PaginatedSessionsResponse(BaseModel):
    sessions: List[SessionRecord]
    total: int
    page: int
    pages: int


class SessionAlertEntry(BaseModel):
    id: str
    session_id: str
    frame_number: int
    created_at: str
    severity: str
    state: str
    title: str
    message: str
    trigger_rule: str
    confidence: float
    requires_ack: bool
    expires_at: str


class SessionDetailResponse(BaseModel):
    id: str
    status: StatusType = "completed"
    session_timestamp: str
    session_duration_seconds: float
    total_frames: int
    risk_percentages: dict
    most_frequent_issue: Optional[str] = None
    most_frequent_issue_count: int = 0
    highest_risk_level: str
    highest_risk_timestamp: Optional[str] = None
    avg_neck_flexion: float
    avg_trunk_flexion: float
    avg_shoulder_symmetry: float
    avg_knee_angle: float
    alerts: List[SessionAlertEntry] = Field(default_factory=list)
    worker_id: Optional[str] = None
    created_by_user_id: Optional[int] = None
    camera_id: Optional[str] = None
    video_path: Optional[str] = None
    video_recording_status: Optional[str] = None
    video_recording_error: Optional[str] = None
    video_frame_count: Optional[int] = None
    video_codec: Optional[str] = None


class WeeklyTrend(BaseModel):
    week: str
    averageRisk: float
    sessions: int
    incidents: int


class FeatureTrend(BaseModel):
    feature: str
    current: float
    previous: float
    change: float


class RiskDistribution(BaseModel):
    low: int
    moderate: int
    high: int


class TrendResponse(BaseModel):
    weeklyTrend: List[WeeklyTrend]
    featureTrends: List[FeatureTrend]
    riskDistribution: RiskDistribution


# --- Additional API Models ---

class CameraInfo(BaseModel):
    id: str
    name: str
    worker: str
    fps: int
    risk: RiskLevel
    recording: bool
    uptime: str
    status: Literal["streaming", "available"] = "available"


class WorkstationInfo(BaseModel):
    id: str
    name: str
    worker: str
    task: str
    risk: RiskLevel
    healthScore: int
    camera: str
    connected: bool
    neckAngle: float
    trunkAngle: float
    shoulderAngle: float
    kneeAngle: float
    issues: List[str]
    recommendation: str


class DeploymentMetrics(BaseModel):
    # Backend
    backendStatus: str
    backendVersion: str
    backendUptimeSeconds: float
    # Database
    databaseEngine: str
    databaseSizeBytes: int
    databaseStatus: str
    # Workers and Cameras
    cameraCount: int
    registeredWorkerCount: int
    activeSessionCount: int
    # Session (if active)
    sessionActive: bool
    sessionFps: float | None = None
    sessionInferenceLatencyMs: float | None = None


class WorkerSummary(BaseModel):
    id: str
    name: str
    status: RiskLevel
    task: str
    risk: float


class DepartmentHeatmapEntry(BaseModel):
    department: str
    averageRisk: float
    workerCount: int
    highRiskCount: int
    level: RiskLevel


class ManagerSummary(BaseModel):
    registeredWorkers: int
    highRiskWorkers: int
    todayAlerts: int
    sessionsCompleted: int
    mostCommonIssue: str = ""
    workers: List[WorkerSummary] = []
    departmentHeatmap: List[DepartmentHeatmapEntry] = []


AlertSeverity = Literal["critical", "warning", "info", "resolved", "low", "moderate", "high"]

class Alert(BaseModel):
    id: str
    severity: AlertSeverity
    title: str
    description: str
    timestamp: str
    worker: Optional[str] = None
    read: bool = False


class AlertResponse(BaseModel):
    """Alert from AlertEngine — mirrors backend.alerts.models.Alert."""
    id: str
    session_id: str
    frame_number: int
    created_at: str
    severity: str
    state: str
    title: str
    message: str
    trigger_rule: str
    confidence: float
    requires_ack: bool
    expires_at: str


class AlertSummary(BaseModel):
    """Summary of alert engine state."""
    total_fired: int
    active_count: int
    critical_count: int
    acknowledged_count: int
    consecutive_high: int


class AlertsResponse(BaseModel):
    """Full alert data from AlertEngine."""
    active: List[AlertResponse]
    history: List[AlertResponse]
    summary: AlertSummary


class AlertsHistoryResponse(BaseModel):
    """Paginated alert history from AlertEngine."""
    alerts: List[AlertResponse]
    total: int
    page: int
    pages: int


class ReportGenerateRequest(BaseModel):
    type: Literal["safety", "trend", "session", "summary", "csv"]
    dateRange: Optional[str] = None


class ReportGenerateResponse(BaseModel):
    id: str
    title: str
    message: str


class SessionActionResponse(BaseModel):
    id: str
    status: str
    message: str


class ReportRecord(BaseModel):
    id: str
    title: str
    type: str
    date: str
    status: str = "completed"
    size: str


class RecommendationResponse(BaseModel):
    """Single recommendation — mirrors backend.recommendations.models.Recommendation."""
    id: str
    title: str
    description: str
    category: str
    priority: str
    target: str
    trigger: str
    confidence: float
    estimated_benefit: str
    expires_at: str = ""


class RecommendationBundleData(BaseModel):
    """Bundle of recommendations generated for one frame."""
    recommendations: List[RecommendationResponse]
    summary: str
    highest_priority: str
    generated_at: str


class RecommendationsBundleResponse(BaseModel):
    """Full recommendation data from RecommendationEngine."""
    bundle: Optional[RecommendationBundleData] = None
    total_generated: int


class GuidanceFeedbackItem(BaseModel):
    """Single per-area guidance feedback entry."""
    area: str
    status: str
    text: str


class GuidanceSnapshot(BaseModel):
    """Human-readable posture guidance computed on-demand from features."""
    feedback: List[GuidanceFeedbackItem]
    flagged_areas: List[str]
    recommendations: List[str]


class ContextSnapshotResponse(BaseModel):
    """Context Intelligence snapshot — mirrors backend.context.engine.ContextSnapshot."""
    session_id: str
    frame_number: int
    captured_at: str
    worker_id: str
    base_risk: float
    context_modifier: float
    fatigue_score: float
    exposure_score: float
    confidence_modifier: float
    final_risk: float
    risk_score_normalized: float
    risk_level: str
    safety_state: str
    reason: str
    active_rules: List[str]
    feature_scores: dict
    guidance: Optional[GuidanceSnapshot] = None
    rula_informed_score: Optional[int] = None
    rula_is_partial: bool = False
    unavailable_features: List[str] = []
    approximate_features: List[str] = []
    lower_body_confidence: float = 0.0


class HistoryPoint(BaseModel):
    """Single data point for the risk history chart."""
    time: str
    value: float
    fatigue: float = 0.0
    exposure: float = 0.0
    risk_level: str = ""


class HistoryStatistics(BaseModel):
    """Aggregated statistics from the history engine."""
    frames_stored: int = 0
    session_duration_seconds: float = 0.0
    average_risk: float = 0.0
    maximum_risk: float = 0.0
    minimum_risk: float = 0.0
    average_fatigue: float = 0.0
    average_exposure: float = 0.0


class HistoryResponse(BaseModel):
    """Full history data from HistoryEngine."""
    points: List[HistoryPoint]
    statistics: HistoryStatistics


class VideoAnalysisFrame(BaseModel):
    frame_index: int
    timestamp_seconds: float
    risk_level: str
    confidence: float
    features: dict[str, float]
    feature_scores: dict[str, float] = Field(default_factory=dict)
    unavailable_features: list[str] = Field(default_factory=list)
    lower_body_confidence: float = 0.0
    # Normalized keypoints: [[x, y, z, visibility], ...] where x/y are 0-1
    keypoints: list[list[float]] = Field(default_factory=list)


class VideoAnalysisSummary(BaseModel):
    analyzed_frames: int
    source_frames: int
    duration_seconds: float
    fps: float
    frame_step: int
    risk_counts: dict[str, int]
    risk_percentages: dict[str, float]
    average_features: dict[str, float]
    # Aggregate unavailable features (union of all unavailable features across frames)
    all_unavailable_features: list[str] = Field(default_factory=list)
    # Percentage of frames with at least one unavailable feature
    frames_with_unavailable_features: float = 0.0


class VideoAnalysisResponse(BaseModel):
    filename: str
    summary: VideoAnalysisSummary
    frames: List[VideoAnalysisFrame]


# --- WebSocket Messages ---

class WsDashboardMessage(BaseModel):
    type: Literal["risk_update", "feature_update", "issue_detected", "recommendation"]
    data: dict
    timestamp: str


class WsAlertMessage(BaseModel):
    type: Literal["alert"]
    data: Alert
    timestamp: str


class WsCameraMessage(BaseModel):
    type: Literal["camera_frame", "camera_status"]
    data: dict
    timestamp: str


# --- Worker Trends ---

class WorkerTrendPoint(BaseModel):
    worker_id: str
    name: str
    department: str
    shift: str
    sessions: int
    avg_risk_score: float
    latest_risk_level: str
    trend: TrendDirection


class DepartmentTrendEntry(BaseModel):
    department: str
    worker_count: int
    avg_risk_score: float
    high_risk_count: int
    improving_count: int
    deteriorating_count: int
    trend: TrendDirection


class WorkerTrendsResponse(BaseModel):
    total_workers: int
    total_workers_with_data: int
    workers: List[WorkerTrendPoint]
    departments: List[DepartmentTrendEntry]
    temporal_curves: List["WorkerTemporalCurve"]
    station_analysis: List["StationAnalysisEntry"]


class TemporalCurvePoint(BaseModel):
    week: str
    avg_risk_score: float
    sessions: int


class WorkerTemporalCurve(BaseModel):
    worker_id: str
    name: str
    department: str
    points: List[TemporalCurvePoint]


class StationAnalysisEntry(BaseModel):
    station_id: str
    display_name: str
    sessions: int
    avg_risk_score: float
    high_risk_count: int
    worker_count: int
