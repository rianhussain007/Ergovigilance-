import React, { useState, useEffect, useMemo } from 'react';
import { Camera, Eye, EyeOff, Monitor, VideoOff, AlertTriangle, ChevronRight, Users, Shield } from 'lucide-react';
import { useNavigate } from 'react-router';
import { SectionHeader, LoadingCard, ErrorCard, EmptyState } from '@/src/components/common';
import { getCameras } from '@/src/services/dashboardService';
import { apiFetch } from '@/src/services/apiClient';
import { getStoredToken } from '@/src/auth/AuthContext';
import type { CameraInfo } from '@/src/types/api';

const riskColors: Record<string, string> = { low: 'text-green-400', moderate: 'text-orange-400', high: 'text-red-400' };
const riskDots: Record<string, string> = { low: 'bg-green-500', moderate: 'bg-orange-500', high: 'bg-red-500' };
const riskBadge: Record<string, string> = {
  low: 'bg-green-500/15 text-green-700 dark:text-green-400 border-green-500/30',
  moderate: 'bg-orange-500/15 text-orange-700 dark:text-orange-400 border-orange-500/30',
  high: 'bg-red-500/15 text-red-700 dark:text-red-400 border-red-500/30',
};

interface Alert {
  id: string;
  title: string;
  severity: string;
  state: string;
  message: string;
  created_at: string;
  session_id: string;
}

interface StationRisk {
  camera_id: string;
  camera_name: string;
  risk_level: string;
  risk_score: number;
  task: string;
  worker: string;
  person_detected: boolean;
  fps: number;
  status: string;
}

function CameraTile({ cam }: { cam: CameraInfo }) {
  const [feedError, setFeedError] = useState(false);
  const [feedLoaded, setFeedLoaded] = useState(false);
  const [showOverlay, setShowOverlay] = useState(true);
  const token = getStoredToken();
  const overlayParam = showOverlay ? '' : '&overlay=false';
  const feedSrc = `/video/feed?camera_id=${encodeURIComponent(cam.id)}${token ? `&token=${encodeURIComponent(token)}` : ''}${overlayParam}`;

  // Only attempt live feed for streaming cameras (not available/idle)
  const isStreaming = cam.status === 'streaming';
  const showFeed = isStreaming && !feedError;

  return (
    <div className={`relative rounded-xl overflow-hidden border group ${isStreaming ? 'bg-black border-outline-variant' : 'bg-surface-container border-outline-variant/50'}`}>
      <div className={`aspect-[4/3] relative ${isStreaming ? 'bg-gradient-to-br from-surface-container-lowest via-surface-container to-surface-container-low' : 'bg-surface-container-lowest'}`}>
        {showFeed && (
          <img
            src={feedSrc}
            alt={cam.name}
            className={`absolute inset-0 w-full h-full object-cover transition-opacity duration-500 ${feedLoaded ? 'opacity-100' : 'opacity-0'}`}
            onLoad={() => { setFeedLoaded(true); setFeedError(false); }}
            onError={() => { setFeedError(true); setFeedLoaded(false); }}
          />
        )}

        {/* Skeleton / idle placeholder */}
        {!showFeed && (
          <div className="absolute inset-0 flex items-center justify-center">
            {isStreaming ? (
              <svg viewBox="0 0 200 280" className="w-24 h-32 md:w-28 md:h-36 opacity-20">
                <circle cx="100" cy="30" r="18" fill="none" stroke="#60a5fa" strokeWidth="1.5" />
                <line x1="100" y1="48" x2="100" y2="130" stroke="#60a5fa" strokeWidth="2" />
                <line x1="100" y1="75" x2="65" y2="100" stroke="#60a5fa" strokeWidth="1.5" />
                <line x1="100" y1="75" x2="135" y2="100" stroke="#60a5fa" strokeWidth="1.5" />
                <line x1="100" y1="130" x2="75" y2="200" stroke="#60a5fa" strokeWidth="2" />
                <line x1="100" y1="130" x2="125" y2="200" stroke="#60a5fa" strokeWidth="2" />
                <line x1="75" y1="200" x2="60" y2="260" stroke="#60a5fa" strokeWidth="1.5" />
                <line x1="125" y1="200" x2="140" y2="260" stroke="#60a5fa" strokeWidth="1.5" />
              </svg>
            ) : (
              <div className="flex flex-col items-center gap-md opacity-40">
                <Camera className="w-10 h-10 text-on-surface-variant" strokeWidth={1.5} />
                <div className="text-center">
                  <p className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Available</p>
                  <p className="text-[8px] text-on-surface-variant/60 mt-0.5">Not currently monitoring</p>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Top-right overlay */}
        <div className="absolute top-2 left-2 right-2 flex items-center justify-between pointer-events-none">
          <div className="flex items-center gap-1.5">
            {cam.recording && <div className="flex items-center gap-1 bg-red-500/20 px-1.5 py-0.5 rounded"><div className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" /><span className="text-[8px] font-bold text-red-400">REC</span></div>}
            {cam.status === 'available' && <div className="flex items-center gap-1 bg-surface-container-highest/80 px-1.5 py-0.5 rounded"><span className="text-[8px] font-bold text-on-surface-variant uppercase tracking-widest">Idle</span></div>}
          </div>
          <div className="flex items-center gap-1.5">
            {showFeed && (
              <button
                type="button"
                onClick={() => setShowOverlay((prev) => !prev)}
                className="pointer-events-auto flex items-center gap-1 rounded border border-white/10 bg-black/50 px-1.5 py-0.5 backdrop-blur-sm text-white/70 transition-colors hover:border-cyan-400/30 hover:text-cyan-200"
                title={showOverlay ? 'Hide skeleton overlay' : 'Show skeleton overlay'}
              >
                {showOverlay ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
                <span className="text-[8px] font-bold uppercase tracking-wider">{showOverlay ? 'Skel' : 'Raw'}</span>
              </button>
            )}
            <span className="text-[8px] font-label-mono text-white/40 bg-black/40 px-1 py-0.5 rounded">{cam.fps} FPS</span>
          </div>
        </div>

        {/* Bottom overlay */}
        <div className="absolute bottom-0 left-0 right-0">
          <div className={`backdrop-blur-sm rounded-lg px-2 py-1.5 mx-1 mb-1 ${isStreaming ? 'bg-black/60' : 'bg-surface-container-higher/80'}`}>
            <p className="text-[10px] font-bold text-on-surface truncate">{cam.name}</p>
            <div className="flex items-center justify-between mt-0.5">
              <span className="text-[8px] text-on-surface-variant truncate">{cam.worker || 'No active session'}</span>
              <span className={`text-[8px] font-bold uppercase ${isStreaming ? riskColors[cam.risk] : 'text-on-surface-variant/40'}`}>{cam.status === 'streaming' ? cam.risk : '—'}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function MultiCameraView() {
  const navigate = useNavigate();
  const [cameras, setCameras] = useState<CameraInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [gridSize, setGridSize] = useState<'2x2' | '3x3'>('3x3');
  const [stationRisks, setStationRisks] = useState<StationRisk[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);

  // Fetch cameras
  useEffect(() => {
    let cancelled = false;
    const fetchCameras = async () => {
      try {
        const data = await getCameras();
        if (!cancelled) { setCameras(data); setError(null); }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load cameras');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchCameras();
    const interval = setInterval(fetchCameras, 30000);
    return () => { cancelled = true; clearInterval(interval); };
  }, []);

  // Fetch live status for each camera (risk ranking)
  useEffect(() => {
    let cancelled = false;
    const fetchRisks = async () => {
      try {
        const risks: StationRisk[] = [];
        for (const cam of cameras) {
          if (cam.status !== 'streaming') continue;
          try {
            const res = await apiFetch(`/api/live/status?camera_id=${cam.id}`);
            if (res.ok) {
              const data = await res.json();
              risks.push({
                camera_id: cam.id,
                camera_name: cam.name,
                risk_level: data.risk_level || 'low',
                risk_score: data.risk_score || 0,
                task: data.task || 'Unknown',
                worker: cam.worker || 'Unassigned',
                person_detected: data.person_detected || false,
                fps: data.fps || 0,
                status: cam.status,
              });
            }
          } catch { /* camera might not have live endpoint */ }
        }
        if (!cancelled) setStationRisks(risks);
      } catch { /* ignore */ }
    };
    if (cameras.length > 0) fetchRisks();
    const interval = setInterval(fetchRisks, 10000);
    return () => { cancelled = true; clearInterval(interval); };
  }, [cameras]);

  // Fetch active alerts
  useEffect(() => {
    let cancelled = false;
    const fetchAlerts = async () => {
      try {
        const res = await apiFetch('/api/alerts?state=ACTIVE');
        if (res.ok) {
          const data = await res.json();
          if (!cancelled) setAlerts(data.alerts || data || []);
        }
      } catch { /* ignore */ }
    };
    fetchAlerts();
    const interval = setInterval(fetchAlerts, 15000);
    return () => { cancelled = true; clearInterval(interval); };
  }, []);

  // Sort cameras by risk level (HIGH first)
  const sortedByRisk = useMemo(() => {
    const riskOrder: Record<string, number> = { high: 0, moderate: 1, low: 2 };
    return [...stationRisks].sort((a, b) =>
      (riskOrder[a.risk_level] ?? 3) - (riskOrder[b.risk_level] ?? 3)
    );
  }, [stationRisks]);

  const highRiskCount = stationRisks.filter(r => r.risk_level === 'high').length;
  const moderateRiskCount = stationRisks.filter(r => r.risk_level === 'moderate').length;

  if (error) return <div className="flex items-center justify-center h-full p-lg"><ErrorCard message={error} onRetry={() => { setLoading(true); setError(null); }} /></div>;

  const sourceCams = cameras;
  const gridSlots = gridSize === '3x3' ? 9 : 4;
  const displayCams = sourceCams.slice(0, gridSlots);
  const cols = gridSize === '3x3' ? 'grid-cols-2 md:grid-cols-3' : 'grid-cols-2';
  const emptySlots = Math.max(0, gridSlots - displayCams.length);

  // With a single camera the page shouldn't look empty — center the tile and
  // point at what's missing rather than scattering one small card in a grid.
  const singleCam = displayCams.length === 1;

  return (
    <div className="p-lg space-y-lg pb-32">
      <div className="flex items-center justify-between flex-wrap gap-md">
        <div>
          <h1 className="text-display-lg font-bold text-on-surface">Multi-Camera View</h1>
          <p className="text-body-sm text-on-surface-variant mt-xs">Live feeds from all connected cameras</p>
        </div>
        <div className="flex items-center gap-sm bg-surface-container rounded-lg p-xs border border-outline-variant">
          <button onClick={() => setGridSize('2x2')} className={`flex items-center gap-1 px-sm py-xs rounded text-[10px] font-bold uppercase transition-colors ${gridSize === '2x2' ? 'bg-primary text-on-primary' : 'text-on-surface-variant hover:text-on-surface'}`}>
            <Grid2x2 className="w-3.5 h-3.5" /> 2×2
          </button>
          <button onClick={() => setGridSize('3x3')} className={`flex items-center gap-1 px-sm py-xs rounded text-[10px] font-bold uppercase transition-colors ${gridSize === '3x3' ? 'bg-primary text-on-primary' : 'text-on-surface-variant hover:text-on-surface'}`}>
            <Grid3X3 className="w-3.5 h-3.5" /> 3×3
          </button>
        </div>
      </div>

      {loading ? (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-md">
          {Array.from({ length: 6 }).map((_, i) => <LoadingCard key={i} height="h-52" />)}
        </div>
      ) : sourceCams.length === 0 ? (
        <EmptyState title="No cameras" message="No cameras are currently connected." />
      ) : singleCam ? (
        <div className="flex flex-col items-center gap-md">
          <div className="w-full max-w-[560px]">
            <CameraTile cam={displayCams[0]} />
          </div>
          <div className="w-full max-w-[560px] flex flex-col items-center gap-sm rounded-xl border border-dashed border-outline-variant bg-surface-container-low p-lg text-center">
            <Camera className="w-8 h-8 text-on-surface-variant/50" strokeWidth={1.5} />
            <p className="text-body-sm font-medium text-on-surface">Add more cameras</p>
            <p className="text-[11px] text-on-surface-variant max-w-sm">
              Connect additional cameras to monitor more stations at once.
            </p>
          </div>
        </div>
      ) : (
        <div className={`grid ${cols} gap-md`}>
          {displayCams.map((cam) => (
            <div key={cam.id}><CameraTile cam={cam} /></div>
          ))}
          {Array.from({ length: emptySlots }).map((_, i) => (
            <div
              key={`slot-${i}`}
              className="flex flex-col items-center justify-center gap-sm rounded-xl border border-dashed border-outline-variant/60 bg-surface-container-lowest aspect-[4/3]"
            >
              <Camera className="w-8 h-8 text-on-surface-variant/40" strokeWidth={1.5} />
              <p className="text-[11px] text-on-surface-variant/80 text-center px-md">
                Add more cameras to monitor additional stations
              </p>
            </div>
          ))}
        </div>
      )}

      {/* Station Risk Ranking */}
      {sortedByRisk.length > 0 && (
        <div className="bg-white dark:bg-surface-container border border-slate-200 dark:border-outline-variant rounded-xl p-lg">
          <div className="flex items-center justify-between mb-md">
            <SectionHeader title="Station Risk Ranking" />
            <div className="flex items-center gap-sm">
              {highRiskCount > 0 && (
                <span className="flex items-center gap-1 px-2 py-1 rounded-full bg-red-500/10 border border-red-500/30 text-xs font-bold text-red-600 dark:text-red-400">
                  <AlertTriangle className="w-3 h-3" /> {highRiskCount} HIGH
                </span>
              )}
              {moderateRiskCount > 0 && (
                <span className="flex items-center gap-1 px-2 py-1 rounded-full bg-orange-500/10 border border-orange-500/30 text-xs font-bold text-orange-600 dark:text-orange-400">
                  {moderateRiskCount} MEDIUM
                </span>
              )}
            </div>
          </div>
          <div className="space-y-2">
            {sortedByRisk.map((station) => (
              <div
                key={station.camera_id}
                className="flex items-center gap-md p-3 rounded-lg border border-slate-100 dark:border-outline-variant/50 bg-slate-50/50 dark:bg-surface-container-low hover:bg-slate-100 dark:hover:bg-surface-container-higher transition-colors cursor-pointer"
                onClick={() => navigate('/monitoring')}
              >
                <div className={`w-2.5 h-10 rounded-full shrink-0 ${
                  station.risk_level === 'high' ? 'bg-red-500' :
                  station.risk_level === 'moderate' ? 'bg-orange-500' : 'bg-green-500'
                }`} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-bold text-slate-900 dark:text-white truncate">{station.camera_name}</p>
                    <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold border ${riskBadge[station.risk_level] || riskBadge.low}`}>
                      {station.risk_level.toUpperCase()}
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                    {station.worker} · {station.task} · {station.risk_score.toFixed(0)}%
                  </p>
                </div>
                <div className="text-right shrink-0">
                  <p className="text-xs font-mono text-slate-600 dark:text-slate-300">{station.fps.toFixed(0)} FPS</p>
                  <p className="text-[9px] text-slate-400 dark:text-slate-500">{station.person_detected ? 'Person detected' : 'No person'}</p>
                </div>
                <ChevronRight className="w-4 h-4 text-slate-400 dark:text-slate-500 shrink-0" />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Unified Alerts Panel */}
      {alerts.length > 0 && (
        <div className="bg-white dark:bg-surface-container border border-slate-200 dark:border-outline-variant rounded-xl p-lg">
          <SectionHeader title="Active Alerts Across All Stations" />
          <div className="space-y-2 mt-md">
            {alerts.slice(0, 8).map((alert) => {
              const isHigh = alert.severity === 'HIGH' || alert.severity === 'CRITICAL';
              return (
                <div
                  key={alert.id}
                  className="flex items-start gap-md p-3 rounded-lg border border-slate-100 dark:border-outline-variant/50 bg-slate-50/50 dark:bg-surface-container-low"
                >
                  <AlertTriangle className={`w-4 h-4 shrink-0 mt-0.5 ${
                    isHigh ? 'text-red-500 dark:text-red-400' : 'text-orange-500 dark:text-orange-400'
                  }`} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-800 dark:text-white">{alert.title}</p>
                    <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 line-clamp-1">{alert.message}</p>
                  </div>
                  <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold shrink-0 ${
                    isHigh ? 'bg-red-500/15 text-red-600 dark:text-red-400' : 'bg-orange-500/15 text-orange-600 dark:text-orange-400'
                  }`}>
                    {alert.severity}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {sourceCams.length > 0 && (
        <div className="bg-white dark:bg-surface-container border border-slate-200 dark:border-outline-variant rounded-xl p-lg">
          <SectionHeader title="Camera Summary" />
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-md mt-md">
            {(() => {
              const streaming = sourceCams.filter((c) => c.status === 'streaming');
              const avgFps = streaming.length > 0
                ? Math.round(streaming.reduce((a, c) => a + c.fps, 0) / streaming.length)
                : null;
              return [
                { label: 'Total Cameras', value: sourceCams.length, icon: Camera },
                { label: 'Streaming', value: streaming.length, icon: Camera },
                { label: 'Available', value: sourceCams.length - streaming.length, icon: Camera },
                { label: 'Avg FPS', value: avgFps !== null ? `${avgFps}` : '—', icon: Monitor },
              ];
            })().map((stat) => (
              <div key={stat.label} className="bg-surface-container-low rounded-lg p-md border border-outline-variant/50 text-center">
                <p className="text-title-lg font-bold text-on-surface">{stat.value}</p>
                <p className="text-[9px] font-bold uppercase tracking-widest text-on-surface-variant mt-1">{stat.label}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Grid2x2(props: React.SVGProps<SVGSVGElement>) {
  return <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}><rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" /><rect x="3" y="14" width="7" height="7" /><rect x="14" y="14" width="7" height="7" /></svg>;
}

function Grid3X3(props: React.SVGProps<SVGSVGElement>) {
  return <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}><rect x="3" y="3" width="5" height="5" /><rect x="9.5" y="3" width="5" height="5" /><rect x="16" y="3" width="5" height="5" /><rect x="3" y="9.5" width="5" height="5" /><rect x="9.5" y="9.5" width="5" height="5" /><rect x="16" y="9.5" width="5" height="5" /><rect x="3" y="16" width="5" height="5" /><rect x="9.5" y="16" width="5" height="5" /><rect x="16" y="16" width="5" height="5" /></svg>;
}
