import React, { useEffect, useRef, useState } from 'react';
import {
  Camera, AlertTriangle, FileText, Users, Brain, ChevronRight,
  ArrowUpRight, ShieldCheck, Lock, MonitorCheck, Zap, ScanLine, Gauge, BarChart3,
  Layers, CheckCircle2, HelpCircle,
  Activity, Eye, Cpu, Radio, Building2, Globe, ArrowRight, Play,
} from 'lucide-react';
import { Link, useNavigate } from 'react-router';
import Logo from '../components/common/Logo';
import { useAuth } from '../auth/AuthContext';

/* ── Intersection Observer for scroll-reveal ───────────────────── */
const useIntersectionObserver = (options = { threshold: 0.1 }) => {
  const ref = useRef<HTMLDivElement>(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        setIsVisible(true);
        observer.unobserve(entry.target);
      }
    }, options);
    const currentRef = ref.current;
    if (currentRef) observer.observe(currentRef);
    return () => { if (currentRef) observer.unobserve(currentRef); };
  }, []);

  return [ref, isVisible] as const;
};

const AnimatedSection = ({ children, className = '', delay = 0 }: { children: React.ReactNode; className?: string; delay?: number }) => {
  const [ref, isVisible] = useIntersectionObserver();
  return (
    <div
      ref={ref as React.RefObject<HTMLDivElement>}
      className={`transition-all duration-700 ease-out ${
        isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-12'
      } ${className}`}
      style={{ transitionDelay: `${delay}ms` }}
    >
      {children}
    </div>
  );
};

/* ── Data ──────────────────────────────────────────────────────── */
const STATS = [
  { value: '33', label: 'Skeletal Landmarks Tracked', icon: Activity },
  { value: '7', label: 'Task Classes Recognized', icon: AlertTriangle },
  { value: '24/7', label: 'Real-time Monitoring', icon: Eye },
  { value: 'RULA/REBA', label: 'Informed Risk Scoring', icon: ShieldCheck },
];

const TECH_FEATURES = [
  {
    icon: Radio,
    title: '33-Point Pose Estimation',
    description: 'MediaPipe-based skeletal tracking extracts 33 landmarks per frame, computing joint angles, velocity, and sustained tension in real time.',
  },
  {
    icon: Activity,
    title: 'RULA/REBA-Informed Scoring',
    description: 'Risk assessment follows Rapid Upper Limb Assessment and Rapid Entire Body Assessment methods — validated ergonomic standards, not arbitrary thresholds.',
  },
  {
    icon: Brain,
    title: 'Task-Aware Risk Adjustment',
    description: 'Classifies the current task (assembly, lifting, reaching, etc.) and adjusts risk thresholds accordingly — a lifting task has different limits than inspection.',
  },
];

const COMMAND_CARDS = [
  {
    icon: BarChart3,
    title: 'Executive Dashboard',
    description: 'Factory-wide risk overview with worker status, department heatmaps, and cross-session trend analytics for safety managers.',
    image: '/images/command-center-monitors.png',
  },
  {
    icon: Radio,
    title: 'Live Monitoring',
    description: 'Real-time pose skeleton overlay on camera feeds with per-joint risk coloring, task recognition, and instant alert generation.',
    image: '/images/robotic-arm-strain.png',
  },
  {
    icon: Brain,
    title: 'AI Insights Engine',
    description: 'Context-aware corrective action suggestions based on RULA/REBA scoring, task type, fatigue level, and exposure duration.',
    image: '/images/tablet-skeleton-assessment.png',
  },
];

const HOW_IT_WORKS = [
  { step: '01', title: 'Camera Capture', description: 'Standard CCTV cameras capture worker posture at individual stations — no wearables, no special hardware.' },
  { step: '02', title: 'Pose Estimation', description: 'Our CV engine extracts 33 skeletal landmarks per frame, computing joint angles, velocity, and tension in real time.' },
  { step: '03', title: 'Risk Scoring', description: 'Context-aware RULA/REBA scoring classifies posture risk per task, adjusted for fatigue, duration, and task type.' },
  { step: '04', title: 'Alerts & Recommendations', description: 'Managers receive real-time alerts when risky posture is sustained, with corrective action suggestions for workers.' },
];

const FEATURE_HIGHLIGHTS = [
  {
    icon: ShieldCheck,
    title: 'No Wearables Required',
    description: 'Workers are monitored through standard webcam or CCTV. No hardware to wear, no batteries to charge, no compliance burden.',
  },
  {
    icon: MonitorCheck,
    title: 'RULA/REBA-Informed Scoring',
    description: 'Risk assessment based on validated ergonomic methods — Rapid Upper Limb Assessment and Rapid Entire Body Assessment — not arbitrary thresholds.',
  },
  {
    icon: Eye,
    title: 'Real-Time Alerts & Recommendations',
    description: 'Get instant alerts when risky posture is sustained, with corrective action suggestions for workers and supervisors.',
  },
];

/* ── Animated Counter ─────────────────────────────────────────── */
function AnimatedCounter({ target, suffix = '' }: { target: string; suffix?: string }) {
  const [count, setCount] = useState(0);
  const [visible, setVisible] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const numericTarget = parseInt(target.replace(/[^0-9]/g, ''), 10);

  useEffect(() => {
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting && !visible) setVisible(true);
    }, { threshold: 0.3 });
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, [visible]);

  useEffect(() => {
    if (!visible || isNaN(numericTarget) || numericTarget === 0) {
      setCount(0);
      return;
    }
    const duration = 1500;
    const start = Date.now();
    const animate = () => {
      const elapsed = Date.now() - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setCount(Math.round(numericTarget * eased));
      if (progress < 1) requestAnimationFrame(animate);
    };
    requestAnimationFrame(animate);
  }, [visible, numericTarget]);

  if (isNaN(numericTarget) || numericTarget === 0) {
    return <span ref={ref}>{target}</span>;
  }

  return (
    <span ref={ref}>
      {target.includes('+') ? `${count}+` : target.includes('/') ? target : `${count}${suffix}`}
    </span>
  );
}

/* ── Interactive Demo Section ──────────────────────────────────── */

const DEMO_VIEWS = [
  {
    id: 'dashboard',
    title: 'Executive Dashboard',
    description: 'Factory-wide risk overview with worker status, department heatmaps, and trend analytics for safety managers.',
    image: '/images/dashboard-admin-full.png',
    stats: ['Real-time risk scores', 'Worker tracking', 'Trend analysis'],
  },
  {
    id: 'monitoring',
    title: 'Live Monitoring',
    description: 'Real-time pose skeleton overlay on camera feeds with per-joint risk coloring and instant alert generation.',
    image: '/images/live_camera.png',
    stats: ['33-point pose tracking', 'Risk scoring', 'Live alerts'],
  },
  {
    id: 'reports',
    title: 'Compliance Reports',
    description: 'Auto-generated PDF/CSV reports with posture scores, risk history, and audit-ready evidence packages.',
    image: '/images/dashboard-operator.png',
    stats: ['PDF export', 'CSV data', 'Audit trail'],
  },
];

function InteractiveDemoSection() {
  const [activeView, setActiveView] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Auto-rotate every 5 seconds when playing
  useEffect(() => {
    if (isPlaying) {
      timerRef.current = setInterval(() => {
        setActiveView(prev => (prev + 1) % DEMO_VIEWS.length);
      }, 5000);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [isPlaying]);

  const view = DEMO_VIEWS[activeView];

  return (
    <section className="relative z-10 py-20 lg:py-28">
      <div className="max-w-7xl mx-auto px-6">
        <AnimatedSection>
          <div className="text-center mb-12">
            <p className="text-[10px] font-bold uppercase tracking-widest text-blue-400 mb-3">Live Demo</p>
            <h2 className="text-3xl sm:text-4xl font-bold text-white">
              See ErgoVigilance in Action.
            </h2>
            <p className="text-base text-slate-400 mt-4 max-w-2xl mx-auto">
              Real screenshots from the platform — dashboard, live monitoring, and compliance reports.
            </p>
          </div>
        </AnimatedSection>

        <AnimatedSection delay={200}>
          <div className="relative">
            {/* View tabs */}
            <div className="flex items-center justify-center gap-2 mb-6">
              {DEMO_VIEWS.map((v, i) => (
                <button
                  key={v.id}
                  onClick={() => { setActiveView(i); setIsPlaying(false); }}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                    i === activeView
                      ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/20'
                      : 'bg-white/5 text-slate-400 hover:bg-white/10 hover:text-white border border-white/10'
                  }`}
                >
                  {v.title}
                </button>
              ))}
              <button
                onClick={() => setIsPlaying(!isPlaying)}
                className={`ml-2 px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                  isPlaying
                    ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                    : 'bg-white/5 text-slate-400 border border-white/10 hover:bg-white/10'
                }`}
              >
                {isPlaying ? 'Pause' : 'Auto-play'}
              </button>
            </div>

            {/* Screenshot display */}
            <div className="relative rounded-2xl overflow-hidden border border-white/10 bg-white/[0.02] shadow-2xl shadow-blue-500/5">
              <img
                src={view.image}
                alt={view.title}
                className="w-full h-auto max-h-[500px] object-cover object-top"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-[#10131a]/80 via-transparent to-transparent" />

              {/* Info overlay */}
              <div className="absolute bottom-0 left-0 right-0 p-6">
                <div className="flex items-end justify-between">
                  <div>
                    <h3 className="text-xl font-bold text-white mb-1">{view.title}</h3>
                    <p className="text-sm text-slate-300 max-w-lg">{view.description}</p>
                  </div>
                  <div className="hidden sm:flex items-center gap-2">
                    {view.stats.map((stat) => (
                      <span key={stat} className="px-2 py-1 rounded bg-white/10 text-[10px] text-white/70">
                        {stat}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {/* Navigation dots */}
              <div className="absolute bottom-6 right-6 flex items-center gap-1.5">
                {DEMO_VIEWS.map((_, i) => (
                  <button
                    key={i}
                    onClick={() => { setActiveView(i); setIsPlaying(false); }}
                    className={`w-2 h-2 rounded-full transition-all ${
                      i === activeView ? 'bg-blue-400 w-4' : 'bg-white/30 hover:bg-white/50'
                    }`}
                  />
                ))}
              </div>
            </div>
          </div>
        </AnimatedSection>
      </div>
    </section>
  );
}

/* ── Page ──────────────────────────────────────────────────────── */export default function LandingPage() {

  const { demoLogin } = useAuth();
  const navigate = useNavigate();
  const [demoLoading, setDemoLoading] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const handleTryDemo = async () => {
    if (demoLoading) return;
    setDemoLoading(true);
    try {
      await demoLogin();
      // Navigate to live monitoring so the customer immediately sees the product in action
      navigate('/monitoring');
    } catch (err) {
      console.error('Demo login failed:', err);
      alert('Demo mode requires the backend server to be running. Please start the backend and try again.');
    } finally {
      setDemoLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#10131a] text-white relative overflow-x-hidden">

      {/* ── Ambient background glows ──────────────────────────────── */}
      <div className="fixed inset-0 pointer-events-none z-0">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[900px] h-[600px] bg-blue-500/[0.04] blur-[140px] rounded-full" />
        <div className="absolute bottom-0 right-1/4 w-[600px] h-[500px] bg-cyan-500/[0.03] blur-[120px] rounded-full" />
        <div className="absolute top-1/3 left-0 w-[400px] h-[400px] bg-primary/[0.03] blur-[100px] rounded-full" />
      </div>

      {/* ══════════════════════════════════════════════════════════════
          NAVIGATION
         ══════════════════════════════════════════════════════════════ */}
      <nav className="sticky top-0 z-50 bg-[#10131a]/80 backdrop-blur-xl border-b border-white/5">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3 group">
            <Logo className="h-10 w-auto" variant="light" />
          </Link>
          <div className="hidden md:flex items-center gap-8">
            <a href="#solutions" className="text-sm text-slate-400 hover:text-white transition-colors">Solutions</a>
            <a href="#technology" className="text-sm text-slate-400 hover:text-white transition-colors">Technology</a>
            <a href="#how-it-works" className="text-sm text-slate-400 hover:text-white transition-colors">How It Works</a>
            <a href="#deployment-options" className="text-sm text-slate-400 hover:text-white transition-colors">Deploy</a>
            <a href="#command-center" className="text-sm text-slate-400 hover:text-white transition-colors">Command Center</a>
            <Link to="/pricing" className="text-sm text-slate-400 hover:text-white transition-colors">Pricing</Link>
            <Link
              to="/request-pilot"
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-blue-600 text-sm font-semibold text-white hover:bg-blue-500 transition-all hover:shadow-lg hover:shadow-blue-500/25 active:scale-[0.97]"
            >
              Request a Pilot
              <ArrowRight className="w-4 h-4" />
            </Link>
            <Link
              to="/login"
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl border border-white/10 text-sm text-slate-400 hover:text-white hover:border-white/20 transition-all"
            >
              Log In
            </Link>
          </div>
          <button className="md:hidden text-slate-400 hover:text-white" onClick={() => setMobileMenuOpen(!mobileMenuOpen)}>
            {mobileMenuOpen ? (
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            ) : (
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            )}
          </button>
        </div>
        {/* Mobile menu drawer */}
        {mobileMenuOpen && (
          <div className="md:hidden border-t border-white/5 bg-[#10131a]/95 backdrop-blur-xl">
            <div className="max-w-7xl mx-auto px-6 py-4 flex flex-col gap-3">
              <a href="#solutions" onClick={() => setMobileMenuOpen(false)} className="text-sm text-slate-400 hover:text-white transition-colors py-2">Solutions</a>
              <a href="#technology" onClick={() => setMobileMenuOpen(false)} className="text-sm text-slate-400 hover:text-white transition-colors py-2">Technology</a>
              <a href="#how-it-works" onClick={() => setMobileMenuOpen(false)} className="text-sm text-slate-400 hover:text-white transition-colors py-2">How It Works</a>
              <a href="#deployment-options" onClick={() => setMobileMenuOpen(false)} className="text-sm text-slate-400 hover:text-white transition-colors py-2">Deploy</a>
              <a href="#command-center" onClick={() => setMobileMenuOpen(false)} className="text-sm text-slate-400 hover:text-white transition-colors py-2">Command Center</a>
              <Link to="/pricing" onClick={() => setMobileMenuOpen(false)} className="text-sm text-slate-400 hover:text-white transition-colors py-2">Pricing</Link>
              <div className="flex flex-col gap-2 pt-2 border-t border-white/5">
                <button
                  onClick={() => { setMobileMenuOpen(false); handleTryDemo(); }}
                  disabled={demoLoading}
                  className="flex items-center justify-center gap-2 px-5 py-3 rounded-xl bg-gradient-to-r from-blue-600 to-cyan-500 text-sm font-bold text-white"
                >
                  <Play className="w-4 h-4" fill="currentColor" />
                  {demoLoading ? 'Starting...' : 'Try Demo'}
                </button>
                <Link to="/request-pilot" onClick={() => setMobileMenuOpen(false)} className="flex items-center justify-center gap-2 px-5 py-3 rounded-xl bg-blue-600 text-sm font-bold text-white">
                  Request a Pilot
                  <ArrowRight className="w-4 h-4" />
                </Link>
                <Link to="/login" onClick={() => setMobileMenuOpen(false)} className="flex items-center justify-center gap-2 px-5 py-3 rounded-xl border border-white/10 text-sm text-slate-400 hover:text-white">
                  Log In
                </Link>
              </div>
            </div>
          </div>
        )}
      </nav>

      {/* ══════════════════════════════════════════════════════════════
          HERO — Command Center 4-panel image
         ══════════════════════════════════════════════════════════════ */}
      <section className="relative z-10">
        <div className="max-w-7xl mx-auto px-6 pt-12 pb-16 lg:pt-20 lg:pb-24">
          {/* Top: Copy + CTAs */}
          <div className="max-w-4xl mx-auto text-center space-y-8">
            <AnimatedSection delay={100}>                <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-blue-500/20 bg-blue-500/[0.08] text-xs font-semibold text-blue-400 uppercase tracking-wider">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                System Online
              </div>
            </AnimatedSection>
            <AnimatedSection delay={200}>
              <h1 className="text-4xl sm:text-5xl lg:text-[3.5rem] font-extrabold leading-[1.1] tracking-tight text-white">
                Industrial Safety,{' '}
                <span className="bg-gradient-to-r from-blue-400 via-cyan-300 to-blue-400 bg-clip-text text-transparent">
                  Reimagined through AI.
                </span>
              </h1>
            </AnimatedSection>
            <AnimatedSection delay={300}>
              <p className="text-lg text-slate-400 leading-relaxed max-w-2xl mx-auto">
                Real-time posture analysis and ergonomic risk mitigation for the modern
                enterprise. Powered by advanced Computer Vision and Machine Learning.
              </p>
            </AnimatedSection>
            <AnimatedSection delay={400}>
              <div className="flex items-center justify-center gap-4 flex-wrap">
                <button
                  onClick={handleTryDemo}
                  disabled={demoLoading}
                  className="flex items-center gap-2.5 px-7 py-3.5 rounded-xl bg-gradient-to-r from-blue-600 to-cyan-500 text-sm font-bold text-white hover:from-blue-500 hover:to-cyan-400 transition-all hover:shadow-xl hover:shadow-blue-500/25 active:scale-[0.97] disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {demoLoading ? (
                    <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  ) : (
                    <Play className="w-4 h-4" fill="currentColor" />
                  )}
                  {demoLoading ? 'Starting...' : 'Try Demo'}
                </button>
                <Link
                  to="/request-pilot"
                  className="flex items-center gap-2.5 px-7 py-3.5 rounded-xl bg-blue-600 text-sm font-bold text-white hover:bg-blue-500 transition-all hover:shadow-xl hover:shadow-blue-500/25 active:scale-[0.97]"
                >
                  Request a Pilot
                  <ArrowRight className="w-4 h-4" />
                </Link>
              </div>
            </AnimatedSection>
            <AnimatedSection delay={500}>
              <div className="flex items-center justify-center gap-6 pt-2">
                {[
                  { icon: MonitorCheck, label: 'No Wearables' },
                  { icon: ShieldCheck, label: 'RULA/REBA Based' },
                  { icon: Eye, label: 'Real-time Alerts' },
                ].map(({ icon: Icon, label }) => (
                  <div key={label} className="flex items-center gap-2 text-xs text-slate-500">
                    <Icon className="w-3.5 h-3.5 text-blue-400/60" />
                    {label}
                  </div>
                ))}
              </div>
            </AnimatedSection>
          </div>

          {/* Bottom: Image (below text) */}
          <AnimatedSection delay={600}>
            <div className="relative mt-12 lg:mt-16 max-w-5xl mx-auto">
              <div className="absolute -inset-4 bg-blue-500/[0.06] blur-3xl rounded-full" />
              <div className="relative rounded-2xl overflow-hidden border border-white/10 shadow-2xl shadow-blue-500/10">
                <img
                  src="/images/command-center-monitors.png"
                  alt="Multi-camera factory monitoring command center with AI pose detection overlays"
                  className="w-full h-auto object-cover"
                  style={{ maxHeight: 520 }}
                />
                <div className="absolute inset-0 bg-gradient-to-t from-[#10131a]/60 via-transparent to-[#10131a]/30" />
                {/* Floating live badge */}
                <div className="absolute top-4 left-4 flex items-center gap-2 bg-black/60 backdrop-blur-sm px-3 py-1.5 rounded-lg border border-cyan-500/30">
                  <div className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
                  <span className="text-[10px] font-bold text-cyan-400 uppercase tracking-wider">Live Analysis</span>
                </div>
                {/* Floating telemetry badges */}
                <div className="absolute top-4 right-4 flex items-center gap-2 bg-black/60 backdrop-blur-sm px-3 py-1.5 rounded-lg border border-emerald-500/30">
                  <span className="text-[10px] font-bold text-emerald-400">SAFE ZONE: POSTURE OPTIMAL</span>
                </div>
                <div className="absolute bottom-4 left-4 right-4 flex items-center justify-between bg-black/60 backdrop-blur-sm px-4 py-2.5 rounded-lg border border-white/10">
                  <div className="flex items-center gap-5">
                    <div>
                      <span className="text-[9px] text-slate-400 block">Risk Level</span>
                      <span className="text-xs font-bold text-emerald-400">LOW</span>
                    </div>
                    <div className="w-px h-6 bg-white/10" />
                    <div>
                      <span className="text-[9px] text-slate-400 block">Workers Tracked</span>
                      <span className="text-xs font-bold text-cyan-400">4</span>
                    </div>
                    <div className="w-px h-6 bg-white/10" />
                    <div>
                      <span className="text-[9px] text-slate-400 block">Confidence</span>
                      <span className="text-xs font-bold text-blue-400">96%</span>
                    </div>
                  </div>
                  <span className="text-[9px] text-slate-500 hidden sm:block">33 landmarks · 12 features · every frame</span>
                </div>
              </div>
            </div>
          </AnimatedSection>
        </div>
      </section>

      {/* ══════════════════════════════════════════════════════════════
          GLOBAL DEPLOYMENT STATS
         ══════════════════════════════════════════════════════════════ */}
      <section className="relative z-10 border-y border-white/5 bg-white/[0.015]">
        <div className="max-w-7xl mx-auto px-6">
          <div className="py-8 border-b border-white/5">
            <p className="text-[10px] font-bold uppercase tracking-widest text-blue-400 mb-2">System Capabilities</p>
            <p className="text-2xl sm:text-3xl font-bold text-white">
              Computer Vision-Powered Ergonomic Assessment —{' '}
              <span className="text-blue-400">Ready for Pilot Deployment.</span>
            </p>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 divide-x divide-white/5">
            {STATS.map((stat) => (
              <AnimatedSection key={stat.label}>
                <div className="py-8 px-6 text-center group cursor-default">
                  <stat.icon className="w-6 h-6 text-blue-400 mx-auto mb-3 group-hover:scale-110 transition-transform" />
                  <p className="text-3xl sm:text-4xl font-bold text-white mb-1"><AnimatedCounter target={stat.value} /></p>
                  <p className="text-sm text-slate-400">{stat.label}</p>
                </div>
              </AnimatedSection>
            ))}
          </div>
        </div>
      </section>

      {/* ══════════════════════════════════════════════════════════════
          INTERACTIVE DEMO — Product screenshots
         ══════════════════════════════════════════════════════════════ */}
      <InteractiveDemoSection />

      {/* ══════════════════════════════════════════════════════════════
          CORE TECHNOLOGY — Robotic arm + strain index image
         ══════════════════════════════════════════════════════════════ */}
      <section className="relative z-10 py-20 lg:py-28" id="technology">
        <div className="max-w-7xl mx-auto px-6 grid lg:grid-cols-2 gap-16 items-center">
          {/* Left — image */}
          <AnimatedSection>
            <div className="relative">
              <div className="absolute -inset-4 bg-blue-500/[0.04] blur-2xl rounded-2xl" />
              <div className="relative rounded-2xl overflow-hidden border border-white/10">
                <img
                  src="/images/robotic-arm-strain.png"
                  alt="Industrial robotic arm with ergonomic strain index display showing real-time force sensing"
                  className="w-full h-auto object-cover"
                  style={{ maxHeight: 480 }}
                />
                <div className="absolute inset-0 bg-gradient-to-r from-[#10131a]/60 via-transparent to-transparent" />
                {/* Overlay data panel */}
                <div className="absolute top-4 left-4 bg-black/70 backdrop-blur-sm rounded-xl border border-white/10 p-4 w-56">
                  <p className="text-[9px] text-slate-400 uppercase tracking-wider mb-3">Pose Analysis</p>
                  <div className="space-y-2">
                    {[
                      { label: 'Neck Angle', val: '18.4°', color: 'bg-emerald-400' },
                      { label: 'Trunk Angle', val: '24.1°', color: 'bg-amber-400' },
                      { label: 'L. Shoulder', val: '42.3°', color: 'bg-red-400' },
                      { label: 'Knee Angle', val: '162°', color: 'bg-emerald-400' },
                    ].map(({ label, val, color }) => (
                      <div key={label} className="flex items-center justify-between">
                        <span className="text-[10px] text-slate-400">{label}</span>
                        <div className="flex items-center gap-1.5">
                          <div className={`w-1.5 h-1.5 rounded-full ${color}`} />
                          <span className="text-[10px] font-mono text-white">{val}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                {/* Floating strain index badge */}
                <div className="absolute bottom-4 right-4 bg-black/70 backdrop-blur-sm rounded-xl border border-emerald-500/30 px-3 py-2">
                  <span className="text-[9px] text-slate-400 block">Ergonomic Strain Index</span>
                  <span className="text-lg font-bold text-emerald-400">2.3</span>
                  <span className="text-[10px] text-emerald-400 ml-1">SAFE</span>
                </div>
              </div>
            </div>
          </AnimatedSection>

          {/* Right — text */}
          <div className="space-y-8">
            <AnimatedSection delay={100}>
              <div>
                <p className="text-[10px] font-bold uppercase tracking-widest text-blue-400 mb-3">Core Technology</p>
                <h2 className="text-3xl sm:text-4xl font-bold text-white mb-4">
                  Computer Vision & Pose Estimation
                </h2>
                <p className="text-base text-slate-400 leading-relaxed">
                  Our proprietary spatial computing engine processes millions of positional data points per second.
                  It transforms standard CCTV into actionable biomechanical insights without requiring wearables.
                </p>
              </div>
            </AnimatedSection>
            <div className="space-y-6">
              {TECH_FEATURES.map((feature, i) => (
                <AnimatedSection key={feature.title} delay={200 + i * 100}>
                  <div className="flex items-start gap-4 group">
                    <div className="w-11 h-11 rounded-xl bg-blue-500/[0.08] border border-blue-500/20 flex items-center justify-center shrink-0 group-hover:bg-blue-500/[0.15] transition-colors">
                      <feature.icon className="w-5 h-5 text-blue-400" />
                    </div>
                    <div>
                      <h3 className="text-base font-bold text-white mb-1">{feature.title}</h3>
                      <p className="text-sm text-slate-400 leading-relaxed">{feature.description}</p>
                    </div>
                  </div>
                </AnimatedSection>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ══════════════════════════════════════════════════════════════
          HOW IT WORKS — 4-step pipeline
         ══════════════════════════════════════════════════════════════ */}
      <section className="relative z-10 py-20 lg:py-28 bg-white/[0.015] border-y border-white/5" id="how-it-works">
        <div className="max-w-7xl mx-auto px-6">
          <AnimatedSection>
            <div className="text-center mb-16">
              <p className="text-[10px] font-bold uppercase tracking-widest text-blue-400 mb-3">Pipeline</p>
              <h2 className="text-3xl sm:text-4xl font-bold text-white">
                From Camera Feed to Actionable Insight.
              </h2>
              <p className="text-base text-slate-400 mt-4 max-w-2xl mx-auto">
                A four-stage processing pipeline that transforms raw video into ergonomic intelligence — fully automated, zero human intervention required.
              </p>
            </div>
          </AnimatedSection>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6 relative">
            <div className="hidden lg:block absolute top-14 left-[12.5%] right-[12.5%] h-px bg-gradient-to-r from-blue-500/20 via-blue-500/40 to-blue-500/20" />
            {HOW_IT_WORKS.map((item, i) => (
              <AnimatedSection key={item.step} delay={i * 120}>
                <div className="relative text-center group">
                  <div className="w-12 h-12 rounded-2xl bg-blue-600 text-white font-bold text-sm flex items-center justify-center mx-auto mb-5 relative z-10 shadow-lg shadow-blue-600/30 group-hover:scale-110 transition-transform">
                    {item.step}
                  </div>
                  <h3 className="text-base font-bold text-white mb-2">{item.title}</h3>
                  <p className="text-sm text-slate-400 leading-relaxed">{item.description}</p>
                </div>
              </AnimatedSection>
            ))}
          </div>
        </div>
      </section>

      {/* ══════════════════════════════════════════════════════════════
          WHY ERGOVIGILANCE — 3 feature highlights
         ══════════════════════════════════════════════════════════════ */}
      <section className="relative z-10 py-20 lg:py-28" id="solutions">
        <div className="max-w-7xl mx-auto px-6">
          <AnimatedSection>
            <div className="text-center mb-16">
              <p className="text-[10px] font-bold uppercase tracking-widest text-blue-400 mb-3">Why ErgoVigilance</p>
              <h2 className="text-3xl sm:text-4xl font-bold text-white">
                Why ErgoVigilance.
              </h2>
            </div>
          </AnimatedSection>
          <div className="grid md:grid-cols-3 gap-8">
            {FEATURE_HIGHLIGHTS.map((item, i) => (
              <AnimatedSection key={item.title} delay={i * 100}>
                <div className="text-center space-y-4">
                  <div className="w-14 h-14 rounded-2xl bg-blue-500/[0.08] border border-blue-500/20 flex items-center justify-center mx-auto">
                    <item.icon className="w-7 h-7 text-blue-400" />
                  </div>
                  <h3 className="text-lg font-bold text-white">{item.title}</h3>
                  <p className="text-sm text-slate-400 leading-relaxed">{item.description}</p>
                </div>
              </AnimatedSection>
            ))}
          </div>
        </div>
      </section>

      {/* ══════════════════════════════════════════════════════════════
          DEPLOYMENT OPTIONS — On-Premise + Cloud
         ══════════════════════════════════════════════════════════════ */}
      <section className="relative z-10 py-20 lg:py-28 bg-white/[0.015] border-y border-white/5" id="deployment-options">
        <div className="max-w-7xl mx-auto px-6">
          <AnimatedSection>
            <div className="text-center mb-16">
              <p className="text-[10px] font-bold uppercase tracking-widest text-cyan-400 mb-3">Deploy Your Way</p>
              <h2 className="text-3xl sm:text-4xl font-bold text-white">
                Two Cores. One Dashboard.
              </h2>
              <p className="mt-4 text-slate-400 max-w-2xl mx-auto">
                Choose on-premise for maximum accuracy, or cloud for zero-install factory deployment.
                Both connect to the same real-time dashboard.
              </p>
            </div>
          </AnimatedSection>
          <div className="grid md:grid-cols-2 gap-8">
            <AnimatedSection delay={0}>
              <div className="p-8 rounded-2xl bg-gradient-to-br from-blue-500/[0.08] to-blue-500/[0.02] border border-blue-500/20">
                <div className="flex items-center gap-3 mb-6">
                  <div className="w-12 h-12 rounded-xl bg-blue-500/20 flex items-center justify-center">
                    <span className="text-2xl">🖥</span>
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-white">MediaPipe Core</h3>
                    <p className="text-xs text-blue-400">On-Premise</p>
                  </div>
                </div>
                <ul className="space-y-3 text-sm text-slate-300">
                  <li className="flex items-start gap-2">
                    <span className="text-blue-400 mt-0.5">✓</span>
                    <span>33-landmark MediaPipe pose estimation</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-blue-400 mt-0.5">✓</span>
                    <span>Real-time processing &lt;100ms latency</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-blue-400 mt-0.5">✓</span>
                    <span>USB webcam or local video input</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-blue-400 mt-0.5">✓</span>
                    <span>Full RULA/REBA with 33 keypoints</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-blue-400 mt-0.5">✓</span>
                    <span>Worker video never leaves the factory</span>
                  </li>
                </ul>
                <div className="mt-6 pt-6 border-t border-blue-500/20">
                  <p className="text-xs text-slate-500">Best for: Safety-critical environments, high-accuracy requirements</p>
                </div>
              </div>
            </AnimatedSection>
            <AnimatedSection delay={100}>
              <div className="p-8 rounded-2xl bg-gradient-to-br from-cyan-500/[0.08] to-cyan-500/[0.02] border border-cyan-500/20">
                <div className="flex items-center gap-3 mb-6">
                  <div className="w-12 h-12 rounded-xl bg-cyan-500/20 flex items-center justify-center">
                    <span className="text-2xl">☁</span>
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-white">YOLO Cloud Core</h3>
                    <p className="text-xs text-cyan-400">Zero-Install SaaS</p>
                  </div>
                </div>
                <ul className="space-y-3 text-sm text-slate-300">
                  <li className="flex items-start gap-2">
                    <span className="text-cyan-400 mt-0.5">✓</span>
                    <span>YOLOv8-pose + ByteTrack worker tracking</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-cyan-400 mt-0.5">✓</span>
                    <span>Just share CCTV RTSP URLs — no on-site install</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-cyan-400 mt-0.5">✓</span>
                    <span>Scales to 100+ cameras across factories</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-cyan-400 mt-0.5">✓</span>
                    <span>Multi-factory dashboard with PDF/CSV reports</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-cyan-400 mt-0.5">✓</span>
                    <span>Monthly SaaS subscription per camera</span>
                  </li>
                </ul>
                <div className="mt-6 pt-6 border-t border-cyan-500/20">
                  <p className="text-xs text-slate-500">Best for: Mass deployment, multiple factories, easy installation</p>
                </div>
              </div>
            </AnimatedSection>
          </div>
        </div>
      </section>

      {/* ══════════════════════════════════════════════════════════════
          COMMAND CENTER — Cards with images
         ══════════════════════════════════════════════════════════════ */}
      <section className="relative z-10 py-20 lg:py-28 bg-white/[0.015] border-y border-white/5" id="command-center">
        <div className="max-w-7xl mx-auto px-6">
          <AnimatedSection>
            <div className="text-center mb-16">
              <p className="text-[10px] font-bold uppercase tracking-widest text-blue-400 mb-3">Command Center</p>
              <h2 className="text-3xl sm:text-4xl font-bold text-white">
                Intelligence at Every Level of the Enterprise.
              </h2>
            </div>
          </AnimatedSection>
          <div className="grid md:grid-cols-3 gap-6">
            {COMMAND_CARDS.map((card, i) => (
              <AnimatedSection key={card.title} delay={i * 100}>
                <div className="group relative bg-white/[0.03] border border-white/10 rounded-2xl overflow-hidden hover:border-blue-500/30 hover:bg-blue-500/[0.04] transition-all duration-300 h-full flex flex-col">
                  {/* Card image */}
                  <div className="relative h-48 overflow-hidden">
                    <img
                      src={card.image}
                      alt={card.title}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-[#10131a] via-[#10131a]/40 to-transparent" />
                    <div className="absolute bottom-3 left-4">
                      <div className="w-10 h-10 rounded-xl bg-blue-500/[0.15] border border-blue-500/30 flex items-center justify-center backdrop-blur-sm">
                        <card.icon className="w-5 h-5 text-blue-400" />
                      </div>
                    </div>
                  </div>
                  {/* Card content */}
                  <div className="p-6 flex-1">
                    <h3 className="text-xl font-bold text-white mb-2">{card.title}</h3>
                    <p className="text-sm text-slate-400 leading-relaxed">{card.description}</p>
                  </div>
                  <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-blue-500/30 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
              </AnimatedSection>
            ))}
          </div>
        </div>
      </section>

      {/* ══════════════════════════════════════════════════════════════
          INDUSTRY INSIGHT — real EHS perspectives on CV-based ergonomics
         ══════════════════════════════════════════════════════════════ */}
      <AnimatedSection className="relative z-10 py-20 lg:py-28 bg-white/[0.015] border-y border-white/5">
        <div className="max-w-7xl mx-auto px-6">
          <AnimatedSection>
            <div className="text-center mb-16">
              <p className="text-[10px] font-bold uppercase tracking-widest text-blue-400 mb-3">Industry Insight</p>
              <h2 className="text-3xl sm:text-4xl font-bold text-white">
                What EHS Managers Say About CV-Based Ergonomics.
              </h2>
              <p className="text-base text-slate-400 mt-4 max-w-2xl mx-auto">
                Real perspectives from safety professionals using computer vision to transform ergonomic assessment.
              </p>
            </div>
          </AnimatedSection>
          <div className="grid md:grid-cols-3 gap-6">
            {/* Quote 1 — Latham Pools */}
            <AnimatedSection delay={0}>
              <div className="bg-white/[0.03] border border-white/10 rounded-2xl p-8 h-full flex flex-col">
                <svg className="w-8 h-8 text-blue-500/30 mb-4" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M14.017 21v-7.391c0-5.704 3.731-9.57 8.983-10.609l.995 2.151c-2.432.917-3.995 3.638-3.995 5.849h4v10h-9.983zm-14.017 0v-7.391c0-5.704 3.748-9.57 9-10.609l.996 2.151c-2.433.917-3.996 3.638-3.996 5.849h3.983v10h-9.983z" />
                </svg>
                <blockquote className="text-base text-slate-300 leading-relaxed flex-1">
                  "It's not just a tool for validation — it's a way to ensure our employees stay safe and healthy, which ultimately improves our bottom line."
                </blockquote>
                <div className="mt-6 pt-4 border-t border-white/5">
                  <p className="text-sm font-bold text-white">Angelica Daniels</p>
                  <p className="text-xs text-slate-400">Regional EHS Manager, Latham Pools</p>
                  <p className="text-[10px] text-blue-400/60 mt-1">91% reduction in sprains & strains with CV monitoring</p>
                </div>
              </div>
            </AnimatedSection>

            {/* Quote 2 — Pacific Southwest Container */}
            <AnimatedSection delay={100}>
              <div className="bg-white/[0.03] border border-white/10 rounded-2xl p-8 h-full flex flex-col">
                <svg className="w-8 h-8 text-blue-500/30 mb-4" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M14.017 21v-7.391c0-5.704 3.731-9.57 8.983-10.609l.995 2.151c-2.432.917-3.995 3.638-3.995 5.849h4v10h-9.983zm-14.017 0v-7.391c0-5.704 3.748-9.57 9-10.609l.996 2.151c-2.433.917-3.996 3.638-3.996 5.849h3.983v10h-9.983z" />
                </svg>
                <blockquote className="text-base text-slate-300 leading-relaxed flex-1">
                  "The software generates skeleton models, color-coded risk scores, and highlights critical angles — all in a matter of seconds. Without it, I'd only be a quarter of the way through my evaluations."
                </blockquote>
                <div className="mt-6 pt-4 border-t border-white/5">
                  <p className="text-sm font-bold text-white">Nicole Maxwell</p>
                  <p className="text-xs text-slate-400">Safety Specialist, Pacific Southwest Container</p>
                  <p className="text-[10px] text-blue-400/60 mt-1">300+ evaluations completed in months</p>
                </div>
              </div>
            </AnimatedSection>

            {/* Quote 3 — Koppers */}
            <AnimatedSection delay={200}>
              <div className="bg-white/[0.03] border border-white/10 rounded-2xl p-8 h-full flex flex-col">
                <svg className="w-8 h-8 text-blue-500/30 mb-4" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M14.017 21v-7.391c0-5.704 3.731-9.57 8.983-10.609l.995 2.151c-2.432.917-3.995 3.638-3.995 5.849h4v10h-9.983zm-14.017 0v-7.391c0-5.704 3.748-9.57 9-10.609l.996 2.151c-2.433.917-3.996 3.638-3.996 5.849h3.983v10h-9.983z" />
                </svg>
                <blockquote className="text-base text-slate-300 leading-relaxed flex-1">
                  "People really like seeing the risk scores and where they can improve. It's sparked healthy competition between sites and made ergonomics approachable."
                </blockquote>
                <div className="mt-6 pt-4 border-t border-white/5">
                  <p className="text-sm font-bold text-white">Blayne Darnell</p>
                  <p className="text-xs text-slate-400">Corporate Safety & Health Manager, Koppers</p>
                  <p className="text-[10px] text-blue-400/60 mt-1">Expanded CV monitoring across 12 global sites</p>
                </div>
              </div>
            </AnimatedSection>
          </div>
          <AnimatedSection delay={300}>
            <p className="text-center text-xs text-slate-500 mt-8">
              Quotes from EHS professionals using computer vision-based ergonomic monitoring systems. Source: TuMeke case studies.
            </p>
          </AnimatedSection>
        </div>
      </AnimatedSection>

      {/* ══════════════════════════════════════════════════════════════
          BY THE NUMBERS — Key metrics
         ══════════════════════════════════════════════════════════════ */}
      <section className="relative z-10 py-16 lg:py-20 border-t border-white/5">
        <div className="max-w-5xl mx-auto px-6">
          <AnimatedSection>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
              {[
                { value: '33', label: 'Skeletal Landmarks', suffix: '' },
                { value: '87', label: 'Ground-Truth Accuracy', suffix: '%' },
                { value: '7', label: 'Task Classes', suffix: '' },
                { value: '4', label: 'Risk Assessment Methods', suffix: '' },
              ].map((stat) => (
                <div key={stat.label}>
                  <AnimatedCounter target={stat.value} suffix={stat.suffix} />
                  <p className="text-xs text-slate-400 mt-2 uppercase tracking-wider">{stat.label}</p>
                </div>
              ))}
            </div>
          </AnimatedSection>
        </div>
      </section>

      {/* ══════════════════════════════════════════════════════════════
          CTA — Request a Pilot
         ══════════════════════════════════════════════════════════════ */}
      <section className="relative z-10 py-20 lg:py-28 border-t border-white/5">
        <div className="max-w-4xl mx-auto px-6">
          <AnimatedSection>
            <div className="relative bg-gradient-to-br from-blue-600/[0.08] via-[#10131a] to-cyan-600/[0.08] border border-blue-500/15 rounded-3xl p-12 lg:p-16 text-center overflow-hidden">
              <div className="absolute top-0 left-1/4 w-64 h-64 bg-blue-500/[0.06] blur-[80px] rounded-full" />
              <div className="absolute bottom-0 right-1/4 w-64 h-64 bg-cyan-500/[0.04] blur-[80px] rounded-full" />
              <div className="relative z-10">
                <h2 className="text-3xl sm:text-4xl font-bold text-white mb-4">
                  Ready to upgrade your facility's safety standards?
                </h2>
                <p className="text-lg text-slate-400 mb-8 max-w-2xl mx-auto">
                  Deploy with a standard webcam — no special hardware, no IT integration.
                  Start a free pilot and see real posture data from your own floor.
                </p>
                <div className="flex items-center justify-center gap-4 flex-wrap">
                  <button
                    onClick={handleTryDemo}
                    disabled={demoLoading}
                    className="inline-flex items-center gap-2.5 px-8 py-4 rounded-xl bg-gradient-to-r from-blue-600 to-cyan-500 text-base font-bold text-white hover:from-blue-500 hover:to-cyan-400 transition-all hover:shadow-xl hover:shadow-blue-500/25 hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {demoLoading ? (
                      <span className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    ) : (
                      <Play className="w-5 h-5" fill="currentColor" />
                    )}
                    {demoLoading ? 'Starting Demo...' : 'Try Demo — No Setup Required'}
                  </button>
                  <Link
                    to="/request-pilot"
                    className="inline-flex items-center gap-2 px-6 py-4 rounded-xl border border-white/15 text-base font-semibold text-slate-300 hover:text-white hover:border-white/30 transition-all"
                  >
                    Request a Pilot
                  </Link>
                </div>
                <div className="flex items-center justify-center gap-6 mt-8 text-xs text-slate-500">
                  <span className="flex items-center gap-1.5"><Lock className="w-3 h-3 text-blue-400/50" /> No Hardware Required</span>
                  <span className="flex items-center gap-1.5"><MonitorCheck className="w-3 h-3 text-blue-400/50" /> Works with Existing Cameras</span>
                  <span className="flex items-center gap-1.5"><ShieldCheck className="w-3 h-3 text-blue-400/50" /> RULA/REBA Informed</span>
                </div>
              </div>
            </div>
          </AnimatedSection>
        </div>
      </section>

      {/* ══════════════════════════════════════════════════════════════
          CHANGELOG
         ══════════════════════════════════════════════════════════════ */}
      <section className="relative z-10 py-20 border-t border-white/5">
        <div className="max-w-4xl mx-auto px-6">
          <AnimatedSection>
            <div className="text-center mb-12">
              <p className="text-[10px] font-bold uppercase tracking-widest text-blue-400 mb-3">Changelog</p>
              <h2 className="text-3xl sm:text-4xl font-bold text-white">
                What We've Built.
              </h2>
              <p className="text-base text-slate-400 mt-4">
                Transparent development — see what's new and what's coming.
              </p>
            </div>
          </AnimatedSection>

          <div className="space-y-6">
            {[
              { version: 'v1.0.0', date: 'Sep 2026', title: 'Initial Release', items: ['34-page React dashboard', 'YOLO cloud core with RTSP ingestion', 'MediaPipe on-premise engine', 'RULA/REBA risk scoring', 'Real-time pose tracking', 'PDF/CSV report export', 'Worker management', 'Alert system with email/Slack'] },
              { version: 'v0.9.0', date: 'Aug 2026', title: 'Cloud Platform', items: ['YOLOv8-pose cloud inference', 'Multi-camera RTSP support', 'API key authentication', 'PostgreSQL persistent storage', 'Webhook alert delivery', 'Model versioning & rollback', 'Data retention policies', 'Public status page'] },
              { version: 'v0.8.0', date: 'Aug 2026', title: 'ML Pipeline', items: ['10 training scripts', 'Risk classifier (94.1% F1)', 'Task classifier (97.6% F1)', '7-class task recognition', 'Feature extraction from COCO_17 keypoints', 'Synthetic data generation', 'Model comparison dashboard'] },
            ].map((release, i) => (
              <AnimatedSection key={release.version} delay={i * 100}>
                <div className="bg-white/[0.03] border border-white/10 rounded-xl p-6 hover:border-white/15 transition-colors">
                  <div className="flex items-center gap-3 mb-3">
                    <span className="px-2.5 py-1 rounded-md bg-blue-500/10 text-blue-400 text-xs font-bold font-mono">{release.version}</span>
                    <span className="text-xs text-slate-500">{release.date}</span>
                    <span className="text-sm font-semibold text-white">{release.title}</span>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                    {release.items.map((item) => (
                      <div key={item} className="flex items-start gap-2 text-xs text-slate-400">
                        <CheckCircle2 className="w-3.5 h-3.5 text-green-400 mt-0.5 shrink-0" />
                        {item}
                      </div>
                    ))}
                  </div>
                </div>
              </AnimatedSection>
            ))}
          </div>
        </div>
      </section>

      {/* ══════════════════════════════════════════════════════════════
          FOOTER
         ══════════════════════════════════════════════════════════════ */}
      <footer className="relative z-10 border-t border-white/5 bg-[#0b0e15]">
        <div className="max-w-7xl mx-auto px-6 py-16">
          <div className="grid md:grid-cols-4 gap-12">
            <div className="md:col-span-2 space-y-4">
              <Logo className="h-10 w-auto" variant="light" />
              <p className="text-sm text-slate-500 leading-relaxed">
                Pioneering Industrial Intelligence through autonomous monitoring. Protecting the workforce with technical precision.
              </p>
            </div>
            <div className="space-y-4">
              <h4 className="text-xs font-bold uppercase tracking-widest text-slate-400">Platform</h4>
              <div className="space-y-3">
                <a href="#solutions" className="block text-sm text-slate-500 hover:text-white transition-colors">Solutions</a>
                <a href="#technology" className="block text-sm text-slate-500 hover:text-white transition-colors">Technology</a>
                <Link to="/login" className="block text-sm text-slate-500 hover:text-white transition-colors">Dashboard</Link>
              </div>
            </div>
            <div className="space-y-4">
              <h4 className="text-xs font-bold uppercase tracking-widest text-slate-400">Company</h4>
              <div className="space-y-3">
                <Link to="/pricing" className="block text-sm text-slate-500 hover:text-white transition-colors">Pricing</Link>
                <Link to="/request-pilot" className="block text-sm text-slate-500 hover:text-white transition-colors">Request Pilot</Link>
                <Link to="/validation" className="block text-sm text-slate-500 hover:text-white transition-colors">Validation</Link>
                <a href="mailto:contact@ergovigilance.com" className="block text-sm text-slate-500 hover:text-white transition-colors">Contact</a>
              </div>
            </div>
          </div>
          <div className="mt-12 pt-8 border-t border-white/5 flex flex-col sm:flex-row items-center justify-between gap-4">
            <p className="text-xs text-slate-600">
              &copy; 2026 ErgoVigilance Systems. All rights reserved.
            </p>
            <div className="flex items-center gap-4 text-xs text-slate-600">
              <span className="flex items-center gap-1.5"><MonitorCheck className="w-3 h-3" /> No Wearables</span>
              <span className="flex items-center gap-1.5"><ShieldCheck className="w-3 h-3" /> RULA/REBA Based</span>
              <span className="flex items-center gap-1.5"><Eye className="w-3 h-3" /> Real-time Alerts</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
