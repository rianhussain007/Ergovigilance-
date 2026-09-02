import { Brain, AlertTriangle, BarChart3 } from 'lucide-react';

interface ClassMetrics {
  className: string;
  precision: number;
  recall: number;
  f1: number;
  support: number;
}

const RISK_MODEL = {
  accuracy: 0.876, macroF1: 0.824,
  classes: [
    { className: 'LOW', precision: 1.0, recall: 0.572, f1: 0.728, support: 145 },
    { className: 'MEDIUM', precision: 0.851, recall: 1.0, f1: 0.92, support: 355 },
    { className: 'HIGH', precision: 0, recall: 0, f1: 0, support: 0 },
  ],
  notes: [
    'Evaluated on 500 labeled frames from 1 session',
    'LOW recall 57% - some LOW classified as MEDIUM',
    'Conservative bias - false positives safer than false negatives',
    'No HIGH-risk frames in ground truth',
    'Ground truth: manual annotation by specialist',
  ],
};

const TASK_MODEL = {
  accuracy: 0.891,
  classes: [
    { className: 'Seated Work', precision: 0.891, recall: 1.0, f1: 0.943, support: 41 },
    { className: 'Assembly Work', precision: 0, recall: 0, f1: 0, support: 4 },
    { className: 'Inspection', precision: 0, recall: 0, f1: 0, support: 1 },
  ],
  notes: [
    'Evaluated on 46 human-labeled frames',
    '89.1% accuracy misleading - predicts ALL as Seated Work',
    'Zero recall on Assembly/Inspection',
    'Root cause: extreme class imbalance',
    'Task classifier is screening aid only',
  ],
};

function MetricBar({ value, color }: { value: number; color: string }) {
  return (
    <div className="h-2 rounded-full bg-surface-container-highest overflow-hidden">
      <div className="h-full rounded-full" style={{ width: (value * 100) + '%', backgroundColor: color }} />
    </div>
  );
}

function MetricsTable({ classes, title }: { classes: ClassMetrics[]; title: string }) {
  return (
    <section className="rounded-2xl border border-outline-variant bg-surface-container p-lg">
      <h3 className="text-title-sm font-bold text-on-surface mb-md">{title}</h3>
      <table className="w-full text-body-sm">
        <thead><tr className="border-b border-outline-variant">
          <th className="text-left py-sm px-sm text-on-surface-variant">Class</th>
          <th className="text-right py-sm px-sm text-on-surface-variant">Precision</th>
          <th className="text-right py-sm px-sm text-on-surface-variant">Recall</th>
          <th className="text-right py-sm px-sm text-on-surface-variant">F1</th>
          <th className="text-right py-sm px-sm text-on-surface-variant">N</th>
          <th className="py-sm px-sm w-32"></th>
        </tr></thead>
        <tbody>
          {classes.map((c) => (
            <tr key={c.className} className="border-b border-outline-variant/50">
              <td className="py-sm px-sm font-medium text-on-surface">{c.className}</td>
              <td className="py-sm px-sm text-right font-mono">{(c.precision * 100).toFixed(1)}%</td>
              <td className="py-sm px-sm text-right font-mono">{(c.recall * 100).toFixed(1)}%</td>
              <td className="py-sm px-sm text-right font-mono">{(c.f1 * 100).toFixed(1)}%</td>
              <td className="py-sm px-sm text-right font-mono text-on-surface-variant">{c.support}</td>
              <td className="py-sm px-sm"><MetricBar value={c.f1} color={c.f1 > 0.8 ? '#22c55e' : c.f1 > 0.5 ? '#f59e0b' : '#ef4444'} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

export default function ModelCardPage() {
  return (
    <div className="p-lg space-y-lg pb-32">
      <div>
        <h1 className="text-display-lg font-bold text-on-surface">Model Card</h1>
        <p className="text-body-sm text-on-surface-variant mt-xs">Honest, transparent display of model performance</p>
      </div>

      <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-md flex items-start gap-md">
        <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
        <div>
          <p className="text-body-sm font-bold text-on-surface">Transparency Notice</p>
          <p className="text-body-sm text-on-surface-variant mt-1">
            Metrics from controlled evaluations. Real-world performance varies. Screening aids, not medical devices.
          </p>
        </div>
      </div>

      <section className="rounded-2xl border border-outline-variant bg-surface-container p-lg space-y-md">
        <div className="flex items-center gap-md">
          <div className="w-12 h-12 rounded-xl bg-red-500/15 flex items-center justify-center">
            <Brain className="w-6 h-6 text-red-400" />
          </div>
          <div>
            <h2 className="text-title-sm font-bold text-on-surface">Risk Classification Model</h2>
            <p className="text-body-sm text-on-surface-variant">MediaPipe Pose + heuristic rules</p>
          </div>
          <div className="ml-auto text-right">
            <p className="text-title-lg font-bold text-on-surface">{(RISK_MODEL.accuracy * 100).toFixed(1)}%</p>
            <p className="text-[10px] text-on-surface-variant">Accuracy</p>
          </div>
        </div>
        <div className="grid grid-cols-3 gap-md text-center">
          <div><p className="text-title-lg font-bold">{(RISK_MODEL.macroF1 * 100).toFixed(1)}%</p><p className="text-[10px] text-on-surface-variant">Macro F1</p></div>
          <div><p className="text-title-lg font-bold">500</p><p className="text-[10px] text-on-surface-variant">Labeled Frames</p></div>
          <div><p className="text-title-lg font-bold">1</p><p className="text-[10px] text-on-surface-variant">Session</p></div>
        </div>
        <MetricsTable classes={RISK_MODEL.classes} title="Per-Class Performance" />
        <div className="space-y-xs">
          <p className="text-body-sm font-bold text-on-surface">Known Limitations</p>
          {RISK_MODEL.notes.map((n, i) => <div key={i} className="text-body-sm text-on-surface-variant">{i+1}. {n}</div>)}
        </div>
      </section>

      <section className="rounded-2xl border border-outline-variant bg-surface-container p-lg space-y-md">
        <div className="flex items-center gap-md">
          <div className="w-12 h-12 rounded-xl bg-blue-500/15 flex items-center justify-center">
            <BarChart3 className="w-6 h-6 text-blue-400" />
          </div>
          <div>
            <h2 className="text-title-sm font-bold text-on-surface">Task Classification Model</h2>
            <p className="text-body-sm text-on-surface-variant">sklearn pipeline</p>
          </div>
          <div className="ml-auto text-right">
            <p className="text-title-lg font-bold text-on-surface">{(TASK_MODEL.accuracy * 100).toFixed(1)}%</p>
            <p className="text-[10px] text-on-surface-variant">Headline*</p>
          </div>
        </div>
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-sm">
          <p className="text-[11px] text-red-400 font-medium">
            * Misleading - predicts ALL as Seated Work. Zero recall on 2/3 classes.
          </p>
        </div>
        <MetricsTable classes={TASK_MODEL.classes} title="Per-Class Performance" />
        <div className="space-y-xs">
          <p className="text-body-sm font-bold text-on-surface">Known Limitations</p>
          {TASK_MODEL.notes.map((n, i) => <div key={i} className="text-body-sm text-on-surface-variant">{i+1}. {n}</div>)}
        </div>
      </section>

      <section className="rounded-2xl border border-outline-variant bg-surface-container p-lg">
        <h2 className="text-title-sm font-bold text-on-surface mb-sm">Improvement Roadmap</h2>
        <div className="space-y-xs text-body-sm text-on-surface-variant">
          <p>- Collect 500+ frames per task class</p>
          <p>- Add HIGH-risk ground truth across 5+ sessions</p>
          <p>- Validate across workers, lighting, camera angles</p>
          <p>- Publish updated card after each retraining</p>
        </div>
      </section>
    </div>
  );
}
