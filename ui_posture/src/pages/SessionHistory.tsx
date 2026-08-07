import { useState, useMemo, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router';
import { Search, ArrowUpDown, AlertTriangle, CheckCircle, XCircle, Clock, ExternalLink, ChevronDown } from 'lucide-react';
import type { StatusType, SessionDetail, SessionAlertEntry, SessionRecord } from '@/src/types/api';
import { useDemo } from '@/src/demo/DemoProvider';
import { getSessionDetail, getSessions } from '@/src/services/dashboardService';
import { StatusBadge, LoadingCard, ErrorCard, EmptyState, SectionHeader } from '@/src/components/common';
import { Drawer } from '@/src/components/common/Drawer';

type SortKey = 'date' | 'duration' | 'task';

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

function severityColor(sev: string): string {
  if (sev === 'HIGH' || sev === 'CRITICAL') return 'bg-red-500/20 text-red-400';
  if (sev === 'MEDIUM') return 'bg-orange-500/20 text-orange-400';
  return 'bg-green-500/20 text-green-400';
}

function severityIcon(sev: string) {
  if (sev === 'HIGH' || sev === 'CRITICAL') return <AlertTriangle className="w-4 h-4 text-red-400" />;
  if (sev === 'MEDIUM') return <Clock className="w-4 h-4 text-orange-400" />;
  return <CheckCircle className="w-4 h-4 text-green-400" />;
}

function AlertTimeline({ alerts }: { alerts: SessionAlertEntry[] }) {
  if (!alerts || alerts.length === 0) {
    return (
      <div className="bg-surface-container-low border border-outline-variant rounded-lg p-lg text-center">
        <p className="text-body-sm text-on-surface-variant">No alert data recorded for this session.</p>
        <p className="text-[11px] text-outline mt-xs">Older sessions may not have been saved with alert information.</p>
      </div>
    );
  }

  return (
    <div className="space-y-sm">
      {alerts.map((a) => (
        <div key={a.id} className="flex items-start gap-md p-md bg-surface-container-low border border-outline-variant/50 rounded-lg">
          <div className="mt-0.5 shrink-0">{severityIcon(a.severity)}</div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-sm flex-wrap">
              <span className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded ${severityColor(a.severity)}`}>{a.severity}</span>
              <span className="text-body-sm font-medium text-on-surface">{a.title}</span>
            </div>
            <p className="text-[11px] text-on-surface-variant mt-1">{a.message}</p>
            <div className="flex items-center gap-md mt-1 text-[10px] text-outline">
              <span>{a.created_at ? new Date(a.created_at).toLocaleTimeString() : 'N/A'}</span>
              <span>Frame {a.frame_number}</span>
              <span>Rule: {a.trigger_rule}</span>
              <span>Confidence: {(a.confidence * 100).toFixed(0)}%</span>
            </div>
          </div>
          <div className="shrink-0">
            <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${a.state === 'RESOLVED' ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'}`}>{a.state}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function RiskBar({ label, pct, color }: { label: string; pct: number; color: string }) {
  return (
    <div className="flex items-center gap-md">
      <span className="text-body-sm text-on-surface-variant w-20 shrink-0">{label}</span>
      <div className="flex-1 h-3 bg-surface-container-highest rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="font-label-mono text-label-mono text-on-surface w-12 text-right">{pct.toFixed(1)}%</span>
    </div>
  );
}

export default function SessionHistory() {
  const navigate = useNavigate();
  const { state: demoState } = useDemo();
  const [allSessions, setAllSessions] = useState<SessionRecord[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const [sessionsError, setSessionsError] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusType | 'all'>('all');
  const [sortKey, setSortKey] = useState<SortKey>('date');
  const [sortAsc, setSortAsc] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  const isDemo = demoState?.active === true;

  // Initial fetch: demo mode gets all sessions from demo state, real mode fetches page 1
  useEffect(() => {
    if (isDemo) {
      setAllSessions(demoState.sessions || []);
      setTotalPages(1);
      setSessionsLoading(false);
      return;
    }
    let cancelled = false;
    setSessionsLoading(true);
    setSessionsError(null);
    getSessions(1, 25)
      .then((resp) => {
        if (cancelled) return;
        setAllSessions(resp.sessions);
        setPage(resp.page);
        setTotalPages(resp.pages);
      })
      .catch((e) => {
        if (cancelled) return;
        setSessionsError(e?.message || 'Failed to load sessions');
      })
      .finally(() => {
        if (!cancelled) setSessionsLoading(false);
      });
    return () => { cancelled = true; };
  }, [isDemo]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadMore = useCallback(async () => {
    if (loadingMore || page >= totalPages || isDemo) return;
    setLoadingMore(true);
    try {
      const resp = await getSessions(page + 1, 25);
      setAllSessions((prev) => [...prev, ...resp.sessions]);
      setPage(resp.page);
      setTotalPages(resp.pages);
    } catch {
      // silent
    } finally {
      setLoadingMore(false);
    }
  }, [loadingMore, page, totalPages, isDemo]);

  const fetchDetail = useCallback(async (id: string) => {
    setDetailLoading(true);
    setDetailError(null);
    setDetail(null);
    try {
      const d = await getSessionDetail(id);
      setDetail(d);
    } catch (e: any) {
      setDetailError(e?.message || 'Failed to load session detail');
    } finally {
      setDetailLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedId) fetchDetail(selectedId);
  }, [selectedId, fetchDetail]);

  const filtered = useMemo(() => {
    let list = allSessions.filter((s) => {
      if (statusFilter !== 'all' && s.status !== statusFilter) return false;
      if (search.trim() && !s.id.toLowerCase().includes(search.toLowerCase()) && !s.task.toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    });
    list.sort((a, b) => {
      let cmp = 0;
      if (sortKey === 'date') cmp = new Date(b.date).getTime() - new Date(a.date).getTime();
      else if (sortKey === 'duration') cmp = b.duration.localeCompare(a.duration);
      else cmp = a.task.localeCompare(b.task);
      return sortAsc ? -cmp : cmp;
    });
    return list;
  }, [allSessions, search, statusFilter, sortKey, sortAsc]);

  if (sessionsError) return <div className="flex items-center justify-center h-full p-lg"><ErrorCard message={sessionsError} onRetry={() => window.location.reload()} /></div>;

  return (
    <div className="p-lg space-y-lg pb-32">
      <div>
        <h1 className="text-display-lg font-bold text-on-surface">Session History</h1>
        <p className="text-body-sm text-on-surface-variant mt-xs">Browse, search, and review past monitoring sessions</p>
      </div>

      <div className="flex flex-wrap items-center gap-md">
        <div className="flex items-center gap-md flex-1 min-w-[200px] max-w-sm bg-surface-container border border-outline-variant rounded-lg px-md py-sm">
          <Search className="w-4 h-5 text-on-surface-variant shrink-0" />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search by ID or task..." className="flex-1 bg-transparent text-body-sm text-on-surface placeholder:text-outline focus:outline-none" />
        </div>
        <div className="flex items-center gap-sm bg-surface-container border border-outline-variant rounded-lg p-xs">
          {(['all', 'active', 'completed', 'interrupted'] as const).map((s) => (
            <button key={s} onClick={() => setStatusFilter(s)} className={`px-md py-sm rounded text-[11px] font-bold uppercase tracking-wider transition-colors ${statusFilter === s ? 'bg-primary text-on-primary' : 'text-on-surface-variant hover:text-on-surface'}`}>{s}</button>
          ))}
        </div>
        <button onClick={() => { setSortAsc(!sortAsc); }} className="flex items-center gap-sm px-md py-sm bg-surface-container border border-outline-variant rounded-lg text-body-sm text-on-surface-variant hover:text-on-surface transition-colors">
          <ArrowUpDown className="w-4 h-4" /> {sortAsc ? 'Asc' : 'Desc'}
        </button>
      </div>

      {sessionsLoading ? (
        <div className="space-y-md"><LoadingCard /><LoadingCard /><LoadingCard /></div>
      ) : filtered.length === 0 ? (
        <EmptyState title="No sessions found" message="Try adjusting your search or filters." />
      ) : (
        <div>
          <div className="bg-surface-container border border-outline-variant rounded-xl overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-outline-variant">
                    {(['Session ID', 'Date', 'Duration', 'Highest Risk', 'Task', 'Status', ''] as const).map((h) => (
                      <th key={h} className="font-label-caps text-[10px] text-on-surface-variant uppercase tracking-widest px-lg py-md">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((s) => (
                    <tr key={s.id} onClick={() => setSelectedId(s.id)} className="border-b border-outline-variant/50 hover:bg-surface-container-low transition-colors cursor-pointer">
                      <td className="px-lg py-md"><span className="font-label-mono text-label-mono text-primary">{s.id}</span></td>
                      <td className="px-lg py-md text-body-sm text-on-surface">{new Date(s.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</td>
                      <td className="px-lg py-md text-body-sm text-on-surface">{s.duration}</td>
                      <td className="px-lg py-md"><span className="text-body-sm font-medium" style={{ color: s.highestRisk === 'Neck Flexion' || s.highestRisk === 'Trunk Flexion' ? '#f97316' : '#60a5fa' }}>{s.highestRisk}</span></td>
                      <td className="px-lg py-md text-body-sm text-on-surface">{s.task}</td>
                      <td className="px-lg py-md"><StatusBadge status={s.status as StatusType} /></td>
                      <td className="px-lg py-md">
                        {s.status === 'completed' || s.status === 'interrupted' ? (
                          <button
                            className="text-[11px] text-primary hover:text-primary/80 transition-colors"
                            onClick={(e) => { e.stopPropagation(); navigate(`/replay/${s.id}`); }}
                          >
                            Replay
                          </button>
                        ) : (
                          <span className="text-[11px] text-outline">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          {!isDemo && page < totalPages && (
            <div className="flex justify-center pt-lg">
              <button
                onClick={loadMore}
                disabled={loadingMore}
                className="flex items-center gap-sm px-lg py-md bg-surface-container border border-outline-variant rounded-lg text-body-sm text-on-surface hover:bg-surface-container-low transition-colors disabled:opacity-60"
              >
                {loadingMore ? (
                  <span className="w-4 h-4 border-2 border-outline border-t-primary rounded-full animate-spin" />
                ) : (
                  <ChevronDown className="w-4 h-4" />
                )}
                {loadingMore ? 'Loading...' : `Load more (page ${page}/${totalPages}, ${allSessions.length} loaded)`}
              </button>
            </div>
          )}
        </div>
      )}

      <Drawer open={!!selectedId} onClose={() => { setSelectedId(null); setDetail(null); }} title={detail?.id || selectedId || 'Session Details'}>
        {detailLoading && (
          <div className="space-y-md"><LoadingCard /><LoadingCard /></div>
        )}
        {detailError && (
          <ErrorCard message={detailError} />
        )}
        {detail && !detailLoading && (
          <div className="space-y-lg">
            {/* Metadata */}
            <div>
              <SectionHeader title="Session Metadata" />
              <div className="grid grid-cols-2 gap-md mt-md">
                <div className="bg-surface-container-low border border-outline-variant rounded-lg p-md">
                  <p className="text-[10px] font-bold uppercase text-on-surface-variant tracking-wider">Timestamp</p>
                  <p className="text-body-sm text-on-surface mt-xs">{detail.session_timestamp}</p>
                </div>
                <div className="bg-surface-container-low border border-outline-variant rounded-lg p-md">
                  <p className="text-[10px] font-bold uppercase text-on-surface-variant tracking-wider">Duration</p>
                  <p className="text-body-sm text-on-surface mt-xs">{formatDuration(detail.session_duration_seconds)}</p>
                </div>
                <div className="bg-surface-container-low border border-outline-variant rounded-lg p-md">
                  <p className="text-[10px] font-bold uppercase text-on-surface-variant tracking-wider">Total Frames</p>
                  <p className="text-body-sm text-on-surface mt-xs">{detail.total_frames.toLocaleString()}</p>
                </div>
                <div className="bg-surface-container-low border border-outline-variant rounded-lg p-md">
                  <p className="text-[10px] font-bold uppercase text-on-surface-variant tracking-wider">Highest Risk</p>
                  <p className={`text-body-sm font-medium mt-xs ${detail.highest_risk_level === 'HIGH' ? 'text-red-400' : detail.highest_risk_level === 'MEDIUM' ? 'text-orange-400' : 'text-green-400'}`}>{detail.highest_risk_level}</p>
                  {detail.highest_risk_timestamp && <p className="text-[10px] text-outline mt-0.5">at {detail.highest_risk_timestamp}</p>}
                </div>
              </div>
              {(detail.status === 'completed' || detail.status === 'interrupted') && (
                <button
                  className="mt-md w-full rounded-lg bg-primary px-md py-sm text-body-sm font-semibold text-on-primary hover:bg-primary/90 transition-colors disabled:opacity-50"
                  onClick={() => navigate(`/replay/${detail.id}`)}
                >
                  <ExternalLink className="w-4 h-4 inline mr-1" />
                  Open in Replay
                </button>
              )}
            </div>

            {/* Risk Breakdown */}
            <div>
              <SectionHeader title="Risk Breakdown" />
              <div className="bg-surface-container-low border border-outline-variant rounded-lg p-md mt-md space-y-sm">
                <RiskBar label="LOW" pct={detail.risk_percentages?.LOW || 0} color="bg-green-500" />
                <RiskBar label="MEDIUM" pct={detail.risk_percentages?.MEDIUM || 0} color="bg-orange-500" />
                <RiskBar label="HIGH" pct={detail.risk_percentages?.HIGH || 0} color="bg-red-500" />
              </div>
            </div>

            {/* Average Features */}
            <div>
              <SectionHeader title="Average Feature Values" />
              <div className="grid grid-cols-2 gap-md mt-md">
                {[
                  { label: 'Neck Flexion', value: detail.avg_neck_flexion, unit: '°' },
                  { label: 'Trunk Flexion', value: detail.avg_trunk_flexion, unit: '°' },
                  { label: 'Shoulder Symmetry', value: detail.avg_shoulder_symmetry, unit: '%' },
                  { label: 'Knee Angle', value: detail.avg_knee_angle, unit: '°' },
                ].map((f) => (
                  <div key={f.label} className="bg-surface-container-low border border-outline-variant rounded-lg p-md">
                    <p className="text-[10px] font-bold uppercase text-on-surface-variant tracking-wider">{f.label}</p>
                    <p className="text-body-lg font-medium text-on-surface mt-xs">{f.value != null ? f.value.toFixed(2) : '—'}{f.unit}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Most Frequent Issue */}
            {detail.most_frequent_issue && (
              <div>
                <SectionHeader title="Most Frequent Issue" />
                <div className="bg-surface-container-low border border-outline-variant rounded-lg p-md mt-md">
                  <p className="text-body-sm font-medium text-on-surface">{detail.most_frequent_issue}</p>
                  <p className="text-[11px] text-on-surface-variant mt-xs">{detail.most_frequent_issue_count} occurrences</p>
                </div>
              </div>
            )}

            {/* Alert Timeline */}
            <div>
              <SectionHeader title="Alert Timeline" />
              <div className="mt-md">
                <AlertTimeline alerts={detail.alerts} />
              </div>
            </div>
          </div>
        )}
      </Drawer>
    </div>
  );
}
