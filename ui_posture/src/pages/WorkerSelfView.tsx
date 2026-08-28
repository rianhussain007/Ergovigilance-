import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router';
import {
  Activity, AlertTriangle, CheckCircle, Clock3, FileText,
  Heart, Shield, TrendingUp, TrendingDown, Minus, Eye, Lock,
  ChevronRight, Gauge, Brain, Zap, Info, BarChart3
} from 'lucide-react';
import { SectionHeader, LoadingCard, ErrorCard, EmptyState } from '@/src/components/common';
import { apiFetch } from '@/src/services/apiClient';
import { useAuth } from '@/src/auth/AuthContext';
import { formatISTSessionLabel } from '@/src/utils/formatTime';

/* ── Types ─────────────────────────────────────────────────────────── */

interface WorkerSummary {
  worker_id: string | null;
  worker_name: string;
  current_risk: string;
  current_score: number;
  current_task: string;
  session_active: boolean;
  confidence_band: string;
  sessions: {
    id: string;
    date: string;
    duration: string;
    highestRisk: string;
    task: string;
    status: string;
  }[];
  alerts: {
    id: string;
    title: string;
    severity: string;
    state: string;
    created_at: string;
    session_id: string;
    message: string;
    confidence: number;
    confidence_band: string;
  }[];
  risk_trend: string;
  total_sessions: number;
  consent_status: string;
  identity_mode: string;
  data_retention: string;
  source?: string;
}

/* ── Color tokens (light + dark) ───────────────────────────────────── */

const RISK_STYLES: Record<string, {
  text: string; bg: string; border: string; ring: string;
  badge: string; icon: string; heading: string;
}> = {
  low: {
    text: 'text-emerald-700 dark:text-emerald-300',
    bg: 'bg-emerald-50 dark:bg-emerald-500/10',
    border: 'border-emerald-200 dark:border-emerald-400/30',
    ring: 'ring-emerald-200 dark:ring-emerald-400/20',
    badge: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300',
    icon: 'text-emerald-500 dark:text-emerald-400',
    heading: 'text-emerald-800 dark:text-emerald-200',
  },
  medium: {
    text: 'text-amber-700 dark:text-amber-300',
    bg: 'bg-amber-50 dark:bg-amber-500/10',
    border: 'border-amber-200 dark:border-amber-400/30',
    ring: 'ring-amber-200 dark:ring-amber-400/20',
    badge: 'bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300',
    icon: 'text-amber-500 dark:text-amber-400',
    heading: 'text-amber-800 dark:text-amber-200',
  },
  high: {
    text: 'text-red-700 dark:text-red-300',
    bg: 'bg-red-50 dark:bg-red-500/10',
    border: 'border-red-200 dark:border-red-400/30',
    ring: 'ring-red-200 dark:ring-red-400/20',
    badge: 'bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300',
    icon: 'text-red-500 dark:text-red-400',
    heading: 'text-red-800 dark:text-red-200',
  },
};

const PLAIN_STATUS: Record<string, string> = {
  low: 'Your posture looks good — keep it up!',
  medium: 'Straighten your back and relax your shoulders.',
  high: 'Stop and adjust your posture now — risk of injury.',
};

const TASK_COACHING: Record<string, { tip: string; why: string; icon: string }> = {
  'Lifting / Picking': {
    tip: 'Bend your knees, keep the load close to your body.',
    why: 'Lifting with your back instead of legs multiplies spinal load by 5×.',
    icon: '🦾',
  },
  'Reaching': {
    tip: 'Move your feet instead of overextending your arms.',
    why: 'Overreach forces your shoulder into an unsafe range of motion.',
    icon: '🙋',
  },
  'Assembly Work': {
    tip: 'Keep your elbows close to your body and take micro-breaks every 20 minutes.',
    why: 'Sustained shoulder elevation during assembly is the #1 cause of MSDs in line workers.',
    icon: '🔧',
  },
  'Seated Work': {
    tip: 'Adjust your chair so your feet are flat on the floor and screen is at eye level.',
    why: 'Poor seated posture compresses the lumbar spine over time.',
    icon: '🪑',
  },
  'Inspection': {
    tip: 'Alternate between standing and sitting. Use a height-adjustable surface.',
    why: 'Static standing for >30 min causes venous pooling and lower-back fatigue.',
    icon: '🔍',
  },
  'Walking / Moving': {
    tip: 'Maintain a natural gait — avoid sudden twists or carrying loads on one side.',
    why: 'Asymmetric loading during movement increases fall and strain risk.',
    icon: '🚶',
  },
  'Neutral Standing': {
    tip: 'Shift your weight between legs periodically. Keep knees slightly soft.',
    why: 'Static standing without movement restricts blood flow and tires core muscles.',
    icon: '🧍',
  },
};

const CONFIDENCE_COLORS: Record<string, string> = {
  high: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-400',
  medium: 'bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-400',
  low: 'bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-400',
};

/* ── Sparkline Component ────────────────────────────────────────────── */

function RiskSparkline({ sessions }: { sessions: WorkerSummary['sessions'] }) {
  const points = useMemo(() => {
    const riskMap: Record<string, number> = { LOW: 1, MEDIUM: 2, HIGH: 3 };
    return sessions.slice(0, 10).reverse().map((s, i) => ({
      x: i,
      y: riskMap[s.highestRisk] || 1,
      risk: s.highestRisk,
      task: s.task,
    }));
  }, [sessions]);

  if (points.length < 2) return null;

  const width = 280;
  const height = 60;
  const padX = 8;
  const padY = 8;
  const plotW = width - padX * 2;
  const plotH = height - padY * 2;

  const pathD = points.map((p, i) => {
    const x = padX + (i / (points.length - 1)) * plotW;
    const y = padY + plotH - ((p.y - 1) / 2) * plotH;
    return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
  }).join(' ');

  const colorMap: Record<string, string> = {
    LOW: '#10b981', MEDIUM: '#f59e0b', HIGH: '#ef4444',
  };

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-16" preserveAspectRatio="none">
      {/* Grid lines */}
      {[1, 2, 3].map((v) => {
        const y = padY + plotH - ((v - 1) / 2) * plotH;
        return <line key={v} x1={padX} y1={y} x2={width - padX} y2={y} stroke="currentColor" strokeOpacity={0.08} strokeDasharray="2 4" />;
      })}
      {/* Gradient fill */}
      <defs>
        <linearGradient id="sparkFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.15} />
          <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.02} />
        </linearGradient>
      </defs>
      <path d={`${pathD} L ${padX + plotW} ${padY + plotH} L ${padX} ${padY + plotH} Z`} fill="url(#sparkFill)" />
      {/* Line */}
      <path d={pathD} fill="none" stroke="#3b82f6" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
      {/* Dots */}
      {points.map((p, i) => {
        const x = padX + (i / (points.length - 1)) * plotW;
        const y = padY + plotH - ((p.y - 1) / 2) * plotH;
        return <circle key={i} cx={x} cy={y} r={3} fill={colorMap[p.risk] || '#3b82f6'} />;
      })}
    </svg>
  );
}

/* ── Main Component ────────────────────────────────────────────────── */

export default function WorkerSelfView() {
  const { user, isDemoMode } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState<WorkerSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const fetchData = async () => {
      try {
        const res = await apiFetch('/api/worker/my-summary');
        if (!res.ok) throw new Error('Failed to load your summary');
        const result = await res.json();
        if (!cancelled) { setData(result); setError(null); }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchData();
    // Poll less frequently in demo mode (data is synthetic, doesn't change)
    const interval = setInterval(fetchData, isDemoMode ? 30000 : 5000);
    return () => { cancelled = true; clearInterval(interval); };
  }, [isDemoMode]);

  if (error) return (
    <div className="flex items-center justify-center h-full p-lg">
      <ErrorCard message={error} onRetry={() => { setLoading(true); setError(null); }} />
    </div>
  );

  if (loading || !data) {
    return (
      <div className="p-lg space-y-lg pb-xl">
        <LoadingCard height="h-24" />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-lg">
          <LoadingCard height="h-48" />
          <LoadingCard height="h-48" />
          <LoadingCard height="h-48" />
        </div>
      </div>
    );
  }

  const risk = RISK_STYLES[data.current_risk] || RISK_STYLES.low;
  const coaching = TASK_COACHING[data.current_task];
  const trendIcon = data.risk_trend === 'improving' ? TrendingUp
    : data.risk_trend === 'deteriorating' ? TrendingDown : Minus;
  const trendColor = data.risk_trend === 'improving' ? 'text-emerald-600 dark:text-emerald-400'
    : data.risk_trend === 'deteriorating' ? 'text-red-600 dark:text-red-400'
    : 'text-slate-500 dark:text-on-surface-variant';
  const trendLabel = data.risk_trend === 'improving' ? 'Improving'
    : data.risk_trend === 'deteriorating' ? 'Needs Attention' : 'Stable';

  // Session stats
  const highCount = data.sessions.filter(s => s.highestRisk === 'HIGH').length;
  const medCount = data.sessions.filter(s => s.highestRisk === 'MEDIUM').length;
  const lowCount = data.sessions.filter(s => s.highestRisk === 'LOW').length;

  return (
    <div className="p-lg space-y-lg pb-xl max-w-4xl mx-auto">

      {/* ── Demo Mode Banner ──────────────────────────────────── */}
      {isDemoMode && (
        <div className="flex items-center gap-md px-md py-sm rounded-xl bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-400/30 text-amber-700 dark:text-amber-300 text-body-sm">
          <Info className="w-4 h-4 shrink-0" />
          <span>Demo mode — showing synthetic data for <strong>{data.worker_name}</strong>. No real workers are being monitored.</span>
        </div>
      )}

      {/* ── Header ────────────────────────────────────────────── */}
      <div>
        <h1 className="text-display-lg font-bold text-slate-900 dark:text-on-surface">My Posture</h1>
        <p className="text-body-sm text-slate-500 dark:text-on-surface-variant mt-xs">
          Your personal posture status and history. This data is yours — only you and your supervisor can see it.
        </p>
      </div>

      {/* ── Current Risk — Hero Card ──────────────────────────── */}
      <section className={`rounded-2xl border-2 ${risk.border} ${risk.bg} p-lg ring-1 ${risk.ring} transition-all`}>
        <div className="flex items-center justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-md mb-xs">
              <Gauge className={`w-5 h-5 ${risk.icon}`} />
              <p className="font-label-caps text-xs text-slate-500 dark:text-on-surface-variant uppercase tracking-widest">Current Posture</p>
            </div>
            <p className={`text-display-lg font-extrabold ${risk.heading}`}>
              {data.current_risk === 'high' ? '⚠️ STOP — Unsafe Posture'
                : data.current_risk === 'medium' ? 'Watch Your Back'
                : '✅ Posture: OK'}
            </p>
            <p className={`text-body-md ${risk.text} mt-1 font-medium`}>
              {PLAIN_STATUS[data.current_risk]}
            </p>
          </div>
          <div className="text-right shrink-0 ml-lg">
            <p className="font-label-mono text-4xl font-bold text-slate-900 dark:text-on-surface">{data.current_score.toFixed(0)}</p>
            <p className="text-[10px] text-slate-500 dark:text-on-surface-variant uppercase tracking-widest mt-1">Risk Score</p>
          </div>
        </div>

        {data.session_active && (
          <div className="mt-4 flex flex-wrap items-center gap-md text-sm text-slate-600 dark:text-on-surface-variant">
            <span className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-white/60 dark:bg-white/5 border border-slate-200 dark:border-outline-variant/50">
              <Activity className="w-3.5 h-3.5" /> {data.current_task}
            </span>
            <span className={`flex items-center gap-1.5 px-2 py-1 rounded-lg text-xs font-medium ${CONFIDENCE_COLORS[data.confidence_band] || CONFIDENCE_COLORS.medium}`}>
              <Brain className="w-3.5 h-3.5" /> {data.confidence_band} confidence
            </span>
          </div>
        )}
      </section>

      {/* ── Coaching Tip (task-specific) ──────────────────────── */}
      {data.session_active && coaching && (
        <section className="rounded-xl border border-cyan-200 dark:border-cyan-400/30 bg-cyan-50 dark:bg-cyan-500/10 p-md">
          <div className="flex items-start gap-md">
            <span className="text-2xl shrink-0">{coaching.icon}</span>
            <div className="flex-1">
              <p className="text-body-sm font-bold text-cyan-800 dark:text-cyan-200">
                Tip for {data.current_task}
              </p>
              <p className="text-body-sm text-cyan-700 dark:text-cyan-200/80 mt-0.5">{coaching.tip}</p>
              <p className="text-[11px] text-cyan-600/70 dark:text-cyan-300/50 mt-1 italic">{coaching.why}</p>
            </div>
          </div>
        </section>
      )}

      {/* ── Quick Stats Row ───────────────────────────────────── */}
      <div className="grid grid-cols-3 gap-md">
        <div className="rounded-xl border border-slate-200 dark:border-outline-variant bg-white dark:bg-surface-container p-md text-center">
          <p className="text-display-sm font-bold text-slate-900 dark:text-on-surface">{data.total_sessions}</p>
          <p className="text-[10px] text-slate-500 dark:text-on-surface-variant uppercase tracking-widest mt-0.5">Total Sessions</p>
        </div>
        <div className="rounded-xl border border-slate-200 dark:border-outline-variant bg-white dark:bg-surface-container p-md text-center">
          <p className="text-display-sm font-bold text-emerald-600 dark:text-emerald-400">{lowCount}</p>
          <p className="text-[10px] text-slate-500 dark:text-on-surface-variant uppercase tracking-widest mt-0.5">Low Risk</p>
        </div>
        <div className="rounded-xl border border-slate-200 dark:border-outline-variant bg-white dark:bg-surface-container p-md text-center">
          <p className="text-display-sm font-bold text-red-600 dark:text-red-400">{highCount}</p>
          <p className="text-[10px] text-slate-500 dark:text-on-surface-variant uppercase tracking-widest mt-0.5">High Risk</p>
        </div>
      </div>

      {/* ── Risk Trend + Sparkline ────────────────────────────── */}
      <section className="bg-white dark:bg-surface-container border border-slate-200 dark:border-outline-variant rounded-xl p-lg">
        <div className="flex items-center justify-between mb-md">
          <div className="flex items-center gap-md">
            {(() => { const Icon = trendIcon; return <Icon className={`w-6 h-6 ${trendColor}`} />; })()}
            <div>
              <p className="font-label-caps text-xs text-slate-500 dark:text-on-surface-variant uppercase tracking-widest">Your Trend</p>
              <p className={`text-title-md font-bold mt-0.5 ${trendColor}`}>{trendLabel}</p>
            </div>
          </div>
          <p className="text-xs text-slate-400 dark:text-on-surface-variant">Last {Math.min(data.total_sessions, 10)} sessions</p>
        </div>
        <RiskSparkline sessions={data.sessions} />
        <div className="flex justify-between text-[9px] text-slate-400 dark:text-on-surface-variant/60 mt-1 px-1">
          <span>Oldest</span>
          <span>Newest</span>
        </div>
      </section>

      {/* ── Recent Sessions ───────────────────────────────────── */}
      <section className="bg-white dark:bg-surface-container border border-slate-200 dark:border-outline-variant rounded-xl p-lg">
        <div className="flex items-center justify-between mb-md">
          <SectionHeader title="My Recent Sessions" />
          <BarChart3 className="w-4 h-4 text-slate-400 dark:text-on-surface-variant" />
        </div>
        {data.sessions.length === 0 ? (
          <EmptyState title="No sessions yet" message="Start a monitoring session to see your history here." />
        ) : (
          <div className="space-y-sm">
            {data.sessions.slice(0, 10).map((s) => {
              const riskKey = (s.highestRisk || 'LOW').toLowerCase();
              const cfg = RISK_STYLES[riskKey] || RISK_STYLES.low;
              return (
                <button
                  key={s.id}
                  onClick={() => navigate(`/replay/${s.id}`)}
                  className="w-full flex items-center gap-md p-md rounded-lg border border-slate-100 dark:border-outline-variant/50 bg-slate-50/50 dark:bg-surface-container-low hover:bg-slate-100 dark:hover:bg-surface-container-higher transition-colors text-left group"
                >
                  <div className={`w-1.5 h-10 rounded-full shrink-0 ${
                    riskKey === 'high' ? 'bg-red-500' : riskKey === 'medium' ? 'bg-amber-500' : 'bg-emerald-500'
                  }`} />
                  <div className="flex-1 min-w-0">
                    <p className="text-body-sm font-medium text-slate-800 dark:text-on-surface truncate">{s.task}</p>
                    <p className="text-[11px] text-slate-500 dark:text-on-surface-variant">
                      {s.date ? formatISTSessionLabel(new Date(s.date)) : s.id} · {s.duration}
                    </p>
                  </div>
                  <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${cfg.badge}`}>{s.highestRisk}</span>
                  <ChevronRight className="w-4 h-4 text-slate-400 dark:text-on-surface-variant group-hover:text-slate-600 dark:group-hover:text-on-surface transition-colors" />
                </button>
              );
            })}
          </div>
        )}
      </section>

      {/* ── Recent Alerts ─────────────────────────────────────── */}
      {data.alerts.length > 0 && (
        <section className="bg-white dark:bg-surface-container border border-slate-200 dark:border-outline-variant rounded-xl p-lg">
          <SectionHeader title="My Recent Alerts" />
          <div className="space-y-sm mt-md">
            {data.alerts.slice(0, 5).map((a) => {
              const isHigh = a.severity === 'HIGH' || a.severity === 'CRITICAL';
              const isMed = a.severity === 'MEDIUM' || a.severity === 'WARNING';
              return (
                <div key={a.id} className="flex items-start gap-md p-md rounded-lg border border-slate-100 dark:border-outline-variant/50 bg-slate-50/50 dark:bg-surface-container-low">
                  <AlertTriangle className={`w-4 h-4 shrink-0 mt-0.5 ${
                    isHigh ? 'text-red-500 dark:text-red-400' : isMed ? 'text-amber-500 dark:text-amber-400' : 'text-blue-500 dark:text-blue-400'
                  }`} />
                  <div className="flex-1 min-w-0">
                    <p className="text-body-sm font-medium text-slate-800 dark:text-on-surface">{a.title}</p>
                    <p className="text-[11px] text-slate-500 dark:text-on-surface-variant mt-0.5 line-clamp-2">{a.message}</p>
                  </div>
                  <span className={`px-1.5 py-0.5 rounded text-[9px] font-medium shrink-0 ${CONFIDENCE_COLORS[a.confidence_band] || CONFIDENCE_COLORS.medium}`}>
                    {a.confidence_band} certainty
                  </span>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* ── Privacy & Consent ─────────────────────────────────── */}
      <section className="bg-white dark:bg-surface-container border border-slate-200 dark:border-outline-variant rounded-xl p-lg">
        <div className="flex items-center gap-md mb-md">
          <Shield className="w-5 h-5 text-blue-500 dark:text-primary" />
          <SectionHeader title="Your Data & Privacy" />
        </div>
        <div className="space-y-sm">
          <InfoRow
            icon={Eye}
            label="Identity mode"
            value={data.identity_mode === 'off' ? 'Anonymous (no face tracking)' : data.identity_mode}
          />
          <InfoRow
            icon={Lock}
            label="Consent status"
            value={data.consent_status === 'granted' ? 'Granted — you can revoke anytime'
              : data.consent_status === 'denied' ? 'Denied — data collection paused'
              : 'Pending — awaiting your consent'}
          />
          <InfoRow
            icon={FileText}
            label="Data retention"
            value={data.data_retention}
          />
        </div>
        <div className="mt-4 p-3 rounded-lg bg-slate-50 dark:bg-surface-container-low border border-slate-100 dark:border-outline-variant/30">
          <p className="text-[11px] text-slate-500 dark:text-on-surface-variant/70 leading-relaxed">
            Your posture data is used <strong>only</strong> to improve your workplace safety. It is <strong>not</strong> used for
            performance evaluation, disciplinary action, or any purpose beyond ergonomic assessment.
            You can request deletion of your data at any time from the Settings page.
          </p>
        </div>
      </section>
    </div>
  );
}

/* ── Info Row ──────────────────────────────────────────────────────── */

function InfoRow({ icon: Icon, label, value }: { icon: typeof Eye; label: string; value: string }) {
  return (
    <div className="flex items-center gap-md p-md rounded-lg bg-slate-50 dark:bg-surface-container-low border border-slate-100 dark:border-outline-variant/50">
      <Icon className="w-4 h-4 text-slate-400 dark:text-on-surface-variant shrink-0" />
      <div className="min-w-0">
        <p className="text-[10px] text-slate-500 dark:text-on-surface-variant uppercase tracking-widest">{label}</p>
        <p className="text-body-sm text-slate-800 dark:text-on-surface mt-0.5">{value}</p>
      </div>
    </div>
  );
}
