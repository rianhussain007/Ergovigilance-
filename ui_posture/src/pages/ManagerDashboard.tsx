import { useState, useEffect } from 'react';
import { Users, AlertTriangle, TrendingUp, Activity } from 'lucide-react';
import { AnalyticCard } from '@/src/components/cards';
import { SectionHeader, ErrorCard, LoadingCard, EmptyState } from '@/src/components/common';
import { getManagerSummary } from '@/src/services/dashboardService';
import type { ManagerSummary, WorkerSummary } from '@/src/types/api';

const colorMap = { low: 'bg-green-500', moderate: 'bg-orange-500', high: 'bg-red-500' };
const pulseMap = { low: '', moderate: 'animate-pulse', high: 'animate-pulse' };

/** Avatar initials: first + last initial when available, else first two
 *  letters of a single-word name ("Asha Patel" -> AP, "Praneeth" -> PR). */
function workerInitials(name: string): string {
  const parts = (name || '').trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

const gridPositions = [
  { x: '10%', y: '15%' }, { x: '35%', y: '10%' }, { x: '60%', y: '18%' }, { x: '85%', y: '12%' },
  { x: '15%', y: '40%' }, { x: '40%', y: '45%' }, { x: '65%', y: '38%' }, { x: '88%', y: '42%' },
  { x: '25%', y: '70%' }, { x: '55%', y: '75%' },
];

export default function ManagerDashboard() {
  const [manager, setManager] = useState<ManagerSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<WorkerSummary | null>(null);

  // ── fetch real data ───────────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    const fetchManager = async () => {
      try {
        const data = await getManagerSummary();
        if (!cancelled) { setManager(data); setError(null); }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load manager data');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchManager();
    const interval = setInterval(fetchManager, 30000);
    return () => { cancelled = true; clearInterval(interval); };
  }, []);

  if (error) return <div className="flex items-center justify-center h-full p-lg"><ErrorCard message={error} onRetry={() => { setLoading(true); setError(null); }} /></div>;

  // Single source of truth — manager is null while first fetch is in flight
  const data = {
    manager: manager ?? {
      registeredWorkers: 0, highRiskWorkers: 0, todayAlerts: 0,
      sessionsCompleted: 0, mostCommonIssue: '', workers: [],
    } as ManagerSummary,
    workers: manager?.workers ?? [],
  };

  if (loading) {
    return (
      <div className="p-lg space-y-lg pb-32">
        <LoadingCard height="h-24" />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-lg">
          <div className="lg:col-span-2"><LoadingCard height="h-[450px]" /></div>
          <div className="space-y-lg"><LoadingCard height="h-48" /><LoadingCard height="h-48" /></div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-lg space-y-lg pb-32">
      <div>
        <h1 className="text-display-lg font-bold text-on-surface">Manager Dashboard</h1>
        <p className="text-body-sm text-on-surface-variant mt-xs">Factory-wide ergonomic overview</p>
      </div>

      {manager?.degraded && (
        <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-md py-sm text-[12px] text-amber-300">
          <strong>Data degraded — database unavailable.</strong> The numbers below are
          sample/mock data, not live floor data. Check the backend database and restart
          it to restore real reporting.
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-md">
        <AnalyticCard label="Registered Workers" value={data.manager.registeredWorkers} accent />
        <AnalyticCard 
          label="High Risk" 
          value={data.manager.highRiskWorkers} 
          isUrgent={true} 
          tone={data.manager.highRiskWorkers > 0 ? 'danger' : 'good'} 
        />
        <AnalyticCard 
          label="Today's Alerts" 
          value={data.manager.todayAlerts} 
          isUrgent={true} 
          tone={data.manager.todayAlerts > 0 ? 'warning' : 'good'} 
        />
        <AnalyticCard label="Sessions Completed" value={data.manager.sessionsCompleted} />
        <AnalyticCard label="Most Common Issue" value={data.manager.mostCommonIssue || '—'} />
      </div>

      <div className="bg-surface-container border border-outline-variant rounded-xl p-lg">
        <SectionHeader title="Cross-Session Metrics" />
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-md mt-md">
          <div className="bg-surface-container-low rounded-lg p-md border border-outline-variant/50 text-center" title="Average session risk over the last 7 days compared with the 7 days before that. With few sessions yet, this figure can swing widely and is directional, not a precise measurement.">
            <TrendingUp className={`w-5 h-5 mx-auto mb-xs ${data.manager.weeklyImprovement !== null && data.manager.weeklyImprovement !== undefined && data.manager.weeklyImprovement < 0 ? 'text-red-400' : 'text-green-400'}`} />
            <p className={`text-title-lg font-bold ${data.manager.weeklyImprovement === null || data.manager.weeklyImprovement === undefined ? 'text-on-surface-variant' : data.manager.weeklyImprovement < 0 ? 'text-red-400' : 'text-green-400'}`}>
              {data.manager.weeklyImprovement === null || data.manager.weeklyImprovement === undefined
                ? '—'
                : `${data.manager.weeklyImprovement > 0 ? '+' : ''}${data.manager.weeklyImprovement.toFixed(1)}%`}
            </p>
            <p className="text-[9px] font-bold uppercase tracking-widest text-on-surface-variant mt-1">Weekly Improvement</p>
            <p className="text-[8px] text-on-surface-variant/60 mt-1">Avg risk this week vs prior 7 days</p>
          </div>
          <div className="bg-surface-container-low rounded-lg p-md border border-outline-variant/50 text-center">
            <Activity className="w-5 h-5 mx-auto text-primary mb-xs" />
            <p className="text-title-lg font-bold text-on-surface">
              {data.manager.averageCompliance === null || data.manager.averageCompliance === undefined ? '—' : `${data.manager.averageCompliance.toFixed(0)}%`}
            </p>
            <p className="text-[9px] font-bold uppercase tracking-widest text-on-surface-variant mt-1">Average Compliance</p>
            <p className="text-[8px] text-on-surface-variant/60 mt-1">100 − avg risk across sessions</p>
          </div>
          <div className="bg-surface-container-low rounded-lg p-md border border-outline-variant/50 text-center">
            <Users className="w-5 h-5 mx-auto text-primary mb-xs" />
            <p className="text-title-lg font-bold text-on-surface">
              {data.manager.healthScore === null || data.manager.healthScore === undefined ? '—' : data.manager.healthScore.toFixed(0)}
              <span className="text-[10px] font-normal text-on-surface-variant">/100</span>
            </p>
            <p className="text-[9px] font-bold uppercase tracking-widest text-on-surface-variant mt-1">Health Score</p>
            <p className="text-[8px] text-on-surface-variant/60 mt-1">Recency-weighted risk composite</p>
          </div>
        </div>
      </div>

      {/* ── Stations Needing Attention — ranked by risk ── */}
      {data.workers.length > 0 && (
        <div className="bg-surface-container border border-outline-variant rounded-xl p-lg">
          <SectionHeader title="Stations Needing Attention" />
          <p className="text-[10px] text-on-surface-variant/60 mb-md">Ranked by risk — highest first. Click to see worker details.</p>
          <div className="space-y-sm">
            {[...data.workers]
              .sort((a, b) => b.risk - a.risk)
              .slice(0, 5)
              .map((w, i) => (
                <button
                  key={w.id}
                  onClick={() => setSelected(selected?.id === w.id ? null : w)}
                  className={`w-full flex items-center gap-md p-md rounded-lg border transition-all ${
                    w.status === 'high' ? 'border-red-500/30 bg-red-500/5 hover:bg-red-500/10' :
                    w.status === 'moderate' ? 'border-orange-500/30 bg-orange-500/5 hover:bg-orange-500/10' :
                    'border-outline-variant/50 bg-surface-container-low hover:bg-surface-container-higher'
                  }`}
                >
                  <span className="font-label-mono text-[10px] text-on-surface-variant w-4">#{i + 1}</span>
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold ${
                    w.status === 'high' ? 'bg-red-500' : w.status === 'moderate' ? 'bg-orange-500' : 'bg-green-500'
                  }`}>
                    {workerInitials(w.name)}
                  </div>
                  <div className="flex-1 text-left min-w-0">
                    <p className="text-body-sm font-medium text-on-surface truncate">{w.name}</p>
                    <p className="text-[10px] text-on-surface-variant">{w.task}</p>
                  </div>
                  <div className="text-right">
                    <p className={`font-label-mono text-title-sm font-bold ${
                      w.status === 'high' ? 'text-red-400' : w.status === 'moderate' ? 'text-orange-400' : 'text-green-400'
                    }`}>{w.risk.toFixed(1)}</p>
                    <p className="text-[9px] text-on-surface-variant uppercase tracking-widest">{w.status}</p>
                  </div>
                </button>
              ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-lg">
        <div className="lg:col-span-2 bg-surface-container border border-outline-variant rounded-xl p-lg">
          <SectionHeader title="Factory Floor" />
          {data.workers.length === 0 ? (
            <EmptyState title="No workers registered" message="Add workers in the Workers page to see them here." />
          ) : (
            <div className="relative h-[450px] bg-surface-container-lowest rounded-lg border border-outline-variant overflow-hidden">
              <div className="absolute inset-0 opacity-[0.03]" style={{ backgroundImage: 'repeating-linear-gradient(90deg, transparent, transparent 40px, rgba(255,255,255,0.05) 40px, rgba(255,255,255,0.05) 41px), repeating-linear-gradient(0deg, transparent, transparent 40px, rgba(255,255,255,0.05) 40px, rgba(255,255,255,0.05) 41px)' }} />
              <div className="absolute top-4 left-4 font-label-mono text-[10px] text-on-surface-variant uppercase tracking-widest">Zone A — Assembly</div>
              <div className="absolute top-4 right-4 font-label-mono text-[10px] text-on-surface-variant uppercase tracking-widest">Zone B — Logistics</div>
              <div className="absolute bottom-4 left-4 font-label-mono text-[10px] text-on-surface-variant uppercase tracking-widest">Zone C — Fabrication</div>
              {data.workers.map((w, i) => (
                <button
                  key={w.id}
                  onClick={() => setSelected(selected?.id === w.id ? null : w)}
                  className={`absolute flex flex-col items-center gap-1 transition-all hover:scale-110 ${pulseMap[w.status]}`}
                  style={{ left: gridPositions[i % gridPositions.length]?.x, top: gridPositions[i % gridPositions.length]?.y }}
                >
                  <div className={`w-12 h-12 rounded-full ${colorMap[w.status]} ${w.status === 'high' ? 'ring-4 ring-red-400 ring-offset-3 ring-offset-surface-container-lowest animate-pulse shadow-2xl' : w.status === 'moderate' ? 'ring-2 ring-orange-400 ring-offset-2 ring-offset-surface-container-lowest shadow-lg' : 'shadow-md'} flex items-center justify-center text-white font-bold text-sm`}>
                    {workerInitials(w.name)}
                  </div>
                  <span className="font-label-mono text-[8px] text-on-surface-variant uppercase">{w.id}</span>
                  {selected?.id === w.id && (
                    <div className="absolute top-14 left-1/2 -translate-x-1/2 bg-surface-container border border-outline-variant rounded-lg p-md w-48 z-20 shadow-xl text-left">
                      <p className="text-body-sm font-bold text-on-surface">{w.name}</p>
                      <p className="text-[10px] text-on-surface-variant mt-0.5">{w.task}</p>
                      <div className="flex justify-between mt-sm text-[10px]">
                        <span className="text-on-surface-variant">Risk</span>
                        <span className={`font-bold ${w.status === 'high' ? 'text-red-400' : w.status === 'moderate' ? 'text-orange-400' : 'text-green-400'}`}>{w.risk}</span>
                      </div>
                      <div className="flex justify-between text-[10px]">
                        <span className="text-on-surface-variant">Status</span>
                        <span className="font-bold text-primary uppercase tracking-widest">{w.status}</span>
                      </div>
                    </div>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="space-y-lg">
          <div className="bg-surface-container border border-outline-variant rounded-xl p-lg">
            <SectionHeader title="Today's Alerts" />
            <div className="flex items-center gap-md p-md bg-surface-container-low rounded-lg">
              <AlertTriangle className="w-5 h-5 text-orange-400 shrink-0" />
              <div>
                <p className="text-body-sm font-medium text-on-surface">{data.manager.todayAlerts} alerts today</p>
                <p className="text-[10px] text-on-surface-variant mt-0.5">Most common: {data.manager.mostCommonIssue || 'N/A'}</p>
              </div>
            </div>
          </div>

          <div className="bg-surface-container border border-outline-variant rounded-xl p-lg">
            <SectionHeader title="Department Heatmap" />
            <div className="space-y-sm mt-md">
              {data.manager.departmentHeatmap.length === 0 ? (
                <p className="text-[10px] text-on-surface-variant/60 italic">No department data — add workers with departments.</p>
              ) : (
                data.manager.departmentHeatmap.map((d) => {
                  const barColor =
                    d.level === 'high' ? 'bg-red-500' : d.level === 'moderate' ? 'bg-orange-500' : 'bg-green-500';
                  const textColor =
                    d.level === 'high' ? 'text-red-400' : d.level === 'moderate' ? 'text-orange-400' : 'text-green-400';
                  return (
                    <div key={d.department}>
                      <div className="flex items-center justify-between text-body-sm mb-1">
                        <div className="flex items-center gap-2">
                          <div className={`w-2 h-2 rounded-full ${barColor}`} />
                          <span className="text-on-surface-variant">{d.department}</span>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className={`font-label-mono text-[11px] ${textColor}`}>{d.averageRisk}</span>
                          <span className="text-[9px] text-on-surface-variant/50">{d.workerCount} workers</span>
                        </div>
                      </div>
                      <div className="h-1.5 bg-surface-container-highest rounded-full overflow-hidden">
                        <div className={`h-full ${barColor} rounded-full`} style={{ width: `${Math.min(d.averageRisk, 100)}%` }} />
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          <div className="bg-surface-container border border-outline-variant rounded-xl p-lg">
            <SectionHeader title="Risk Distribution" />
            <div className="space-y-sm mt-md">
              {[
                { label: 'Low Risk', count: data.workers.filter((w) => w.status === 'low').length, color: 'bg-green-500' },
                { label: 'Moderate', count: data.workers.filter((w) => w.status === 'moderate').length, color: 'bg-orange-500' },
                { label: 'High Risk', count: data.workers.filter((w) => w.status === 'high').length, color: 'bg-red-500' },
              ].map((d) => (
                <div key={d.label}>
                  <div className="flex justify-between text-body-sm mb-xs"><span className="text-on-surface-variant">{d.label}</span><span className="font-label-mono text-on-surface">{d.count}</span></div>
                  <div className="h-2 bg-surface-container-highest rounded-full overflow-hidden">
                    <div className={`h-full ${d.color} rounded-full`} style={{ width: `${data.workers.length > 0 ? (d.count / data.workers.length) * 100 : 0}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
