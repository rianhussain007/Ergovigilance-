import type { DashboardRepository } from './DashboardRepository';
import type { DashboardResponse, PaginatedSessionsResponse, ContextSnapshot, AlertsResponse, RecommendationsBundleResponse, HistoryResponse, SessionDetail, ReportRecord, RiskTrendResponse, SafetyReportResponse, WorkerTrendsResponse, AnalyticsResponse, CameraInfo, ManagerSummary, DeploymentMetrics } from '@/src/types/api';
import { apiFetch, friendlyHttpError } from '@/src/services/apiClient';

const API_BASE = '/api';

export class ApiDashboardRepository implements DashboardRepository {
  async getDashboard(): Promise<DashboardResponse> {
    const res = await apiFetch(`${API_BASE}/dashboard`);
    if (!res.ok) throw new Error(`Dashboard fetch failed: ${res.status}`);
    return res.json();
  }

  async getSessions(page = 1, limit = 25): Promise<PaginatedSessionsResponse> {
    const res = await apiFetch(`${API_BASE}/sessions?page=${page}&limit=${limit}`);
    if (!res.ok) throw new Error(friendlyHttpError(res.status, 'Sessions'));
    return res.json();
  }

  async getSessionDetail(sessionId: string): Promise<SessionDetail | null> {
    const res = await apiFetch(`${API_BASE}/sessions/${encodeURIComponent(sessionId)}`);
    if (res.status === 404) return null;
    if (!res.ok) throw new Error(`Session detail fetch failed: ${res.status}`);
    return res.json();
  }

  async getReports(): Promise<ReportRecord[]> {
    const res = await apiFetch(`${API_BASE}/reports`);
    if (!res.ok) throw new Error(friendlyHttpError(res.status, 'Reports'));
    return res.json();
  }

  async getContextSnapshot(): Promise<ContextSnapshot | null> {
    const res = await apiFetch(`${API_BASE}/context/snapshot`);
    if (!res.ok) throw new Error(`Context snapshot fetch failed: ${res.status}`);
    const data = await res.json();
    return data ?? null;
  }

  async getAlerts(): Promise<AlertsResponse> {
    const res = await apiFetch(`${API_BASE}/alerts`);
    if (!res.ok) throw new Error(`Alerts fetch failed: ${res.status}`);
    return res.json();
  }

  async getRecommendations(): Promise<RecommendationsBundleResponse> {
    const res = await apiFetch(`${API_BASE}/recommendations`);
    if (!res.ok) throw new Error(`Recommendations fetch failed: ${res.status}`);
    return res.json();
  }

  async getHistory(): Promise<HistoryResponse> {
    const res = await apiFetch(`${API_BASE}/history`);
    if (!res.ok) throw new Error(`History fetch failed: ${res.status}`);
    return res.json();
  }

  async getRiskTrend(): Promise<RiskTrendResponse> {
    const res = await apiFetch(`${API_BASE}/reports/risk-trend`);
    if (!res.ok) throw new Error(`Risk trend fetch failed: ${res.status}`);
    return res.json();
  }

  async getSafetyReport(): Promise<SafetyReportResponse> {
    const res = await apiFetch(`${API_BASE}/reports/safety-report`);
    if (!res.ok) throw new Error(`Safety report fetch failed: ${res.status}`);
    return res.json();
  }

  async getWorkerTrends(): Promise<WorkerTrendsResponse> {
    const res = await apiFetch(`${API_BASE}/reports/worker-trends`);
    if (!res.ok) throw new Error(`Worker trends fetch failed: ${res.status}`);
    return res.json();
  }

  async getCameras(): Promise<CameraInfo[]> {
    const res = await apiFetch(`${API_BASE}/cameras`);
    if (!res.ok) throw new Error(`Cameras fetch failed: ${res.status}`);
    return res.json();
  }

  async getManagerSummary(): Promise<ManagerSummary> {
    const res = await apiFetch(`${API_BASE}/manager`);
    if (!res.ok) throw new Error(`Manager summary fetch failed: ${res.status}`);
    return res.json();
  }

  async getAnalytics(): Promise<AnalyticsResponse> {
    const res = await apiFetch(`${API_BASE}/analytics`);
    if (!res.ok) throw new Error(`Analytics fetch failed: ${res.status}`);
    return res.json();
  }

  async getDeployment(): Promise<DeploymentMetrics> {
    const res = await apiFetch(`${API_BASE}/deployment`);
    if (!res.ok) throw new Error(`Deployment metrics fetch failed: ${res.status}`);
    return res.json();
  }
}
