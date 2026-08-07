import React, { useState, useEffect } from 'react';
import { Camera, Monitor, VideoOff } from 'lucide-react';
import { SectionHeader, LoadingCard, ErrorCard, EmptyState } from '@/src/components/common';
import { getCameras } from '@/src/services/dashboardService';
import { getStoredToken } from '@/src/auth/AuthContext';
import { useDemo } from '@/src/demo/DemoProvider';
import { DEMO_CAMERAS } from '@/src/demo/demoConstants';
import type { CameraInfo } from '@/src/types/api';

const riskColors: Record<string, string> = { low: 'text-green-400', moderate: 'text-orange-400', high: 'text-red-400' };
const riskDots: Record<string, string> = { low: 'bg-green-500', moderate: 'bg-orange-500', high: 'bg-red-500' };

const DEMO_BANNER = 'SAMPLE DATA — Demo Camera Grid, not live feeds';

function CameraTile({ cam, demo }: { cam: CameraInfo; demo?: boolean }) {
  const [feedError, setFeedError] = useState(false);
  const [feedLoaded, setFeedLoaded] = useState(false);
  const token = getStoredToken();
  const feedSrc = `/video/feed?camera_id=${encodeURIComponent(cam.id)}${token ? `&token=${encodeURIComponent(token)}` : ''}`;

  // Only attempt live feed for streaming cameras (not available/idle)
  const isStreaming = cam.status === 'streaming';
  const showFeed = isStreaming && !demo && !feedError;

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
        {(!showFeed && !demo) && (
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

        {demo && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="bg-amber-500/20 backdrop-blur-sm px-lg py-sm rounded border border-amber-400/40">
              <p className="text-[10px] font-bold text-amber-300 uppercase tracking-widest text-center">{DEMO_BANNER}</p>
            </div>
          </div>
        )}

        {/* Top-right overlay */}
        <div className="absolute top-2 left-2 right-2 flex items-center justify-between pointer-events-none">
          <div className="flex items-center gap-1.5">
            {cam.recording && <div className="flex items-center gap-1 bg-red-500/20 px-1.5 py-0.5 rounded"><div className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" /><span className="text-[8px] font-bold text-red-400">REC</span></div>}
            {cam.status === 'available' && <div className="flex items-center gap-1 bg-surface-container-highest/80 px-1.5 py-0.5 rounded"><span className="text-[8px] font-bold text-on-surface-variant uppercase tracking-widest">Idle</span></div>}
          </div>
          <span className="text-[8px] font-label-mono text-white/40 bg-black/40 px-1 py-0.5 rounded">{cam.fps} FPS</span>
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
  const { state: demoState } = useDemo();
  const [cameras, setCameras] = useState<CameraInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [gridSize, setGridSize] = useState<'2x2' | '3x3'>('3x3');

  useEffect(() => {
    if (demoState.active) { setLoading(false); return; }
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
  }, [demoState.active]);

  if (error) return <div className="flex items-center justify-center h-full p-lg"><ErrorCard message={error} onRetry={() => { setLoading(true); setError(null); }} /></div>;

  const isDemo = demoState.active;
  const sourceCams = isDemo ? DEMO_CAMERAS : cameras;
  const displayCams = isDemo ? sourceCams : gridSize === '3x3' ? sourceCams.slice(0, 9) : sourceCams.slice(0, 4);
  const cols = gridSize === '3x3' ? 'grid-cols-2 md:grid-cols-3' : 'grid-cols-2';

  return (
    <div className="p-lg space-y-lg pb-32">
      <div className="flex items-center justify-between flex-wrap gap-md">
        <div>
          <h1 className="text-display-lg font-bold text-on-surface">Multi-Camera View</h1>
          <p className="text-body-sm text-on-surface-variant mt-xs">{isDemo ? 'Demo — simulated camera feeds' : 'Live feeds from all connected cameras'}</p>
        </div>
        {!isDemo && (
          <div className="flex items-center gap-sm bg-surface-container rounded-lg p-xs border border-outline-variant">
            <button onClick={() => setGridSize('2x2')} className={`flex items-center gap-1 px-sm py-xs rounded text-[10px] font-bold uppercase transition-colors ${gridSize === '2x2' ? 'bg-primary text-on-primary' : 'text-on-surface-variant hover:text-on-surface'}`}>
              <Grid2x2 className="w-3.5 h-3.5" /> 2×2
            </button>
            <button onClick={() => setGridSize('3x3')} className={`flex items-center gap-1 px-sm py-xs rounded text-[10px] font-bold uppercase transition-colors ${gridSize === '3x3' ? 'bg-primary text-on-primary' : 'text-on-surface-variant hover:text-on-surface'}`}>
              <Grid3X3 className="w-3.5 h-3.5" /> 3×3
            </button>
          </div>
        )}
      </div>

      {isDemo && (
        <div className="bg-amber-500/10 border border-amber-400/30 rounded-lg px-lg py-md">
          <p className="text-[11px] font-bold text-amber-300 uppercase tracking-widest text-center">{DEMO_BANNER}</p>
        </div>
      )}

      {loading ? (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-md">
          {Array.from({ length: 6 }).map((_, i) => <LoadingCard key={i} height="h-52" />)}
        </div>
      ) : sourceCams.length === 0 && !isDemo ? (
        <EmptyState title="No cameras" message="No cameras are currently connected." />
      ) : (
        <div className={`grid ${cols} gap-md`}>
          {displayCams.map((cam) => (
            <div key={cam.id}><CameraTile cam={cam} demo={isDemo} /></div>
          ))}
        </div>
      )}

      {sourceCams.length > 0 && (
        <div className="bg-surface-container border border-outline-variant rounded-xl p-lg">
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
