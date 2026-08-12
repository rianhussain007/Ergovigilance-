import React from 'react';
import { AlertTriangle, Shield, Info } from 'lucide-react';
import type { Issue } from '@/src/types/api';
import { formatISTTime } from '@/src/utils/formatTime';

interface IssueCardProps {
  issue: Issue;
}

const severityConfig = {
  high: { icon: AlertTriangle, color: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/30', badge: 'bg-red-500/20 text-red-400' },
  moderate: { icon: Shield, color: 'text-orange-400', bg: 'bg-orange-500/10', border: 'border-orange-500/30', badge: 'bg-orange-500/20 text-orange-400' },
  low: { icon: Info, color: 'text-blue-400', bg: 'bg-blue-500/10', border: 'border-blue-500/30', badge: 'bg-blue-500/20 text-blue-400' },
};

export const IssueCard: React.FC<IssueCardProps> = ({ issue }) => {
  const cfg = severityConfig[issue.severity] || severityConfig.low;
  const Icon = cfg.icon;

  const time = formatISTTime(new Date(issue.timestamp));

  return (
    <div className={`flex gap-md p-sm bg-surface-container-low border ${cfg.border} rounded-xl hover:border-opacity-60 transition-colors`}>
      <div className={`w-8 h-8 rounded-full ${cfg.bg} flex items-center justify-center shrink-0`}>
        <Icon className={`w-4 h-4 ${cfg.color}`} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-sm">
          <span className={`text-[9px] font-bold uppercase tracking-wider px-1 py-0.5 rounded ${cfg.badge}`}>{issue.severity}</span>
          <span className="font-label-mono text-[10px] text-on-surface-variant shrink-0">{time}</span>
        </div>
        <p className="text-body-sm font-medium text-on-surface mt-1">{issue.name}</p>
        <p className="text-[11px] text-on-surface-variant mt-0.5 leading-tight">{issue.detail}</p>
      </div>
    </div>
  );
}
