import { Activity, BarChart3, Clock3, HeartPulse, Lightbulb, Thermometer, Timer, TrendingUp } from 'lucide-react';
import type { TimelineEntry } from '@/src/types/api';

// Some recorded sessions predate fields like context/fatigue/exposure — those
// values can arrive as null, so format defensively instead of crashing.
const fmt = (v: number | null | undefined, unit = ''): string =>
  v == null || v !== v ? '—' : `${v.toFixed(1)}${unit}`;

const ITEMS = (entry: TimelineEntry) => [
  { icon: Activity, label: 'Current Risk', value: entry.risk_level || '—', color: entry.risk_level === 'HIGH' ? 'text-red-400' : entry.risk_level === 'MEDIUM' ? 'text-orange-400' : 'text-green-400' },
  { icon: Thermometer, label: 'Risk Score', value: fmt(entry.risk_score) },
  { icon: BarChart3, label: 'Confidence', value: fmt(entry.confidence, '%') },
  { icon: TrendingUp, label: 'Context Score', value: fmt(entry.context_score) },
  { icon: HeartPulse, label: 'Fatigue', value: fmt(entry.fatigue, '%') },
  { icon: Clock3, label: 'Exposure', value: fmt(entry.exposure, '%') },
  { icon: Activity, label: 'Task', value: entry.current_task || '—' },
  { icon: Timer, label: 'Duration', value: entry.task_duration_seconds != null && entry.task_duration_seconds === entry.task_duration_seconds ? `${Math.round(entry.task_duration_seconds)}s` : '0s' },
];

export default function TelemetryPanel({ entry }: { entry: TimelineEntry }) {
  return (
    <div className="rounded-lg border border-outline-variant bg-surface-container p-md space-y-md">
      <h3 className="text-body-sm font-bold text-on-surface">Live Telemetry</h3>
      <div className="grid grid-cols-2 gap-sm">
        {ITEMS(entry).map((item) => (
          <div key={item.label} className="rounded border border-outline-variant/60 bg-surface-container-low p-sm min-h-[72px]">
            <div className="flex items-center gap-1 mb-1">
              <item.icon className="w-3 h-3 text-primary" />
              <span className="font-label-caps text-[9px] text-on-surface-variant">{item.label}</span>
            </div>
            <p className={`text-body-sm font-bold text-on-surface ${item.color ?? ''}`}>{item.value}</p>
          </div>
        ))}
      </div>
      {entry.recommendations?.length > 0 && (
        <div className="rounded border border-outline-variant/60 bg-surface-container-low p-sm">
          <div className="flex items-center gap-1 mb-1">
            <Lightbulb className="w-3 h-3 text-tertiary" />
            <span className="font-label-caps text-[9px] text-on-surface-variant">Recommendation</span>
          </div>
          <p className="text-body-sm text-on-surface">{entry.recommendations[0].title}</p>
        </div>
      )}
    </div>
  );
}
