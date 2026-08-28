import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router';
import {
  Camera, Radio, BarChart3, CheckCircle2, ChevronRight, ChevronLeft,
  Play, AlertTriangle, Brain, Shield, Eye, ArrowRight, X, Loader2
} from 'lucide-react';
import { useAuth } from '@/src/auth/AuthContext';
import { apiFetch } from '@/src/services/apiClient';

/* ── Types ────────────────────────────────────────────────────────── */

interface SetupStatus {
  session_active: boolean;
  camera_status: string;
  camera_reconnecting: boolean;
  streaming: boolean;
  fps: number;
  framing_state?: string | null;
  brightness?: number | null;
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

interface OnboardingStep {
  id: string;
  title: string;
  description: string;
  icon: typeof Camera;
}

const STEPS: OnboardingStep[] = [
  {
    id: 'welcome',
    title: 'Welcome to ErgoVigilance',
    description: 'This quick setup will help you get started with ergonomic monitoring. It takes about 2 minutes.',
    icon: Shield,
  },
  {
    id: 'camera',
    title: 'Camera Setup',
    description: 'Position the camera so workers are fully visible. We\'ll check lighting, framing, and face visibility in real time.',
    icon: Camera,
  },
  {
    id: 'session',
    title: 'Start Monitoring',
    description: 'Once your camera is positioned, start a monitoring session to see live posture analysis.',
    icon: Radio,
  },
  {
    id: 'dashboard',
    title: 'Your Dashboard',
    description: 'Risk scores, alerts, and recommendations appear here. Green means good posture — red means stop and adjust.',
    icon: BarChart3,
  },
];

/* ── Main Component ────────────────────────────────────────────────── */

export default function OnboardingFlow({ onComplete }: { onComplete: () => void }) {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [step, setStep] = useState(0);
  const [cameraStatus, setCameraStatus] = useState<SetupStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [sessionStarted, setSessionStarted] = useState(false);

  // Poll camera status when on camera step
  useEffect(() => {
    if (step !== 1) return; // Only poll on camera step
    let cancelled = false;
    const poll = async () => {
      try {
        const res = await apiFetch('/api/setup/status');
        if (res.ok) {
          const data = await res.json();
          if (!cancelled) setCameraStatus(data);
        }
      } catch { /* ignore */ }
    };
    poll();
    const id = setInterval(poll, 2000);
    return () => { cancelled = true; clearInterval(id); };
  }, [step]);

  // Initial status load
  useEffect(() => {
    const load = async () => {
      try {
        const res = await apiFetch('/api/setup/status');
        if (res.ok) {
          const data = await res.json();
          setCameraStatus(data);
        }
      } catch { /* ignore */ }
      setLoading(false);
    };
    load();
  }, []);

  const checks = cameraStatus?.checks;
  const allChecksPass = checks && Object.values(checks).every(Boolean);
  const checksPassCount = checks ? Object.values(checks).filter(Boolean).length : 0;
  const totalChecks = checks ? Object.values(checks).length : 5;

  const handleStartSession = useCallback(async () => {
    try {
      const res = await apiFetch('/api/session/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ worker_id: null, camera_index: 0 }),
      });
      if (res.ok) {
        setSessionStarted(true);
        setStep(2);
      }
    } catch { /* ignore */ }
  }, []);

  const handleSkip = () => {
    localStorage.setItem('ergovigilance_onboarded', 'true');
    onComplete();
  };

  const handleFinish = () => {
    localStorage.setItem('ergovigilance_onboarded', 'true');
    navigate('/dashboard');
    onComplete();
  };

  return (
    <div className="fixed inset-0 z-[100] bg-slate-50 dark:bg-[#10131a] flex flex-col">
      {/* ── Progress Bar ──────────────────────────────────────── */}
      <div className="h-1 bg-slate-200 dark:bg-white/5">
        <div
          className="h-full bg-gradient-to-r from-blue-500 to-cyan-400 transition-all duration-500"
          style={{ width: `${((step + 1) / STEPS.length) * 100}%` }}
        />
      </div>

      {/* ── Header ────────────────────────────────────────────── */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-white/5">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center">
            {(() => { const Icon = STEPS[step].icon; return <Icon className="w-4 h-4 text-white" />; })()}
          </div>
          <div>
            <p className="text-xs text-slate-500 dark:text-slate-400">Step {step + 1} of {STEPS.length}</p>
            <p className="text-sm font-semibold text-slate-900 dark:text-white">{STEPS[step].title}</p>
          </div>
        </div>
        <button
          onClick={handleSkip}
          className="text-sm text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-white transition-colors"
        >
          Skip all →
        </button>
      </div>

      {/* ── Content ───────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto">
        {step === 0 && <WelcomeStep user={user} />}
        {step === 1 && <CameraStep status={cameraStatus} loading={loading} allChecksPass={allChecksPass} checksPassCount={checksPassCount} totalChecks={totalChecks} />}
        {step === 2 && <SessionStep started={sessionStarted} onStart={handleStartSession} />}
        {step === 3 && <DashboardStep />}
      </div>

      {/* ── Footer ────────────────────────────────────────────── */}
      <div className="flex items-center justify-between px-6 py-4 border-t border-slate-200 dark:border-white/5 bg-white dark:bg-[#10131a]">
        <button
          onClick={() => setStep(Math.max(0, step - 1))}
          disabled={step === 0}
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-white/5 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
        >
          <ChevronLeft className="w-4 h-4" /> Back
        </button>
        {step === STEPS.length - 1 ? (
          <button
            onClick={handleFinish}
            className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-blue-600 text-sm font-bold text-white hover:bg-blue-500 transition-all hover:shadow-lg hover:shadow-blue-500/25"
          >
            Go to Dashboard <ArrowRight className="w-4 h-4" />
          </button>
        ) : (
          <button
            onClick={() => setStep(step + 1)}
            className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-blue-600 text-sm font-bold text-white hover:bg-blue-500 transition-all hover:shadow-lg hover:shadow-blue-500/25"
          >
            Next <ChevronRight className="w-4 h-4" />
          </button>
        )}
      </div>
    </div>
  );
}

/* ── Step: Welcome ──────────────────────────────────────────────── */

function WelcomeStep({ user }: { user: { email?: string } | null }) {
  return (
    <div className="max-w-2xl mx-auto px-6 py-16 text-center space-y-8">
      <div className="w-20 h-20 rounded-2xl bg-blue-600 flex items-center justify-center mx-auto">
        <Shield className="w-10 h-10 text-white" />
      </div>
      <div>
        <h2 className="text-3xl font-bold text-slate-900 dark:text-white mb-3">
          Welcome{user?.email ? `, ${user.email.split('@')[0]}` : ''}!
        </h2>
        <p className="text-lg text-slate-600 dark:text-slate-400 leading-relaxed">
          ErgoVigilance monitors worker posture in real time using your existing cameras — no wearables needed.
          Let's get you set up in about 2 minutes.
        </p>
      </div>
      <div className="grid grid-cols-3 gap-6 text-left">
        {[
          { icon: Camera, title: 'Position Camera', desc: 'One-time setup guided by live feedback' },
          { icon: Radio, title: 'Start Session', desc: 'Begin monitoring with one click' },
          { icon: BarChart3, title: 'See Results', desc: 'Risk scores and alerts in real time' },
        ].map(({ icon: Icon, title, desc }) => (
          <div key={title} className="p-4 rounded-xl border border-slate-200 dark:border-white/10 bg-white dark:bg-white/[0.03]">
            <Icon className="w-6 h-6 text-blue-600 dark:text-blue-400 mb-3" />
            <p className="text-sm font-bold text-slate-900 dark:text-white mb-1">{title}</p>
            <p className="text-xs text-slate-500 dark:text-slate-400">{desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Step: Camera Setup ─────────────────────────────────────────── */

function CameraStep({
  status, loading, allChecksPass, checksPassCount, totalChecks
}: {
  status: SetupStatus | null;
  loading: boolean;
  allChecksPass: boolean;
  checksPassCount: number;
  totalChecks: number;
}) {
  return (
    <div className="max-w-3xl mx-auto px-6 py-8 space-y-6">
      <div className="text-center">
        <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-2">Camera Positioning</h2>
        <p className="text-sm text-slate-600 dark:text-slate-400">
          {allChecksPass
            ? 'All checks passed! Your camera is well positioned.'
            : `${checksPassCount}/${totalChecks} checks passed — adjust the camera to improve coverage.`}
        </p>
      </div>

      {/* Check list */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {[
          { key: 'streaming', label: 'Camera Streaming', detail: status?.camera_status === 'active' ? 'Active' : 'Not connected' },
          { key: 'worker_visible', label: 'Worker Visible', detail: status?.framing_state || 'Checking...' },
          { key: 'lighting_ok', label: 'Lighting OK', detail: status?.brightness ? `${Math.round((status.brightness / 255) * 100)}%` : 'Checking...' },
          { key: 'face_visible', label: 'Face Visible', detail: status?.faces_seen ? 'Detected' : 'Not detected' },
          { key: 'full_body', label: 'Full Body', detail: status?.lower_body_confidence ? `${Math.round(status.lower_body_confidence)}%` : 'Checking...' },
        ].map(({ key, label, detail }) => {
          const ok = status?.checks?.[key as keyof typeof status.checks] ?? false;
          return (
            <div
              key={key}
              className={`flex items-center gap-3 p-3 rounded-xl border transition-all ${
                ok
                  ? 'border-emerald-200 dark:border-emerald-500/30 bg-emerald-50 dark:bg-emerald-500/5'
                  : 'border-slate-200 dark:border-white/10 bg-white dark:bg-white/[0.03]'
              }`}
            >
              <CheckCircle2 className={`w-5 h-5 shrink-0 ${ok ? 'text-emerald-500' : 'text-slate-300 dark:text-slate-600'}`} />
              <div className="min-w-0">
                <p className={`text-sm font-medium ${ok ? 'text-emerald-700 dark:text-emerald-300' : 'text-slate-700 dark:text-slate-300'}`}>{label}</p>
                <p className="text-xs text-slate-500 dark:text-slate-400 truncate">{detail}</p>
              </div>
            </div>
          );
        })}
      </div>

      {loading && (
        <div className="flex items-center justify-center gap-2 text-sm text-slate-500 dark:text-slate-400">
          <Loader2 className="w-4 h-4 animate-spin" /> Reading camera status...
        </div>
      )}

      {allChecksPass && (
        <div className="p-4 rounded-xl bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/30 text-center">
          <p className="text-sm font-bold text-emerald-700 dark:text-emerald-300">✅ Camera is well positioned!</p>
          <p className="text-xs text-emerald-600 dark:text-emerald-400 mt-1">Click "Next" to start your first monitoring session.</p>
        </div>
      )}
    </div>
  );
}

/* ── Step: Start Session ────────────────────────────────────────── */

function SessionStep({ started, onStart }: { started: boolean; onStart: () => void }) {
  return (
    <div className="max-w-2xl mx-auto px-6 py-16 text-center space-y-8">
      <div className="w-16 h-16 rounded-2xl bg-blue-600 flex items-center justify-center mx-auto">
        <Radio className="w-8 h-8 text-white" />
      </div>
      <div>
        <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-2">Start Monitoring</h2>
        <p className="text-sm text-slate-600 dark:text-slate-400">
          Click below to start a live monitoring session. You'll see posture analysis, risk scores, and alerts in real time.
        </p>
      </div>
      {!started ? (
        <button
          onClick={onStart}
          className="inline-flex items-center gap-2 px-8 py-3.5 rounded-xl bg-gradient-to-r from-blue-600 to-cyan-500 text-base font-bold text-white hover:from-blue-500 hover:to-cyan-400 transition-all hover:shadow-xl hover:shadow-blue-500/25 active:scale-[0.97]"
        >
          <Play className="w-5 h-5" fill="currentColor" />
          Start Monitoring Session
        </button>
      ) : (
        <div className="p-6 rounded-xl bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/30 space-y-3">
          <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto" />
          <p className="text-sm font-bold text-emerald-700 dark:text-emerald-300">Session started!</p>
          <p className="text-xs text-emerald-600 dark:text-emerald-400">Workers are now being monitored. Click "Next" to see the dashboard.</p>
        </div>
      )}
    </div>
  );
}

/* ── Step: Dashboard Overview ───────────────────────────────────── */

function DashboardStep() {
  return (
    <div className="max-w-3xl mx-auto px-6 py-8 space-y-6">
      <div className="text-center">
        <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-2">Your Dashboard</h2>
        <p className="text-sm text-slate-600 dark:text-slate-400">
          Here's what you'll see every time you log in.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
          {
            icon: BarChart3,
            title: 'Risk Gauge',
            desc: 'Real-time risk score (0-100). Green = safe, amber = caution, red = stop.',
            color: 'text-blue-600 dark:text-blue-400',
          },
          {
            icon: AlertTriangle,
            title: 'Active Alerts',
            desc: 'High-risk postures trigger instant alerts with corrective action suggestions.',
            color: 'text-amber-600 dark:text-amber-400',
          },
          {
            icon: Brain,
            title: 'AI Insights',
            desc: 'Context-aware recommendations based on task type, fatigue, and exposure.',
            color: 'text-cyan-600 dark:text-cyan-400',
          },
        ].map(({ icon: Icon, title, desc, color }) => (
          <div key={title} className="p-4 rounded-xl border border-slate-200 dark:border-white/10 bg-white dark:bg-white/[0.03]">
            <Icon className={`w-6 h-6 ${color} mb-3`} />
            <p className="text-sm font-bold text-slate-900 dark:text-white mb-1">{title}</p>
            <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">{desc}</p>
          </div>
        ))}
      </div>

      <div className="p-4 rounded-xl bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/30">
        <div className="flex items-start gap-3">
          <Eye className="w-5 h-5 text-blue-600 dark:text-blue-400 shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-bold text-blue-700 dark:text-blue-300">Privacy first</p>
            <p className="text-xs text-blue-600 dark:text-blue-400 mt-1">
              Your posture data is used only for safety — never for performance evaluation. You can request deletion anytime from Settings.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
