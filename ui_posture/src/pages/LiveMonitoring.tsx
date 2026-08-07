import { useState, useEffect, useMemo, useCallback } from 'react';
import { FeatureCard, AnalyticCard } from '@/src/components/cards';
import { RiskHistoryChart, CameraPanel } from '@/src/components/charts';
import { SectionHeader, StatusBadge, LoadingCard, ErrorCard, EmptyState, WorkerProfile, AIInsights, DigitalTwin, HealthScore, ShiftSummary, ExportsCenter, LiveAlerts, ContextAwareRiskCard, AlertManagementCard, SystemPerformanceCard, RecommendationsCard } from '@/src/components/common';
import { TimelineBar, FeatureGraph, TelemetryPanel } from '@/src/components/timeline';
import { useDashboardWithDemo } from '@/src/hooks/useDashboardWithDemo';
import { useHistory } from '@/src/hooks/useHistory';
import { useLiveTimeline } from '@/src/hooks/useLiveTimeline';
import { useContextSnapshot } from '@/src/hooks/useContextSnapshot';
import { useRecommendations } from '@/src/hooks/useRecommendations';
import { useToast } from '@/src/hooks/useToast';
import { useDemo } from '@/src/demo/DemoProvider';
import { CameraPlayback } from '@/src/components/demo';
import { AlertTriangle, Camera, Clock3, FileDown, FileText, Radio, ShieldAlert } from 'lucide-react';
import type { StatusType, Issue, ErgonomicFeature, LiveStatus, Recommendations, SessionInfo } from '@/src/types/api';

export default function LiveMonitoring() {
  const { dashboard, sessions, loading, error, refetch } = useDashboardWithDemo();
  const { state } = useDemo();
  const history = useHistory();
  const { timeline: liveTimeline } = useLiveTimeline();
  const { snapshot: contextSnapshot } = useContextSnapshot();
  const { data: recData } = useRecommendations();
  const { addToast } = useToast();
  const [showExports, setShowExports] = useState(false);
  const [showAlerts, setShowAlerts] = useState(false);
  const [selectedFeature, setSelectedFeature] = useState('neck_flexion');
  const [selectedTime, setSelectedTime] = useState(0);

  const latestEntry = liveTimeline.length > 0 ? liveTimeline[liveTimeline.length - 1] : null;

  const liveAlerts = useMemo(() => {
    const result: { frame_number: number; severity: string; title: string }[] = [];
    for (const entry of liveTimeline) {
      for (const alert of entry.alerts) {
        if (alert.severity === 'HIGH' || alert.severity === 'CRITICAL' || alert.severity === 'WARNING') {
          result.push({ frame_number: entry.frame_number, severity: alert.severity, title: alert.title });
        }
      }
    }
    return result;
  }, [liveTimeline]);

  const seekTo = useCallback((t: number) => {
    setSelectedTime(t);
  }, []);

  useEffect(() => {
    if (liveTimeline.length > 0) {
      setSelectedTime(liveTimeline[liveTimeline.length - 1].timestamp);
    }
  }, [liveTimeline.length > 0 ? liveTimeline[liveTimeline.length - 1].timestamp : 0]);

  if (error) return <div className="flex items-center justify-center h-full p-lg"><ErrorCard message={error} onRetry={refetch} /></div>;

  if (loading || !dashboard) {
    return (
      <div className="p-lg space-y-lg pb-32">
        {/* Title skeleton */}
        <div className="h-8 w-1/3 bg-surface-container-highest rounded-lg animate-pulse" />
        <div className="h-4 w-1/2 bg-surface-container-high rounded animate-pulse mt-sm" />
        {/* Live status section skeleton */}
        <div className="rounded-lg border border-outline-variant/20 bg-[#080d13] p-md">
          <div className="flex items-center gap-sm mb-md">
            <div className="h-4 w-4 bg-surface-container-highest rounded animate-pulse" />
            <div className="h-4 w-48 bg-surface-container-highest rounded animate-pulse" />
          </div>
          <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_320px] gap-md">
            <div className="aspect-video bg-surface-container-highest rounded-lg animate-pulse" />
            <div className="space-y-md">
              <div className="h-24 bg-surface-container-highest rounded-lg animate-pulse" />
              <div className="h-24 bg-surface-container-highest rounded-lg animate-pulse" />
              <div className="h-24 bg-surface-container-highest rounded-lg animate-pulse" />
            </div>
          </div>
          <div className="h-8 bg-surface-container-highest rounded-lg mt-md animate-pulse" />
        </div>
        {/* Cards row skeleton */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-lg">
          <LoadingCard height="h-48" />
          <LoadingCard height="h-48" />
          <LoadingCard height="h-48" />
        </div>
        {/* Charts row skeleton */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-lg">
          <div className="lg:col-span-2"><LoadingCard height="h-64" /></div>
          <LoadingCard height="h-64" />
        </div>
      </div>
    );
  }

  const { liveStatus, ergonomicFeatures, issues, recommendations, sessionAnalytics, riskHistory, trendAnalysis, session, unavailableFeatures = [] } = dashboard;
  const approximateFeatures = contextSnapshot?.approximate_features ?? [];

  return (
    <div className="p-lg space-y-lg pb-32">
      <section className="rounded-lg border border-cyan-400/15 bg-[#080d13] p-md shadow-[0_24px_80px_rgba(0,0,0,0.35)]">
        <div className="mb-md flex flex-wrap items-center justify-between gap-md">
          <div className="flex items-center gap-sm min-w-0">
            <Radio className="h-4 w-4 text-red-400" />
            <span className="font-label-caps text-label-caps tracking-widest text-red-300 uppercase">Live Status: {session.cameraStatus === 'active' ? 'Active' : session.cameraStatus}</span>
            <span className="font-label-mono text-[10px] text-on-surface-variant truncate">{session.id}</span>
          </div>
          <div className="flex items-center gap-xs text-[10px] font-label-mono text-on-surface-variant">
            <Clock3 className="h-3.5 w-3.5" />
            <span>{sessionAnalytics.sessionDuration}</span>
          </div>
        </div>
        <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_320px] gap-md">
          {state.active ? (
            <CameraPlayback workerName={session.workerName} />
          ) : (
            <CameraPanel status={session.cameraStatus} workerName={session.workerName} task={liveStatus.currentTask} />
          )}
          <TelemetrySidebar
            session={session}
            liveStatus={liveStatus}
            features={ergonomicFeatures}
            issues={issues}
            recommendations={recommendations}
            unavailableFeatures={unavailableFeatures}
            approximateFeatures={approximateFeatures}
            onPlaceholder={(label) => addToast('info', `${label} coming soon`, 'This control is a visual placeholder until backend support is connected.')}
          />
        </div>
        {liveTimeline.length > 0 && (
          <TimelineBar timeline={liveTimeline} seekTime={selectedTime} seekTo={seekTo} alerts={liveAlerts} />
        )}
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-lg">
        <div className="space-y-lg">
          <WorkerProfile session={session} liveStatus={liveStatus} />
        </div>
        <div className="space-y-lg">
          <HealthScore liveStatus={liveStatus} trend={trendAnalysis.improving > 50 ? 'improving' : trendAnalysis.improving < 50 ? 'deteriorating' : 'stable'} />
        </div>
        <div className="space-y-lg">
          <ContextAwareRiskCard />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-lg">
        <div className="lg:col-span-2 space-y-lg">
          <section>
            <SectionHeader title="Ergonomic Features" />
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-md">
              {ergonomicFeatures.map((f) => <FeatureCard feature={f} key={f.id} isApproximate={approximateFeatures.includes(f.id)} />)}
            </div>
          </section>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-lg">
            <div>
              <SectionHeader title="Issues Detected" />
              <div className="space-y-sm mt-sm">
                {issues.length === 0 ? <EmptyState title="No issues" message="All clear." /> : issues.map((issue) => (
                  <div key={issue.id} className="flex items-start gap-md p-sm bg-surface-container rounded-lg border border-outline-variant/50">
                    <AlertTriangle className={`w-4 h-4 shrink-0 mt-0.5 ${issue.severity === 'high' ? 'text-red-400' : issue.severity === 'moderate' ? 'text-orange-400' : 'text-blue-400'}`} />
                    <div>
                      <p className="text-body-sm text-on-surface font-medium">{issue.name}</p>
                      <p className="text-[10px] text-on-surface-variant mt-0.5">{issue.detail}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <RecommendationsCard />
          </div>

          <section>
            <SectionHeader title="Session Analytics" />
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-7 gap-md mt-sm">
              <AnalyticCard label="Session Duration" value={sessionAnalytics.sessionDuration} />
              <AnalyticCard label="Frames Analysed" value={sessionAnalytics.framesAnalyzed.toLocaleString()} />
              <AnalyticCard label="Highest Risk" value={sessionAnalytics.highestRisk} accent />
              <AnalyticCard label="Most Frequent Issue" value={sessionAnalytics.mostFrequentIssue} />
              <AnalyticCard label="Avg Neck" value={`${sessionAnalytics.averageNeck}°`} />
              <AnalyticCard label="Avg Trunk" value={`${sessionAnalytics.averageTrunk}°`} />
              <AnalyticCard label="Avg Knee" value={`${sessionAnalytics.averageKnee}°`} />
            </div>
          </section>

          {history.data.points.length === 0 ? <EmptyState title="No risk history" /> : <RiskHistoryChart data={history.data.points} />}
        </div>

        <div className="space-y-lg">
          <AlertManagementCard />
          <SystemPerformanceCard data={state.active ? state.systemPerformance : {
            systemHealth: 'healthy', cpuUsage: 22, memoryUsage: 38, fps: 30, cameraStatus: 'active',
            cameraLatency: 8, detectionLatency: 6, processedFrames: 0, droppedFrames: 0,
            avgProcessingTime: 3.5, peakMemory: 42, uptime: 0, gpuUtilization: 12,
            aiModelConfidence: 94, inferenceTime: 5.2, lastModelUpdate: '2026-06-28',
            timeline: [],
          }} />
          <ShiftSummary analytics={sessionAnalytics} trend={trendAnalysis} />
          <DigitalTwin features={ergonomicFeatures} />
          <AIInsights snapshot={contextSnapshot} recData={recData} />
          {liveTimeline.length > 0 && (
            <>
              {latestEntry && <TelemetryPanel entry={latestEntry} />}
              <FeatureGraph
                timeline={liveTimeline}
                selectedFeature={selectedFeature}
                onSelectFeature={setSelectedFeature}
                seekTo={seekTo}
                currentTime={selectedTime}
              />
            </>
          )}
        </div>
      </div>

      <div className="flex items-center gap-md">
        <button onClick={() => setShowExports(true)} className="flex items-center gap-sm px-lg py-sm bg-primary text-on-primary rounded-lg text-body-sm font-medium hover:bg-primary-hover transition-colors">
          <FileDown className="w-4 h-4" />
          Export Data
        </button>
        <button onClick={() => setShowAlerts(!showAlerts)} className="flex items-center gap-sm px-lg py-sm bg-surface-container border border-outline-variant text-on-surface rounded-lg text-body-sm font-medium hover:bg-surface-container-higher transition-colors">
          <AlertTriangle className="w-4 h-4" />
          Live Alerts
          {issues.filter((i) => i.severity === 'high').length > 0 && (
            <span className="text-[9px] bg-red-500/15 text-red-400 px-1.5 py-0.5 rounded-full font-bold">{issues.filter((i) => i.severity === 'high').length}</span>
          )}
        </button>
      </div>

      <section>
        <SectionHeader title="Recent Sessions" />
        {sessions.length === 0 ? <EmptyState title="No sessions" /> : (
          <div className="bg-surface-container border border-outline-variant rounded-xl overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-outline-variant">
                    <th className="font-label-caps text-[10px] text-on-surface-variant uppercase tracking-widest px-lg py-md">Session ID</th>
                    <th className="font-label-caps text-[10px] text-on-surface-variant uppercase tracking-widest px-lg py-md">Date</th>
                    <th className="font-label-caps text-[10px] text-on-surface-variant uppercase tracking-widest px-lg py-md">Duration</th>
                    <th className="font-label-caps text-[10px] text-on-surface-variant uppercase tracking-widest px-lg py-md">Highest Risk</th>
                    <th className="font-label-caps text-[10px] text-on-surface-variant uppercase tracking-widest px-lg py-md">Task</th>
                    <th className="font-label-caps text-[10px] text-on-surface-variant uppercase tracking-widest px-lg py-md">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {sessions.map((s) => (
                    <tr key={s.id} className="border-b border-outline-variant/50 hover:bg-surface-container-low transition-colors">
                      <td className="px-lg py-md"><span className="font-label-mono text-label-mono text-primary">{s.id}</span></td>
                      <td className="px-lg py-md text-body-sm text-on-surface">{new Date(s.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</td>
                      <td className="px-lg py-md text-body-sm text-on-surface">{s.duration}</td>
                      <td className="px-lg py-md"><span className="text-body-sm font-medium" style={{ color: s.highestRisk === 'Neck Flexion' || s.highestRisk === 'Trunk Flexion' ? '#f97316' : '#60a5fa' }}>{s.highestRisk}</span></td>
                      <td className="px-lg py-md text-body-sm text-on-surface">{s.task}</td>
                      <td className="px-lg py-md"><StatusBadge status={s.status as StatusType} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>

      {showExports && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setShowExports(false)}>
          <div className="bg-surface-container w-full max-w-sm mx-lg rounded-xl border border-outline-variant shadow-2xl p-lg" onClick={(e) => e.stopPropagation()}>
            <ExportsCenter
              onClose={() => setShowExports(false)}
              timeline={liveTimeline}
              dashboard={dashboard}
            />
          </div>
        </div>
      )}

      {showAlerts && (
        <div className="fixed inset-0 z-50 flex justify-end" onClick={() => setShowAlerts(false)}>
          <div className="w-full max-w-sm bg-surface-container border-l border-outline-variant shadow-2xl h-full" onClick={(e) => e.stopPropagation()}>
            <LiveAlerts issues={issues as Issue[]} onClose={() => setShowAlerts(false)} />
          </div>
        </div>
      )}
    </div>
  );
}

function TelemetrySidebar({
  session,
  liveStatus,
  features,
  issues,
  recommendations,
  unavailableFeatures,
  approximateFeatures,
  onPlaceholder,
}: {
  session: SessionInfo;
  liveStatus: LiveStatus;
  features: ErgonomicFeature[];
  issues: Issue[];
  recommendations: Recommendations;
  unavailableFeatures: string[];
  approximateFeatures: string[];
  onPlaceholder: (label: string) => void;
}) {
  const primaryIssue = issues[0];
  const guidanceText = recommendations.worker || primaryIssue?.detail || 'No active guidance from the live pipeline.';

  return (
    <aside className="rounded border border-white/10 bg-black/35 p-md space-y-md">
      <RiskGauge liveStatus={liveStatus} />

      <div className="space-y-sm">
        <div className="flex items-center justify-between">
          <p className="font-label-caps text-[10px] text-on-surface-variant uppercase tracking-widest">Real-Time Joint Telemetry</p>
          <span className="font-label-mono text-[10px] text-cyan-200">{features.length} tracked</span>
        </div>
        <div className="space-y-xs">
          {features.map((feature) => (
            <div key={feature.id}>
              <TelemetryRow feature={feature} unavailableFeatures={unavailableFeatures} isApproximate={approximateFeatures.includes(feature.id)} />
            </div>
          ))}
        </div>
      </div>

      <div className="rounded border border-orange-400/20 bg-orange-500/10 p-sm">
        <div className="flex items-start gap-sm">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-orange-300" />
          <div className="min-w-0">
            <p className="text-[10px] font-label-caps tracking-widest uppercase text-orange-200">
              {primaryIssue ? primaryIssue.name : 'Guidance'}
            </p>
            <p className="mt-xs text-[11px] leading-relaxed text-on-surface-variant">{guidanceText}</p>
            {recommendations.supervisor && (
              <p className="mt-xs text-[10px] leading-relaxed text-on-surface-variant/75">Supervisor: {recommendations.supervisor}</p>
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-xs">
        <PlaceholderAction icon={ShieldAlert} label="Override" onClick={() => onPlaceholder('Manual override')} />
        <PlaceholderAction icon={Camera} label="Capture" onClick={() => onPlaceholder('Capture')} />
        <PlaceholderAction icon={FileText} label="Log" onClick={() => onPlaceholder('Log')} />
      </div>

      <div className="grid grid-cols-3 gap-sm pt-sm border-t border-white/10">
        <Metric label="Worker" value={session.workerName} />
        <Metric label="Task" value={liveStatus.currentTask || 'Unknown'} />
        <Metric label="Duration" value={liveStatus.taskDurationSeconds ? `${Math.round(liveStatus.taskDurationSeconds)}s` : '0s'} />
        <Metric label="Status" value={liveStatus.workerStatus || session.cameraStatus} />
        <Metric label="Confidence" value={`${Math.round(liveStatus.confidence)}%`} />
      </div>
    </aside>
  );
}

function RiskGauge({ liveStatus }: { liveStatus: LiveStatus }) {
  const score = Math.max(0, Math.min(100, liveStatus.riskScore || 0));
  const color = liveStatus.riskLevel === 'high' ? '#fb7185' : liveStatus.riskLevel === 'moderate' ? '#f59e0b' : '#22c55e';
  const ring = `conic-gradient(${color} ${score * 3.6}deg, rgba(148,163,184,0.16) 0deg)`;

  return (
    <div className="rounded border border-cyan-400/15 bg-white/[0.03] p-md text-center">
      <p className="font-label-caps text-[10px] text-on-surface-variant uppercase tracking-widest">Current Risk Index</p>
      <div className="mx-auto mt-sm grid h-28 w-28 place-items-center rounded-full" style={{ background: ring, boxShadow: `0 0 24px ${color}33` }}>
        <div className="grid h-20 w-20 place-items-center rounded-full bg-[#080d13] border border-white/10">
          <div>
            <p className="font-label-mono text-2xl font-bold text-on-surface">{score.toFixed(0)}</p>
            <p className="font-label-caps text-[9px] uppercase tracking-widest" style={{ color }}>{liveStatus.riskLevel}</p>
          </div>
        </div>
      </div>
      <p className="mt-sm text-[11px] italic text-on-surface-variant">Normal operation range maintained</p>
    </div>
  );
}

const UNAVAILABLE_GUIDANCE: Record<string, string> = {
  neck_flexion: 'N/A — move back so your hips are visible',
  trunk_flexion: 'N/A — move back so your hips are visible',
  alignment_deviation: 'N/A — move back so your hips are visible',
  knee_angle: 'N/A — move back so your legs are visible',
  elbow_flexion_angle: 'N/A — move your wrists into frame',
  upper_arm_angle_from_vertical: 'N/A — move your wrists into frame',
  left_shoulder_elev: 'N/A — reposition your left arm in frame',
  right_shoulder_elev: 'N/A — reposition your right arm in frame',
  shoulder_symmetry: 'N/A — reposition your shoulders in frame',
};

function TelemetryRow({ feature, unavailableFeatures = [], isApproximate }: { feature: ErgonomicFeature; unavailableFeatures?: string[]; isApproximate?: boolean }) {
  const isUnavailable = feature.status === 'unavailable' || feature.value === null || unavailableFeatures.includes(feature.id);
  const range = Math.max(feature.max - feature.min, 1);
  const percent = isUnavailable || isApproximate ? 0 : Math.max(0, Math.min(100, ((feature.value! - feature.min) / range) * 100));
  const color = isUnavailable ? 'bg-gray-500' : isApproximate ? 'bg-amber-500/70' : feature.status === 'high' ? 'bg-red-400' : feature.status === 'moderate' ? 'bg-orange-400' : feature.status === 'low' ? 'bg-blue-400' : 'bg-green-400';
  const guidance = UNAVAILABLE_GUIDANCE[feature.id] || 'N/A — adjust position so full body is in frame';

  return (
    <div className={`rounded border ${isUnavailable ? 'border-gray-800/50 bg-black/10' : isApproximate ? 'border-amber-500/20 bg-amber-500/5' : 'border-white/10 bg-black/20'} px-sm py-xs`} title={isUnavailable ? guidance : feature.name}>
      <div className="flex items-center justify-between gap-sm">
        <span className={`text-[11px] truncate ${isUnavailable ? 'text-on-surface-variant/50' : 'text-on-surface-variant'}`}>{feature.name}</span>
        <span className={`font-label-mono text-[11px] flex items-center gap-1 ${isUnavailable ? 'text-on-surface-variant/50' : 'text-on-surface'}`}>
          {isUnavailable ? 'N/A' : isApproximate ? `~${feature.value!.toFixed(1)}${feature.unit}` : `${feature.value!.toFixed(1)}${feature.unit}`}
          {isApproximate && !isUnavailable && (
            <span className="text-[8px] text-amber-400/70 italic font-normal" title="Computed via fallback method (image-vertical instead of hip-anchored)">approx</span>
          )}
        </span>
      </div>
      <div className="mt-xs h-1 overflow-hidden rounded-full bg-white/10">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <p className="font-label-caps text-[9px] uppercase tracking-widest text-on-surface-variant">{label}</p>
      <p className="mt-0.5 truncate font-label-mono text-[11px] text-on-surface">{value}</p>
    </div>
  );
}

function PlaceholderAction({ icon: Icon, label, onClick }: { icon: typeof Camera; label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="relative flex items-center justify-center gap-xs rounded border border-white/10 bg-white/[0.03] px-sm py-sm text-[10px] font-medium text-on-surface-variant hover:border-cyan-400/25 hover:text-cyan-100 transition-colors"
      title={`${label} - coming soon`}
    >
      <Icon className="h-3.5 w-3.5" />
      {label}
      <span className="absolute -top-1 -right-1 text-[8px] leading-none text-on-surface-variant/60">*</span>
    </button>
  );
}


