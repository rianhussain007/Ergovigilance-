import React, { useState, useMemo, useCallback, useEffect } from 'react';
import { 
  Bell, X, AlertTriangle, CheckCircle, Info, Search, Eye, ShieldCheck, 
  ChevronDown, ChevronUp, Clock, TrendingUp, Filter, BarChart3
} from 'lucide-react';
import { EmptyState } from '@/src/components/common';
import { useAlertsContext } from '@/src/hooks/useAlertsContext';
import { useAuth } from '@/src/auth/AuthContext';
import { apiFetch } from '@/src/services/apiClient';
import type { AlertData, AlertsHistoryResponse } from '@/src/types/api';

type NotifCategory = 'critical' | 'warning' | 'info' | 'resolved';

interface Notification {
  id: string;
  timestamp: string;
  category: NotifCategory;
  title: string;
  description: string;
  read: boolean;
  trigger_rule: string;
  severity: string;
  state: string;
  confidence: number;
  confidence_band: string;
}

// Theme-aware severity colors
const SEVERITY_CONFIG: Record<string, { 
  color: string; 
  bg: string; 
  dot: string; 
  icon: React.ElementType;
  border: string;
  pulse: boolean;
}> = {
  CRITICAL: { 
    color: 'text-red-500', 
    bg: 'bg-red-500/10', 
    dot: 'bg-red-500', 
    icon: AlertTriangle,
    border: 'border-red-500/30',
    pulse: true,
  },
  HIGH: { 
    color: 'text-orange-500', 
    bg: 'bg-orange-500/10', 
    dot: 'bg-orange-500', 
    icon: AlertTriangle,
    border: 'border-orange-500/30',
    pulse: true,
  },
  WARNING: { 
    color: 'text-yellow-500', 
    bg: 'bg-yellow-500/10', 
    dot: 'bg-yellow-500', 
    icon: AlertTriangle,
    border: 'border-yellow-500/30',
    pulse: false,
  },
  MEDIUM: { 
    color: 'text-yellow-500', 
    bg: 'bg-yellow-500/10', 
    dot: 'bg-yellow-500', 
    icon: AlertTriangle,
    border: 'border-yellow-500/30',
    pulse: false,
  },
  LOW: { 
    color: 'text-blue-500', 
    bg: 'bg-blue-500/10', 
    dot: 'bg-blue-500', 
    icon: Info,
    border: 'border-blue-500/30',
    pulse: false,
  },
};

function alertToNotification(alert: AlertData, read: boolean): Notification {
  let category: NotifCategory;
  if (alert.state === 'RESOLVED') {
    category = 'resolved';
  } else if (alert.severity === 'CRITICAL' || alert.severity === 'HIGH') {
    category = 'critical';
  } else if (alert.severity === 'WARNING' || alert.severity === 'MEDIUM') {
    category = 'warning';
  } else {
    category = 'info';
  }
  return {
    id: alert.id,
    timestamp: alert.created_at,
    category,
    title: alert.title,
    description: alert.message,
    read,
    trigger_rule: alert.trigger_rule,
    severity: alert.severity,
    state: alert.state,
    confidence: alert.confidence,
    confidence_band: alert.confidence_band || 'medium',
  };
}

function AlertStats({ alerts }: { alerts: AlertData[] }) {
  const stats = useMemo(() => {
    const now = Date.now();
    const last24h = alerts.filter(a => 
      now - new Date(a.created_at).getTime() < 24 * 60 * 60 * 1000
    );
    const bySeverity = {
      CRITICAL: last24h.filter(a => a.severity === 'CRITICAL').length,
      HIGH: last24h.filter(a => a.severity === 'HIGH').length,
      MEDIUM: last24h.filter(a => a.severity === 'MEDIUM').length,
      LOW: last24h.filter(a => a.severity === 'LOW').length,
    };
    const resolved = last24h.filter(a => a.state === 'RESOLVED').length;
    const active = last24h.filter(a => a.state === 'ACTIVE').length;
    return { total: last24h.length, bySeverity, resolved, active };
  }, [alerts]);

  return (
    <div className="grid grid-cols-4 gap-2 mb-4">
      <div className="text-center p-2 bg-surface-container-higher rounded-lg">
        <div className="text-[10px] text-on-surface-variant uppercase tracking-wider">24h</div>
        <div className="text-lg font-bold text-on-surface">{stats.total}</div>
      </div>
      <div className="text-center p-2 bg-red-500/10 rounded-lg">
        <div className="text-[10px] text-red-400 uppercase tracking-wider">Critical</div>
        <div className="text-lg font-bold text-red-400">{stats.bySeverity.CRITICAL}</div>
      </div>
      <div className="text-center p-2 bg-orange-500/10 rounded-lg">
        <div className="text-[10px] text-orange-400 uppercase tracking-wider">High</div>
        <div className="text-lg font-bold text-orange-400">{stats.bySeverity.HIGH}</div>
      </div>
      <div className="text-center p-2 bg-green-500/10 rounded-lg">
        <div className="text-[10px] text-green-400 uppercase tracking-wider">Resolved</div>
        <div className="text-lg font-bold text-green-400">{stats.resolved}</div>
      </div>
    </div>
  );
}

function AlertItem({
  alert,
  config,
  showActions,
  canAck,
  canResolve,
  loadingId,
  onAction,
  onToggleExpand,
  isExpanded,
}: {
  alert: Notification;
  config: typeof SEVERITY_CONFIG[string];
  showActions: boolean;
  canAck: boolean;
  canResolve: boolean;
  loadingId: string | null;
  onAction: (id: string, action: 'acknowledge' | 'resolve') => void;
  onToggleExpand: (id: string) => void;
  isExpanded: boolean;
}) {
  const Icon = config.icon;
  const timeAgo = getTimeAgo(alert.timestamp);

  return (
    <div className={`rounded-xl border transition-all duration-200 ${config.border} ${config.bg} ${alert.read ? 'opacity-70' : ''}`}>
      <div className="flex items-start gap-3 p-3">
        <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${config.bg}`}>
          <Icon className={`w-4 h-4 ${config.color} ${config.pulse ? 'animate-pulse' : ''}`} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <p className={`text-sm ${alert.read ? 'text-on-surface-variant' : 'text-on-surface font-medium'}`}>
                {alert.title}
              </p>
              {!alert.read && <div className={`w-2 h-2 rounded-full ${config.dot}`} />}
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[9px] text-on-surface-variant">{timeAgo}</span>
              <button
                onClick={() => onToggleExpand(alert.id)}
                className="p-1 rounded hover:bg-surface-container-higher text-on-surface-variant"
              >
                {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
              </button>
            </div>
          </div>
          
          {isExpanded && (
            <div className="mt-2 space-y-2">
              <p className="text-xs text-on-surface-variant">{alert.description}</p>
              
              <div className="flex items-center gap-4 text-[9px] text-on-surface-variant">
                <span className="flex items-center gap-1">
                  <BarChart3 className="w-3 h-3" />
                  {alert.confidence.toFixed(0)}% confidence
                </span>
                <span className={`px-1.5 py-0.5 rounded font-medium ${
                  alert.confidence_band === 'high' ? 'bg-green-500/15 text-green-400' :
                  alert.confidence_band === 'low' ? 'bg-red-500/15 text-red-400' :
                  'bg-yellow-500/15 text-yellow-400'
                }`}>
                  {alert.confidence_band === 'high' ? '● High certainty' :
                   alert.confidence_band === 'low' ? '● Low certainty' :
                   '● Medium certainty'}
                </span>
                <span className="flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {alert.trigger_rule}
                </span>
                <span className={`px-1.5 py-0.5 rounded ${config.bg} ${config.color}`}>
                  {alert.severity}
                </span>
              </div>
              
              {showActions && (
                <div className="flex gap-2 pt-1">
                  {canAck && alert.state === 'ACTIVE' && (
                    <button
                      onClick={() => onAction(alert.id, 'acknowledge')}
                      disabled={loadingId === alert.id}
                      className="flex items-center gap-1 text-[10px] bg-green-500/10 text-green-400 hover:bg-green-500/20 px-2 py-1 rounded-lg font-medium transition-colors disabled:opacity-40"
                    >
                      <Eye className="w-3 h-3" />
                      Acknowledge
                    </button>
                  )}
                  {canResolve && alert.state !== 'RESOLVED' && (
                    <button
                      onClick={() => onAction(alert.id, 'resolve')}
                      disabled={loadingId === alert.id}
                      className="flex items-center gap-1 text-[10px] bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 px-2 py-1 rounded-lg font-medium transition-colors disabled:opacity-40"
                    >
                      <ShieldCheck className="w-3 h-3" />
                      Resolve
                    </button>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function getTimeAgo(timestamp: string): string {
  const now = Date.now();
  const then = new Date(timestamp).getTime();
  const diff = now - then;
  
  if (diff < 60000) return 'Just now';
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
  return `${Math.floor(diff / 86400000)}d ago`;
}

export function AlertCenter({ onClose }: { onClose?: () => void }) {
  const { user } = useAuth();
  const { alerts, refetch } = useAlertsContext();
  const [readIds, setReadIds] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<NotifCategory | 'all'>('all');
  const [loadingId, setLoadingId] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [fullHistory, setFullHistory] = useState<AlertData[]>([]);
  const [historyPage, setHistoryPage] = useState(0);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [historyPages, setHistoryPages] = useState(0);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  const role = user?.role ?? 'operator';
  const canAck = role === 'supervisor' || role === 'safety_mgr' || role === 'admin';
  const canResolve = role === 'safety_mgr' || role === 'admin';

  const fetchMoreHistory = useCallback(async () => {
    const nextPage = historyPage + 1;
    setHistoryLoading(true);
    try {
      const res = await apiFetch(`/api/alerts/history?page=${nextPage}&limit=50`);
      if (!res.ok) throw new Error('Failed to fetch alert history');
      const data: AlertsHistoryResponse = await res.json();
      setFullHistory((prev) => [...prev, ...data.alerts]);
      setHistoryPage(nextPage);
      setHistoryTotal(data.total);
      setHistoryPages(data.pages);
    } catch {
      // silent
    } finally {
      setHistoryLoading(false);
    }
  }, [historyPage]);

  const hasMoreHistory = historyPages > 0 && historyPage < historyPages;

  const activeNotifs = useMemo(
    () => alerts.active.map((a) => alertToNotification(a, readIds.has(a.id))),
    [alerts.active, readIds],
  );

  // Merge polled history (last 20) with on-demand paginated full history, deduped by id
  const mergedHistory = useMemo(() => {
    const seen = new Set<string>();
    const all: AlertData[] = [];
    for (const a of [...alerts.history, ...fullHistory]) {
      if (!seen.has(a.id)) {
        seen.add(a.id);
        all.push(a);
      }
    }
    return all;
  }, [alerts.history, fullHistory]);

  const historyNotifs = useMemo(
    () => mergedHistory.map((a) => alertToNotification(a, readIds.has(a.id))),
    [mergedHistory, readIds],
  );

  const searchQ = search.trim().toLowerCase();

  const filteredActive = useMemo(
    () => activeNotifs.filter((n) => matchesFilter(n, filter, searchQ)).sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()),
    [activeNotifs, filter, searchQ],
  );
  const filteredHistory = useMemo(
    () => historyNotifs.filter((n) => matchesFilter(n, filter, searchQ)).sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()),
    [historyNotifs, filter, searchQ],
  );

  const allNotifs = useMemo(() => [...activeNotifs, ...historyNotifs], [activeNotifs, historyNotifs]);
  const unread = allNotifs.filter((n) => !n.read).length;
  const critical = allNotifs.filter((n) => n.category === 'critical' && !n.read).length;
  const hasAny = filteredActive.length > 0 || filteredHistory.length > 0;

  const markAllRead = () => setReadIds(new Set(allNotifs.map((n) => n.id)));

  const handleAction = useCallback(async (alertId: string, action: 'acknowledge' | 'resolve') => {
    setLoadingId(alertId);
    setErrorMsg(null);
    try {
      const res = await apiFetch(`/api/alerts/${alertId}/${action}`, { method: 'PATCH' });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `${action} failed`);
      }
      refetch();
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Action failed');
    } finally {
      setLoadingId(null);
    }
  }, [refetch]);

  const toggleExpand = useCallback((id: string) => {
    setExpandedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  return (
    <div className="flex flex-col h-full bg-surface">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-outline-variant">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
            <Bell className="w-5 h-5 text-primary" />
          </div>
          <div>
            <h3 className="text-title-md font-bold text-on-surface">Alert Center</h3>
            <p className="text-[10px] text-on-surface-variant">
              {unread > 0 ? `${unread} unread` : 'All caught up'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {unread > 0 && (
            <button onClick={markAllRead} className="text-[10px] text-primary hover:underline font-medium">
              Mark all read
            </button>
          )}
          {onClose && (
            <button onClick={onClose} className="p-2 rounded-lg hover:bg-surface-container-higher text-on-surface-variant">
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Stats */}
      <div className="px-4 pt-4">
        <AlertStats alerts={mergedHistory} />
      </div>

      {/* Search & Filters */}
      <div className="px-4 pb-3 space-y-3">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-on-surface-variant" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search alerts..."
            className="w-full bg-surface-container-high border border-outline-variant rounded-xl pl-10 pr-4 py-2.5 text-xs text-on-surface placeholder:text-on-surface-variant outline-none focus:border-primary/50 transition-colors"
          />
        </div>
        <div className="flex gap-1.5 flex-wrap">
          {[
            { label: 'All', value: 'all' },
            { label: 'Critical', value: 'critical' },
            { label: 'Warning', value: 'warning' },
            { label: 'Info', value: 'info' },
            { label: 'Resolved', value: 'resolved' },
          ].map((f) => (
            <button
              key={f.value}
              onClick={() => setFilter(f.value as NotifCategory | 'all')}
              className={`px-3 py-1.5 rounded-lg text-[10px] font-medium uppercase tracking-wider transition-all ${
                filter === f.value
                  ? 'bg-primary text-on-primary'
                  : 'bg-surface-container-high text-on-surface-variant hover:text-on-surface'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* Alert List */}
      <div className="flex-1 overflow-y-auto px-4">
        {!hasAny ? (
          <div className="flex flex-col items-center justify-center h-full text-on-surface-variant">
            <div className="w-16 h-16 rounded-full bg-green-500/10 flex items-center justify-center mb-4">
              <CheckCircle className="w-8 h-8 text-green-500" />
            </div>
            <p className="text-sm font-medium mb-1">No alerts</p>
            <p className="text-[10px] text-center">System is operating normally. Alerts will appear here when risk events are detected.</p>
          </div>
        ) : (
          <div className="space-y-3 py-2">
            {filteredActive.length > 0 && (
              <div>
                <p className="text-[9px] font-bold uppercase tracking-widest text-on-surface-variant mb-2">Active Alerts</p>
                <div className="space-y-2">
                  {filteredActive.map((alert) => (
                    <AlertItem
                      key={alert.id}
                      alert={alert}
                      config={SEVERITY_CONFIG[alert.severity] || SEVERITY_CONFIG.LOW}
                      showActions
                      canAck={canAck}
                      canResolve={canResolve}
                      loadingId={loadingId}
                      onAction={handleAction}
                      onToggleExpand={toggleExpand}
                      isExpanded={expandedIds.has(alert.id)}
                    />
                  ))}
                </div>
              </div>
            )}

            {filteredHistory.length > 0 && (
              <div>
                <p className="text-[9px] font-bold uppercase tracking-widest text-on-surface-variant mb-2">History</p>
                <div className="space-y-2">
                  {filteredHistory.map((alert) => (
                    <AlertItem
                      key={alert.id}
                      alert={alert}
                      config={SEVERITY_CONFIG[alert.severity] || SEVERITY_CONFIG.LOW}
                      showActions={false}
                      canAck={false}
                      canResolve={false}
                      loadingId={null}
                      onAction={() => {}}
                      onToggleExpand={toggleExpand}
                      isExpanded={expandedIds.has(alert.id)}
                    />
                  ))}
                </div>
                {hasMoreHistory && (
                  <div className="mt-3 text-center">
                    <button
                      onClick={fetchMoreHistory}
                      disabled={historyLoading}
                      className="inline-flex items-center gap-1 text-[10px] text-primary hover:underline disabled:opacity-40"
                    >
                      <ChevronDown className="w-3 h-3" />
                      {historyLoading ? 'Loading...' : `Load more (${historyTotal - fullHistory.length - Math.min(alerts.history.length, 20)} remaining)`}
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-outline-variant">
        {errorMsg && <p className="text-[10px] text-red-400 mb-2">{errorMsg}</p>}
        <div className="flex items-center justify-between text-[10px] text-on-surface-variant">
          <span>{allNotifs.length} total · {historyTotal > 0 ? historyTotal : alerts.summary.total_fired} history</span>
          <span className="flex items-center gap-1">
            <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
            {critical} critical
          </span>
        </div>
      </div>
    </div>
  );
}

function matchesFilter(n: Notification, filter: NotifCategory | 'all', searchQ: string): boolean {
  if (filter !== 'all' && n.category !== filter) return false;
  if (searchQ && !n.title.toLowerCase().includes(searchQ) && !n.description.toLowerCase().includes(searchQ)) return false;
  return true;
}

export default AlertCenter;
