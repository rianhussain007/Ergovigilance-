import type { DashboardResponse, PaginatedSessionsResponse, ContextSnapshot, AlertsResponse, RecommendationsBundleResponse, HistoryResponse, SessionDetail, ReportRecord, RiskTrendResponse, SafetyReportResponse, WorkerTrendsResponse, AnalyticsResponse, CameraInfo, ManagerSummary, DeploymentMetrics } from '@/src/types/api';

/**
 * Repository interface — the single contract for dashboard data access.
 *
 * ApiDashboardRepository calls FastAPI REST endpoints.
 */
export interface DashboardRepository {
  getDashboard(): Promise<DashboardResponse>;
  getSessions(page?: number, limit?: number): Promise<PaginatedSessionsResponse>;
  getSessionDetail(sessionId: string): Promise<SessionDetail | null>;
  getReports(): Promise<ReportRecord[]>;
  getContextSnapshot(): Promise<ContextSnapshot | null>;
  getAlerts(): Promise<AlertsResponse>;
  getRecommendations(): Promise<RecommendationsBundleResponse>;
  getHistory(): Promise<HistoryResponse>;
  getRiskTrend(): Promise<RiskTrendResponse>;
  getSafetyReport(): Promise<SafetyReportResponse>;
  getWorkerTrends(): Promise<WorkerTrendsResponse>;
  getAnalytics(): Promise<AnalyticsResponse>;
  getCameras(): Promise<CameraInfo[]>;
  getManagerSummary(): Promise<ManagerSummary>;
  getDeployment(): Promise<DeploymentMetrics>;
}
