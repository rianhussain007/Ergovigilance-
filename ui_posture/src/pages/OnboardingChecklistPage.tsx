import { FormEvent, useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import {
  CheckCircle2, Camera, Users, Play, BarChart3, ArrowRight, ArrowLeft,
  Building2, Loader2, Wifi, Eye, ChevronRight,
} from 'lucide-react';
import { useAuth } from '@/src/auth/AuthContext';
import { apiFetch, friendlyHttpError } from '@/src/services/apiClient';
import Logo from '../components/common/Logo';

/* ── Step definitions ──────────────────────────────────────────── */

interface StepDef {
  id: string;
  title: string;
  subtitle: string;
  icon: React.ElementType;
}

const STEPS: StepDef[] = [
  { id: 'welcome',     title: 'Welcome',           subtitle: 'Your factory profile',     icon: Building2 },
  { id: 'camera',      title: 'First Camera',      subtitle: 'Connect a camera',         icon: Camera },
  { id: 'worker',      title: 'First Worker',      subtitle: 'Add a team member',        icon: Users },
  { id: 'monitor',     title: 'Start Monitoring',  subtitle: 'Run a test session',       icon: Play },
  { id: 'dashboard',   title: 'Dashboard',         subtitle: 'See your results',         icon: BarChart3 },
];

/* ── Wizard Page ───────────────────────────────────────────────── */

export default function OnboardingChecklistPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);

  // Step data
  const [department, setDepartment] = useState('');
  const [cameraUrl, setCameraUrl] = useState('webcam');
  const [cameraName, setCameraName] = useState('Main Station');
  const [workerName, setWorkerName] = useState('');
  const [workerId, setWorkerId] = useState('');
  const [workerDept, setWorkerDept] = useState('');

  // Results
  const [cameraResult, setCameraResult] = useState<string | null>(null);
  const [workerResult, setWorkerResult] = useState<string | null>(null);
  const [sessionResult, setSessionResult] = useState<{ id: string; status: string } | null>(null);

  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Pre-fill from user org context
    if (user?.role) setWorkerDept('Production');
  }, [user]);

  const s = STEPS[step];

  /* ── Step handlers ─────────────────────────────────────────── */

  const handleCreateCamera = async () => {
    // Webcam needs no setup; an RTSP URL is really registered with the
    // cloud core. Failures stay on this step with the reason — the old
    // code advanced with a "ready" label having created nothing.
    setLoading(true); setError(null);
    try {
      if (cameraUrl === 'webcam') {
        setCameraResult('Webcam selected — no setup needed');
      } else {
        const name = cameraName.trim() || 'Main Station';
        const id = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'station-1';
        const res = await apiFetch('/cloud-api/cloud/cameras', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id, name, url: cameraUrl }),
        });
        if (!res.ok) {
          setError(`Could not add the camera (${friendlyHttpError(res.status, 'Camera setup')}). Fix the URL or skip setup above and add it later from Cloud Cameras.`);
          return;
        }
        setCameraResult(`${name} connected`);
      }
      setStep(2);
    } catch (e) {
      setError('Network error — is the cloud core running? See docs/DEV_START.md, or skip setup above.');
    } finally { setLoading(false); }
  };

  const handleCreateWorker = async () => {
    if (!workerName.trim()) { setError('Enter a worker name'); return; }
    setLoading(true); setError(null);
    try {
      const empId = workerId.trim() || `EMP-${Date.now().toString(36).slice(-4).toUpperCase()}`;
      const res = await apiFetch('/api/workers', {
        method: 'POST',
        body: JSON.stringify({
          employee_id: empId,
          name: workerName.trim(),
          department: workerDept || 'Production',
          shift: 'Day',
        }),
      });
      if (!res.ok) {
        setError(`${friendlyHttpError(res.status, 'Worker setup')} You can also skip setup above and add workers later.`);
        return;
      }
      setWorkerResult(`${workerName.trim()} (${empId})`);
      setStep(3);
    } catch (e) {
      // Network failure (backend down) — stay with guidance, not a fake skip.
      setError('Network error — is the backend running? See docs/DEV_START.md, or skip setup above.');
    } finally { setLoading(false); }
  };

  const handleStartTestSession = async () => {
    // The old endpoint path (/api/sessions/start, plural) never existed —
    // every call 404'd and the wizard showed a fabricated LOW result.
    // Real endpoint, real response, honest failure that stays on-step.
    setLoading(true); setError(null);
    try {
      const body: Record<string, unknown> = {};
      if (cameraUrl !== 'webcam') body.camera_id = cameraUrl;
      if (workerId.trim()) body.worker_id = workerId.trim();
      const res = await apiFetch('/api/session/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        if (res.status === 503) {
          setError('No camera available for a live session — connect a camera first, or continue to the dashboard (Skip setup above).');
        } else {
          setError(`${friendlyHttpError(res.status, 'Test session')} You can continue to the dashboard (Skip setup above).`);
        }
        return;
      }
      const data = await res.json();
      setSessionResult({ id: data.id || 'unknown', status: data.status || 'started' });
      setStep(4);
    } catch {
      setError('Network error — is the backend running? See docs/DEV_START.md, or skip setup above.');
    } finally { setLoading(false); }
  };

  const handleFinish = () => {
    localStorage.setItem('ergovigilance_onboarded', 'true');
    navigate('/dashboard', { replace: true });
  };

  /* ── Input styling ─────────────────────────────────────────── */

  const inputCls = 'w-full h-11 rounded-xl border border-slate-200 dark:border-outline-variant/80 bg-slate-50 dark:bg-surface px-4 text-sm text-slate-900 dark:text-on-surface outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/15 transition-all';
  const labelCls = 'block text-xs font-medium uppercase tracking-wider text-slate-400 dark:text-on-surface-variant mb-1.5';

  /* ── Render ────────────────────────────────────────────────── */

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-surface flex flex-col">
      {/* Top bar */}
      <header className="border-b border-slate-200 dark:border-outline-variant/60 bg-white/80 dark:bg-surface-container/80 backdrop-blur-sm">
        <div className="mx-auto max-w-3xl flex items-center justify-between px-6 py-4">
          <Logo className="h-8 w-auto" variant="light" />
          <button
            onClick={() => { localStorage.setItem('ergovigilance_onboarded', 'true'); navigate('/dashboard'); }}
            className="text-xs text-slate-400 hover:text-slate-600 dark:text-on-surface-variant dark:hover:text-on-surface transition-colors"
          >
            Skip setup →
          </button>
        </div>
      </header>

      <main className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-xl">
          {/* Progress dots */}
          <div className="flex items-center justify-center gap-2 mb-8">
            {STEPS.map((st, i) => {
              const done = i < step;
              const active = i === step;
              return (
                <div key={st.id} className="flex items-center gap-2">
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all duration-300 ${
                    done ? 'bg-green-500 text-white' :
                    active ? 'bg-blue-600 text-white ring-4 ring-blue-600/20' :
                    'bg-slate-200 dark:bg-surface-variant text-slate-400 dark:text-on-surface-variant'
                  }`}>
                    {done ? <CheckCircle2 className="h-4 w-4" /> : i + 1}
                  </div>
                  {i < STEPS.length - 1 && (
                    <div className={`w-12 h-0.5 rounded transition-all duration-300 ${
                      done ? 'bg-green-500' : 'bg-slate-200 dark:bg-surface-variant'
                    }`} />
                  )}
                </div>
              );
            })}
          </div>

          {/* Step card */}
          <div className="rounded-2xl border border-slate-200 dark:border-outline-variant/60 bg-white dark:bg-surface-container shadow-xl shadow-slate-200/50 dark:shadow-2xl dark:shadow-black/20 overflow-hidden animate-fade-in" key={s.id}>
            {/* Header */}
            <div className="px-8 pt-8 pb-6">
              <div className="flex items-center gap-3 mb-1">
                <s.icon className="h-5 w-5 text-blue-600 dark:text-primary" />
                <span className="text-xs font-medium uppercase tracking-wider text-slate-400 dark:text-on-surface-variant">
                  Step {step + 1} of {STEPS.length}
                </span>
              </div>
              <h2 className="text-2xl font-bold text-slate-900 dark:text-on-surface">{s.title}</h2>
              <p className="text-sm text-slate-500 dark:text-on-surface-variant mt-1">{s.subtitle}</p>
            </div>

            {/* Body */}
            <div className="px-8 pb-8">
              {/* Step 0: Welcome */}
              {step === 0 && (
                <div className="space-y-5">
                  <div className="rounded-xl bg-blue-50 dark:bg-primary/10 border border-blue-200 dark:border-primary/20 p-4">
                    <p className="text-sm text-blue-700 dark:text-primary font-medium">
                      Welcome{user?.email ? `, ${user.email.split('@')[0]}` : ''}! Let&apos;s get your factory monitoring set up in under 5 minutes.
                    </p>
                  </div>
                  <div className="space-y-3">
                    <p className="text-sm text-slate-600 dark:text-on-surface-variant">
                      What department will this monitor first?
                    </p>
                    <input
                      type="text"
                      value={department}
                      onChange={(e) => setDepartment(e.target.value)}
                      placeholder="e.g. Assembly Line A, Packaging, Warehouse"
                      className={inputCls}
                      autoFocus
                    />
                  </div>
                  <div className="grid grid-cols-3 gap-3 text-center">
                    {['Production', 'Assembly', 'Warehouse'].map(d => (
                      <button
                        key={d}
                        onClick={() => setDepartment(d)}
                        className={`rounded-xl border p-3 text-sm transition-all ${
                          department === d
                            ? 'border-blue-500 bg-blue-50 dark:bg-primary/10 text-blue-700 dark:text-primary font-medium'
                            : 'border-slate-200 dark:border-outline-variant/60 hover:border-slate-300 text-slate-600 dark:text-on-surface-variant'
                        }`}
                      >
                        {d}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Step 1: Camera */}
              {step === 1 && (
                <div className="space-y-5">
                  <div className="space-y-3">
                    <p className="text-sm text-slate-600 dark:text-on-surface-variant">
                      How will you connect a camera? You can skip this and add cameras later.
                    </p>
                    <input
                      type="text"
                      value={cameraName}
                      onChange={(e) => setCameraName(e.target.value)}
                      placeholder="Station name"
                      className={inputCls}
                    />
                    <div className="grid grid-cols-2 gap-3">
                      <button
                        onClick={() => setCameraUrl('webcam')}
                        className={`rounded-xl border p-4 text-left transition-all ${
                          cameraUrl === 'webcam'
                            ? 'border-blue-500 bg-blue-50 dark:bg-primary/10'
                            : 'border-slate-200 dark:border-outline-variant/60 hover:border-slate-300'
                        }`}
                      >
                        <Eye className="h-5 w-5 text-blue-600 dark:text-primary mb-2" />
                        <p className="text-sm font-medium text-slate-900 dark:text-on-surface">Webcam</p>
                        <p className="text-xs text-slate-400">Use your laptop camera</p>
                      </button>
                      <button
                        onClick={() => setCameraUrl('rtsp://')}
                        className={`rounded-xl border p-4 text-left transition-all ${
                          cameraUrl !== 'webcam'
                            ? 'border-blue-500 bg-blue-50 dark:bg-primary/10'
                            : 'border-slate-200 dark:border-outline-variant/60 hover:border-slate-300'
                        }`}
                      >
                        <Wifi className="h-5 w-5 text-blue-600 dark:text-primary mb-2" />
                        <p className="text-sm font-medium text-slate-900 dark:text-on-surface">RTSP Camera</p>
                        <p className="text-xs text-slate-400">CCTV / IP camera</p>
                      </button>
                    </div>
                    {cameraUrl !== 'webcam' && (
                      <input
                        type="text"
                        value={cameraUrl}
                        onChange={(e) => setCameraUrl(e.target.value)}
                        placeholder="rtsp://admin:password@192.168.1.100:554/stream"
                        className={`${inputCls} font-mono text-xs`}
                      />
                    )}
                  </div>
                </div>
              )}

              {/* Step 2: Worker */}
              {step === 2 && (
                <div className="space-y-5">
                  <p className="text-sm text-slate-600 dark:text-on-surface-variant">
                    Add your first worker to monitor. You can add more later.
                  </p>
                  <div className="space-y-3">
                    <div>
                      <label className={labelCls}>Worker Name *</label>
                      <input
                        type="text"
                        value={workerName}
                        onChange={(e) => setWorkerName(e.target.value)}
                        placeholder="e.g. Rajesh Kumar"
                        className={inputCls}
                        autoFocus
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className={labelCls}>Employee ID</label>
                        <input
                          type="text"
                          value={workerId}
                          onChange={(e) => setWorkerId(e.target.value)}
                          placeholder="Auto-generated if empty"
                          className={inputCls}
                        />
                      </div>
                      <div>
                        <label className={labelCls}>Department</label>
                        <input
                          type="text"
                          value={workerDept}
                          onChange={(e) => setWorkerDept(e.target.value)}
                          placeholder="e.g. Assembly"
                          className={inputCls}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Step 3: Monitor */}
              {step === 3 && (
                <div className="space-y-5">
                  <div className="rounded-xl bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/20 p-4">
                    <p className="text-sm text-amber-700 dark:text-amber-400">
                      <strong>Ready to monitor!</strong> This will start a test session using {cameraUrl === 'webcam' ? 'your webcam' : 'the configured camera'}. The system will analyze posture in real-time.
                    </p>
                  </div>
                  <div className="grid grid-cols-3 gap-3 text-center">
                    <div className="rounded-xl border border-slate-200 dark:border-outline-variant/60 p-3">
                      <p className="text-xs text-slate-400">Camera</p>
                      <p className="text-sm font-medium text-slate-900 dark:text-on-surface">{cameraResult || 'Not set'}</p>
                    </div>
                    <div className="rounded-xl border border-slate-200 dark:border-outline-variant/60 p-3">
                      <p className="text-xs text-slate-400">Worker</p>
                      <p className="text-sm font-medium text-slate-900 dark:text-on-surface">{workerResult || 'Not set'}</p>
                    </div>
                    <div className="rounded-xl border border-slate-200 dark:border-outline-variant/60 p-3">
                      <p className="text-xs text-slate-400">Department</p>
                      <p className="text-sm font-medium text-slate-900 dark:text-on-surface">{department || 'General'}</p>
                    </div>
                  </div>
                </div>
              )}

              {/* Step 4: Dashboard */}
              {step === 4 && (
                <div className="space-y-5">
                  <div className="rounded-xl bg-green-50 dark:bg-green-500/10 border border-green-200 dark:border-green-500/20 p-4 flex items-start gap-3">
                    <CheckCircle2 className="h-5 w-5 text-green-600 dark:text-green-400 mt-0.5" />
                    <div>
                      <p className="text-sm text-green-700 dark:text-green-400 font-medium">Setup complete!</p>
                      <p className="text-xs text-green-600 dark:text-green-400/80 mt-1">
                        Your factory is ready for ergonomic monitoring. Explore the dashboard to see analytics, reports, and real-time posture data.
                      </p>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    {[
                      { label: 'Dashboard', desc: 'Overview & analytics', href: '/dashboard' },
                      { label: 'Live Monitoring', desc: 'Real-time posture', href: '/monitoring' },
                      { label: 'Workers', desc: 'Manage team', href: '/workers' },
                      { label: 'Reports', desc: 'Safety reports', href: '/reports' },
                    ].map(item => (
                      <a
                        key={item.href}
                        href={item.href}
                        className="rounded-xl border border-slate-200 dark:border-outline-variant/60 p-3 hover:border-blue-300 dark:hover:border-primary/40 transition-all group"
                      >
                        <p className="text-sm font-medium text-slate-900 dark:text-on-surface group-hover:text-blue-600 dark:group-hover:text-primary">{item.label}</p>
                        <p className="text-xs text-slate-400">{item.desc}</p>
                        <ChevronRight className="h-3 w-3 text-slate-300 mt-1 group-hover:text-blue-500 transition-colors" />
                      </a>
                    ))}
                  </div>
                </div>
              )}

              {/* Error */}
              {error && (
                <div className="mt-4 rounded-xl bg-red-50 dark:bg-danger/10 border border-red-200 dark:border-danger/30 px-4 py-3 text-sm text-red-600 dark:text-danger">
                  {error}
                </div>
              )}

              {/* Actions */}
              <div className="flex items-center justify-between mt-6 pt-5 border-t border-slate-100 dark:border-outline-variant/60">
                {step > 0 && step < 4 ? (
                  <button
                    onClick={() => setStep(step - 1)}
                    className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm text-slate-500 hover:text-slate-700 dark:text-on-surface-variant dark:hover:text-on-surface transition-colors"
                  >
                    <ArrowLeft className="h-3.5 w-3.5" /> Back
                  </button>
                ) : <div />}

                {step === 0 && (
                  <button
                    onClick={() => setStep(1)}
                    className="flex items-center gap-1.5 px-5 py-2.5 rounded-xl bg-blue-600 dark:bg-primary text-white dark:text-on-primary text-sm font-semibold hover:bg-blue-700 dark:hover:shadow-lg transition-all active:scale-[0.98]"
                  >
                    Get started <ArrowRight className="h-3.5 w-3.5" />
                  </button>
                )}
                {step === 1 && (
                  <button
                    onClick={handleCreateCamera}
                    disabled={loading}
                    className="flex items-center gap-1.5 px-5 py-2.5 rounded-xl bg-blue-600 dark:bg-primary text-white dark:text-on-primary text-sm font-semibold hover:bg-blue-700 dark:hover:shadow-lg disabled:opacity-50 transition-all active:scale-[0.98]"
                  >
                    {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ArrowRight className="h-3.5 w-3.5" />}
                    {cameraUrl === 'webcam' ? 'Use webcam' : 'Connect camera'}
                  </button>
                )}
                {step === 2 && (
                  <button
                    onClick={handleCreateWorker}
                    disabled={loading}
                    className="flex items-center gap-1.5 px-5 py-2.5 rounded-xl bg-blue-600 dark:bg-primary text-white dark:text-on-primary text-sm font-semibold hover:bg-blue-700 dark:hover:shadow-lg disabled:opacity-50 transition-all active:scale-[0.98]"
                  >
                    {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ArrowRight className="h-3.5 w-3.5" />}
                    Add worker
                  </button>
                )}
                {step === 3 && (
                  <button
                    onClick={handleStartTestSession}
                    disabled={loading}
                    className="flex items-center gap-1.5 px-5 py-2.5 rounded-xl bg-blue-600 dark:bg-primary text-white dark:text-on-primary text-sm font-semibold hover:bg-blue-700 dark:hover:shadow-lg disabled:opacity-50 transition-all active:scale-[0.98]"
                  >
                    {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
                    Start test session
                  </button>
                )}
                {step === 4 && (
                  <button
                    onClick={handleFinish}
                    className="flex items-center gap-1.5 px-5 py-2.5 rounded-xl bg-green-600 text-white text-sm font-semibold hover:bg-green-700 transition-all active:scale-[0.98]"
                  >
                    Go to dashboard <ArrowRight className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Footer tip */}
          <p className="text-center text-xs text-slate-400 dark:text-on-surface-variant/60 mt-6">
            Free pilot · No credit card · 3 cameras · 50 workers · Local processing
          </p>
        </div>
      </main>
    </div>
  );
}
