import { X, AlertTriangle, TrendingUp, RefreshCw } from 'lucide-react';
import type { Issue, RiskLevel } from '@/src/types/api';

type AlertSeverity = RiskLevel;

interface LiveAlertsProps {
  issues: Issue[];
  onClose: () => void;
}

const severityConfig = {
  high: { color: 'bg-red-500/10 border-red-500/30 text-red-400', dot: 'bg-red-500' },
  moderate: { color: 'bg-orange-500/10 border-orange-500/30 text-orange-400', dot: 'bg-orange-500' },
  low: { color: 'bg-blue-500/10 border-blue-500/30 text-blue-400', dot: 'bg-blue-500' },
};

export function LiveAlerts({ issues, onClose }: LiveAlertsProps) {
  const sorted = [...issues].sort((a, b) => {
    const order = { high: 0, moderate: 1, low: 2 };
    return (order[a.severity] ?? 2) - (order[b.severity] ?? 2);
  });

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between p-lg border-b border-outline-variant">
        <div className="flex items-center gap-md">
          <AlertTriangle className="w-5 h-5 text-orange-400" />
          <h3 className="text-title-md font-bold text-on-surface">Live Alerts</h3>
          <span className="text-[10px] bg-red-500/15 text-red-400 px-2 py-0.5 rounded-full font-bold">
            {issues.filter((i) => i.severity === 'high').length}
          </span>
        </div>
        <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-surface-container-higher text-on-surface-variant transition-colors">
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {sorted.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-on-surface-variant">
            <TrendingUp className="w-8 h-8 mb-sm opacity-40" />
            <p className="text-body-sm">No active alerts</p>
          </div>
        ) : (
          <div className="p-lg space-y-sm">
            {sorted.map((issue) => {
              const cfg = severityConfig[issue.severity];
              return (
                <div key={issue.id} className={`flex items-start gap-md p-sm rounded-lg border ${cfg.color}`}>
                  <div className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${cfg.dot}`} />
                  <div className="min-w-0">
                    <div className="flex items-center gap-sm">
                      <p className="text-body-sm font-medium text-on-surface">{issue.name}</p>
                      {issue.severity === 'high' && <RefreshCw className="w-3 h-3 text-red-400 animate-spin" />}
                    </div>
                    <p className="text-[10px] text-on-surface-variant mt-0.5">{issue.detail}</p>
                    <p className="text-[9px] text-on-surface-variant mt-1 opacity-60">
                      {new Date(issue.timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="p-lg border-t border-outline-variant text-center">
        <p className="text-[10px] text-on-surface-variant">{issues.length} alert{issues.length !== 1 ? 's' : ''} in the last 24h</p>
      </div>
    </div>
  );
}
