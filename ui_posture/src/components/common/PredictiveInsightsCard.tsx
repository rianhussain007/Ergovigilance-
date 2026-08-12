import { useEffect, useState } from 'react';
import { LineChart, TrendingUp, Activity } from 'lucide-react';
import { apiFetch } from '@/src/services/apiClient';

interface Forecast {
  predicted_mean_risk: number | null;
  band: 'LOW' | 'MEDIUM' | 'HIGH' | null;
  confidence: number;
  insufficient_data: boolean;
  reason: string;
  method: 'model' | 'fallback';
  horizon_seconds?: number;
  model_metrics?: {
    next_window?: { mae: number; r2: number; rows: number };
    early_session?: { mae: number; r2: number; rows: number };
  };
}

interface Props {
  mode: 'live' | 'session';
  sessionId?: string;
  /** Re-fetch when this changes (e.g. live timeline length ticks). */
  refreshKey?: number | string;
  active?: boolean;
}

function bandColor(band: Forecast['band']): string {
  if (band === 'HIGH') return 'var(--color-chart-red)';
  if (band === 'MEDIUM') return 'var(--color-chart-orange)';
  return 'var(--color-chart-green)';
}

export function PredictiveInsightsCard({ mode, sessionId, refreshKey = 0, active = true }: Props) {
  const [forecast, setForecast] = useState<Forecast | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!active) {
      setForecast(null);
      return;
    }
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const url =
          mode === 'live'
            ? '/api/predictions/next-window'
            : `/api/predictions/session-forecast${sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : ''}`;
        const res = await apiFetch(url);
        if (!res.ok) throw new Error(`Forecast request failed (${res.status})`);
        const data = await res.json();
        if (cancelled) return;
        if (data.insufficient_data && data.forecast == null) {
          setForecast(null);
        } else {
          setForecast(data.forecast ?? null);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Forecast unavailable');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [mode, sessionId, refreshKey, active]);

  const f = forecast;

  return (
    <div className="bg-surface-container border border-outline-variant rounded-xl p-lg">
      <div className="flex items-center justify-between mb-md">
        <div className="flex items-center gap-sm">
          <Activity className="w-4 h-4 text-cyan-400" />
          <span className="font-label-caps text-label-caps text-on-surface uppercase tracking-widest">Predictive Insights</span>
        </div>
        {f?.method === 'model' ? (
          <span className="text-[9px] px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-400/30 font-medium" title="Forecast from the trained risk forecaster, cross-checked with the statistical baseline">
            ML model
          </span>
        ) : f?.method === 'fallback' ? (
          <span className="text-[9px] px-1.5 py-0.5 rounded bg-surface-container-higher text-on-surface-variant border border-outline-variant/40 font-medium" title="Statistical baseline (recent-window mean)">
            baseline
          </span>
        ) : null}
      </div>

      {error ? (
        <p className="text-[11px] text-red-400">{error}</p>
      ) : loading ? (
        <div className="h-16 bg-surface-container-high rounded-lg animate-pulse" />
      ) : !active ? (
        <p className="text-[11px] text-on-surface-variant">Start monitoring to see a risk forecast.</p>
      ) : f == null ? (
        <p className="text-[11px] text-on-surface-variant">
          {mode === 'live'
            ? 'No forecast yet — we need a few minutes of live data before predicting the next risk window.'
            : 'Not enough early-session data to forecast this session yet.'}
        </p>
      ) : (
        <div>
          <div className="flex items-end gap-md">
            <div>
              <p className="font-label-caps text-[9px] text-on-surface-variant uppercase tracking-widest">
                {mode === 'live' ? `Predicted risk · next ${Math.round((f.horizon_seconds ?? 600) / 60)} min` : 'Full-session risk forecast'}
              </p>
              <p className="font-label-mono text-3xl font-bold mt-1" style={{ color: bandColor(f.band) }}>
                {f.predicted_mean_risk != null ? f.predicted_mean_risk.toFixed(1) : '—'}
                <span className="text-sm text-on-surface-variant font-normal"> / 100</span>
              </p>
            </div>
            <div className="mb-1">
              <span
                className="inline-block text-[10px] font-bold px-2 py-0.5 rounded"
                style={{ color: bandColor(f.band), backgroundColor: `color-mix(in srgb, ${bandColor(f.band)} 12%, transparent)` }}
              >
                {f.band ?? '—'}
              </span>
              <p className="mt-1 text-[10px] text-on-surface-variant">
                Confidence {Math.round((f.confidence ?? 0) * 100)}%
              </p>
            </div>
          </div>

          {f.reason && (
            <p className="mt-sm text-[10px] text-on-surface-variant italic leading-relaxed">{f.reason}</p>
          )}

          {f.model_metrics?.next_window && (
            <div className="mt-sm pt-sm border-t border-outline-variant/50 flex items-center gap-md text-[9px] text-on-surface-variant">
              <span className="flex items-center gap-1"><LineChart className="w-3 h-3" /> MAE {f.model_metrics.next_window.mae}</span>
              <span>R² {f.model_metrics.next_window.r2}</span>
              <span className="flex items-center gap-1"><TrendingUp className="w-3 h-3" /> trained on {f.model_metrics.next_window.rows} windows</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
