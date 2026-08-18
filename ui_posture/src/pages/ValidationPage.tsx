import { useEffect, useState } from 'react';
import { Link } from 'react-router';
import { ShieldCheck, FlaskConical, Scale, EyeOff, ArrowUpRight, CheckCircle2, Clock } from 'lucide-react';
import { IndustrialBackdrop } from '@/src/components/common';

interface ModelMetrics {
  accuracy: number;
  per_class_accuracy: Record<string, number>;
  train_rows: number;
  test_rows: number;
  model_name: string;
}

interface GtEvaluation {
  accuracy?: number;
  overall?: { accuracy?: number };
  n_labeled_frames?: number;
  [key: string]: unknown;
}

const CORE_FEATURES: { name: string; unit: string; medium: string; high: string; note: string }[] = [
  { name: 'Neck flexion', unit: 'degrees', medium: '> 10°', high: '> 30°', note: 'Forward head tilt toward the work surface' },
  { name: 'Trunk flexion', unit: 'degrees', medium: '> 20°', high: '> 60°', note: 'Forward bend at the waist' },
  { name: 'Shoulder elevation', unit: 'degrees', medium: '> 30°', high: '> 60°', note: 'Arms raised at the shoulder (per side)' },
  { name: 'Shoulder symmetry', unit: 'percent', medium: '> 5%', high: '> 15%', note: 'Left/right imbalance while working' },
  { name: 'Alignment deviation', unit: 'percent', medium: '> 10%', high: '> 30%', note: 'Body off the neutral vertical line' },
  { name: 'Knee angle', unit: 'degrees', medium: '< 150°', high: '< 100°', note: 'Deep knee flexion (squatting)' },
];

export default function ValidationPage() {
  const [metrics, setMetrics] = useState<ModelMetrics | null>(null);
  const [gt, setGt] = useState<GtEvaluation | null>(null);
  const [gtExists, setGtExists] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      fetch('/results/best_model_metrics.json').then((r) => (r.ok ? r.json() : null)),
      fetch('/results/ground_truth_evaluation.json')
        .then((r) => (r.ok ? r.json() : null))
        .catch(() => null),
    ]).then(([m, g]) => {
      if (cancelled) return;
      setMetrics(m);
      setGt(g);
      setGtExists(!!g);
      setLoading(false);
    });
    return () => { cancelled = true; };
  }, []);

  const heldOutAccuracy = metrics ? (metrics.accuracy * 100).toFixed(1) : null;
  const gtAccuracy = gt
    ? ((gt.accuracy ?? gt.overall?.accuracy ?? 0) * 100).toFixed(1)
    : null;
  const headline = gtAccuracy ? `${gtAccuracy}%` : heldOutAccuracy ? `${heldOutAccuracy}%` : '—';
  const trainRows = metrics?.train_rows ?? 0;

  return (
    <div className="min-h-screen bg-background text-on-surface relative">
      <IndustrialBackdrop />
      <div className="relative z-10 max-w-5xl mx-auto px-lg py-xl">
        {/* ── Header ── */}
        <header className="flex items-center justify-between mb-xl">
          <Link to="/" className="flex items-center gap-sm">
            <img src="/favicon.png" alt="ErgoVigilance" className="w-9 h-9 rounded-lg" />
            <span className="text-title-lg font-bold">ErgoVigilance</span>
          </Link>
          <Link to="/request-pilot" className="text-body-sm font-semibold text-primary hover:underline flex items-center gap-1">
            Request a Free Pilot <ArrowUpRight className="w-4 h-4" />
          </Link>
        </header>

        <h1 className="text-display-sm font-extrabold mb-sm">How we validate</h1>
        <p className="text-body-lg text-on-surface-variant max-w-3xl mb-xl">
          Safety software earns trust with evidence, not adjectives. Here is exactly how
          ErgoVigilance is tested, what the numbers mean, and — just as importantly — what
          we do not claim.
        </p>

        {/* ── The number ── */}
        <section className="rounded-xl border border-outline-variant bg-surface-container p-lg mb-xl">
          <div className="flex items-center gap-sm mb-md">
            <ShieldCheck className="w-5 h-5 text-primary" />
            <h2 className="text-title-lg font-bold">The accuracy number, honestly framed</h2>
          </div>
          <div className="flex items-end gap-lg flex-wrap">
            <div>
              <p className="text-display-lg font-extrabold text-primary">{headline}</p>
              <p className="text-body-sm text-on-surface-variant">
                {gtAccuracy
                  ? 'overall accuracy on human-labeled ground-truth frames'
                  : 'held-out test-split accuracy on our training data'}
              </p>
            </div>
            <div className="flex-1 min-w-[260px]">
              {gtAccuracy ? (
                <p className="text-body-sm text-on-surface-variant">
                  This number comes from frames labeled by a human against the same scoring the
                  live engine uses, then evaluated by a model it has never seen.
                </p>
              ) : (
                <p className="text-body-sm text-on-surface-variant">
                  {loading
                    ? 'Loading metrics…'
                    : `Measured on a held-out split of ${trainRows.toLocaleString()} training rows. Honest caveat: the training labels are auto-generated by the risk engine itself, so this number measures the model's self-consistency with its own thresholds — not yet real-world accuracy. We are replacing it with human-labeled ground truth (see the ladder below), and we will not call it validated until then.`}
                </p>
              )}
            </div>
          </div>
        </section>

        {/* ── Validation ladder ── */}
        <section className="mb-xl">
          <div className="flex items-center gap-sm mb-md">
            <FlaskConical className="w-5 h-5 text-primary" />
            <h2 className="text-title-lg font-bold">The validation ladder</h2>
          </div>
          <div className="space-y-md">
            {[
              {
                title: '1 · The engine runs real shifts',
                status: 'done',
                body: 'Every alert traces to a measured joint angle and a documented threshold. The full pipeline — camera → pose → features → risk → alert → report — is exercised against real recorded sessions and a 230+ test suite.',
              },
              {
                title: '2 · Held-out model accuracy',
                status: 'done',
                body: `A gradient-boosting model was trained on ${trainRows.toLocaleString()} poses and evaluated on a held-out split it never saw. Useful as a self-consistency check — not yet a real-world claim.`,
              },
              {
                title: '3 · Human-labeled ground truth',
                status: gtExists ? 'done' : 'in-progress',
                body: gtExists
                  ? 'A human has labeled frames from real recordings against the same risk scoring used live, and the model is now evaluated against those labels.'
                  : 'Frames from real session recordings are being labeled by a human and will produce the first accuracy number we will call validated. This is our current focus — we would rather say "measuring" than overstate.',
              },
            ].map((r) => (
              <div key={r.title} className="rounded-lg border border-outline-variant bg-surface-container-low p-md flex gap-md">
                {r.status === 'done' ? (
                  <CheckCircle2 className="w-5 h-5 text-green-400 shrink-0 mt-0.5" />
                ) : (
                  <Clock className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
                )}
                <div>
                  <p className="text-body-md font-bold">{r.title}</p>
                  <p className="text-body-sm text-on-surface-variant">{r.body}</p>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* ── Methodology ── */}
        <section className="mb-xl">
          <div className="flex items-center gap-sm mb-md">
            <Scale className="w-5 h-5 text-primary" />
            <h2 className="text-title-lg font-bold">Methodology — thresholds you can inspect</h2>
          </div>
          <p className="text-body-sm text-on-surface-variant max-w-3xl mb-md">
            Risk is computed from RULA/REBA-informed thresholds on measured joint angles — not a
            black box. Every score traces to a specific feature, a specific threshold, and a
            specific frame. The core features and thresholds:
          </p>
          <div className="overflow-x-auto rounded-lg border border-outline-variant">
            <table className="w-full text-left text-body-sm">
              <thead className="bg-surface-container-high text-on-surface-variant">
                <tr>
                  <th className="px-md py-sm font-bold">Feature</th>
                  <th className="px-md py-sm font-bold">Unit</th>
                  <th className="px-md py-sm font-bold">Medium risk</th>
                  <th className="px-md py-sm font-bold">High risk</th>
                  <th className="px-md py-sm font-bold">What it measures</th>
                </tr>
              </thead>
              <tbody>
                {CORE_FEATURES.map((f) => (
                  <tr key={f.name} className="border-t border-outline-variant/50">
                    <td className="px-md py-sm font-semibold">{f.name}</td>
                    <td className="px-md py-sm">{f.unit}</td>
                    <td className="px-md py-sm">{f.medium}</td>
                    <td className="px-md py-sm">{f.high}</td>
                    <td className="px-md py-sm text-on-surface-variant">{f.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-body-sm text-on-surface-variant mt-md">
            Beyond the core set, the engine also measures head tilt, forward head posture, elbow
            flexion, wrist deviation, stance stability, and weight shift — all explainable, all
            adjustable per workstation by the site administrator.
          </p>
        </section>

        {/* ── What we don't claim ── */}
        <section className="mb-xl">
          <div className="flex items-center gap-sm mb-md">
            <EyeOff className="w-5 h-5 text-amber-400" />
            <h2 className="text-title-lg font-bold">What we do not claim</h2>
          </div>
          <ul className="space-y-sm text-body-sm text-on-surface-variant max-w-3xl">
            <li>• Not a medical device. The system does not diagnose or treat any condition.</li>
            <li>• Thresholds are heuristic and informed by published RULA/REBA methodology — they are not clinically validated.</li>
            <li>• One camera per workstation, monocular vision: occlusion, extreme angles, and low light reduce accuracy.</li>
            <li>• A static photo or screen of a face is detected and flagged, but a video replay of a live person is the honest limit of a single camera.</li>
            <li>• Reports are for awareness and prioritization — a starting point for a qualified ergonomist or safety professional, never a substitute.</li>
          </ul>
        </section>

        {/* ── CTA ── */}
        <section className="rounded-xl border border-primary/30 bg-surface-container p-lg text-center">
          <h2 className="text-title-lg font-bold mb-sm">See it on one workstation for two weeks.</h2>
          <p className="text-body-sm text-on-surface-variant mb-md">
            Free. No card. Your video never leaves your building.
          </p>
          <Link to="/request-pilot" className="inline-flex items-center gap-1 rounded-lg bg-primary px-lg py-sm font-bold text-on-primary hover:opacity-90">
            Request a Free Pilot <ArrowUpRight className="w-4 h-4" />
          </Link>
        </section>
      </div>
    </div>
  );
}
