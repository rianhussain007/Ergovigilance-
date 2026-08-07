import type {
  DashboardResponse, SessionRecord,
  LiveStatus, ErgonomicFeature, Issue, Recommendations,
  SessionAnalytics, RiskDataPoint, RiskLevel,
} from '@/src/types/api';

export type AlertLevel = 'none' | 'low' | 'medium' | 'high' | 'critical';
export type NotificationTarget = 'worker' | 'supervisor' | 'both';

export interface AlertItem {
  id: string;
  time: string;
  level: AlertLevel;
  message: string;
  explanation: string;
  acknowledged: boolean;
  suppressed: boolean;
  escalated: boolean;
  notificationTarget: NotificationTarget;
}

export interface AlertEngineState {
  currentLevel: AlertLevel;
  previousLevel: AlertLevel;
  cooldownRemaining: number;
  escalationLevel: number;
  duplicateCount: number;
  totalAlertCount: number;
  lastAlertTime: number;
  lastAlertMessage: string;
  lastAlertExplanation: string;
  notificationTarget: NotificationTarget;
  history: AlertItem[];
}

export interface ContextAwareRiskData {
  currentTask: string;
  workstation: string;
  exposureDuration: string;
  fatigueLevel: number;
  contextModifier: number;
  contextConfidence: number;
  finalContextRisk: RiskLevel;
  biomechanicalRisk: RiskLevel;
  explanation: string;
}

export interface DemoToastEvent {
  type: 'success' | 'info' | 'warning' | 'error';
  title: string;
}

export interface DemoAiMessage {
  time: number;
  icon: string;
  text: string;
}

export interface DepartmentData {
  name: string;
  risk: number;
  fatigue: number;
  compliance: number;
}

export interface TopIssue {
  name: string;
  count: number;
  severity: 'high' | 'moderate' | 'low';
}

export interface WeeklyTrend {
  week: string;
  risk: number;
  compliance: number;
  alerts: number;
}

export interface ExecutiveDashboardData {
  safetyScore: number;
  workersMonitored: number;
  highRiskWorkers: number;
  mediumRiskWorkers: number;
  lowRiskWorkers: number;
  activeCameras: number;
  currentSessions: number;
  weeklyTrends: WeeklyTrend[];
  departments: DepartmentData[];
  topIssues: TopIssue[];
  executiveSummary: string;
  recommendedActions: string[];
  overallSafety: number;
  compliance: number;
  productivity: number;
  cameraAvailability: number;
  systemHealth: number;
  avgRisk: number;
  avgFatigue: number;
}

export interface SystemPerformanceData {
  systemHealth: 'healthy' | 'degraded' | 'critical';
  cpuUsage: number;
  memoryUsage: number;
  fps: number;
  cameraStatus: 'active' | 'degraded' | 'offline';
  cameraLatency: number;
  detectionLatency: number;
  processedFrames: number;
  droppedFrames: number;
  avgProcessingTime: number;
  peakMemory: number;
  uptime: number;
  gpuUtilization: number;
  aiModelConfidence: number;
  inferenceTime: number;
  lastModelUpdate: string;
  timeline: { time: string; value: number; label: string }[];
}

export interface DemoEvent {
  time: number;
  description: string;
  toast?: DemoToastEvent;
  aiMessage?: DemoAiMessage;
  delta: {
    liveStatus?: Partial<LiveStatus>;
    ergonomicFeatures?: ErgonomicFeature[];
    issues?: Issue[];
    recommendations?: Recommendations;
    sessionAnalytics?: Partial<SessionAnalytics>;
    riskHistory?: RiskDataPoint[];
    contextAwareRisk?: Partial<ContextAwareRiskData>;
    alertEngine?: Partial<AlertEngineState>;
    performance?: Partial<SystemPerformanceData>;
    executiveDashboard?: Partial<ExecutiveDashboardData>;
  };
}

export interface DemoScenario {
  id: string;
  name: string;
  description: string;
  workerName: string;
  workerId: string;
  department: string;
  shift: string;
  workstation: string;
  experience: string;
  initialDashboard: DashboardResponse;
  events: DemoEvent[];
  initialContextAwareRisk: ContextAwareRiskData;
  initialAlertEngine: AlertEngineState;
  initialSystemPerformance: SystemPerformanceData;
  initialExecutiveDashboard: ExecutiveDashboardData;
}

export interface DemoState {
  active: boolean;
  playing: boolean;
  speed: number;
  elapsed: number;
  scenarioIndex: number;
  dashboard: DashboardResponse;
  sessions: SessionRecord[];
  aiMessages: DemoAiMessage[];
  presentationMode: boolean;
  contextAwareRisk: ContextAwareRiskData;
  alertEngine: AlertEngineState;
  systemPerformance: SystemPerformanceData;
  executiveDashboard: ExecutiveDashboardData;
}

export type DemoAction =
  | { type: 'PLAY' }
  | { type: 'PAUSE' }
  | { type: 'TOGGLE_PLAY' }
  | { type: 'RESTART' }
  | { type: 'NEXT_SCENARIO' }
  | { type: 'SET_SCENARIO'; index: number }
  | { type: 'SET_SPEED'; speed: number }
  | { type: 'TICK'; delta: number }
  | { type: 'TOGGLE_DEMO' }
  | { type: 'TOGGLE_PRESENTATION' }
  | { type: 'STOP_DEMO' }
  | { type: 'ACKNOWLEDGE_ALERT'; alertId: string };
