import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router';
import { AnalyticCard } from '@/src/components/cards';
import { RiskHistoryChart, CameraPanel } from '@/src/components/charts';
import { SectionHeader, LoadingCard, ErrorCard, ExportsCenter, LiveAlerts, ContextAwareRiskCard, RecommendationsCard, PredictiveInsightsCard } from '@/src/components/common';
import { TimelineBar } from '@/src/components/timeline';
import { useDashboard } from '@/src/hooks/useDashboard';
import { useHistory } from '@/src/hooks/useHistory';
import { useLiveTimeline } from '@/src/hooks/useLiveTimeline';
import { useContextSnapshot } from '@/src/hooks/useContextSnapshot';
import { useToast } from '@/src/hooks/useToast';
import { useSettings } from '@/src/hooks/useSettings';
import { AlertTriangle, Camera, Clock3, FileDown, FileText, Radio, ShieldAlert, Brain, ScanLine, Users } from 'lucide-react';
import type { Issue, ErgonomicFeature, LiveStatus, Recommendations, SessionInfo, ContextSnapshot } from '@/src/types/api';

export default function LiveMonitoring() {
  const { dashboard, sessions, loading, error, refetch } = useDashboard();
  const { settings } = useSettings();
  const history = useHistory();
  const { timeline: liveTimeline } = useLiveTimeline();
  const { snapshot: contextSnapshot } = useContextSnapshot();
  const { addToast } = useToast();
  const [showExports, setShowExports] = useState(false);
  const [showAlerts, setShowAlerts] = useState(false);
  const captureRef = useRef<(() => void) | null>(null);
  const [selectedTime, setSelectedTime] = useState(0);

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

  // CameraPanel registers its screenshot handler here; stable callback so the
  // registration effect in CameraPanel doesn't re-run on every parent render.
  const registerCapture = useCallback((fn: () => void) => {
    captureRef.current = fn;
  }, []);

  const handleSidebarCapture = useCallback(() => {
    if (captureRef.current) {
      captureRef.current();
    } else {
      addToast('warning', 'No camera feed', 'Start a live monitoring session to capture a frame.');
    }
  }, [addToast]);

  const handleLogObservation = useCallback(async (note: string, category: string) => {
    try {
      const { apiFetch } = await import('@/src/services/apiClient');
      const res = await apiFetch('/api/session/observation', {
        method: 'POST',
        body: JSON.stringify({ note, category }),
      });
      if (res.ok) {
        const data = await res.json();
        addToast('success', 'Observation logged', `${data.observation_id} recorded to ${data.session_id}`);
      } else {
        const err = await res.json().catch(() => ({ detail: 'Failed to log' }));
        addToast('error', 'Log failed', err.detail || 'Could not record observation.');
      }
    } catch {
      addToast('error', 'Log failed', 'Network error while recording observation.');
    }
  }, [addToast]);

  const handleRiskOverride = useCallback(async (level: string, reason: string) => {
    try {
      const { apiFetch } = await import('@/src/services/apiClient');
      const res = await apiFetch('/api/session/override', {
        method: 'POST',
        body: JSON.stringify({ risk_level: level, reason }),
      });
      if (res.ok) {
        const data = await res.json();
        addToast('info', 'Risk overridden', `${data.previous_level} → ${data.new_level}`);
      } else {
        const err = await res.json().catch(() => ({ detail: 'Failed' }));
        addToast('error', 'Override failed', err.detail || 'Could not apply override.');
      }
    } catch {
      addToast('error', 'Override failed', 'Network error while applying override.');
    }
  }, [addToast]);

  useEffect(() => {
    if (liveTimeline.length > 0) {
      setSelectedTime(liveTimeline[liveTimeline.length - 1].timestamp);
    }
  }, [liveTimeline.length > 0 ? liveTimeline[liveTimeline.length - 1].timestamp : 0]);

  if (error) return <div className="flex items-center justify-center h-full p-lg"><ErrorCard message={error} onRetry={refetch} /></div>;

  if (loading || !dashboard) {
    return (
      <div className="p-lg space-y-lg pb-xl">
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

  const { liveStatus, ergonomicFeatures, issues, sessionAnalytics, session, unavailableFeatures = [] } = dashboard;
  const approximateFeatures = contextSnapshot?.approximate_features ?? [];
  // Single source of truth: is a live session actually running right now?
  const isActive = session?.cameraStatus === 'active';
  // Post-stop prompt: when a session ends, tell the operator their report is
  // ready instead of leaving them to hunt through two navigations (QA #5).
  const [justStopped, setJustStopped] = useState(false);
  const prevActiveRef = useRef(isActive);
  useEffect(() => {
    if (prevActiveRef.current && !isActive) setJustStopped(true);
    prevActiveRef.current = isActive;
  }, [isActive]);
  const navigate = useNavigate();
  const hasTimeline = liveTimeline.length > 0;

  // Filter displayed issues by the user's alert threshold (low | moderate | high).
  const filteredIssues = issues.filter((i) => {
    const rank: Record<string, number> = { low: 0, moderate: 1, high: 2 };
    const minRank = rank[settings.alertThreshold] ?? 0;
    return (rank[i.severity] ?? 0) >= minRank;
  });

  return (
    <div className="p-lg space-y-lg pb-xl">
      {/* ── Plain-language posture status (operator layer) ── */}
      <PostureStatusBanner riskLevel={liveStatus.riskLevel} active={isActive} currentTask={liveStatus.currentTask} />

      {/* ── Post-stop: session saved — report is ready ── */}
      {justStopped && (
        <div className="rounded-xl border border-green-500/30 bg-green-500/5 px-lg py-md flex flex-wrap items-center justify-between gap-md">
          <div className="flex items-center gap-md">
            <FileText className="w-5 h-5 text-emerald-300" />
            <div>
              <p className="text-body-md font-bold text-emerald-300">Session saved — your report is ready.</p>
              <p className="text-body-sm text-on-surface-variant">Open Session History to review it, replay the video, or export the evidence package.</p>
            </div>
          </div>
          <div className="flex items-center gap-sm">
            <button
              className="rounded-lg bg-primary px-md py-sm text-body-sm font-bold text-on-primary hover:opacity-90 transition-opacity"
              onClick={() => navigate('/sessions')}
            >
              View Session Report
            </button>
            <button
              className="rounded-lg border border-outline-variant px-md py-sm text-body-sm text-on-surface-variant hover:text-on-surface transition-colors"
              onClick={() => setJustStopped(false)}
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* ── Live status: camera feed + session/task/status panel ── */}
      <section className="rounded-lg border border-cyan-400/15 bg-[#080d13] p-md shadow-[0_24px_80px_rgba(0,0,0,0.35)]">
        <div className="mb-md flex flex-wrap items-center justify-between gap-md">
          <div className="flex items-center gap-sm min-w-0">
            {isActive ? (
              <>
                <Radio className="h-4 w-4 text-red-400" />
                <span className="font-label-caps text-label-caps tracking-widest text-red-300 uppercase">Live Session</span>
                {session.id && <span className="font-label-mono text-sm text-on-surface-variant truncate">{session.id}</span>}
              </>
            ) : (
              <span className="font-label-caps text-label-caps tracking-widest text-on-surface-variant uppercase">Not monitoring</span>
            )}
          </div>
          {isActive && (
            <div className="flex items-center gap-xs text-sm font-label-mono text-on-surface-variant">
              <Clock3 className="h-3.5 w-3.5" />
              <span>{sessionAnalytics.sessionDuration}</span>
            </div>
          )}
        </div>
        <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_340px] gap-md">
          <CameraPanel
            status={session.cameraStatus}
            workerName={session.workerName}
            task={liveStatus.currentTask}
            reconnecting={session.cameraReconnecting}
            onCaptureReady={registerCapture}
          />
          <TelemetrySidebar
            session={session}
            liveStatus={liveStatus}
            contextSnapshot={contextSnapshot}
            unavailableFeatures={unavailableFeatures}
            active={isActive}
            onCapture={handleSidebarCapture}
            onLog={handleLogObservation}
            onOverride={handleRiskOverride}
          />
        </div>
        {hasTimeline && (
          <TimelineBar timeline={liveTimeline} seekTime={selectedTime} seekTo={seekTo} alerts={liveAlerts} />
        )}
      </section>

      {/* ── Ergonomic Features ── */}
      <section className="bg-surface-container border border-outline-variant rounded-xl p-lg">
        <SectionHeader title="Ergonomic Features" />
        {isActive ? (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-md mt-sm">
            {ergonomicFeatures.map((f) => <FeatureRowCompact feature={f} key={f.id} isApproximate={approximateFeatures.includes(f.id)} />)}
          </div>
        ) : (
          <IdleNote message="Start monitoring to see live joint measurements." />
        )}
      </section>

      {/* ── RULA / Assessment + Camera Framing + Context Risk ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-lg">
        <RulaScoreCard snapshot={contextSnapshot} active={isActive} />
        <CameraFramingCard snapshot={contextSnapshot} unavailableFeatures={unavailableFeatures} active={isActive} />
        <ContextAwareRiskCard />
      </div>

      {/* ── Station Risk — every person the camera sees, not just the primary ── */}
      <StationRiskCard snapshot={contextSnapshot} active={isActive} />

      {/* ── Issues + Guidance ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-lg">
        <div className="bg-surface-container border border-outline-variant rounded-xl p-lg">
          <SectionHeader title="Issues Detected" />
          <div className="space-y-sm mt-sm">
            {issues.length === 0 ? (
              <IdleNote message={isActive ? 'No posture issues detected.' : 'Start monitoring to detect posture issues.'} />
            ) : issues.map((issue) => (
              <div key={issue.id} className="flex items-start gap-md p-sm bg-surface-container-low rounded-lg border border-outline-variant/50">
                <AlertTriangle className={`w-4 h-4 shrink-0 mt-0.5 ${issue.severity === 'high' ? 'text-red-400' : issue.severity === 'moderate' ? 'text-orange-400' : 'text-blue-400'}`} />
                <div>
                  <p className="text-body-sm text-on-surface font-medium">{issue.name}</p>
                  <p className="text-sm text-on-surface-variant mt-0.5">{issue.detail}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
        <RecommendationsCard idle={!isActive} />
      </div>

      {/* ── Session Stats + Risk History ── */}
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_400px] gap-lg">
        <section className="bg-surface-container border border-outline-variant rounded-xl p-lg">
          <SectionHeader title="Session Stats" />
          {isActive ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-md mt-sm">
              <AnalyticCard label="Session Duration" value={sessionAnalytics.sessionDuration} />
              <AnalyticCard label="Frames Analysed" value={sessionAnalytics.framesAnalyzed.toLocaleString()} />
              <AnalyticCard label="Highest Risk" value={sessionAnalytics.highestRisk} accent />
              <AnalyticCard label="Most Frequent Issue" value={sessionAnalytics.mostFrequentIssue} />
              <AnalyticCard label="Avg Neck" value={`${sessionAnalytics.averageNeck}°`} />
              <AnalyticCard label="Avg Trunk" value={`${sessionAnalytics.averageTrunk}°`} />
              <AnalyticCard label="Avg Knee" value={`${sessionAnalytics.averageKnee}°`} />
            </div>
          ) : (
            <IdleNote message="Start monitoring to collect session statistics." />
          )}
        </section>
        {history.data.points.length === 0 ? (
          <IdleNote message="Start monitoring to build a risk history." />
        ) : (
          <RiskHistoryChart data={history.data.points} />
        )}
      </div>

      {/* ── Predictive forecast (advisory) ── */}
      <PredictiveInsightsCard
        mode="live"
        active={isActive}
        refreshKey={liveTimeline.length > 0 ? Math.floor(liveTimeline[liveTimeline.length - 1].timestamp / 30) : 0}
      />

      <div className="flex items-center gap-md">
        <button
          onClick={() => setShowExports(true)}
          disabled={!isActive}
          title={isActive ? 'Export this session' : 'Start monitoring to export session data'}
          className={`flex items-center gap-sm h-12 px-lg rounded-lg text-body-sm font-medium transition-colors ${isActive ? 'bg-primary text-on-primary hover:bg-primary-hover' : 'bg-surface-container-high text-on-surface-variant cursor-not-allowed'}`}
        >
          <FileDown className="w-4 h-4" />
          Export Data
        </button>
        <button onClick={() => setShowAlerts(!showAlerts)} className="flex items-center gap-sm h-12 px-lg bg-surface-container border border-outline-variant text-on-surface rounded-lg text-body-sm font-medium hover:bg-surface-container-higher transition-colors">
          <AlertTriangle className="w-4 h-4" />
          Live Alerts
          {issues.filter((i) => i.severity === 'high').length > 0 && (
            <span className="text-xs bg-red-500/15 text-red-400 px-1.5 py-0.5 rounded-full font-bold">{issues.filter((i) => i.severity === 'high').length}</span>
          )}
        </button>
        <span className="text-sm text-on-surface-variant">Alert level: {settings.alertThreshold}</span>
      </div>

      {showExports && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setShowExports(false)}>
          <div className="bg-surface-container w-full max-w-[24rem] mx-lg rounded-xl border border-outline-variant shadow-2xl p-lg" onClick={(e) => e.stopPropagation()}>
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
          <div className="w-full max-w-[24rem] bg-surface-container border-l border-outline-variant shadow-2xl h-full" onClick={(e) => e.stopPropagation()}>
            <LiveAlerts issues={filteredIssues as Issue[]} onClose={() => setShowAlerts(false)} />
          </div>
        </div>
      )}
    </div>
  );
}

function TelemetrySidebar({
  session,
  liveStatus,
  contextSnapshot,
  unavailableFeatures,
  active,
  onCapture,
  onLog,
  onOverride,
}: {
  session: SessionInfo;
  liveStatus: LiveStatus;
  contextSnapshot: ContextSnapshot | null;
  unavailableFeatures: string[];
  active: boolean;
  onCapture?: () => void;
  onLog?: (note: string, category: string) => void;
  onOverride?: (level: string, reason: string) => void;
}) {
  return (
    <aside className="rounded border border-outline-variant bg-surface-container-low p-md space-y-md">
      <RiskGauge liveStatus={liveStatus} active={active} />

      {/* ── Current Task (trained 7-class model) ── */}
      {(() => {
        const conf = liveStatus.taskConfidence ?? liveStatus.confidence ?? 0;
        const confPct = Math.round(conf * 100);
        const isUncertain = active && confPct < 50 && !!liveStatus.currentTask;
        const taskDisplay = !active
          ? 'No active session'
          : isUncertain
            ? 'Task: Uncertain'
            : (liveStatus.currentTask || 'Not yet classified');
        return (
          <div className="rounded border border-cyan-400/30 bg-cyan-500/10 p-sm">
            <p className="font-label-caps text-xs text-on-surface-variant uppercase tracking-widest">Current Task</p>
            <p className="text-title-md font-bold text-on-surface mt-0.5">
              {taskDisplay}
            </p>
            <div className="flex items-center justify-between mt-1">
              <span className="font-label-mono text-sm text-on-surface-variant">
                {active ? `Conf ${confPct}%${isUncertain ? ' — baseline thresholds applied' : ''}` : '—'}
              </span>
              <span className="font-label-mono text-sm text-on-surface-variant">
                {active ? (liveStatus.taskDurationSeconds ? `${Math.round(liveStatus.taskDurationSeconds)}s` : '0s') : '—'}
              </span>
            </div>
          </div>
        );
      })()}

      {/* ── Assessment (RULA / REBA) ── */}
      <div className="rounded border border-purple-400/30 bg-purple-500/10 p-sm">
        <p className="font-label-caps text-xs text-on-surface-variant uppercase tracking-widest">Assessment</p>
        {!active ? (
          <p className="text-sm text-on-surface-variant mt-0.5">No active session — assessment starts when monitoring begins.</p>
        ) : contextSnapshot?.assessment_method ? (
          <div className="flex items-center justify-between mt-0.5">
            <span className="text-title-md font-bold" style={{ color: riskColorHex(contextSnapshot.assessment_band || 'low') }}>
              {contextSnapshot.assessment_method} {contextSnapshot.assessment_score}
              <span className="text-on-surface-variant text-sm">/{contextSnapshot.assessment_method === 'REBA' ? '15' : '7'}</span>
            </span>
            <span
              className="text-sm font-medium px-1.5 py-0.5 rounded"
              style={{ color: riskColorHex(contextSnapshot.assessment_band || 'low'), backgroundColor: `color-mix(in srgb, ${riskColorHex(contextSnapshot.assessment_band || 'low')} 13%, transparent)` }}
            >
              {contextSnapshot.assessment_band?.toUpperCase() || '—'}
            </span>
          </div>
        ) : (
          <p className="text-sm text-on-surface-variant mt-0.5">Waiting for assessment…</p>
        )}
      </div>

      {/* ── Camera framing ── */}
      <CameraFramingNote snapshot={contextSnapshot} unavailableFeatures={unavailableFeatures} active={active} />

      <div className="grid grid-cols-3 gap-xs">
        <OverrideButton onOverride={onOverride} currentLevel={liveStatus.riskLevel} disabled={!active} />
        <PlaceholderAction icon={Camera} label="Capture" onClick={onCapture} real disabled={!active} />
        <LogButton onLog={onLog} workerName={session.workerName} disabled={!active} />
      </div>

      <div className="grid grid-cols-3 gap-sm pt-sm border-t border-outline-variant">
        <Metric label="Worker" value={session.workerName || 'Not assigned'} />
        <Metric label="Task" value={(() => { const c = Math.round((liveStatus.taskConfidence ?? liveStatus.confidence ?? 0) * 100); return active ? (c < 50 && liveStatus.currentTask ? 'Uncertain' : (liveStatus.currentTask || 'Classifying…')) : 'No active session'; })()} />
        <Metric label="Duration" value={active ? (liveStatus.taskDurationSeconds ? `${Math.round(liveStatus.taskDurationSeconds)}s` : '0s') : '—'} />
        <Metric label="Status" value={active ? humanizeStatus(liveStatus.workerStatus || session.cameraStatus) : 'Idle'} />
        <Metric label="Confidence" value={active ? `${Math.round(liveStatus.confidence)}%` : '—'} />
      </div>
    </aside>
  );
}

function humanizeStatus(status: string): string {
  const s = (status || '').toLowerCase();
  if (s === 'active' || s === 'monitoring') return 'Active';
  if (s === 'disconnected' || s === 'offline') return 'No camera';
  if (s === 'idle' || s === 'ready') return 'Idle';
  return status || '—';
}

function riskColorHex(level: string): string {
  switch (level.toLowerCase()) {
    case 'low': return 'var(--color-chart-green)';
    case 'medium': return 'var(--color-chart-orange)';
    case 'high': return 'var(--color-chart-red)';
    default: return 'var(--color-outline)';
  }
}

// ── RULA / REBA score card (mirrors the demo's RULA SCORE panel) ──
function RulaScoreCard({ snapshot, active }: { snapshot: ContextSnapshot | null; active: boolean }) {
  const method = snapshot?.assessment_method ?? null;
  const score = snapshot?.assessment_score ?? null;
  const band = snapshot?.assessment_band ?? null;
  const maxScore = method === 'REBA' ? 15 : 7;
  const color = riskColorHex(band || 'low');

  return (
    <div className="bg-surface-container border border-outline-variant rounded-xl p-lg">
      <div className="flex items-center gap-sm mb-md">
        <Brain className="w-4 h-4 text-purple-400" />
        <SectionHeader title="Posture Assessment" />
      </div>
      <p className="text-[11px] text-on-surface-variant/70 -mt-sm mb-md">RULA/REBA-informed score (technical detail for supervisors)</p>
      {!active ? (
        <IdleNote message="Start monitoring to see the posture assessment." />
      ) : method && score != null ? (
        <>
          <div className="flex items-center gap-md">
            <span className="font-label-mono text-3xl font-bold" style={{ color }}>
              {score}
              <span className="text-on-surface-variant text-lg">/{maxScore}</span>
            </span>
            <div>
              <p className="text-body-sm font-bold" style={{ color }}>{band?.toUpperCase() || '—'}</p>
              <p className="text-sm text-on-surface-variant">{method} — {method === 'REBA' ? 'full body' : 'upper body'} assessment</p>
            </div>
          </div>
          {snapshot?.rula_is_partial && method === 'RULA' && (
            <p className="mt-sm text-sm text-amber-400 rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-1">
              Partial assessment — some landmarks unavailable (legs out of frame score neutral).
            </p>
          )}
          <p className="mt-md text-sm text-on-surface-variant leading-relaxed">
            RULA 1–2 low · 3–4 medium · 5+ high. REBA 1–3 low · 4–7 medium · 8+ high.
          </p>
        </>
      ) : (
        <IdleNote message="Waiting for assessment…" />
      )}
    </div>
  );
}

// ── Camera framing card (mirrors the demo's CAMERA FRAMING panel) ──
function CameraFramingCard({ snapshot, unavailableFeatures, active }: { snapshot: ContextSnapshot | null; unavailableFeatures: string[]; active: boolean }) {
  // Tier 3: when the framing-intelligence module has produced a real
  // assessment (profile view / cropped / occlusion aware), prefer its state
  // and guidance over the legacy lower-body heuristic.
  const framingState = snapshot?.framing?.framing_state;
  const framingGuidance = snapshot?.framing?.guidance as string[] | undefined;
  const framingQuality = snapshot?.framing?.quality_score as number | undefined;
  const personCount = snapshot?.person_count;
  const lowerBodyConf = snapshot?.lower_body_confidence;
  const missingLower = unavailableFeatures.some((f) => ['trunk_flexion', 'knee_angle', 'stance_stability', 'weight_shift_offset'].includes(f));
  const bad = framingState === 'poor' || framingState === 'upper_body'
    || (!framingState && (missingLower || (lowerBodyConf != null && lowerBodyConf < 50)));
  const idWorker = snapshot?.identified_worker;
  const idEmp = idWorker?.employee_id || idWorker?.worker_id;
  const idConf = idWorker?.confidence;
  const idMatched = !!idWorker?.matched;
  const idLive = idWorker?.liveness;
  const idSpoofed = idMatched && idLive === 'suspicious';
  // ALL detected persons with per-person identity (box + worker_id + name).
  // This is the source of truth — the primary card entry is just the largest
  // matched box. Unknown faces show as "Not recognized".
  const personIdentities = snapshot?.person_identities || [];

  const guidanceLines = framingGuidance?.length
    ? framingGuidance
    : ['Lower body out of frame — reposition camera to mid-thigh for full-body REBA.'];

  return (
    <div className={`bg-surface-container border rounded-xl p-lg ${bad ? 'border-amber-500/40' : 'border-outline-variant'}`}>
      <div className="flex items-center gap-sm mb-md">
        <ScanLine className={`w-4 h-4 ${bad ? 'text-amber-400' : active ? 'text-green-400' : 'text-on-surface-variant'}`} />
        <SectionHeader title="Camera Framing" />
      </div>
      {!active ? (
        <IdleNote message="Start monitoring to check camera framing." />
      ) : bad ? (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-md py-sm">
          <p className="text-body-sm font-bold text-amber-400">
            {framingState === 'poor' ? 'Poor framing — worker not fully visible' : framingState === 'upper_body' ? 'Upper body only — lower body out of frame' : 'Lower body out of frame'}
          </p>
          {guidanceLines.slice(0, 2).map((g, i) => (
            <p key={i} className="text-sm text-amber-400/80 mt-0.5">{g}</p>
          ))}
          {framingQuality != null && (
            <p className="text-sm font-mono text-amber-400/70 mt-1">Framing quality: {Math.round(framingQuality)}%</p>
          )}
          {lowerBodyConf != null && (
            <p className="text-sm font-mono text-amber-400/70 mt-1">Lower-body confidence: {Math.round(lowerBodyConf)}%</p>
          )}
          {unavailableFeatures.length > 0 && (
            <p className="text-xs text-amber-400/60 mt-1">Unavailable: {unavailableFeatures.join(', ')}</p>
          )}
        </div>
      ) : (
        <div>
          <p className="text-body-sm text-green-400 font-medium">{personCount && personCount > 1 ? `${personCount} workers in view` : 'Full body in frame'}</p>
          {personIdentities.length > 0 ? (
            <ul className="mt-1 space-y-0.5">
              {personIdentities.map((p, i) => {
                const emp = p.employee_id || p.worker_id;
                const matched = !!p.matched && !!p.worker_id;
                const spoofed = matched && p.liveness === 'suspicious';
                const verifying = matched && !spoofed && p.liveness !== 'live';
                // Tag by Employee ID. A matched face only counts as PRESENT
                // once the liveness gate proves it live — otherwise it's
                // flagged PHOTO? (spoof) or VERIFYING (still accumulating
                // blink/motion evidence).
                const tag = matched
                  ? `${emp}${p.confidence && p.confidence > 0 ? ` · ${(p.confidence * 100).toFixed(0)}%` : ''}${spoofed ? ' · PHOTO?' : verifying ? ' · VERIFYING' : ''}`
                  : p.seen || (p.confidence && p.confidence > 0)
                    ? 'Not recognized'
                    : null;
                if (!tag) return null;
                const color = spoofed ? 'text-orange-400' : verifying ? 'text-amber-300' : matched ? 'text-emerald-300' : 'text-amber-300';
                return (
                  <li key={i} className={`text-body-sm ${color} font-medium`}>
                    {spoofed ? '⚠ ' : matched && !verifying ? '✓ ' : ''}{tag}
                  </li>
                );
              })}
              {personIdentities.some((p) => !!p.matched && p.liveness === 'suspicious') && (
                <li className="mt-1 text-body-sm font-bold text-orange-400">
                  ⚠ Spoof detected — face is a photo/screen, NOT physically present
                </li>
              )}
            </ul>
          ) : active && personCount ? (
            <p className="text-body-sm text-on-surface-variant mt-1">Worker identity: not enrolled / unseen</p>
          ) : null}
          {framingQuality != null && (
            <p className="text-sm font-mono text-green-400/70 mt-0.5">Framing quality: {Math.round(framingQuality)}%</p>
          )}
        </div>
      )}
    </div>
  );
}

// ── Plain-language posture status (the tired-worker layer) ──
// Big, jargon-free, color-coded: a worker at 3 m should know in one glance
// whether their posture is OK, needs attention, or must be corrected NOW.
// Technical detail (RULA/REBA bands, feature values) stays in the cards below.
function PostureStatusBanner({ riskLevel, active, currentTask }: { riskLevel: string; active: boolean; currentTask?: string | null }) {
  if (!active) {
    return (
      <div className="rounded-xl border border-outline-variant bg-surface-container-low px-lg py-md">
        <p className="text-body-md font-semibold text-on-surface-variant">Start monitoring to see your posture status.</p>
      </div>
    );
  }
  const level = (riskLevel || '').toUpperCase();
  const critical = level === 'HIGH' || level === 'CRITICAL';
  const attention = level === 'MEDIUM';
  const statusText = critical ? 'STOP — unsafe posture' : attention ? 'Watch your back' : 'Posture: OK';
  const statusDetail = critical
    ? 'Correct your posture now — hold position and adjust.'
    : attention
      ? 'Posture needs attention — straighten up and take it easy.'
      : 'Working in a safe range — keep it up.';
  return (
    <div
      className={`rounded-xl border px-lg py-md flex flex-wrap items-center justify-between gap-md ${
        critical ? 'border-red-500/40 bg-red-500/10' : attention ? 'border-amber-500/40 bg-amber-500/10' : 'border-green-500/30 bg-green-500/5'
      }`}
    >
      <div>
        <p
          className={`text-display-md font-extrabold ${
            critical ? 'text-red-400' : attention ? 'text-amber-400' : 'text-emerald-300'
          }`}
        >
          {statusText}
        </p>
        <p className="text-body-md text-on-surface-variant mt-0.5">{statusDetail}</p>
      </div>
      {currentTask ? (
        <div className="text-right">
          <p className="font-label-caps text-xs uppercase tracking-widest text-on-surface-variant">Current task</p>
          <p className="text-body-md font-semibold text-on-surface">{currentTask}</p>
        </div>
      ) : null}
    </div>
  );
}

// ── Station Risk — per-person posture risk for every worker in view ──
// Each detected pose gets its own risk (the primary mirrors the main engine;
// secondary workers are scored by the same deterministic thresholds). This is
// the multi-worker answer to "what's happening on line 2 right now."
function StationRiskCard({ snapshot, active }: { snapshot: ContextSnapshot | null; active: boolean }) {
  const risks = snapshot?.person_risks || [];
  const color = (level: string) => {
    const l = (level || '').toLowerCase();
    if (l === 'high' || l === 'critical') return 'text-red-400';
    if (l === 'medium') return 'text-orange-400';
    return 'text-emerald-300';
  };
  return (
    <section className="bg-surface-container border border-outline-variant rounded-xl p-lg">
      <div className="flex items-center gap-sm mb-md">
        <Users className="w-4 h-4 text-primary" />
        <SectionHeader title="Station Risk" />
      </div>
      {!active ? (
        <IdleNote message="Start monitoring to see every worker's risk at this station." />
      ) : risks.length === 0 ? (
        <IdleNote message="No people in view." />
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-md">
          {risks.map((r) => (
            <div
              key={r.person_index}
              className={`rounded-lg border p-md ${r.is_primary ? 'border-primary/40 bg-primary/5' : 'border-outline-variant/60 bg-surface-container-low'}`}
            >
              <div className="flex items-center justify-between">
                <p className="text-body-sm font-bold text-on-surface">
                  {r.is_primary ? 'Primary worker' : `Person ${r.person_index + 1}`}
                </p>
                <p className={`text-body-sm font-bold ${color(r.risk_level)}`}>{r.risk_level}</p>
              </div>
              <p className="text-body-sm text-on-surface-variant mt-1">
                {r.top_issue ? `Issue: ${String(r.top_issue).replace(/_/g, ' ')}` : 'No posture issue'}
              </p>
              {typeof r.keypoint_visibility === 'number' && r.keypoint_visibility > 0 && (
                <p className="text-[11px] text-on-surface-variant/70 mt-0.5">
                  Visibility {Math.round(r.keypoint_visibility * 100)}%
                </p>
              )}
            </div>
          ))}
        </div>
      )}
      {risks.length > 1 && (
        <p className="text-[11px] text-on-surface-variant/70 mt-md">
          Secondary workers are scored by deterministic thresholds; fatigue &amp; alerts track the primary worker.
        </p>
      )}
    </section>
  );
}

function CameraFramingNote({ snapshot, unavailableFeatures, active }: { snapshot: ContextSnapshot | null; unavailableFeatures: string[]; active: boolean }) {
  const lowerBodyConf = snapshot?.lower_body_confidence;
  const missingLower = unavailableFeatures.some((f) => ['trunk_flexion', 'knee_angle', 'stance_stability', 'weight_shift_offset'].includes(f));
  const bad = missingLower || (lowerBodyConf != null && lowerBodyConf < 50);

  if (!active) {
    return (
      <div className="flex items-center gap-sm rounded border border-white/10 bg-white/[0.03] px-sm py-xs">
        <span className="w-1.5 h-1.5 rounded-full bg-outline" />
        <span className="text-sm text-on-surface-variant">Camera not in use — framing check starts with the session</span>
      </div>
    );
  }
  if (!bad) {
    return (
      <div className="flex items-center gap-sm rounded border border-green-400/20 bg-green-500/5 px-sm py-xs">
        <span className="w-1.5 h-1.5 rounded-full bg-green-400" />
        <span className="text-sm text-green-300">Full body in frame</span>
      </div>
    );
  }
  return (
    <div className="rounded border border-amber-400/30 bg-amber-500/10 px-sm py-xs">
      <p className="text-sm font-bold text-amber-300 uppercase tracking-widest">⚠ Camera Framing</p>
      <p className="text-sm text-amber-300/80 mt-0.5">Lower body out of frame — reposition camera to mid-thigh.</p>
    </div>
  );
}

function RiskGauge({ liveStatus, active }: { liveStatus: LiveStatus; active: boolean }) {
  const score = Math.max(0, Math.min(100, liveStatus.riskScore || 0));
  const color = liveStatus.riskLevel === 'high' ? '#fb7185' : liveStatus.riskLevel === 'moderate' ? '#f59e0b' : '#22c55e';
  const ring = `conic-gradient(${color} ${score * 3.6}deg, rgba(148,163,184,0.16) 0deg)`;

  if (!active) {
    return (
      <div className="rounded border border-white/10 bg-white/[0.03] p-md text-center">
        <p className="font-label-caps text-sm text-on-surface-variant uppercase tracking-widest">Current Risk Index</p>
        <div className="mx-auto mt-sm grid h-28 w-28 place-items-center rounded-full border border-white/10 bg-black/30">
          <div className="grid h-20 w-20 place-items-center rounded-full bg-[#080d13] border border-white/10">
            <div>
              <p className="font-label-mono text-2xl font-bold text-on-surface-variant">—</p>
              <p className="font-label-caps text-xs uppercase tracking-widest text-on-surface-variant">Not measuring</p>
            </div>
          </div>
        </div>
        <p className="mt-sm text-sm italic text-on-surface-variant">Start monitoring to measure risk.</p>
      </div>
    );
  }

  return (
    <div className="rounded border border-cyan-400/15 bg-white/[0.03] p-md text-center">
      <p className="font-label-caps text-sm text-on-surface-variant uppercase tracking-widest">Current Risk Index</p>
      <div className="mx-auto mt-sm grid h-28 w-28 place-items-center rounded-full" style={{ background: ring, boxShadow: `0 0 24px ${color}33` }}>
        <div className="grid h-20 w-20 place-items-center rounded-full bg-[#080d13] border border-white/10">
          <div>
            <p className="font-label-mono text-2xl font-bold text-on-surface">{score.toFixed(0)}</p>
            <p className="font-label-caps text-xs uppercase tracking-widest" style={{ color }}>{liveStatus.riskLevel}</p>
          </div>
        </div>
      </div>
      <p className="mt-sm text-sm italic text-on-surface-variant">Normal operation range maintained</p>
    </div>
  );
}

// Unified neutral empty-state note for the "no active session" case — muted
// icon, consistent phrasing, gray (idle is neither good nor bad).
function IdleNote({ message }: { message: string }) {
  return (
    <div className="flex min-h-[160px] flex-col items-center justify-center gap-md rounded-xl border border-outline-variant bg-surface-container-low p-lg text-center">
      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-surface-container-highest">
        <Radio className="h-5 w-5 text-on-surface-variant" />
      </div>
      <p className="text-body-sm font-medium text-on-surface-variant">{message}</p>
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
  forward_head_posture: 'N/A — face the camera so your face is visible',
  head_tilt_angle: 'N/A — face the camera so your face is visible',
  wrist_deviation_angle: 'N/A — move your hands into frame',
  stance_stability: 'N/A — move back so your legs are visible',
  weight_shift_offset: 'N/A — move back so your legs are visible',
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
        <span className={`text-sm truncate ${isUnavailable ? 'text-on-surface-variant/50' : 'text-on-surface-variant'}`}>{feature.name}</span>
        <span className={`font-label-mono text-sm flex items-center gap-1 ${isUnavailable ? 'text-on-surface-variant/50' : 'text-on-surface'}`}>
          {isUnavailable ? 'N/A' : isApproximate ? `~${feature.value!.toFixed(1)}${feature.unit}` : `${feature.value!.toFixed(1)}${feature.unit}`}
          {isApproximate && !isUnavailable && (
            <span className="text-[11px] text-amber-400/70 italic font-normal" title="Computed via fallback method (image-vertical instead of hip-anchored)">approx</span>
          )}
        </span>
      </div>
      <div className="mt-xs h-1 overflow-hidden rounded-full bg-white/10">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}

function FeatureRowCompact({ feature, isApproximate }: { feature: ErgonomicFeature; isApproximate?: boolean }) {
  const isUnavailable = feature.status === 'unavailable' || feature.value === null;
  const color = isUnavailable ? 'text-on-surface-variant/50' : feature.status === 'high' ? 'text-red-400' : feature.status === 'moderate' ? 'text-orange-400' : feature.status === 'low' ? 'text-blue-400' : 'text-green-400';
  return (
    <div className={`rounded-lg border p-md ${isUnavailable ? 'border-outline-variant/40 bg-surface-container-low' : 'border-outline-variant/60 bg-surface-container-low'}`}>
      <p className={`text-sm font-medium truncate ${isUnavailable ? 'text-on-surface-variant/50' : 'text-on-surface-variant'}`}>{feature.name}</p>
      <p className={`font-label-mono text-title-md font-bold mt-0.5 ${color}`}>
        {isUnavailable ? 'N/A' : isApproximate ? `~${feature.value!.toFixed(1)}${feature.unit}` : `${feature.value!.toFixed(1)}${feature.unit}`}
      </p>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <p className="font-label-caps text-xs uppercase tracking-widest text-on-surface-variant">{label}</p>
      <p className="mt-0.5 truncate font-label-mono text-sm text-on-surface">{value}</p>
    </div>
  );
}

function PlaceholderAction({ icon: Icon, label, onClick, real, disabled }: { icon: typeof Camera; label: string; onClick?: () => void; real?: boolean; disabled?: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={disabled ? 'Start monitoring to use this action' : `${label} current frame`}
      className={`relative flex items-center justify-center gap-xs rounded border h-12 px-md text-sm font-medium transition-colors ${
        disabled
          ? 'border-white/5 bg-white/[0.02] text-on-surface-variant/40 cursor-not-allowed'
          : real
            ? 'border-cyan-400/40 bg-cyan-400/10 text-cyan-200 hover:bg-cyan-400/20'
            : 'border-white/10 bg-white/[0.03] text-on-surface-variant hover:border-cyan-400/25 hover:text-cyan-100'
      }`}
    >
      <Icon className="h-3.5 w-3.5" />
      {label}
      {!real && !disabled && <span className="absolute -top-1 -right-1 text-[11px] leading-none text-on-surface-variant/60">*</span>}
    </button>
  );
}

function LogButton({ onLog, workerName, disabled }: { onLog?: (note: string, category: string) => void; workerName: string; disabled?: boolean }) {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState('');
  const [category, setCategory] = useState('general');

  const handleSubmit = () => {
    if (!note.trim()) return;
    onLog?.(note.trim(), category);
    setNote('');
    setCategory('general');
    setOpen(false);
  };

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        disabled={disabled}
        title={disabled ? 'Start monitoring to log observations' : 'Log an observation'}
        className={`relative flex items-center justify-center gap-xs rounded border h-12 px-md text-sm font-medium transition-colors ${
          disabled
            ? 'border-white/5 bg-white/[0.02] text-on-surface-variant/40 cursor-not-allowed'
            : 'border-white/10 bg-white/[0.03] text-on-surface-variant hover:border-cyan-400/25 hover:text-cyan-100'
        }`}
      >
        <FileText className="h-3.5 w-3.5" />
        Log
      </button>
    );
  }

  return (
    <div className="col-span-3 rounded border border-cyan-400/30 bg-black/60 p-sm space-y-xs">
      <select
        value={category}
        onChange={(e) => setCategory(e.target.value)}
        className="w-full bg-surface-container-high border border-outline-variant rounded px-sm py-2 text-sm text-on-surface"
      >
        <option value="general">General</option>
        <option value="safety">Safety</option>
        <option value="posture">Posture</option>
        <option value="environment">Environment</option>
      </select>
      <textarea
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="Observation note..."
        rows={2}
        className="w-full bg-surface-container-high border border-outline-variant rounded px-sm py-2 text-sm text-on-surface placeholder:text-on-surface-variant resize-none"
        autoFocus
      />
      <div className="flex gap-xs">
        <button type="button" onClick={handleSubmit} className="flex-1 rounded bg-cyan-500/20 border border-cyan-400/40 text-cyan-200 text-sm py-2 hover:bg-cyan-500/30">
          Save
        </button>
        <button type="button" onClick={() => { setOpen(false); setNote(''); }} className="flex-1 rounded border border-white/10 text-on-surface-variant text-sm py-2 hover:text-cyan-100">
          Cancel
        </button>
      </div>
    </div>
  );
}

function OverrideButton({ onOverride, currentLevel, disabled }: { onOverride?: (level: string, reason: string) => void; currentLevel: string; disabled?: boolean }) {
  const [open, setOpen] = useState(false);
  const [level, setLevel] = useState(currentLevel.toUpperCase());
  const [reason, setReason] = useState('');

  const handleSubmit = () => {
    onOverride?.(level, reason.trim());
    setReason('');
    setOpen(false);
  };

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        disabled={disabled}
        title={disabled ? 'Start monitoring to override risk' : 'Manually override risk level'}
        className={`relative flex items-center justify-center gap-xs rounded border h-12 px-md text-sm font-medium transition-colors ${
          disabled
            ? 'border-white/5 bg-white/[0.02] text-on-surface-variant/40 cursor-not-allowed'
            : 'border-white/10 bg-white/[0.03] text-on-surface-variant hover:border-orange-400/40 hover:text-orange-300'
        }`}
      >
        <ShieldAlert className="h-3.5 w-3.5" />
        Override
      </button>
    );
  }

  return (
    <div className="col-span-3 rounded border border-orange-400/30 bg-black/60 p-sm space-y-xs">
      <select
        value={level}
        onChange={(e) => setLevel(e.target.value)}
        className="w-full bg-surface-container-high border border-outline-variant rounded px-sm py-2 text-sm text-on-surface"
      >
        <option value="LOW">LOW</option>
        <option value="MEDIUM">MEDIUM</option>
        <option value="HIGH">HIGH</option>
      </select>
      <input
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        placeholder="Reason (optional)"
        className="w-full bg-surface-container-high border border-outline-variant rounded px-sm py-2 text-sm text-on-surface placeholder:text-on-surface-variant"
        autoFocus
      />
      <div className="flex gap-xs">
        <button type="button" onClick={handleSubmit} className="flex-1 rounded bg-orange-500/20 border border-orange-400/40 text-orange-300 text-sm py-2 hover:bg-orange-500/30">
          Apply
        </button>
        <button type="button" onClick={() => { setOpen(false); setReason(''); }} className="flex-1 rounded border border-white/10 text-on-surface-variant text-sm py-2 hover:text-cyan-100">
          Cancel
        </button>
      </div>
    </div>
  );
}


