import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import type { LiveStatus, TrendDirection } from '@/src/types/api';

interface HealthScoreProps {
  liveStatus: LiveStatus | null;
  trend: TrendDirection;
}

function healthScore(riskScore: number): number {
  return Math.max(0, Math.min(100, 100 - riskScore * 1.2));
}

export function HealthScore({ liveStatus, trend }: HealthScoreProps) {
  const score = liveStatus ? healthScore(liveStatus.riskScore) : 82;
  const circumference = 2 * Math.PI * 54;
  const offset = circumference - (score / 100) * circumference;
  const TrendIcon = trend === 'improving' ? TrendingUp : trend === 'deteriorating' ? TrendingDown : Minus;
  const trendColor = trend === 'improving' ? 'text-green-400' : trend === 'deteriorating' ? 'text-red-400' : 'text-blue-400';

  return (
    <div className="bg-surface-container border border-outline-variant rounded-xl p-lg flex flex-col items-center">
      <h3 className="font-label-caps text-label-caps text-on-surface uppercase tracking-widest mb-md self-start">Health Score</h3>
      <div className="relative w-36 h-36">
        <svg className="w-full h-full -rotate-90" viewBox="0 0 120 120">
          <circle cx="60" cy="60" r="54" fill="none" stroke="var(--color-outline-variant)" strokeWidth="8" />
          <circle cx="60" cy="60" r="54" fill="none" stroke="url(#healthGrad)" strokeWidth="8" strokeLinecap="round"
            strokeDasharray={circumference} strokeDashoffset={offset} style={{ transition: 'stroke-dashoffset 0.8s ease' }} />
          <defs>
            <linearGradient id="healthGrad" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" style={{ stopColor: 'var(--color-chart-green)' }} />
              <stop offset="50%" style={{ stopColor: 'var(--color-chart-orange)' }} />
              <stop offset="100%" stopColor="#ef4444" />
            </linearGradient>
          </defs>
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-display-lg font-bold text-on-surface">{score.toFixed(0)}</span>
          <span className="font-label-mono text-[10px] text-on-surface-variant uppercase tracking-widest">/100</span>
        </div>
      </div>
      <div className="flex items-center gap-sm mt-md">
        <TrendIcon className={`w-4 h-4 ${trendColor}`} />
        <span className={`font-label-caps text-label-caps ${trendColor}`}>{trend === 'improving' ? 'Improving' : trend === 'deteriorating' ? 'Declining' : 'Stable'}</span>
      </div>
      {liveStatus && (
        <p className="text-body-sm text-on-surface-variant mt-xs">Risk: {liveStatus.riskLevel === 'high' ? 'High — Action needed' : liveStatus.riskLevel === 'moderate' ? 'Moderate — Monitor' : 'Low — On track'}</p>
      )}
    </div>
  );
}
