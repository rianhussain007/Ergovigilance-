import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router';
import { AlertTriangle, Sparkles } from 'lucide-react';
import { getRecordingSummary, getRecordingTimeline, getRecordingVideoUrl } from '@/src/services/dashboardService';
import type { RecordingSummary, TimelineEntry } from '@/src/types/api';
import { EmptyState, ErrorCard, LoadingCard } from '@/src/components/common';
import { TimelineBar, FeatureGraph, TelemetryPanel } from '@/src/components/timeline';

const FEATURE_LABELS: Record<string, string> = {
  neck_flexion: 'Neck Flexion',
  trunk_flexion: 'Trunk Flexion',
  left_shoulder_elev: 'L Shoulder Elev',
  right_shoulder_elev: 'R Shoulder Elev',
  shoulder_symmetry: 'Shoulder Sym',
  alignment_deviation: 'Alignment Dev',
  knee_angle: 'Knee Angle',
  forward_head_posture: 'Forward Head Posture',
  head_tilt_angle: 'Head Tilt',
  wrist_deviation_angle: 'Wrist Deviation',
  stance_stability: 'Stance Stability',
  weight_shift_offset: 'Weight Shift',
};

const FEATURE_COLORS: Record<string, string> = {
  neck_flexion: '#60a5fa',
  trunk_flexion: '#34d399',
  left_shoulder_elev: '#f472b6',
  right_shoulder_elev: '#fb923c',
  shoulder_symmetry: '#a78bfa',
  alignment_deviation: '#fbbf24',
  knee_angle: '#38bdf8',
  forward_head_posture: '#f97316',
  head_tilt_angle: '#22d3ee',
  wrist_deviation_angle: '#e879f9',
  stance_stability: '#4ade80',
  weight_shift_offset: '#facc15',
};

export default function ReplayPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [summary, setSummary] = useState<RecordingSummary | null>(null);
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentEntry, setCurrentEntry] = useState<TimelineEntry | null>(null);
  const [seekTime, setSeekTime] = useState<number>(0);
  const [selectedFeature, setSelectedFeature] = useState<string>('neck_flexion');
  const [showSummary, setShowSummary] = useState(false);

  useEffect(() => {
    if (!sessionId) { setError('No session ID provided'); setLoading(false); return; }
    let cancelled = false;
    Promise.all([
      getRecordingSummary(sessionId),
      getRecordingTimeline(sessionId),
    ]).then(([s, t]) => {
      if (cancelled) return;
      setSummary(s);
      setTimeline(t.timeline);
      if (t.timeline.length > 0) setCurrentEntry(t.timeline[0]);
      setLoading(false);
    }).catch((err) => {
      if (cancelled) return;
      const msg = err instanceof Error ? err.message : 'Failed to load recording';
      if (msg.includes('not found') || msg.includes('Recording not found')) {
        setError('No recording available for this session.');
      } else {
        setError(msg);
      }
      setLoading(false);
    });
    return () => { cancelled = true; };
  }, [sessionId]);

  const videoUrl = sessionId ? getRecordingVideoUrl(sessionId) : '';

  const handleTimeUpdate = useCallback(() => {
    const video = videoRef.current;
    if (!video || timeline.length === 0) return;
    const t = video.currentTime;
    let closest = timeline[0];
    let minDiff = Math.abs(t - closest.timestamp);
    for (let i = 1; i < timeline.length; i++) {
      const diff = Math.abs(t - timeline[i].timestamp);
      if (diff < minDiff) { minDiff = diff; closest = timeline[i]; }
    }
    setCurrentEntry(closest);
    setSeekTime(t);
  }, [timeline]);

  const seekTo = useCallback((time: number) => {
    const video = videoRef.current;
    if (!video) return;
    video.currentTime = time;
    video.play().catch(() => {});
  }, []);

  const riskColor = (level: string) =>
    level === 'HIGH' ? '#ef4444' : level === 'MEDIUM' ? '#f59e0b' : '#22c55e';

  if (loading) return (
    <div className="p-lg space-y-lg pb-32">
      <h1 className="text-display-lg font-bold text-on-surface">Session Replay</h1>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-lg"><LoadingCard height="h-48" /><LoadingCard height="h-48" /><LoadingCard height="h-48" /></div>
    </div>
  );

  if (error) return (
    <div className="p-lg space-y-lg pb-32">
      <h1 className="text-display-lg font-bold text-on-surface">Session Replay</h1>
      <ErrorCard message={error} />
    </div>
  );

  if (!summary) return (
    <div className="p-lg space-y-lg pb-32">
      <h1 className="text-display-lg font-bold text-on-surface">Session Replay</h1>
      <EmptyState title="No replay data" message="Replay is being prepared..." />
    </div>
  );

  return (
    <div className="p-lg space-y-lg pb-32">
      <div className="flex flex-wrap items-end justify-between gap-md">
        <div>
          <h1 className="text-display-lg font-bold text-on-surface">Session Replay</h1>
          <p className="mt-xs text-body-sm text-on-surface-variant">
            {summary.session_id} &middot; {summary.worker_id}
          </p>
        </div>
        <button
          className="rounded-lg bg-surface-container border border-outline-variant px-md py-sm text-body-sm text-on-surface-variant hover:bg-surface-container-highest"
          onClick={() => setShowSummary(!showSummary)}
        >
          {showSummary ? 'Hide Summary' : 'Session Summary'}
        </button>
      </div>

      {showSummary && summary && <SessionSummaryCard summary={summary} />}

      <section className="grid grid-cols-1 gap-lg xl:grid-cols-[1fr_380px]">
        <div className="space-y-lg">
          <div className="rounded-lg border border-outline-variant bg-surface-container overflow-hidden">
            <video
              ref={videoRef}
              src={videoUrl}
              className="w-full max-h-[480px] bg-black"
              controls
              onTimeUpdate={handleTimeUpdate}
              onSeeked={handleTimeUpdate}
            />
          </div>

          <TimelineBar
            timeline={timeline}
            seekTime={seekTime}
            seekTo={seekTo}
            alerts={summary.alerts.filter(a => a.severity === 'HIGH' || a.severity === 'CRITICAL')}
          />

          <FeatureGraph
            timeline={timeline}
            selectedFeature={selectedFeature}
            onSelectFeature={setSelectedFeature}
            seekTo={seekTo}
            currentTime={seekTime}
          />

          {(timeline.length > 0) && (
            <section className="rounded-lg border border-outline-variant bg-surface-container-low p-md">
              <h3 className="text-body-sm font-bold text-on-surface mb-sm">Alert Timeline</h3>
              {summary.alerts.length === 0 ? (
                <p className="text-body-sm text-on-surface-variant">No alerts during this session.</p>
              ) : (
                <div className="max-h-48 overflow-y-auto space-y-xs">
                  {summary.alerts.map((alert) => {
                    const entry = timeline.find(e => e.frame_number === alert.frame_number);
                    const ts = entry ? entry.timestamp : 0;
                    return (
                      <button
                        key={alert.id}
                        className="w-full text-left rounded border border-outline-variant/60 bg-surface-container p-sm hover:bg-surface-container-highest transition-colors"
                        onClick={() => seekTo(ts)}
                      >
                        <div className="flex items-center justify-between gap-sm">
                          <span className="text-body-sm font-medium text-on-surface">{alert.title}</span>
                          <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${
                            alert.severity === 'CRITICAL' ? 'bg-red-500/20 text-red-400' : 'bg-orange-500/20 text-orange-400'
                          }`}>{alert.severity}</span>
                        </div>
                        <p className="text-[11px] text-on-surface-variant mt-0.5">
                          {alert.message} &middot; @{ts.toFixed(1)}s
                        </p>
                      </button>
                    );
                  })}
                </div>
              )}
            </section>
          )}
        </div>

        <aside className="space-y-lg">
          {currentEntry && <TelemetryPanel entry={currentEntry} />}

          <section className="rounded-lg border border-outline-variant bg-surface-container-low p-md">
            <h3 className="text-body-sm font-bold text-on-surface mb-sm">Current Features</h3>
            <div className="space-y-xs">
              {Object.entries(currentEntry?.features ?? {} as Record<string, number>).map(([name, value]) => (
                <button
                  key={name}
                  className={`w-full flex items-center justify-between gap-md rounded px-sm py-1 text-body-sm transition-colors ${
                    selectedFeature === name
                      ? 'bg-primary/10 border border-primary/30'
                      : 'hover:bg-surface-container-highest'
                  }`}
                  onClick={() => { setSelectedFeature(name); }}
                >
                  <span className="text-on-surface-variant">{FEATURE_LABELS[name] ?? name}</span>
                  <span className="font-label-mono text-on-surface" style={{ color: FEATURE_COLORS[name] }}>
                    {value.toFixed(1)}
                  </span>
                </button>
              ))}
            </div>
          </section>

          <section className="rounded-lg border border-dashed border-outline-variant bg-surface-container p-md">
            <div className="flex items-start gap-md">
              <Sparkles className="mt-0.5 h-5 w-5 shrink-0 text-on-surface-variant" />
              <div>
                <p className="font-label-caps text-[10px] text-on-surface-variant">Coming Soon</p>
                <p className="mt-sm text-body-sm text-on-surface-variant">
                  Supervisor comments, AI coaching, replay comparison, frame annotation, collaborative review, and clip export.
                </p>
              </div>
            </div>
          </section>
        </aside>
      </section>
    </div>
  );
}

function SessionSummaryCard({ summary }: { summary: RecordingSummary }) {
  return (
    <section className="rounded-lg border border-outline-variant bg-surface-container p-lg space-y-md">
      <h3 className="text-headline-md font-bold text-on-surface">Session Summary</h3>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-md">
        <div className="rounded border border-outline-variant/60 bg-surface-container-low p-md">
          <p className="font-label-caps text-[9px] text-on-surface-variant">Duration</p>
          <p className="text-body-sm font-bold text-on-surface">{summary.session_duration_seconds.toFixed(1)}s</p>
        </div>
        <div className="rounded border border-outline-variant/60 bg-surface-container-low p-md">
          <p className="font-label-caps text-[9px] text-on-surface-variant">Total Frames</p>
          <p className="text-body-sm font-bold text-on-surface">{summary.total_frames}</p>
        </div>
        <div className="rounded border border-outline-variant/60 bg-surface-container-low p-md">
          <p className="font-label-caps text-[9px] text-on-surface-variant">Highest Risk</p>
          <p className="text-body-sm font-bold text-on-surface" style={{ color: riskColor(summary.highest_risk_level) }}>{summary.highest_risk_level}</p>
        </div>
        <div className="rounded border border-outline-variant/60 bg-surface-container-low p-md">
          <p className="font-label-caps text-[9px] text-on-surface-variant">Alert Count</p>
          <p className="text-body-sm font-bold text-on-surface">{summary.alerts?.length ?? 0}</p>
        </div>
      </div>
      {(summary.risk_percentages) && (
        <div className="grid grid-cols-3 gap-md">
          {(['LOW', 'MEDIUM', 'HIGH'] as const).map((level) => (
            <div key={level} className="rounded border border-outline-variant/60 bg-surface-container-low p-md">
              <p className="font-label-caps text-[9px] text-on-surface-variant">{level}</p>
              <p className="text-body-sm font-bold text-on-surface">{(summary.risk_percentages[level] ?? 0).toFixed(1)}%</p>
              <div className="mt-1 h-1.5 rounded bg-surface-container-highest overflow-hidden">
                <div className="h-full rounded" style={{
                  width: `${Math.min(100, summary.risk_percentages[level] ?? 0)}%`,
                  backgroundColor: level === 'HIGH' ? '#ef4444' : level === 'MEDIUM' ? '#f59e0b' : '#22c55e'
                }} />
              </div>
            </div>
          ))}
        </div>
      )}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-md">
        <div className="rounded border border-outline-variant/60 bg-surface-container-low p-md">
          <p className="font-label-caps text-[9px] text-on-surface-variant">Avg Neck Flexion</p>
          <p className="text-body-sm font-bold text-on-surface">{summary.avg_neck_flexion.toFixed(1)}°</p>
        </div>
        <div className="rounded border border-outline-variant/60 bg-surface-container-low p-md">
          <p className="font-label-caps text-[9px] text-on-surface-variant">Avg Trunk Flexion</p>
          <p className="text-body-sm font-bold text-on-surface">{summary.avg_trunk_flexion.toFixed(1)}°</p>
        </div>
        <div className="rounded border border-outline-variant/60 bg-surface-container-low p-md">
          <p className="font-label-caps text-[9px] text-on-surface-variant">Avg Shoulder Sym</p>
          <p className="text-body-sm font-bold text-on-surface">{summary.avg_shoulder_symmetry.toFixed(1)}%</p>
        </div>
        <div className="rounded border border-outline-variant/60 bg-surface-container-low p-md">
          <p className="font-label-caps text-[9px] text-on-surface-variant">Avg Knee Angle</p>
          <p className="text-body-sm font-bold text-on-surface">{summary.avg_knee_angle.toFixed(1)}°</p>
        </div>
      </div>
    </section>
  );
}

function riskColor(level: string) {
  return level === 'HIGH' ? '#ef4444' : level === 'MEDIUM' ? '#f59e0b' : '#22c55e';
}
