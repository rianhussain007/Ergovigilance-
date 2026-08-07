import { Bell, X, CheckCircle, Clock, AlertTriangle, Eye } from 'lucide-react';
import { EmptyState } from '@/src/components/common';
import { useAlertsContext } from '@/src/hooks/useAlertsContext';
import type { AlertData } from '@/src/types/api';

const SEVERITY_COLORS: Record<string, string> = {
  LOW: '#22c55e',
  MEDIUM: '#f97316',
  HIGH: '#ef4444',
  CRITICAL: '#dc2626',
};

const SEVERITY_BG: Record<string, string> = {
  LOW: 'rgba(34,197,94,0.08)',
  MEDIUM: 'rgba(249,115,22,0.08)',
  HIGH: 'rgba(239,68,68,0.08)',
  CRITICAL: 'rgba(220,38,38,0.12)',
};

const SEVERITY_LABELS: Record<string, string> = {
  LOW: 'Low',
  MEDIUM: 'Medium',
  HIGH: 'High',
  CRITICAL: 'Critical',
};

function severityColor(severity: string): string {
  return SEVERITY_COLORS[severity] || '#6b7280';
}

function severityPulse(severity: string): string {
  if (severity === 'CRITICAL' || severity === 'HIGH') return 'animate-pulse';
  return '';
}

function AlertTimelineItem({ alert }: { alert: AlertData }) {
  const isAck = alert.state === 'ACKNOWLEDGED';
  const isResolved = alert.state === 'RESOLVED';

  return (
    <div className="flex items-center gap-2 text-[10px] py-0.5">
      <div
        className={`w-2 h-2 rounded-full shrink-0 ${severityPulse(alert.severity)}`}
        style={{ backgroundColor: severityColor(alert.severity) }}
      />
      <span className="text-on-surface-variant font-mono w-14 shrink-0">
        {new Date(alert.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
      </span>
      <span className="text-on-surface flex-1 truncate">{alert.title}</span>
      <span className="text-[8px] bg-surface-container-higher text-on-surface-variant px-1 rounded shrink-0 font-mono">
        {alert.trigger_rule}
      </span>
      {isAck && <Eye className="w-3 h-3 text-green-400 shrink-0" />}
      {isResolved && <CheckCircle className="w-3 h-3 text-blue-400 shrink-0" />}
    </div>
  );
}

export default function AlertManagementCard() {
  const { alerts, loading } = useAlertsContext();
  const { active, history, summary } = alerts;

  const highestSeverity = active.length > 0
    ? active.reduce((max, a) => {
        const order = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];
        return order.indexOf(a.severity) > order.indexOf(max) ? a.severity : max;
      }, active[0].severity)
    : 'NONE';

  const displaySeverity = highestSeverity === 'NONE' ? 'NONE' : highestSeverity;

  if (loading) {
    return (
      <div className="bg-surface-container border border-outline-variant rounded-xl p-lg">
        <div className="flex items-center gap-sm mb-md">
          <Bell className="w-4 h-4 text-blue-400" />
          <span className="text-label-caps text-[10px] uppercase tracking-widest text-on-surface-variant">
            Alert Management
          </span>
        </div>
        <div className="space-y-sm">
          <div className="h-4 bg-surface-container-higher rounded animate-pulse" />
          <div className="h-4 bg-surface-container-higher rounded animate-pulse w-3/4" />
        </div>
      </div>
    );
  }

  return (
    <div className="bg-surface-container border border-outline-variant rounded-xl p-lg space-y-md">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-sm">
          <Bell className={`w-4 h-4 ${severityPulse(displaySeverity)}`} style={{ color: severityColor(displaySeverity) }} />
          <span className="text-label-caps text-[10px] uppercase tracking-widest text-on-surface-variant">
            Alert Management
          </span>
        </div>
        <span className="text-[9px] bg-surface-container-higher text-on-surface-variant px-2 py-0.5 rounded-full font-mono">
          {summary.total_fired}
        </span>
      </div>

      <div
        className="rounded-lg px-md py-sm text-center border transition-all duration-500"
        style={{
          backgroundColor: SEVERITY_BG[displaySeverity] || 'rgba(107,114,128,0.08)',
          borderColor: `${severityColor(displaySeverity)}40`,
        }}
      >
        <div className="flex items-center justify-center gap-2">
          {displaySeverity !== 'NONE' && (
            <AlertTriangle className={`w-4 h-4 ${severityPulse(displaySeverity)}`} style={{ color: severityColor(displaySeverity) }} />
          )}
          <span className="font-bold text-sm tracking-wider" style={{ color: severityColor(displaySeverity) }}>
            {SEVERITY_LABELS[displaySeverity] || 'None'}
          </span>
          <span className="text-[10px] text-on-surface-variant">CURRENT LEVEL</span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-x-md gap-y-sm">
        <div>
          <span className="text-[10px] text-on-surface-variant uppercase tracking-wider">Active Alerts</span>
          <p className="text-body-sm text-on-surface font-mono mt-0.5">{summary.active_count}</p>
        </div>
        <div>
          <span className="text-[10px] text-on-surface-variant uppercase tracking-wider">Critical</span>
          <p className="text-body-sm text-on-surface font-mono mt-0.5">{summary.critical_count}</p>
        </div>
        <div>
          <span className="text-[10px] text-on-surface-variant uppercase tracking-wider">Acknowledged</span>
          <p className="text-body-sm text-on-surface font-mono mt-0.5">{summary.acknowledged_count}</p>
        </div>
        <div>
          <span className="text-[10px] text-on-surface-variant uppercase tracking-wider">Consecutive HIGH</span>
          <p className="text-body-sm text-on-surface font-mono mt-0.5">{summary.consecutive_high}</p>
        </div>
      </div>

      {active.length > 0 && (
        <div className="border-t border-outline-variant/30 pt-sm">
          <span className="text-[9px] uppercase tracking-widest text-on-surface-variant font-bold block mb-2">Active Alerts</span>
          <div className="space-y-1 max-h-32 overflow-y-auto">
            {active.map((alert) => (
              <AlertTimelineItem key={alert.id} alert={alert} />
            ))}
          </div>
        </div>
      )}

      {history.length > 0 && (
        <div className="border-t border-outline-variant/30 pt-sm">
          <span className="text-[9px] uppercase tracking-widest text-on-surface-variant font-bold block mb-2">Alert History</span>
          <div className="space-y-1 max-h-32 overflow-y-auto">
            {history.slice(-10).reverse().map((alert) => (
              <AlertTimelineItem key={alert.id} alert={alert} />
            ))}
          </div>
        </div>
      )}

      {active.length === 0 && history.length === 0 && (
        <EmptyState
          title="No active alerts"
          message="Alerts will appear here when the Alert Engine detects risk events."
        />
      )}
    </div>
  );
}
