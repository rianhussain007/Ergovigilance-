import { useState, useEffect } from 'react';
import { Users, AlertTriangle, TrendingUp, Activity } from 'lucide-react';
import { AnalyticCard } from '@/src/components/cards';
import { SectionHeader, ErrorCard, LoadingCard, EmptyState } from '@/src/components/common';
import { getManagerSummary } from '@/src/services/dashboardService';
import { useDemo } from '@/src/demo/DemoProvider';
import { DEMO_WORKERS } from '@/src/demo/demoConstants';
import type { ManagerSummary, WorkerSummary } from '@/src/types/api';

const colorMap = { low: 'bg-green-500', moderate: 'bg-orange-500', high: 'bg-red-500' };
const pulseMap = { low: '', moderate: 'animate-pulse', high: 'animate-pulse' };

const gridPositions = [
  { x: '10%', y: '15%' }, { x: '35%', y: '10%' }, { x: '60%', y: '18%' }, { x: '85%', y: '12%' },
  { x: '15%', y: '40%' }, { x: '40%', y: '45%' }, { x: '65%', y: '38%' }, { x: '88%', y: '42%' },
  { x: '25%', y: '70%' }, { x: '55%', y: '75%' },
];

const DEMO_BANNER = 'SAMPLE DATA — Demo Factory Floor, not live';

export default function ManagerDashboard() {
  const { state: demoState } = useDemo();
  const [manager, setManager] = useState<ManagerSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<WorkerSummary | null>(null);
  const isDemo = demoState.active;

  // ── fetch real data (only when demo is OFF) ───────────────────────
  useEffect(() => {
    if (isDemo) {
      setManager(null);
      setLoading(false);
      return;
    }
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
  }, [isDemo]);

  if (error) return <div className="flex items-center justify-center h-full p-lg"><ErrorCard message={error} onRetry={() => { setLoading(true); setError(null); }} /></div>;

  // ── Single source of truth — one ternary, one object ──────────────
  // Never split demo/real across two separate expressions.
  const data = (() => {
    if (isDemo) {
      return {
        manager: {
          registeredWorkers: DEMO_WORKERS.length,
          highRiskWorkers: DEMO_WORKERS.filter((w) => w.status === 'high').length,
          todayAlerts: 8,
          sessionsCompleted: 42,
          mostCommonIssue: 'Neck Flexion',
          workers: DEMO_WORKERS,
          departmentHeatmap: [
            { department: 'Assembly Line A', averageRisk: 33.5, workerCount: 2, highRiskCount: 0, level: 'moderate' },
            { department: 'Assembly Line B', averageRisk: 42.0, workerCount: 1, highRiskCount: 0, level: 'moderate' },
            { department: 'Fabrication', averageRisk: 68.0, workerCount: 1, highRiskCount: 1, level: 'high' },
            { department: 'Welding', averageRisk: 72.0, workerCount: 1, highRiskCount: 1, level: 'high' },
            { department: 'Quality Control', averageRisk: 12.0, workerCount: 1, highRiskCount: 0, level: 'low' },
            { department: 'Packaging', averageRisk: 29.0, workerCount: 2, highRiskCount: 0, level: 'moderate' },
            { department: 'Inspection', averageRisk: 15.0, workerCount: 1, highRiskCount: 0, level: 'low' },
            { department: 'Loading Dock', averageRisk: 18.0, workerCount: 1, highRiskCount: 0, level: 'low' },
          ],
        } as ManagerSummary,
        workers: DEMO_WORKERS,
      };
    }
    // Real mode — manager is null while first fetch is in flight
    return {
      manager: manager ?? {
        registeredWorkers: 0, highRiskWorkers: 0, todayAlerts: 0,
        sessionsCompleted: 0, mostCommonIssue: '', workers: [],
      } as ManagerSummary,
      workers: manager?.workers ?? [],
    };
  })();

  if (!isDemo && loading) {
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
        <p className="text-body-sm text-on-surface-variant mt-xs">{isDemo ? 'Demo — simulated factory floor' : 'Factory-wide ergonomic overview'}</p>
      </div>

      {isDemo && (
        <div className="bg-amber-500/10 border border-amber-400/30 rounded-lg px-lg py-md">
          <p className="text-[11px] font-bold text-amber-300 uppercase tracking-widest text-center">{DEMO_BANNER}</p>
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
          <div className="bg-surface-container-low rounded-lg p-md border border-outline-variant/50 text-center opacity-60">
            <TrendingUp className="w-5 h-5 mx-auto text-on-surface-variant mb-xs" />
            <p className="text-title-lg font-bold text-on-surface">—</p>
            <p className="text-[9px] font-bold uppercase tracking-widest text-on-surface-variant mt-1">Weekly Improvement</p>
            <p className="text-[8px] text-on-surface-variant/60 mt-1">Coming soon</p>
          </div>
          <div className="bg-surface-container-low rounded-lg p-md border border-outline-variant/50 text-center opacity-60">
            <Activity className="w-5 h-5 mx-auto text-on-surface-variant mb-xs" />
            <p className="text-title-lg font-bold text-on-surface">—</p>
            <p className="text-[9px] font-bold uppercase tracking-widest text-on-surface-variant mt-1">Average Compliance</p>
            <p className="text-[8px] text-on-surface-variant/60 mt-1">Coming soon</p>
          </div>
          <div className="bg-surface-container-low rounded-lg p-md border border-outline-variant/50 text-center opacity-60">
            <Users className="w-5 h-5 mx-auto text-on-surface-variant mb-xs" />
            <p className="text-title-lg font-bold text-on-surface">—</p>
            <p className="text-[9px] font-bold uppercase tracking-widest text-on-surface-variant mt-1">Health Score</p>
            <p className="text-[8px] text-on-surface-variant/60 mt-1">Coming soon</p>
          </div>
        </div>
      </div>

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
                    {w.name.split(' ').map(n => n[0]).join('')}
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
