import type { DashboardResponse, SessionRecord } from '@/src/types/api';
import type { DemoScenario, DemoAiMessage, DemoState, ContextAwareRiskData, AlertEngineState, SystemPerformanceData, ExecutiveDashboardData } from './types';
import { buildSessions } from './scenarios';

type Delta = {
  liveStatus?: Partial<DashboardResponse['liveStatus']>;
  ergonomicFeatures?: DashboardResponse['ergonomicFeatures'];
  issues?: DashboardResponse['issues'];
  recommendations?: DashboardResponse['recommendations'];
  sessionAnalytics?: Partial<DashboardResponse['sessionAnalytics']>;
  riskHistory?: DashboardResponse['riskHistory'];
  contextAwareRisk?: Partial<ContextAwareRiskData>;
  alertEngine?: Partial<AlertEngineState>;
  performance?: Partial<SystemPerformanceData>;
  executiveDashboard?: Partial<ExecutiveDashboardData>;
};

function deepClone<T>(o: T): T {
  return JSON.parse(JSON.stringify(o));
}

function applyDelta(base: DashboardResponse, event: { delta: Delta }): DashboardResponse {
  const result = deepClone(base);
  const d = event.delta;
  if (d.liveStatus) Object.assign(result.liveStatus, d.liveStatus);
  if (d.ergonomicFeatures) result.ergonomicFeatures = deepClone(d.ergonomicFeatures);
  if (d.issues) result.issues = deepClone(d.issues);
  if (d.recommendations) result.recommendations = deepClone(d.recommendations);
  if (d.sessionAnalytics) Object.assign(result.sessionAnalytics, d.sessionAnalytics);
  if (d.riskHistory) result.riskHistory = deepClone(d.riskHistory);
  return result;
}

function applyAlertDelta(base: AlertEngineState, delta: Partial<AlertEngineState>): AlertEngineState {
  const result = deepClone(base);
  Object.assign(result, delta);
  if (delta.history) result.history = deepClone(delta.history);
  return result;
}

export function computeDashboard(scenario: DemoScenario, elapsed: number): { dashboard: DashboardResponse; aiMessages: DemoAiMessage[]; contextAwareRisk: ContextAwareRiskData; alertEngine: AlertEngineState; systemPerformance: SystemPerformanceData; executiveDashboard: ExecutiveDashboardData } {
  let dashboard = deepClone(scenario.initialDashboard);
  let contextAwareRisk = deepClone(scenario.initialContextAwareRisk);
  let alertEngine = deepClone(scenario.initialAlertEngine);
  let systemPerformance = deepClone(scenario.initialSystemPerformance);
  let executiveDashboard = deepClone(scenario.initialExecutiveDashboard);
  const aiMessages: DemoAiMessage[] = [];

  const applied = scenario.events.filter((e) => e.time <= elapsed);
  for (const event of applied) {
    dashboard = applyDelta(dashboard, { delta: event.delta });
    if (event.delta.contextAwareRisk) {
      Object.assign(contextAwareRisk, event.delta.contextAwareRisk);
    }
    if (event.delta.alertEngine) {
      alertEngine = applyAlertDelta(alertEngine, event.delta.alertEngine);
    }
    if (event.delta.performance) {
      Object.assign(systemPerformance, event.delta.performance);
      if (event.delta.performance.timeline) {
        systemPerformance.timeline = deepClone(event.delta.performance.timeline);
      }
    }
    if (event.delta.executiveDashboard) {
      Object.assign(executiveDashboard, event.delta.executiveDashboard);
      if (event.delta.executiveDashboard.departments) {
        executiveDashboard.departments = deepClone(event.delta.executiveDashboard.departments);
      }
      if (event.delta.executiveDashboard.topIssues) {
        executiveDashboard.topIssues = deepClone(event.delta.executiveDashboard.topIssues);
      }
      if (event.delta.executiveDashboard.weeklyTrends) {
        executiveDashboard.weeklyTrends = deepClone(event.delta.executiveDashboard.weeklyTrends);
      }
    }
    if (event.aiMessage) {
      aiMessages.push(event.aiMessage);
    }
  }

  const sec = Math.floor(elapsed);
  const h = String(Math.floor(sec / 3600)).padStart(2, '0');
  const m = String(Math.floor((sec % 3600) / 60)).padStart(2, '0');
  const s = String(sec % 60).padStart(2, '0');

  // Update session times dynamically
  const baseTime = new Date(scenario.initialDashboard.session.startTime);
  baseTime.setSeconds(baseTime.getSeconds() + sec);
  dashboard.session.currentTime = baseTime.toISOString();
  dashboard.session.duration = sec;
  dashboard.session.framesAnalyzed = Math.round(sec * 0.8);

  // Keep riskHistory updated
  const lastRiskTime = dashboard.riskHistory.length > 0 ? dashboard.riskHistory[dashboard.riskHistory.length - 1].time : '00:00';
  const newTime = `${h}:${m}`;
  if (newTime !== lastRiskTime) {
    dashboard.riskHistory = [
      ...dashboard.riskHistory,
      { time: newTime, value: Math.round(dashboard.liveStatus.riskScore) },
    ];
  }

  // Update session analytics
  dashboard.sessionAnalytics.sessionDuration = `${h}h ${m}m`;
  dashboard.sessionAnalytics.framesAnalyzed = dashboard.session.framesAnalyzed;

  return { dashboard, aiMessages, contextAwareRisk, alertEngine, systemPerformance, executiveDashboard };
}

export function computeSessions(scenario: DemoScenario, elapsed: number): SessionRecord[] {
  const sessions = buildSessions(scenario.workerId, scenario.initialDashboard.liveStatus.currentTask);
  const minutes = Math.floor(elapsed / 60);
  sessions[0] = {
    ...sessions[0],
    duration: `${Math.floor(minutes / 60)}h ${minutes % 60}m`,
    task: scenario.initialDashboard.liveStatus.currentTask,
    status: minutes > 30 ? 'active' : 'active',
  };
  return sessions;
}

export function computeAll(scenario: DemoScenario, elapsed: number): Pick<DemoState, 'dashboard' | 'sessions' | 'aiMessages' | 'contextAwareRisk' | 'alertEngine' | 'systemPerformance' | 'executiveDashboard'> {
  const { dashboard, aiMessages, contextAwareRisk, alertEngine, systemPerformance, executiveDashboard } = computeDashboard(scenario, elapsed);
  const sessions = computeSessions(scenario, elapsed);
  return { dashboard, sessions, aiMessages, contextAwareRisk, alertEngine, systemPerformance, executiveDashboard };
}
