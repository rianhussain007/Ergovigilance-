import React, { useEffect, useRef, useState } from 'react';
import { Camera, AlertTriangle, FileText, Users, Activity, ChevronRight, ArrowUpRight, Brain } from 'lucide-react';
import { Link } from 'react-router-dom';

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
    if (currentRef) {
      observer.observe(currentRef);
    }

    return () => {
      if (currentRef) {
        observer.unobserve(currentRef);
      }
    };
  }, [options]);

  return [ref, isVisible];
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

const FeatureCard = ({ icon: Icon, title, description }: { icon: React.ElementType; title: string; description: string }) => {
  return (
    <div className="bg-surface-container border border-outline-variant rounded-xl p-lg hover:border-primary/30 transition-colors">
      <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center mb-md">
        <Icon className="w-6 h-6 text-primary" />
      </div>
      <h3 className="text-title-lg font-bold text-on-surface mb-sm">{title}</h3>
      <p className="text-body-sm text-on-surface-variant">{description}</p>
    </div>
  );
};

export default function LandingPage() {
  const [activeIndex, setActiveIndex] = useState(0);
  const videoRefs = useRef<(HTMLVideoElement | null)[]>([]);

  const slides = [
    {
      type: 'video',
      src: '/videos/Static_tripod_shot_of_a_worker_processed.mp4',
    },
    {
      type: 'video',
      src: '/videos/Static_wide_shot_of_a_warehous_processed.mp4',
    },
  ];

  const nextSlide = () => {
    setActiveIndex((prev) => (prev + 1) % slides.length);
  };

  const prevSlide = () => {
    setActiveIndex((prev) => (prev - 1 + slides.length) % slides.length);
  };

  useEffect(() => {
    console.log('Active index:', activeIndex);
    console.log('Slide data:', slides[activeIndex]);
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
    <div className="min-h-screen bg-surface text-on-surface">
      {/* Navigation */}
      <nav className="sticky top-0 z-50 bg-surface/80 backdrop-blur-lg border-b border-outline-variant">
        <div className="max-w-6xl mx-auto px-lg py-md flex items-center justify-between">
          <div className="flex items-center gap-sm">
            <img src="/favicon.png" alt="ErgoVigilance" className="w-10 h-10 rounded-lg" />
            <span className="text-title-lg font-bold text-on-surface">ErgoVigilance</span>
          </div>
          <Link to="/login" className="flex items-center gap-sm px-md py-sm rounded-lg bg-surface-container-high text-on-surface-variant hover:text-on-surface hover:bg-surface-container transition-colors text-body-sm">
            Log In <ArrowUpRight className="w-4 h-4" />
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative overflow-hidden px-lg py-24 sm:py-28">
        <div className="absolute inset-0 z-0">
          {slides.map((slide, index) => (
            <div
              key={index}
              className={`absolute inset-0 transition-opacity duration-300 ease-out ${
                index === activeIndex ? 'opacity-100 z-10' : 'opacity-0 z-0'
              }`}
            >
              <video
                ref={(el) => (videoRefs.current[index] = el)}
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
          <div className="absolute inset-0 z-20 bg-gradient-to-r from-surface via-surface/88 to-surface/70" />
          <div className="absolute inset-0 z-20 bg-[radial-gradient(circle_at_top_right,rgba(173,198,255,0.16),transparent_32%)]" />
        </div>



        {/* Slideshow Controls */}
        <div className="absolute bottom-6 left-1/2 z-30 flex -translate-x-1/2 items-center gap-4">
          <button
            onClick={prevSlide}
            className="flex h-10 w-10 items-center justify-center rounded-full bg-surface/70 text-on-surface backdrop-blur-sm hover:bg-surface/90 transition-colors"
            aria-label="Previous slide"
          >
            <ChevronRight className="h-5 w-5 rotate-180" />
          </button>
          <div className="flex items-center gap-2">
            {slides.map((slide, index) => (
            <button
                key={index}
                onClick={() => setActiveIndex(index)}
                className={`h-2.5 rounded-full transition-all ${
                  index === activeIndex
                    ? 'w-8 bg-primary'
                    : 'bg-on-surface-variant/40 hover:bg-on-surface-variant/60'
                }`}
                aria-label={`Go to slide ${index + 1}`}
              >
              </button>
            ))}
          </div>
          <button
            onClick={nextSlide}
            className="flex h-10 w-10 items-center justify-center rounded-full bg-surface/70 text-on-surface backdrop-blur-sm hover:bg-surface/90 transition-colors"
            aria-label="Next slide"
          >
            <ChevronRight className="h-5 w-5" />
          </button>
        </div>

        <div className="relative z-30 mx-auto max-w-6xl">
          <div className="max-w-3xl space-y-lg animate-[fadeInUp_0.8s_ease-out] text-left">
            <div className="inline-flex items-center gap-sm rounded-full border border-outline-variant bg-surface/60 px-md py-xs text-[10px] font-bold uppercase tracking-widest text-on-surface-variant backdrop-blur-sm">
              Real-time posture monitoring for industrial teams
            </div>
            <div className="space-y-md">
              <h1 className="max-w-2xl text-display-xl font-bold leading-tight text-on-surface text-left sm:text-5xl">
                Continuous Ergonomic Monitoring
                <br />
                for Industrial Workstations
              </h1>
              <p className="max-w-2xl text-body-lg leading-8 text-on-surface-variant text-left">
                Real-time camera-based posture analysis, rule-based risk scoring, and explainable alerts — designed for factory and warehouse safety teams who need defensible, actionable data.
              </p>
            </div>
            <div className="flex items-center gap-md flex-wrap text-left">
              <Link to="/request-pilot" className="flex items-center gap-sm rounded-lg bg-primary px-lg py-md font-bold text-on-primary transition-opacity hover:opacity-90">
                  Request a Pilot <ChevronRight className="w-5 h-5" />
              </Link>
              <Link to="/login" className="rounded-lg border border-outline-variant bg-surface/35 px-lg py-md font-bold text-on-surface-variant backdrop-blur-sm transition-colors hover:border-outline hover:text-on-surface">
                Log In
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Problem Framing */}
      <AnimatedSection className="py-16 px-lg bg-surface-container-low">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-display-md font-bold text-on-surface mb-md">The Limitation of Point-in-Time Audits</h2>
          <p className="text-body-lg text-on-surface-variant mb-sm">
            Traditional ergonomic assessments (RULA/REBA) provide a snapshot of risk at one moment — but repetitive strain and musculoskeletal injury risk accumulates continuously over an entire shift.
          </p>
          <p className="text-body-lg text-on-surface-variant">
            Workers adapt their posture minute by minute, and hazards that only appear occasionally are easy to miss in a manual audit.
          </p>
        </div>
      </AnimatedSection>

      <div className="h-px bg-outline-variant/20"></div>

      {/* How It Works */}
      <AnimatedSection className="py-20 px-lg">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-display-md font-bold text-on-surface mb-lg text-center">How It Works</h2>
          <div className="grid md:grid-cols-4 gap-lg">
            {[
              { icon: Camera, title: "Camera-Based Monitoring", desc: "Live video feed analyzed with MediaPipe pose estimation to track 33 skeletal landmarks in real time." },
              { icon: Activity, title: "7-Point Risk Scoring", desc: "Calculates per-joint ergonomic risk using RULA-informed logic, with clear visual indicators for each body part." },
              { icon: AlertTriangle, title: "Rule-Based Alerts", desc: "Configurable thresholds trigger immediate, explainable alerts to workers and supervisors when risk exceeds safe limits." },
              { icon: FileText, title: "Evidence-Backed Reports", desc: "Per-session reports with CSV/JSON/PDF export for compliance, analysis, and continuous improvement." }
            ].map((step, i) => (
              <div key={i} className="text-center">
                <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-md">
                  <step.icon className="w-8 h-8 text-primary" />
                </div>
                <h3 className="text-title-sm font-bold text-on-surface mb-sm">{step.title}</h3>
                <p className="text-body-sm text-on-surface-variant">{step.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </AnimatedSection>

      <div className="h-px bg-outline-variant/20"></div>

      {/* Visual Proof / Demo */}
      <AnimatedSection className="py-20 px-lg bg-surface-container">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-display-md font-bold text-on-surface mb-lg text-center">See It In Action</h2>
          <div className="bg-surface border border-outline-variant rounded-xl overflow-hidden shadow-xl">
            <div className="aspect-video relative">
              <video
                autoPlay
                muted
                loop
                playsInline
                preload="auto"
                className="w-full h-full object-cover"
                style={{ backgroundColor: "#000" }}
              >
                <source src="/videos/13386601_3840_2160_50fps.mp4" type="video/mp4" />
              </video>
              <div className="absolute inset-0 bg-gradient-to-t from-surface/80 to-transparent pointer-events-none"></div>
            </div>
            <div className="p-lg">
              <h3 className="text-title-lg font-bold text-on-surface mb-sm">Real-Time Posture Overlay & Risk Scoring</h3>
              <p className="text-body-sm text-on-surface-variant">
                The platform overlays a 33-point skeletal landmark tracking system on the live video feed, 
                calculating ergonomic risk scores for each joint in real time. No black-box AI — every score 
                is derived from auditable, threshold-based rules.
              </p>
            </div>
          </div>
        </div>
      </AnimatedSection>

      <div className="h-px bg-outline-variant/20"></div>

      {/* Core Capabilities */}
      <AnimatedSection className="py-20 px-lg bg-surface-container-low">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-display-md font-bold text-on-surface mb-lg text-center">Core Capabilities</h2>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-lg">
            <FeatureCard
              icon={Camera}
              title="Live Posture Monitoring"
              description="Real-time skeletal tracking using MediaPipe, with on-screen posture overlay for immediate worker feedback."
            />
            <FeatureCard
              icon={Activity}
              title="Ergonomic Risk Scoring"
              description="7-point risk scoring system per body part, with RULA-informed metrics as an additional visual signal."
            />
            <FeatureCard
              icon={AlertTriangle}
              title="Explainable Alerts"
              description="Rule-based threshold alerts that every safety manager can trace, audit, and adjust — no black-box ML."
            />
            <FeatureCard
              icon={FileText}
              title="Session Recording & Replay"
              description="Full session recording with synchronized risk data for post-incident review and coaching."
            />
            <FeatureCard
              icon={Users}
              title="Role-Based Access"
              description="Secure multi-user system with operator, supervisor, safety manager, and admin role levels."
            />
            <FeatureCard
              icon={Brain}
              title="Offline Local AI Assistant"
              description="Built-in AI assistant for product Q&A, running locally on your hardware with no cloud dependency."
            />
          </div>
        </div>
      </AnimatedSection>

      <div className="h-px bg-outline-variant/20"></div>

      {/* Why Threshold-Based */}
      <AnimatedSection className="py-20 px-lg">
        <div className="max-w-4xl mx-auto">
          <div className="bg-surface-container border border-primary/30 rounded-2xl p-xl">
            <h2 className="text-display-md font-bold text-on-surface mb-md">Why Threshold-Based, Not Black-Box ML?</h2>
            <p className="text-body-lg text-on-surface-variant mb-md">
              This is a deliberate design choice, not a limitation. For safety software that a factory has to trust and defend:
            </p>
            <ul className="space-y-sm text-body-sm text-on-surface-variant">
              <li className="flex items-start gap-sm">
                <div className="w-2 h-2 rounded-full bg-primary mt-1.5 shrink-0" />
                <span>Every alert traces to a specific, auditable joint angle or time threshold</span>
              </li>
              <li className="flex items-start gap-sm">
                <div className="w-2 h-2 rounded-full bg-primary mt-1.5 shrink-0" />
                <span>Safety managers can adjust rules to match their specific workstations and compliance requirements</span>
              </li>
              <li className="flex items-start gap-sm">
                <div className="w-2 h-2 rounded-full bg-primary mt-1.5 shrink-0" />
                <span>No unexpected "AI decisions" that you can't explain to your own safety officers or regulators</span>
              </li>
            </ul>
          </div>
        </div>
      </AnimatedSection>

      <div className="h-px bg-outline-variant/20"></div>

      {/* Pilot Program */}
      <AnimatedSection className="py-20 px-lg bg-surface-container-low">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-display-md font-bold text-on-surface mb-md">2-Week Free Pilot</h2>
          <p className="text-body-lg text-on-surface-variant mb-lg">
            Try a full single-station deployment on your factory floor, no strings attached. In exchange, we ask for your feedback and a potential case study (if you're open to it).
          </p>
          <Link to="/request-pilot" className="px-lg py-md rounded-lg bg-primary text-on-primary font-bold hover:opacity-90 transition-opacity flex items-center gap-sm mx-auto inline-flex">
            Request Your Pilot <ChevronRight className="w-5 h-5" />
          </Link>
        </div>
      </AnimatedSection>

      {/* Footer */}
      <footer className="py-12 px-lg border-t border-outline-variant">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-md">
          <div className="flex items-center gap-sm">
            <img src="/favicon.png" alt="ErgoVigilance" className="w-10 h-10 rounded-lg" />
            <span className="text-title-lg font-bold text-on-surface">ErgoVigilance</span>
          </div>
          <div className="flex items-center gap-md">
            <Link to="/login" className="text-body-sm text-on-surface-variant hover:text-on-surface transition-colors">
              Log In
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
