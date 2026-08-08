import type { DashboardRepository } from '@/src/repositories/DashboardRepository';
import { ApiDashboardRepository } from '@/src/repositories/ApiDashboardRepository';
import type { AdminDashboardSummary, DashboardResponse, SessionRecord, SupervisorDashboardSummary, ContextSnapshot, AlertsResponse, RecommendationsBundleResponse, HistoryResponse, SessionDetail, ReportRecord, RiskTrendResponse, SafetyReportResponse, AnalyticsResponse, AuditEntry, PaginatedSessionsResponse } from '@/src/types/api';
import { apiFetch } from '@/src/services/apiClient';
import { getStoredToken } from '@/src/auth/AuthContext';

/** Singleton repository — always uses the real API */
let repository: DashboardRepository | null = null;

function getRepository(): DashboardRepository {
  if (!repository) {
    repository = new ApiDashboardRepository();
  }
  return repository;
}

/** Expose each repository method as a standalone function.
 *  Components call these — they never touch the repository directly.
 */
export function getDashboardData(): Promise<DashboardResponse> {
  return getRepository().getDashboard();
}

export async function getSupervisorDashboardSummary(): Promise<SupervisorDashboardSummary> {
  const res = await apiFetch('/api/dashboard/supervisor-summary');
  if (!res.ok) throw new Error(`Supervisor dashboard summary fetch failed: ${res.status}`);
  return res.json();
}

export async function getAdminDashboardSummary(): Promise<AdminDashboardSummary> {
  const res = await apiFetch('/api/dashboard/admin-summary');
  if (!res.ok) throw new Error(`Admin dashboard summary fetch failed: ${res.status}`);
  return res.json();
}

export async function startVideoAnalysis(file: File): Promise<import('@/src/types/api').VideoAnalysisJobStart> {
  const body = new FormData();
  body.append('file', file);
  const res = await apiFetch('/api/video/analyze', {
    method: 'POST',
    body,
  });
  if (!res.ok) {
    const payload = await res.json().catch(() => ({ detail: `Video analysis failed: ${res.status}` }));
    throw new Error(payload.detail || `Video analysis failed: ${res.status}`);
  }
  return res.json();
}

export async function getVideoAnalysisJob(jobId: string): Promise<import('@/src/types/api').VideoAnalysisJob> {
  const res = await apiFetch(`/api/video/analyze/${encodeURIComponent(jobId)}`);
  if (res.status === 404) {
    throw new Error('Analysis job expired. Please re-upload the video.');
  }
  if (!res.ok) {
    const payload = await res.json().catch(() => ({ detail: `Job fetch failed: ${res.status}` }));
    throw new Error(payload.detail || `Job fetch failed: ${res.status}`);
  }
  return res.json();
}

export function getSessions(page?: number, limit?: number): Promise<PaginatedSessionsResponse> {
  return getRepository().getSessions(page, limit);
}

export function getSessionDetail(sessionId: string): Promise<SessionDetail | null> {
  return getRepository().getSessionDetail(sessionId);
}

export function getReports(): Promise<ReportRecord[]> {
  return getRepository().getReports();
}

export function getContextSnapshot(): Promise<ContextSnapshot | null> {
  return getRepository().getContextSnapshot();
}

export function getAlerts(): Promise<AlertsResponse> {
  return getRepository().getAlerts();
}

export function getRecommendations(): Promise<RecommendationsBundleResponse> {
  return getRepository().getRecommendations();
}

export function getHistory(): Promise<HistoryResponse> {
  return getRepository().getHistory();
}

export function getRiskTrend(): Promise<RiskTrendResponse> {
  return getRepository().getRiskTrend();
}

export function getSafetyReport(): Promise<SafetyReportResponse> {
  return getRepository().getSafetyReport();
}

export function getWorkerTrends(): Promise<import('@/src/types/api').WorkerTrendsResponse> {
  return getRepository().getWorkerTrends();
}

export async function getAnalytics(): Promise<AnalyticsResponse> {
  return getRepository().getAnalytics();
}

export function getCameras(): Promise<import('@/src/types/api').CameraInfo[]> {
  return getRepository().getCameras();
}

export function getManagerSummary(): Promise<import('@/src/types/api').ManagerSummary> {
  return getRepository().getManagerSummary();
}

export async function getRecordings(): Promise<{ recordings: import('@/src/types/api').RecordingListItem[] }> {
  const res = await apiFetch('/api/recordings');
  if (!res.ok) throw new Error(`Failed to fetch recordings: ${res.status}`);
  return res.json();
}

export async function getLiveTimeline(n: number = 200): Promise<{ timeline: import('@/src/types/api').TimelineEntry[] }> {
  const res = await apiFetch(`/api/session/timeline/recent?n=${n}`);
  if (res.status === 503) return { timeline: [] };
  if (!res.ok) throw new Error(`Failed to fetch live timeline: ${res.status}`);
  return res.json();
}

export async function getRecordingSummary(sessionId: string): Promise<import('@/src/types/api').RecordingSummary> {
  const res = await apiFetch(`/api/recordings/${sessionId}/summary`);
  if (res.status === 404) throw new Error('Recording not found');
  if (!res.ok) throw new Error(`Failed to fetch recording summary: ${res.status}`);
  return res.json();
}

export async function getRecordingTimeline(sessionId: string): Promise<{ timeline: import('@/src/types/api').TimelineEntry[] }> {
  const res = await apiFetch(`/api/recordings/${sessionId}/timeline`);
  if (res.status === 404) throw new Error('Recording not found');
  if (!res.ok) throw new Error(`Failed to fetch recording timeline: ${res.status}`);
  return res.json();
}

export function getRecordingVideoUrl(sessionId: string): string {
  const base = `${import.meta.env.VITE_API_URL ?? ''}/api/recordings/${sessionId}/video`;
  const token = getStoredToken();
  return token ? `${base}?token=${encodeURIComponent(token)}` : base;
}

export async function getDeployment(): Promise<import('@/src/types/api').DeploymentMetrics> {
  return getRepository().getDeployment();
}

export async function getRetentionStats(): Promise<import('@/src/types/api').RetentionStats> {
  const res = await apiFetch('/api/retention/stats');
  if (!res.ok) throw new Error(`Failed to fetch retention stats: ${res.status}`);
  return res.json();
}

export async function updateRetentionConfig(
  cfg: Partial<import('@/src/types/api').RetentionPolicy>
): Promise<{ status: string; policy: import('@/src/types/api').RetentionPolicy }> {
  const res = await apiFetch('/api/retention/config', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(cfg),
  });
  if (!res.ok) {
    const payload = await res.json().catch(() => ({ detail: `Retention update failed: ${res.status}` }));
    throw new Error(payload.detail || `Retention update failed: ${res.status}`);
  }
  return res.json();
}

export async function detectCameras(): Promise<import('@/src/types/api').DetectedCamera[]> {
  const res = await apiFetch('/api/cameras/detect');
  if (!res.ok) throw new Error(`Camera detection failed: ${res.status}`);
  return res.json();
}

export async function getAuditLog(
  actionType?: string,
  actorEmail?: string,
  limit: number = 100,
  offset: number = 0
): Promise<AuditEntry[]> {
  const params = new URLSearchParams();
  if (actionType) params.set('action_type', actionType);
  if (actorEmail) params.set('actor_email', actorEmail);
  params.set('limit', String(limit));
  params.set('offset', String(offset));
  const res = await apiFetch(`/api/audit?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to fetch audit log: ${res.status}`);
  return res.json();
}
