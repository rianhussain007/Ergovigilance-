import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useNavigate, useLocation } from 'react-router';
import {
  ChevronRight, ChevronLeft, X, HelpCircle, Keyboard,
  BarChart3, Radio, AlertTriangle, FileText, Settings, Camera,
} from 'lucide-react';

/* ── Tour Step Types ─────────────────────────────────────────────── */

interface TourStep {
  id: string;
  route: string | null;
  target: string | null;
  position: 'top' | 'bottom' | 'left' | 'right' | 'center';
  icon: typeof BarChart3;
  title: string;
  description: string;
  detail?: string;
}

const TOUR_STEPS: TourStep[] = [
  {
    id: 'welcome',
    route: '/dashboard',
    target: null,
    position: 'center',
    icon: BarChart3,
    title: 'Welcome to ErgoVigilance',
    description:
      'Your ergonomic command center. In 90 seconds, learn how to monitor posture, receive alerts, and generate compliance reports.',
    detail: 'Click "Next" or press → to continue the tour.',
  },
  {
    id: 'risk-gauge',
    route: '/dashboard',
    target: '[data-tour="risk-gauge"]',
    position: 'top',
    icon: BarChart3,
    title: 'Real-Time Risk Score',
    description:
      'This animated gauge shows the current ergonomic risk level. Green means safe — red means correct immediately.',
    detail: 'Scores use 33 skeletal landmarks with RULA/REBA assessment methods.',
  },
  {
    id: 'getting-started',
    route: '/dashboard',
    target: '[data-tour="getting-started"]',
    position: 'bottom',
    icon: HelpCircle,
    title: 'Getting Started Checklist',
    description:
      'New users see a 5-step setup guide. Complete each step to unlock the full monitoring experience.',
    detail: 'Progress is saved automatically. Dismiss when done.',
  },
  {
    id: 'live-monitoring',
    route: '/monitoring',
    target: '[data-tour="camera-panel"]',
    position: 'bottom',
    icon: Radio,
    title: 'Live Camera Feed',
    description:
      'The live feed shows the pose skeleton overlay with per-joint risk coloring. Click "Start Monitoring" to begin.',
    detail: 'No special hardware — works with standard webcams and CCTV cameras.',
  },
  {
    id: 'task-recognition',
    route: '/monitoring',
    target: '[data-tour="task-card"]',
    position: 'left',
    icon: Camera,
    title: 'AI Task Recognition',
    description:
      'The system classifies worker actions (assembly, lifting, reaching) and adjusts risk thresholds per task type.',
    detail: '7-class task model with real-time confidence scoring.',
  },
  {
    id: 'posture-status',
    route: '/monitoring',
    target: '[data-tour="posture-banner"]',
    position: 'top',
    icon: Radio,
    title: 'Posture Status Banner',
    description:
      'A plain-language banner tells the worker exactly what to do: "Posture OK" or "Stop — unsafe posture".',
    detail: 'Available in English, Hindi, and Chinese via Settings → Language.',
  },
  {
    id: 'alerts',
    route: '/dashboard',
    target: '[data-tour="alerts-section"]',
    position: 'left',
    icon: AlertTriangle,
    title: 'Alert Management',
    description:
      'When a worker holds a risky posture too long, an alert fires with severity, duration, and corrective action.',
    detail: 'Alerts are sent via email, Slack, and webhooks when configured.',
  },
  {
    id: 'reports',
    route: '/reports',
    target: '[data-tour="reports-content"]',
    position: 'bottom',
    icon: FileText,
    title: 'Compliance Reports',
    description:
      'Generate PDF, CSV, and JSON reports. Includes risk trends, safety analysis, and nightly risk digests.',
    detail: 'Evidence packages include session data + MP4 for OSHA/insurance review.',
  },
  {
    id: 'analytics',
    route: '/analytics',
    target: null,
    position: 'center',
    icon: BarChart3,
    title: 'Analytics Dashboard',
    description:
      'Session analytics with risk trend charts, department comparisons, and worker performance breakdowns.',
    detail: 'Data updates in real-time during active monitoring sessions.',
  },
  {
    id: 'workers',
    route: '/workers',
    target: null,
    position: 'center',
    icon: Settings,
    title: 'Worker Management',
    description:
      'Enroll workers with face recognition, badge/QR codes, or anonymous mode. Each worker gets a consent record.',
    detail: 'GDPR-compliant: workers can request data deletion.',
  },
  {
    id: 'cloud-cameras',
    route: '/cloud-cameras',
    target: null,
    position: 'center',
    icon: Camera,
    title: 'Cloud Cameras (YOLO)',
    description:
      'Connect factory CCTV cameras via RTSP. The YOLO cloud core processes multiple cameras simultaneously.',
    detail: 'Ideal for factories with existing CCTV infrastructure.',
  },
  {
    id: 'settings',
    route: '/settings',
    target: '[data-tour="settings-content"]',
    position: 'bottom',
    icon: Settings,
    title: 'Settings & Language',
    description:
      'Configure alerts, notifications, theme, and switch between English, Hindi, and Chinese.',
    detail: 'Press Ctrl+K anywhere to search across the entire application.',
  },
  {
    id: 'complete',
    route: null,
    target: null,
    position: 'center',
    icon: HelpCircle,
    title: 'Tour Complete!',
    description:
      'You\'re ready to start monitoring. Explore the sidebar for more features, or press ? for keyboard shortcuts.',
    detail: 'Tip: Use "Try Demo" on the login page for a live walkthrough with synthetic data.',
  },
];

const TOUR_DISMISSED_KEY = 'ergovigilance_tour_dismissed_at';

/* ── Hook: whether to show the tour ──────────────────────────────── */

export function useProductTour() {
  const [showTour, setShowTour] = useState(false);
  const [showHelp, setShowHelp] = useState(false);

  const startTour = useCallback(() => {
    localStorage.removeItem(TOUR_DISMISSED_KEY);
    setShowTour(true);
  }, []);

  const dismissTour = useCallback(() => {
    setShowTour(false);
    // Record when the user dismissed so we don't re-show immediately
    localStorage.setItem(TOUR_DISMISSED_KEY, String(Date.now()));
  }, []);

  const dismissHelp = useCallback(() => setShowHelp(false), []);

  return { showTour, showHelp, startTour, dismissTour, setShowHelp, dismissHelp };
}

/* ── Main Tour Overlay ───────────────────────────────────────────── */

export function ProductTour({ onComplete }: { onComplete: () => void }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [currentStep, setCurrentStep] = useState(0);
  const [spotlightRect, setSpotlightRect] = useState<DOMRect | null>(null);
  const [navigating, setNavigating] = useState(false);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const completedRef = useRef(false);

  // Memoize the step to prevent useEffect re-runs on every render.
  // TOUR_STEPS[currentStep] creates a new object reference each render;
  // memoizing by currentStep index avoids that.
  const step = useMemo(() => TOUR_STEPS[currentStep], [currentStep]);
  const isFirst = currentStep === 0;
  const isLast = currentStep === TOUR_STEPS.length - 1;

  // Navigate to the step's route if needed
  useEffect(() => {
    if (step.route && location.pathname !== step.route) {
      setNavigating(true);
      navigate(step.route, { replace: true });
    } else if (navigating) {
      // Only clear navigating when we were actually navigating
      setNavigating(false);
    }
  }, [step.route, location.pathname, navigate]); // intentionally omit `navigating` to avoid loop

  // Calculate spotlight rect after navigation settles
  useEffect(() => {
    if (navigating) return;

    // Use a longer delay for lazy-loaded pages (code-split routes need time
    // to fetch and render their chunk). 300ms covers most Vite chunk loads.
    const timer = setTimeout(() => {
      if (step.target) {
        const el = document.querySelector(step.target);
        if (el) {
          setSpotlightRect(el.getBoundingClientRect());
          return;
        }
        // Element not found yet — retry once more after another tick
        const retryTimer = setTimeout(() => {
          const retryEl = document.querySelector(step.target!);
          setSpotlightRect(retryEl ? retryEl.getBoundingClientRect() : null);
        }, 300);
        return () => clearTimeout(retryTimer);
      }
      setSpotlightRect(null);
    }, 300);

    return () => clearTimeout(timer);
  }, [step.target, navigating, location.pathname]);

  const goNext = useCallback(() => {
    if (completedRef.current) return; // Guard against double-fire
    if (isLast) {
      completedRef.current = true;
      onComplete();
      return;
    }
    setCurrentStep((s) => s + 1);
  }, [isLast, onComplete]);

  const goPrev = useCallback(() => {
    setCurrentStep((s) => Math.max(0, s - 1));
  }, []);

  // Keyboard navigation — only the tour handles keys, Layout's handler is
  // suppressed via `tourActive` prop to useKeyboardShortcuts.
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight' || e.key === 'Enter') {
        e.preventDefault();
        e.stopPropagation(); // Prevent Layout handler from seeing this
        goNext();
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault();
        e.stopPropagation();
        goPrev();
      } else if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        if (!completedRef.current) {
          completedRef.current = true;
          onComplete();
        }
      }
    };
    window.addEventListener('keydown', handler, true); // Capture phase to run first
    return () => window.removeEventListener('keydown', handler, true);
  }, [goNext, goPrev, onComplete]);

  if (navigating) {
    return (
      <div className="fixed inset-0 z-[200] bg-black/40 flex items-center justify-center">
        <div className="flex items-center gap-3 bg-slate-900 border border-white/10 rounded-xl px-6 py-4 shadow-2xl">
          <div className="w-4 h-4 border-2 border-blue-400/30 border-t-blue-400 rounded-full animate-spin" />
          <span className="text-sm text-white">Loading…</span>
        </div>
      </div>
    );
  }

  const tooltipStyle = computeTooltipStyle(spotlightRect, step.position);

  return (
    <div className="fixed inset-0 z-[200]">
      {/* Backdrop with spotlight hole */}
      <div className="absolute inset-0">
        <div className="absolute inset-0 bg-black/60" />
        {spotlightRect && (
          <div
            className="absolute rounded-xl ring-4 ring-blue-400/60 shadow-[0_0_0_9999px_rgba(0,0,0,0.6)] transition-all duration-500 ease-out pointer-events-none"
            style={{
              top: spotlightRect.top - 8,
              left: spotlightRect.left - 8,
              width: spotlightRect.width + 16,
              height: spotlightRect.height + 16,
            }}
          />
        )}
      </div>

      {/* Step counter */}
      <div className="absolute top-6 left-1/2 -translate-x-1/2 flex items-center gap-2 bg-black/70 backdrop-blur-sm px-4 py-2 rounded-full border border-white/10 z-10 pointer-events-none">
        {TOUR_STEPS.map((_, i) => (
          <div
            key={i}
            className={`w-2 h-2 rounded-full transition-all duration-300 ${
              i === currentStep ? 'bg-blue-400 scale-125' : i < currentStep ? 'bg-blue-400/50' : 'bg-white/20'
            }`}
          />
        ))}
        <span className="text-xs text-white/60 ml-2">{currentStep + 1}/{TOUR_STEPS.length}</span>
      </div>

      {/* Close button */}
      <button
        onClick={() => { if (!completedRef.current) { completedRef.current = true; onComplete(); } }}
        className="absolute top-6 right-6 z-10 w-10 h-10 rounded-full bg-black/60 backdrop-blur-sm border border-white/10 flex items-center justify-center text-white/60 hover:text-white hover:border-white/30 transition-all"
        title="End tour"
      >
        <X className="w-4 h-4" />
      </button>

      {/* Tooltip card */}
      <div
        ref={tooltipRef}
        className="absolute z-20 w-[380px] max-w-[calc(100vw-2rem)] bg-slate-900 border border-white/10 rounded-2xl shadow-2xl shadow-black/50 overflow-hidden"
        style={tooltipStyle}
      >
        <div className="h-1 bg-gradient-to-r from-blue-500 to-cyan-400" />

        <div className="p-6">
          <div className="flex items-start gap-4 mb-4">
            <div className="w-10 h-10 rounded-xl bg-blue-600/20 border border-blue-500/30 flex items-center justify-center shrink-0">
              <step.icon className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-white">{step.title}</h3>
              <p className="text-sm text-slate-300 leading-relaxed mt-1">{step.description}</p>
            </div>
          </div>

          {step.detail && (
            <p className="text-xs text-slate-500 leading-relaxed ml-14">{step.detail}</p>
          )}

          <div className="flex items-center justify-between mt-6 pt-4 border-t border-white/5">
            <button
              onClick={goPrev}
              disabled={isFirst}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm text-slate-400 hover:text-white hover:bg-white/5 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
              Back
            </button>
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-slate-600">← → navigate</span>
              <button
                onClick={goNext}
                className="flex items-center gap-1.5 px-5 py-2 rounded-xl bg-blue-600 text-sm font-bold text-white hover:bg-blue-500 transition-all hover:shadow-lg hover:shadow-blue-500/25"
              >
                {isLast ? 'Get Started' : 'Next'}
                {!isLast && <ChevronRight className="w-3.5 h-3.5" />}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Keyboard Shortcuts Help Panel ───────────────────────────────── */

interface Shortcut {
  keys: string[];
  label: string;
  description: string;
}

const SHORTCUTS: Shortcut[] = [
  { keys: ['Ctrl', 'K'], label: 'search', description: 'Open search modal' },
  { keys: ['?'], label: 'help', description: 'Toggle this shortcuts panel' },
  { keys: ['Esc'], label: 'close', description: 'Close modals and panels' },
  { keys: ['→'], label: 'next', description: 'Next step (during tour)' },
  { keys: ['←'], label: 'prev', description: 'Previous step (during tour)' },
  { keys: ['D'], label: 'dashboard', description: 'Go to Dashboard' },
  { keys: ['M'], label: 'monitor', description: 'Go to Live Monitoring' },
  { keys: ['R'], label: 'reports', description: 'Go to Reports' },
  { keys: ['S'], label: 'settings', description: 'Go to Settings' },
  { keys: ['1'], label: 'sessions', description: 'Go to Session History' },
];

export function KeyboardHelpPanel({ onClose }: { onClose: () => void }) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-[150] flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="w-[480px] max-w-[calc(100vw-2rem)] bg-slate-900 border border-white/10 rounded-2xl shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/5">
          <div className="flex items-center gap-3">
            <Keyboard className="w-5 h-5 text-blue-400" />
            <h2 className="text-lg font-bold text-white">Keyboard Shortcuts</h2>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center text-slate-400 hover:text-white hover:bg-white/10 transition-all"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="px-6 py-4 max-h-[60vh] overflow-y-auto">
          <div className="space-y-1">
            {SHORTCUTS.map((shortcut) => (
              <div
                key={shortcut.label}
                className="flex items-center justify-between py-2.5 px-3 rounded-lg hover:bg-white/5 transition-colors group"
              >
                <div className="flex items-center gap-3">
                  <span className="text-sm text-slate-300 group-hover:text-white transition-colors">
                    {shortcut.description}
                  </span>
                </div>
                <div className="flex items-center gap-1">
                  {shortcut.keys.map((key, i) => (
                    <span key={i}>
                      <kbd className="inline-flex items-center justify-center min-w-[24px] h-6 px-1.5 rounded-md bg-white/5 border border-white/10 text-xs font-mono text-slate-400">
                        {key}
                      </kbd>
                      {i < shortcut.keys.length - 1 && (
                        <span className="text-slate-600 text-xs mx-0.5">+</span>
                      )}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="px-6 py-3 border-t border-white/5 bg-white/[0.02]">
          <p className="text-xs text-slate-500 text-center">
            Navigation shortcuts (D, M, R, S) work when no input is focused.
          </p>
        </div>
      </div>
    </div>
  );
}

/* ── Keyboard Shortcuts Manager (global listener) ────────────────── */

export function useKeyboardShortcuts({
  onToggleSearch,
  onToggleHelp,
  tourActive,
}: {
  onToggleSearch: () => void;
  onToggleHelp: () => void;
  tourActive: boolean;
}) {
  const navigate = useNavigate();

  // Memoize the handler to prevent unnecessary listener re-registration.
  // The handler references tourActive, so it's only recreated when tourActive changes.
  const handler = useCallback((e: KeyboardEvent) => {
    const target = e.target as HTMLElement;
    if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) return;

    // Don't trigger during tour — ProductTour has its own capture-phase handler
    if (tourActive) return;

    if ((e.ctrlKey || e.metaKey) && e.key === 'k') return; // SearchModal handles this

    if (e.key === '?') {
      e.preventDefault();
      onToggleHelp();
      return;
    }

    if (!e.ctrlKey && !e.metaKey && !e.altKey) {
      switch (e.key.toLowerCase()) {
        case 'd': navigate('/dashboard'); break;
        case 'm': navigate('/monitoring'); break;
        case 'r': navigate('/reports'); break;
        case 's': navigate('/settings'); break;
        case '1': navigate('/sessions'); break;
      }
    }
  }, [onToggleHelp, tourActive, navigate]);

  useEffect(() => {
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [handler]);
}

/* ── Network Status Indicator ────────────────────────────────────── */

export function NetworkStatusIndicator() {
  const [status, setStatus] = useState<'online' | 'offline' | 'reconnecting'>('online');
  const failCountRef = useRef(0);
  const checkRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const dismissedRef = useRef(false);

  const checkBackend = useCallback(async () => {
    if (dismissedRef.current) return;
    try {
      // Use /health which is proxied to backend via vite.config.ts
      const res = await fetch('/health', { method: 'GET', signal: AbortSignal.timeout(5000) });
      if (res.ok) {
        failCountRef.current = 0;
        setStatus('online');
      } else {
        failCountRef.current++;
        // Only show banner after 2 consecutive failures to avoid flash on startup
        if (failCountRef.current >= 2) setStatus('reconnecting');
      }
    } catch {
      failCountRef.current++;
      if (failCountRef.current >= 2) {
        setStatus(navigator.onLine ? 'reconnecting' : 'offline');
      }
    }
  }, []);

  useEffect(() => {
    checkRef.current = setInterval(checkBackend, 15000);
    // Initial check after 3s (give backend time to respond)
    const initTimer = setTimeout(checkBackend, 3000);
    return () => { if (checkRef.current) clearInterval(checkRef.current); clearTimeout(initTimer); };
  }, [checkBackend]);

  useEffect(() => {
    const onOffline = () => { failCountRef.current = 10; setStatus('offline'); };
    const onOnline = () => { failCountRef.current = 0; dismissedRef.current = false; setStatus('reconnecting'); checkBackend(); };
    window.addEventListener('offline', onOffline);
    window.addEventListener('online', onOnline);
    return () => {
      window.removeEventListener('offline', onOffline);
      window.removeEventListener('online', onOnline);
    };
  }, [checkBackend]);

  if (status === 'online') return null;

  return (
    <div
      className={`fixed bottom-4 right-4 z-[90] flex items-center gap-3 px-4 py-3 rounded-xl border shadow-lg backdrop-blur-sm transition-all duration-300 ${
        status === 'offline'
          ? 'bg-red-950/90 border-red-500/30 text-red-300'
          : 'bg-amber-950/90 border-amber-500/30 text-amber-300'
      }`}
    >
      <div className={`w-2 h-2 rounded-full animate-pulse ${status === 'offline' ? 'bg-red-400' : 'bg-amber-400'}`} />
      <div>
        <p className="text-xs font-bold">{status === 'offline' ? 'Offline' : 'Reconnecting…'}</p>
        <p className="text-[10px] opacity-70">
          {status === 'offline' ? 'Backend unreachable — data may be stale' : 'Attempting to restore connection'}
        </p>
      </div>
      <button onClick={() => { failCountRef.current = 0; checkBackend(); }} className="ml-1 px-2 py-1 rounded-lg bg-white/10 hover:bg-white/20 text-xs font-medium transition-colors">
        Retry
      </button>
      <button onClick={() => { dismissedRef.current = true; setStatus('online'); }} className="ml-1 px-1.5 py-1 rounded-lg bg-white/5 hover:bg-white/15 text-xs opacity-60 hover:opacity-100 transition-all" title="Dismiss">
        ✕
      </button>
    </div>
  );
}

/* ── Help Button (floating) ──────────────────────────────────────── */

export function FloatingHelpButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="fixed bottom-4 left-4 z-[80] w-10 h-10 rounded-full bg-slate-800/90 border border-white/10 flex items-center justify-center text-slate-400 hover:text-white hover:border-white/20 hover:bg-slate-700/90 transition-all shadow-lg backdrop-blur-sm group"
      title="Keyboard shortcuts (?)"
    >
      <HelpCircle className="w-4 h-4 group-hover:scale-110 transition-transform" />
    </button>
  );
}

/* ── Helpers ─────────────────────────────────────────────────────── */

function computeTooltipStyle(
  rect: DOMRect | null,
  position: string,
): React.CSSProperties {
  if (!rect || position === 'center') {
    return { top: '50%', left: '50%', transform: 'translate(-50%, -50%)' };
  }

  const gap = 16;
  const TOOLTIP_H = 220; // Approximate tooltip height
  const TOOLTIP_W = 380;
  const vw = window.innerWidth;
  const vh = window.innerHeight;

  let style: React.CSSProperties = {};

  switch (position) {
    case 'bottom': {
      let top = rect.bottom + gap;
      // If it would go below viewport, flip to top
      if (top + TOOLTIP_H > vh - 16) {
        top = Math.max(16, rect.top - gap - TOOLTIP_H);
      }
      style.top = top;
      style.left = rect.left + rect.width / 2;
      style.transform = 'translateX(-50%)';
      break;
    }
    case 'top': {
      let top = rect.top - gap - TOOLTIP_H;
      // If it would go above viewport, flip to bottom
      if (top < 16) {
        top = rect.bottom + gap;
      }
      style.top = top;
      style.left = rect.left + rect.width / 2;
      style.transform = 'translateX(-50%)';
      break;
    }
    case 'right': {
      let top = rect.top + rect.height / 2;
      // Clamp vertically
      top = Math.max(TOOLTIP_H / 2 + 16, Math.min(vh - TOOLTIP_H / 2 - 16, top));
      style.top = top;
      style.left = rect.right + gap;
      style.transform = 'translateY(-50%)';
      // If it would go off right edge, flip to left
      if (rect.right + gap + TOOLTIP_W > vw - 16) {
        style.left = undefined;
        style.right = vw - rect.left + gap;
      }
      break;
    }
    case 'left': {
      let top = rect.top + rect.height / 2;
      top = Math.max(TOOLTIP_H / 2 + 16, Math.min(vh - TOOLTIP_H / 2 - 16, top));
      style.top = top;
      style.right = vw - rect.left + gap;
      style.transform = 'translateY(-50%)';
      // If it would go off left edge, flip to right
      if (vw - rect.left + gap + TOOLTIP_W > vw - 16) {
        style.right = undefined;
        style.left = rect.right + gap;
      }
      break;
    }
  }

  // Horizontal clamp: ensure tooltip stays within viewport
  if (style.left != null && typeof style.left === 'number') {
    const halfW = TOOLTIP_W / 2;
    if (style.left - halfW < 16) style.left = halfW + 16;
    if (style.left + halfW > vw - 16) style.left = vw - halfW - 16;
  }

  return style;
}
