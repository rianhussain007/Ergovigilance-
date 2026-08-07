import React, { useState, useEffect, useMemo } from 'react';
import { Clock, AlertTriangle, CheckCircle, FileText, Download, Camera, User, Search, Filter, ArrowUpDown, Shield, Bell } from 'lucide-react';
import { EmptyState } from '@/src/components/common';
import { getAuditLog } from '@/src/services/dashboardService';
import type { AuditEntry } from '@/src/types/api';

const iconMap: Record<string, React.ElementType> = {
  session_started: User,
  session_stopped: User,
  alert_acknowledged: AlertTriangle,
  alert_resolved: CheckCircle,
  worker_created: User,
  worker_updated: User,
  worker_deleted: User,
  user_login: Shield,
  default: Bell,
};

const categoryStyles: Record<string, string> = {
  alert_acknowledged: 'border-orange-500/30 bg-orange-500/5',
  alert_resolved: 'border-green-500/30 bg-green-500/5',
  session_started: 'border-blue-500/30 bg-blue-500/5',
  session_stopped: 'border-blue-500/30 bg-blue-500/5',
  worker_created: 'border-purple-500/30 bg-purple-500/5',
  worker_updated: 'border-purple-500/30 bg-purple-500/5',
  worker_deleted: 'border-red-500/30 bg-red-500/5',
  user_login: 'border-teal-500/30 bg-teal-500/5',
  default: 'border-gray-500/30 bg-gray-500/5',
};

const categoryDots: Record<string, string> = {
  alert_acknowledged: 'bg-orange-500',
  alert_resolved: 'bg-green-500',
  session_started: 'bg-blue-500',
  session_stopped: 'bg-blue-500',
  worker_created: 'bg-purple-500',
  worker_updated: 'bg-purple-500',
  worker_deleted: 'bg-red-500',
  user_login: 'bg-teal-500',
  default: 'bg-gray-500',
};

const actionLabels: Record<string, string> = {
  alert_acknowledged: 'Alert Acknowledged',
  alert_resolved: 'Alert Resolved',
  session_started: 'Session Started',
  session_stopped: 'Session Stopped',
  worker_created: 'Worker Created',
  worker_updated: 'Worker Updated',
  worker_deleted: 'Worker Deleted',
  user_login: 'User Logged In',
};

export default function AuditTrail() {
  const [search, setSearch] = useState('');
  const [actionFilter, setActionFilter] = useState<string>('all');
  const [sortAsc, setSortAsc] = useState(false);
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;

    async function fetchData() {
      try {
        setLoading(true);
        setError(null);
        const data = await getAuditLog();
        if (mounted) {
          setEntries(data);
        }
      } catch (err) {
        if (mounted) {
          setError(err instanceof Error ? err.message : 'Failed to load audit log');
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    fetchData();
    return () => { mounted = false; };
  }, []);

  const filtered = useMemo(() => {
    let list = [...entries];
    if (actionFilter !== 'all') {
      list = list.filter(e => e.action_type === actionFilter);
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(e =>
        e.actor_email.toLowerCase().includes(q) ||
        e.action_type.toLowerCase().includes(q) ||
        (e.target_id && e.target_id.toLowerCase().includes(q)) ||
        (e.details && e.details.toLowerCase().includes(q))
      );
    }
    list.sort((a, b) => {
      const timeA = new Date(a.timestamp).getTime();
      const timeB = new Date(b.timestamp).getTime();
      return sortAsc ? timeA - timeB : timeB - timeA;
    });
    return list;
  }, [entries, actionFilter, search, sortAsc]);

  const uniqueActionTypes = useMemo(() => {
    const types = new Set(entries.map(e => e.action_type));
    return Array.from(types).sort();
  }, [entries]);

  function getEntryTitle(entry: AuditEntry) {
    const label = actionLabels[entry.action_type] || entry.action_type;
    if (entry.target_type && entry.target_id) {
      return `${label} — ${entry.target_type} ${entry.target_id}`;
    }
    return label;
  }

  function getEntryDescription(entry: AuditEntry) {
    let desc = `Performed by ${entry.actor_email} (${entry.actor_role})`;
    if (entry.details) {
      try {
        const details = JSON.parse(entry.details);
        desc += ` — ${JSON.stringify(details)}`;
      } catch {
        desc += ` — ${entry.details}`;
      }
    }
    return desc;
  }

  if (loading) {
    return (
      <div className="p-lg space-y-lg pb-32">
        <div className="space-y-sm">
          <div className="h-8 bg-surface-container-highest rounded-lg w-1/3 animate-pulse" />
          <div className="h-4 bg-surface-container-high rounded w-1/2 animate-pulse" />
        </div>
        <div className="flex items-center gap-md flex-wrap">
          <div className="h-10 bg-surface-container-highest rounded-lg flex-1 min-w-[200px] max-w-md animate-pulse" />
          <div className="h-10 bg-surface-container-highest rounded-lg w-32 animate-pulse" />
        </div>
        <div className="flex items-center gap-xs flex-wrap">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-7 bg-surface-container-highest rounded-lg w-20 animate-pulse" />
          ))}
        </div>
        <div className="space-y-sm">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="flex items-start gap-md p-md rounded-lg border border-outline-variant bg-surface-container animate-pulse">
              <div className="w-8 h-8 rounded-lg bg-surface-container-highest shrink-0" />
              <div className="flex-1 min-w-0 space-y-sm">
                <div className="flex items-center gap-sm flex-wrap">
                  <div className="h-4 bg-surface-container-highest rounded w-1/3" />
                  <div className="w-1.5 h-1.5 rounded-full bg-surface-container-highest" />
                  <div className="h-3 bg-surface-container-highest rounded w-1/6" />
                </div>
                <div className="h-4 bg-surface-container-highest rounded w-2/3" />
                <div className="flex items-center gap-md">
                  <div className="h-3 bg-surface-container-highest rounded w-1/4" />
                  <div className="h-3 bg-surface-container-highest rounded w-1/5" />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-lg">
        <EmptyState title="Failed to load audit trail" message={error} />
      </div>
    );
  }

  return (
    <div className="p-lg space-y-lg pb-32">
      <div>
        <h1 className="text-display-lg font-bold text-on-surface">Audit Trail</h1>
        <p className="text-body-sm text-on-surface-variant mt-xs">Complete event history across the system</p>
      </div>

      <div className="flex items-center gap-md flex-wrap">
        <div className="relative flex-1 min-w-[200px] max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-on-surface-variant" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search events, actors, or targets..."
            className="w-full bg-surface-container-high border border-outline-variant rounded-lg pl-10 pr-md py-sm text-body-sm text-on-surface placeholder:text-on-surface-variant outline-none focus:border-primary/50"
          />
        </div>
        <button
          onClick={() => setSortAsc(!sortAsc)}
          className="flex items-center gap-sm px-md py-sm rounded-lg border border-outline-variant text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high transition-colors text-body-sm"
        >
          <ArrowUpDown className="w-4 h-4" />
          {sortAsc ? 'Oldest first' : 'Newest first'}
        </button>
      </div>

      <div className="flex items-center gap-xs flex-wrap">
        <button
          key="all"
          onClick={() => setActionFilter('all')}
          className={`px-md py-xs rounded-lg text-[10px] font-bold uppercase tracking-widest transition-colors ${actionFilter === 'all' ? 'bg-primary text-on-primary' : 'bg-surface-container-high text-on-surface-variant hover:text-on-surface'}`}
        >
          All
        </button>
        {uniqueActionTypes.map(type => (
          <button
            key={type}
            onClick={() => setActionFilter(type)}
            className={`px-md py-xs rounded-lg text-[10px] font-bold uppercase tracking-widest transition-colors ${actionFilter === type ? 'bg-primary text-on-primary' : 'bg-surface-container-high text-on-surface-variant hover:text-on-surface'}`}
          >
            {actionLabels[type] || type}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          title="No audit events found"
          message={entries.length === 0 ? "No audit events have been recorded yet." : "Try adjusting your search or filters."}
        />
      ) : (
        <div className="space-y-sm">
          {filtered.map((entry, i) => {
            const Icon = iconMap[entry.action_type] || iconMap.default;
            const showDate = i === 0 || new Date(filtered[i - 1].timestamp).toDateString() !== new Date(entry.timestamp).toDateString();

            return (
              <div key={entry.id}>
                {showDate && (
                  <div className="flex items-center gap-md py-md">
                    <div className="h-px flex-1 bg-outline-variant/30" />
                    <span className="text-[9px] font-bold uppercase tracking-widest text-on-surface-variant">
                      {new Date(entry.timestamp).toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric', year: 'numeric' })}
                    </span>
                    <div className="h-px flex-1 bg-outline-variant/30" />
                  </div>
                )}
                <div className={`flex items-start gap-md p-md rounded-lg border ${categoryStyles[entry.action_type] || categoryStyles.default}`}>
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${categoryStyles[entry.action_type]?.replace('/5', '/15') || categoryStyles.default.replace('/5', '/15')}`}>
                    <Icon className="w-4 h-4 text-on-surface" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-sm flex-wrap">
                      <span className="text-body-sm font-bold text-on-surface">{getEntryTitle(entry)}</span>
                      <div className={`w-1.5 h-1.5 rounded-full ${categoryDots[entry.action_type] || categoryDots.default}`} />
                      <span className="text-[9px] font-bold uppercase tracking-widest text-on-surface-variant">{entry.action_type}</span>
                    </div>
                    <p className="text-body-sm text-on-surface-variant mt-0.5">{getEntryDescription(entry)}</p>
                    <div className="flex items-center gap-md mt-sm">
                      <Clock className="w-3 h-3 text-on-surface-variant" />
                      <span className="text-[10px] font-label-mono text-on-surface-variant">{new Date(entry.timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })}</span>
                      <User className="w-3 h-3 text-on-surface-variant" />
                      <span className="text-[10px] font-label-mono text-on-surface-variant">{entry.actor_email}</span>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
