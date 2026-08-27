// Centralized data contracts — single source of truth for all API responses.
// Every component must consume these interfaces.
// When the real FastAPI backend is ready, only the repository layer changes.

export type RiskLevel = 'low' | 'moderate' | 'high';
export type StatusType = 'active' | 'completed' | 'interrupted';
export type FeatureStatus = 'good' | 'low' | 'moderate' | 'high' | 'unavailable';
export type TrendDirection = 'improving' | 'stable' | 'deteriorating';
export type TabId = 'dashboard' | 'monitoring' | 'image_analysis' | 'video_review' | 'analytics' | 'workers' | 'task_recognition';

export interface SessionInfo {
  id: string;
  workerName: string;
  workerId: string;
  startTime: string;
  currentTime: string;
  duration: number;
  framesAnalyzed: number;
  cameraStatus: string;
  /** True while the backend is attempting to reopen a dropped camera (RTSP). */
  cameraReconnecting?: boolean;
}

export interface LiveStatus {
  riskLevel: RiskLevel;
  riskScore: number;
  confidence: number;
  currentTask: string;
  taskConfidence?: number;
  taskDurationSeconds: number;
  workerStatus: string;
}

export interface ErgonomicFeature {
  id: string;
  name: string;
  value: number | null;
  unit: string;
  min: number;
  max: number;
  status: FeatureStatus;
}

export interface Issue {
  id: string;
  severity: RiskLevel;
  name: string;
  timestamp: string;
  detail: string;
}

export interface CameraInfo {
  id: string;
  name: string;
  worker: string;
  fps: number;
  risk: RiskLevel;
  recording: boolean;
  uptime: string;
  status: 'streaming' | 'available';
}

export interface DetectedCamera {
  index: number;
  name: string;
  width: number;
  height: number;
  fps: number;
  backend: string;
}

export interface WorkerSummary {
  id: string;
  name: string;
  status: RiskLevel;
  task: string;
  risk: number;
}

export interface DepartmentHeatmapEntry {
  department: string;
  averageRisk: number;
  workerCount: number;
  highRiskCount: number;
  level: 'low' | 'moderate' | 'high';
}

export interface ManagerSummary {
  registeredWorkers: number;
  highRiskWorkers: number;
  todayAlerts: number;
  sessionsCompleted: number;
  mostCommonIssue: string;
  workers: WorkerSummary[];
  departmentHeatmap: DepartmentHeatmapEntry[];
  weeklyImprovement?: number | null;
  averageCompliance?: number | null;
  healthScore?: number | null;
  /** True when the database was unavailable and these are mock/fallback numbers. */
  degraded?: boolean;
}

export interface RetentionPolicy {
  session_retention_days: number;
  recording_retention_days: number;
  recordings_max_gb: number;
}

export interface RetentionStats {
  policy: RetentionPolicy;
  sessions: { dir: string; file_count: number; bytes: number };
  recordings: { dir: string; session_count: number; bytes: number };
}

export interface Recommendations {
  worker: string;
  supervisor: string;
}

export interface SessionAnalytics {
  sessionDuration: string;
  framesAnalyzed: number;
  highestRisk: string;
  mostFrequentIssue: string;
  averageNeck: number;
  averageTrunk: number;
  averageKnee: number;
}

export interface RiskDataPoint {
  time: string;
  value: number;
}

export interface TrendAnalysis {
  trend: TrendDirection;
  averageRisk: number;
  sessionsAnalyzed: number;
  improving: number;
  stable: number;
  deteriorating: number;
}

export interface DashboardResponse {
  session: SessionInfo;
  liveStatus: LiveStatus;
  ergonomicFeatures: ErgonomicFeature[];
  issues: Issue[];
  recommendations: Recommendations;
  sessionAnalytics: SessionAnalytics;
  riskHistory: RiskDataPoint[];
  trendAnalysis: TrendAnalysis;
  unavailableFeatures: string[];
}

export interface RecentSessionSummary {
  id: string;
  date: string;
  duration: string;
  highestRisk: string;
  task: string;
  status: StatusType;
  worker_id?: string | null;
}

export interface RecentAlertSummary {
  id: string;
  title: string;
  severity: string;
  state: string;
  created_at: string;
  session_id: string;
}

export interface SupervisorDashboardSummary {
  worker_count: number;
  sessions_today: number;
  open_alerts: number;
  average_risk: number | null;
  recent_sessions: RecentSessionSummary[];
  recent_alerts: RecentAlertSummary[];
}

export interface AdminDashboardSummary extends SupervisorDashboardSummary {
  total_users: number;
  total_sessions: number;
  backend_status: string;
  database_status: string;
  connected_camera_status: string;
  role_distribution: Record<string, number>;
}

export interface SessionRecord {
  id: string;
  date: string;
  duration: string;
  highestRisk: string;
  highest_risk_level?: string;
  // Dominant (plurality) risk level across the session's frames — what the
  // list/calendar display. Falls back to the peak when absent.
  risk_level?: string;
  task: string;
  status: StatusType;
  worker_id?: string | null;
  created_by_user_id?: number | null;
  camera_id?: string | null;
}

export interface PaginatedSessionsResponse {
  sessions: SessionRecord[];
  total: number;
  page: number;
  pages: number;
}

export interface ReportRecord {
  id: string;
  title: string;
  type: string;
  date: string;
  status: string;
  size: string;
}

export interface SessionAlertEntry {
  id: string;
  session_id: string;
  frame_number: number;
  created_at: string;
  severity: string;
  state: string;
  title: string;
  message: string;
  trigger_rule: string;
  confidence: number;
  requires_ack: boolean;
  expires_at: string;
}

export interface SessionDetail {
  id: string;
  status: StatusType;
  session_timestamp: string;
  session_duration_seconds: number;
  total_frames: number;
  risk_percentages: { LOW: number; MEDIUM: number; HIGH: number };
  most_frequent_issue: string | null;
  most_frequent_issue_count: number;
  highest_risk_level: string;
  risk_level?: string;
  highest_risk_timestamp: string | null;
  avg_neck_flexion: number;
  avg_trunk_flexion: number;
  avg_shoulder_symmetry: number;
  avg_knee_angle: number;
  alerts: SessionAlertEntry[];
  worker_id?: string | null;
  created_by_user_id?: number | null;
  camera_id?: string | null;
}

export interface WorkerRecord {
  worker_id: string;
  employee_id: string;
  name: string;
  department: string;
  shift: string;
}

export interface WeeklyTrend {
  week: string;
  averageRisk: number;
  sessions: number;
  incidents: number;
}

export interface FeatureTrend {
  feature: string;
  current: number;
  previous: number;
  change: number;
}

export interface RiskDistribution {
  low: number;
  moderate: number;
  high: number;
}

export interface TrendResponse {
  weeklyTrend: WeeklyTrend[];
  featureTrends: FeatureTrend[];
  riskDistribution: RiskDistribution;
}

export interface AnalyticsSummary {
  total_sessions: number;
  avg_risk_score: number;
  improving: number;
  stable: number;
  deteriorating: number;
}

export interface WeeklyRiskTrend {
  week: string;
  averageRisk: number;
  sessions: number;
}

export interface RiskDistEntry {
  name: string;
  value: number;
  color: string;
}

export interface IssueFreqEntry {
  name: string;
  count: number;
}

export interface NeckTrunkTrend {
  week: string;
  neck: number;
  trunk: number;
}

export interface AnalyticsResponse {
  summary: AnalyticsSummary;
  weekly_risk_trend: WeeklyRiskTrend[];
  risk_distribution: RiskDistEntry[];
  issue_frequency: IssueFreqEntry[];
  neck_trunk_trend: NeckTrunkTrend[];
}

export interface RiskTrendMetric {
  name: string;
  label: string;
  unit: string;
  average: number;
  trend: 'Improving' | 'Stable' | 'Deteriorating';
}

export interface RiskTrendResponse {
  total_sessions: number;
  earliest_session: string;
  latest_session: string;
  risk_distribution: {
    low_pct: number;
    medium_pct: number;
    high_pct: number;
  };
  most_common_issue: string | null;
  most_common_issue_count: number;
  most_common_highest_risk: string;
  metrics: RiskTrendMetric[];
  overall_trend: 'Improving' | 'Stable' | 'Deteriorating';
}

export interface TriggerRuleEntry {
  rule: string;
  count: number;
  pct: number;
}

export interface TopSessionAlert {
  session_timestamp: string;
  alert_count: number;
  highest_risk_level: string;
}

export interface IssueEntry {
  issue: string;
  count: number;
}

export interface SafetyReportResponse {
  total_sessions_with_alerts: number;
  total_all_sessions: number;
  earliest_session: string;
  latest_session: string;
  coverage_statement: string;
  total_alerts: number;
  severity_breakdown: Record<string, number>;
  high_severity_total: number;
  medium_severity_total: number;
  low_severity_total: number;
  trigger_rule_breakdown: TriggerRuleEntry[];
  alert_density: {
    avg_per_session: number;
    alerts_per_hour: number;
    total_monitored_hours: number;
    avg_session_duration_seconds: number;
    min_alerts_per_session: number;
    max_alerts_per_session: number;
  };
  top_sessions_by_alerts: TopSessionAlert[];
  most_frequent_issues: IssueEntry[];
}

export interface ContextSnapshot {
  session_id: string;
  frame_number: number;
  captured_at: string;
  worker_id: string;
  base_risk: number;
  context_modifier: number;
  fatigue_score: number;
  exposure_score: number;
  confidence_modifier: number;
  final_risk: number;
  risk_level: string;
  safety_state: string;
  reason: string;
  active_rules: string[];
  feature_scores: Record<string, number>;
  rula_informed_score?: number;
  rula_is_partial?: boolean;
  assessment_method?: string | null;
  assessment_score?: number | null;
  assessment_band?: string | null;
  calibrated_band?: string | null;
  calibrated_confidence?: number | null;
  calibrated_agrees?: boolean | null;
  confidence_band?: string;
  unavailable_features?: string[];
  approximate_features?: string[];
  lower_body_confidence?: number;
  // Tier 3 framing intelligence + person count
  framing?: {
    framing_state?: string;
    profile_view?: boolean;
    cropped_edges?: string[];
    occluded_joints?: string[];
    guidance?: string[];
    quality_score?: number;
    joint_uncertainty?: Record<string, number>;
    detail?: string;
  };
  person_count?: number;
  // YOLO person boxes + face-recognized worker identities (ALL persons)
  person_boxes?: { x1: number; y1: number; x2: number; y2: number; confidence: number }[];
  person_identities?: {
    box: { x1: number; y1: number; x2: number; y2: number; confidence: number };
    worker_id?: string | null;
    name?: string | null;
    employee_id?: string | null;
    confidence?: number;
    matched?: boolean;
    seen?: boolean;
    // Anti-photo-spoof liveness: 'live' | 'suspicious' (likely photo) | 'unverified'
    liveness?: string;
    blinks?: number;
    observed_seconds?: number;
  }[];
  identified_worker?: { worker_id?: string; name?: string; employee_id?: string | null; confidence?: number; matched?: boolean; liveness?: string; blinks?: number };
  // Per-person risk (station view): every detected pose, primary marked.
  person_risks?: {
    person_index: number;
    is_primary?: boolean;
    risk_level: string;
    top_issue?: string | null;
    keypoint_visibility?: number;
  }[];
}

export interface AlertData {
  id: string;
  session_id: string;
  frame_number: number;
  created_at: string;
  severity: string;
  state: string;
  title: string;
  message: string;
  trigger_rule: string;
  confidence: number;
  confidence_band: string;
  priority_score: number;
  group_id: string;
  occurrence_count: number;
  requires_ack: boolean;
  expires_at: string;
}

export interface AlertSummary {
  total_fired: number;
  active_count: number;
  critical_count: number;
  acknowledged_count: number;
  consecutive_high: number;
}

export interface AlertsResponse {
  active: AlertData[];
  history: AlertData[];
  summary: AlertSummary;
}

export interface AlertsHistoryResponse {
  alerts: AlertData[];
  total: number;
  page: number;
  pages: number;
}

export interface RecommendationItem {
  id: string;
  title: string;
  description: string;
  category: string;
  priority: string;
  target: string;
  trigger: string;
  confidence: number;
  estimated_benefit: string;
  expires_at: string;
}

export interface RecommendationBundle {
  recommendations: RecommendationItem[];
  summary: string;
  highest_priority: string;
  generated_at: string;
}

export interface RecommendationsBundleResponse {
  bundle: RecommendationBundle | null;
  total_generated: number;
}

export interface HistoryPoint {
  time: string;
  value: number;
  fatigue: number;
  exposure: number;
  risk_level: string;
}

export interface HistoryStatistics {
  frames_stored: number;
  session_duration_seconds: number;
  average_risk: number;
  maximum_risk: number;
  minimum_risk: number;
  average_fatigue: number;
  average_exposure: number;
}

export interface HistoryResponse {
  points: HistoryPoint[];
  statistics: HistoryStatistics;
}

export interface VideoAnalysisFrame {
  frame_index: number;
  timestamp_seconds: number;
  risk_level: string;
  confidence: number;
  features: Record<string, number>;
  feature_scores: Record<string, number>;
  unavailable_features: string[];
  lower_body_confidence: number;
  keypoints: number[][]; // [[x, y, z, visibility], x/y 0-1]
  // Worst risk band per body region (head/torso/left_arm/right_arm/left_leg/right_leg)
  region_risks: Record<string, string>;
  // YOLO person boxes + per-person face identities (mirrors the live overlay)
  person_boxes?: { x1: number; y1: number; x2: number; y2: number; confidence: number }[];
  person_identities?: {
    box: { x1: number; y1: number; x2: number; y2: number; confidence: number };
    worker_id?: string | null;
    name?: string | null;
    employee_id?: string | null;
    confidence?: number;
    matched?: boolean;
    seen?: boolean;
    liveness?: string;
    blinks?: number;
    observed_seconds?: number;
  }[];
}

export interface VideoAnalysisSummary {
  analyzed_frames: number;
  source_frames: number;
  duration_seconds: number;
  fps: number;
  frame_step: number;
  risk_counts: Record<string, number>;
  risk_percentages: Record<string, number>;
  average_features: Record<string, number>;
  all_unavailable_features: string[];
  frames_with_unavailable_features: number;
}

export interface VideoAnalysisResponse {
  filename: string;
  summary: VideoAnalysisSummary;
  frames: VideoAnalysisFrame[];
}

export interface VideoAnalysisJob {
  job_id: string;
  status: 'queued' | 'processing' | 'complete' | 'error';
  progress: {
    frames_processed: number;
    total_frames: number;
    percent: number;
  };
  result?: VideoAnalysisResponse | null;
  error?: string | null;
}

export interface VideoAnalysisJobStart {
  job_id: string;
  status: string;
}

export interface TimelineEntry {
  timestamp: number;
  frame_number: number;
  risk_score: number;
  risk_level: string;
  confidence: number;
  features: Record<string, number>;
  fatigue: number;
  exposure: number;
  context_score: number;
  current_task: string;
  task_duration_seconds: number;
  recommendations: { id: string; title: string; category: string; priority: string }[];
  alerts: { id: string; severity: string; title: string; message: string; trigger_rule: string }[];
  // Tier 3 framing intelligence + person count (optional for legacy entries)
  framing_state?: string;
  framing_guidance?: string[];
  framing_quality?: number;
  person_count?: number;
}

export interface RecordingSummary {
  session_id: string;
  session_timestamp: string;
  worker_id: string;
  session_duration_seconds: number;
  total_frames: number;
  risk_percentages: Record<string, number>;
  highest_risk_level: string;
  avg_neck_flexion: number;
  avg_trunk_flexion: number;
  avg_shoulder_symmetry: number;
  avg_knee_angle: number;
  alerts: {
    id: string;
    session_id: string;
    frame_number: number;
    severity: string;
    title: string;
    message: string;
    trigger_rule: string;
  }[];
  video_recording_status: string;
}

export interface RecordingListItem {
  session_id: string;
  session_timestamp: string;
  worker_id: string;
  duration_seconds: number;
  total_frames: number;
  highest_risk_level: string;
  risk_level?: string;
  risk_percentages: Record<string, number>;
  has_video: boolean;
  has_timeline: boolean;
}

export interface ModelDriftMetrics {
  samples: number;
  window_seconds: number;
  model_samples: number;
  gaussian_samples: number;
  fallback_rate: number;
  avg_confidence: number | null;
  avg_model_confidence: number | null;
  trend: 'stable' | 'rising' | 'falling';
  trend_delta_pp: number;
  healthy: boolean;
}

export interface DeploymentMetrics {
  backendStatus: string;
  backendVersion: string;
  backendUptimeSeconds: number;
  databaseEngine: string;
  databaseSizeBytes: number;
  databaseStatus: string;
  cameraCount: number;
  registeredWorkerCount: number;
  activeSessionCount: number;
  sessionActive: boolean;
  sessionFps?: number | null;
  sessionInferenceLatencyMs?: number | null;
  drift?: ModelDriftMetrics | null;
}

export interface AuditEntry {
  id: string;
  actor_id: number | null;
  actor_email: string;
  actor_role: string;
  action_type: string;
  target_type: string | null;
  target_id: string | null;
  timestamp: string;
  details: string | null;
}

export interface WorkerTrendPoint {
  worker_id: string;
  name: string;
  department: string;
  shift: string;
  sessions: number;
  avg_risk_score: number;
  latest_risk_level: string;
  trend: 'improving' | 'stable' | 'deteriorating';
}

export interface DepartmentTrendEntry {
  department: string;
  worker_count: number;
  avg_risk_score: number;
  high_risk_count: number;
  improving_count: number;
  deteriorating_count: number;
  trend: 'improving' | 'stable' | 'deteriorating';
}

export interface WorkerTrendsResponse {
  total_workers: number;
  total_workers_with_data: number;
  workers: WorkerTrendPoint[];
  departments: DepartmentTrendEntry[];
  temporal_curves: WorkerTemporalCurve[];
  station_analysis: StationAnalysisEntry[];
}

export interface TemporalCurvePoint {
  week: string;
  avg_risk_score: number;
  sessions: number;
}

export interface WorkerTemporalCurve {
  worker_id: string;
  name: string;
  department: string;
  points: TemporalCurvePoint[];
}

export interface StationAnalysisEntry {
  station_id: string;
  display_name: string;
  sessions: number;
  avg_risk_score: number;
  high_risk_count: number;
  worker_count: number;
}
