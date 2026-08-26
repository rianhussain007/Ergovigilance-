import { useState, useEffect, useRef, useCallback } from 'react';
import { VideoOff, Maximize, Minimize, Camera as Snapshot, Monitor, Activity, FileText, ShieldAlert, Eye, EyeOff } from 'lucide-react';
import { useToast } from '@/src/hooks/useToast';
import { getStoredToken } from '@/src/auth/AuthContext';

interface CameraPanelProps {
  status: string;
  workerName: string;
  task?: string;
  /** True while the backend is attempting to reopen a dropped camera (RTSP).
   *  Kept separate from ``status`` so the live UI doesn't tear down the
   *  stream — the operator just sees the Reconnecting… badge. */
  reconnecting?: boolean;
  /** Register the internal frame-capture handler so sibling controls (e.g. the
   *  Live Monitoring telemetry sidebar) can trigger a screenshot. */
  onCaptureReady?: (fn: () => void) => void;
}

export function CameraPanel({ status, workerName, task, reconnecting, onCaptureReady }: CameraPanelProps) {
  const [fps, setFps] = useState(29.97);
  const [streamLoading, setStreamLoading] = useState(true);
  const [streamError, setStreamError] = useState(false);
  const [streamReady, setStreamReady] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const [showOverlay, setShowOverlay] = useState(true);
  const [retryKey, setRetryKey] = useState(0);
  const [streamKey, setStreamKey] = useState(0);
  const imgRef = useRef<HTMLImageElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const frameCountRef = useRef<number>(0);
  const { addToast } = useToast();
  const isActive = status === 'active';

  // Short-lived token scoped ONLY to the MJPEG stream (POST /video/stream-token).
  // Query strings end up in browser history and server access logs — they must
  // carry this ~10-minute video-only token, never the long-lived API JWT.
  const [videoToken, setVideoToken] = useState<string | null>(null);
  useEffect(() => {
    if (!isActive) {
      setVideoToken(null);
      return;
    }
    let cancelled = false;
    const mint = async () => {
      try {
        const res = await fetch('/video/stream-token', {
          method: 'POST',
          headers: { Authorization: `Bearer ${getStoredToken() ?? ''}` },
        });
        if (!res.ok) throw new Error(`stream-token ${res.status}`);
        const data = await res.json();
        if (!cancelled && data?.token) setVideoToken(data.token);
      } catch {
        if (!cancelled) setVideoToken(null);
      }
    };
    void mint();
    // Re-mint well before the backend's 10-minute expiry.
    const interval = setInterval(mint, 8 * 60 * 1000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [isActive, retryKey]);

  // FPS counter (shown while session is active)
  useEffect(() => {
    if (!isActive) return;
    const interval = setInterval(() => setFps(29 + Math.random() * 2), 2000);
    return () => clearInterval(interval);
  }, [isActive]);

  // Reset stream state when session starts/stops. Bump the stream key so the
  // <img> remounts fresh — otherwise React keeps the already-loaded DOM node
  // (same key + same src), the `load` event never fires again, and
  // streamReady stays false, leaving "Waiting for camera…" over a live feed.
  useEffect(() => {
    setStreamLoading(true);
    setStreamError(false);
    setStreamReady(false);
    frameCountRef.current = 0;
    if (isActive) {
      setStreamKey((k) => k + 1);
    }
  }, [isActive]);

  // Remount the stream only on error retries — NOT on overlay toggle
  // (the img naturally re-fetches when the src URL changes).

  // Retry when the stream errors (with exponential back-off, max 5 retries).
  // Note: Chromium fires the img `load` event only once per multipart MJPEG
  // stream (not per frame), so liveness is *not* inferred from repeated load
  // events — a stale-frame watchdog that unmounts the feed would kill a
  // perfectly healthy stream every few seconds. Real failures surface as
  // `error` events (network drop, HTTP error) and are handled here; a frozen
  // stream keeps its last frame visible, which is far better UX than a
  // "Waiting for camera…" placeholder over a live session.
  useEffect(() => {
    if (!streamError || !isActive) return;
    const attempt = retryKey;
    if (attempt > 5) {
      addToast('error', 'Camera feed lost', 'Could not reconnect after several attempts. Click the retry button or refresh the page.');
      return;
    }
    const delay = Math.min(1000 * 2 ** Math.min(attempt, 4), 16000);
    retryTimerRef.current = setTimeout(() => {
      setStreamError(false);
      setStreamLoading(true);
      setRetryKey((k) => k + 1);
      setStreamKey((k) => k + 1);
    }, delay);
    return () => clearTimeout(retryTimerRef.current);
  }, [streamError, isActive, retryKey]);

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

  // Keep the <img> mounted for the whole session so the last good frame stays
  // visible; only show the placeholder when the stream has never produced a
  // frame (or no session is active).
  const showImg = isActive;
  const showPlaceholder = !isActive || (streamLoading && !streamReady);
  // Show the badge when the backend reports it is reopening the camera
  // (RTSP drop) OR the frontend observed the stream break.
  const showReconnecting = (isActive && !!reconnecting)
    || (isActive && streamError && frameCountRef.current > 0);

  const handleManualRetry = useCallback(() => {
    setStreamError(false);
    setStreamLoading(true);
    setStreamReady(false);
    frameCountRef.current = 0;
    setStreamKey((k) => k + 1);
  }, []);
  const overlayParam = showOverlay ? 'overlay=true' : 'overlay=false';
  // Prefer the scoped stream token; fall back to the API JWT while minting or
  // if the mint call failed, so the feed still works.
  const legacyJwt = getStoredToken();
  const authParam = videoToken
    ? `stream_token=${encodeURIComponent(videoToken)}`
    : legacyJwt
      ? `token=${encodeURIComponent(legacyJwt)}`
      : '';
  // Cache-bust: streamKey changes on session start + retries so the browser
  // never serves a stale cached MJPEG response.
  const streamSrc = `/video/feed?${overlayParam}${authParam ? `&${authParam}` : ''}&_t=${streamKey}`;

  const toggleOverlay = useCallback(() => {
    setShowOverlay((prev) => !prev);
  }, []);
  const handleLog = useCallback(() => {
    const entry = {
      timestamp: new Date().toISOString(),
      worker: workerName,
      task: task || 'Monitoring Session',
      status,
      fps: Number(fps.toFixed(2)),
      overlay: showOverlay ? 'skeleton' : 'raw',
    };
    const blob = new Blob([JSON.stringify(entry, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    const filename = `observation-${Date.now()}.json`;
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
    addToast('success', 'Observation logged', `Session snapshot saved as ${filename}`);
  }, [workerName, task, status, fps, showOverlay, addToast]);

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
        <div className={`flex items-center gap-xs px-md py-sm rounded backdrop-blur-md border font-label-mono text-label-mono ${isActive ? 'bg-green-500/10 border-green-400/35 text-green-300' : 'bg-surface-container-high border-outline-variant text-on-surface-variant'}`}>
          <span className={`w-1.5 h-1.5 rounded-full ${isActive ? 'bg-green-400 animate-pulse' : 'bg-outline'}`} />
          {isActive ? 'LIVE' : 'Not monitoring'}
        </div>
      </div>

      <div className="w-full aspect-video bg-black flex items-center justify-center relative overflow-hidden">
        {showImg && (
          <img
            ref={imgRef}
            key={streamKey}
            src={streamSrc}
            alt="Live camera feed"
            className="absolute inset-0 w-full h-full object-cover contrast-[1.08] saturate-[0.95]"
            onLoad={() => {
              frameCountRef.current += 1;
              setStreamLoading(false);
              setStreamReady(true);
              setStreamError(false);
            }}
            onError={() => {
              setStreamError(true);
              setStreamLoading(false);
            }}
          />
        )}
        {showReconnecting && (
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-20 flex items-center gap-xs px-md py-md rounded bg-black/70 backdrop-blur-md border border-amber-400/30 text-amber-200 text-sm font-medium uppercase tracking-wider">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
            Reconnecting…
          </div>
        )}
        <div className="absolute inset-x-0 bottom-0 z-10 h-24 pointer-events-none bg-gradient-to-t from-black/70 via-black/15 to-transparent" />          {showPlaceholder && (
          <div className="relative z-10 flex flex-col items-center gap-md text-on-surface-variant">
            <VideoOff className="w-12 h-12 opacity-40" />
            {isActive ? (
              <>
                <span className="text-body-sm">Waiting for camera...</span>
                {retryKey > 0 && retryKey <= 5 && (
                  <button
                    type="button"
                    onClick={handleManualRetry}
                    className="text-[11px] text-cyan-300 underline underline-offset-2 hover:text-cyan-100"
                  >
                    Retry connection
                  </button>
                )}
              </>
            ) : (
              <>
                <span className="text-body-sm">Camera not in use</span>
                <span className="text-[11px] text-on-surface-variant/70">Start monitoring to connect the camera</span>
              </>
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
            className={`flex items-center gap-xs px-md py-md rounded border text-sm font-medium uppercase tracking-wider transition-colors ${
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
          <ActionButton title="Log observation" onClick={handleLog} icon={FileText} />
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
      className="p-md rounded border border-white/10 bg-white/[0.03] text-on-surface-variant hover:text-cyan-100 hover:border-cyan-400/25 transition-colors"
      title={title}
    >
      <Icon className="w-4 h-4" />
    </button>
  );
}

