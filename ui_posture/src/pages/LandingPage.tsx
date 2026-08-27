import React, { useEffect, useRef, useState } from 'react';
import {
  Camera, AlertTriangle, FileText, Users, Brain, ChevronRight,
  ArrowUpRight, ShieldCheck, Lock, MonitorCheck, Zap, ScanLine, Gauge, BarChart3,
  Layers, CheckCircle2, HelpCircle,
  Activity, Eye, Cpu, Radio, Building2, Globe,
} from 'lucide-react';
import { Link } from 'react-router';

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

    return () => {
      if (currentRef) observer.unobserve(currentRef);
    };
  }, []);

  return [ref, isVisible] as const;
};

const AnimatedSection = ({ children, className = '' }: { children: React.ReactNode; className?: string }) => {
  const [ref, isVisible] = useIntersectionObserver();
  return (
    <div
      ref={ref as React.RefObject<HTMLDivElement>}
      className={`transition-all duration-700 ease-out ${
        isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-12'
      } ${className}`}
    >
      {children}
    </div>
  );
};

// ── Stats Data ────────────────────────────────────────────────────
const STATS = [
  { value: '98%', label: 'Detection Accuracy', icon: Activity },
  { value: '35%', label: 'Reduction in MSDs', icon: AlertTriangle },
  { value: '24/7', label: 'Real-time Monitoring', icon: Eye },
  { value: 'ISO 11226', label: 'Compliant Assessment', icon: ShieldCheck },
];

// ── Core Technology Features ──────────────────────────────────────
const TECH_FEATURES = [
  {
    icon: Radio,
    title: 'Real-time Joint Telemetry',
    description: 'Tracks 33 skeletal landmarks to calculate joint angles, velocity, and sustained tension with clinical precision.',
  },
  {
    icon: Activity,
    title: 'Automated RULA/REBA Assessment',
    description: 'Instantly calculates Rapid Upper Limb Assessment and Rapid Entire Body Assessment scores, eliminating manual observational audits.',
  },
  {
    icon: Brain,
    title: 'Context-Aware Task Recognition',
    description: 'AI models understand the specific task being performed, allowing for dynamic threshold adjustments rather than generic baselines.',
  },
];

// ── Command Center Cards ──────────────────────────────────────────
const COMMAND_CARDS = [
  {
    icon: BarChart3,
    title: 'Executive Dashboard',
    description: 'Aggregate risk scores across multiple facilities. Identify systemic ergonomic failures before they become recordable incidents.',
  },
  {
    icon: Radio,
    title: 'Live Monitoring',
    description: 'Deploy virtual safety auditors on the floor. View posture overlays and risk scores from multiple camera feeds for immediate intervention.',
  },
  {
    icon: Brain,
    title: 'AI Insights Engine',
    description: 'Receive automated, data-backed corrective action suggestions and ergonomic redesign guidelines based on aggregated posture and task data.',
  },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[#0a0e1a] text-white relative overflow-x-hidden">

      {/* ── Background ambient glows ─────────────────────────────────── */}
      <div className="fixed inset-0 pointer-events-none z-0">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[600px] bg-blue-500/5 blur-[120px] rounded-full" />
        <div className="absolute bottom-0 right-0 w-[600px] h-[400px] bg-cyan-500/5 blur-[100px] rounded-full" />
      </div>

      {/* ── Navigation ───────────────────────────────────────────────── */}
      <nav className="sticky top-0 z-50 bg-[#0a0e1a]/80 backdrop-blur-xl border-b border-white/5">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3 group">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-blue-500 to-cyan-400 flex items-center justify-center">
              <ScanLine className="w-5 h-5 text-white" />
            </div>
            <span className="text-lg font-bold tracking-tight text-white">ERGOVIGILANCE</span>
          </Link>
          <div className="hidden md:flex items-center gap-8">
            <a href="#solutions" className="text-sm text-slate-400 hover:text-white transition-colors">Solutions</a>
            <a href="#technology" className="text-sm text-slate-400 hover:text-white transition-colors">Product</a>
            <a href="#command-center" className="text-sm text-slate-400 hover:text-white transition-colors">Resources</a>
            <Link
              to="/request-pilot"
              className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-blue-600 text-sm font-semibold text-white hover:bg-blue-500 transition-all hover:shadow-lg hover:shadow-blue-500/25"
            >
              REQUEST DEMO
            </Link>
            <Link
              to="/login"
              className="flex items-center gap-2 px-4 py-2.5 rounded-lg border border-white/10 text-sm text-slate-400 hover:text-white hover:border-white/20 transition-all"
            >
              Log In
            </Link>
          </div>
          <button className="md:hidden text-slate-400 hover:text-white">
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
        </div>
      </nav>

      {/* ── Hero ─────────────────────────────────────────────────────── */}
      <section className="relative z-10">
        <div className="max-w-7xl mx-auto px-6 py-16 lg:py-24 grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">
          {/* Left — copy */}
          <div className="space-y-8">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-blue-500/30 bg-blue-500/10 text-xs font-semibold text-blue-400 uppercase tracking-wider">
              <Zap className="w-3.5 h-3.5" />
              System Online &gt; V2.4.1
            </div>
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold leading-tight text-white">
              Industrial Safety,{' '}
              <span className="bg-gradient-to-r from-blue-400 to-cyan-300 bg-clip-text text-transparent">
                Reimagined through AI.
              </span>
            </h1>
            <p className="text-lg text-slate-400 leading-relaxed max-w-xl">
              Real-time posture analysis and ergonomic risk mitigation for the modern
              enterprise. Powered by advanced Computer Vision and Machine Learning.
            </p>
            <div className="flex items-center gap-4 flex-wrap">
              <Link
                to="/request-pilot"
                className="flex items-center gap-2 px-6 py-3 rounded-lg bg-blue-600 text-sm font-bold text-white hover:bg-blue-500 transition-all hover:shadow-lg hover:shadow-blue-500/25"
              >
                REQUEST A DEMO
              </Link>
              <a
                href="#technology"
                className="flex items-center gap-2 px-6 py-3 rounded-lg border border-white/20 text-sm font-semibold text-slate-300 hover:text-white hover:border-white/40 transition-all"
              >
                EXPLORE SOLUTIONS
              </a>
            </div>
          </div>

          {/* Right — hero image */}
          <div className="relative">
            <div className="absolute -inset-8 bg-blue-500/10 blur-3xl rounded-full" />
            <div className="relative rounded-2xl overflow-hidden border border-white/10 shadow-2xl shadow-blue-500/10">
              <img
                src="/images/hero-factory-worker.png"
                alt="Factory worker with AI pose skeleton overlay"
                className="w-full h-auto object-cover"
                style={{ maxHeight: 520 }}
              />
              {/* Gradient overlay */}
              <div className="absolute inset-0 bg-gradient-to-t from-[#0a0e1a]/60 via-transparent to-transparent" />
              {/* Floating data badges */}
              <div className="absolute top-4 left-4 flex items-center gap-2 bg-black/60 backdrop-blur-sm px-3 py-1.5 rounded-lg border border-cyan-500/30">
                <div className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
                <span className="text-[10px] font-bold text-cyan-400 uppercase tracking-wider">Live Analysis</span>
              </div>
              <div className="absolute bottom-4 left-4 right-4 flex items-center justify-between bg-black/60 backdrop-blur-sm px-3 py-2 rounded-lg border border-white/10">
                <div className="flex items-center gap-4">
                  <div>
                    <span className="text-[9px] text-slate-400 block">Risk Level</span>
                    <span className="text-xs font-bold text-emerald-400">LOW</span>
                  </div>
                  <div>
                    <span className="text-[9px] text-slate-400 block">REBA Score</span>
                    <span className="text-xs font-bold text-cyan-400">3</span>
                  </div>
                  <div>
                    <span className="text-[9px] text-slate-400 block">Confidence</span>
                    <span className="text-xs font-bold text-blue-400">96%</span>
                  </div>
                </div>
                <span className="text-[9px] text-slate-500">33 landmarks · 12 features · every frame</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Global Deployment Stats ──────────────────────────────────── */}
      <section className="relative z-10 border-y border-white/5 bg-white/[0.02]">
        <div className="max-w-7xl mx-auto px-6">
          {/* Section header */}
          <div className="py-8 border-b border-white/5">
            <p className="text-[10px] font-bold uppercase tracking-widest text-blue-400 mb-2">Global Deployment</p>
            <p className="text-2xl sm:text-3xl font-bold text-white">
              Protecting <span className="text-blue-400">50,000+</span> Workers Across{' '}
              <span className="text-blue-400">200</span> Facilities Worldwide.
            </p>
          </div>
          {/* Stats grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 divide-x divide-white/5">
            {STATS.map((stat) => (
              <div key={stat.label} className="py-8 px-6 text-center group">
                <stat.icon className="w-6 h-6 text-blue-400 mx-auto mb-3 group-hover:scale-110 transition-transform" />
                <p className="text-3xl sm:text-4xl font-bold text-white mb-1">{stat.value}</p>
                <p className="text-sm text-slate-400">{stat.label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Core Technology ──────────────────────────────────────────── */}
      <section className="relative z-10 py-20 lg:py-28" id="technology">
        <div className="max-w-7xl mx-auto px-6 grid lg:grid-cols-2 gap-16 items-center">
          {/* Left — image */}
          <div className="relative">
            <div className="absolute -inset-4 bg-blue-500/5 blur-2xl rounded-2xl" />
            <div className="relative rounded-2xl overflow-hidden border border-white/10">
              <img
                src="/images/hero-factory-worker.png"
                alt="Computer Vision & Pose Estimation"
                className="w-full h-auto object-cover"
                style={{ maxHeight: 480 }}
              />
              <div className="absolute inset-0 bg-gradient-to-r from-[#0a0e1a]/80 via-transparent to-transparent" />
              {/* Overlay data panel */}
              <div className="absolute top-4 left-4 bg-black/70 backdrop-blur-sm rounded-xl border border-white/10 p-4 w-56">
                <p className="text-[9px] text-slate-400 uppercase tracking-wider mb-2">Pose Analysis</p>
                <div className="space-y-1.5">
                  {[
                    { label: 'Neck Angle', val: '18.4°', color: 'bg-emerald-400' },
                    { label: 'Trunk Angle', val: '24.1°', color: 'bg-amber-400' },
                    { label: 'L.Shoulder', val: '42.3°', color: 'bg-red-400' },
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
            </div>
          </div>

          {/* Right — text */}
          <div className="space-y-8">
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
            <div className="space-y-6">
              {TECH_FEATURES.map((feature) => (
                <div key={feature.title} className="flex items-start gap-4 group">
                  <div className="w-10 h-10 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center shrink-0 group-hover:bg-blue-500/20 transition-colors">
                    <feature.icon className="w-5 h-5 text-blue-400" />
                  </div>
                  <div>
                    <h3 className="text-base font-bold text-white mb-1">{feature.title}</h3>
                    <p className="text-sm text-slate-400 leading-relaxed">{feature.description}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── Command Center ───────────────────────────────────────────── */}
      <section className="relative z-10 py-20 lg:py-28 bg-white/[0.02] border-y border-white/5" id="command-center">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center mb-16">
            <p className="text-[10px] font-bold uppercase tracking-widest text-blue-400 mb-3">Command Center</p>
            <h2 className="text-3xl sm:text-4xl font-bold text-white">
              Intelligence at Every Level of the Enterprise.
            </h2>
          </div>
          <div className="grid md:grid-cols-3 gap-6">
            {COMMAND_CARDS.map((card) => (
              <div
                key={card.title}
                className="group relative bg-white/[0.03] border border-white/10 rounded-2xl p-8 hover:border-blue-500/30 hover:bg-blue-500/5 transition-all duration-300"
              >
                <div className="w-12 h-12 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center mb-6 group-hover:bg-blue-500/20 group-hover:scale-105 transition-all">
                  <card.icon className="w-6 h-6 text-blue-400" />
                </div>
                <h3 className="text-xl font-bold text-white mb-3">{card.title}</h3>
                <p className="text-sm text-slate-400 leading-relaxed">{card.description}</p>
                <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-blue-500/30 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Testimonial ──────────────────────────────────────────────── */}
      <AnimatedSection className="relative z-10 py-20 lg:py-28">
        <div className="max-w-4xl mx-auto px-6 text-center">
          <div className="mb-8">
            <svg className="w-12 h-12 text-blue-500/30 mx-auto" fill="currentColor" viewBox="0 0 24 24">
              <path d="M14.017 21v-7.391c0-5.704 3.731-9.57 8.983-10.609l.995 2.151c-2.432.917-3.995 3.638-3.995 5.849h4v10h-9.983zm-14.017 0v-7.391c0-5.704 3.748-9.57 9-10.609l.996 2.151c-2.433.917-3.996 3.638-3.996 5.849h3.983v10h-9.983z" />
            </svg>
          </div>
          <blockquote className="text-2xl sm:text-3xl lg:text-4xl font-bold text-white leading-tight mb-8">
            "ErgoVigilance has transformed our safety culture from reactive to proactive.{' '}
            <span className="text-blue-400">We're seeing risks before they become injuries.</span>"
          </blockquote>
          <div className="flex items-center justify-center gap-4">
            <div className="w-12 h-12 rounded-full bg-gradient-to-br from-blue-500 to-cyan-400 flex items-center justify-center text-white font-bold text-lg">
              SJ
            </div>
            <div className="text-left">
              <p className="text-base font-bold text-white">Sarah Jenkins</p>
              <p className="text-sm text-slate-400">Chief Safety Officer, Apex Manufacturing</p>
            </div>
          </div>
        </div>
      </AnimatedSection>

      {/* ── CTA Section ──────────────────────────────────────────────── */}
      <section className="relative z-10 py-20 lg:py-28 border-t border-white/5">
        <div className="max-w-4xl mx-auto px-6">
          <div className="bg-gradient-to-br from-blue-600/10 via-[#0a0e1a] to-cyan-600/10 border border-blue-500/20 rounded-3xl p-12 lg:p-16 text-center">
            <h2 className="text-3xl sm:text-4xl font-bold text-white mb-4">
              Ready to upgrade your facility's safety standards?
            </h2>
            <p className="text-lg text-slate-400 mb-8 max-w-2xl mx-auto">
              Deploy ErgoVigilance in hours, not weeks. Connect with our engineering team to design a pilot program.
            </p>
            <Link
              to="/request-pilot"
              className="inline-flex items-center gap-2 px-8 py-4 rounded-xl bg-blue-600 text-base font-bold text-white hover:bg-blue-500 transition-all hover:shadow-xl hover:shadow-blue-500/25 hover:scale-[1.02] active:scale-[0.98]"
            >
              CONTACT SALES
              <ArrowUpRight className="w-5 h-5" />
            </Link>
          </div>
        </div>
      </section>

      {/* ── Footer ───────────────────────────────────────────────────── */}
      <footer className="relative z-10 border-t border-white/5 bg-[#060911]">
        <div className="max-w-7xl mx-auto px-6 py-16">
          <div className="grid md:grid-cols-4 gap-12">
            {/* Brand */}
            <div className="md:col-span-2 space-y-4">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-blue-500 to-cyan-400 flex items-center justify-center">
                  <ScanLine className="w-5 h-5 text-white" />
                </div>
                <span className="text-lg font-bold tracking-tight text-white">ERGOVIGILANCE</span>
              </div>
              <p className="text-sm text-slate-500 leading-relaxed max-w-sm">
                Pioneering Industrial Intelligence through autonomous monitoring.
                Protecting the workforce with technical precision.
              </p>
            </div>

            {/* Platform */}
            <div className="space-y-4">
              <h4 className="text-xs font-bold uppercase tracking-widest text-slate-400">Platform</h4>
              <div className="space-y-3">
                <a href="#solutions" className="block text-sm text-slate-500 hover:text-white transition-colors">Solutions</a>
                <a href="#technology" className="block text-sm text-slate-500 hover:text-white transition-colors">Product</a>
                <Link to="/login" className="block text-sm text-slate-500 hover:text-white transition-colors">Pricing</Link>
              </div>
            </div>

            {/* Company */}
            <div className="space-y-4">
              <h4 className="text-xs font-bold uppercase tracking-widest text-slate-400">Company</h4>
              <div className="space-y-3">
                <Link to="/validation" className="block text-sm text-slate-500 hover:text-white transition-colors">About</Link>
                <a href="#" className="block text-sm text-slate-500 hover:text-white transition-colors">Privacy Policy</a>
                <a href="#" className="block text-sm text-slate-500 hover:text-white transition-colors">Terms of Service</a>
              </div>
            </div>
          </div>

          {/* Bottom bar */}
          <div className="mt-12 pt-8 border-t border-white/5 flex flex-col sm:flex-row items-center justify-between gap-4">
            <p className="text-xs text-slate-600">
              &copy; 2026 ErgoVigilance Systems. All rights reserved.
            </p>
            <div className="flex items-center gap-4 text-xs text-slate-600">
              <span className="flex items-center gap-1.5">
                <Lock className="w-3 h-3" /> 100% On-Premise
              </span>
              <span className="flex items-center gap-1.5">
                <MonitorCheck className="w-3 h-3" /> No Wearables
              </span>
              <span className="flex items-center gap-1.5">
                <ShieldCheck className="w-3 h-3" /> No Cloud Upload
              </span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
