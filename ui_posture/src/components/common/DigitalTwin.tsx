import type { ErgonomicFeature } from '@/src/types/api';

interface DigitalTwinProps {
  features: ErgonomicFeature[];
}

function bodyColor(features: ErgonomicFeature[], id: string): string {
  const f = features.find((x) => x.id === id);
  if (!f) return '#8c909f';
  if (f.status === 'high') return '#ef4444';
  if (f.status === 'moderate') return '#f97316';
  if (f.status === 'low') return '#22c55e';
  return '#22c55e';
}

function bodyGlow(features: ErgonomicFeature[], id: string): string {
  const f = features.find((x) => x.id === id);
  if (!f) return 'none';
  if (f.status === 'high') return 'url(#glowRed)';
  if (f.status === 'moderate') return 'url(#glowOrange)';
  return 'none';
}

export function DigitalTwin({ features }: DigitalTwinProps) {
  return (
    <div className="bg-surface-container border border-outline-variant rounded-xl p-lg flex flex-col items-center">
      <h3 className="font-label-caps text-label-caps text-on-surface uppercase tracking-widest mb-md self-start">Digital Twin</h3>
      <svg viewBox="0 0 200 380" className="w-32 h-64 md:w-40 md:h-72">
        <defs>
          <radialGradient id="glowRed" cx="50%" cy="50%" r="50%"><stop offset="0%" stopColor="#ef4444" stopOpacity="0.6" /><stop offset="100%" stopColor="#ef4444" stopOpacity="0" /></radialGradient>
          <radialGradient id="glowOrange" cx="50%" cy="50%" r="50%"><stop offset="0%" stopColor="#f97316" stopOpacity="0.5" /><stop offset="100%" stopColor="#f97316" stopOpacity="0" /></radialGradient>
        </defs>
        <g strokeWidth="2.5" fill="none" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="100" cy="42" r="18" stroke={bodyColor(features, 'neck_flexion')} fill={bodyGlow(features, 'neck_flexion')} />
          <line x1="100" y1="60" x2="100" y2="110" stroke={bodyColor(features, 'trunk_flexion')} />
          <line x1="100" y1="82" x2="70" y2="105" stroke={bodyColor(features, 'left_shoulder_elev')} />
          <line x1="100" y1="82" x2="130" y2="105" stroke={bodyColor(features, 'right_shoulder_elev')} />
          <line x1="70" y1="105" x2="55" y2="155" stroke={bodyColor(features, 'left_shoulder_elev')} />
          <line x1="130" y1="105" x2="145" y2="155" stroke={bodyColor(features, 'right_shoulder_elev')} />
          <line x1="100" y1="110" x2="100" y2="200" stroke={bodyColor(features, 'trunk_flexion')} />
          <line x1="100" y1="155" x2="75" y2="185" stroke={bodyColor(features, 'alignment_deviation')} />
          <line x1="100" y1="155" x2="125" y2="185" stroke={bodyColor(features, 'alignment_deviation')} />
          <line x1="100" y1="200" x2="80" y2="260" stroke={bodyColor(features, 'knee_angle')} />
          <line x1="100" y1="200" x2="120" y2="260" stroke={bodyColor(features, 'knee_angle')} />
          <line x1="80" y1="260" x2="80" y2="320" stroke={bodyColor(features, 'knee_angle')} />
          <line x1="120" y1="260" x2="120" y2="320" stroke={bodyColor(features, 'knee_angle')} />
          <line x1="75" y1="185" x2="55" y2="210" stroke={bodyColor(features, 'alignment_deviation')} />
          <line x1="125" y1="185" x2="145" y2="210" stroke={bodyColor(features, 'alignment_deviation')} />
        </g>
      </svg>
      <div className="flex items-center gap-md mt-md text-[10px] font-label-mono">
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-green-500" />Safe</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-orange-500" />Caution</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-500" />Risk</span>
      </div>
    </div>
  );
}
