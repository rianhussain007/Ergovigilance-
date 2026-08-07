import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import type { TrendDirection } from '@/src/types/api';

interface TrendCardProps {
  label: string;
  value: string | number;
  direction: TrendDirection;
}

const dirConfig = {
  improving: { icon: TrendingUp, color: 'text-green-400', bg: 'bg-green-500/10', border: 'border-green-500/30' },
  stable: { icon: Minus, color: 'text-blue-400', bg: 'bg-blue-500/10', border: 'border-blue-500/30' },
  deteriorating: { icon: TrendingDown, color: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/30' },
};

export function TrendCard({ label, value, direction }: TrendCardProps) {
  const cfg = dirConfig[direction] || dirConfig.stable;
  const Icon = cfg.icon;

  return (
    <div className={`rounded-xl p-md border ${cfg.border} ${cfg.bg}`}>
      <div className="flex items-center justify-between mb-sm">
        <span className="font-label-caps text-label-caps text-on-surface-variant uppercase tracking-widest">{label}</span>
        <Icon className={`w-5 h-5 ${cfg.color}`} />
      </div>
      <span className="text-display-lg font-bold text-on-surface">{value}</span>
    </div>
  );
}
