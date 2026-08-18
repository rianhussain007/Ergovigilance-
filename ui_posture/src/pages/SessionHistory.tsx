import { useState, useMemo, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router';
import { Search, AlertTriangle, CheckCircle, XCircle, Clock, ExternalLink, RotateCcw, FileDown } from 'lucide-react';
import { getStoredToken } from '@/src/auth/AuthContext';
import type { StatusType, SessionDetail, SessionAlertEntry, SessionRecord } from '@/src/types/api';
import { getSessionDetail, getSessions } from '@/src/services/dashboardService';
import { StatusBadge, LoadingCard, ErrorCard, EmptyState, SectionHeader } from '@/src/components/common';
import { Drawer } from '@/src/components/common/Drawer';
import SessionCalendar, { parseSessionTimestamp, toDateKey } from '@/src/components/common/SessionCalendar';
import { normalizeSessionId } from '@/src/utils/sessionId';
import { formatISTSessionLabel, formatISTTime } from '@/src/utils/formatTime';

type SortKey = 'date' | 'duration' | 'task';

const PAGE_SIZE = 20;

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

/** Human-readable session label in IST — the raw ID stays on hover. */
function formatSessionLabel(date: string, rawId: string): string {
  const d = parseSessionTimestamp(date);
  if (d && !Number.isNaN(d.getTime())) {
    return formatISTSessionLabel(d);
  }
  return rawId;
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
              <span>{a.created_at ? formatISTTime(new Date(a.created_at)) : 'N/A'}</span>
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

// Download the incident evidence package (zip: session + timeline + alerts +
// video) for OSHA / insurance / workers'-comp review.
async function downloadEvidence(sessionId: string) {
  try {
    const token = getStoredToken();
    const res = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/evidence`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error(`Evidence package failed (${res.status})`);
    const blob = await res.blob();
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `evidence_${sessionId}.zip`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(link.href);
  } catch (err) {
    console.error('Evidence download failed:', err);
    alert(err instanceof Error ? err.message : 'Could not download the evidence package.');
  }
}

export default function SessionHistory() {
  const navigate = useNavigate();
  const [allSessions, setAllSessions] = useState<SessionRecord[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const [sessionsError, setSessionsError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusType | 'all'>('all');
  const [workerFilter, setWorkerFilter] = useState('');
  const [riskFilter, setRiskFilter] = useState('');
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>('date');
  const [sortAsc, setSortAsc] = useState(false);
  const [page, setPage] = useState(1);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  // Fetch the FULL session list (loop pages) so the calendar + filters work
  // over every session, not just the first page. The backend serves each page
  // from a cached full scan, so this is a few fast requests.
  useEffect(() => {
    let cancelled = false;
    setSessionsLoading(true);
    setSessionsError(null);
    (async () => {
      const all: SessionRecord[] = [];
      let page = 1;
      let total = Infinity;
      while (all.length < total && page <= 50) {
        const resp = await getSessions(page, 200);
        if (cancelled) return;
        all.push(...resp.sessions);
        total = resp.total;
        page += 1;
      }
      if (!cancelled) setAllSessions(all);
    })().catch((e) => {
      if (cancelled) return;
      setSessionsError(e?.message || 'Failed to load sessions');
    }).finally(() => {
      if (!cancelled) setSessionsLoading(false);
    });
    return () => { cancelled = true; };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

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

  const workerOptions = useMemo(() => {
    const set = new Set<string>();
    for (const s of allSessions) if (s.worker_id) set.add(s.worker_id);
    return [...set].sort();
  }, [allSessions]);

  // Display the DOMINANT risk level (plurality of frames) — a session that
  // was 98% MEDIUM with one stray HIGH frame should not render as red. Falls
  // back to the peak (highest_risk_level) for records predating the field.
  const sessionRiskLevel = useCallback((s: SessionRecord): string => {
    const dom = (s.risk_level || '').toUpperCase();
    if (dom === 'HIGH' || dom === 'MEDIUM' || dom === 'LOW') return dom;
    const rl = (s.highest_risk_level || '').toUpperCase();
    if (rl === 'HIGH' || rl === 'MEDIUM' || rl === 'LOW') return rl;
    const hr = (s.highestRisk || '').toLowerCase();
    if (hr.includes('high')) return 'HIGH';
    if (hr.includes('medium') || hr.includes('moderate')) return 'MEDIUM';
    if (hr.includes('low')) return 'LOW';
    return 'LOW';
  }, []);

  // Reset to the first page whenever filters/sort change the visible set.
  useEffect(() => { setPage(1); }, [search, statusFilter, workerFilter, riskFilter, selectedDate, sortKey, sortAsc]);

  const hasActiveFilters =
    workerFilter !== '' || riskFilter !== '' || selectedDate !== null || statusFilter !== 'all' || search.trim() !== '';

  const clearFilters = useCallback(() => {
    setSearch('');
    setStatusFilter('all');
    setWorkerFilter('');
    setRiskFilter('');
    setSelectedDate(null);
  }, []);

  const filtered = useMemo(() => {
    let list = allSessions.filter((s) => {
      if (statusFilter !== 'all' && s.status !== statusFilter) return false;
      if (workerFilter && s.worker_id !== workerFilter) return false;
      if (riskFilter && sessionRiskLevel(s) !== riskFilter) return false;
      if (selectedDate) {
        const d = parseSessionTimestamp(s.date);
        if (!d || toDateKey(d) !== selectedDate) return false;
      }
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
  }, [allSessions, search, statusFilter, workerFilter, riskFilter, selectedDate, sortKey, sortAsc, sessionRiskLevel]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount);
  const paged = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);
  const shownStart = filtered.length === 0 ? 0 : (safePage - 1) * PAGE_SIZE + 1;
  const shownEnd = Math.min(safePage * PAGE_SIZE, filtered.length);

  if (sessionsError) return <div className="flex items-center justify-center h-full p-lg"><ErrorCard message={sessionsError} onRetry={() => window.location.reload()} /></div>;

  return (
    <div className="p-lg space-y-lg pb-32">
      {/* Two-column top: LEFT = title + filters (fills the space beside the
          calendar), RIGHT = work calendar. This removes the dead gap that
          appeared when the title row and the filter row were stacked. */}
      <div className="flex flex-wrap items-start justify-between gap-lg">
        <div className="flex-1 min-w-0 space-y-lg">
          <div>
            <h1 className="text-display-lg font-bold text-on-surface">Session History</h1>
            <p className="text-body-sm text-on-surface-variant mt-xs">Browse, search, and review past monitoring sessions</p>
          </div>

          <div className="flex flex-wrap items-center gap-md">
            <div className="flex items-center gap-md flex-1 min-w-[200px] max-w-[24rem] bg-surface-container border border-outline-variant rounded-lg px-md py-sm">
              <Search className="w-4 h-5 text-on-surface-variant shrink-0" />
              <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search by ID or task..." className="flex-1 bg-transparent text-body-sm text-on-surface placeholder:text-outline focus:outline-none" />
            </div>
            <div className="flex items-center gap-sm bg-surface-container border border-outline-variant rounded-lg p-xs">
              {(['all', 'active', 'completed', 'interrupted'] as const).map((s) => (
                <button key={s} onClick={() => setStatusFilter(s)} className={`px-md py-sm rounded text-[11px] font-bold uppercase tracking-wider transition-colors ${statusFilter === s ? 'bg-primary text-on-primary' : 'text-on-surface-variant hover:text-on-surface'}`}>{s}</button>
              ))}
            </div>
            <select
              value={workerFilter}
              onChange={(e) => setWorkerFilter(e.target.value)}
              className="px-md py-sm bg-surface-container border border-outline-variant rounded-lg text-body-sm text-on-surface focus:outline-none"
            >
              <option value="">All workers</option>
              {workerOptions.map((w) => (
                <option key={w} value={w}>{w}</option>
              ))}
            </select>
            <select
              value={riskFilter}
              onChange={(e) => setRiskFilter(e.target.value)}
              className="px-md py-sm bg-surface-container border border-outline-variant rounded-lg text-body-sm text-on-surface focus:outline-none"
            >
              <option value="">Any risk</option>
              <option value="LOW">LOW</option>
              <option value="MEDIUM">MEDIUM</option>
              <option value="HIGH">HIGH</option>
            </select>
            <button onClick={() => { setSortAsc(!sortAsc); }} className="flex items-center gap-sm px-md py-sm bg-surface-container border border-outline-variant rounded-lg text-body-sm text-on-surface-variant hover:text-on-surface transition-colors">
              {sortKey === 'date' ? (sortAsc ? 'Date Asc' : 'Date Desc') : sortKey === 'duration' ? 'Duration' : 'Task'}
            </button>
            {hasActiveFilters && (
              <button onClick={clearFilters} className="flex items-center gap-sm px-md py-sm bg-surface-container border border-outline-variant rounded-lg text-body-sm text-on-surface-variant hover:text-on-surface transition-colors">
                <RotateCcw className="w-3.5 h-3.5" /> Clear
              </button>
            )}
          </div>
        </div>
        <div className="w-full shrink-0 sm:w-[300px]">
          <SessionCalendar
            compact
            items={allSessions.map((s) => ({
              timestamp: s.date,
              riskLevel: sessionRiskLevel(s),
            }))}
            selectedDate={selectedDate}
            onSelectDate={setSelectedDate}
          />
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-sm text-[11px] text-on-surface-variant">
        <span>
          {filtered.length} session{filtered.length === 1 ? '' : 's'}
          {hasActiveFilters ? ' match the filters' : ' available'}
          {selectedDate && <span className="ml-sm">· Showing: {selectedDate}</span>}
        </span>
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
                    {(['Session', 'Duration', 'Highest Risk', 'Task', 'Status', ''] as const).map((h) => (
                      <th key={h} className="font-label-caps text-[10px] text-on-surface-variant uppercase tracking-widest px-lg py-md">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {paged.map((s) => (
                    <tr key={s.id} onClick={() => setSelectedId(s.id)} className="border-b border-outline-variant/50 hover:bg-surface-container-low transition-colors cursor-pointer">
                      <td className="px-lg py-md" title={`Session ID: ${s.id}`}>
                        <span className="text-body-sm font-medium text-on-surface">
                          {formatSessionLabel(s.date, s.id)}
                        </span>
                        <span className="block font-label-mono text-[10px] text-on-surface-variant/70 mt-0.5">{normalizeSessionId(s.id)}</span>
                      </td>
                      <td className="px-lg py-md text-body-sm text-on-surface">{s.duration}</td>
                      <td className="px-lg py-md">
                        <span className={`text-body-sm font-bold ${sessionRiskLevel(s) === 'HIGH' ? 'text-danger' : sessionRiskLevel(s) === 'MEDIUM' ? 'text-warning' : 'text-success'}`}>
                          {sessionRiskLevel(s)}
                        </span>
                      </td>
                      <td className="px-lg py-md text-body-sm text-on-surface">
                        {s.task && s.task !== 'Not classified' ? (
                          s.task
                        ) : (
                          <span className="text-on-surface-variant/60">—</span>
                        )}
                      </td>
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

          {filtered.length > PAGE_SIZE && (
            <div className="mt-md flex flex-wrap items-center justify-between gap-md">
              <span className="text-[11px] text-on-surface-variant">
                Showing {shownStart}–{shownEnd} of {filtered.length}
              </span>
              <div className="flex items-center gap-sm">
                <button
                  disabled={safePage <= 1}
                  onClick={() => setPage(safePage - 1)}
                  className="px-md py-sm rounded-lg border border-outline-variant bg-surface-container text-body-sm text-on-surface-variant hover:text-on-surface transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  ← Prev
                </button>
                <span className="text-[11px] text-on-surface-variant">Page {safePage} of {pageCount}</span>
                <button
                  disabled={safePage >= pageCount}
                  onClick={() => setPage(safePage + 1)}
                  className="px-md py-sm rounded-lg border border-outline-variant bg-surface-container text-body-sm text-on-surface-variant hover:text-on-surface transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Next →
                </button>
              </div>
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
              {/* Incident evidence package: one-click zip for OSHA / insurance */}
              <button
                className="mt-md w-full flex items-center justify-center gap-sm rounded-lg border border-outline-variant bg-surface-container-low px-md py-sm text-body-sm font-semibold text-on-surface hover:border-primary/40 hover:bg-surface-container transition-colors"
                onClick={() => downloadEvidence(detail.id)}
              >
                <FileDown className="w-4 h-4 text-primary" />
                Incident Evidence Package (zip)
              </button>
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
