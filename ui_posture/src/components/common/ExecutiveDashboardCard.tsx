import { useState } from 'react';
interface WeeklyTrend { week: string; averageRisk: number; sessions: number; alerts?: number }
interface DepartmentData { name: string; risk: number; fatigue: number; compliance: number }
interface TopIssue { name: string; count: number; severity: string }

export interface ExecutiveDashboardData {
  safetyScore: number;
  workersMonitored: number;
  highRiskWorkers: number;
  mediumRiskWorkers: number;
  lowRiskWorkers: number;
  activeCameras: number;
  currentSessions: number;
  weeklyTrends: WeeklyTrend[];
  departments: DepartmentData[];
  topIssues: TopIssue[];
  executiveSummary: string;
  recommendedActions: string[];
  overallSafety: number;
  compliance: number;
  productivity: number;
  cameraAvailability: number;
  systemHealth: number;
  avgRisk: number;
  avgFatigue: number;
}

interface ExecutiveDashboardCardProps {
  data: ExecutiveDashboardData;
}

function SafetyGauge({ score }: { score: number }) {
  const r = 48;
  const circ = 2 * Math.PI * r;
  const offset = circ * (1 - score / 100);
  const color = score >= 80 ? 'var(--color-chart-green)' : score >= 65 ? 'var(--color-chart-orange)' : 'var(--color-chart-red)';
  return (
    <div className="relative inline-flex items-center justify-center">
      <svg width="120" height="120" viewBox="0 0 120 120">
        <circle cx="60" cy="60" r={r} fill="none" stroke="var(--color-outline-variant)" strokeWidth="8" />
        <circle cx="60" cy="60" r={r} fill="none" stroke={color} strokeWidth="8"
          strokeDasharray={circ} strokeDashoffset={offset}
          strokeLinecap="round" transform="rotate(-90 60 60)" style={{ transition: 'stroke-dashoffset 0.6s ease, stroke 0.3s ease' }} />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-bold tracking-tight" style={{ color }}>{score}</span>
        <span className="text-[9px] text-on-surface-variant -mt-0.5">Safety</span>
      </div>
    </div>
  );
}

function MiniSparkline({ values, color = 'stroke-primary' }: { values: number[]; color?: string }) {
  const w = 80; const h = 28; const pts = values.map((v, i) => `${(i / (values.length - 1)) * w},${h - (v / 100) * h}`).join(' ');
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} className="shrink-0">
      <polyline fill="none" className={color.replace('stroke-', 'stroke-')} strokeWidth="1.5" vectorEffect="non-scaling-stroke" points={pts} />
    </svg>
  );
}

function MiniBar({ label, value, color = 'bg-primary' }: { label: string; value: number; color?: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] text-on-surface-variant w-20 shrink-0">{label}</span>
      <div className="flex-1 h-2 bg-surface-container-higher rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${Math.min(value, 100)}%` }} />
      </div>
      <span className="text-[10px] font-medium text-on-surface w-6 text-right">{value}%</span>
    </div>
  );
}

function IssueRow({ name, count, severity }: { name: string; count: number; severity: string }) {
  const dotColor = severity === 'high' ? 'bg-red-400' : severity === 'moderate' ? 'bg-orange-400' : 'bg-blue-400';
  return (
    <div className="flex items-center gap-2 py-0.5">
      <span className={`w-1.5 h-1.5 rounded-full ${dotColor} shrink-0`} />
      <span className="text-[11px] text-on-surface flex-1">{name}</span>
      <span className="text-[10px] text-on-surface-variant font-medium">{count}</span>
    </div>
  );
}

export default function ExecutiveDashboardCard({ data }: ExecutiveDashboardCardProps) {
  const [showModal, setShowModal] = useState(false);

  return (
    <>
      <div className="bg-surface-container border border-outline-variant rounded-xl overflow-hidden relative">
        {/* Enterprise Intelligence Badge */}
        <div className="absolute top-0 right-0">
          <div className="bg-primary/15 text-primary text-[8px] font-bold uppercase tracking-[0.15em] px-3 py-1 rounded-bl-lg border-l border-b border-primary/20">
            Enterprise Intelligence &bull; Prototype
          </div>
        </div>

        <div className="px-md py-sm border-b border-outline-variant/50 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-bold uppercase tracking-widest text-on-surface-variant">Executive Safety Dashboard</span>
          </div>
          <button onClick={() => setShowModal(true)} className="text-[10px] text-primary hover:text-primary-hover underline underline-offset-2 transition-colors">
            View Architecture
          </button>
        </div>

        <div className="p-md space-y-md">

          {/* Section 1 — Safety Score + KPI badges */}
          <div className="flex items-start gap-md">
            <SafetyGauge score={data.safetyScore} />
            <div className="flex-1 grid grid-cols-2 gap-x-3 gap-y-1.5">
              <div><span className="text-[9px] text-on-surface-variant block">Compliance</span><span className="text-label-mono text-[14px] font-bold text-on-surface">{data.compliance}%</span></div>
              <div><span className="text-[9px] text-on-surface-variant block">Productivity</span><span className="text-label-mono text-[14px] font-bold text-on-surface">{data.productivity}%</span></div>
              <div><span className="text-[9px] text-on-surface-variant block">Camera Availability</span><span className="text-label-mono text-[14px] font-bold text-on-surface">{data.cameraAvailability}%</span></div>
              <div><span className="text-[9px] text-on-surface-variant block">System Health</span><span className="text-label-mono text-[14px] font-bold text-on-surface">{data.systemHealth}%</span></div>
              <div><span className="text-[9px] text-on-surface-variant block">Avg Risk</span><span className="text-label-mono text-[14px] font-bold text-on-surface">{data.avgRisk}</span></div>
              <div><span className="text-[9px] text-on-surface-variant block">Avg Fatigue</span><span className="text-label-mono text-[14px] font-bold text-on-surface">{data.avgFatigue}</span></div>
            </div>
          </div>

          {/* Section 2 — Factory Overview */}
          <div>
            <p className="text-[9px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">Factory Overview</p>
            <div className="bg-surface-container-higher rounded-lg p-sm grid grid-cols-3 gap-y-2 gap-x-3">
              <div><span className="text-[9px] text-on-surface-variant block">Workers</span><span className="text-label-mono text-[13px] font-bold text-on-surface">{data.workersMonitored}</span></div>
              <div><span className="text-[9px] text-red-400 block">High Risk</span><span className="text-label-mono text-[13px] font-bold text-red-400">{data.highRiskWorkers}</span></div>
              <div><span className="text-[9px] text-orange-400 block">Medium Risk</span><span className="text-label-mono text-[13px] font-bold text-orange-400">{data.mediumRiskWorkers}</span></div>
              <div><span className="text-[9px] text-green-400 block">Low Risk</span><span className="text-label-mono text-[13px] font-bold text-green-400">{data.lowRiskWorkers}</span></div>
              <div><span className="text-[9px] text-on-surface-variant block">Cameras</span><span className="text-label-mono text-[13px] font-bold text-on-surface">{data.activeCameras}</span></div>
              <div><span className="text-[9px] text-on-surface-variant block">Sessions</span><span className="text-label-mono text-[13px] font-bold text-on-surface">{data.currentSessions}</span></div>
            </div>
          </div>

          {/* Section 3 — Weekly Trends */}
          <div>
            <p className="text-[9px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">Weekly Trends</p>
            <div className="bg-surface-container-higher rounded-lg p-sm space-y-1">
              <MiniBar label="Risk" value={100 - data.avgRisk} color="bg-green-400" />
              <MiniBar label="Compliance" value={data.compliance} color="bg-primary" />
              <div className="flex items-center gap-2 pt-1">
                <span className="text-[10px] text-on-surface-variant w-20 shrink-0">Alerts</span>
                <div className="flex items-center gap-1">
                  {data.weeklyTrends.slice(-4).map((w, i) => (
                    <div key={i} className="flex flex-col items-center">
                      <div className="w-4 h-4 rounded-sm bg-surface-container flex items-center justify-center">
                        <span className="text-[7px] text-on-surface-variant">{w.alerts}</span>
                      </div>
                      <span className="text-[6px] text-on-surface-variant mt-0.5">{w.week}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Section 4 — Department Comparison */}
          <div>
            <p className="text-[9px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">Department Comparison</p>
            <div className="bg-surface-container-higher rounded-lg p-sm overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="text-[8px] text-on-surface-variant uppercase tracking-wider">
                    <th className="pb-1 pr-2">Dept</th>
                    <th className="pb-1 pr-2">Risk</th>
                    <th className="pb-1 pr-2">Fatigue</th>
                    <th className="pb-1">Comply</th>
                  </tr>
                </thead>
                <tbody>
                  {data.departments.map((d) => {
                    const rCol = d.risk > 50 ? 'text-red-400' : d.risk > 35 ? 'text-orange-400' : 'text-green-400';
                    const fCol = d.fatigue > 40 ? 'text-red-400' : d.fatigue > 30 ? 'text-orange-400' : 'text-green-400';
                    const cCol = d.compliance >= 85 ? 'text-green-400' : d.compliance >= 70 ? 'text-orange-400' : 'text-red-400';
                    return (
                      <tr key={d.name} className="text-[10px]">
                        <td className="py-0.5 pr-2 text-on-surface font-medium">{d.name}</td>
                        <td className={`py-0.5 pr-2 ${rCol}`}>{d.risk}</td>
                        <td className={`py-0.5 pr-2 ${fCol}`}>{d.fatigue}</td>
                        <td className={`py-0.5 ${cCol}`}>{d.compliance}%</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Section 5 — Top Safety Issues */}
          <div>
            <p className="text-[9px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">Top Safety Issues</p>
            <div className="bg-surface-container-higher rounded-lg p-sm">
              {data.topIssues.map((issue) => (
                <IssueRow key={issue.name} {...issue} />
              ))}
            </div>
          </div>

          {/* Section 6 — AI Executive Summary */}
          <div>
            <p className="text-[9px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">AI Executive Summary</p>
            <div className="bg-surface-container-higher rounded-lg p-sm">
              <p className="text-[11px] text-on-surface leading-relaxed">{data.executiveSummary}</p>
            </div>
          </div>

          {/* Section 7 — Recommended Actions */}
          <div>
            <p className="text-[9px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">Recommended Actions</p>
            <div className="bg-surface-container-higher rounded-lg p-sm space-y-1">
              {data.recommendedActions.map((action, i) => (
                <div key={i} className="flex items-start gap-2">
                  <span className="text-primary text-[10px] mt-0.5 shrink-0">{'\u25B6'}</span>
                  <span className="text-[11px] text-on-surface">{action}</span>
                </div>
              ))}
            </div>
          </div>

        </div>
      </div>

      {/* Architecture Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setShowModal(false)}>
          <div className="bg-surface-container w-full max-w-[32rem] mx-lg rounded-xl border border-outline-variant shadow-2xl p-lg max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>

            <div className="flex items-center justify-between mb-md">
              <h2 className="text-body-sm font-bold text-on-surface">Project Architecture</h2>
              <button onClick={() => setShowModal(false)} className="text-on-surface-variant hover:text-on-surface text-sm">\u2716</button>
            </div>

            <div className="space-y-2 mb-md">
              {[
                ['Camera', 'Camera Stream'],
                ['\u2193', ''],
                ['Pose', 'Pose Estimation (MediaPipe)'],
                ['\u2193', ''],
                ['Features', 'Feature Extraction'],
                ['\u2193', ''],
                ['Task Recognition', 'Task Classification'],
                ['\u2193', ''],
                ['Context Risk', 'Context-Aware Risk Assessment'],
                ['\u2193', ''],
                ['Alert Engine', 'Intelligent Alert Management'],
                ['\u2193', ''],
                ['Performance Monitor', 'System Performance Dashboard'],
                ['\u2193', ''],
                ['Executive Dashboard', 'Enterprise Safety Dashboard'],
                ['\u2193', ''],
                ['Reports', 'Reporting & Analytics'],
                ['\u2193', ''],
                ['Management', 'Management Decisions'],
              ].map(([label, desc], i) => (
                <div key={i} className={`flex items-center ${desc ? 'bg-surface-container-higher rounded-lg px-3 py-2' : 'justify-center py-0.5'}`}>
                  {desc ? (
                    <>
                      <span className="text-[10px] font-bold text-primary w-28 shrink-0">{label}</span>
                      <span className="text-[10px] text-on-surface-variant">{desc}</span>
                    </>
                  ) : (
                    <span className="text-[14px] text-on-surface-variant/40">{label}</span>
                  )}
                </div>
              ))}
            </div>

            <div className="border-t border-outline-variant/50 pt-md">
              <h3 className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-2">Week 4 Progress</h3>
              <div className="space-y-1">
                {[
                  ['Task Recognition', true],
                  ['Context-Aware Risk', true],
                  ['Alert Management', true],
                  ['Performance Dashboard', true],
                  ['Executive Dashboard', true],
                ].map(([name, done]) => (
                  <div key={name as string} className="flex items-center gap-2">
                    <span className={`text-[10px] ${done ? 'text-green-400' : 'text-on-surface-variant'}`}>{done ? '\u2713' : '\u25CB'}</span>
                    <span className="text-[11px] text-on-surface">{name as string}</span>
                  </div>
                ))}
              </div>
            </div>

          </div>
        </div>
      )}
    </>
  );
}
