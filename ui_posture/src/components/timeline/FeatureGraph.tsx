import { useRef, type MouseEvent } from 'react';
import type { TimelineEntry } from '@/src/types/api';

const FEATURE_LABELS: Record<string, string> = {
  risk_score: 'Overall Risk',
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
  risk_score: '#fb7185',
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

interface Props {
  timeline: TimelineEntry[];
  selectedFeature: string;
  onSelectFeature: (f: string) => void;
  seekTo: (t: number) => void;
  currentTime: number;
}

export default function FeatureGraph({ timeline, selectedFeature, onSelectFeature, seekTo, currentTime }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  if (timeline.length === 0) return null;

  const maxTime = timeline[timeline.length - 1].timestamp;
  const values = timeline.map(e => e.risk_score ?? e.features[selectedFeature] ?? 0);
  const minVal = Math.min(...values);
  const maxVal = Math.max(...values);
  const range = maxVal - minVal || 1;

  const points = timeline.map((e, i) => {
    const x = 50 + (e.timestamp / maxTime) * 700;
    const v = e.risk_score ?? e.features[selectedFeature] ?? minVal;
    const y = 180 - (v - minVal) / range * 150;
    return `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`;
  }).join(' ');

  const seekPct = maxTime > 0 ? (currentTime / maxTime) : 0;
  const seekX = 50 + seekPct * 700;

  const handleClick = (e: MouseEvent<SVGSVGElement>) => {
    if (!svgRef.current || maxTime <= 0) return;
    const rect = svgRef.current.getBoundingClientRect();
    const pct = (e.clientX - rect.left) / rect.width;
    seekTo(pct * maxTime);
  };

  const label = FEATURE_LABELS[selectedFeature] ?? selectedFeature;
  const unit = selectedFeature === 'knee_angle' ? '°' : selectedFeature.includes('shoulder') || selectedFeature === 'neck_flexion' || selectedFeature === 'trunk_flexion' ? '°' : '%';

  return (
    <section className="rounded-lg border border-outline-variant bg-surface-container-low p-md">
      <div className="flex flex-wrap items-center justify-between gap-sm mb-sm">
        <h3 className="text-body-sm font-bold text-on-surface">{label} Over Time</h3>
        <div className="flex flex-wrap gap-1">
          {Object.entries(FEATURE_LABELS).map(([key, name]) => (
            <button
              key={key}
              className={`text-[9px] px-1.5 py-0.5 rounded transition-colors ${
                selectedFeature === key
                  ? 'bg-primary/20 text-primary border border-primary/40'
                  : 'text-on-surface-variant border border-outline-variant/60 hover:bg-surface-container-highest'
              }`}
              onClick={() => onSelectFeature(key)}
            >
              {name}
            </button>
          ))}
        </div>
      </div>
      <svg ref={svgRef} viewBox="0 0 800 200" className="w-full h-48 cursor-pointer" onClick={handleClick}>
        <line x1="50" y1="30" x2="50" y2="180" stroke="#424754" />
        <line x1="50" y1="180" x2="780" y2="180" stroke="#424754" />
        <text x="8" y="36" fill="#c2c6d6" fontSize="10">{maxVal.toFixed(0)}{unit}</text>
        <text x="22" y="108" fill="#c2c6d6" fontSize="10">{((maxVal + minVal) / 2).toFixed(0)}{unit}</text>
        <text x="28" y="176" fill="#c2c6d6" fontSize="10">{minVal.toFixed(0)}{unit}</text>
        {points && <path d={points} fill="none" stroke={FEATURE_COLORS[selectedFeature] ?? '#60a5fa'} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />}
        <line x1={seekX} y1="30" x2={seekX} y2="180" stroke="#fff" strokeWidth="1" strokeDasharray="3,3" opacity="0.7" />
        <text x={seekX - 10} y="196" fill="#fff" fontSize="9">{currentTime.toFixed(1)}s</text>
      </svg>
    </section>
  );
}
