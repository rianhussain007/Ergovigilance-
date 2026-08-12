import { Shield, AlertTriangle, CheckCircle } from 'lucide-react';
import type { RiskLevel } from '@/src/types/api';

interface StatusCardProps {
  riskLevel: RiskLevel;
  riskScore: number;
  confidence: number;
  currentTask: string;
  workerStatus: string;
}

const statusConfig: Record<RiskLevel, { color: string; bg: string; border: string; icon: typeof Shield; label: string }> = {
  low: { color: 'text-green-400', bg: 'bg-green-500/10', border: 'border-green-500/30', icon: CheckCircle, label: 'Low Risk' },
  moderate: { color: 'text-orange-400', bg: 'bg-orange-500/10', border: 'border-orange-500/30', icon: Shield, label: 'Moderate Risk' },
  high: { color: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/30', icon: AlertTriangle, label: 'High Risk' },
};

export function StatusCard({ riskLevel, riskScore, confidence, currentTask, workerStatus }: StatusCardProps) {
  const cfg = statusConfig[riskLevel] || statusConfig.moderate;
  const Icon = cfg.icon;

  const gaugeColor = riskLevel === 'high' ? 'stroke-red-500' : riskLevel === 'moderate' ? 'stroke-orange-500' : 'stroke-green-500';
  const gaugeOffset = 364 - (riskScore / 100) * 364;

  return (
    <div className={`bg-surface-container border ${cfg.border} rounded-xl p-lg flex flex-col`}>
      <div className="flex items-center justify-between mb-md">
        <span className="font-label-caps text-label-caps text-on-surface-variant uppercase tracking-widest">Live Status</span>
        <span className={`flex items-center gap-xs px-sm py-0.5 rounded-full text-[10px] font-bold ${cfg.bg} ${cfg.color}`}>
          <span className={`w-1.5 h-1.5 rounded-full ${cfg.color.replace('text-', 'bg-')}`}></span>
          {workerStatus === 'active' ? 'Active' : 'Idle'}
        </span>
      </div>

      <div className="flex items-center gap-lg">
        <div className="relative w-28 h-28 flex items-center justify-center shrink-0">
          <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
            <circle cx="50" cy="50" r="42" fill="none" stroke="var(--color-outline-variant)" strokeWidth="8" />
            <circle cx="50" cy="50" r="42" fill="none" className={gaugeColor} strokeWidth="8" strokeLinecap="round"
              strokeDasharray="264" strokeDashoffset={gaugeOffset} style={{ transition: 'stroke-dashoffset 0.8s ease' }} />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <Icon className={`w-5 h-5 ${cfg.color}`} />
            <span className={`text-headline-md font-bold ${cfg.color}`}>{riskScore}</span>
          </div>
        </div>

        <div className="flex-1 min-w-0 space-y-1">
          <p className="font-label-caps text-label-caps text-on-surface-variant uppercase tracking-widest">Risk Level</p>
          <p className={`text-headline-md font-bold ${cfg.color}`}>{cfg.label}</p>
          <div className="flex items-center gap-sm text-body-sm text-on-surface-variant">
            <span>Confidence:</span>
            <span className="font-label-mono text-primary">{confidence.toFixed(1)}%</span>
          </div>
        </div>
      </div>

      <div className="mt-md pt-md border-t border-outline-variant/50 space-y-1">
        <p className="text-body-sm text-on-surface-variant">
          <span className="font-bold text-on-surface">Task:</span> {currentTask}
        </p>
      </div>
    </div>
  );
}
