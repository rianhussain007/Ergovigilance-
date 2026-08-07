
import React, { useState, useEffect, useCallback, useRef } from 'react';
import type { ElementType } from 'react';
import { Server, Database, Camera, Users, Gauge, Zap } from 'lucide-react';
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
