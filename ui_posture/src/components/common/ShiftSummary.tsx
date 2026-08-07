import { Clock, TrendingUp, TrendingDown, AlertTriangle, CheckCircle, Coffee } from 'lucide-react';
import type { SessionAnalytics, TrendAnalysis } from '@/src/types/api';

interface ShiftSummaryProps {
  analytics: SessionAnalytics | null;
  trend: TrendAnalysis | null;
}

export function ShiftSummary({ analytics, trend }: ShiftSummaryProps) {
  const correct = trend ? Math.min(100, 70 + trend.improving * 0.5) : 78;
  const incorrect = 100 - correct;
  const suggestions = Math.floor((correct / 100) * 8 + 2);

  return (
    <div className="bg-surface-container border border-outline-variant rounded-xl p-lg space-y-md">
      <h3 className="font-label-caps text-label-caps text-on-surface uppercase tracking-widest">Shift Summary</h3>
      <Row icon={Clock} label="Total Monitoring" value={analytics?.sessionDuration || '—'} />
      <Row icon={TrendingUp} label="Correct Posture" value={`${correct.toFixed(0)}%`} color="text-green-400" />
      <Row icon={TrendingDown} label="Incorrect Posture" value={`${incorrect.toFixed(0)}%`} color="text-red-400" />
      <Row icon={AlertTriangle} label="Highest Risk" value={analytics?.highestRisk || '—'} color="text-orange-400" />
      <Row icon={CheckCircle} label="Corrections Made" value={String(trend?.improving || 0)} color="text-primary" />
      <Row icon={Coffee} label="Break Suggestions" value={String(suggestions)} />
    </div>
  );
}

function Row({ icon: Icon, label, value, color }: { icon: typeof Clock; label: string; value: string; color?: string }) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-sm">
        <Icon className="w-4 h-4 text-on-surface-variant shrink-0" />
        <span className="text-body-sm text-on-surface-variant">{label}</span>
      </div>
      <span className={`font-label-mono text-label-mono font-bold ${color || 'text-on-surface'}`}>{value}</span>
    </div>
  );
}
