import { useEffect, useState } from 'react';
import { BarChart3, RefreshCw, ShieldCheck } from 'lucide-react';
import { SectionHeader } from '@/src/components/common';
import { useAuth } from '@/src/auth/AuthContext';
import { apiFetch } from '@/src/services/apiClient';
import { getSessions } from '@/src/services/dashboardService';

interface MetricSummary {
  count: number;
  min?: number;
  median?: number;
  max?: number;
}

interface BenchmarkSummary {
  generated_at: string | null;
  session_count: number;
  metrics: Record<string, MetricSummary>;
}

interface PercentileResult {
  metric: string;
  label: string;
  value: number;
  percentile: number | null;
  n: number;
  band: string;
}

const KEY_METRICS: Array<[string, string]> = [
  ['avg_neck_flexion', 'Neck flexion'],
  ['avg_trunk_flexion', 'Trunk flexion'],
  ['avg_forward_head_posture', 'Forward head'],
  ['avg_wrist_deviation_angle', 'Wrist deviation'],
  ['avg_knee_angle', 'Knee angle'],
];

const MANAGER_ROLES = new Set(['supervisor', 'safety_mgr', 'admin']);

export function BenchmarkCard() {
  const { user } = useAuth();
  const isManager = user ? MANAGER_ROLES.has(user.role) : false;

  const [summary, setSummary] = useState<BenchmarkSummary | null>(null);
  const [latest, setLatest] = useState<PercentileResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [rebuilding, setRebuilding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch('/api/benchmark');
      if (!res.ok) throw new Error(`Benchmark fetch failed (${res.status})`);
      const data = (await res.json()) as BenchmarkSummary;
      setSummary(data);

      // Rank the latest session's neck flexion against the baseline.
      try {
        const sessions = await getSessions(1, 5);
        const newest = sessions.sessions?.find((s) => typeof (s as unknown as Record<string, unknown>).avg_neck_flexion === 'number');
        if (newest) {
          const neck = (newest as unknown as Record<string, number>).avg_neck_flexion;
          const pRes = await apiFetch('/api/benchmark/percentile', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ metric: 'avg_neck_flexion', value: neck }),
          });
          if (pRes.ok) setLatest((await pRes.json()) as PercentileResult);
        }
      } catch {
        // Non-fatal: percentile sentence is an enhancement.
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Benchmark failed to load');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const rebuild = async () => {
    setRebuilding(true);
    setError(null);
    try {
      const res = await apiFetch('/api/benchmark/rebuild', { method: 'POST' });
      if (!res.ok) throw new Error(`Rebuild failed (${res.status})`);
      setSummary((await res.json()) as BenchmarkSummary);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Rebuild failed');
    } finally {
      setRebuilding(false);
    }
  };

  const n = summary?.session_count ?? 0;

  return (
    <div className="bg-surface-container border border-outline-variant rounded-xl p-lg">
      <div className="flex items-center justify-between">
        <SectionHeader title="Industry Benchmark" />
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-green-400" />
          <span className="text-[11px] text-on-surface-variant">De-identified — no worker data stored</span>
        </div>
      </div>

      {error && <div className="text-red-400 text-body-sm mb-sm">{error}</div>}

      {loading ? (
        <div className="text-center text-on-surface-variant py-xl text-body-sm">Loading benchmark…</div>
      ) : n === 0 ? (
        <div className="text-on-surface-variant text-body-sm py-md">
          No benchmark yet — recorded sessions become the baseline automatically. Run at least one session, then rebuild.
        </div>
      ) : (
        <>
          <p className="text-body-sm text-on-surface mb-md">
            Compared against <span className="text-on-surface font-semibold">{n}</span> recorded session{n === 1 ? '' : 's'}.
            {latest?.percentile !== null && latest?.percentile !== undefined && (
              <span className="block mt-1 text-primary font-medium">
                Your latest neck-flexion is in the <span className="text-display-sm font-bold">{Math.round(latest.percentile)}th</span> percentile — {latest.band === 'above-typical' ? 'above the typical range, worth a look' : latest.band === 'below-typical' ? 'below the typical range — good' : 'within the typical range'}.
              </span>
            )}
          </p>

          <div className="overflow-x-auto">
            <table className="w-full text-body-sm">
              <thead>
                <tr className="border-b border-outline-variant text-on-surface-variant text-[10px] uppercase tracking-wider">
                  <th className="text-left py-sm pr-md font-medium">Metric</th>
                  <th className="text-right py-sm px-md font-medium">Sessions</th>
                  <th className="text-right py-sm px-md font-medium">Median</th>
                  <th className="text-right py-sm px-md font-medium">Range</th>
                </tr>
              </thead>
              <tbody>
                {KEY_METRICS.map(([metric, label]) => {
                  const m = summary?.metrics?.[metric];
                  if (!m || !m.count) return null;
                  return (
                    <tr key={metric} className="border-b border-outline-variant/30">
                      <td className="py-sm pr-md text-on-surface">{label}</td>
                      <td className="py-sm px-md text-right text-on-surface-variant">{m.count}</td>
                      <td className="py-sm px-md text-right text-on-surface font-mono">{m.median?.toFixed(1) ?? '—'}°</td>
                      <td className="py-sm px-md text-right text-on-surface-variant font-mono">{m.min?.toFixed(1)}–{m.max?.toFixed(1)}°</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {isManager && (
            <div className="mt-md">
              <button
                onClick={rebuild}
                disabled={rebuilding}
                className="inline-flex items-center gap-sm px-md py-sm rounded-lg text-body-sm font-medium border border-outline-variant text-on-surface-variant hover:text-on-surface hover:bg-surface-container-higher transition-colors disabled:opacity-50"
                title="Rescan all sessions and rebuild the percentile pool"
              >
                <RefreshCw className={`w-4 h-4 ${rebuilding ? 'animate-spin' : ''}`} />
                {rebuilding ? 'Rebuilding…' : 'Rebuild baseline'}
              </button>
              <span className="ml-sm text-[11px] text-on-surface-variant">
                <BarChart3 className="inline w-3.5 h-3.5 mr-0.5" />
                Baseline: {summary?.generated_at ? new Date(summary.generated_at).toLocaleString() : '—'}
              </span>
            </div>
          )}
        </>
      )}
    </div>
  );
}
