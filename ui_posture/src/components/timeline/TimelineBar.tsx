import { useMemo, useRef, type MouseEvent } from 'react';
import type { TimelineEntry } from '@/src/types/api';

interface TimelineAlert {
  frame_number: number;
  severity: string;
  title: string;
}

interface Props {
  timeline: TimelineEntry[];
  seekTime: number;
  seekTo: (t: number) => void;
  alerts: TimelineAlert[];
}

export default function TimelineBar({ timeline, seekTime, seekTo, alerts }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const maxTime = timeline.length > 0 ? timeline[timeline.length - 1].timestamp : 1;
  const seekPct = maxTime > 0 ? (seekTime / maxTime) * 100 : 0;

  const alertTimes = useMemo(() => {
    const times: { pct: number; severity: string; title: string }[] = [];
    for (const alert of alerts) {
      const e = timeline.find(te => te.frame_number === alert.frame_number);
      if (e && maxTime > 0) {
        times.push({ pct: (e.timestamp / maxTime) * 100, severity: alert.severity, title: alert.title });
      }
    }
    return times;
  }, [alerts, timeline, maxTime]);

  const handleClick = (e: MouseEvent<HTMLDivElement>) => {
    if (!containerRef.current || maxTime <= 0) return;
    const rect = containerRef.current.getBoundingClientRect();
    const pct = (e.clientX - rect.left) / rect.width;
    seekTo(pct * maxTime);
  };

  if (timeline.length === 0) return null;

  return (
    <div className="rounded-lg border border-outline-variant bg-surface-container-low p-md">
      <div className="flex items-center justify-between gap-md mb-sm">
        <h3 className="text-body-sm font-bold text-on-surface">Risk Timeline</h3>
        <div className="flex items-center gap-2 text-xs text-on-surface-variant">
          <span className="flex items-center gap-1"><i className="w-2 h-2 rounded-full bg-green-400" /> Low</span>
          <span className="flex items-center gap-1"><i className="w-2 h-2 rounded-full bg-orange-400" /> Med</span>
          <span className="flex items-center gap-1"><i className="w-2 h-2 rounded-full bg-red-400" /> High</span>
        </div>
      </div>
      <div ref={containerRef} className="relative h-8 rounded overflow-hidden cursor-pointer" onClick={handleClick} style={{ background: 'var(--color-surface-container-high)' }}>
        <div className="absolute inset-0 flex">
          {timeline.map((entry, i) => {
            if (i === timeline.length - 1) return null;
            const x1 = (entry.timestamp / maxTime) * 100;
            const x2 = (timeline[i + 1].timestamp / maxTime) * 100;
            const color = entry.risk_level === 'HIGH' ? 'var(--color-chart-red)' : entry.risk_level === 'MEDIUM' ? 'var(--color-chart-orange)' : 'var(--color-chart-green)';
            return <div key={i} style={{ position: 'absolute', left: `${x1}%`, width: `${x2 - x1}%`, height: '100%', backgroundColor: color, opacity: 0.8 }} />;
          })}
        </div>
        {alertTimes.map((a, i) => (
          <div key={i} className="absolute top-0" style={{ left: `${a.pct}%`, transform: 'translateX(-50%)' }}>
            <span className="text-sm" title={a.title}>{'▲'}</span>
          </div>
        ))}
        <div className="absolute top-0 w-0.5 h-full bg-white opacity-90" style={{ left: `${seekPct}%` }} />
      </div>
      <div className="flex justify-between mt-1 text-xs text-on-surface-variant">
        <span>0s</span>
        <span>{(maxTime / 2).toFixed(0)}s</span>
        <span>{maxTime.toFixed(0)}s</span>
      </div>
    </div>
  );
}
