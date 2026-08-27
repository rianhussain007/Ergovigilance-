import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router';
import {
  Activity, AlertTriangle, CheckCircle, Clock3, FileText,
  Heart, Shield, TrendingUp, TrendingDown, Minus, Eye, Lock,
  ChevronRight, Gauge, Brain
} from 'lucide-react';
import { SectionHeader, LoadingCard, ErrorCard, EmptyState } from '@/src/components/common';
import { apiFetch } from '@/src/services/apiClient';
import { useAuth } from '@/src/auth/AuthContext';
import { formatISTSessionLabel } from '@/src/utils/formatTime';

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
}

const RISK_COLORS: Record<string, { text: string; bg: string; border: string }> = {
  low: { text: 'text-emerald-300', bg: 'bg-emerald-500/10', border: 'border-emerald-400/30' },
  medium: { text: 'text-amber-300', bg: 'bg-amber-500/10', border: 'border-amber-400/30' },
  high: { text: 'text-red-300', bg: 'bg-red-500/10', border: 'border-red-400/30' },
};

const PLAIN_TIPS: Record<string, string> = {
  low: 'Your posture looks good. Keep it up!',
  medium: 'Straighten your back and relax your shoulders.',
  high: 'Stop and adjust your posture now — risk of injury.',
};

const TASK_TIPS: Record<string, string> = {
  'Lifting / Picking': 'Bend your knees, keep the load close to your body.',
  'Reaching': 'Move your feet instead of overextending your arms.',
  'Assembly Work': 'Keep your elbows close to your body and take breaks.',
  'Seated Work': 'Adjust your chair so your feet are flat on the floor.',
  'Inspection': 'Alternate between standing and sitting.',
  'Walking / Moving': 'Maintain a natural gait — avoid sudden twists.',
  'Neutral Standing': 'Shift your weight between legs periodically.',
};

export default function WorkerSelfView() {
  const { user } = useAuth();
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
    const interval = setInterval(fetchData, 5000);
    return () => { cancelled = true; clearInterval(interval); };
  }, []);

  if (error) return <div className="flex items-center justify-center h-full p-lg"><ErrorCard message={error} onRetry={() => { setLoading(true); setError(null); }} /></div>;
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

  const riskCfg = RISK_COLORS[data.current_risk] || RISK_COLORS.low;
  const trendIcon = data.risk_trend === 'improving' ? TrendingUp : data.risk_trend === 'deteriorating' ? TrendingDown : Minus;
  const trendColor = data.risk_trend === 'improving' ? 'text-emerald-300' : data.risk_trend === 'deteriorating' ? 'text-red-300' : 'text-on-surface-variant';

  return (
    <div className="p-lg space-y-lg pb-xl max-w-4xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-display-lg font-bold text-on-surface">My Posture</h1>
        <p className="text-body-sm text-on-surface-variant mt-xs">
          Your personal posture status and history. This data is yours — only you and your supervisor can see it.
        </p>
      </div>

      {/* Current Risk — Big, jargon-free */}
      <section className={`rounded-2xl border ${riskCfg.border} ${riskCfg.bg} p-lg`}>
        <div className="flex items-center justify-between">
          <div>
            <p className="font-label-caps text-xs text-on-surface-variant uppercase tracking-widest">My Current Posture</p>
            <p className={`text-display-lg font-extrabold mt-1 ${riskCfg.text}`}>
              {data.current_risk === 'high' ? 'STOP — Unsafe Posture' :
               data.current_risk === 'medium' ? 'Watch Your Back' : 'Posture: OK'}
            </p>
            <p className="text-body-md text-on-surface-variant mt-1">
              {PLAIN_TIPS[data.current_risk] || 'Monitoring your posture.'}
            </p>
          </div>
          <div className="text-right">
            <p className="font-label-mono text-3xl font-bold text-on-surface">{data.current_score.toFixed(0)}</p>
            <p className="text-[10px] text-on-surface-variant uppercase tracking-widest">Risk Score</p>
          </div>
        </div>
        {data.session_active && (
          <div className="mt-4 flex items-center gap-md text-sm text-on-surface-variant">
            <span className="flex items-center gap-1"><Activity className="w-3.5 h-3.5" /> {data.current_task}</span>
            <span className="flex items-center gap-1"><Brain className="w-3.5 h-3.5" /> Confidence: {data.confidence_band}</span>
          </div>
        )}
      </section>

      {/* Actionable Tip */}
      {data.session_active && data.current_task && TASK_TIPS[data.current_task] && (
        <section className="rounded-xl border border-cyan-400/30 bg-cyan-500/10 p-md">
          <div className="flex items-start gap-md">
            <Heart className="w-5 h-5 text-cyan-300 shrink-0 mt-0.5" />
            <div>
              <p className="text-body-sm font-bold text-cyan-200">Tip for {data.current_task}</p>
              <p className="text-body-sm text-cyan-200/80 mt-0.5">{TASK_TIPS[data.current_task]}</p>
            </div>
          </div>
        </section>
      )}

      {/* Risk Trend */}
      <section className="bg-surface-container border border-outline-variant rounded-xl p-lg">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-md">
            {(() => { const Icon = trendIcon; return <Icon className={`w-6 h-6 ${trendColor}`} />; })()}
            <div>
              <p className="font-label-caps text-xs text-on-surface-variant uppercase tracking-widest">Your Trend</p>
              <p className={`text-title-md font-bold mt-0.5 ${trendColor}`}>
                {data.risk_trend === 'improving' ? 'Improving' : data.risk_trend === 'deteriorating' ? 'Needs Attention' : 'Stable'}
              </p>
            </div>
          </div>
          <p className="text-sm text-on-surface-variant">Based on your last {Math.min(data.total_sessions, 10)} sessions</p>
        </div>
      </section>

      {/* Recent Sessions */}
      <section className="bg-surface-container border border-outline-variant rounded-xl p-lg">
        <SectionHeader title="My Recent Sessions" />
        {data.sessions.length === 0 ? (
          <EmptyState title="No sessions yet" message="Start a monitoring session to see your history here." />
        ) : (
          <div className="space-y-sm mt-md">
            {data.sessions.slice(0, 10).map((s) => {
              const risk = (s.highestRisk || 'LOW').toLowerCase();
              const cfg = RISK_COLORS[risk] || RISK_COLORS.low;
              return (
                <button
                  key={s.id}
                  onClick={() => navigate(`/replay/${s.id}`)}
                  className="w-full flex items-center gap-md p-md rounded-lg border border-outline-variant/50 bg-surface-container-low hover:bg-surface-container-higher transition-colors text-left"
                >
                  <div className={`w-2 h-8 rounded-full ${risk === 'high' ? 'bg-red-500' : risk === 'medium' ? 'bg-amber-500' : 'bg-emerald-500'}`} />
                  <div className="flex-1 min-w-0">
                    <p className="text-body-sm font-medium text-on-surface truncate">{s.task}</p>
                    <p className="text-[11px] text-on-surface-variant">
                      {s.date ? formatISTSessionLabel(new Date(s.date)) : s.id} · {s.duration}
                    </p>
                  </div>
                  <span className={`text-body-sm font-bold ${cfg.text}`}>{s.highestRisk}</span>
                  <ChevronRight className="w-4 h-4 text-on-surface-variant" />
                </button>
              );
            })}
          </div>
        )}
      </section>

      {/* Recent Alerts */}
      {data.alerts.length > 0 && (
        <section className="bg-surface-container border border-outline-variant rounded-xl p-lg">
          <SectionHeader title="My Recent Alerts" />
          <div className="space-y-sm mt-md">
            {data.alerts.slice(0, 5).map((a) => (
              <div key={a.id} className="flex items-start gap-md p-md rounded-lg border border-outline-variant/50 bg-surface-container-low">
                <AlertTriangle className={`w-4 h-4 shrink-0 mt-0.5 ${
                  a.severity === 'HIGH' || a.severity === 'CRITICAL' ? 'text-red-400' :
                  a.severity === 'WARNING' ? 'text-amber-400' : 'text-blue-400'
                }`} />
                <div className="flex-1">
                  <p className="text-body-sm font-medium text-on-surface">{a.title}</p>
                  <p className="text-[11px] text-on-surface-variant mt-0.5">{a.message}</p>
                </div>
                <span className={`px-1.5 py-0.5 rounded text-[9px] font-medium ${
                  a.confidence_band === 'high' ? 'bg-green-500/15 text-green-400' :
                  a.confidence_band === 'low' ? 'bg-red-500/15 text-red-400' :
                  'bg-yellow-500/15 text-yellow-400'
                }`}>
                  {a.confidence_band} certainty
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Privacy & Consent */}
      <section className="bg-surface-container border border-outline-variant rounded-xl p-lg">
        <div className="flex items-center gap-md mb-md">
          <Shield className="w-5 h-5 text-primary" />
          <SectionHeader title="Your Data & Privacy" />
        </div>
        <div className="space-y-sm">
          <InfoRow icon={Eye} label="Identity mode" value={data.identity_mode === 'off' ? 'Anonymous (no face tracking)' : data.identity_mode} />
          <InfoRow icon={Lock} label="Consent status" value={data.consent_status} />
          <InfoRow icon={FileText} label="Data retention" value={data.data_retention} />
        </div>
        <p className="text-[11px] text-on-surface-variant/60 mt-md">
          Your posture data is used only to improve your workplace safety. It is not used for performance evaluation.
          You can request deletion of your data at any time from the Settings page.
        </p>
      </section>
    </div>
  );
}

function InfoRow({ icon: Icon, label, value }: { icon: typeof Eye; label: string; value: string }) {
  return (
    <div className="flex items-center gap-md p-md rounded-lg bg-surface-container-low border border-outline-variant/50">
      <Icon className="w-4 h-4 text-on-surface-variant shrink-0" />
      <div>
        <p className="text-[10px] text-on-surface-variant uppercase tracking-widest">{label}</p>
        <p className="text-body-sm text-on-surface mt-0.5">{value}</p>
      </div>
    </div>
  );
}
