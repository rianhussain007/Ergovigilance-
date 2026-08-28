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
  TrendingUp,
  TrendingDown,
  Minus,
  UserCog,
  Users,
  Zap,
} from 'lucide-react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, PieChart, Pie, Cell } from 'recharts';
import { NeckTrunkTrendChart } from '@/src/components/charts/NeckTrunkTrendChart';
import { chartTooltipStyle, chartTick, chartColors, riskLevelColor } from '@/src/components/charts/chartTheme';
import { useDashboard } from '@/src/hooks/useDashboard';
import { useContextSnapshot } from '@/src/hooks/useContextSnapshot';
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
import { formatISTSessionLabel } from '@/src/utils/formatTime';
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
  const { dashboard, sessions, loading, error, refetch } = useDashboard();
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
    <div className="p-lg space-y-lg pb-xl">
      <div className="flex flex-wrap items-end justify-between gap-md">
        <div>
          <h1 className="text-display-lg font-bold text-slate-900 dark:text-on-surface">
            {user?.role === 'operator' ? 'My Dashboard' : 'Dashboard'}
          </h1>
          <p className="text-body-sm text-slate-500 dark:text-on-surface-variant mt-xs">
            {user?.role === 'operator' && ('Welcome back, ' + user.email.split('@')[0] + '. Here is your current posture status.')}
            {(user?.role === 'supervisor' || user?.role === 'safety_mgr') && "Real-time visibility across your team's ergonomic risk."}
            {user?.role === 'admin' && 'System health, monitoring activity, and team performance at a glance.'}
          </p>
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
              liveSessionActive={session?.cameraStatus === 'active'}
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
  workerStatus: string;
  trendAnalysis: { trend: string; sessionsAnalyzed: number; improving: number; stable: number; deteriorating: number; averageRisk: number };
  analytics: AnalyticsResponse | null;
}) {
  const navigate = useNavigate();
  return (
    <>
      <section className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-md">
        <div className="animate-stagger"><MetricCard icon={Gauge} label="My Current Risk" value={formatMaybeNumber(riskScore, 0)} detail={riskLevel.toUpperCase()} tone={riskLevel === 'high' ? 'danger' : riskLevel === 'moderate' ? 'warning' : 'good'} onClick={() => navigate('/monitoring')} isUrgent={true} /></div>
        <div className="animate-stagger"><MetricCard icon={Activity} label="My Current Task" value={task || 'Unavailable'} detail={workerStatus || 'No worker status'} onClick={() => navigate('/monitoring')} /></div>
        <div className="animate-stagger"><MetricCard icon={Clock3} label="Today's Monitoring" value={currentSessionActive ? (sessionDuration ?? 'Calculating') : 'No active session'} detail={sessionId ?? 'Start monitoring to begin'} onClick={() => navigate('/sessions')} /></div>
        <div className="animate-stagger"><MetricCard icon={ShieldAlert} label="My Alerts" value={String(alertCount)} detail={`${activeAlertCount} active`} tone={activeAlertCount > 0 ? 'warning' : 'good'} onClick={() => navigate('/monitoring')} isUrgent={true} /></div>
      </section>

      <section className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_380px] gap-lg">
        <div className="bg-white dark:bg-surface-container border border-slate-200 dark:border-outline-variant rounded-2xl p-lg space-y-lg shadow-sm dark:shadow-none">
          <SectionHeader title="My Health Context" />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-md">
            <ContextTile label="Fatigue" value={snapshot?.fatigue_score != null ? `${Number(snapshot.fatigue_score).toFixed(1)}%` : 'Waiting for live context'} />
            <ContextTile label="Exposure" value={snapshot?.exposure_score != null ? `${Number(snapshot.exposure_score).toFixed(1)}%` : 'Waiting for live context'} />
            <ContextTile label="Context Risk" value={snapshot?.final_risk != null ? Number(snapshot.final_risk).toFixed(1) : 'Waiting for live context'} />
          </div>
          <div>
            <p className="font-label-caps text-[10px] text-slate-400 dark:text-on-surface-variant mb-sm">My Feature Averages</p>
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
              <p className="text-body-sm text-slate-500 dark:text-on-surface-variant">No alerts visible for your current scope.</p>
            ) : ownAlerts.map((alert) => (
              <div key={alert.id}>
                <FeedRow title={alert.title} meta={`${alert.severity} - frame ${alert.frame_number}`} />
              </div>
            ))}
          </FeedCard>

          <FeedCard title="My Recommendations" icon={Lightbulb}>
            {latestRecommendations.length === 0 ? (
              <p className="text-body-sm text-slate-500 dark:text-on-surface-variant">No current recommendations from the Recommendation Engine.</p>
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
            <p className="text-body-sm text-slate-500 dark:text-on-surface-variant">No completed sessions are visible for your account yet.</p>
          ) : operatorRecentSessions.map((session) => (
            <div key={session.id}>
              <FeedRow title={formatSessionLabel(session.date, session.id)} meta={`${session.status} - ${session.duration} - ${session.highestRisk}`} />
            </div>
          ))}
        </FeedCard>
        <TrendSummaryCard trendAnalysis={trendAnalysis} analytics={analytics} />
        <TopIssuesCard analytics={analytics} />
      </section>

      <section className="grid grid-cols-1 xl:grid-cols-2 gap-lg">
        <TaskRecognitionCard task={task} taskDuration={sessionDuration} />
        <AIInsightsCard snapshot={snapshot} />
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
  liveSessionActive,
}: {
  adminSummary: AdminDashboardSummary | null;
  isAdmin: boolean;
  summary: SupervisorDashboardSummary | null;
  summaryError: string | null;
  trendAnalysis: { trend: string; sessionsAnalyzed: number; improving: number; stable: number; deteriorating: number; averageRisk: number };
  analytics: AnalyticsResponse | null;
  snapshot: { fatigue_score: number; exposure_score: number; final_risk: number; rula_informed_score?: number; feature_scores?: Record<string, number> } | null;
  setNotifOpen: (v: boolean) => void;
  liveSessionActive: boolean;
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
        <div className="animate-stagger"><MetricCard icon={Users} label="Visible Workers" value={String(summary.worker_count)} detail="Workers currently tracked" onClick={() => navigate('/workers')} /></div>
        <div className="animate-stagger"><MetricCard icon={Clock3} label="Sessions Today" value={String(summary.sessions_today)} detail="Sessions run today" onClick={() => navigate('/sessions')} /></div>
        <div className="animate-stagger"><MetricCard icon={ShieldAlert} label="Open Alerts" value={String(summary.open_alerts)} detail="Alerts awaiting action" tone={summary.open_alerts > 0 ? 'warning' : 'good'} onClick={() => setNotifOpen(true)} isUrgent={true} /></div>
        <div className="animate-stagger"><MetricCard icon={Gauge} label="Average Risk" value={formatMaybeNumber(summary.average_risk, 1)} detail="Average across visible sessions" onClick={() => navigate('/reports')} isUrgent={true} tone={(summary.average_risk != null && summary.average_risk >= 60) ? 'danger' : (summary.average_risk != null && summary.average_risk >= 30) ? 'warning' : 'good'} /></div>
      </section>

      {isAdmin && adminSummary && (
        <section className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-md">
          <div className="animate-stagger"><MetricCard icon={UserCog} label="Total Users" value={String(adminSummary.total_users)} detail="Registered users" onClick={() => navigate('/users')} /></div>
          <div className="animate-stagger"><MetricCard icon={BarChart3} label="Total Sessions" value={String(adminSummary.total_sessions)} detail="All recorded sessions" onClick={() => navigate('/sessions')} /></div>
          <div className="animate-stagger"><MetricCard icon={Server} label="System Health" value={adminSummary.backend_status === 'healthy' ? 'Operational' : adminSummary.backend_status} detail={`Database: ${adminSummary.database_status}`} tone={adminSummary.backend_status === 'healthy' && adminSummary.database_status === 'healthy' ? 'good' : 'warning'} onClick={() => navigate('/settings')} /></div>
          <div className="animate-stagger"><MetricCard icon={Camera} label="Camera Status" value={adminSummary.connected_camera_status === 'active' ? 'Connected' : 'Disconnected'} detail={adminSummary.connected_camera_status === 'active' ? 'Streaming this session' : liveSessionActive ? 'Connection lost — check cable or network' : 'No camera connected — start a session to connect'} tone={adminSummary.connected_camera_status === 'active' ? 'good' : liveSessionActive ? 'danger' : 'warning'} onClick={() => navigate('/monitoring')} /></div>
        </section>
      )}

      <section className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_380px] gap-lg">
        <div className="bg-white dark:bg-surface-container border border-slate-200 dark:border-outline-variant rounded-2xl p-lg shadow-sm dark:shadow-none">
          <SectionHeader title="Visible Worker Activity" />
          <div className="mt-lg grid grid-cols-1 md:grid-cols-2 gap-md">
            <FeedCard title="Recent Sessions" icon={History}>
              {summary.recent_sessions.length === 0 ? (
                <p className="text-body-sm text-slate-500 dark:text-on-surface-variant">No sessions are visible for this role yet.</p>
              ) : summary.recent_sessions.map((session) => (
                <div key={session.id}>
                  <FeedRow title={formatSessionLabel(session.date, session.id)} meta={`${session.status} - ${session.duration} - ${session.worker_id ?? 'No worker assigned'}`} />
                </div>
              ))}
            </FeedCard>
            <FeedCard title="Recent Alerts" icon={AlertTriangle}>
              {summary.recent_alerts.length === 0 ? (
                <p className="text-body-sm text-slate-500 dark:text-on-surface-variant">No alert history is currently available.</p>
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
            <div className="bg-white dark:bg-surface-container border border-slate-200 dark:border-outline-variant rounded-2xl p-lg shadow-sm dark:shadow-none">
              <div className="flex items-center gap-sm mb-md">
                <Database className="w-4 h-4 text-blue-600 dark:text-primary" />
                <SectionHeader title="Role Distribution" />
              </div>
              <div className="space-y-sm">
                {Object.entries(adminSummary.role_distribution).map(([role, count]) => (
                  <div key={role} className="flex items-center justify-between rounded-xl bg-slate-50 dark:bg-surface-container-low border border-slate-100 dark:border-outline-variant/60 px-md py-sm">
                    <span className="text-body-sm text-slate-600 dark:text-on-surface-variant">{role}</span>
                    <span className="font-label-mono text-slate-800 dark:text-on-surface">{count}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="bg-white dark:bg-surface-container border border-slate-200 dark:border-outline-variant rounded-2xl p-lg shadow-sm dark:shadow-none">
              <div className="flex items-center gap-sm mb-md">
                <HeartPulse className="w-4 h-4 text-blue-600 dark:text-primary" />
                <SectionHeader title="Safety Scope" />
              </div>
              <p className="text-body-sm text-slate-500 dark:text-on-surface-variant">
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

      <section className="grid grid-cols-1 xl:grid-cols-2 gap-lg">
        <TaskRecognitionCard task="No active session" taskDuration="—" />
        <AIInsightsCard snapshot={snapshot} />
      </section>
    </>
  );
}

function MetricCard({ icon: Icon, label, value, detail, tone = 'neutral', onClick, isUrgent = false }: { icon: ElementType; label: string; value: string; detail: string; tone?: 'neutral' | 'good' | 'warning' | 'danger'; onClick?: () => void; isUrgent?: boolean }) {
  const numericValue = parseFloat(value);
  const hasNonZeroUrgent = isUrgent && !isNaN(numericValue) && numericValue > 0;

  const iconClass = tone === 'danger' ? 'text-red-500 dark:text-red-400' : tone === 'warning' ? 'text-amber-500 dark:text-orange-400' : tone === 'good' ? 'text-emerald-500 dark:text-green-400' : 'text-blue-600 dark:text-primary';

  const leftBorderClass = tone === 'danger' ? 'border-l-red-500' : tone === 'warning' ? 'border-l-amber-500' : tone === 'good' ? 'border-l-emerald-500' : 'border-l-slate-200 dark:border-l-outline-variant';

  const bgClass = hasNonZeroUrgent
    ? (tone === 'danger' ? 'bg-red-50 dark:bg-red-500/10' : tone === 'warning' ? 'bg-amber-50 dark:bg-orange-500/10' : 'bg-emerald-50 dark:bg-green-500/10')
    : 'bg-white dark:bg-surface-container';

  const borderClass = tone === 'danger' ? 'border border-red-100 dark:border-red-500/30' : tone === 'warning' ? 'border border-amber-100 dark:border-orange-500/30' : tone === 'good' ? 'border border-emerald-100 dark:border-green-500/30' : 'border border-slate-200 dark:border-outline-variant';

  const sizeClass = isUrgent ? 'min-h-[140px]' : 'min-h-[132px]';
  const textSizeClass = isUrgent ? 'text-display-lg' : 'text-display-md';

  const Tag = onClick ? 'button' : 'div';
  return (
    <Tag onClick={onClick} className={`${bgClass} border-l-4 ${leftBorderClass} ${borderClass} rounded-xl shadow-sm dark:shadow-none p-md ${sizeClass} text-left w-full ${onClick ? 'cursor-pointer hover:shadow-md hover:-translate-y-0.5 transition-all duration-200' : ''}`}>
      <div className="flex items-center justify-between mb-sm gap-sm">
        <span className="font-label-caps text-[10px] text-slate-400 dark:text-on-surface-variant">{label}</span>
        <Icon className={`w-5 h-5 ${iconClass} shrink-0`} />
      </div>
      <p className={`${textSizeClass} font-bold text-slate-900 dark:text-on-surface break-words`}>{value}</p>
      <p className="text-[11px] text-slate-500 dark:text-on-surface-variant mt-xs">{detail}</p>
    </Tag>
  );
}

function ContextTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-200 dark:border-outline-variant/60 bg-slate-50 dark:bg-surface-container-low p-md min-h-[96px] hover:border-blue-200 dark:hover:border-primary/20 transition-colors">
      <p className="font-label-caps text-[10px] text-slate-400 dark:text-on-surface-variant">{label}</p>
      <p className="mt-sm text-display-sm font-bold text-slate-900 dark:text-on-surface break-words">{value}</p>
    </div>
  );
}

function FeatureAverageBar({ label, value, unit }: { label: string; value: number | null | undefined; unit: string }) {
  const safeValue = typeof value === 'number' && Number.isFinite(value) ? value : 0;
  const width = Math.max(4, Math.min(100, unit === '%' ? safeValue : safeValue / 1.8));
  return (
    <div className="group">
      <div className="flex justify-between text-body-sm mb-xs gap-md">
        <span className="text-slate-500 dark:text-on-surface-variant group-hover:text-slate-700 dark:group-hover:text-on-surface transition-colors">{label}</span>
        <span className="font-label-mono text-slate-700 dark:text-on-surface">{safeValue.toFixed(1)} {unit}</span>
      </div>
      <div className="h-2 rounded-full bg-slate-100 dark:bg-surface-container-highest overflow-hidden">
        <div className="h-full rounded-full bg-blue-500 dark:bg-primary transition-all duration-500 ease-out" style={{ width: `${width}%` }} />
      </div>
    </div>
  );
}

function FeedCard({ children, icon: Icon, title }: { children: ReactNode; icon: ElementType; title: string }) {
  return (
    <div className="bg-white dark:bg-surface-container border border-slate-200 dark:border-outline-variant rounded-2xl p-lg min-h-[220px] shadow-sm dark:shadow-none">
      <div className="flex items-center gap-sm mb-md">
        <Icon className="w-4 h-4 text-blue-600 dark:text-primary" />
        <SectionHeader title={title} />
      </div>
      <div className="space-y-sm">{children}</div>
    </div>
  );
}

function FeedRow({ title, meta }: { title: string; meta: string }) {
  return (
    <div className="rounded-xl border border-slate-100 dark:border-outline-variant/60 bg-slate-50 dark:bg-surface-container-low p-sm">
      <p className="text-body-sm font-medium text-slate-800 dark:text-on-surface">{title}</p>
      <p className="text-[11px] text-slate-500 dark:text-on-surface-variant mt-0.5">{meta}</p>
    </div>
  );
}

function TrendSummaryCard({ trendAnalysis, analytics }: { trendAnalysis: { trend: string; sessionsAnalyzed: number; improving: number; stable: number; deteriorating: number; averageRisk: number }; analytics: AnalyticsResponse | null }) {
  const navigate = useNavigate();
  // The headline must match the underlying counts: if more sessions are
  // deteriorating than improving, the trend is Declining — never "Stable".
  const improving = analytics?.summary.improving ?? trendAnalysis.improving;
  const deteriorating = analytics?.summary.deteriorating ?? trendAnalysis.deteriorating;
  const effectiveTrend = deteriorating > improving && deteriorating > 0
    ? 'declining'
    : improving > deteriorating && improving > 0
      ? 'improving'
      : 'stable';
  const TrendIcon = effectiveTrend === 'improving' ? TrendingUp : effectiveTrend === 'declining' ? TrendingDown : Minus;
  const trendColor = effectiveTrend === 'improving' ? 'text-emerald-600 dark:text-green-400' : effectiveTrend === 'declining' ? 'text-red-600 dark:text-red-400' : 'text-slate-600 dark:text-on-surface-variant';
  const trendBg = effectiveTrend === 'improving' ? 'bg-emerald-50 dark:bg-green-500/10 border-emerald-200 dark:border-green-500/30' : effectiveTrend === 'declining' ? 'bg-red-50 dark:bg-red-500/10 border-red-200 dark:border-red-500/30' : 'bg-slate-50 dark:bg-surface-container-low border-slate-200 dark:border-outline-variant';
  const weeklyData = analytics?.weekly_risk_trend ?? [];

  return (
    <div className={`border rounded-lg p-lg min-h-[180px] flex flex-col justify-between ${trendBg}`}>
      <div>
        <div className="flex items-center gap-sm mb-sm">
          <TrendIcon className={`w-5 h-5 ${trendColor}`} />
          <span className="font-label-caps text-[10px] text-on-surface-variant">Cross-Session Trend</span>
        </div>
        <p className={`text-display-sm font-bold ${trendColor}`}>
          {effectiveTrend === 'improving' ? 'Improving' : effectiveTrend === 'declining' ? 'Declining' : 'Stable'}
        </p>
        <p className="text-body-sm text-on-surface-variant mt-xs">
          Based on {analytics?.summary.total_sessions ?? trendAnalysis.sessionsAnalyzed} session{((analytics?.summary.total_sessions ?? trendAnalysis.sessionsAnalyzed) !== 1) ? 's' : ''}
        </p>
        <div className="flex gap-md mt-sm text-[11px]">
          <span className="text-emerald-600 dark:text-green-400">{improving} improving</span>
          <span className="text-slate-500 dark:text-on-surface-variant">{analytics?.summary.stable ?? trendAnalysis.stable} stable</span>
          <span className="text-red-600 dark:text-red-400">{deteriorating} deteriorating</span>
        </div>
      </div>
      {weeklyData.length > 0 && (
        <div className="h-16 mt-sm">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={weeklyData}>
              <XAxis dataKey="week" tick={{ fill: 'var(--color-outline)', fontSize: 9 }} axisLine={false} tickLine={false} />
              {/* Explicit cursor keeps hover from flashing the default gray rectangle */}
              <Tooltip contentStyle={chartTooltipStyle} cursor={{ fill: 'rgba(77, 142, 255, 0.12)' }} />
              <Bar dataKey="averageRisk" name="Average Risk" fill={chartColors.blue} radius={[3, 3, 0, 0]} />
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
    <div className="bg-white dark:bg-surface-container border border-slate-200 dark:border-outline-variant rounded-2xl p-lg min-h-[180px] shadow-sm dark:shadow-none">
      <div className="flex items-center gap-sm mb-md">
        <AlertTriangle className="w-4 h-4 text-amber-500 dark:text-orange-400" />
        <SectionHeader title="Top Ergonomic Issues" />
      </div>
      {issues.length === 0 ? (
        <p className="text-body-sm text-slate-500 dark:text-on-surface-variant">No issue data available.</p>
      ) : (
        <div className="space-y-sm">
          {issues.slice(0, 5).map((issue) => (
            <div key={issue.name}>
              <div className="flex justify-between text-body-sm mb-xs">
                <span className="text-slate-600 dark:text-on-surface-variant">{issue.name}</span>
                <span className="font-label-mono text-slate-800 dark:text-on-surface">{issue.count}</span>
              </div>
              <div className="h-1.5 rounded-full bg-slate-100 dark:bg-surface-container-highest overflow-hidden">
                <div className="h-full rounded-full bg-amber-400 dark:bg-orange-400" style={{ width: `${(issue.count / maxCount) * 100}%` }} />
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
  return (
    <div className="bg-white dark:bg-surface-container border border-slate-200 dark:border-outline-variant rounded-2xl p-lg min-h-[180px] shadow-sm dark:shadow-none">
      <div className="flex items-center gap-sm mb-md">
        <BarChart3 className="w-4 h-4 text-blue-600 dark:text-primary" />
        <SectionHeader title="Risk Distribution" />
      </div>
      {distData.length === 0 ? (
        <p className="text-body-sm text-on-surface-variant">No distribution data.</p>
      ) : (
        <div className="h-40">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={distData} cx="50%" cy="50%" outerRadius={60} dataKey="value" label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                {distData.map((entry, i) => <Cell key={i} fill={riskLevelColor(entry.name)} />)}
              </Pie>
              <Tooltip contentStyle={chartTooltipStyle} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

function NeckTrunkTrendCard({ analytics }: { analytics: AnalyticsResponse | null }) {
  const neckTrunkData = analytics?.neck_trunk_trend ?? [];
  return (
    <div className="bg-white dark:bg-surface-container border border-slate-200 dark:border-outline-variant rounded-2xl p-lg min-h-[180px] shadow-sm dark:shadow-none">
      <div className="flex items-center gap-sm mb-md">
        <Activity className="w-4 h-4 text-blue-600 dark:text-primary" />
        <SectionHeader title="Neck & Trunk Trend" />
      </div>
      {neckTrunkData.length === 0 ? (
        <p className="text-body-sm text-on-surface-variant">No trend data available.</p>
      ) : (
        <div className="h-40">
          <NeckTrunkTrendChart data={neckTrunkData} />
        </div>
      )}
    </div>
  );
}

function SessionSummaryCard({ analytics }: { analytics: AnalyticsResponse | null }) {
  const summary = analytics?.summary;
  const avgRisk = summary?.avg_risk_score ?? 0;
  const riskLabel = avgRisk < 40 ? 'Low' : avgRisk < 70 ? 'Moderate' : 'High';
  const riskColor = avgRisk < 40 ? 'text-emerald-600 dark:text-green-400' : avgRisk < 70 ? 'text-amber-600 dark:text-orange-400' : 'text-red-600 dark:text-red-400';
  return (
    <div className="bg-white dark:bg-surface-container border border-slate-200 dark:border-outline-variant rounded-2xl p-lg min-h-[180px] shadow-sm dark:shadow-none">
      <div className="flex items-center gap-sm mb-md">
        <Gauge className="w-4 h-4 text-blue-600 dark:text-primary" />
        <SectionHeader title="Session Summary" />
      </div>
      {summary ? (
        <div className="space-y-sm">
          <div className="flex items-center justify-between rounded-xl bg-slate-50 dark:bg-surface-container-low border border-slate-100 dark:border-outline-variant/60 px-md py-sm">
            <span className="text-body-sm text-slate-500 dark:text-on-surface-variant">Total Sessions</span>
            <span className="font-label-mono text-slate-800 dark:text-on-surface">{summary.total_sessions}</span>
          </div>
          <div className="flex items-center justify-between rounded-xl bg-slate-50 dark:bg-surface-container-low border border-slate-100 dark:border-outline-variant/60 px-md py-sm">
            <span className="text-body-sm text-slate-500 dark:text-on-surface-variant">Avg Risk</span>
            <span className={`font-label-mono ${riskColor}`}>{avgRisk.toFixed(1)} ({riskLabel})</span>
          </div>
          <div className="flex items-center justify-between rounded-xl bg-slate-50 dark:bg-surface-container-low border border-slate-100 dark:border-outline-variant/60 px-md py-sm">
            <span className="text-body-sm text-slate-500 dark:text-on-surface-variant">Improving</span>
            <span className="font-label-mono text-emerald-600 dark:text-green-400">{summary.improving}</span>
          </div>
          <div className="flex items-center justify-between rounded-xl bg-slate-50 dark:bg-surface-container-low border border-slate-100 dark:border-outline-variant/60 px-md py-sm">
            <span className="text-body-sm text-slate-500 dark:text-on-surface-variant">Deteriorating</span>
            <span className="font-label-mono text-red-600 dark:text-red-400">{summary.deteriorating}</span>
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

/** Human-readable session label in IST with the raw ID on hover. */
function formatSessionLabel(date: string, rawId: string): string {
  const d = date ? new Date(date) : null;
  if (d && !Number.isNaN(d.getTime())) {
    return formatISTSessionLabel(d);
  }
  return rawId;
}

const TASK_ICONS: Record<string, typeof Activity> = {
  'Neutral Standing': Activity,
  'Walking / Moving': Activity,
  'Inspection': Gauge,
  'Seated Work': Cpu,
  'Assembly Work': Cpu,
  'Reaching': Zap,
  'Lifting / Picking': ShieldAlert,
};

function TaskRecognitionCard({ task, taskDuration }: { task: string; taskDuration?: string }) {
  const TaskIcon = TASK_ICONS[task] || Activity;

  return (
    <div className="bg-white dark:bg-surface-container border border-slate-200 dark:border-outline-variant rounded-2xl p-lg min-h-[180px] shadow-sm dark:shadow-none">
      <div className="flex items-center gap-sm mb-md">
        <Cpu className="w-4 h-4 text-blue-600 dark:text-primary" />
        <SectionHeader title="Current Task" />
      </div>
      <div className="space-y-sm">
        <div className="flex items-center justify-between rounded-xl bg-slate-50 dark:bg-surface-container-low border border-slate-100 dark:border-outline-variant/60 px-md py-sm">
          <div className="flex items-center gap-sm">
            <TaskIcon className="w-4 h-4 text-blue-600 dark:text-primary" />
            <span className="text-body-sm text-slate-800 dark:text-on-surface font-medium">{task || 'No active session'}</span>
          </div>
          {taskDuration && taskDuration !== '—' && (
            <span className="font-label-mono text-slate-700 dark:text-on-surface">{taskDuration}</span>
          )}
        </div>
        <p className="text-[11px] text-slate-500 dark:text-on-surface-variant leading-relaxed">
          The activity recognized from the live camera feed (e.g. lifting, reaching, seated work).
        </p>
      </div>
    </div>
  );
}

function AIInsightsCard({ snapshot }: { snapshot: { fatigue_score: number; exposure_score: number; final_risk: number; rula_informed_score?: number; feature_scores?: Record<string, number> } | null }) {
  const insights: { icon: typeof AlertTriangle; color: string; bg: string; title: string; desc: string }[] = [];

  if (snapshot) {
    const fatigueScore = snapshot.fatigue_score ?? 0;
    const exposureScore = snapshot.exposure_score ?? 0;

    if (fatigueScore > 70) {
      insights.push({ icon: AlertTriangle, color: 'text-red-500 dark:text-red-400', bg: 'bg-red-50 dark:bg-red-500/10', title: 'Fatigue Risk Elevated', desc: `Fatigue at ${Number(fatigueScore).toFixed(1)}%. Consider a break.` });
    } else if (fatigueScore > 40) {
      insights.push({ icon: TrendingUp, color: 'text-amber-500 dark:text-orange-400', bg: 'bg-amber-50 dark:bg-orange-500/10', title: 'Fatigue Building', desc: `Fatigue at ${Number(fatigueScore).toFixed(1)}%. Monitor closely.` });
    }

    if (exposureScore > 60) {
      insights.push({ icon: Activity, color: 'text-red-500 dark:text-red-400', bg: 'bg-red-50 dark:bg-red-500/10', title: 'High Exposure Duration', desc: `Exposure at ${Number(exposureScore).toFixed(1)}%. Extended session detected.` });
    } else if (exposureScore > 35) {
      insights.push({ icon: Activity, color: 'text-amber-500 dark:text-orange-400', bg: 'bg-amber-50 dark:bg-orange-500/10', title: 'Moderate Exposure', desc: `Exposure at ${Number(exposureScore).toFixed(1)}%. Keep monitoring.` });
    }

    if (snapshot.rula_informed_score !== undefined) {
      if (snapshot.rula_informed_score >= 5) {
        insights.push({ icon: AlertTriangle, color: 'text-red-500 dark:text-red-400', bg: 'bg-red-50 dark:bg-red-500/10', title: 'Poor Posture Detected', desc: `Posture score ${snapshot.rula_informed_score}/7. Adjust now.` });
      } else if (snapshot.rula_informed_score >= 3) {
        insights.push({ icon: TrendingUp, color: 'text-amber-500 dark:text-orange-400', bg: 'bg-amber-50 dark:bg-orange-500/10', title: 'Moderate Posture Risk', desc: `Posture score ${snapshot.rula_informed_score}/7. Review positioning.` });
      }
    }

    if (snapshot.feature_scores) {
      const neck = snapshot.feature_scores['avg_neck_flexion'] ?? snapshot.feature_scores['neck_flexion'] ?? 0;
      if (neck > 30) {
        insights.push({ icon: AlertTriangle, color: 'text-amber-600 dark:text-yellow-400', bg: 'bg-amber-50 dark:bg-yellow-500/10', title: 'High Neck Flexion', desc: `Neck angle at ${neck.toFixed(1)}°. Lower chin slightly.` });
      }
    }
  }

  if (insights.length === 0) {
    insights.push({ icon: CheckCircle, color: 'text-emerald-500 dark:text-green-400', bg: 'bg-emerald-50 dark:bg-green-500/10', title: 'All Clear', desc: 'All ergonomic indicators within safe ranges.' });
  }

  return (
    <div className="bg-white dark:bg-surface-container border border-slate-200 dark:border-outline-variant rounded-2xl p-lg min-h-[180px] shadow-sm dark:shadow-none">
      <div className="flex items-center gap-sm mb-md">
        <Brain className="w-4 h-4 text-blue-600 dark:text-primary" />
        <SectionHeader title="AI Insights" />
      </div>
      <div className="space-y-sm">
        {insights.slice(0, 4).map((item, i) => {
          const Icon = item.icon;
          return (
            <div key={i} className={`flex gap-sm p-sm rounded-xl ${item.bg} border border-transparent`}>
              <Icon className={`w-4 h-4 ${item.color} shrink-0 mt-0.5`} />
              <div className="min-w-0">
                <p className="text-body-sm font-medium text-slate-800 dark:text-on-surface">{item.title}</p>
                <p className="text-[10px] text-slate-500 dark:text-on-surface-variant mt-0.5 leading-tight">{item.desc}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
