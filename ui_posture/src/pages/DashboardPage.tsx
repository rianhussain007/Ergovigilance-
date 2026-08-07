import { useState, useEffect, useMemo } from 'react';
import type { ElementType, ReactNode } from 'react';
import { useNavigate, useOutletContext } from 'react-router';
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Brain,
  Camera,
  CheckCircle,
  Clock3,
  Cpu,
  Database,
  Gauge,
  HeartPulse,
  History,
  Lightbulb,
  Server,
  ShieldAlert,
  Sparkles,
  TrendingUp,
  TrendingDown,
  Minus,
  UserCog,
  Users,
  Zap,
} from 'lucide-react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, PieChart, Pie, Cell, AreaChart, Area } from 'recharts';
import { useDashboardWithDemo } from '@/src/hooks/useDashboardWithDemo';
import { useContextSnapshot } from '@/src/hooks/useContextSnapshot';
import { apiFetch } from '@/src/services/apiClient';
import { useAlerts } from '@/src/hooks/useAlerts';
import { useRecommendations } from '@/src/hooks/useRecommendations';
import { useAuth } from '@/src/auth/AuthContext';
import {
  getAdminDashboardSummary,
  getAnalytics,
  getSessionDetail,
  getSupervisorDashboardSummary,
} from '@/src/services/dashboardService';
import { EmptyState, ErrorCard, LoadingCard, SectionHeader } from '@/src/components/common';
import type {
  AdminDashboardSummary,
  AnalyticsResponse,
  ContextSnapshot,
  RecentAlertSummary,
  RecentSessionSummary,
  SessionDetail,
  SupervisorDashboardSummary,
} from '@/src/types/api';

const elevatedRoles = new Set(['supervisor', 'safety_mgr', 'admin']);

export default function DashboardPage() {
  const { user } = useAuth();
  const { dashboard, sessions, loading, error, refetch } = useDashboardWithDemo();
  const { snapshot } = useContextSnapshot();
  const { alerts } = useAlerts();
  const { data: recommendations } = useRecommendations();
  const navigate = useNavigate();
  const { setNotifOpen } = useOutletContext<{ setNotifOpen: (v: boolean) => void }>();
  const [latestDetail, setLatestDetail] = useState<SessionDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [supervisorSummary, setSupervisorSummary] = useState<SupervisorDashboardSummary | null>(null);
  const [adminSummary, setAdminSummary] = useState<AdminDashboardSummary | null>(null);
  const [summaryError, setSummaryError] = useState<string | null>(null);
  const [analytics, setAnalytics] = useState<AnalyticsResponse | null>(null);

  const latestCompleted = useMemo(() => sessions.find((s) => s.status === 'completed') ?? null, [sessions]);
  const latestCompletedId = latestCompleted?.id ?? null;
  const isElevated = !!user && elevatedRoles.has(user.role);
  const isAdmin = user?.role === 'admin';

  useEffect(() => {
    let cancelled = false;
    if (!latestCompletedId) {
      setLatestDetail(null);
      return;
    }
    setDetailLoading(true);
    getSessionDetail(latestCompletedId)
      .then((detail) => {
        if (!cancelled) setLatestDetail(detail);
      })
      .catch(() => {
        if (!cancelled) setLatestDetail(null);
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false);
      });
    return () => { cancelled = true; };
  }, [latestCompletedId]);

  useEffect(() => {
    let cancelled = false;
    setSummaryError(null);
    setSupervisorSummary(null);
    setAdminSummary(null);

    if (!user || !isElevated) return;

    const loadSummary = async () => {
      try {
        if (isAdmin) {
          const summary = await getAdminDashboardSummary();
          if (!cancelled) {
            setAdminSummary(summary);
            setSupervisorSummary(summary);
          }
          return;
        }
        const summary = await getSupervisorDashboardSummary();
        if (!cancelled) setSupervisorSummary(summary);
      } catch (err) {
        if (!cancelled) setSummaryError(err instanceof Error ? err.message : 'Dashboard summary unavailable');
      }
    };

    loadSummary();
    const id = window.setInterval(loadSummary, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [isAdmin, isElevated, user]);

  useEffect(() => {
    let cancelled = false;
    getAnalytics()
      .then((data) => { if (!cancelled) setAnalytics(data); })
      .catch(() => { if (!cancelled) setAnalytics(null); });
    return () => { cancelled = true; };
  }, []);

  if (error) {
    return <div className="flex items-center justify-center h-full p-lg"><ErrorCard message={error} onRetry={refetch} /></div>;
  }

  const riskScore = dashboard?.liveStatus.riskScore;
  const riskLevel = dashboard?.liveStatus.riskLevel ?? 'low';
  const session = dashboard?.session;
  const currentAverages = dashboard?.sessionAnalytics;
  const latestRecommendations = recommendations.bundle?.recommendations ?? [];
  const currentSessionActive = !!session?.startTime;
  const operatorRecentSessions = sessions.slice(0, 5).map((item) => ({
    id: item.id,
    date: item.date,
    duration: item.duration,
    highestRisk: item.highestRisk,
    task: item.task,
    status: item.status,
    worker_id: item.worker_id,
  }));

  const featureAverages = latestDetail ? [
    { label: 'Neck', value: latestDetail.avg_neck_flexion, unit: 'deg' },
    { label: 'Trunk', value: latestDetail.avg_trunk_flexion, unit: 'deg' },
    { label: 'Shoulder', value: latestDetail.avg_shoulder_symmetry, unit: '%' },
    { label: 'Knee', value: latestDetail.avg_knee_angle, unit: 'deg' },
  ] : currentAverages ? [
    { label: 'Neck', value: currentAverages.averageNeck, unit: 'deg' },
    { label: 'Trunk', value: currentAverages.averageTrunk, unit: 'deg' },
    { label: 'Knee', value: currentAverages.averageKnee, unit: 'deg' },
  ] : [];

  return (
    <div className="p-lg space-y-lg pb-32">
      <div className="flex flex-wrap items-end justify-between gap-md">
        <div>
          <h1 className="text-display-lg font-bold text-on-surface">Dashboard</h1>
          <p className="text-body-sm text-on-surface-variant mt-xs">
            {user?.role === 'operator' && 'What is happening to me right now.'}
            {(user?.role === 'supervisor' || user?.role === 'safety_mgr') && 'What is happening across visible workers right now.'}
            {user?.role === 'admin' && 'Operational, user, database, and monitoring status from live sources.'}
          </p>
        </div>
        <div className="rounded-lg border border-outline-variant bg-surface-container px-md py-sm text-right">
          <p className="font-label-caps text-[10px] text-on-surface-variant">Signed In Role</p>
          <p className="font-label-mono text-body-sm text-primary">{user?.role ?? 'unknown'}</p>
        </div>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-lg">
          <LoadingCard height="h-48" />
          <LoadingCard height="h-48" />
          <LoadingCard height="h-48" />
        </div>
      ) : !dashboard ? (
        <EmptyState title="No dashboard data" message="Start a monitoring session to populate the summary." />
      ) : (
        <>
          {user?.role === 'operator' ? (
            <OperatorDashboard
              alertCount={alerts.summary.total_fired}
              activeAlertCount={alerts.summary.active_count}
              currentSessionActive={currentSessionActive}
              featureAverages={featureAverages}
              latestRecommendations={latestRecommendations}
              detailLoading={detailLoading}
              operatorRecentSessions={operatorRecentSessions}
              riskLevel={riskLevel}
              riskScore={riskScore}
              sessionDuration={currentAverages?.sessionDuration}
              sessionId={currentSessionActive ? session?.id : null}
              snapshot={snapshot}
              task={dashboard.liveStatus.currentTask}
              taskConfidence={dashboard.liveStatus.confidence}
              workerStatus={dashboard.liveStatus.workerStatus}
              ownAlerts={alerts.history.slice(0, 5)}
              trendAnalysis={dashboard.trendAnalysis}
              analytics={analytics}
            />
          ) : (
            <ElevatedDashboard
              adminSummary={adminSummary}
              isAdmin={isAdmin}
              summary={supervisorSummary}
              summaryError={summaryError}
              trendAnalysis={dashboard.trendAnalysis}
              analytics={analytics}
              snapshot={snapshot}
              setNotifOpen={setNotifOpen}
            />
          )}
        </>
      )}
    </div>
  );
}

function OperatorDashboard({
  alertCount,
  activeAlertCount,
  currentSessionActive,
  detailLoading,
  featureAverages,
  latestRecommendations,
  operatorRecentSessions,
  ownAlerts,
  riskLevel,
  riskScore,
  sessionDuration,
  sessionId,
  snapshot,
  task,
  taskConfidence,
  workerStatus,
  trendAnalysis,
  analytics,
}: {
  alertCount: number;
  activeAlertCount: number;
  currentSessionActive: boolean;
  detailLoading: boolean;
  featureAverages: { label: string; value: number; unit: string }[];
  latestRecommendations: { id: string; title: string; description: string; priority: string }[];
  operatorRecentSessions: RecentSessionSummary[];
  ownAlerts: { id: string; title: string; severity: string; frame_number: number }[];
  riskLevel: string;
  riskScore?: number;
  sessionDuration?: string;
  sessionId: string | null | undefined;
  snapshot: { fatigue_score: number; exposure_score: number; final_risk: number } | null;
  task: string;
  taskConfidence?: number;
  workerStatus: string;
  trendAnalysis: { trend: string; sessionsAnalyzed: number; improving: number; stable: number; deteriorating: number; averageRisk: number };
  analytics: AnalyticsResponse | null;
}) {
  const navigate = useNavigate();
  return (
    <>
      <section className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-md">
        <MetricCard icon={Gauge} label="My Current Risk" value={formatMaybeNumber(riskScore, 0)} detail={riskLevel.toUpperCase()} tone={riskLevel === 'high' ? 'danger' : riskLevel === 'moderate' ? 'warning' : 'good'} onClick={() => navigate('/monitoring')} isUrgent={true} />
        <MetricCard icon={Activity} label="My Current Task" value={task || 'Unavailable'} detail={workerStatus || 'No worker status'} onClick={() => navigate('/monitoring')} />
        <MetricCard icon={Clock3} label="Today's Monitoring" value={currentSessionActive ? (sessionDuration ?? 'Calculating') : 'No active session'} detail={sessionId ?? 'Start monitoring to begin'} onClick={() => navigate('/sessions')} />
        <MetricCard icon={ShieldAlert} label="My Alerts" value={String(alertCount)} detail={`${activeAlertCount} active`} tone={activeAlertCount > 0 ? 'warning' : 'good'} onClick={() => navigate('/monitoring')} isUrgent={true} />
      </section>

      <section className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_380px] gap-lg">
        <div className="bg-surface-container border border-outline-variant rounded-lg p-lg space-y-lg">
          <SectionHeader title="My Health Context" />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-md">
            <ContextTile label="Fatigue" value={snapshot ? `${snapshot.fatigue_score.toFixed(1)}%` : 'Waiting for live context'} />
            <ContextTile label="Exposure" value={snapshot ? `${snapshot.exposure_score.toFixed(1)}%` : 'Waiting for live context'} />
            <ContextTile label="Context Risk" value={snapshot ? snapshot.final_risk.toFixed(1) : 'Waiting for live context'} />
          </div>
          <div>
            <p className="font-label-caps text-[10px] text-on-surface-variant mb-sm">My Feature Averages</p>
            {detailLoading ? (
              <LoadingCard height="h-32" />
            ) : featureAverages.length === 0 ? (
              <EmptyState title="No feature averages yet" message="Saved or active session averages will appear here." />
            ) : (
              <div className="space-y-sm">
                {featureAverages.map((item) => (
                  <div key={item.label}>
                    <FeatureAverageBar label={item.label} value={item.value} unit={item.unit} />
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <aside className="space-y-lg">
          <FeedCard title="My Alerts" icon={AlertTriangle}>
            {ownAlerts.length === 0 ? (
              <p className="text-body-sm text-on-surface-variant">No alerts visible for your current scope.</p>
            ) : ownAlerts.map((alert) => (
              <div key={alert.id}>
                <FeedRow title={alert.title} meta={`${alert.severity} - frame ${alert.frame_number}`} />
              </div>
            ))}
          </FeedCard>

          <FeedCard title="My Recommendations" icon={Lightbulb}>
            {latestRecommendations.length === 0 ? (
              <p className="text-body-sm text-on-surface-variant">No current recommendations from the Recommendation Engine.</p>
            ) : latestRecommendations.slice(0, 4).map((rec) => (
              <div key={rec.id}>
                <FeedRow title={rec.title} meta={`${rec.priority} - ${rec.description}`} />
              </div>
            ))}
          </FeedCard>
        </aside>
      </section>

      <section className="grid grid-cols-1 xl:grid-cols-3 gap-lg">
        <FeedCard title="My Recent Sessions" icon={History}>
          {operatorRecentSessions.length === 0 ? (
            <p className="text-body-sm text-on-surface-variant">No completed sessions are visible for your account yet.</p>
          ) : operatorRecentSessions.map((session) => (
            <div key={session.id}>
              <FeedRow title={session.id} meta={`${session.status} - ${session.duration} - ${session.highestRisk}`} />
            </div>
          ))}
        </FeedCard>
        <TrendSummaryCard trendAnalysis={trendAnalysis} analytics={analytics} />
        <TopIssuesCard analytics={analytics} />
      </section>

      <section className="grid grid-cols-1 xl:grid-cols-3 gap-lg">
        <TaskRecognitionCard task={task} taskDuration={sessionDuration} taskConfidence={taskConfidence} snapshot={snapshot} />
        <AIInsightsCard snapshot={snapshot} />
        <ModelPerformanceCard />
      </section>
    </>
  );
}

function ElevatedDashboard({
  adminSummary,
  isAdmin,
  summary,
  summaryError,
  trendAnalysis,
  analytics,
  snapshot,
  setNotifOpen,
}: {
  adminSummary: AdminDashboardSummary | null;
  isAdmin: boolean;
  summary: SupervisorDashboardSummary | null;
  summaryError: string | null;
  trendAnalysis: { trend: string; sessionsAnalyzed: number; improving: number; stable: number; deteriorating: number; averageRisk: number };
  analytics: AnalyticsResponse | null;
  snapshot: { fatigue_score: number; exposure_score: number; final_risk: number; rula_informed_score?: number; feature_scores?: Record<string, number> } | null;
  setNotifOpen: (v: boolean) => void;
}) {
  const navigate = useNavigate();
  if (summaryError) {
    return <ErrorCard message={summaryError} />;
  }

  if (!summary) {
    return (
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-lg">
        <LoadingCard height="h-48" />
        <LoadingCard height="h-48" />
        <LoadingCard height="h-48" />
      </div>
    );
  }

  return (
    <>
      <section className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-md">
        <MetricCard icon={Users} label="Visible Workers" value={String(summary.worker_count)} detail="COUNT(workers) from SQLite" onClick={() => navigate('/workers')} />
        <MetricCard icon={Clock3} label="Sessions Today" value={String(summary.sessions_today)} detail="Visible session rows dated today" onClick={() => navigate('/sessions')} />
        <MetricCard icon={ShieldAlert} label="Open Alerts" value={String(summary.open_alerts)} detail="Active AlertEngine alerts" tone={summary.open_alerts > 0 ? 'warning' : 'good'} onClick={() => setNotifOpen(true)} isUrgent={true} />
        <MetricCard icon={Gauge} label="Average Risk" value={summary.average_risk === null ? 'Not enough data' : summary.average_risk.toFixed(1)} detail="Computed from visible sessions" onClick={() => navigate('/reports')} isUrgent={true} tone={(summary.average_risk && summary.average_risk >= 60) ? 'danger' : (summary.average_risk && summary.average_risk >= 30) ? 'warning' : 'good'} />
      </section>

      {isAdmin && adminSummary && (
        <section className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-md">
          <MetricCard icon={UserCog} label="Total Users" value={String(adminSummary.total_users)} detail="COUNT(users) from SQLite" onClick={() => navigate('/users')} />
          <MetricCard icon={BarChart3} label="Total Sessions" value={String(adminSummary.total_sessions)} detail="Saved session files plus active session" onClick={() => navigate('/sessions')} />
          <MetricCard icon={Server} label="Backend Health" value={adminSummary.backend_status} detail={`Database ${adminSummary.database_status}`} tone={adminSummary.backend_status === 'healthy' && adminSummary.database_status === 'healthy' ? 'good' : 'warning'} onClick={() => navigate('/settings')} />
          <MetricCard icon={Camera} label="Camera Status" value={adminSummary.connected_camera_status || 'unknown'} detail="LiveMonitoringService state" onClick={() => navigate('/monitoring')} />
        </section>
      )}

      <section className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_380px] gap-lg">
        <div className="bg-surface-container border border-outline-variant rounded-lg p-lg">
          <SectionHeader title="Visible Worker Activity" />
          <div className="mt-lg grid grid-cols-1 md:grid-cols-2 gap-md">
            <FeedCard title="Recent Sessions" icon={History}>
              {summary.recent_sessions.length === 0 ? (
                <p className="text-body-sm text-on-surface-variant">No sessions are visible for this role yet.</p>
              ) : summary.recent_sessions.map((session) => (
                <div key={session.id}>
                  <FeedRow title={session.id} meta={`${session.status} - ${session.duration} - ${session.worker_id ?? 'unassigned worker'}`} />
                </div>
              ))}
            </FeedCard>
            <FeedCard title="Recent Alerts" icon={AlertTriangle}>
              {summary.recent_alerts.length === 0 ? (
                <p className="text-body-sm text-on-surface-variant">No alert history is currently available.</p>
              ) : summary.recent_alerts.map((alert) => (
                <div key={alert.id}>
                  <FeedRow title={alert.title} meta={`${alert.severity} - ${alert.state} - ${alert.session_id}`} />
                </div>
              ))}
            </FeedCard>
          </div>
        </div>

        <aside className="space-y-lg">
          {isAdmin && adminSummary ? (
            <div className="bg-surface-container border border-outline-variant rounded-lg p-lg">
              <div className="flex items-center gap-sm mb-md">
                <Database className="w-4 h-4 text-primary" />
                <SectionHeader title="Role Distribution" />
              </div>
              <div className="space-y-sm">
                {Object.entries(adminSummary.role_distribution).map(([role, count]) => (
                  <div key={role} className="flex items-center justify-between rounded-lg bg-surface-container-low border border-outline-variant/60 px-md py-sm">
                    <span className="text-body-sm text-on-surface-variant">{role}</span>
                    <span className="font-label-mono text-on-surface">{count}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="bg-surface-container border border-outline-variant rounded-lg p-lg">
              <div className="flex items-center gap-sm mb-md">
                <HeartPulse className="w-4 h-4 text-primary" />
                <SectionHeader title="Safety Scope" />
              </div>
              <p className="text-body-sm text-on-surface-variant">
                Aggregates are computed across workers and sessions visible to this role.
              </p>
            </div>
          )}

          <RiskDistributionCard analytics={analytics} />
        </aside>
      </section>

      <section className="grid grid-cols-1 xl:grid-cols-3 gap-lg">
        <TrendSummaryCard trendAnalysis={trendAnalysis} analytics={analytics} />
        <NeckTrunkTrendCard analytics={analytics} />
        <SessionSummaryCard analytics={analytics} />
      </section>

      <section className="grid grid-cols-1 xl:grid-cols-3 gap-lg">
        <TaskRecognitionCard task="Unknown" taskDuration="—" snapshot={snapshot} />
        <AIInsightsCard snapshot={snapshot} />
        <ModelPerformanceCard />
      </section>
    </>
  );
}

function MetricCard({ icon: Icon, label, value, detail, tone = 'neutral', onClick, isUrgent = false }: { icon: ElementType; label: string; value: string; detail: string; tone?: 'neutral' | 'good' | 'warning' | 'danger'; onClick?: () => void; isUrgent?: boolean }) {
  // Check if value is non-zero (for urgent metrics)
  const numericValue = parseFloat(value);
  const hasNonZeroUrgent = isUrgent && !isNaN(numericValue) && numericValue > 0;
  
  const iconClass = tone === 'danger' ? 'text-red-400' : tone === 'warning' ? 'text-orange-400' : tone === 'good' ? 'text-green-400' : 'text-primary';
  
  // Left border
  const leftBorderClass = tone === 'danger' ? 'border-l-red-500' : tone === 'warning' ? 'border-l-orange-500' : tone === 'good' ? 'border-l-green-500' : 'border-l-outline-variant';
  
  // Background
  const bgClass = hasNonZeroUrgent 
    ? (tone === 'danger' ? 'bg-red-500/10' : tone === 'warning' ? 'bg-orange-500/10' : 'bg-green-500/10')
    : 'bg-surface-container';
  
  // Other borders
  const otherBorderClass = tone === 'danger' ? 'border-t border-r border-b border-red-500/30' : tone === 'warning' ? 'border-t border-r border-b border-orange-500/30' : tone === 'good' ? 'border-t border-r border-b border-green-500/30' : 'border-t border-r border-b border-outline-variant';
  
  // Size for urgent metrics
  const sizeClass = isUrgent ? 'min-h-[140px]' : 'min-h-[132px]';
  const textSizeClass = isUrgent ? 'text-display-lg' : 'text-display-md';
  
  const Tag = onClick ? 'button' : 'div';
  return (
    <Tag onClick={onClick} className={`${bgClass} border-l-4 ${leftBorderClass} ${otherBorderClass} rounded-lg p-md ${sizeClass} text-left w-full ${onClick ? 'cursor-pointer hover:shadow-sm transition-all duration-150' : ''}`}>
      <div className="flex items-center justify-between mb-sm gap-sm">
        <span className="font-label-caps text-[10px] text-on-surface-variant">{label}</span>
        <Icon className={`w-5 h-5 ${iconClass} shrink-0`} />
      </div>
      <p className={`${textSizeClass} font-bold text-on-surface break-words`}>{value}</p>
      <p className="text-[11px] text-on-surface-variant mt-xs">{detail}</p>
    </Tag>
  );
}

function ContextTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-outline-variant bg-surface-container-low p-md min-h-[96px]">
      <p className="font-label-caps text-[10px] text-on-surface-variant">{label}</p>
      <p className="mt-sm text-display-sm font-bold text-on-surface break-words">{value}</p>
    </div>
  );
}

function FeatureAverageBar({ label, value, unit }: { label: string; value: number; unit: string }) {
  const width = Math.max(4, Math.min(100, unit === '%' ? value : value / 1.8));
  return (
    <div>
      <div className="flex justify-between text-body-sm mb-xs gap-md">
        <span className="text-on-surface-variant">{label}</span>
        <span className="font-label-mono text-on-surface">{value.toFixed(1)} {unit}</span>
      </div>
      <div className="h-2 rounded-full bg-surface-container-highest overflow-hidden">
        <div className="h-full rounded-full bg-primary" style={{ width: `${width}%` }} />
      </div>
    </div>
  );
}

function FeedCard({ children, icon: Icon, title }: { children: ReactNode; icon: ElementType; title: string }) {
  return (
    <div className="bg-surface-container border border-outline-variant rounded-lg p-lg min-h-[220px]">
      <div className="flex items-center gap-sm mb-md">
        <Icon className="w-4 h-4 text-primary" />
        <SectionHeader title={title} />
      </div>
      <div className="space-y-sm">{children}</div>
    </div>
  );
}

function FeedRow({ title, meta }: { title: string; meta: string }) {
  return (
    <div className="rounded-lg border border-outline-variant/60 bg-surface-container-low p-sm">
      <p className="text-body-sm font-medium text-on-surface">{title}</p>
      <p className="text-[11px] text-on-surface-variant mt-0.5">{meta}</p>
    </div>
  );
}

function ComingSoon({ title, description }: { title: string; description: string }) {
  return (
    <div className="bg-surface-container border border-dashed border-outline-variant rounded-lg p-lg min-h-[180px]">
      <div className="flex items-start gap-md">
        <Sparkles className="w-5 h-5 text-on-surface-variant shrink-0 mt-0.5" />
        <div>
          <p className="font-label-caps text-[10px] text-on-surface-variant">{title} - Coming Soon</p>
          <p className="text-body-sm text-on-surface-variant mt-sm">{description}</p>
        </div>
      </div>
    </div>
  );
}

function TrendSummaryCard({ trendAnalysis, analytics }: { trendAnalysis: { trend: string; sessionsAnalyzed: number; improving: number; stable: number; deteriorating: number; averageRisk: number }; analytics: AnalyticsResponse | null }) {
  const navigate = useNavigate();
  const TrendIcon = trendAnalysis.trend === 'improving' ? TrendingUp : trendAnalysis.trend === 'deteriorating' ? TrendingDown : Minus;
  const trendColor = trendAnalysis.trend === 'improving' ? 'text-green-400' : trendAnalysis.trend === 'deteriorating' ? 'text-red-400' : 'text-on-surface-variant';
  const trendBg = trendAnalysis.trend === 'improving' ? 'bg-green-500/10 border-green-500/30' : trendAnalysis.trend === 'deteriorating' ? 'bg-red-500/10 border-red-500/30' : 'bg-surface-container-low border-outline-variant';
  const weeklyData = analytics?.weekly_risk_trend ?? [];
  const tooltipStyle = { background: '#1d2027', border: '1px solid #424754', borderRadius: '8px', fontSize: '11px', color: '#e1e2ec' };

  return (
    <div className={`border rounded-lg p-lg min-h-[180px] flex flex-col justify-between ${trendBg}`}>
      <div>
        <div className="flex items-center gap-sm mb-sm">
          <TrendIcon className={`w-5 h-5 ${trendColor}`} />
          <span className="font-label-caps text-[10px] text-on-surface-variant">Cross-Session Trend</span>
        </div>
        <p className={`text-display-sm font-bold ${trendColor}`}>
          {trendAnalysis.trend === 'improving' ? 'Improving' : trendAnalysis.trend === 'deteriorating' ? 'Deteriorating' : 'Stable'}
        </p>
        <p className="text-body-sm text-on-surface-variant mt-xs">
          Based on {analytics?.summary.total_sessions ?? trendAnalysis.sessionsAnalyzed} session{((analytics?.summary.total_sessions ?? trendAnalysis.sessionsAnalyzed) !== 1) ? 's' : ''}
        </p>
        <div className="flex gap-md mt-sm text-[11px]">
          <span className="text-green-400">{analytics?.summary.improving ?? trendAnalysis.improving} improving</span>
          <span className="text-on-surface-variant">{analytics?.summary.stable ?? trendAnalysis.stable} stable</span>
          <span className="text-red-400">{analytics?.summary.deteriorating ?? trendAnalysis.deteriorating} deteriorating</span>
        </div>
      </div>
      {weeklyData.length > 0 && (
        <div className="h-16 mt-sm">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={weeklyData}>
              <XAxis dataKey="week" tick={{ fill: '#8c909f', fontSize: 9 }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="averageRisk" fill="#4d8eff" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
      <button
        onClick={() => navigate('/reports?view=risk-trend')}
        className="mt-sm text-body-sm text-primary hover:underline cursor-pointer text-left"
      >
        View full trend analysis →
      </button>
    </div>
  );
}

function TopIssuesCard({ analytics }: { analytics: AnalyticsResponse | null }) {
  const issues = analytics?.issue_frequency ?? [];
  const maxCount = issues.length > 0 ? Math.max(...issues.map((i) => i.count)) : 1;
  return (
    <div className="bg-surface-container border border-outline-variant rounded-lg p-lg min-h-[180px]">
      <div className="flex items-center gap-sm mb-md">
        <AlertTriangle className="w-4 h-4 text-orange-400" />
        <SectionHeader title="Top Ergonomic Issues" />
      </div>
      {issues.length === 0 ? (
        <p className="text-body-sm text-on-surface-variant">No issue data available.</p>
      ) : (
        <div className="space-y-sm">
          {issues.slice(0, 5).map((issue) => (
            <div key={issue.name}>
              <div className="flex justify-between text-body-sm mb-xs">
                <span className="text-on-surface-variant">{issue.name}</span>
                <span className="font-label-mono text-on-surface">{issue.count}</span>
              </div>
              <div className="h-1.5 rounded-full bg-surface-container-highest overflow-hidden">
                <div className="h-full rounded-full bg-orange-400" style={{ width: `${(issue.count / maxCount) * 100}%` }} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function RiskDistributionCard({ analytics }: { analytics: AnalyticsResponse | null }) {
  const distData = analytics?.risk_distribution ?? [];
  const tooltipStyle = { background: '#1d2027', border: '1px solid #424754', borderRadius: '8px', fontSize: '11px', color: '#e1e2ec' };
  return (
    <div className="bg-surface-container border border-outline-variant rounded-lg p-lg min-h-[180px]">
      <div className="flex items-center gap-sm mb-md">
        <BarChart3 className="w-4 h-4 text-primary" />
        <SectionHeader title="Risk Distribution" />
      </div>
      {distData.length === 0 ? (
        <p className="text-body-sm text-on-surface-variant">No distribution data.</p>
      ) : (
        <div className="h-40">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={distData} cx="50%" cy="50%" outerRadius={60} dataKey="value" label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                {distData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
              </Pie>
              <Tooltip contentStyle={tooltipStyle} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

function NeckTrunkTrendCard({ analytics }: { analytics: AnalyticsResponse | null }) {
  const neckTrunkData = analytics?.neck_trunk_trend ?? [];
  const tooltipStyle = { background: '#1d2027', border: '1px solid #424754', borderRadius: '8px', fontSize: '11px', color: '#e1e2ec' };
  return (
    <div className="bg-surface-container border border-outline-variant rounded-lg p-lg min-h-[180px]">
      <div className="flex items-center gap-sm mb-md">
        <Activity className="w-4 h-4 text-primary" />
        <SectionHeader title="Neck & Trunk Trend" />
      </div>
      {neckTrunkData.length === 0 ? (
        <p className="text-body-sm text-on-surface-variant">No trend data available.</p>
      ) : (
        <div className="h-40">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={neckTrunkData}>
              <defs>
                <linearGradient id="dashNeckGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#4d8eff" stopOpacity={0.3} /><stop offset="100%" stopColor="#4d8eff" stopOpacity={0} /></linearGradient>
                <linearGradient id="dashTrunkGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#f97316" stopOpacity={0.3} /><stop offset="100%" stopColor="#f97316" stopOpacity={0} /></linearGradient>
              </defs>
              <XAxis dataKey="week" tick={{ fill: '#8c909f', fontSize: 9 }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={tooltipStyle} />
              <Area type="monotone" dataKey="neck" name="Neck" stroke="#4d8eff" strokeWidth={2} fill="url(#dashNeckGrad)" />
              <Area type="monotone" dataKey="trunk" name="Trunk" stroke="#f97316" strokeWidth={2} fill="url(#dashTrunkGrad)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

function SessionSummaryCard({ analytics }: { analytics: AnalyticsResponse | null }) {
  const summary = analytics?.summary;
  const avgRisk = summary?.avg_risk_score ?? 0;
  const riskLabel = avgRisk < 40 ? 'Low' : avgRisk < 70 ? 'Moderate' : 'High';
  const riskColor = avgRisk < 40 ? 'text-green-400' : avgRisk < 70 ? 'text-orange-400' : 'text-red-400';
  return (
    <div className="bg-surface-container border border-outline-variant rounded-lg p-lg min-h-[180px]">
      <div className="flex items-center gap-sm mb-md">
        <Gauge className="w-4 h-4 text-primary" />
        <SectionHeader title="Session Summary" />
      </div>
      {summary ? (
        <div className="space-y-sm">
          <div className="flex items-center justify-between rounded-lg bg-surface-container-low border border-outline-variant/60 px-md py-sm">
            <span className="text-body-sm text-on-surface-variant">Total Sessions</span>
            <span className="font-label-mono text-on-surface">{summary.total_sessions}</span>
          </div>
          <div className="flex items-center justify-between rounded-lg bg-surface-container-low border border-outline-variant/60 px-md py-sm">
            <span className="text-body-sm text-on-surface-variant">Avg Risk</span>
            <span className={`font-label-mono ${riskColor}`}>{avgRisk.toFixed(1)} ({riskLabel})</span>
          </div>
          <div className="flex items-center justify-between rounded-lg bg-surface-container-low border border-outline-variant/60 px-md py-sm">
            <span className="text-body-sm text-on-surface-variant">Improving</span>
            <span className="font-label-mono text-green-400">{summary.improving}</span>
          </div>
          <div className="flex items-center justify-between rounded-lg bg-surface-container-low border border-outline-variant/60 px-md py-sm">
            <span className="text-body-sm text-on-surface-variant">Deteriorating</span>
            <span className="font-label-mono text-red-400">{summary.deteriorating}</span>
          </div>
        </div>
      ) : (
        <p className="text-body-sm text-on-surface-variant">No session summary data.</p>
      )}
    </div>
  );
}

function formatMaybeNumber(value: number | undefined, digits: number) {
  return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : 'Unavailable';
}

const TASK_MODIFIERS: Record<string, number> = {
  'Neutral Standing': 0,
  'Assembly Work': 5,
  'Reaching': 8,
  'Lifting / Picking': 12,
  'Inspection': 3,
};

const TASK_ICONS: Record<string, typeof Activity> = {
  'Neutral Standing': Activity,
  'Assembly Work': Cpu,
  'Reaching': Zap,
  'Lifting / Picking': ShieldAlert,
  'Inspection': Gauge,
};

function TaskRecognitionCard({ task, taskDuration, taskConfidence, snapshot }: { task: string; taskDuration?: string; taskConfidence?: number; snapshot: { fatigue_score: number; exposure_score: number; final_risk: number; rula_informed_score?: number; feature_scores?: Record<string, number> } | null }) {
  const [modifiers, setModifiers] = useState<Record<string, number>>(TASK_MODIFIERS);

  useEffect(() => {
    let cancelled = false;
    apiFetch('/api/task-modifiers')
      .then((res) => (res.ok ? res.json() : null))
      .then((data: Record<string, number> | null) => {
        if (!cancelled && data) setModifiers(data);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const TaskIcon = TASK_ICONS[task] || Cog;
  const riskImpact = modifiers[task] ?? 0;
  const riskLabel = riskImpact === 0 ? 'Low' : riskImpact <= 5 ? 'Moderate' : riskImpact <= 8 ? 'Elevated' : 'High';
  const riskColor = riskImpact === 0 ? 'text-green-400' : riskImpact <= 5 ? 'text-orange-400' : riskImpact <= 8 ? 'text-yellow-400' : 'text-red-400';
  const riskBg = riskImpact === 0 ? 'bg-green-500/10' : riskImpact <= 5 ? 'bg-orange-500/10' : riskImpact <= 8 ? 'bg-yellow-500/10' : 'bg-red-500/10';
  const confidence = taskConfidence ?? 0;

  return (
    <div className="bg-surface-container border border-outline-variant rounded-lg p-lg min-h-[180px]">
      <div className="flex items-center gap-sm mb-md">
        <Cpu className="w-4 h-4 text-primary" />
        <SectionHeader title="Task Recognition" />
      </div>
      <div className="space-y-sm">
        <div className="flex items-center justify-between rounded-lg bg-surface-container-low border border-outline-variant/60 px-md py-sm">
          <div className="flex items-center gap-sm">
            <TaskIcon className="w-4 h-4 text-primary" />
            <span className="text-body-sm text-on-surface font-medium">{task || 'Unknown'}</span>
          </div>
          <span className="font-label-mono text-on-surface">{taskDuration || '—'}</span>
        </div>
        <div className={`flex items-center justify-between rounded-lg ${riskBg} border border-outline-variant/60 px-md py-sm`}>
          <span className="text-body-sm text-on-surface-variant">Risk Impact</span>
          <span className={`font-label-mono ${riskColor}`}>+{riskImpact} ({riskLabel})</span>
        </div>
        {confidence > 0 && (
          <div className="rounded-lg bg-surface-container-low border border-outline-variant/60 px-md py-sm">
            <div className="flex justify-between text-body-sm mb-xs">
              <span className="text-on-surface-variant">Confidence</span>
              <span className="font-label-mono text-on-surface">{confidence}%</span>
            </div>
            <div className="h-1.5 rounded-full bg-surface-container-highest overflow-hidden">
              <div className="h-full rounded-full bg-primary" style={{ width: `${confidence}%` }} />
            </div>
          </div>
        )}
        <div className="rounded-lg bg-surface-container-low border border-outline-variant/60 px-md py-sm">
          <p className="font-label-caps text-[9px] text-on-surface-variant mb-xs">Task Risk Modifiers</p>
          <div className="space-y-xs">
            {Object.entries(modifiers).map(([name, impact]) => (
              <div key={name} className="flex items-center justify-between text-[10px]">
                <span className="text-on-surface-variant">{name}</span>
                <span className={`font-mono ${impact === 0 ? 'text-green-400' : impact <= 5 ? 'text-orange-400' : 'text-red-400'}`}>+{impact}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

const Cog = ({ className }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
  </svg>
);

function AIInsightsCard({ snapshot }: { snapshot: { fatigue_score: number; exposure_score: number; final_risk: number; rula_informed_score?: number; feature_scores?: Record<string, number> } | null }) {
  const insights: { icon: typeof AlertTriangle; color: string; bg: string; title: string; desc: string }[] = [];

  if (snapshot) {
    if (snapshot.fatigue_score > 70) {
      insights.push({ icon: AlertTriangle, color: 'text-red-400', bg: 'bg-red-500/10', title: 'Fatigue Risk Elevated', desc: `Fatigue at ${snapshot.fatigue_score.toFixed(1)}%. Consider a break.` });
    } else if (snapshot.fatigue_score > 40) {
      insights.push({ icon: TrendingUp, color: 'text-orange-400', bg: 'bg-orange-500/10', title: 'Fatigue Building', desc: `Fatigue at ${snapshot.fatigue_score.toFixed(1)}%. Monitor closely.` });
    }

    if (snapshot.exposure_score > 60) {
      insights.push({ icon: Activity, color: 'text-red-400', bg: 'bg-red-500/10', title: 'High Exposure Duration', desc: `Exposure at ${snapshot.exposure_score.toFixed(1)}%. Extended session detected.` });
    } else if (snapshot.exposure_score > 35) {
      insights.push({ icon: Activity, color: 'text-orange-400', bg: 'bg-orange-500/10', title: 'Moderate Exposure', desc: `Exposure at ${snapshot.exposure_score.toFixed(1)}%. Keep monitoring.` });
    }

    if (snapshot.rula_informed_score !== undefined) {
      if (snapshot.rula_informed_score >= 5) {
        insights.push({ icon: AlertTriangle, color: 'text-red-400', bg: 'bg-red-500/10', title: 'Poor Posture Detected', desc: `RULA score ${snapshot.rula_informed_score}/7. Adjust now.` });
      } else if (snapshot.rula_informed_score >= 3) {
        insights.push({ icon: TrendingUp, color: 'text-orange-400', bg: 'bg-orange-500/10', title: 'Moderate Posture Risk', desc: `RULA score ${snapshot.rula_informed_score}/7. Review positioning.` });
      }
    }

    if (snapshot.feature_scores) {
      const neck = snapshot.feature_scores['avg_neck_flexion'] ?? snapshot.feature_scores['neck_flexion'] ?? 0;
      if (neck > 30) {
        insights.push({ icon: AlertTriangle, color: 'text-yellow-400', bg: 'bg-yellow-500/10', title: 'High Neck Flexion', desc: `Neck angle at ${neck.toFixed(1)}°. Lower chin slightly.` });
      }
    }
  }

  if (insights.length === 0) {
    insights.push({ icon: CheckCircle, color: 'text-green-400', bg: 'bg-green-500/10', title: 'All Clear', desc: 'All ergonomic indicators within safe ranges.' });
  }

  return (
    <div className="bg-surface-container border border-outline-variant rounded-lg p-lg min-h-[180px]">
      <div className="flex items-center gap-sm mb-md">
        <Brain className="w-4 h-4 text-primary" />
        <SectionHeader title="AI Insights" />
      </div>
      <div className="space-y-sm">
        {insights.slice(0, 4).map((item, i) => {
          const Icon = item.icon;
          return (
            <div key={i} className={`flex gap-sm p-sm rounded-lg ${item.bg} border border-transparent`}>
              <Icon className={`w-4 h-4 ${item.color} shrink-0 mt-0.5`} />
              <div className="min-w-0">
                <p className="text-body-sm font-medium text-on-surface">{item.title}</p>
                <p className="text-[10px] text-on-surface-variant mt-0.5 leading-tight">{item.desc}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

interface ModelMetrics {
  accuracy: number;
  labels: string[];
  confusion_matrix: number[][];
  per_class_accuracy: Record<string, number>;
  classification_report: Record<string, { precision: number; recall: number; 'f1-score': number; support: number }>;
  best_params: Record<string, number>;
  train_rows: number;
  test_rows: number;
  model_name: string;
  model_comparison: Record<string, { accuracy: number; best_params: Record<string, number>; per_class_accuracy: Record<string, number> }>;
}

function ModelPerformanceCard() {
  const [metrics, setMetrics] = useState<ModelMetrics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetch('/results/best_model_metrics.json')
      .then((r) => r.json())
      .then((data) => { if (!cancelled) setMetrics(data); })
      .catch(() => { if (!cancelled) setMetrics(null); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  const accuracy = metrics ? (metrics.accuracy * 100).toFixed(1) : '—';
  const modelName = metrics?.model_name?.replace('_', ' ') ?? '—';
  const trainRows = metrics?.train_rows ?? 0;
  const testRows = metrics?.test_rows ?? 0;
  const perClass: Record<string, number> = metrics?.per_class_accuracy ?? {};
  const svmAccuracy = metrics?.model_comparison?.svm?.accuracy;
  const perClassValues = Object.values(perClass).map((v) => Number(v) * 100);
  const maxPerClass = perClassValues.length > 0 ? Math.max(...perClassValues) : 1;

  return (
    <div className="bg-surface-container border border-outline-variant rounded-lg p-lg min-h-[180px]">
      <div className="flex items-center gap-sm mb-md">
        <Brain className="w-4 h-4 text-primary" />
        <SectionHeader title="Risk Model" />
      </div>
      {loading ? (
        <div className="space-y-sm">
          <div className="h-4 bg-surface-container-higher rounded animate-pulse" />
          <div className="h-4 bg-surface-container-higher rounded animate-pulse w-3/4" />
        </div>
      ) : metrics ? (
        <div className="space-y-sm">
          <div className="flex items-center justify-between rounded-lg bg-surface-container-low border border-outline-variant/60 px-md py-sm">
            <span className="text-body-sm text-on-surface-variant">Accuracy</span>
            <span className="font-label-mono text-on-surface">{accuracy}%</span>
          </div>
          <div className="rounded-lg bg-surface-container-low border border-outline-variant/60 px-md py-sm">
            <p className="font-label-caps text-[9px] text-on-surface-variant mb-xs">Per-Class Accuracy</p>
            <div className="space-y-xs">
              {Object.entries(perClass).map(([label, val]) => {
                const value = Number(val);
                return (
                <div key={label}>
                  <div className="flex justify-between text-[10px] mb-0.5">
                    <span className="text-on-surface-variant">{label}</span>
                    <span className="font-mono text-on-surface">{(value * 100).toFixed(1)}%</span>
                  </div>
                  <div className="h-1 rounded-full bg-surface-container-highest overflow-hidden">
                    <div className="h-full rounded-full bg-primary" style={{ width: `${(value * 100) / maxPerClass * 100}%` }} />
                  </div>
                </div>
                );
              })}
            </div>
          </div>
          <div className="flex items-center justify-between rounded-lg bg-surface-container-low border border-outline-variant/60 px-md py-sm">
            <span className="text-body-sm text-on-surface-variant">Model</span>
            <span className="font-label-mono text-on-surface capitalize">{modelName}</span>
          </div>
          <div className="flex items-center justify-between rounded-lg bg-surface-container-low border border-outline-variant/60 px-md py-sm">
            <span className="text-body-sm text-on-surface-variant">Training / Test</span>
            <span className="font-label-mono text-on-surface">{trainRows} / {testRows}</span>
          </div>
          {svmAccuracy !== undefined && (
            <div className="flex items-center justify-between rounded-lg bg-surface-container-low border border-outline-variant/60 px-md py-sm">
              <span className="text-body-sm text-on-surface-variant">vs SVM</span>
              <span className="font-label-mono text-on-surface-variant">{(svmAccuracy * 100).toFixed(1)}%</span>
            </div>
          )}
        </div>
      ) : (
        <p className="text-body-sm text-on-surface-variant">Model metrics unavailable.</p>
      )}
    </div>
  );
}
