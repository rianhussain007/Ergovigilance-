import { useState, useEffect, useRef, useCallback } from 'react';
import { VideoOff, Maximize, Minimize, Camera as Snapshot, Monitor, Activity, FileText, ShieldAlert, Eye, EyeOff } from 'lucide-react';
import { useToast } from '@/src/hooks/useToast';
import { getStoredToken } from '@/src/auth/AuthContext';

interface CameraPanelProps {
  status: string;
  workerName: string;
  task?: string;
  /** Register the internal frame-capture handler so sibling controls (e.g. the
   *  Live Monitoring telemetry sidebar) can trigger a screenshot. */
  onCaptureReady?: (fn: () => void) => void;
}

export function CameraPanel({ status, workerName, task, onCaptureReady }: CameraPanelProps) {
  const [fps, setFps] = useState(29.97);
  const [streamLoading, setStreamLoading] = useState(true);
  const [streamError, setStreamError] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const [showOverlay, setShowOverlay] = useState(true);
  const imgRef = useRef<HTMLImageElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const { addToast } = useToast();
  const isActive = status === 'active';

  useEffect(() => {
    if (!isActive) return;
    const interval = setInterval(() => setFps(29 + Math.random() * 2), 2000);
    return () => clearInterval(interval);
  }, [isActive]);

  useEffect(() => {
    setStreamLoading(true);
    setStreamError(false);
  }, [isActive, showOverlay]);

  useEffect(() => {
    if (!isActive || streamError) return;
    let checkId: ReturnType<typeof setInterval>;
    let attempts = 0;
    const check = () => {
      const img = imgRef.current;
      attempts++;
      if (img && (img.naturalWidth > 0 || img.complete)) {
        setStreamLoading(false);
        clearInterval(checkId);
      }
      if (attempts > 50) {
        setStreamLoading(false);
        clearInterval(checkId);
      }
    };
    checkId = setInterval(check, 200);
    return () => clearInterval(checkId);
  }, [isActive, streamError]);

  useEffect(() => {
    const onFsChange = () => setFullscreen(!!document.fullscreenElement);
    document.addEventListener('fullscreenchange', onFsChange);
    return () => document.removeEventListener('fullscreenchange', onFsChange);
  }, []);

  const toggleFullscreen = useCallback(() => {
    if (!containerRef.current) return;
    if (document.fullscreenElement) {
      document.exitFullscreen();
    } else {
      containerRef.current.requestFullscreen();
    }
  }, []);

  const handleCapture = useCallback(() => {
    const img = imgRef.current;
    if (!img || !img.complete || img.naturalWidth === 0) {
      addToast('warning', 'No frame available', 'The camera stream is not ready yet.');
      return;
    }
    const canvas = document.createElement('canvas');
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.drawImage(img, 0, 0);
    canvas.toBlob((blob) => {
      if (!blob) return;
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `capture-${Date.now()}.png`;
      a.click();
      URL.revokeObjectURL(url);
      addToast('success', 'Screenshot captured', `Frame saved as capture-${Date.now()}.png`);
    }, 'image/png');
  }, [addToast]);

  // Publish the capture handler to parent (sidebar Capture button).
  useEffect(() => {
    onCaptureReady?.(handleCapture);
  }, [handleCapture, onCaptureReady]);

  const showStream = isActive && !streamError;
  const showPlaceholder = !isActive || streamError || streamLoading;
  const streamToken = getStoredToken();
  const overlayParam = showOverlay ? '' : '&overlay=false';
  const streamSrc = streamToken
    ? `/video/feed?token=${encodeURIComponent(streamToken)}${overlayParam}`
    : `/video/feed${overlayParam ? '?overlay=false' : ''}`;

  const toggleOverlay = useCallback(() => {
    setShowOverlay((prev) => !prev);
  }, []);
  const showComingSoon = (label: string) => {
    addToast('info', `${label} coming soon`, 'This control is a visual placeholder until backend support is connected.');
  };

  return (
    <div ref={containerRef} className="bg-[#070b10] border border-cyan-400/15 rounded-lg overflow-hidden relative group shadow-[0_0_0_1px_rgba(34,211,238,0.04),0_24px_70px_rgba(0,0,0,0.45)]">
      <div className="absolute inset-0 z-10 pointer-events-none bg-[linear-gradient(180deg,rgba(34,211,238,0.06),transparent_26%,rgba(0,0,0,0.25)),linear-gradient(90deg,rgba(255,255,255,0.035)_1px,transparent_1px),linear-gradient(180deg,rgba(255,255,255,0.025)_1px,transparent_1px)] bg-[size:100%_100%,44px_44px,44px_44px]" />
      <div className="absolute top-md left-md z-20 flex flex-col gap-sm">
        <span className="font-label-caps text-label-caps bg-black/55 backdrop-blur-md px-md py-sm rounded border border-cyan-400/20 text-cyan-100 tracking-widest uppercase flex items-center gap-sm">
          <Monitor className="w-3.5 h-3.5 text-primary" />
          {workerName}
          <span className="text-on-surface-variant/60">*</span>
        </span>
        <span className="font-label-mono text-[10px] bg-black/45 backdrop-blur-md px-md py-xs rounded border border-white/10 text-on-surface-variant uppercase tracking-wider">
          Task: {task || 'Monitoring Session'}
        </span>
      </div>

      <div className="absolute top-md right-md z-20 flex items-center gap-sm">
        <div className="flex items-center gap-xs px-md py-sm rounded border border-cyan-400/15 backdrop-blur-md font-label-mono text-label-mono bg-black/55">
          <Activity className="w-3 h-3 text-on-surface-variant" />
          <span className="text-on-surface-variant">{fps.toFixed(1)}</span>
          <span className="text-[8px] text-on-surface-variant">FPS</span>
        </div>
        <div className={`flex items-center gap-xs px-md py-sm rounded backdrop-blur-md border font-label-mono text-label-mono ${isActive ? 'bg-green-500/10 border-green-400/35 text-green-300' : 'bg-red-500/10 border-red-500/30 text-red-400'}`}>
          <span className={`w-1.5 h-1.5 rounded-full ${isActive ? 'bg-green-400 animate-pulse' : 'bg-red-400'}`} />
          LIVE
        </div>
      </div>

      <div className="w-full aspect-video bg-black flex items-center justify-center relative overflow-hidden">
        {showStream && (
          <img
            ref={imgRef}
            src={streamSrc}
            alt="Live camera feed"
            className="absolute inset-0 w-full h-full object-cover contrast-[1.08] saturate-[0.95]"
            onError={() => { setStreamError(true); setStreamLoading(false); }}
          />
        )}
        <div className="absolute inset-x-0 bottom-0 z-10 h-24 pointer-events-none bg-gradient-to-t from-black/70 via-black/15 to-transparent" />
        {showPlaceholder && (
          <div className="relative z-10 flex flex-col items-center gap-md text-on-surface-variant">
            <VideoOff className="w-12 h-12 opacity-40" />
            {isActive ? (
              <span className="text-body-sm">Waiting for camera...</span>
            ) : (
              <span className="text-body-sm">Camera Offline</span>
            )}
          </div>
        )}
      </div>

      <div className="flex items-center justify-between px-md py-sm bg-black/70 border-t border-cyan-400/15">
        <div className="flex items-center gap-sm min-w-0">
          <span className="font-label-mono text-[10px] text-cyan-200 uppercase tracking-widest">{showOverlay ? 'Skeleton' : 'Raw'} Feed</span>
          <span className="hidden sm:inline text-[10px] text-on-surface-variant/60 truncate">{showOverlay ? 'Pose skeleton from live camera landmarks' : 'Raw video without overlay'}</span>
        </div>
        <div className="flex items-center gap-xs">
          <button
            type="button"
            onClick={toggleOverlay}
            className={`flex items-center gap-xs px-md py-sm rounded border text-[10px] font-medium uppercase tracking-wider transition-colors ${
              showOverlay
                ? 'border-cyan-400/40 bg-cyan-400/10 text-cyan-200'
                : 'border-white/10 bg-white/[0.03] text-on-surface-variant hover:text-cyan-100 hover:border-cyan-400/25'
            }`}
            title={showOverlay ? 'Hide skeleton overlay' : 'Show skeleton overlay'}
          >
            {showOverlay ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
            {showOverlay ? 'Skeleton' : 'Raw'}
          </button>
          <ActionButton title="Capture" onClick={handleCapture} icon={Snapshot} />
          <PlaceholderButton title="Log" onClick={() => showComingSoon('Log')} icon={FileText} />
          <ActionButton title={fullscreen ? 'Exit Fullscreen' : 'Fullscreen'} onClick={toggleFullscreen} icon={fullscreen ? Minimize : Maximize} />
        </div>
      </div>
    </div>
  );
}

function ActionButton({ title, onClick, icon: Icon }: { title: string; onClick: () => void; icon: typeof Snapshot }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="p-sm rounded border border-white/10 bg-white/[0.03] text-on-surface-variant hover:text-cyan-100 hover:border-cyan-400/25 transition-colors"
      title={title}
    >
      <Icon className="w-4 h-4" />
    </button>
  );
}

function PlaceholderButton({ title, onClick, icon: Icon }: { title: string; onClick: () => void; icon: typeof Snapshot }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="p-sm rounded border border-white/10 bg-white/[0.03] text-on-surface-variant hover:text-cyan-100 hover:border-cyan-400/25 transition-colors relative"
      title={`${title} - coming soon`}
    >
      <Icon className="w-4 h-4" />
      <span className="absolute -top-1 -right-1 text-[8px] leading-none text-on-surface-variant/60">*</span>
    </button>
  );
}
