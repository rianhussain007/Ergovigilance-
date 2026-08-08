
import React, { useState, useEffect, useCallback, useRef } from 'react';
import type { ElementType } from 'react';
import { Server, Database, Camera, Users, Gauge, Zap, BrainCircuit, Activity, AlertTriangle } from 'lucide-react';
import { getDeployment } from '@/src/services/dashboardService';
import { getStoredToken } from '@/src/auth/AuthContext';
import { useDemo } from '@/src/demo/DemoProvider';
import { ErrorCard, LoadingCard, SectionHeader } from '@/src/components/common';
import type { DeploymentMetrics } from '@/src/types/api';

const formatBytes = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`;
  else if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  else if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  else return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
};

const formatDuration = (seconds: number): string => {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
};

export default function DeploymentCenter() {
  const { state: demoState } = useDemo();
  const [metrics, setMetrics] = useState<DeploymentMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  const fetchDeploymentMetrics = useCallback(async () => {
    if (demoState.active) {
      setMetrics({
        backendStatus: 'ok',
        backendVersion: '0.1.0',
        backendUptimeSeconds: 3600,
        databaseEngine: 'SQLite',
        databaseSizeBytes: 159744,
        databaseStatus: 'ok',
        cameraCount: 1,
        registeredWorkerCount: 3,
        activeSessionCount: 0,
        sessionActive: false,
        sessionFps: null,
        sessionInferenceLatencyMs: null,
        drift: {
          samples: 1820,
          window_seconds: 300,
          model_samples: 1650,
          gaussian_samples: 170,
          fallback_rate: 9.3,
          avg_confidence: 88.4,
          avg_model_confidence: 91.2,
          trend: 'stable',
          trend_delta_pp: 1.2,
          healthy: true,
        },
      });
      setLoading(false);
      setError(null);
      return;
    }

    if (!getStoredToken()) {
      setMetrics(null);
      setLoading(false);
      setError('Please log in to view deployment metrics');
      return;
    }
    try {
      const data = await getDeployment();
      if (!mountedRef.current) return;
      setMetrics(data);
      setError(null);
    } catch (err) {
      if (!mountedRef.current) return;
      setError(err instanceof Error ? err.message : 'Failed to load metrics');
      console.error('Error fetching deployment metrics:', err);
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  }, [demoState.active]);

  useEffect(() => {
    mountedRef.current = true;
    fetchDeploymentMetrics();
    const interval = setInterval(fetchDeploymentMetrics, 30000);
    return () => {
      mountedRef.current = false;
      clearInterval(interval);
    };
  }, [fetchDeploymentMetrics]);

  if (loading) {
    return (
      <div className="p-lg space-y-lg pb-32">
        <div className="flex flex-wrap items-end justify-between gap-md">
          <div>
            <h1 className="text-display-lg font-bold text-on-surface">Deployment Center</h1>
            <p className="text-body-sm text-on-surface-variant mt-xs">
              Real system status and operational metrics.
            </p>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-md">
          <LoadingCard height="h-48" />
          <LoadingCard height="h-48" />
          <LoadingCard height="h-48" />
          <LoadingCard height="h-48" />
        </div>
      </div>
    );
  }

  if (error || !metrics) {
    return (
      <div className="p-lg space-y-lg pb-32">
        <div className="flex flex-wrap items-end justify-between gap-md">
          <div>
            <h1 className="text-display-lg font-bold text-on-surface">Deployment Center</h1>
            <p className="text-body-sm text-on-surface-variant mt-xs">
              Real system status and operational metrics.
            </p>
          </div>
        </div>
        <ErrorCard message={error || 'Failed to load metrics'} onRetry={fetchDeploymentMetrics} />
      </div>
    );
  }

  const backendTone = metrics.backendStatus === 'ok' ? 'good' : 'warning';
  const dbTone = metrics.databaseStatus === 'ok' ? 'good' : 'warning';

  return (
    <div className="p-lg space-y-lg pb-32">
      <div className="flex flex-wrap items-end justify-between gap-md">
        <div>
          <h1 className="text-display-lg font-bold text-on-surface">Deployment Center</h1>
          <p className="text-body-sm text-on-surface-variant mt-xs">
            Real system status and operational metrics.
          </p>
        </div>
      </div>

      <section className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-md">
        <MetricCard
          icon={Server}
          label="Backend API"
          value={metrics.backendVersion}
          detail={`Status: ${metrics.backendStatus} • Uptime: ${formatDuration(metrics.backendUptimeSeconds)}`}
          tone={backendTone}
        />
        <MetricCard
          icon={Database}
          label="Database"
          value={metrics.databaseEngine}
          detail={`Size: ${formatBytes(metrics.databaseSizeBytes)} • Status: ${metrics.databaseStatus}`}
          tone={dbTone}
        />
        <MetricCard
          icon={Camera}
          label="Detected Cameras"
          value={String(metrics.cameraCount)}
          detail="Cameras detected on host"
        />
        <MetricCard
          icon={Users}
          label="Registered Workers"
          value={String(metrics.registeredWorkerCount)}
          detail="Workers in SQLite"
        />
      </section>

      <section className="grid grid-cols-1 md:grid-cols-2 gap-md">
        <MetricCard
          icon={Gauge}
          label="Active Sessions"
          value={String(metrics.activeSessionCount)}
          detail="Currently active monitoring sessions"
          tone={metrics.activeSessionCount > 0 ? 'good' : 'neutral'}
        />
        {metrics.sessionActive && (
          <div className="bg-surface-container border border-outline-variant rounded-lg p-lg min-h-[132px]">
            <div className="flex items-center gap-sm mb-sm">
              <Zap className="w-5 h-5 text-primary shrink-0" />
              <span className="font-label-caps text-[10px] text-on-surface-variant">Session Performance</span>
            </div>
            <div className="space-y-xs">
              <div className="flex items-center justify-between rounded-lg bg-surface-container-low border border-outline-variant/60 px-md py-sm">
                <span className="text-body-sm text-on-surface-variant">FPS</span>
                <span className="font-label-mono text-on-surface">{metrics.sessionFps?.toFixed(1) ?? '—'}</span>
              </div>
              <div className="flex items-center justify-between rounded-lg bg-surface-container-low border border-outline-variant/60 px-md py-sm">
                <span className="text-body-sm text-on-surface-variant">Inference Latency</span>
                <span className="font-label-mono text-on-surface">{metrics.sessionInferenceLatencyMs?.toFixed(1) ?? '—'} ms</span>
              </div>
            </div>
          </div>
        )}
      </section>

      <section className="bg-surface-container border border-outline-variant rounded-xl p-lg">
        <div className="flex items-center gap-md mb-md">
          <BrainCircuit className="w-5 h-5 text-primary" />
          <div>
            <h2 className="text-headline-md font-bold text-on-surface">Model Health</h2>
            <p className="text-[10px] text-on-surface-variant">Task-classifier drift canary — model usage vs Gaussian fallback</p>
          </div>
          {metrics.drift ? (
            <span className={`ml-auto inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider border ${
              metrics.drift.healthy
                ? 'bg-green-500/10 border-green-500/30 text-green-400'
                : 'bg-amber-500/10 border-amber-500/30 text-amber-400'
            }`}>
              {metrics.drift.healthy ? <Activity className="w-3 h-3" /> : <AlertTriangle className="w-3 h-3" />}
              {metrics.drift.healthy ? 'Healthy' : 'Attention'}
            </span>
          ) : (
            <span className="ml-auto text-[10px] text-on-surface-variant/60">No samples yet — start a session</span>
          )}
        </div>

        {metrics.drift && metrics.drift.samples > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-md">
            <DriftStat label="Fallback Rate" value={`${metrics.drift.fallback_rate.toFixed(1)}%`} sub={`${metrics.drift.gaussian_samples}/${metrics.drift.samples} frames`} tone={metrics.drift.fallback_rate > 50 ? 'danger' : metrics.drift.fallback_rate > 25 ? 'warning' : 'good'} />
            <DriftStat label="Model Samples" value={String(metrics.drift.model_samples)} sub={`of ${metrics.drift.samples} in window`} />
            <DriftStat label="Avg Confidence" value={metrics.drift.avg_confidence != null ? `${metrics.drift.avg_confidence.toFixed(1)}%` : '—'} sub={metrics.drift.avg_model_confidence != null ? `model-only: ${metrics.drift.avg_model_confidence.toFixed(1)}%` : ''} />
            <DriftStat
              label="Trend (5 min)"
              value={metrics.drift.trend === 'stable' ? 'Stable' : metrics.drift.trend === 'rising' ? 'Rising' : 'Falling'}
              sub={`${metrics.drift.trend_delta_pp > 0 ? '+' : ''}${metrics.drift.trend_delta_pp.toFixed(1)}pp`}
              tone={metrics.drift.trend === 'rising' ? 'danger' : metrics.drift.trend === 'falling' ? 'good' : 'neutral'}
            />
            <div className="bg-surface-container-low rounded-lg p-md border border-outline-variant/50 min-h-[96px]">
              <p className="text-[10px] text-on-surface-variant">Fallback rate trend</p>
              <div className="mt-sm space-y-xs">
                {[['Model', metrics.drift.model_samples], ['Fallback', metrics.drift.gaussian_samples]].map(([label, count]) => {
                  const total = Math.max(metrics.drift.samples, 1);
                  const pct = (Number(count) / total) * 100;
                  return (
                    <div key={String(label)}>
                      <div className="flex justify-between text-[10px]">
                        <span className="text-on-surface-variant">{label}</span>
                        <span className="font-label-mono text-on-surface">{pct.toFixed(0)}%</span>
                      </div>
                      <div className="h-1.5 bg-surface-container-higher rounded-full overflow-hidden mt-0.5">
                        <div className={`h-full rounded-full ${String(label) === 'Model' ? 'bg-green-500' : 'bg-orange-500'}`} style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        ) : (
          <p className="text-body-sm text-on-surface-variant">
            Run a live monitoring session so the canary can measure how often the trained task model is used vs. the Gaussian fallback.
          </p>
        )}
      </section>
    </div>
  );
}

function DriftStat({ label, value, sub, tone = 'neutral' }: { label: string; value: string; sub?: string; tone?: 'neutral' | 'good' | 'warning' | 'danger' }) {
  const color = tone === 'danger' ? 'text-red-400' : tone === 'warning' ? 'text-orange-400' : tone === 'good' ? 'text-green-400' : 'text-on-surface';
  return (
    <div className="bg-surface-container-low rounded-lg p-md border border-outline-variant/50 min-h-[96px]">
      <p className="text-[10px] text-on-surface-variant">{label}</p>
      <p className={`text-title-lg font-bold mt-1 ${color}`}>{value}</p>
      {sub && <p className="text-[10px] text-on-surface-variant/70 mt-0.5">{sub}</p>}
    </div>
  );
}

function MetricCard({ icon: Icon, label, value, detail, tone = 'neutral', onClick }: { icon: ElementType; label: string; value: string; detail: string; tone?: 'neutral' | 'good' | 'warning' | 'danger'; onClick?: () => void }) {
  const iconClass = tone === 'danger' ? 'text-red-400' : tone === 'warning' ? 'text-orange-400' : tone === 'good' ? 'text-green-400' : 'text-primary';
  const borderClass = tone === 'danger' ? 'border-red-500/30' : tone === 'warning' ? 'border-orange-500/30' : tone === 'good' ? 'border-green-500/30' : 'border-outline-variant';
  const Tag = onClick ? 'button' : 'div';
  return (
    <Tag onClick={onClick} className={`bg-surface-container border ${borderClass} rounded-lg p-md min-h-[132px] text-left w-full ${onClick ? 'cursor-pointer hover:bg-surface-container-higher hover:shadow-sm transition-all duration-150' : ''}`}>
      <div className="flex items-center justify-between mb-sm gap-sm">
        <span className="font-label-caps text-[10px] text-on-surface-variant">{label}</span>
        <Icon className={`w-5 h-5 ${iconClass} shrink-0`} />
      </div>
      <p className="text-display-md font-bold text-on-surface break-words">{value}</p>
      <p className="text-[11px] text-on-surface-variant mt-xs">{detail}</p>
    </Tag>
  );
}
