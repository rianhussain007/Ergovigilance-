import React, { useState, useMemo, useCallback } from 'react';
import { X, Bell, AlertTriangle, Info, CheckCircle, Search, Eye, ShieldCheck, ChevronDown } from 'lucide-react';
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
}

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
  };
}

const categoryConfig: Record<NotifCategory, { color: string; bg: string; dot: string; icon: React.ElementType }> = {
  critical: { color: 'text-red-400', bg: 'bg-red-500/10', dot: 'bg-red-500', icon: AlertTriangle },
  warning: { color: 'text-orange-400', bg: 'bg-orange-500/10', dot: 'bg-orange-500', icon: AlertTriangle },
  info: { color: 'text-blue-400', bg: 'bg-blue-500/10', dot: 'bg-blue-500', icon: Info },
  resolved: { color: 'text-green-400', bg: 'bg-green-500/10', dot: 'bg-green-500', icon: CheckCircle },
};

const categoryFilters: { label: string; value: NotifCategory | 'all' }[] = [
  { label: 'All', value: 'all' }, { label: 'Critical', value: 'critical' }, { label: 'Warning', value: 'warning' }, { label: 'Info', value: 'info' }, { label: 'Resolved', value: 'resolved' },
];

function matchesFilter(n: Notification, filter: NotifCategory | 'all', searchQ: string): boolean {
  if (filter !== 'all' && n.category !== filter) return false;
  if (searchQ && !n.title.toLowerCase().includes(searchQ) && !n.description.toLowerCase().includes(searchQ)) return false;
  return true;
}

function NotificationItem({
  n,
  cfg,
  showActions,
  canAck,
  canResolve,
  loadingId,
  onAction,
}: {
  n: Notification;
  cfg: { color: string; bg: string; dot: string; icon: React.ElementType };
  showActions: boolean;
  canAck: boolean;
  canResolve: boolean;
  loadingId: string | null;
  onAction: (id: string, action: 'acknowledge' | 'resolve') => void;
}) {
  return (
    <div className={`flex items-start gap-md p-sm rounded-lg border transition-colors ${n.read ? 'border-outline-variant/30 bg-surface-container-low opacity-70' : 'border-outline-variant bg-surface-container'}`}>
      <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ${cfg.bg}`}>
        <cfg.icon className={`w-3.5 h-3.5 ${cfg.color}`} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-sm">
          <p className={`text-body-sm ${n.read ? 'text-on-surface-variant' : 'text-on-surface font-medium'}`}>{n.title}</p>
          {!n.read && <div className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />}
        </div>
        <p className="text-[10px] text-on-surface-variant mt-0.5">{n.description}</p>
        {showActions && (
          <div className="flex gap-1 mt-1">
            {canAck && (
              <button
                onClick={() => onAction(n.id, 'acknowledge')}
                disabled={loadingId === n.id}
                className="flex items-center gap-0.5 text-[9px] bg-surface-container-higher text-on-surface-variant hover:text-green-400 px-1.5 py-0.5 rounded font-bold uppercase tracking-wider transition-colors disabled:opacity-40"
              >
                <Eye className="w-2.5 h-2.5" />
                Acknowledge
              </button>
            )}
            {canResolve && (
              <button
                onClick={() => onAction(n.id, 'resolve')}
                disabled={loadingId === n.id}
                className="flex items-center gap-0.5 text-[9px] bg-surface-container-higher text-on-surface-variant hover:text-blue-400 px-1.5 py-0.5 rounded font-bold uppercase tracking-wider transition-colors disabled:opacity-40"
              >
                <ShieldCheck className="w-2.5 h-2.5" />
                Resolve
              </button>
            )}
          </div>
        )}
        <span className="text-[9px] font-label-mono text-on-surface-variant mt-1 block">{new Date(n.timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })}</span>
      </div>
    </div>
  );
}

export function NotificationCenter({ onClose }: { onClose?: () => void }) {
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

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between p-lg border-b border-outline-variant">
        <div className="flex items-center gap-md">
          <Bell className="w-5 h-5 text-on-surface" />
          <h3 className="text-title-md font-bold text-on-surface">Notifications</h3>
          {unread > 0 && <span className="text-[10px] bg-red-500/15 text-red-400 px-1.5 py-0.5 rounded-full font-bold">{unread}</span>}
        </div>
        <div className="flex items-center gap-sm">
          {unread > 0 && <button onClick={markAllRead} className="text-[10px] text-primary hover:underline">Mark all read</button>}
          {onClose && <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-surface-container-higher text-on-surface-variant"><X className="w-4 h-4" /></button>}
        </div>
      </div>

      <div className="p-lg border-b border-outline-variant space-y-sm">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-on-surface-variant" />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search notifications..." className="w-full bg-surface-container-high border border-outline-variant rounded-lg pl-9 pr-md py-sm text-[12px] text-on-surface placeholder:text-on-surface-variant outline-none focus:border-primary/50" />
        </div>
        <div className="flex gap-1 flex-wrap">
          {categoryFilters.map((f) => (
            <button key={f.value} onClick={() => setFilter(f.value)} className={`px-2 py-0.5 rounded text-[9px] font-bold uppercase tracking-widest transition-colors ${filter === f.value ? 'bg-primary text-on-primary' : 'bg-surface-container-high text-on-surface-variant hover:text-on-surface'}`}>{f.label}</button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {!hasAny ? (
          <div className="flex flex-col items-center justify-center h-full text-on-surface-variant">
            <Bell className="w-8 h-8 mb-sm opacity-40" />
            <p className="text-body-sm">No notifications</p>
          </div>
        ) : (
          <div className="p-lg space-y-md">
            {filteredActive.length === 0 ? (
              <div className="text-center py-md text-on-surface-variant">
                <p className="text-[11px] font-medium uppercase tracking-widest text-on-surface-variant/60 mb-1">Active Alerts</p>
                <p className="text-[10px]">No active alerts</p>
              </div>
            ) : (
              <div>
                <p className="text-[9px] font-bold uppercase tracking-widest text-on-surface-variant mb-2">Active Alerts</p>
                <div className="space-y-sm">
                  {filteredActive.map((n) => (
                    <NotificationItem
                      key={n.id}
                      n={n}
                      cfg={categoryConfig[n.category]}
                      showActions
                      canAck={canAck}
                      canResolve={canResolve}
                      loadingId={loadingId}
                      onAction={handleAction}
                    />
                  ))}
                </div>
              </div>
            )}

            {filteredHistory.length === 0 ? (
              <div className="text-center py-md text-on-surface-variant">
                <p className="text-[11px] font-medium uppercase tracking-widest text-on-surface-variant/60 mb-1">Past Alerts</p>
                <p className="text-[10px]">No past alerts</p>
              </div>
            ) : (
              <div>
                <p className="text-[9px] font-bold uppercase tracking-widest text-on-surface-variant mb-2">Past Alerts</p>
                <div className="space-y-sm">
                  {filteredHistory.map((n) => (
                    <NotificationItem
                      key={n.id}
                      n={n}
                      cfg={categoryConfig[n.category]}
                      showActions={false}
                      canAck={false}
                      canResolve={false}
                      loadingId={null}
                      onAction={() => {}}
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

      <div className="p-lg border-t border-outline-variant text-center space-y-1">
        {errorMsg && <p className="text-[10px] text-red-400">{errorMsg}</p>}
        <p className="text-[10px] text-on-surface-variant">{allNotifs.length} total ({historyTotal > 0 ? historyTotal : alerts.summary.total_fired} history) · {critical} critical</p>
      </div>
    </div>
  );
}
