import { vi } from 'vitest';

/**
 * Fetch-mock fixtures for the frontend smoke tests.
 *
 * The smoke flow is: login → dashboard renders → sessions list → alert
 * center loads. Every endpoint that flow touches is served a small but
 * schema-valid JSON payload here (see ui_posture/src/types/api.ts for the
 * contracts). Unknown endpoints return 404 so a test that relies on an
 * endpoint we forgot to stub fails loudly instead of silently passing.
 */

export interface FetchMockHandler {
  (url: string, init?: RequestInit): Promise<Response>;
}

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

const EMPTY_ALERTS = {
  active: [],
  history: [],
  summary: {
    total_fired: 0,
    active_count: 0,
    critical_count: 0,
    acknowledged_count: 0,
    consecutive_high: 0,
  },
};

const DASHBOARD = {
  liveStatus: {
    riskScore: 12.4,
    riskLevel: 'low',
    currentTask: 'Assembly Work',
    workerStatus: 'active',
  },
  session: { startTime: null, cameraStatus: 'inactive' },
  sessionAnalytics: { sessionDuration: '1h 02m', averageNeck: 8.2, averageTrunk: 6.1, averageKnee: 168.4 },
  trendAnalysis: { trend: 'stable', sessionsAnalyzed: 12, improving: 2, stable: 8, deteriorating: 2, averageRisk: 18.5 },
  activeAlerts: 0,
};

const SESSIONS = {
  sessions: [
    { id: 'SESH-2026-06-30-001', date: '2026-06-30', duration: '6h 30m', highestRisk: 'Neck Flexion', task: 'Assembly Line B', status: 'completed', highest_risk_level: 'LOW', risk_level: 'LOW', worker_id: 'worker-001', camera_id: null, created_by_user_id: null, risk_percentages: {} },
  ],
  total: 1,
  page: 1,
  limit: 25,
};

const RECOMMENDATIONS = {
  bundle: {
    session_id: 'SESH-TEST',
    recommendations: [{ id: 'rec-1', title: 'Raise the work surface', description: 'Reduce trunk flexion', priority: 'high' }],
    generated_at: '2026-08-15T00:00:00Z',
  },
};

const ANALYTICS = {
  summary: { total_sessions: 1, avg_risk_score: 18.5, improving: 0, stable: 1, deteriorating: 0 },
  risk_distribution: [],
  issue_frequency: [],
  neck_trunk_trend: [],
  weekly_risk_trend: [],
};

const SNAPSHOT = {
  session_id: 'SESH-TEST',
  timestamp: '2026-08-15T00:00:00Z',
  risk_level: 'LOW',
  final_risk: 12.4,
  fatigue_score: 12.0,
  exposure_score: 8.0,
  safety_state: 'SAFE',
  movement_velocity: 0.0,
  task_label: 'Assembly Work',
  task_confidence: 88.0,
  reason: 'test',
  active_rules: [],
  feature_scores: {},
  approximate_features: [],
};

/** Default fixture map for the smoke flow. */
export const FIXTURES: Record<string, () => unknown> = {
  'POST:/api/auth/login': () => ({
    token: 'header.payload.signature',
    user: { id: 1, email: 'operator@example.local', role: 'operator' },
  }),
  'GET:/api/dashboard': () => DASHBOARD,
  'GET:/api/sessions': () => SESSIONS,
  'GET:/api/alerts': () => EMPTY_ALERTS,
  'GET:/api/recommendations': () => RECOMMENDATIONS,
  'GET:/api/analytics': () => ANALYTICS,
  'GET:/api/context/snapshot': () => SNAPSHOT,
  'GET:/api/context': () => SNAPSHOT,
  'GET:/api/session/timeline/recent': () => ({ timeline: [] }),
  'GET:/api/recordings': () => ({ recordings: [] }),
  // Bare arrays: ApiDashboardRepository.getCameras()/getReports() return
  // CameraInfo[] / ReportRecord[] directly via res.json() (see the repo).
  'GET:/api/cameras': () => [],
  'GET:/api/reports': () => [],
  'GET:/api/manager': () => ({
    worker_count: 1,
    sessions_today: 0,
    open_alerts: 0,
    average_risk: 12.0,
    degraded: false,
    data_source: 'json',
    recent_sessions: [],
    recent_alerts: [],
  }),
};

/**
 * Build a fetch mock from the fixture map. Any request not in the map
 * returns 404 so unmocked endpoints surface immediately in tests.
 */
export function createFetchMock(fixtures: Record<string, () => unknown> = FIXTURES) {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : String(input);
    const method = (init?.method ?? 'GET').toUpperCase();
    const path = url.split('?')[0];
    const key = `${method}:${path}`;
    const maker = fixtures[key];
    if (!maker) {
      return jsonResponse({ detail: `Unmocked endpoint ${key} — add a fixture` }, 404);
    }
    return jsonResponse(maker());
  });
}
