import { useState } from 'react';
import { Link } from 'react-router';
import {
  Check, X, Camera, Cloud, Server, Shield, BarChart3, Users,
  Headphones, Zap, ArrowRight, Building2, Globe, Lock,
  FileText, AlertTriangle, Radio, Eye,
} from 'lucide-react';
import Logo from '../components/common/Logo';

const TIERS = [
  {
    id: 'starter',
    name: 'On-Premise Starter',
    tagline: 'For small facilities with 1-4 cameras',
    price: 'Free',
    priceDetail: 'Open source + self-hosted',
    icon: Server,
    color: 'blue',
    popular: false,
    features: [
      { text: 'Up to 4 USB/webcam feeds', included: true },
      { text: 'Real-time 33-point pose tracking', included: true },
      { text: 'RULA/REBA risk scoring', included: true },
      { text: 'Live dashboard + alerts', included: true },
      { text: 'PDF/CSV report export', included: true },
      { text: 'Session recording + replay', included: true },
      { text: 'Worker management', included: true },
      { text: 'AI Assistant (local Ollama)', included: true },
      { text: 'RTSP/CCTV camera support', included: false },
      { text: 'Multi-site fleet management', included: false },
      { text: 'Priority support', included: false },
      { text: 'Custom integrations', included: false },
    ],
  },
  {
    id: 'cloud',
    name: 'Cloud Professional',
    tagline: 'For factories with IP cameras — zero on-site hardware',
    price: '$299',
    priceDetail: '/month per 10 cameras',
    icon: Cloud,
    color: 'cyan',
    popular: true,
    features: [
      { text: 'Up to 20 RTSP/IP cameras', included: true },
      { text: 'YOLOv8-pose cloud inference', included: true },
      { text: 'Real-time risk scoring + alerts', included: true },
      { text: 'Email & Slack notifications', included: true },
      { text: 'Daily/weekly PDF reports', included: true },
      { text: 'Single-site dashboard', included: true },
      { text: 'Worker trend analytics', included: true },
      { text: 'REST API access', included: true },
      { text: '99.5% uptime target', included: true },
      { text: 'Priority email support', included: true },
      { text: 'Custom alert rules', included: false },
      { text: 'Multi-site fleet management', included: false },
    ],
  },
  {
    id: 'enterprise',
    name: 'Enterprise',
    tagline: 'For large manufacturers with 50+ cameras across multiple sites',
    price: 'Custom',
    priceDetail: 'Volume pricing + dedicated support',
    icon: Building2,
    color: 'purple',
    popular: false,
    features: [
      { text: 'Everything in Cloud Professional', included: true },
      { text: '50+ cameras across all sites', included: true },
      { text: 'Dedicated GPU inference cluster', included: true },
      { text: 'Custom risk model training', included: true },
      { text: 'Multi-site fleet dashboard', included: true },
      { text: 'On-premise deployment option', included: true },
      { text: 'Custom integrations (ERP, CMMS)', included: true },
      { text: 'Dedicated success manager', included: true },
      { text: 'SLA with 4-hour response', included: true },
      { text: 'Audit trail + compliance export', included: true },
      { text: 'Webhook integrations', included: true },
      { text: 'Volume discounts (50+ cameras)', included: true },
    ],
  },
];

const FAQ = [
  {
    q: 'How does the free on-premise version work?',
    a: 'Install Docker, plug in a webcam, and run `docker compose up`. The full platform — dashboard, alerts, reports, AI assistant — runs on your local machine with zero internet required. Open source under MIT license.',
  },
  {
    q: 'What cameras does the cloud version support?',
    a: 'Any camera with an RTSP stream — which is virtually every IP camera made after 2015. Hikvision, Dahua, Axis, Reolink, Amcrest, and thousands more. If your camera has a web interface, it almost certainly has RTSP.',
  },
  {
    q: 'Is worker data kept private?',
    a: 'Yes. On-premise mode: data never leaves your network. Cloud mode: we process video frames in-memory and only store anonymized pose keypoints (no faces, no video). Full GDPR compliance, per-worker right-to-erasure, configurable retention.',
  },
  {
    q: 'How accurate is the risk scoring?',
    a: 'The system uses RULA/REBA-informed models trained on 30,698 labeled poses. On-premise (MediaPipe) achieves 87.6% agreement with human assessors on 500 labeled frames (LOW/MEDIUM risk categories; HIGH unvalidated). Real-world accuracy depends on camera angle, lighting, and worker body types — which is exactly why we recommend a pilot to validate for your facility. It is a screening aid, not a medical device.',
  },
  {
    q: 'Can I try before buying?',
    a: 'Absolutely. The on-premise version is free forever. For the cloud version, we offer a 14-day free trial with full features — start monitoring immediately after signing up.'
  },
];

export default function PricingPage() {
  const [annual, setAnnual] = useState(false);
  const [checkoutLoading, setCheckoutLoading] = useState(false);

  const handleCheckout = async () => {
    setCheckoutLoading(true);
    try {
      const res = await fetch('/api/billing/checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tier: 'cloud' }),
      });
      const data = await res.json();
      if (data.checkout_url) {
        window.location.href = data.checkout_url;
      } else {
        // Stripe not configured — redirect to request pilot
        window.location.href = '/request-pilot';
      }
    } catch {
      window.location.href = '/request-pilot';
    } finally {
      setCheckoutLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0b0f14]">
      {/* Header */}
      <header className="relative z-10 border-b border-white/5">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3">
            <Logo className="h-8 w-auto" variant="light" />
          </Link>
          <div className="flex items-center gap-4">
            <Link to="/login" className="text-sm text-slate-400 hover:text-white transition-colors">
              Sign In
            </Link>
            <Link
              to="/request-pilot"
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg transition-colors"
            >
              Request a Pilot
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="relative py-20 text-center">
        <div className="max-w-3xl mx-auto px-6">
          <h1 className="text-4xl sm:text-5xl font-bold text-white mb-4">
            Simple, transparent pricing
          </h1>
          <p className="text-lg text-slate-400 mb-8">
            Choose self-hosted for full control or cloud for zero-maintenance. Both include the same AI-powered ergonomic monitoring.
          </p>
          <div className="flex items-center justify-center gap-3">
            <span className={`text-sm ${!annual ? 'text-white' : 'text-slate-500'}`}>Monthly</span>
            <button
              onClick={() => setAnnual(!annual)}
              className={`relative w-12 h-6 rounded-full transition-colors ${annual ? 'bg-blue-600' : 'bg-slate-600'}`}
            >
              <div className={`absolute top-0.5 w-5 h-5 rounded-full bg-white transition-transform ${annual ? 'translate-x-6' : 'translate-x-0.5'}`} />
            </button>
            <span className={`text-sm ${annual ? 'text-white' : 'text-slate-500'}`}>
              Annual <span className="text-green-400 text-xs font-medium">Save 20%</span>
            </span>
          </div>
        </div>
      </section>

      {/* Pricing Cards */}
      <section className="relative pb-20">
        <div className="max-w-6xl mx-auto px-6 grid md:grid-cols-3 gap-6">
          {TIERS.map((tier) => {
            const Icon = tier.icon;
            const displayPrice = tier.id === 'cloud' && annual
              ? '$239'
              : tier.price;
            const displayDetail = tier.id === 'cloud' && annual
              ? '/month per 10 cameras (billed annually)'
              : tier.priceDetail;

            return (
              <div
                key={tier.id}
                className={`relative rounded-2xl border p-8 flex flex-col ${
                  tier.popular
                    ? 'border-cyan-500/50 bg-gradient-to-b from-cyan-500/[0.08] to-transparent shadow-lg shadow-cyan-500/10'
                    : 'border-white/10 bg-white/[0.02]'
                }`}
              >
                {tier.popular && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 bg-cyan-500 text-white text-xs font-bold rounded-full">
                    MOST POPULAR
                  </div>
                )}
                <div className="mb-6">
                  <Icon className={`w-8 h-8 mb-4 ${
                    tier.color === 'cyan' ? 'text-cyan-400' :
                    tier.color === 'purple' ? 'text-purple-400' :
                    'text-blue-400'
                  }`} />
                  <h3 className="text-xl font-bold text-white">{tier.name}</h3>
                  <p className="text-sm text-slate-400 mt-1">{tier.tagline}</p>
                </div>
                <div className="mb-6">
                  <span className="text-4xl font-bold text-white">{displayPrice}</span>
                  <span className="text-sm text-slate-400 ml-1">{displayDetail}</span>
                </div>
                <ul className="space-y-3 mb-8 flex-1">
                  {tier.features.map((f, i) => (
                    <li key={i} className="flex items-start gap-2.5 text-sm">
                      {f.included ? (
                        <Check className="w-4 h-4 text-green-400 mt-0.5 shrink-0" />
                      ) : (
                        <X className="w-4 h-4 text-slate-600 mt-0.5 shrink-0" />
                      )}
                      <span className={f.included ? 'text-slate-300' : 'text-slate-600'}>
                        {f.text}
                      </span>
                    </li>
                  ))}
                </ul>
                {tier.id === 'cloud' ? (
                  <button
                    onClick={handleCheckout}
                    disabled={checkoutLoading}
                    className={`block w-full text-center py-3 rounded-xl font-semibold text-sm transition-all ${
                      'bg-gradient-to-r from-cyan-600 to-blue-600 text-white hover:from-cyan-500 hover:to-blue-500 hover:shadow-lg hover:shadow-cyan-500/20 disabled:opacity-50'
                    }`}
                  >
                    {checkoutLoading ? 'Loading...' : 'Start Free Trial'}
                  </button>
                ) : (
                  <Link
                    to={tier.id === 'starter' ? '/login' : '/request-pilot'}
                    className={`block text-center py-3 rounded-xl font-semibold text-sm transition-all ${
                      tier.color === 'purple'
                        ? 'bg-purple-600/20 text-purple-300 border border-purple-500/30 hover:bg-purple-600/30'
                        : 'bg-white/5 text-white border border-white/15 hover:bg-white/10'
                    }`}
                  >
                    {tier.id === 'starter' ? 'Get Started Free' : 'Contact Sales'}
                  </Link>
                )}
              </div>
            );
          })}
        </div>
      </section>

      {/* Feature Comparison */}
      <section className="relative py-20 border-t border-white/5">
        <div className="max-w-5xl mx-auto px-6">
          <h2 className="text-2xl font-bold text-white text-center mb-12">Compare all features</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/10">
                  <th className="text-left py-3 px-4 text-slate-400 font-medium">Feature</th>
                  <th className="text-center py-3 px-4 text-blue-400 font-medium">Starter</th>
                  <th className="text-center py-3 px-4 text-cyan-400 font-medium">Cloud</th>
                  <th className="text-center py-3 px-4 text-purple-400 font-medium">Enterprise</th>
                </tr>
              </thead>
              <tbody className="text-slate-300">
                {[
                  ['Real-time pose tracking', true, true, true],
                  ['RULA/REBA risk scoring', true, true, true],
                  ['Live dashboard + alerts', true, true, true],
                  ['PDF/CSV report export', true, true, true],
                  ['Session recording + replay', true, true, true],
                  ['AI Assistant', true, true, true],
                  ['RTSP camera support', false, true, true],
                  ['Email/Slack notifications', false, true, true],
                  ['Single-site dashboard', false, true, true],
                  ['REST API access', false, true, true],
                  ['99.5% uptime target', false, true, true],
                  ['Custom risk model training', false, false, true],
                  ['Multi-site fleet dashboard', false, false, true],
                  ['On-premise cloud option', false, false, true],
                  ['Custom ERP/CMMS integrations', false, false, true],
                  ['Webhook integrations', false, false, true],
                ].map(([feature, ...tiers], i) => (
                  <tr key={i} className="border-b border-white/5 hover:bg-white/[0.02]">
                    <td className="py-3 px-4">{feature}</td>
                    {tiers.map((included, j) => (
                      <td key={j} className="text-center py-3 px-4">
                        {included ? (
                          <Check className="w-4 h-4 text-green-400 mx-auto" />
                        ) : (
                          <X className="w-4 h-4 text-slate-600 mx-auto" />
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="relative py-20 border-t border-white/5">
        <div className="max-w-3xl mx-auto px-6">
          <h2 className="text-2xl font-bold text-white text-center mb-12">Frequently asked questions</h2>
          <div className="space-y-6">
            {FAQ.map((item, i) => (
              <div key={i} className="bg-white/[0.03] border border-white/10 rounded-xl p-6">
                <h3 className="text-base font-semibold text-white mb-2">{item.q}</h3>
                <p className="text-sm text-slate-400 leading-relaxed">{item.a}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="relative py-20 border-t border-white/5">
        <div className="max-w-3xl mx-auto px-6 text-center">
          <h2 className="text-3xl font-bold text-white mb-4">
            Start protecting your workers today
          </h2>
          <p className="text-slate-400 mb-8">
            Deploy in under 10 minutes. No special hardware. No IT integration required.
          </p>
          <div className="flex items-center justify-center gap-4">
            <Link
              to="/request-pilot"
              className="px-8 py-4 bg-gradient-to-r from-blue-600 to-cyan-500 text-white font-bold rounded-xl hover:from-blue-500 hover:to-cyan-400 transition-all hover:shadow-lg hover:shadow-blue-500/25"
            >
              Request a Free Pilot
            </Link>
            <Link
              to="/login"
              className="px-6 py-4 border border-white/15 text-slate-300 font-semibold rounded-xl hover:text-white hover:border-white/30 transition-all"
            >
              Try the Demo
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
