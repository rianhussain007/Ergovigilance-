import { useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle, Info, Shield, Save } from 'lucide-react';

interface TimelineEvent {
  time: string;
  icon: typeof AlertTriangle;
  color: string;
  text: string;
}

const baseEvents: TimelineEvent[] = [
  { time: '09:12', icon: AlertTriangle, color: 'text-orange-400', text: 'Neck Flexion detected' },
  { time: '09:15', icon: CheckCircle, color: 'text-green-400', text: 'Worker corrected posture' },
  { time: '09:17', icon: Shield, color: 'text-orange-400', text: 'Medium Risk' },
  { time: '09:25', icon: CheckCircle, color: 'text-blue-400', text: 'Recommendation acknowledged' },
  { time: '09:40', icon: Save, color: 'text-primary', text: 'Session saved' },
];

const liveEvents: TimelineEvent[] = [
  { time: '', icon: AlertTriangle, color: 'text-red-400', text: 'High Risk — Trunk asymmetry' },
  { time: '', icon: Info, color: 'text-primary', text: 'AI Insight: Fatigue likely developing' },
  { time: '', icon: CheckCircle, color: 'text-green-400', text: 'Shoulder posture improving' },
];

export function LiveTimeline() {
  const [events, setEvents] = useState<TimelineEvent[]>(baseEvents);
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const interval = setInterval(() => setNow(new Date()), 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      const mins = String(now.getHours()).padStart(2, '0') + ':' + String(now.getMinutes()).padStart(2, '0');
      const idx = Math.floor(Math.random() * liveEvents.length);
      const ev = { ...liveEvents[idx], time: mins };
      setEvents((prev) => [ev, ...prev].slice(0, 12));
    }, 8000);
    return () => clearInterval(interval);
  }, [now]);

  return (
    <div className="bg-surface-container border border-outline-variant rounded-xl p-lg">
      <h3 className="font-label-caps text-label-caps text-on-surface uppercase tracking-widest mb-md">Live Timeline</h3>
      <div className="space-y-0 max-h-72 overflow-y-auto">
        {events.map((ev, i) => {
          const Icon = ev.icon;
          return (
            <div key={i} className="flex gap-md py-sm relative">
              {i < events.length - 1 && <div className="absolute left-[15px] top-8 bottom-0 w-px bg-outline-variant/30" />}
              <div className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 ${ev.color.replace('text-', 'bg-').replace('orange', 'orange-500').replace('green', 'green-500').replace('blue', 'blue-500').replace('red', 'red-500').replace('primary', 'primary')}/10`}>
                <Icon className={`w-3.5 h-3.5 ${ev.color}`} />
              </div>
              <div className="min-w-0 flex-1 flex items-center justify-between">
                <span className="text-body-sm text-on-surface">{ev.text}</span>
                <span className="font-label-mono text-[10px] text-on-surface-variant shrink-0 ml-md">{ev.time}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
