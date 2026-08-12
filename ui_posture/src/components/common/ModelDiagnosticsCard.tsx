import { useEffect, useState } from 'react';
import { Brain } from 'lucide-react';

interface ModelMetrics {
  accuracy: number;
  labels: string[];
  confusion_matrix: number[][];
  per_class_accuracy: Record<string, number>;
  classification_report: Record<string, { precision: number; recall: number; 'f1-score': number; support: number }>;
  best_params: Record<string, number>;
  train_rows: number;
  test_rows: number;
  model_name: string;
  model_comparison: Record<string, { accuracy: number; best_params: Record<string, number>; per_class_accuracy: Record<string, number> }>;
}

/**
 * Internal model diagnostics (training accuracy, per-class metrics, benchmark
 * comparison). Admin-only — these are engineering internals, not something a
 * pilot customer needs on the primary dashboard.
 */
export default function ModelDiagnosticsCard() {
  const [metrics, setMetrics] = useState<ModelMetrics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetch('/results/best_model_metrics.json')
      .then((r) => r.json())
      .then((data) => { if (!cancelled) setMetrics(data); })
      .catch(() => { if (!cancelled) setMetrics(null); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  const accuracy = metrics ? (metrics.accuracy * 100).toFixed(1) : '—';
  const rawModelName = metrics?.model_name ?? '';
  // The live engine uses HistGradientBoosting (trained by scripts/train_svm.py
  // — the file name predates the migration). Display that, not the legacy name.
  const modelName = rawModelName.includes('hist') || rawModelName.includes('gradient')
    ? 'Gradient Boosting (HistGradientBoosting)'
    : (rawModelName.replace('_', ' ') || '—');
  const trainRows = metrics?.train_rows ?? 0;
  const testRows = metrics?.test_rows ?? 0;
  const perClass: Record<string, number> = metrics?.per_class_accuracy ?? {};
  const benchmarkAccuracy = metrics?.model_comparison?.random_forest?.accuracy;
  const perClassValues = Object.values(perClass).map((v) => Number(v) * 100);
  const maxPerClass = perClassValues.length > 0 ? Math.max(...perClassValues) : 1;

  return (
    <div className="w-full rounded-lg border border-outline-variant bg-surface-container-low p-lg">
      <div className="flex items-center gap-sm mb-md">
        <Brain className="w-4 h-4 text-primary" />
        <h3 className="text-body-sm font-bold text-on-surface">Risk Model</h3>
      </div>
      {loading ? (
        <div className="space-y-sm">
          <div className="h-4 bg-surface-container-higher rounded animate-pulse" />
          <div className="h-4 bg-surface-container-higher rounded animate-pulse w-3/4" />
        </div>
      ) : metrics ? (
        <div className="space-y-sm">
          <div className="flex items-center justify-between rounded-lg bg-surface-container-low border border-outline-variant/60 px-md py-sm">
            <span className="text-body-sm text-on-surface-variant">Accuracy</span>
            <span className="font-label-mono text-on-surface">{accuracy}%</span>
          </div>
          <div className="rounded-lg bg-surface-container-low border border-outline-variant/60 px-md py-sm">
            <p className="font-label-caps text-[9px] text-on-surface-variant mb-xs">Per-Class Accuracy</p>
            <div className="space-y-xs">
              {Object.entries(perClass).map(([label, val]) => {
                const value = Number(val);
                return (
                  <div key={label}>
                    <div className="flex justify-between text-[10px] mb-0.5">
                      <span className="text-on-surface-variant">{label}</span>
                      <span className="font-mono text-on-surface">{(value * 100).toFixed(1)}%</span>
                    </div>
                    <div className="h-1 rounded-full bg-surface-container-highest overflow-hidden">
                      <div className="h-full rounded-full bg-primary" style={{ width: `${(value * 100) / maxPerClass * 100}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
          <div className="flex items-center justify-between rounded-lg bg-surface-container-low border border-outline-variant/60 px-md py-sm">
            <span className="text-body-sm text-on-surface-variant">Model</span>
            <span className="font-label-mono text-on-surface capitalize">{modelName}</span>
          </div>
          <div className="flex items-center justify-between rounded-lg bg-surface-container-low border border-outline-variant/60 px-md py-sm">
            <span className="text-body-sm text-on-surface-variant">Training / Test</span>
            <span className="font-label-mono text-on-surface">{trainRows} / {testRows}</span>
          </div>
          {benchmarkAccuracy !== undefined && (
            <div className="flex items-center justify-between rounded-lg bg-surface-container-low border border-outline-variant/60 px-md py-sm">
              <span className="text-body-sm text-on-surface-variant">vs Random Forest</span>
              <span className="font-label-mono text-on-surface-variant">{(benchmarkAccuracy * 100).toFixed(1)}%</span>
            </div>
          )}
        </div>
      ) : (
        <p className="text-body-sm text-on-surface-variant">Model metrics unavailable.</p>
      )}
    </div>
  );
}
