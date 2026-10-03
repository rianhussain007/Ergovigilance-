import { useCallback, useEffect, useMemo, useState } from 'react';
import { Activity, Server, Database, Wifi, WifiOff, Clock, Cpu, HardDrive, RefreshCw, CheckCircle2, XCircle, AlertTriangle, Zap, Shield, FileText, Gauge, HeartPulse } from 'lucide-react';
import { ErrorCard } from '@/src/components/common';
import { usePolledResource } from '@/src/hooks/usePolling';
import { apiFetchJson } from '@/src/services/apiClient';

type HealthPayload = Record<string, any>;

/**
 * One poll of the backend health payload feeds every panel on this page
 * (audit F-UX-04): the four enterprise monitoring cards below each used to run
 * their own `fetch('/health')` on a 15s timer, so an idle page cost five
 * requests per 15s, none with a timeout, visibility or unmount guard.
 */
async function fetchBackendHealth(): Promise<HealthPayload> {
  return apiFetchJson<HealthPayload>('/health', { timeoutMs: 8000 }, 'Backend health');
}

async function fetchCloudHealth(): Promise<HealthPayload> {
  return apiFetchJson<HealthPayload>(
    '/cloud-api/cloud/health',
    { timeoutMs: 8000 },
    'Cloud core health',
  );
}

interface ServiceHealth {
  name: string;
  status: 'healthy' | 'degraded' | 'down';
  port: number;
  uptime: string;
  latency_ms: number;
  last_check: string;
  details?: Record<string, any>;
}

interface SystemMetrics {
  services: ServiceHealth[];
  database: {
    status: string;
    connections: number;
    max_connections: number;
    size_mb: number;
  };
  storage: {
    sessions_mb: number;
    recordings_mb: number;
    models_mb: number;
    total_mb: number;
  };
  api: {
    total_requests: number;
    avg_response_ms: number;
    error_rate: number;
    endpoints_count: number;
  };
}

export default function SystemHealthPage() {
  const health = usePolledResource<HealthPayload | null>(fetchBackendHealth, {
    initial: null,
    intervalMs: 10_000,
    requiresAuth: false,
    label: 'Backend health',
  });
  const cloud = usePolledResource<HealthPayload | null>(fetchCloudHealth, {
    initial: null,
    intervalMs: 30_000,
    requiresAuth: false,
    label: 'Cloud core health',
  });
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());

  useEffect(() => {
    if (health.data) setLastRefresh(new Date());
  }, [health.data]);

  const refresh = useCallback(() => {
    health.refetch();
    cloud.refetch();
  }, [health.refetch, cloud.refetch]);

  const metrics = useMemo<SystemMetrics | null>(() => {
    const backend = health.data;
    const cloudCore = cloud.data ?? {};
    if (!backend) return null;

      // Backend is healthy if it returned a JSON with status healthy/degraded
      const backendUp = backend.status === 'healthy' || backend.status === 'degraded';
      const cloudUp = cloudCore.status === 'healthy' || cloudCore.status === 'degraded';

      const services: ServiceHealth[] = [
        {
          name: 'Backend API',
          status: backendUp ? (backend.status === 'healthy' ? 'healthy' : 'degraded') : 'down',
          port: 8000,
          uptime: backend.uptime || '-',
          latency_ms: backend.latency_ms || backend.db_latency_ms || 0,
          last_check: new Date().toISOString(),
          details: backend,
        },
        {
          name: 'YOLO Cloud Core',
          status: cloudUp ? (cloudCore.status === 'healthy' ? 'healthy' : 'degraded') : 'down',
          port: 8100,
          uptime: cloudCore.uptime || cloudCore.uptime_seconds ? `${Math.round(cloudCore.uptime_seconds || 0)}s` : '-',
          latency_ms: cloudCore.latency_ms || 0,
          last_check: new Date().toISOString(),
          details: cloudCore,
        },
        {
          name: 'Frontend',
          status: 'healthy',
          port: 3000,
          uptime: '-',
          latency_ms: 0,
          last_check: new Date().toISOString(),
        },
        {
          name: 'Database (SQLite)',
          status: backend.database_status === 'connected' ? 'healthy' : backendUp ? 'degraded' : 'down',
          port: 0,
          uptime: '-',
          latency_ms: backend.db_latency_ms || 0,
          last_check: new Date().toISOString(),
          details: { status: backend.database_status || 'unknown' },
        },
      ];

      // Get storage info from health endpoint
      const disk = backend.disk_usage_mb || {};
      const metricsData: SystemMetrics = {
        services,
        database: {
          status: backend.database_status || 'unknown',
          connections: 1,
          max_connections: 1,
          size_mb: disk.sessions || 0,
        },
        storage: {
          sessions_mb: disk.sessions || 0,
          recordings_mb: disk.recordings || 0,
          models_mb: disk.models || 0,
          total_mb: (disk.sessions || 0) + (disk.recordings || 0) + (disk.models || 0),
        },
        api: {
          total_requests: backend.total_requests || 0,
          avg_response_ms: backend.latency_ms || 0,
          error_rate: backend.error_rate || 0,
          endpoints_count: 87,
        },
      };

    return metricsData;
  }, [health.data, cloud.data]);

  if (health.loading && !metrics) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  // Never fabricate an "all services down" dashboard: if the backend never
  // answered, say so and offer a retry instead of painting a fake green/red grid.
  if (!metrics) {
    return (
      <div className="mx-auto max-w-2xl p-6">
        <ErrorCard
          message={health.error ?? 'System health is unavailable right now.'}
          onRetry={refresh}
        />
      </div>
    );
  }

  const allHealthy = metrics?.services.every(s => s.status === 'healthy');
  const anyDown = metrics?.services.some(s => s.status === 'down');

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`rounded-lg p-2 ${allHealthy ? 'bg-green-500/10' : anyDown ? 'bg-red-500/10' : 'bg-amber-500/10'}`}>
            <Activity className={`h-6 w-6 ${allHealthy ? 'text-green-400' : anyDown ? 'text-red-400' : 'text-amber-400'}`} />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">System Health</h1>
            <p className="text-sm text-slate-400">
              Live status of all services — auto-refreshes every 10s
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-500">
            Last check: {lastRefresh.toLocaleTimeString()}
          </span>
          <button
            onClick={refresh}
            aria-label="Refresh system health now"
            className="p-2 rounded-lg bg-white/5 border border-white/10 text-slate-400 hover:text-white hover:bg-white/10 transition"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
      </div>

      {health.degraded && (
        <div
          role="status"
          className="rounded-xl border border-amber-500/20 bg-amber-500/10 p-3 text-sm text-amber-300"
        >
          Showing the last values that loaded ({lastRefresh.toLocaleTimeString()}) — the backend has
          not answered since.
          <button onClick={refresh} className="ml-2 font-medium underline underline-offset-2">
            Retry now
          </button>
        </div>
      )}

      {/* Overall Status Banner */}
      <div className={`rounded-xl border p-4 ${
        allHealthy
          ? 'border-green-500/20 bg-green-500/10'
          : anyDown
          ? 'border-red-500/20 bg-red-500/10'
          : 'border-amber-500/20 bg-amber-500/10'
      }`}>
        <div className="flex items-center gap-3">
          {allHealthy ? (
            <CheckCircle2 className="h-5 w-5 text-green-400" />
          ) : anyDown ? (
            <XCircle className="h-5 w-5 text-red-400" />
          ) : (
            <AlertTriangle className="h-5 w-5 text-amber-400" />
          )}
          <span className={`font-medium ${
            allHealthy ? 'text-green-400' : anyDown ? 'text-red-400' : 'text-amber-400'
          }`}>
            {allHealthy ? 'All Systems Operational' : anyDown ? 'Some Services Down' : 'Degraded Performance'}
          </span>
        </div>
      </div>

      {/* Service Cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {metrics?.services.map(service => (
          <ServiceCard key={service.name} service={service} />
        ))}
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <MetricCard
          icon={Zap}
          label="API Requests"
          value={metrics?.api.total_requests.toLocaleString() || '0'}
          sub="total"
        />
        <MetricCard
          icon={Clock}
          label="Avg Response"
          value={`${metrics?.api.avg_response_ms.toFixed(0) || '0'}ms`}
          sub="latency"
        />
        <MetricCard
          icon={HardDrive}
          label="Storage"
          value={`${((metrics?.storage.total_mb || 0) + (metrics?.storage.sessions_mb || 0)).toFixed(1)}MB`}
          sub="used"
        />
        <MetricCard
          icon={Database}
          label="DB Connections"
          value={`${metrics?.database.connections || 0}/${metrics?.database.max_connections || 100}`}
          sub="active"
        />
      </div>

      {/* Storage Breakdown */}
      <div className="rounded-xl border border-white/10 bg-white/5 p-6">
        <h2 className="mb-4 text-lg font-semibold text-white">Storage Usage</h2>
        <div className="space-y-3">
          <StorageBar label="Session Data" used={metrics?.storage.sessions_mb || 0} max={500} color="bg-cyan-500" />
          <StorageBar label="YOLO Models" used={metrics?.storage.models_mb || 0} max={10} color="bg-purple-500" />
          <StorageBar label="Recordings" used={metrics?.storage.recordings_mb || 0} max={1000} color="bg-amber-500" />
        </div>
      </div>

      {/* Enterprise Monitoring */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <CacheStatsCard stats={health.data?.cache} />
        <QueryStatsCard stats={health.data?.queries} />
        <RecoveryStatsCard stats={health.data?.recovery} />
        <LogStatsCard stats={health.data?.logs} />
      </div>
    </div>
  );
}

function ServiceCard({ service }: { service: ServiceHealth }) {
  const statusColors = {
    healthy: 'border-green-500/20 bg-green-500/5',
    degraded: 'border-amber-500/20 bg-amber-500/5',
    down: 'border-red-500/20 bg-red-500/5',
  };
  const statusText = {
    healthy: 'text-green-400',
    degraded: 'text-amber-400',
    down: 'text-red-400',
  };
  const statusDot = {
    healthy: 'bg-green-400',
    degraded: 'bg-amber-400',
    down: 'bg-red-400',
  };

  return (
    <div className={`rounded-xl border p-4 ${statusColors[service.status]}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className={`h-2 w-2 rounded-full ${statusDot[service.status]}`} />
          <h3 className="font-medium text-white">{service.name}</h3>
        </div>
        <span className={`text-xs font-medium ${statusText[service.status]}`}>
          {service.status.toUpperCase()}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div>
          <span className="text-slate-500">Port</span>
          <p className="font-mono text-slate-300">{service.port}</p>
        </div>
        <div>
          <span className="text-slate-500">Latency</span>
          <p className="font-mono text-slate-300">{service.latency_ms > 0 ? `${service.latency_ms}ms` : '-'}</p>
        </div>
        <div>
          <span className="text-slate-500">Uptime</span>
          <p className="font-mono text-slate-300">{service.uptime}</p>
        </div>
        <div>
          <span className="text-slate-500">Last Check</span>
          <p className="font-mono text-slate-300">{new Date(service.last_check).toLocaleTimeString()}</p>
        </div>
      </div>
    </div>
  );
}

function MetricCard({ icon: Icon, label, value, sub }: {
  icon: any; label: string; value: string; sub: string;
}) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/5 p-4">
      <Icon className="mb-2 h-4 w-4 text-slate-500" />
      <p className="text-sm text-slate-400">{label}</p>
      <p className="text-xl font-bold text-white">{value}</p>
      <p className="text-xs text-slate-500">{sub}</p>
    </div>
  );
}

function StorageBar({ label, used, max, color }: {
  label: string; used: number; max: number; color: string;
}) {
  const pct = Math.min(100, (used / max) * 100);
  return (
    <div>
      <div className="flex items-center justify-between text-xs mb-1">
        <span className="text-slate-400">{label}</span>
        <span className="text-slate-500">{used.toFixed(1)}MB / {max}MB</span>
      </div>
      <div className="h-2 rounded-full bg-white/10">
        <div className={`h-full rounded-full ${color} transition-all`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

// ── Enterprise Monitoring Cards ──────────────────────────

function CacheStatsCard({ stats }: { stats?: any }) {

  return (
    <div className="rounded-xl border border-white/10 bg-white/5 p-5">
      <div className="flex items-center gap-2 mb-3">
        <Gauge className="h-4 w-4 text-cyan-400" />
        <h3 className="font-medium text-white">Response Cache</h3>
      </div>
      {stats ? (
        <div className="space-y-2 text-sm">
          <div className="flex justify-between"><span className="text-slate-400">Hit Rate</span><span className="text-white font-mono">{stats.hit_rate_percent || 0}%</span></div>
          <div className="flex justify-between"><span className="text-slate-400">Entries</span><span className="text-white font-mono">{stats.entries || 0}/{stats.max_entries || 500}</span></div>
          <div className="flex justify-between"><span className="text-slate-400">Hits</span><span className="text-green-400 font-mono">{stats.hits || 0}</span></div>
          <div className="flex justify-between"><span className="text-slate-400">Misses</span><span className="text-amber-400 font-mono">{stats.misses || 0}</span></div>
        </div>
      ) : (
        <p className="text-xs text-slate-500">Loading...</p>
      )}
    </div>
  );
}

function QueryStatsCard({ stats }: { stats?: any }) {

  return (
    <div className="rounded-xl border border-white/10 bg-white/5 p-5">
      <div className="flex items-center gap-2 mb-3">
        <Database className="h-4 w-4 text-purple-400" />
        <h3 className="font-medium text-white">Query Performance</h3>
      </div>
      {stats ? (
        <div className="space-y-2 text-sm">
          <div className="flex justify-between"><span className="text-slate-400">Total Queries</span><span className="text-white font-mono">{stats.total_queries || 0}</span></div>
          <div className="flex justify-between"><span className="text-slate-400">Slow Queries</span><span className={`font-mono ${(stats.slow_queries || 0) > 0 ? 'text-amber-400' : 'text-green-400'}`}>{stats.slow_queries || 0}</span></div>
          <div className="flex justify-between"><span className="text-slate-400">Avg Latency</span><span className="text-white font-mono">{stats.avg_query_ms || 0}ms</span></div>
          <div className="flex justify-between"><span className="text-slate-400">Threshold</span><span className="text-slate-500 font-mono">{stats.slow_threshold_ms || 100}ms</span></div>
        </div>
      ) : (
        <p className="text-xs text-slate-500">Loading...</p>
      )}
    </div>
  );
}

function RecoveryStatsCard({ stats }: { stats?: any }) {

  return (
    <div className="rounded-xl border border-white/10 bg-white/5 p-5">
      <div className="flex items-center gap-2 mb-3">
        <HeartPulse className="h-4 w-4 text-green-400" />
        <h3 className="font-medium text-white">Auto-Recovery</h3>
      </div>
      {stats ? (
        <div className="space-y-2 text-sm">
          <div className="flex justify-between"><span className="text-slate-400">Status</span><span className={`font-medium ${stats.enabled ? 'text-green-400' : 'text-red-400'}`}>{stats.enabled ? 'Enabled' : 'Disabled'}</span></div>
          <div className="flex justify-between"><span className="text-slate-400">Check Interval</span><span className="text-white font-mono">{stats.check_interval_seconds || 30}s</span></div>
          {stats.services && Object.entries(stats.services).map(([name, svc]: [string, any]) => (
            <div key={name} className="flex justify-between">
              <span className="text-slate-400 capitalize">{name}</span>
              <span className={`font-mono text-xs ${svc.status === 'healthy' ? 'text-green-400' : svc.status === 'down' ? 'text-red-400' : 'text-amber-400'}`}>{svc.status}</span>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-xs text-slate-500">Loading...</p>
      )}
    </div>
  );
}

function LogStatsCard({ stats }: { stats?: any }) {

  return (
    <div className="rounded-xl border border-white/10 bg-white/5 p-5">
      <div className="flex items-center gap-2 mb-3">
        <FileText className="h-4 w-4 text-amber-400" />
        <h3 className="font-medium text-white">Logging</h3>
      </div>
      {stats ? (
        <div className="space-y-2 text-sm">
          <div className="flex justify-between"><span className="text-slate-400">Level</span><span className="text-white font-mono">{stats.level || 'INFO'}</span></div>
          <div className="flex justify-between"><span className="text-slate-400">Format</span><span className="text-white font-mono">{stats.json_format ? 'JSON' : 'Text'}</span></div>
          {stats.files && Object.entries(stats.files).map(([name, file]: [string, any]) => (
            <div key={name} className="flex justify-between">
              <span className="text-slate-400 font-mono text-xs">{name}</span>
              <span className="text-white font-mono text-xs">{file.size_mb || 0}MB</span>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-xs text-slate-500">Loading...</p>
      )}
    </div>
  );
}
