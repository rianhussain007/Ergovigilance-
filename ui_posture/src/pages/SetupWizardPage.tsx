import { useEffect, useState } from 'react';
import { getStoredToken } from '@/src/auth/AuthContext';
import { apiFetch } from '@/src/services/apiClient';
import { CheckCircle2, XCircle, Loader2, Video, Sun, User, ScanFace, Camera as CameraIcon, ArrowLeft } from 'lucide-react';
import { useNavigate } from 'react-router';

interface SetupStatus {
  session_active: boolean;
  camera_status: string;
  camera_reconnecting: boolean;
  streaming: boolean;
  fps: number;
  framing_state?: string | null;
  quality_score?: number | null;
  guidance: string[];
  brightness?: number | null;
  brightness_ok: boolean;
  person_detected: boolean;
  person_count: number;
  faces_seen: boolean;
  lower_body_confidence?: number | null;
  checks: {
    streaming: boolean;
    worker_visible: boolean;
    lighting_ok: boolean;
    face_visible: boolean;
    full_body: boolean;
  };
}

function CheckRow({ ok, label, detail }: { ok: boolean; label: string; detail?: string }) {
  return (
    <div className={`flex items-start gap-md rounded-lg border p-md ${ok ? 'border-green-500/30 bg-green-500/5' : 'border-amber-500/30 bg-amber-500/5'}`}>
      {ok ? (
        <CheckCircle2 className="w-5 h-5 text-emerald-300 shrink-0 mt-0.5" />
      ) : (
        <XCircle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
      )}
      <div>
        <p className={`text-body-md font-bold ${ok ? 'text-emerald-300' : 'text-amber-400'}`}>{label}</p>
        {detail && <p className="text-body-sm text-on-surface-variant mt-0.5">{detail}</p>}
      </div>
    </div>
  );
}

export default function SetupWizardPage() {
  const navigate = useNavigate();
  const [status, setStatus] = useState<SetupStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const token = getStoredToken();

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const res = await apiFetch('/api/setup/status');
        if (!res.ok) throw new Error(`Setup status failed (${res.status})`);
        const data = await res.json();
        if (!cancelled) {
          setStatus(data);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Cannot reach the backend.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    poll();
    const id = setInterval(poll, 2000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  const checks = status?.checks;
  const allPass = checks && Object.values(checks).every(Boolean);
  const brightness = status?.brightness;
  const brightPct = brightness != null ? Math.min(100, Math.round((brightness / 255) * 100)) : 0;

  return (
    <div className="p-lg space-y-lg pb-xl">
      <button onClick={() => navigate('/settings')} className="flex items-center gap-sm text-body-sm text-on-surface-variant hover:text-on-surface transition-colors">
        <ArrowLeft className="w-4 h-4" /> Back to Settings
      </button>

      <div>
        <h1 className="text-display-lg font-bold text-on-surface">Camera Setup Wizard</h1>
        <p className="text-body-sm text-on-surface-variant mt-xs">
          Position the camera once, guided by live feedback. Start a monitoring session (or use Demo mode) — the wizard reads the live assessment every 2 seconds.
        </p>
      </div>

      {loading && !status ? (
        <div className="flex items-center gap-sm text-on-surface-variant">
          <Loader2 className="w-4 h-4 animate-spin" /> Reading camera…
        </div>
      ) : error ? (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-md py-sm text-body-sm text-red-400">{error}</div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-lg">
          {/* ── Live feed ── */}
          <div className="rounded-xl border border-outline-variant bg-surface-container p-lg">
            <div className="flex items-center gap-sm mb-md">
              <CameraIcon className="w-4 h-4 text-primary" />
              <h2 className="text-title-sm font-bold text-on-surface">Live view</h2>
              {status?.camera_reconnecting && (
                <span className="text-xs font-bold text-amber-400">Reconnecting…</span>
              )}
            </div>
            <div className="rounded-lg overflow-hidden bg-black">
              <img
                src={`/video/feed?overlay=true&token=${encodeURIComponent(token || '')}`}
                alt="Live camera with pose overlay"
                className="w-full h-auto"
              />
            </div>
            <div className="flex items-center justify-between mt-md text-body-sm text-on-surface-variant">
              <span>{status?.camera_status === 'active' ? 'Camera active' : 'Camera idle'}</span>
              {status?.fps ? <span className="font-mono">{status.fps.toFixed(1)} fps</span> : null}
            </div>
          </div>

          {/* ── Checklist ── */}
          <div className="space-y-md">
            <div className="rounded-xl border border-outline-variant bg-surface-container p-lg space-y-md">
              <div className="flex items-center justify-between">
                <h2 className="text-title-sm font-bold text-on-surface">Positioning checklist</h2>
                {allPass ? (
                  <span className="text-xs font-bold text-emerald-300 bg-green-500/10 border border-green-500/30 rounded-full px-3 py-1">All checks passed</span>
                ) : (
                  <span className="text-xs font-bold text-amber-400 bg-amber-500/10 border border-amber-500/30 rounded-full px-3 py-1">Keep adjusting</span>
                )}
              </div>
              <CheckRow ok={!!checks?.streaming} label="Camera streaming" detail={status?.session_active ? `Live session active${status?.camera_reconnecting ? ' — reconnecting' : ''}` : 'No session yet — start monitoring or use Demo mode.'} />
              <CheckRow
                ok={!!checks?.worker_visible}
                label="Worker fully visible"
                detail={status?.framing_state === 'poor' ? 'No good pose detected — reposition the camera to see the full body.' : status?.framing_state === 'upper_body' ? 'Only upper body visible — move the camera down / further back.' : status?.framing_state ? `Framing: ${status.framing_state}` : 'Waiting for a pose assessment…'}
              />
              <CheckRow
                ok={!!checks?.lighting_ok}
                label="Lighting adequate"
                detail={brightness != null ? `Measured brightness ${brightness}/255 (target 60–200). ${brightness < 60 ? 'Too dark — add light.' : brightness > 200 ? 'Too bright — reduce glare.' : 'Good range.'}` : 'No frame yet to measure lighting.'}
              />
              <CheckRow
                ok={!!checks?.face_visible}
                label="Face visible for identification"
                detail={status?.faces_seen ? `${status.person_count || 1} person(s) with a visible face` : 'No face seen — position the camera so the face is clearly in view.'}
              />
              <CheckRow
                ok={!!checks?.full_body}
                label="Full body in frame (for posture scores)"
                detail={status?.lower_body_confidence != null ? `Lower-body confidence ${Math.round(status.lower_body_confidence)}% (target ≥ 50%)` : 'No assessment yet.'}
              />
            </div>

            {/* ── Guidance ── */}
            <div className="rounded-xl border border-outline-variant bg-surface-container p-lg">
              <h2 className="text-title-sm font-bold text-on-surface mb-md">Live guidance</h2>
              {status?.guidance && status.guidance.length > 0 ? (
                <ul className="space-y-sm text-body-sm text-on-surface-variant">
                  {status.guidance.slice(0, 4).map((g, i) => (
                    <li key={i} className="flex items-start gap-sm">
                      <span className="text-amber-400 mt-0.5">•</span> {g}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-body-sm text-on-surface-variant">No guidance yet — start a session.</p>
              )}
              {/* Brightness bar */}
              <div className="mt-md">
                <div className="flex items-center gap-sm text-body-sm text-on-surface-variant mb-1">
                  <Sun className="w-4 h-4" /> Brightness
                  <span className="font-mono">{brightness != null ? brightness : '—'}/255</span>
                </div>
                <div className="h-2 rounded-full bg-surface-container-highest overflow-hidden">
                  <div className="h-full rounded-full bg-amber-400 transition-all" style={{ width: `${brightPct}%` }} />
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="flex flex-wrap gap-md text-body-sm text-on-surface-variant">
        <span className="flex items-center gap-sm"><Video className="w-4 h-4" /> Streaming</span>
        <span className="flex items-center gap-sm"><User className="w-4 h-4" /> Person visible</span>
        <span className="flex items-center gap-sm"><ScanFace className="w-4 h-4" /> Face for ID</span>
      </div>
    </div>
  );
}
