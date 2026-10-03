import { useEffect, useMemo, useState } from 'react';
import { usePolledResource } from '@/src/hooks/usePolling';
import { ConfirmDialog } from '@/src/components/common';
import { motion } from 'framer-motion';
import {
  Video, Plus, Trash2, Play, Square, Wifi, WifiOff,
  AlertTriangle, RefreshCw, Camera, Radio, Activity,
  TrendingUp, TrendingDown, Minus, Shield, Clock, Zap
} from 'lucide-react';

// Field names mirror the cloud core's /cloud/cameras payload exactly. They
// used to be stale (frames_processed / persons_tracked / fps_actual / error),
// so a streaming camera rendered "0 frames" with no workers and a failing one
// showed no reason at all — nothing mapped between the two shapes.
interface CloudCamera {
  camera_id: string;
  camera_name: string;
  camera_state?: string;
  url?: string;
  is_active: boolean;
  session_id: string | null;
  frame_count?: number;
  person_count?: number;
  latest_poses?: Array<{
    track_id: number;
    risk_level: string;
    risk_score: number;
    task: string;
    confidence: number;
  }>;
  last_frame_time?: string | null;
  last_error?: string | null;
  avg_confidence?: number;
  avg_risk_score?: number;
  highest_risk?: string;
  reconnect_attempts?: number;
  uptime_seconds?: number;
  fps?: number;
}

interface CameraHealth {
  status: string;
  engine: string;
  model: string;
  device: string;
  cameras_active: number;
  cameras_configured: number;
  total_frames: number;
  avg_latency_ms: number;
  alerts_today: number;
}export default function CloudCamerasPage() {
  const [showAddModal, setShowAddModal] = useState(false);
  const [newCam, setNewCam] = useState({ id: '', name: '', url: '' });
  const [addingError, setAddingError] = useState('');
  const [pendingRemove, setPendingRemove] = useState<string | null>(null);

  // Cameras, cloud-core health and thumbnails are three polled resources
  // (audit F-UX-04): each pauses while the tab is hidden, never stacks
  // requests, retries with backoff, and carries its own timeout. These calls
  // target the cloud core through the Vite proxy, so they stay raw fetches with
  // an explicit AbortSignal.timeout — but every response is validated.
  const cameraState = usePolledResource<CloudCamera[]>(
    async () => {
      const res = await fetch('/cloud-api/cloud/cameras', { signal: AbortSignal.timeout(8000) });
      if (!res.ok) throw new Error(`Cloud cameras unavailable (HTTP ${res.status})`);
      const data = await res.json();
      return (data.cameras || []) as CloudCamera[];
    },
    { initial: [], intervalMs: 5000, label: 'Cloud cameras' },
  );
  const cameras = cameraState.data;

  const healthState = usePolledResource<any>(
    async () => {
      const res = await fetch('/cloud-api/cloud/health', { signal: AbortSignal.timeout(8000) });
      if (!res.ok) throw new Error(`Cloud core health unavailable (HTTP ${res.status})`);
      return await res.json();
    },
    { initial: null, intervalMs: 5000, requiresAuth: false, label: 'Cloud core' },
  );
  const healthStatus = healthState.data;
  const coreDown = !!healthState.error || healthState.degraded;
  const loading = cameraState.loading;

  const activeIds = useMemo(
    () => cameras.filter((c) => c.is_active).map((c) => c.camera_id),
    [cameras],
  );

  const thumbState = usePolledResource<Record<string, string>>(
    async () => {
      const next: Record<string, string> = {};
      await Promise.all(
        activeIds.map(async (id) => {
          try {
            const res = await fetch(`/cloud-api/cloud/cameras/${id}/snapshot`, {
              signal: AbortSignal.timeout(8000),
            });
            if (res.ok) next[id] = URL.createObjectURL(await res.blob());
          } catch {
            // ignore — camera may not be streaming
          }
        })
      );
      return next;
    },
    { initial: {}, intervalMs: 3000, enabled: activeIds.length > 0, label: 'Camera thumbnails' },
  );
  const thumbnails = thumbState.data;

  // Every poll mints fresh blob URLs; revoke the previous batch so a long shift
  // on this page cannot accumulate unbounded image memory.
  useEffect(() => {
    const batch = thumbState.data;
    return () => {
      Object.values(batch).forEach((url) => {
        if (url.startsWith('blob:')) URL.revokeObjectURL(url);
      });
    };
  }, [thumbState.data]);

  const addCamera = async () => {
    setAddingError('');
    try {
      const res = await fetch('/cloud-api/cloud/cameras', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newCam),
      });
      if (res.ok) {
        setShowAddModal(false);
        setNewCam({ id: '', name: '', url: '' });
        cameraState.refetch();
      } else {
        const err = await res.json();
        setAddingError(err.detail || 'Failed to add camera');
      }
    } catch {
      setAddingError('Network error. Is the cloud service running?');
    }
  };

  const stopCamera = async (cameraId: string) => {
    await fetch(`/cloud-api/cloud/cameras/${cameraId}/stop`, { method: 'POST' });
    cameraState.refetch();
  };

  // Removal asks in-app instead of window.confirm (guarded by ux_guards): the
  // native dialog is unstyleable, can be blocked in kiosk shells, and gives no
  // context about which camera is about to be deleted.
  const removeCamera = async (cameraId: string) => {
    await fetch(`/cloud-api/cloud/cameras/${cameraId}`, { method: 'DELETE' });
    cameraState.refetch();
  };

  const activeCameras = cameras.filter(c => c.is_active);
  const inactiveCameras = cameras.filter(c => !c.is_active);

  // Confidence alerts
  // Only flag low confidence when the camera is actually producing
  // frames — a dead/reconnecting stream reports 0% (no data), which is
  // not a lighting problem and must not raise a "check your angle" banner.
  const lowConfidenceCams = cameras.filter(c => c.is_active && (c.frame_count ?? 0) > 0 && c.avg_confidence !== undefined && c.avg_confidence < 0.7);
  const highRiskCams = cameras.filter(c => c.is_active && c.highest_risk === 'HIGH');

  const formatUptime = (seconds?: number) => {
    if (!seconds) return '-';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    return h > 0 ? `${h}h ${m}m` : `${m}m`;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <Radio className="w-7 h-7 text-cyan-400" />
            Cloud Cameras
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            YOLO-based monitoring via CCTV RTSP streams
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => { cameraState.refetch(); healthState.refetch(); }}
            aria-label="Refresh cameras and cloud core status"
            className="p-2 rounded-lg bg-white/5 border border-white/10 text-slate-400 hover:text-white hover:bg-white/10 transition"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
          <button
            onClick={() => setShowAddModal(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-cyan-500/20 border border-cyan-500/30 text-cyan-400 hover:bg-cyan-500/30 transition text-sm font-medium"
          >
            <Plus className="w-4 h-4" />
            Add Camera
          </button>
        </div>
      </div>

      {cameraState.error && (
        <div role="alert" className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-2 text-sm text-red-300">
          {cameraState.error} — the camera list below may be incomplete.
        </div>
      )}

      {cameraState.degraded && !cameraState.error && (
        <div role="status" className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-2 text-sm text-amber-300">
          Live refresh failed — showing the last camera snapshot that loaded. Start, stop and remove
          actions may not be reflected yet.
        </div>
      )}

      {/* Confidence & Risk Alerts */}
      {(lowConfidenceCams.length > 0 || highRiskCams.length > 0) && (
        <div className="space-y-2">
          {lowConfidenceCams.map(cam => (
            <div key={cam.camera_id} className="flex items-center gap-3 px-4 py-2 rounded-lg bg-amber-500/10 border border-amber-500/20">
              <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0" />
              <span className="text-sm text-amber-400">
                Low confidence on <strong>{cam.camera_name}</strong> ({((cam.avg_confidence || 0) * 100).toFixed(0)}%) — check camera angle and lighting
              </span>
              {cam.reconnect_attempts ? (
                <span className="ml-auto text-xs text-amber-500">Reconnecting ({cam.reconnect_attempts})</span>
              ) : null}
            </div>
          ))}
          {highRiskCams.map(cam => (
            <div key={cam.camera_id} className="flex items-center gap-3 px-4 py-2 rounded-lg bg-red-500/10 border border-red-500/20">
              <Shield className="w-4 h-4 text-red-400 flex-shrink-0" />
              <span className="text-sm text-red-400">
                High risk detected on <strong>{cam.camera_name}</strong> — review session for ergonomic intervention
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Health Card */}
      {healthStatus && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="p-4 rounded-xl bg-white/5 border border-white/10"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-6 text-sm">
              <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${healthStatus.status === 'healthy' ? 'bg-green-400' : 'bg-red-400'}`} />
                <span className="text-slate-300">{healthStatus.status === 'healthy' ? 'Service Online' : 'Service Offline'}</span>
              </div>
              <span className="text-slate-500">Engine: <span className="text-slate-300">{healthStatus.engine}</span></span>
              <span className="text-slate-500">Model: <span className="text-slate-300">{healthStatus.model}</span></span>
              <span className="text-slate-500">Device: <span className="text-slate-300">{healthStatus.device}</span></span>
              <span className="text-slate-500">
                Cameras: <span className="text-cyan-400">{healthStatus.cameras_active}</span>/{healthStatus.cameras_configured} active
              </span>
            </div>
            <div className="flex items-center gap-4 text-xs text-slate-500">
              <span className="flex items-center gap-1"><Activity className="w-3 h-3" /> {healthStatus.total_frames?.toLocaleString() || 0} frames</span>
              <span className="flex items-center gap-1"><Zap className="w-3 h-3" /> {healthStatus.avg_latency_ms?.toFixed(0) || '-'}ms</span>
              <span className="flex items-center gap-1"><AlertTriangle className="w-3 h-3" /> {healthStatus.alerts_today || 0} alerts</span>
            </div>
          </div>
        </motion.div>
      )}

      {/* Core unreachable — the empty state below would otherwise lie
          ("no cameras" when we simply cannot reach the service) */}
      {coreDown && (
        <div className="flex items-center gap-3 rounded-xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-300">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          <span>
            Cloud core unreachable — camera list unavailable. Start it:{' '}
            <code className="rounded bg-black/30 px-1">python -m uvicorn yolo_cloud.api:create_app --factory --port 8100</code>{' '}
            (see docs/DEV_START.md).
          </span>
        </div>
      )}

      {/* No cameras */}
      {!loading && cameras.length === 0 && !coreDown && (
        <div className="flex flex-col items-center justify-center py-20 px-8">
          <div className="rounded-2xl bg-white/5 border border-white/10 p-8 flex flex-col items-center text-center w-full max-w-[32rem]">
            <div className="w-20 h-20 rounded-full bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center mb-6">
              <Camera className="w-10 h-10 text-cyan-400/60" />
            </div>
            <h3 className="text-xl text-white font-semibold mb-3">No Cameras Configured</h3>
            <p className="text-slate-400 text-sm leading-relaxed mb-8 max-w-[28rem]">
              Add your factory CCTV cameras using RTSP stream URLs. The cloud service will process worker posture in real-time using YOLOv8-pose.
            </p>
            <button
              onClick={() => setShowAddModal(true)}
              className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-cyan-500/20 border border-cyan-500/30 text-cyan-400 hover:bg-cyan-500/30 transition text-sm font-medium"
            >
              <Plus className="w-5 h-5" />
              Add Your First Camera
            </button>
            <p className="text-slate-600 text-xs mt-4">
              Supports Hikvision, Dahua, Axis, and any RTSP-compatible camera
            </p>
          </div>
        </div>
      )}

      {/* Active Cameras */}
      {activeCameras.length > 0 && (
        <div>
          <h2 className="text-sm font-medium text-slate-400 uppercase tracking-wider mb-3">
            Active ({activeCameras.length})
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {activeCameras.map((cam, i) => (
              <motion.div
                key={cam.camera_id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
                className="p-4 rounded-xl bg-gradient-to-br from-white/5 to-white/[0.02] border border-cyan-500/20"
              >
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h3 className="text-white font-medium">{cam.camera_name}</h3>
                    <p className="text-xs text-slate-500 font-mono">{cam.camera_id}</p>
                  </div>
                  <div className="flex items-center gap-1">
                    <Wifi className={`w-4 h-4 ${cam.camera_state === 'streaming' ? 'text-green-400' : 'text-amber-400'}`} />
                    <span className={`text-xs ${cam.camera_state === 'streaming' ? 'text-green-400' : 'text-amber-400'}`}>
                      {(cam.camera_state || 'active').toUpperCase()}
                    </span>
                  </div>
                </div>
                {cam.last_error && (
                  <p className="text-xs text-amber-400 bg-amber-500/10 rounded px-2 py-1 mb-2">
                    {cam.last_error}
                  </p>
                )}
                {/* Live thumbnail preview */}
                {thumbnails[cam.camera_id] ? (
                  <div className="relative mb-3 rounded-lg overflow-hidden border border-white/10">
                    <img
                      src={thumbnails[cam.camera_id]}
                      alt={`${cam.camera_name} live feed`}
                      className="w-full h-32 object-contain bg-black"
                    />
                    <div className="absolute top-1 right-1 flex items-center gap-1 bg-black/60 backdrop-blur-sm px-1.5 py-0.5 rounded text-[9px]">
                      <div className="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse" />
                      <span className="text-red-300 font-bold">REC</span>
                    </div>
                    <div className="absolute bottom-1 left-1 flex items-center gap-2 bg-black/60 backdrop-blur-sm px-1.5 py-0.5 rounded text-[9px]">
                      <span className="text-white">{(cam.frame_count ?? 0).toLocaleString()} frames</span>
                      <span className="text-slate-400">|</span>
                      <span className="text-white">{cam.person_count ?? 0} workers</span>
                    </div>
                  </div>
                ) : (
                  <div className="mb-3 h-32 rounded-lg bg-black/30 border border-white/5 flex items-center justify-center">
                    <div className="text-center">
                      <Radio className={`w-6 h-6 text-slate-600 mx-auto mb-1 ${cam.camera_state === 'streaming' || cam.camera_state === 'connecting' ? 'animate-pulse' : ''}`} />
                      <p className="text-[10px] text-slate-500">
                        {cam.camera_state === 'streaming' || cam.camera_state === 'connecting'
                          ? 'Loading preview...'
                          : 'No signal — stream not receiving data'}
                      </p>
                    </div>
                  </div>
                )}
                <div className="grid grid-cols-4 gap-2 text-xs mb-3">
                  <div className="text-center p-2 rounded-lg bg-white/5">
                    <p className="text-slate-500">Frames</p>
                    <p className="text-white font-medium">{(cam.frame_count ?? 0).toLocaleString()}</p>
                  </div>
                  <div className="text-center p-2 rounded-lg bg-white/5">
                    <p className="text-slate-500">Workers</p>
                    <p className="text-white font-medium">{cam.person_count ?? 0}</p>
                  </div>
                  <div className="text-center p-2 rounded-lg bg-white/5">
                    <p className="text-slate-500">Confidence</p>
                    <p className={`font-medium ${(cam.avg_confidence || 0) >= 0.8 ? 'text-green-400' : (cam.avg_confidence || 0) >= 0.6 ? 'text-amber-400' : 'text-red-400'}`}>
                      {cam.avg_confidence ? `${(cam.avg_confidence * 100).toFixed(0)}%` : '-'}
                    </p>
                  </div>
                  <div className="text-center p-2 rounded-lg bg-white/5">
                    <p className="text-slate-500">Risk</p>
                    <p className={`font-medium ${cam.highest_risk === 'HIGH' ? 'text-red-400' : cam.highest_risk === 'MEDIUM' ? 'text-amber-400' : 'text-green-400'}`}>
                      {cam.highest_risk || '-'}
                    </p>
                  </div>
                </div>
                <div className="flex items-center justify-between text-xs text-slate-500 mb-3">
                  <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> {formatUptime(cam.uptime_seconds)}</span>
                  <span>{cam.fps ? `${cam.fps.toFixed(1)} fps` : ''}</span>
                  <span>{cam.session_id?.slice(-8) || '-'}</span>
                </div>
                <p className="text-xs text-slate-500 truncate mb-3 font-mono">{cam.url}</p>
                <div className="flex gap-2">
                  <button
                    onClick={() => stopCamera(cam.camera_id)}
                    className="flex-1 flex items-center justify-center gap-1 px-3 py-1.5 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400 text-xs hover:bg-amber-500/20 transition"
                  >
                    <Square className="w-3 h-3" /> Stop
                  </button>
                  <button
                    onClick={() => setPendingRemove(cam.camera_id)}
                    aria-label={`Remove ${cam.camera_name || cam.camera_id}`}
                    className="px-3 py-1.5 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-xs hover:bg-red-500/20 transition"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      )}

      {/* Inactive Cameras */}
      {inactiveCameras.length > 0 && (
        <div>
          <h2 className="text-sm font-medium text-slate-400 uppercase tracking-wider mb-3">
            Configured ({inactiveCameras.length})
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {inactiveCameras.map((cam, i) => (
              <motion.div
                key={cam.camera_id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
                className="p-4 rounded-xl bg-white/[0.02] border border-white/10 opacity-70"
              >
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <h3 className="text-white font-medium">{cam.camera_name}</h3>
                    <p className="text-xs text-slate-500 font-mono">{cam.camera_id}</p>
                  </div>
                  <WifiOff className="w-4 h-4 text-slate-500" />
                </div>
                {cam.last_error && (
                  <p className="text-xs text-amber-400 bg-amber-500/10 rounded px-2 py-1 mb-2">
                    {cam.last_error}
                  </p>
                )}
                {cam.reconnect_attempts ? (
                  <div className="flex items-center gap-2 text-xs text-amber-400 mb-2">
                    <RefreshCw className="w-3 h-3 animate-spin" />
                    <span>Reconnecting... (attempt {cam.reconnect_attempts})</span>
                  </div>
                ) : null}
                <p className="text-xs text-slate-500 truncate mb-3 font-mono">{cam.url}</p>
                <div className="flex gap-2">
                  <button
                    onClick={async () => {
                      await fetch(`/cloud-api/cloud/cameras/${cam.camera_id}/start`, { method: 'POST' });
                      cameraState.refetch();
                    }}
                    className="flex-1 flex items-center justify-center gap-1 px-3 py-1.5 rounded-lg bg-green-500/10 border border-green-500/20 text-green-400 text-xs hover:bg-green-500/20 transition"
                  >
                    <Play className="w-3 h-3" /> Start
                  </button>
                  <button
                    onClick={() => setPendingRemove(cam.camera_id)}
                    aria-label={`Remove ${cam.camera_name || cam.camera_id}`}
                    className="px-3 py-1.5 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-xs hover:bg-red-500/20 transition"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      )}

      {/* Add Camera Modal */}
      <ConfirmDialog
        open={pendingRemove !== null}
        destructive
        title="Remove this camera?"
        message={`${pendingRemove ?? ''} will be deleted from the cloud core. Live monitoring from this camera stops immediately; recorded sessions are unaffected.`}
        confirmLabel="Remove camera"
        onCancel={() => setPendingRemove(null)}
        onConfirm={() => {
          const id = pendingRemove;
          setPendingRemove(null);
          if (id) void removeCamera(id);
        }}
      />

      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label="Add cloud camera"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="w-full max-w-[28rem] p-6 rounded-2xl bg-surface-container border border-outline-variant shadow-2xl"
          >
            <h3 className="text-lg font-semibold text-white mb-4">Add Cloud Camera</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-xs text-slate-400 mb-1">Camera ID</label>
                <input
                  value={newCam.id}
                  onChange={e => setNewCam({ ...newCam, id: e.target.value })}
                  placeholder="e.g. assembly-line-01"
                  className="w-full px-3 py-2 rounded-lg bg-black/40 border border-white/10 text-white text-sm focus:outline-none focus:border-cyan-500"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Camera Name</label>
                <input
                  value={newCam.name}
                  onChange={e => setNewCam({ ...newCam, name: e.target.value })}
                  placeholder="e.g. Assembly Line Camera 1"
                  className="w-full px-3 py-2 rounded-lg bg-black/40 border border-white/10 text-white text-sm focus:outline-none focus:border-cyan-500"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">RTSP Stream URL</label>
                <input
                  value={newCam.url}
                  onChange={e => setNewCam({ ...newCam, url: e.target.value })}
                  placeholder="rtsp://192.168.1.100:554/stream1"
                  className="w-full px-3 py-2 rounded-lg bg-black/40 border border-white/10 text-white text-sm font-mono focus:outline-none focus:border-cyan-500"
                />
                <p className="text-xs text-slate-500 mt-1">
                  Get this from your CCTV camera settings or NVR system
                </p>
              </div>
              {addingError && (
                <p className="text-xs text-red-400 bg-red-500/10 rounded px-3 py-2">{addingError}</p>
              )}
              <div className="flex gap-3 pt-2">
                <button
                  onClick={() => setShowAddModal(false)}
                  className="flex-1 px-4 py-2 rounded-lg border border-white/10 text-slate-400 text-sm hover:bg-white/5 transition"
                >
                  Cancel
                </button>
                <button
                  onClick={addCamera}
                  disabled={!newCam.id || !newCam.url}
                  className="flex-1 px-4 py-2 rounded-lg bg-cyan-500 text-white text-sm font-medium hover:bg-cyan-400 transition disabled:opacity-50"
                >
                  Add & Start
                </button>
              </div>
            </div>
          </motion.div>
        </div>
      )}
    </div>
  );
}
