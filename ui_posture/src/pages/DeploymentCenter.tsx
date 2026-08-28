import { useState, useEffect, useCallback, useRef } from 'react';
import { Server, Database, Camera, Users, Settings, Activity, AlertTriangle, RefreshCw, Terminal } from 'lucide-react';
import { getDeployment } from '@/src/services/dashboardService';
import { apiFetch } from '@/src/services/apiClient';
import { ErrorCard, LoadingCard } from '@/src/components/common';
import type { DeploymentMetrics } from '@/src/types/api';

/* ── Types ────────────────────────────────────────────────────────── */

interface CameraStatus {
  id: string;
  name: string;
  status: 'active' | 'standby' | 'error';
  station: string;
  fps: number;
  worker?: string;
}

interface AuditEntry {
  timestamp: string;
  type: string;
  message: string;
  level: 'info' | 'warning' | 'error' | 'success';
}

interface SystemConfig {
  camera_refresh_ms: number;
  edge_compute_profile: string;
  system_theme_dark: boolean;
  log_verbosity: string;
}

/* ── Main Component ────────────────────────────────────────────────── */

export default function DeploymentCenter() {
  const [metrics, setMetrics] = useState<DeploymentMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cameras, setCameras] = useState<CameraStatus[]>([]);
  const [auditLog, setAuditLog] = useState<AuditEntry[]>([]);
  const [config, setConfig] = useState<SystemConfig>({
    camera_refresh_ms: 1000,
    edge_compute_profile: 'MEDIUM',
    system_theme_dark: true,
    log_verbosity: 'INFO',
  });
  const [configSaved, setConfigSaved] = useState(false);
  const mountedRef = useRef(true);
  const logEndRef = useRef<HTMLDivElement>(null);

  // Fetch deployment metrics
  const fetchData = useCallback(async () => {
    try {
      const data = await getDeployment();
      if (!mountedRef.current) return;
      setMetrics(data);
      setError(null);
    } catch (err) {
      if (!mountedRef.current) return;
      setError(err instanceof Error ? err.message : 'Failed to load metrics');
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  }, []);

  // Fetch camera statuses
  const fetchCameras = useCallback(async () => {
    try {
      const res = await apiFetch('/api/cameras');
      if (res.ok) {
        const data = await res.json();
        const camList = (data.cameras || []).map((c: any) => ({
          id: c.id,
          name: c.name || `CAM${c.id}`,
          status: c.status === 'streaming' ? 'active' : 'standby',
          station: c.station || `Station ${c.id}`,
          fps: c.fps || 0,
          worker: c.worker,
        }));
        if (mountedRef.current) setCameras(camList);
      }
    } catch { /* ignore */ }
  }, []);

  // Fetch audit trail
  const fetchAudit = useCallback(async () => {
    try {
      const res = await apiFetch('/api/audit?limit=20');
      if (res.ok) {
        const data = await res.json();
        const entries = (data.events || data || []).map((e: any) => ({
          timestamp: e.timestamp || e.created_at || '',
          type: e.action_type || e.type || 'unknown',
          message: e.details || e.message || '',
          level: e.action_type?.includes('login') ? 'info' :
                 e.action_type?.includes('alert') ? 'warning' :
                 e.action_type?.includes('error') ? 'error' : 'info',
        }));
        if (mountedRef.current) setAuditLog(entries);
      }
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    fetchData();
    fetchCameras();
    fetchAudit();
    const interval = setInterval(() => {
      fetchData();
      fetchCameras();
      fetchAudit();
    }, 15000);
    return () => { mountedRef.current = false; clearInterval(interval); };
  }, [fetchData, fetchCameras, fetchAudit]);

  // Auto-scroll audit log
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [auditLog]);

  const handleSaveConfig = async () => {
    try {
      await apiFetch('/api/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });
      setConfigSaved(true);
      setTimeout(() => setConfigSaved(false), 2000);
    } catch { /* ignore */ }
  };

  if (loading) {
    return (
      <div className="p-lg space-y-lg pb-32">
        <h1 className="text-display-lg font-bold text-slate-900 dark:text-white">Deployment Center</h1>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-lg">
          <LoadingCard height="h-64" />
          <LoadingCard height="h-64" />
          <LoadingCard height="h-64" />
          <LoadingCard height="h-64" />
        </div>
      </div>
    );
  }

  if (error || !metrics) {
    return (
      <div className="p-lg space-y-lg pb-32">
        <h1 className="text-display-lg font-bold text-slate-900 dark:text-white">Deployment Center</h1>
        <ErrorCard message={error || 'Failed to load metrics'} onRetry={() => { setLoading(true); fetchData(); }} />
      </div>
    );
  }

  const activeStations = cameras.filter(c => c.status === 'active').length;
  const totalStations = cameras.length || metrics.cameraCount;

  return (
    <div className="p-lg space-y-lg pb-32">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-display-lg font-bold text-slate-900 dark:text-white">Deployment Center</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">Under the Hood — System status and configuration</p>
        </div>
        <div className="flex items-center gap-2">
          <span className={`px-3 py-1.5 rounded-full text-xs font-bold ${
            metrics.backendStatus === 'ok' 
              ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-500/30'
              : 'bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-400 border border-red-200 dark:border-red-500/30'
          }`}>
            {metrics.backendStatus === 'ok' ? '● SYSTEM ONLINE' : '● SYSTEM ERROR'}
          </span>
        </div>
      </div>

      {/* 4-Panel Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-lg">

        {/* ── Panel 1: Multi-Cam Engine ──────────────────────────── */}
        <div className="bg-white dark:bg-[#0a0e14] border border-slate-200 dark:border-emerald-500/20 rounded-xl overflow-hidden">
          <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-200 dark:border-emerald-500/20 bg-slate-50 dark:bg-[#0d1117]">
            <Camera className="w-4 h-4 text-blue-600 dark:text-cyan-400" />
            <h2 className="text-sm font-bold text-slate-900 dark:text-white">Multi-Cam Engine</h2>
          </div>
          <div className="p-4">
            <p className="text-xs text-slate-600 dark:text-slate-400 mb-3">
              Live detection of available, integrated camera streams across the production floor. Dynamic scaling based on station count.
            </p>
            <div className="font-mono text-xs space-y-1 bg-slate-50 dark:bg-[#0d1117] rounded-lg p-3 border border-slate-200 dark:border-emerald-500/10">
              {cameras.length > 0 ? cameras.slice(0, 5).map(cam => (
                <div key={cam.id} className="flex items-center gap-2">
                  <span className="text-slate-700 dark:text-emerald-400">{cam.name}</span>
                  <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${
                    cam.status === 'active' 
                      ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-400'
                      : 'bg-slate-200 text-slate-600 dark:bg-slate-700 dark:text-slate-400'
                  }`}>
                    [{cam.status.toUpperCase()}]
                  </span>
                  <span className="text-slate-500 dark:text-slate-500">—</span>
                  <span className="text-slate-600 dark:text-slate-300">{cam.station}</span>
                </div>
              )) : (
                <div className="text-slate-500 dark:text-slate-500">No cameras detected</div>
              )}
              <div className="pt-2 mt-2 border-t border-slate-200 dark:border-emerald-500/10 text-slate-600 dark:text-slate-400">
                DEPLOYED STATIONS: <span className="text-slate-900 dark:text-white font-bold">{totalStations}</span> / SCALING FACTOR: <span className="text-slate-900 dark:text-white font-bold">1.2x</span>
              </div>
            </div>
          </div>
        </div>

        {/* ── Panel 2: Database & Inference ──────────────────────── */}
        <div className="bg-white dark:bg-[#0a0e14] border border-slate-200 dark:border-cyan-500/20 rounded-xl overflow-hidden">
          <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-200 dark:border-cyan-500/20 bg-slate-50 dark:bg-[#0d1117]">
            <Database className="w-4 h-4 text-purple-600 dark:text-cyan-400" />
            <h2 className="text-sm font-bold text-slate-900 dark:text-white">Database & Inference</h2>
          </div>
          <div className="p-4">
            <p className="text-xs text-slate-600 dark:text-slate-400 mb-3">
              {metrics.databaseEngine} architecture powered by a HistGradientBoosting model. Trained on ergonomic records for high-fidelity posture assessment.
            </p>
            <div className="font-mono text-xs space-y-1 bg-slate-50 dark:bg-[#0d1117] rounded-lg p-3 border border-slate-200 dark:border-cyan-500/10">
              <div className="text-slate-500 dark:text-slate-500">sqlite&gt; PRAGMA database_list;</div>
              <div className="text-slate-600 dark:text-slate-300">0: '{metrics.databaseEngine.toLowerCase()}.db' [RW]</div>
              <div className="pt-2 text-cyan-600 dark:text-cyan-400">&gt; MODEL STATUS: TRAINED ({metrics.registeredWorkerCount}+ RECORDS)</div>
              <div className="text-cyan-600 dark:text-cyan-400">&gt; ALGORITHM: HistGradientBoosting + RULA/REBA</div>
              <div className="text-cyan-600 dark:text-cyan-400">&gt; INFERENCE TIME: &lt;{metrics.sessionInferenceLatencyMs?.toFixed(0) || '15'}ms (EDGE COMPUTE)</div>
              <div className="text-cyan-600 dark:text-cyan-400">&gt; DB SIZE: {(metrics.databaseSizeBytes / 1024 / 1024).toFixed(1)} MB</div>
            </div>
          </div>
        </div>

        {/* ── Panel 3: Audit Trail ──────────────────────────────── */}
        <div className="bg-white dark:bg-[#0a0e14] border border-slate-200 dark:border-amber-500/20 rounded-xl overflow-hidden">
          <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-200 dark:border-amber-500/20 bg-slate-50 dark:bg-[#0d1117]">
            <Terminal className="w-4 h-4 text-amber-600 dark:text-amber-400" />
            <h2 className="text-sm font-bold text-slate-900 dark:text-white">Audit Trail</h2>
          </div>
          <div className="p-4">
            <p className="text-xs text-slate-600 dark:text-slate-400 mb-3">
              Daily admin logs tracking user logins, session starts, and system health metrics to ensure absolute operational accountability.
            </p>
            <div className="font-mono text-[11px] space-y-0.5 bg-slate-50 dark:bg-[#0d1117] rounded-lg p-3 border border-slate-200 dark:border-amber-500/10 max-h-48 overflow-y-auto">
              {auditLog.length > 0 ? auditLog.slice(0, 15).map((entry, i) => {
                const levelColor = entry.level === 'warning' ? 'text-amber-600 dark:text-amber-400' :
                                  entry.level === 'error' ? 'text-red-600 dark:text-red-400' :
                                  entry.level === 'success' ? 'text-emerald-600 dark:text-emerald-400' :
                                  'text-slate-600 dark:text-slate-400';
                return (
                  <div key={i} className={levelColor}>
                    [{entry.timestamp}] {entry.type}: {entry.message}
                  </div>
                );
              }) : (
                <div className="text-slate-500 dark:text-slate-500">No audit entries yet</div>
              )}
              <div ref={logEndRef} />
            </div>
          </div>
        </div>

        {/* ── Panel 4: Settings & Config ────────────────────────── */}
        <div className="bg-white dark:bg-[#0a0e14] border border-slate-200 dark:border-blue-500/20 rounded-xl overflow-hidden">
          <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-200 dark:border-blue-500/20 bg-slate-50 dark:bg-[#0d1117]">
            <Settings className="w-4 h-4 text-blue-600 dark:text-blue-400" />
            <h2 className="text-sm font-bold text-slate-900 dark:text-white">Settings & Config</h2>
          </div>
          <div className="p-4">
            <p className="text-xs text-slate-600 dark:text-slate-400 mb-3">
              Customizable camera refresh intervals for varying edge compute environments, and toggleable system theme constraints.
            </p>
            <div className="font-mono text-xs space-y-2 bg-slate-50 dark:bg-[#0d1117] rounded-lg p-3 border border-slate-200 dark:border-blue-500/10">
              <div className="text-slate-500 dark:text-slate-500 mb-2">[SETTINGS.CONF]</div>
              
              {/* Camera Refresh */}
              <div className="flex items-center justify-between">
                <span className="text-slate-600 dark:text-slate-400">CAMERA_REFRESH_MS:</span>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    value={config.camera_refresh_ms}
                    onChange={(e) => setConfig({ ...config, camera_refresh_ms: parseInt(e.target.value) || 1000 })}
                    className="w-20 px-2 py-0.5 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-600 rounded text-xs font-mono text-slate-900 dark:text-white text-right"
                  />
                  <span className="text-slate-500 dark:text-slate-500">(EDIT)</span>
                </div>
              </div>

              {/* Edge Compute Profile */}
              <div className="flex items-center justify-between">
                <span className="text-slate-600 dark:text-slate-400">EDGE_COMPUTE_PROFILE:</span>
                <div className="flex items-center gap-2">
                  <select
                    value={config.edge_compute_profile}
                    onChange={(e) => setConfig({ ...config, edge_compute_profile: e.target.value })}
                    className="px-2 py-0.5 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-600 rounded text-xs font-mono text-slate-900 dark:text-white"
                  >
                    <option value="LOW">LOW</option>
                    <option value="MEDIUM">MEDIUM</option>
                    <option value="HIGH">HIGH</option>
                  </select>
                  <span className="text-slate-500 dark:text-slate-500">(EDIT)</span>
                </div>
              </div>

              {/* Theme Toggle */}
              <div className="flex items-center justify-between">
                <span className="text-slate-600 dark:text-slate-400">SYSTEM_THEME_DARK:</span>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setConfig({ ...config, system_theme_dark: !config.system_theme_dark })}
                    className={`w-10 h-5 rounded-full transition-colors ${
                      config.system_theme_dark ? 'bg-blue-500' : 'bg-slate-300'
                    }`}
                  >
                    <div className={`w-4 h-4 bg-white rounded-full transition-transform mx-0.5 ${
                      config.system_theme_dark ? 'translate-x-5' : 'translate-x-0'
                    }`} />
                  </button>
                  <span className="text-slate-500 dark:text-slate-500">(TOGGLE)</span>
                </div>
              </div>

              {/* Log Verbosity */}
              <div className="flex items-center justify-between">
                <span className="text-slate-600 dark:text-slate-400">LOG_VERBOSITY:</span>
                <div className="flex items-center gap-2">
                  <select
                    value={config.log_verbosity}
                    onChange={(e) => setConfig({ ...config, log_verbosity: e.target.value })}
                    className="px-2 py-0.5 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-600 rounded text-xs font-mono text-slate-900 dark:text-white"
                  >
                    <option value="DEBUG">DEBUG</option>
                    <option value="INFO">INFO</option>
                    <option value="WARNING">WARNING</option>
                    <option value="ERROR">ERROR</option>
                  </select>
                  <span className="text-slate-500 dark:text-slate-500">(EDIT)</span>
                </div>
              </div>

              {/* Save Button */}
              <div className="pt-2 mt-2 border-t border-slate-200 dark:border-blue-500/10">
                <button
                  onClick={handleSaveConfig}
                  className={`w-full py-1.5 rounded text-xs font-bold transition-all ${
                    configSaved
                      ? 'bg-emerald-500 text-white'
                      : 'bg-blue-600 text-white hover:bg-blue-500'
                  }`}
                >
                  {configSaved ? '✓ SAVED' : 'SAVE CONFIG'}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* System Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-md">
        <StatCard icon={Server} label="Backend" value={metrics.backendStatus === 'ok' ? 'Operational' : 'Error'} status={metrics.backendStatus === 'ok' ? 'ok' : 'error'} />
        <StatCard icon={Database} label="Database" value={`${(metrics.databaseSizeBytes / 1024 / 1024).toFixed(1)} MB`} status={metrics.databaseStatus === 'ok' ? 'ok' : 'error'} />
        <StatCard icon={Camera} label="Cameras" value={`${activeStations}/${totalStations} Active`} status={activeStations > 0 ? 'ok' : 'warning'} />
        <StatCard icon={Users} label="Workers" value={`${metrics.registeredWorkerCount} Registered`} status="ok" />
      </div>
    </div>
  );
}

/* ── Stat Card ────────────────────────────────────────────────────── */

function StatCard({ icon: Icon, label, value, status }: { icon: any; label: string; value: string; status: 'ok' | 'warning' | 'error' }) {
  const statusColor = status === 'ok' ? 'text-emerald-500 dark:text-emerald-400' :
                     status === 'warning' ? 'text-amber-500 dark:text-amber-400' :
                     'text-red-500 dark:text-red-400';
  return (
    <div className="bg-white dark:bg-surface-container border border-slate-200 dark:border-outline-variant rounded-xl p-4">
      <div className="flex items-center justify-between mb-2">
        <Icon className={`w-4 h-4 ${statusColor}`} />
        <div className={`w-2 h-2 rounded-full ${status === 'ok' ? 'bg-emerald-500' : status === 'warning' ? 'bg-amber-500' : 'bg-red-500'}`} />
      </div>
      <p className="text-xs text-slate-500 dark:text-slate-400">{label}</p>
      <p className="text-sm font-bold text-slate-900 dark:text-white mt-0.5">{value}</p>
    </div>
  );
}
