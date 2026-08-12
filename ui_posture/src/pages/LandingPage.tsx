import React, { useEffect, useRef, useState } from 'react';
import {
  Camera, AlertTriangle, FileText, Users, Brain, ChevronRight,
  ArrowUpRight, ShieldCheck, Lock, MonitorCheck, Zap, ScanLine, Gauge, BarChart3,
  Layers, CheckCircle2, HeartHandshake, HelpCircle, UserCheck,
} from 'lucide-react';
import { Link } from 'react-router';
import { IndustrialBackdrop } from '@/src/components/common';

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
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

// One phrase, everywhere — the microcopy below it removes the unspoken
// "how much does this cost / how committed am I" hesitation.
const PILOT_CTA = 'Request a Free Pilot';
const PILOT_MICROCOPY = 'Free · No card · 2-week trial on one workstation';

const FeatureCard = ({ icon: Icon, title, description }: { icon: React.ElementType; title: string; description: string }) => (
  <div className="group bg-surface-container border border-outline-variant rounded-xl p-lg hover:border-primary/40 hover:shadow-lg hover:shadow-primary/5 hover:-translate-y-0.5 transition-all duration-200">
    <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center mb-md group-hover:bg-primary/15 group-hover:scale-105 transition-all">
      <Icon className="w-6 h-6 text-primary" />
    </div>
    <h3 className="text-title-lg font-bold text-on-surface mb-sm group-hover:text-primary transition-colors">{title}</h3>
    <p className="text-body-sm text-on-surface-variant leading-relaxed">{description}</p>
  </div>
);

const Stat = ({ value, label }: { value: string; label: string }) => (
  <div className="text-center group">
    <p className="text-display-md font-bold text-primary group-hover:scale-105 transition-transform">{value}</p>
    <p className="text-body-sm text-on-surface-variant mt-1">{label}</p>
  </div>
);

// Recognition statements — the "this is for you if" moment. No stats, no
// features: just the situations a safety manager or EHS consultant lives in.
const RECOGNITION_POINTS = [
  'You’ve filed a workers’ comp claim for a musculoskeletal injury — or you suspect one is coming.',
  'Your ergonomic audits happen once a quarter, if that — and each one captures a single moment, not a shift.',
  'You’re the one who has to stand in front of management and explain the incident report.',
  'You have cameras on your floor already — you’ve just never used them to prevent instead of review.',
];

const PIPELINE_STEPS = [
  {
    icon: Camera,
    title: '1 · Capture',
    desc: 'A standard camera watches one workstation. USB webcam or existing factory IP/RTSP cameras — no special hardware, no wearables.',
  },
  {
    icon: ScanLine,
    title: '2 · 33 Landmarks',
    desc: 'MediaPipe pose estimation tracks 33 skeletal landmarks per frame — head, spine, shoulders, elbows, wrists, hips, knees, ankles — in real time.',
  },
  {
    icon: Gauge,
    title: '3 · Biomechanical Features',
    desc: 'Landmarks become 12 measured features: neck flexion, trunk flexion, shoulder elevation, knee angle, weight shift, wrist deviation, and more.',
  },
  {
    icon: Brain,
    title: '4 · Risk Engine',
    desc: 'RULA/REBA-informed rule scoring on every joint, overlaid with a REBA-calibrated model and fatigue/exposure context — every score is explainable.',
  },
  {
    icon: AlertTriangle,
    title: '5 · Alerts & Guidance',
    desc: 'Crossing a threshold fires an immediate, traceable alert to the worker and supervisor with the exact rule that triggered it.',
  },
  {
    icon: FileText,
    title: '6 · Evidence & Reports',
    desc: 'Every session records synchronized risk data and video. Export PDF, CSV, or JSON reports for compliance and continuous improvement.',
  },
];

const FAQ_ITEMS: Array<[string, string]> = [
  [
    'Will workers know they’re being monitored?',
    'Yes — always. Worker notice and consent are part of the deployment process, and the on-screen skeleton overlay makes the tracking visible in real time. Workers can see what’s recorded, how long it’s kept, and can request erasure of their data. We don’t do hidden monitoring — it’s bad for trust, and it’s bad for unions.',
  ],
  [
    'Does this replace our safety officer or ergonomist?',
    'No — it’s advisory, not a replacement. ErgoVigilance is an extra set of eyes that never blinks: it surfaces continuous risk data so your safety team knows where to look and what to prioritize. Every alert is explainable and traceable to a specific rule — no black-box verdicts you’d have to defend.',
  ],
  [
    'What happens after the two weeks?',
    'You keep the full report and the data either way — no obligation. At the end you have a documented, continuous risk assessment of one workstation that a point-in-time audit can’t give you. Most pilots extend or buy; some decide it’s not a fit. Either way, the report is yours.',
  ],
  [
    'Is this a medical device?',
    'No. ErgoVigilance uses heuristic risk thresholds and is an awareness and prioritization tool — not a medical device and not a diagnostic. It doesn’t diagnose, treat, or prevent any medical condition, and every report carries that disclaimer in writing.',
  ],
];

const PILOT_CTA_BUTTON = (
  <Link
    to="/request-pilot"
    className="group flex items-center gap-sm rounded-lg bg-primary px-lg py-md font-bold text-on-primary transition-all hover:shadow-lg hover:shadow-primary/25 hover:scale-[1.02] active:scale-[0.98]"
  >
    {PILOT_CTA} <ChevronRight className="w-5 h-5 transition-transform group-hover:translate-x-0.5" />
  </Link>
);

export default function LandingPage() {
  const [activeIndex, setActiveIndex] = useState(0);
  const videoRefs = useRef<(HTMLVideoElement | null)[]>([]);

  const slides = [
    { type: 'video', src: '/videos/Static_tripod_shot_of_a_worker_processed.mp4' },
    { type: 'video', src: '/videos/Static_wide_shot_of_a_warehous_processed.mp4' },
  ];

  const nextSlide = () => setActiveIndex((prev) => (prev + 1) % slides.length);
  const prevSlide = () => setActiveIndex((prev) => (prev - 1 + slides.length) % slides.length);

  useEffect(() => {
    videoRefs.current.forEach((video, index) => {
      if (video) {
        if (index === activeIndex) {
          video.play().catch((err) => console.error('Video play error:', err));
        } else {
          video.pause();
          video.currentTime = 0;
        }
      }
    });
  }, [activeIndex]);

  return (
    <div className="min-h-screen bg-surface text-on-surface relative">
      {/* Full-viewport decorative background — one industrial visual language
          shared with the login and pilot-request pages: blueprint dot-grid
          plus amber/primary glows, all theme-aware behind the content. */}
      <IndustrialBackdrop />

      {/* ── Navigation ─────────────────────────────────────────────────── */}
      <nav className="sticky top-0 z-50 bg-surface/80 backdrop-blur-xl border-b border-outline-variant/60">
        <div className="max-w-7xl mx-auto px-lg py-md flex items-center justify-between">
          <Link to="/" className="flex items-center gap-sm group">
            <img src="/favicon.png" alt="ErgoVigilance" className="w-10 h-10 rounded-lg group-hover:scale-105 transition-transform" />
            <span className="text-title-lg font-bold text-on-surface">ErgoVigilance</span>
          </Link>
          <div className="flex items-center gap-md">
            <a href="#how-it-works" className="hidden sm:block text-body-sm text-on-surface-variant hover:text-on-surface transition-colors">How it works</a>
            <a href="#who-for" className="hidden sm:block text-body-sm text-on-surface-variant hover:text-on-surface transition-colors">Who it’s for</a>
            <a href="#faq" className="hidden sm:block text-body-sm text-on-surface-variant hover:text-on-surface transition-colors">FAQ</a>
            <Link to="/login" className="flex items-center gap-sm px-md py-sm rounded-lg bg-surface-container-high text-on-surface-variant hover:text-on-surface hover:bg-surface-container-highest hover:shadow-sm transition-all text-body-sm">
              Log In <ArrowUpRight className="w-4 h-4" />
            </Link>
            <Link to="/request-pilot" className="hidden md:flex items-center gap-sm px-md py-sm rounded-lg bg-primary text-body-sm font-bold text-on-primary hover:shadow-lg hover:shadow-primary/25 transition-all">
              {PILOT_CTA}
            </Link>
          </div>
        </div>
      </nav>

      {/* ── Hero — the buyer's pain, not the product's mechanism ───────── */}
      <section className="relative overflow-hidden">
        {/* Multi-layer gradient mesh for visual depth */}
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(120,160,255,0.18),transparent_45%)]" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_bottom_left,rgba(251,146,60,0.10),transparent_40%)]" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(77,142,255,0.06),transparent_60%)]" />
        {/* Subtle grid pattern overlay */}
        <div className="absolute inset-0 opacity-[0.03]" style={{ backgroundImage: 'linear-gradient(var(--color-primary) 1px, transparent 1px), linear-gradient(90deg, var(--color-primary) 1px, transparent 1px)', backgroundSize: '60px 60px' }} />
        <div className="relative max-w-7xl mx-auto px-lg py-20 sm:py-24 lg:py-28 grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">
          <div className="space-y-lg">
            <div className="inline-flex items-center gap-sm rounded-full border border-primary/30 bg-primary/10 px-md py-xs text-[10px] font-bold uppercase tracking-widest text-primary">
              <Zap className="w-3.5 h-3.5" />
              Continuous ergonomics monitoring — no wearables
            </div>
            <div className="space-y-md">
              <h1 className="text-display-xl font-bold leading-[1.08] text-on-surface sm:text-5xl">
                Your next comp claim is{' '}
                <span className="text-primary">preventable</span>.
                <br />
                You just can’t see it yet.
              </h1>
              <p className="text-body-lg leading-8 text-on-surface-variant max-w-2xl">
                A worker holds an awkward reach for the 400th time this shift — a strain that
                accumulates silently until it’s an incident report, a comp claim, and lost
                production. ErgoVigilance watches that workstation with a camera you already
                own, and flags the risk while it’s still a habit — not yet a claim.
              </p>
            </div>
            <div className="space-y-md">
              <div className="flex items-center gap-md flex-wrap">
                {PILOT_CTA_BUTTON}
                <a href="#how-it-works" className="rounded-lg border border-outline-variant bg-surface/60 px-lg py-md font-bold text-on-surface-variant backdrop-blur-sm transition-colors hover:border-outline hover:text-on-surface">
                  See how it works
                </a>
              </div>
              <span className="block text-[11px] text-on-surface-variant">{PILOT_MICROCOPY}</span>
            </div>
            <div className="flex items-center gap-md pt-sm text-body-sm text-on-surface-variant">
              <span className="flex items-center gap-1.5"><Lock className="w-4 h-4 text-primary" /> 100% on-premise</span>
              <span className="flex items-center gap-1.5"><MonitorCheck className="w-4 h-4 text-primary" /> No wearables</span>
              <span className="flex items-center gap-1.5"><ShieldCheck className="w-4 h-4 text-primary" /> No cloud upload</span>
            </div>
          </div>

          {/* Factory worker video slideshow */}
          <div className="relative">
            <div className="absolute -inset-8 bg-primary/8 blur-3xl rounded-full opacity-80" />
            <div className="absolute -inset-4 bg-red-500/5 blur-2xl rounded-full opacity-60" />
            <div className="relative">
              <div className="relative overflow-hidden rounded-2xl border border-white/10 shadow-2xl shadow-primary/5" style={{ height: 420 }}>
                {/* Video layers */}
                {slides.map((slide, index) => (
                  <div key={index} className={`absolute inset-0 transition-opacity duration-500 ${index === activeIndex ? 'opacity-100 z-10' : 'opacity-0 z-0'}`}>
                    <video
                      ref={(el) => { videoRefs.current[index] = el; }}
                      autoPlay
                      muted
                      loop
                      playsInline
                      preload="auto"
                      className="h-full w-full object-cover"
                      style={{ backgroundColor: '#000' }}
                    >
                      <source src={slide.src} type="video/mp4" />
                    </video>
                  </div>
                ))}
                {/* Gradient overlays */}
                <div className="absolute inset-0 bg-gradient-to-br from-surface/30 via-transparent to-surface/50 z-20 pointer-events-none" />
                <div className="absolute inset-0 bg-gradient-to-t from-surface/60 to-transparent z-20 pointer-events-none" />
                {/* Live badge */}
                <div className="absolute top-3 left-3 z-30 flex items-center gap-1.5 bg-primary/20 backdrop-blur-sm px-2.5 py-1 rounded-md border border-primary/30">
                  <div className="w-2 h-2 rounded-full bg-primary animate-pulse" />
                  <span className="text-[10px] font-bold text-primary uppercase tracking-wider">Live monitoring</span>
                </div>
                <div className="absolute bottom-3 left-3 z-30 flex items-center gap-1.5 bg-black/60 backdrop-blur-sm px-2.5 py-1 rounded-md border border-primary/30">
                  <span className="text-[10px] font-bold text-primary uppercase tracking-wider">Risk: LOW</span>
                  <span className="text-[10px] text-white/80">Normal operation range</span>
                </div>
                {/* Corner accents */}
                <div className="absolute top-2 right-2 z-30 w-6 h-6 border-t-2 border-r-2 border-primary/20 rounded-tr-md" />
                <div className="absolute bottom-2 right-2 z-30 w-6 h-6 border-b-2 border-r-2 border-primary/20 rounded-br-md" />
              </div>
              {/* Slideshow controls */}
              <div className="absolute bottom-6 left-1/2 z-30 flex -translate-x-1/2 items-center gap-4">
                <button onClick={prevSlide} className="flex h-10 w-10 items-center justify-center rounded-full bg-surface/70 text-on-surface backdrop-blur-sm hover:bg-surface/90 transition-colors" aria-label="Previous slide">
                  <ChevronRight className="h-5 w-5 rotate-180" />
                </button>
                <div className="flex items-center gap-2">
                  {slides.map((_, index) => (
                    <button
                      key={index}
                      onClick={() => setActiveIndex(index)}
                      className={`h-2.5 rounded-full transition-all ${index === activeIndex ? 'w-8 bg-primary' : 'bg-on-surface-variant/40 hover:bg-on-surface-variant/60'}`}
                      aria-label={`Go to slide ${index + 1}`}
                    />
                  ))}
                </div>
                <button onClick={nextSlide} className="flex h-10 w-10 items-center justify-center rounded-full bg-surface/70 text-on-surface backdrop-blur-sm hover:bg-surface/90 transition-colors" aria-label="Next slide">
                  <ChevronRight className="h-5 w-5" />
                </button>
              </div>
              <div className="absolute -bottom-8 left-1/2 -translate-x-1/2 bg-surface border border-outline-variant rounded-full px-lg py-1.5 text-[10px] font-bold uppercase tracking-widest text-on-surface-variant shadow-lg whitespace-nowrap">
                <span className="text-primary mr-1">33</span> landmarks · <span className="text-primary mr-1">12</span> features · every frame
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Stats strip — credibility, kept lean ───────────────────────── */}
      <section className="border-y border-outline-variant/60 bg-surface-container-low/80 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-lg py-10 grid grid-cols-2 md:grid-cols-4 gap-lg">
          <Stat value="33" label="Skeletal landmarks tracked per frame" />
          <Stat value="12" label="Biomechanical risk features scored" />
          <Stat value="30k+" label="REBA-labeled poses used for calibration" />
          <Stat value="0" label="Cloud uploads — video never leaves the site" />
        </div>
      </section>

      {/* ── Who this is for — recognition before features ─────────────── */}
      <AnimatedSection className="py-20 px-lg">
        <div className="max-w-4xl mx-auto" id="who-for">
          <div className="flex items-center gap-sm mb-md text-primary">
            <UserCheck className="w-5 h-5" />
            <span className="text-[10px] font-bold uppercase tracking-widest">Is this you?</span>
          </div>
          <h2 className="text-display-md font-bold text-on-surface mb-lg">
            If any of this sounds familiar, this is for you.
          </h2>
          <div className="space-y-sm">
            {RECOGNITION_POINTS.map((point) => (
              <div key={point} className="flex items-start gap-md rounded-lg bg-surface-container border border-outline-variant/60 px-lg py-md">
                <CheckCircle2 className="w-5 h-5 text-primary shrink-0 mt-0.5" />
                <p className="text-body-lg text-on-surface leading-relaxed">{point}</p>
              </div>
            ))}
          </div>
          <p className="text-body-md text-on-surface-variant mt-lg">
            Most small and mid-size plants can’t afford continuous ergonomics monitoring — and can’t
            afford the claims, either. That gap is the whole reason this exists.
          </p>
        </div>
      </AnimatedSection>

      {/* ── Founder note — a person built this ────────────────────────── */}
      <AnimatedSection className="py-20 px-lg bg-surface-container-low">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-center gap-sm mb-md text-primary">
            <HeartHandshake className="w-5 h-5" />
            <span className="text-[10px] font-bold uppercase tracking-widest">A note from the builder</span>
          </div>
          <div className="bg-surface border border-outline-variant rounded-2xl p-xl">
            <p className="text-body-lg leading-relaxed text-on-surface mb-md">
              I built ErgoVigilance as an engineering intern at GGS Information Services, where I
              designed the pose-estimation module for an industrial ergonomics system. The deeper
              I got, the clearer the gap became: classic ergonomic audits (RULA/REBA) are
              snapshots — a clipboard, twenty minutes, once a quarter. But the posture that
              injures a worker is the one that repeats a thousand times a shift and never lands
              on a form.
            </p>
            <p className="text-body-lg leading-relaxed text-on-surface">
              So I built what I couldn’t find: a camera on one workstation, measuring
              continuously, explaining every alert it fires. It’s early — and I’d rather
              be upfront about that than pretend otherwise.
            </p>
          </div>
          <div className="mt-lg rounded-xl border border-primary/30 bg-primary/10 px-lg py-md">
            <p className="text-body-sm text-on-surface leading-relaxed">
              <strong className="text-on-surface">Why the pilots are free:</strong> we’re new and we don’t have
              testimonials — and we won’t fake them. We’re onboarding a small number of pilot sites this
              quarter in exchange for real feedback and, if you’re willing, a case study. We’d rather earn
              a reference than invent one.
            </p>
          </div>
        </div>
      </AnimatedSection>

      {/* ── How risk assessment works (the core) ───────────────────────── */}
      <AnimatedSection className="py-20 px-lg">
        <div className="max-w-7xl mx-auto" id="how-it-works">
          <div className="text-center mb-14">
            <div className="inline-flex items-center gap-sm rounded-full border border-outline-variant bg-surface px-md py-xs text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-md">
              <ScanLine className="w-3.5 h-3.5" /> The core pipeline
            </div>
            <h2 className="text-display-md font-bold text-on-surface mb-md">How the Risk Assessment Works</h2>
            <p className="text-body-lg text-on-surface-variant max-w-2xl mx-auto">
              From camera frame to defensible report in six auditable steps. No black box —
              every risk score traces back to a specific joint angle and a specific threshold.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-lg">
            {PIPELINE_STEPS.map((step, i) => (
              <div key={i} className="relative bg-surface border border-outline-variant rounded-xl p-lg hover:border-primary/30 hover:shadow-md hover:shadow-primary/5 transition-all group">
                <div className="flex items-start gap-md">
                  <div className="w-11 h-11 rounded-lg bg-primary/10 flex items-center justify-center shrink-0 group-hover:bg-primary/15 transition-colors">
                    <step.icon className="w-5 h-5 text-primary" />
                  </div>
                  <div>
                    <h3 className="text-title-sm font-bold text-on-surface mb-sm">{step.title}</h3>
                    <p className="text-body-sm text-on-surface-variant leading-relaxed">{step.desc}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Example feature readout */}
          <div className="mt-12 bg-surface border border-outline-variant rounded-xl p-lg max-w-3xl mx-auto">
            <div className="flex items-center gap-md mb-md">
              <BarChart3 className="w-5 h-5 text-primary" />
              <h3 className="text-title-md font-bold text-on-surface">A live feature readout (what the safety manager sees)</h3>
            </div>
            <div className="grid sm:grid-cols-2 gap-sm">
              {[
                ['Neck Flexion', '9.4°', 'good'],
                ['Trunk Flexion', '28.7°', 'moderate'],
                ['Left Shoulder Elev.', '34.2°', 'high'],
                ['Right Shoulder Elev.', '12.1°', 'good'],
                ['Shoulder Symmetry', '19.8%', 'moderate'],
                ['Knee Angle', '158.3°', 'good'],
                ['Weight Shift', '14.5%', 'moderate'],
                ['Wrist Deviation', '7.2°', 'good'],
              ].map(([name, val, status]) => (
                <div key={name} className="flex items-center justify-between gap-md rounded-lg bg-surface-container px-md py-sm border border-outline-variant/50">
                  <span className="text-body-sm text-on-surface-variant">{name}</span>
                  <span className="flex items-center gap-sm">
                    <span className="font-label-mono text-body-sm text-on-surface">{val}</span>
                    <span
                      className={`px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider ${
                        status === 'high' ? 'bg-red-500/15 text-red-400' :
                        status === 'moderate' ? 'bg-orange-500/15 text-orange-400' : 'bg-green-500/15 text-green-400'
                      }`}
                    >
                      {status}
                    </span>
                  </span>
                </div>
              ))}
            </div>
            <p className="text-body-sm text-on-surface-variant mt-md flex items-start gap-sm">
              <CheckCircle2 className="w-4 h-4 text-primary shrink-0 mt-0.5" />
              Every feature maps to a threshold the safety manager can inspect and tune —
              not a mysterious AI score.
            </p>
          </div>
        </div>
      </AnimatedSection>

      {/* ── Visual proof — the human moment being caught ──────────────── */}
      <AnimatedSection className="py-20 px-lg bg-surface-container-low">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-display-md font-bold text-on-surface mb-md">See the System Working</h2>
            <p className="text-body-lg text-on-surface-variant max-w-2xl mx-auto">
              The moment that matters isn’t the dashboard — it’s the reach, the bend, the
              repetition that happens a hundred times an hour. This is what that looks like
              through ErgoVigilance.
            </p>
          </div>
          <div className="grid md:grid-cols-2 gap-lg">
            <div className="bg-surface-container border border-outline-variant rounded-xl overflow-hidden shadow-xl shadow-black/10 hover:shadow-2xl hover:shadow-black/15 transition-shadow">
              {/* Live Camera simulation */}
              <div className="relative bg-surface-container-low rounded-t-xl overflow-hidden">
                {/* Header bar */}
                <div className="flex items-center justify-between px-md py-2 border-b border-outline-variant/50">
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                    <span className="text-[11px] font-bold text-on-surface">Live Camera</span>
                  </div>
                  <span className="text-[10px] text-on-surface-variant">30 FPS</span>
                </div>
                <div className="p-sm">
                  <p className="text-[10px] text-on-surface-variant mb-2">Webcam feed with risk overlay</p>
                  {/* Risk badge */}
                  <div className="inline-flex items-center gap-1.5 bg-amber-500/90 text-white text-[10px] font-bold uppercase tracking-wider px-sm py-1 rounded-md mb-3">
                    <AlertTriangle className="w-3 h-3" />
                    MEDIUM RISK
                  </div>
                  {/* Two-panel layout: skeleton + features */}
                  <div className="grid grid-cols-3 gap-2">
                    {/* Skeleton overlay panel */}
                    <div className="col-span-2 bg-surface-container-lowest border border-outline-variant/30 rounded-lg p-sm min-h-[180px] relative overflow-hidden">
                      <span className="text-[9px] text-on-surface-variant/70 block mb-1">Real-time OpenCV frames with skeleton overlay</span>
                      {/* Animated skeleton figure */}
                      <svg viewBox="0 0 200 160" className="w-full h-auto" style={{ filter: 'drop-shadow(0 0 6px rgba(34,197,94,0.4))' }}>
                        {/* Head */}
                        <circle cx="100" cy="25" r="8" fill="none" stroke="#22c55e" strokeWidth="2" className="animate-pulse" />
                        {/* Neck to spine */}
                        <line x1="100" y1="33" x2="100" y2="80" stroke="#22c55e" strokeWidth="2" />
                        {/* Shoulders */}
                        <line x1="70" y1="45" x2="130" y2="45" stroke="#22c55e" strokeWidth="2" />
                        {/* Left arm */}
                        <line x1="70" y1="45" x2="55" y2="75" stroke="#22c55e" strokeWidth="2" />
                        <line x1="55" y1="75" x2="45" y2="105" stroke="#22c55e" strokeWidth="2" />
                        {/* Right arm */}
                        <line x1="130" y1="45" x2="145" y2="75" stroke="#22c55e" strokeWidth="2" />
                        <line x1="145" y1="75" x2="155" y2="105" stroke="#22c55e" strokeWidth="2" />                          {/* Spine to hips */}
                          <line x1="100" y1="80" x2="100" y2="110" stroke="#22c55e" strokeWidth="2" />
                          {/* Hips */}
                          <line x1="80" y1="110" x2="120" y2="110" stroke="#22c55e" strokeWidth="2" />                        {/* Left leg */}
                        <line x1="80" y1="110" x2="70" y2="140" stroke="#22c55e" strokeWidth="2" />
                        <line x1="70" y1="140" x2="65" y2="155" stroke="#22c55e" strokeWidth="2" />                        {/* Right leg */}
                        <line x1="120" y1="110" x2="130" y2="140" stroke="#22c55e" strokeWidth="2" />
                        <line x1="130" y1="140" x2="135" y2="155" stroke="#22c55e" strokeWidth="2" />                        {/* Joint dots */}
                        {[[100,25],[100,80],[70,45],[130,45],[55,75],[145,75],[45,105],[155,105],[80,110],[120,110],[70,140],[130,140],[65,155],[135,155]].map(([cx,cy], i) => (
                          <circle key={i} cx={cx} cy={cy} r="3" fill="#22c55e" className="animate-pulse" style={{ animationDelay: `${i * 0.1}s` }} />
                        ))}                        {/* Angle indicators */}
                        <path d="M 65 55 Q 60 65 55 75" fill="none" stroke="#f59e0b" strokeWidth="1.5" strokeDasharray="3 2" />
                        <path d="M 135 55 Q 140 65 145 75" fill="none" stroke="#22c55e" strokeWidth="1.5" strokeDasharray="3 2" />
                      </svg>
                    </div>
                    {/* Feature metrics panel */}
                    <div className="col-span-1 bg-surface-container-lowest border border-outline-variant/30 rounded-lg p-sm min-h-[180px]">
                      <span className="text-[9px] text-on-surface-variant/70 block mb-2">Feature values / metrics</span>
                      <div className="space-y-1.5">
                        {[{ label: 'Neck', val: '18°', pct: 36, color: 'bg-green-500' },
                          { label: 'Trunk', val: '22°', pct: 44, color: 'bg-amber-500' },
                          { label: 'L.Shoulder', val: '45°', pct: 75, color: 'bg-red-500' },
                          { label: 'R.Shoulder', val: '12°', pct: 24, color: 'bg-green-500' },
                          { label: 'L.Elbow', val: '89°', pct: 60, color: 'bg-amber-500' },
                          { label: 'R.Elbow', val: '35°', pct: 28, color: 'bg-green-500' },
                          { label: 'Hip', val: '8°', pct: 16, color: 'bg-green-500' },
                          { label: 'Knee', val: '165°', pct: 20, color: 'bg-green-500' },
                        ].map(({ label, val, pct, color }) => (
                          <div key={label} className="flex items-center gap-1">
                            <span className="text-[8px] text-on-surface-variant w-14 shrink-0 truncate">{label}</span>
                            <div className="flex-1 h-1 bg-surface-container rounded-full overflow-hidden">
                              <div className={`h-full rounded-full ${color} transition-all duration-1000`} style={{ width: `${pct}%` }} />
                            </div>
                            <span className="text-[8px] text-on-surface-variant w-6 text-right shrink-0">{val}</span>
                          </div>
                        ))}
                      </div>
                      <div className="mt-2 pt-2 border-t border-outline-variant/30">
                        <div className="flex justify-between">
                          <span className="text-[9px] text-on-surface-variant">REBA Score</span>
                          <span className="text-[9px] font-bold text-amber-500">5</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-[9px] text-on-surface-variant">Fatigue</span>
                          <span className="text-[9px] font-bold text-amber-500">32%</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              <div className="p-lg">
                <h3 className="text-title-lg font-bold text-on-surface mb-sm">Normal work, watched continuously</h3>
                <p className="text-body-sm text-on-surface-variant leading-relaxed">
                  When posture stays within safe ranges the overlay reads calm and green — the
                  system runs quietly in the background, so the risky reach never gets to be the
                  first time anyone notices.
                </p>
              </div>
            </div>
            <div className="bg-surface-container border border-outline-variant rounded-xl overflow-hidden shadow-xl shadow-black/10 hover:shadow-2xl hover:shadow-black/15 transition-shadow">
              <div className="aspect-video relative">
                <img src="/images/dashboard-admin.png" alt="ErgoVigilance dashboard" className="w-full h-full object-cover object-top" />
                <div className="absolute inset-0 bg-gradient-to-t from-surface/60 to-transparent pointer-events-none" />
              </div>
              <div className="p-lg">
                <h3 className="text-title-lg font-bold text-on-surface mb-sm">The worker sees their own risk in real time</h3>
                <p className="text-body-sm text-on-surface-variant leading-relaxed">
                  Per-joint readouts, fatigue and exposure curves, and a running alert timeline —
                  with the corrective action spelled out, not buried in a report.
                </p>
              </div>
            </div>
          </div>
        </div>
      </AnimatedSection>

      {/* ── Core capabilities ──────────────────────────────────────────── */}
      <AnimatedSection className="py-20 px-lg">
        <div className="max-w-7xl mx-auto" id="capabilities">
          <div className="text-center mb-12">
            <h2 className="text-display-md font-bold text-on-surface mb-md">Core Capabilities</h2>
            <p className="text-body-lg text-on-surface-variant max-w-2xl mx-auto">
              Built for real factory floors: explainable, auditable, and entirely on-premise.
            </p>
          </div>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-lg">
            <FeatureCard icon={Camera} title="Live Posture Monitoring" description="Real-time 33-landmark skeletal tracking with an on-screen pose overlay for immediate worker feedback." />
            <FeatureCard icon={Gauge} title="Ergonomic Risk Scoring" description="12 biomechanical features scored per body part with RULA-informed logic and a REBA-calibrated advisory overlay." />
            <FeatureCard icon={AlertTriangle} title="Explainable Alerts" description="Rule-based threshold alerts every safety manager can trace, audit, and tune — no black-box ML decisions." />
            <FeatureCard icon={FileText} title="Recording, Replay & Reports" description="Full session recording with synchronized risk data for post-incident review, coaching, and PDF/CSV/JSON export." />
            <FeatureCard icon={Layers} title="Multi-Camera Ready" description="Add existing factory IP/RTSP cameras alongside USB webcams — each station gets its own monitored feed." />
            <FeatureCard icon={Users} title="Role-Based Access & Audit" description="Operator, supervisor, safety manager, and admin roles with a full audit trail of every action." />
          </div>
        </div>
      </AnimatedSection>

      {/* ── Why threshold-based ────────────────────────────────────────── */}
      <AnimatedSection className="py-20 px-lg bg-surface-container-low/80">
        <div className="max-w-4xl mx-auto">
          <div className="bg-surface-container border border-primary/30 rounded-2xl p-xl shadow-lg shadow-primary/5">
            <h2 className="text-display-md font-bold text-on-surface mb-md">Why Threshold-Based, Not Black-Box AI?</h2>
            <p className="text-body-lg text-on-surface-variant mb-md leading-relaxed">
              A deliberate design choice. For safety software a factory has to trust and defend:
            </p>
            <ul className="space-y-sm text-body-sm text-on-surface-variant">
              <li className="flex items-start gap-sm">
                <div className="w-2 h-2 rounded-full bg-primary mt-1.5 shrink-0" />
                <span>Every alert traces to a specific, auditable joint angle or time threshold</span>
              </li>
              <li className="flex items-start gap-sm">
                <div className="w-2 h-2 rounded-full bg-primary mt-1.5 shrink-0" />
                <span>Safety managers can adjust rules to match their workstations and compliance requirements</span>
              </li>
              <li className="flex items-start gap-sm">
                <div className="w-2 h-2 rounded-full bg-primary mt-1.5 shrink-0" />
                <span>No unexpected “AI decisions” you can’t explain to your own safety officers or regulators</span>
              </li>
              <li className="flex items-start gap-sm">
                <div className="w-2 h-2 rounded-full bg-primary mt-1.5 shrink-0" />
                <span>A REBA-calibrated model cross-checks the rules as an advisory signal — never a replacement for them</span>
              </li>
            </ul>
          </div>
        </div>
      </AnimatedSection>

      {/* ── FAQ — objection handling before the ask ────────────────────── */}
      <AnimatedSection className="py-20 px-lg">
        <div className="max-w-3xl mx-auto" id="faq">
          <div className="flex items-center justify-center gap-sm mb-md text-primary">
            <HelpCircle className="w-5 h-5" />
            <span className="text-[10px] font-bold uppercase tracking-widest">Straight answers</span>
          </div>
          <h2 className="text-display-md font-bold text-on-surface mb-lg text-center">
            Questions safety managers actually ask
          </h2>
          <div className="space-y-sm">
            {FAQ_ITEMS.map(([question, answer]) => (
              <details key={question} className="group rounded-xl border border-outline-variant bg-surface-container px-lg transition-all open:border-primary/30 open:shadow-md open:shadow-primary/5">
                <summary className="flex items-center justify-between gap-md py-md cursor-pointer list-none text-body-lg font-semibold text-on-surface hover:text-primary transition-colors">
                  {question}
                  <ChevronRight className="w-5 h-5 text-on-surface-variant shrink-0 transition-transform duration-200 group-open:rotate-90 group-open:text-primary" />
                </summary>
                <p className="pb-md text-body-sm text-on-surface-variant leading-relaxed border-t border-outline-variant/50 pt-md">{answer}</p>
              </details>
            ))}
          </div>
        </div>
      </AnimatedSection>

      {/* ── Final pilot CTA — action ───────────────────────────────────── */}
      <AnimatedSection className="py-20 px-lg bg-surface-container-low">
        <div className="max-w-4xl mx-auto text-center" id="pilot">
          <h2 className="text-display-md font-bold text-on-surface mb-md">
            Put it on one workstation for two weeks.
          </h2>
          <p className="text-body-lg text-on-surface-variant mb-lg leading-relaxed">
            Free. No card. We deploy on your camera, your network, your workers — and your video
            never leaves your building.
          </p>
          <div className="flex flex-col items-center gap-md">
            {PILOT_CTA_BUTTON}
            <span className="text-[11px] text-on-surface-variant">{PILOT_MICROCOPY}</span>
            <p className="text-body-sm text-primary flex items-center gap-sm">
              <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
              Currently onboarding 2 pilot sites this quarter — we’re keeping it deliberately small.
            </p>
          </div>
        </div>
      </AnimatedSection>

      {/* ── Footer ─────────────────────────────────────────────────────── */}
      <footer className="py-12 px-lg border-t border-outline-variant/60 bg-surface-container-low/50">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-md">
          <div className="flex items-center gap-sm">
            <img src="/favicon.png" alt="ErgoVigilance" className="w-10 h-10 rounded-lg" />
            <span className="text-title-lg font-bold text-on-surface">ErgoVigilance</span>
          </div>
          <p className="text-body-sm text-on-surface-variant/80 text-center">
            Heuristic risk thresholds · Not a medical device · For awareness &amp; prioritization
          </p>
          <div className="flex items-center gap-md">
            <Link to="/request-pilot" className="text-body-sm font-semibold text-primary hover:underline">
              {PILOT_CTA}
            </Link>
            <Link to="/login" className="text-body-sm text-on-surface-variant hover:text-on-surface transition-colors">
              Log In
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
