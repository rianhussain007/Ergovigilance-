import { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router';
import { FileText, Download, Search, Clock, Shield, TrendingUp, FileSpreadsheet, FileJson, ArrowLeft, AlertTriangle, CheckCircle, ChevronUp, Minus, ChevronDown, Loader2 } from 'lucide-react';
import { useToast } from '@/src/hooks/useToast';
import { EmptyState, SectionHeader, LoadingCard } from '@/src/components/common';
import { getReports, getSessionDetail, getRiskTrend, getSafetyReport, getWorkerTrends } from '@/src/services/dashboardService';
import { apiFetch } from '@/src/services/apiClient';
import { getStoredToken } from '@/src/auth/AuthContext';
import { normalizeReportId } from '@/src/utils/sessionId';
import { formatISTFull, formatISTDate } from '@/src/utils/formatTime';
import type { ReportRecord, SessionDetail, RiskTrendResponse, SafetyReportResponse, WorkerTrendsResponse, WorkerRecord } from '@/src/types/api';

// Standard limitation disclosure appended to every exported artifact. Heuristic
// thresholds are not clinically validated; screening aid, not a medical device.
const EXPORT_DISCLAIMER =
  'ErgoVigilance export — heuristic posture-risk thresholds, not clinically validated. ' +
  'Screening and awareness tool only; not a medical device; not a professional ergonomic assessment. ' +
  'Risk scores are estimates for prioritization and do not establish causation of injury.';

const TYPE_CONFIG: Record<string, { icon: typeof Shield; color: string; label: string }> = {
  safety: { icon: Shield, color: 'text-red-400', label: 'Safety' },
  session: { icon: FileText, color: 'text-blue-400', label: 'Session' },
  summary: { icon: TrendingUp, color: 'text-green-400', label: 'Summary' },
};

function severityColor(severity: string): string {
  if (severity === 'HIGH' || severity === 'CRITICAL') return 'text-red-400';
  if (severity === 'MEDIUM') return 'text-orange-400';
  return 'text-green-400';
}

function riskColor(level: string): string {
  if (level === 'HIGH') return 'text-red-400';
  if (level === 'MEDIUM') return 'text-orange-400';
  return 'text-green-400';
}

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

function formatTimestamp(iso: string): string {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return formatISTFull(d);
  } catch {
    return iso;
  }
}

const PAGE_SIZE = 20;

/** Report titles are "<Type> Report — <session id>" — show only the type. */
function reportDisplayTitle(title: string): string {
  const typePart = title.split(' — ')[0];
  return typePart.trim() || title;
}

export default function ReportsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [page, setPage] = useState(1);
  const [reports, setReports] = useState<ReportRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedReport, setSelectedReport] = useState<SessionDetail | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [riskTrendData, setRiskTrendData] = useState<RiskTrendResponse | null>(null);
  const [loadingTrend, setLoadingTrend] = useState(false);
  const [safetyReportData, setSafetyReportData] = useState<SafetyReportResponse | null>(null);
  const [loadingSafety, setLoadingSafety] = useState(false);
  const [workerTrendsData, setWorkerTrendsData] = useState<WorkerTrendsResponse | null>(null);
  const [loadingWorkerTrends, setLoadingWorkerTrends] = useState(false);
  // Nightly risk digest
  const [digestSummary, setDigestSummary] = useState<{ session_count: number; alert_count: number; highest_risk_level: string; risk_percentages: Record<string, number> } | null>(null);
  const [digestList, setDigestList] = useState<{ filename: string; generated_at: string; summary: { session_count: number } }[]>([]);
  const [loadingDigest, setLoadingDigest] = useState(false);
  const { addToast } = useToast();

  const fetchReports = useCallback(async () => {
    try {
      setLoading(true);
      const data = await getReports();
      setReports(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load reports');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchReports();
  }, [fetchReports]);

  const fetchDigests = useCallback(async () => {
    try {
      const res = await apiFetch('/api/reports/digest');
      if (!res.ok) return;
      const data = await res.json();
      setDigestList(data?.digests ?? []);
    } catch {
      // Non-fatal — the digest card simply shows nothing saved yet.
    }
  }, []);

  useEffect(() => {
    fetchDigests();
  }, [fetchDigests]);

  const handleGenerateDigest = async () => {
    setLoadingDigest(true);
    try {
      const res = await apiFetch('/api/reports/digest/generate', { method: 'POST' });
      if (!res.ok) throw new Error(`Digest request failed (${res.status})`);
      const data = await res.json();
      setDigestSummary(data?.summary ?? null);
      addToast('success', 'Digest generated', data?.saved ? 'Saved to outputs/reports/' : 'Nothing in the last 24 hours yet.');
      fetchDigests();
    } catch (err) {
      addToast('error', 'Failed', err instanceof Error ? err.message : 'Could not generate the digest.');
    } finally {
      setLoadingDigest(false);
    }
  };

  useEffect(() => {
    if (searchParams.get('view') === 'risk-trend') {
      setSearchParams({}, { replace: true });
      setLoadingTrend(true);
      getRiskTrend()
        .then((data) => setRiskTrendData(data))
        .catch((err) => addToast('error', 'Failed', err instanceof Error ? err.message : 'Could not generate risk trend report.'))
        .finally(() => setLoadingTrend(false));
    }
    if (searchParams.get('view') === 'worker-trends') {
      setSearchParams({}, { replace: true });
      setLoadingWorkerTrends(true);
      getWorkerTrends()
        .then((data) => setWorkerTrendsData(data))
        .catch((err) => addToast('error', 'Failed', err instanceof Error ? err.message : 'Could not generate worker trends report.'))
        .finally(() => setLoadingWorkerTrends(false));
    }
  }, []);

  const handleViewReport = async (report: ReportRecord) => {
    // Report IDs are "RPT-session_YYYYMMDD_HHMMSS", session detail expects "SESH-YYYYMMDD_HHMMSS"
    const rawId = report.id.replace('RPT-', '');
    const sessionId = rawId.startsWith('session_')
      ? 'SESH-' + rawId.replace('session_', '')
      : rawId;
    try {
      setLoadingDetail(true);
      setSelectedId(rawId);
      const detail = await getSessionDetail(sessionId);
      if (detail) {
        setSelectedReport(detail);
      } else {
        addToast('error', 'Not found', 'Session data for this report could not be loaded.');
        setSelectedId(null);
      }
    } catch (err) {
      addToast('error', 'Load failed', err instanceof Error ? err.message : 'Could not load report data.');
      setSelectedId(null);
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleBack = () => {
    setSelectedReport(null);
    setSelectedId(null);
  };

  const handleGenerateRiskTrend = async () => {
    try {
      setLoadingTrend(true);
      const data = await getRiskTrend();
      setRiskTrendData(data);
    } catch (err) {
      addToast('error', 'Failed', err instanceof Error ? err.message : 'Could not generate risk trend report.');
    } finally {
      setLoadingTrend(false);
    }
  };

  const handleBackFromTrend = () => setRiskTrendData(null);

  const handleGenerateSafetyReport = async () => {
    try {
      setLoadingSafety(true);
      const data = await getSafetyReport();
      setSafetyReportData(data);
    } catch (err) {
      addToast('error', 'Failed', err instanceof Error ? err.message : 'Could not generate safety report.');
    } finally {
      setLoadingSafety(false);
    }
  };

  const handleBackFromSafety = () => setSafetyReportData(null);

  const handleGenerateWorkerTrends = async () => {
    try {
      setLoadingWorkerTrends(true);
      const data = await getWorkerTrends();
      setWorkerTrendsData(data);
    } catch (err) {
      addToast('error', 'Failed', err instanceof Error ? err.message : 'Could not generate worker trends report.');
    } finally {
      setLoadingWorkerTrends(false);
    }
  };

  const handleBackFromWorkerTrends = () => setWorkerTrendsData(null);

  const handlePrint = () => {
    if (!selectedReport) return;
    const sessionId = selectedReport.id;
    const tsPart = sessionId.replace('SESH-', '');
    downloadPdf(`/api/reports/session/${sessionId}/pdf`, `session-report-${tsPart}.pdf`, addToast);
  };

  const filtered = reports.filter((r) => {
    if (search.trim() && !r.title.toLowerCase().includes(search.toLowerCase())) return false;
    if (typeFilter !== 'all' && r.type !== typeFilter) return false;
    if (dateFrom && r.date < dateFrom) return false;
    if (dateTo && r.date > dateTo) return false;
    return true;
  });

  // Reset to the first page whenever the visible set changes.
  useEffect(() => { setPage(1); }, [search, typeFilter, dateFrom, dateTo]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount);
  const paged = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);
  const shownStart = filtered.length === 0 ? 0 : (safePage - 1) * PAGE_SIZE + 1;
  const shownEnd = Math.min(safePage * PAGE_SIZE, filtered.length);

  if (safetyReportData) {
    return <SafetyReportView data={safetyReportData} onBack={handleBackFromSafety} addToast={addToast} />;
  }

  if (riskTrendData) {
    return <RiskTrendView data={riskTrendData} onBack={handleBackFromTrend} addToast={addToast} />;
  }

  if (workerTrendsData) {
    return <WorkerTrendsView data={workerTrendsData} onBack={handleBackFromWorkerTrends} addToast={addToast} />;
  }

  if (selectedReport) {
    return <ReportView detail={selectedReport} onBack={handleBack} onPrint={handlePrint} addToast={addToast} />;
  }

  return (
    <div className="p-lg space-y-lg pb-32">
      <div>
        <h1 className="text-display-lg font-bold text-on-surface">Reports</h1>
        <p className="text-body-sm text-on-surface-variant mt-xs">Generate, search, and download ergonomic reports</p>
      </div>

      {/* Nightly Risk Digest */}
      <section className="bg-surface-container border border-outline-variant rounded-xl p-lg">
        <div className="flex items-center justify-between flex-wrap gap-md mb-md">
          <div className="flex items-center gap-sm">
            <FileText className="w-5 h-5 text-primary" />
            <div>
              <h2 className="text-body-md font-bold text-on-surface">Nightly Risk Digest</h2>
              <p className="text-body-sm text-on-surface-variant mt-0.5">Zero-touch summary of the last 24 h — written automatically each night to outputs/reports/</p>
            </div>
          </div>
          <button
            onClick={handleGenerateDigest}
            disabled={loadingDigest}
            className="flex items-center gap-sm rounded-lg border border-primary/40 bg-primary/10 px-md py-sm text-body-sm font-bold text-primary hover:bg-primary/20 transition-colors disabled:opacity-50"
          >
            <FileText className="w-4 h-4" />
            {loadingDigest ? 'Generating…' : 'Generate Now'}
          </button>
        </div>
        {digestSummary && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-md text-body-sm mb-md">
            <div>
              <span className="text-on-surface-variant">Sessions (24 h)</span>
              <p className="font-bold text-on-surface mt-0.5">{digestSummary.session_count}</p>
            </div>
            <div>
              <span className="text-on-surface-variant">Alerts</span>
              <p className="font-bold text-on-surface mt-0.5">{digestSummary.alert_count}</p>
            </div>
            <div>
              <span className="text-on-surface-variant">Highest risk</span>
              <p className={`font-bold mt-0.5 ${riskColor(digestSummary.highest_risk_level)}`}>{digestSummary.highest_risk_level}</p>
            </div>
            <div className="flex items-end gap-sm">
              {(['LOW', 'MEDIUM', 'HIGH'] as const).map((l) => (
                <div key={l} className="text-center">
                  <p className={`text-body-sm font-bold ${riskColor(l)}`}>{((digestSummary.risk_percentages[l] ?? 0)).toFixed(0)}%</p>
                  <p className="text-[10px] text-on-surface-variant">{l}</p>
                </div>
              ))}
            </div>
          </div>
        )}
        {digestList.length > 0 && (
          <ul className="space-y-1">
            {digestList.slice(0, 5).map((d) => (
              <li key={d.filename} className="flex items-center justify-between text-body-sm border-t border-outline-variant/50 pt-1">
                <span className="font-mono text-on-surface-variant">{d.filename}</span>
                <span className="text-on-surface-variant">{d.summary?.session_count ?? 0} sessions · {d.generated_at ? formatISTDate(d.generated_at) : ''}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="grid grid-cols-1 md:grid-cols-3 gap-md">
        <button
          onClick={handleGenerateRiskTrend}
          disabled={loadingTrend}
          className="flex items-center gap-md bg-orange-500/10 border border-orange-500/30 rounded-xl p-lg hover:border-orange-500/50 transition-colors text-left disabled:opacity-50"
        >
          <div className="w-12 h-12 rounded-lg bg-orange-500/20 flex items-center justify-center shrink-0">
            <TrendingUp className="w-6 h-6 text-orange-400" />
          </div>
          <div>
            <p className="text-body-md font-bold text-on-surface">{loadingTrend ? 'Generating...' : 'Generate Risk Trend Report'}</p>
            <p className="text-body-sm text-on-surface-variant mt-0.5">Analyze risk trends across multiple sessions</p>
          </div>
        </button>
        <button
          onClick={handleGenerateSafetyReport}
          disabled={loadingSafety}
          className="flex items-center gap-md bg-blue-500/10 border border-blue-500/30 rounded-xl p-lg hover:border-blue-500/50 transition-colors text-left disabled:opacity-50"
        >
          <div className="w-12 h-12 rounded-lg bg-blue-500/20 flex items-center justify-center shrink-0">
            <Shield className="w-6 h-6 text-blue-400" />
          </div>
          <div>
            <p className="text-body-md font-bold text-on-surface">{loadingSafety ? 'Generating...' : 'Generate Safety Report'}</p>
            <p className="text-body-sm text-on-surface-variant mt-0.5">Comprehensive safety analysis across sessions</p>
          </div>
        </button>
        <button
          onClick={handleGenerateWorkerTrends}
          disabled={loadingWorkerTrends}
          className="flex items-center gap-md bg-green-500/10 border border-green-500/30 rounded-xl p-lg hover:border-green-500/50 transition-colors text-left disabled:opacity-50"
        >
          <div className="w-12 h-12 rounded-lg bg-green-500/20 flex items-center justify-center shrink-0">
            <Clock className="w-6 h-6 text-green-400" />
          </div>
          <div>
            <p className="text-body-md font-bold text-on-surface">{loadingWorkerTrends ? 'Generating...' : 'Generate Worker Trends Report'}</p>
            <p className="text-body-sm text-on-surface-variant mt-0.5">Per-worker fatigue trends and department patterns</p>
          </div>
        </button>
      </section>

      <section>
        <SectionHeader title="Session Reports" />

        <div className="mb-md flex flex-wrap items-center gap-md">
          <div className="flex h-8 w-full max-w-[340px] items-center gap-md rounded-lg border border-outline-variant bg-surface-container-high px-md">
            <Search className="w-4 h-4 shrink-0 text-on-surface-variant/60" />
            <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search reports..." className="h-full min-w-0 flex-1 bg-transparent text-body-sm text-on-surface placeholder:text-on-surface-variant/60 focus:outline-none" />
          </div>
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="h-8 px-md bg-surface-container border border-outline-variant rounded-lg text-body-sm text-on-surface focus:outline-none"
          >
            <option value="all">All report types</option>
            <option value="safety">Safety</option>
            <option value="session">Session</option>
            <option value="summary">Summary</option>
          </select>
          <label className="flex items-center gap-sm text-[11px] text-on-surface-variant">
            From
            <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className="h-8 px-md bg-surface-container border border-outline-variant rounded-lg text-body-sm text-on-surface focus:outline-none" />
          </label>
          <label className="flex items-center gap-sm text-[11px] text-on-surface-variant">
            To
            <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className="h-8 px-md bg-surface-container border border-outline-variant rounded-lg text-body-sm text-on-surface focus:outline-none" />
          </label>
        </div>

        <div className="mb-md text-[11px] text-on-surface-variant">
          {filtered.length} report{filtered.length === 1 ? '' : 's'} available
        </div>

        {loading ? (
          <LoadingCard height="h-40" />
        ) : error ? (
          <EmptyState title="Error loading reports" message={error} />
        ) : filtered.length === 0 ? (
          <EmptyState title="No reports found" message="Run a monitoring session to generate reports." />
        ) : (
          <>
            <div className="space-y-sm">
              {paged.map((r) => {
                const cfg = TYPE_CONFIG[r.type] || TYPE_CONFIG.summary;
                const Icon = cfg.icon;
                return (
                  <button
                    key={r.id}
                    onClick={() => handleViewReport(r)}
                    disabled={selectedId === r.id && loadingDetail}
                    className="w-full bg-surface-container border border-outline-variant rounded-lg p-md flex items-center gap-md hover:border-primary/30 transition-colors group text-left"
                  >
                    <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                      <Icon className={`w-5 h-5 ${cfg.color}`} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-body-sm font-medium text-on-surface">{reportDisplayTitle(r.title)}</p>
                      <div className="flex flex-wrap items-center gap-md mt-0.5">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-primary">{cfg.label}</span>
                        <span className="flex items-center gap-xs text-[10px] text-on-surface-variant"><Clock className="w-3 h-3" />{r.date}</span>
                        <span className="font-label-mono text-[10px] text-on-surface-variant/70" title={r.id}>{normalizeReportId(r.id)}</span>
                      </div>
                    </div>
                    <span className="text-[10px] text-on-surface-variant/60 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                      {selectedId === r.id && loadingDetail ? 'Loading...' : 'View →'}
                    </span>
                  </button>
                );
              })}
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
          </>
        )}
      </section>
    </div>
  );
}

function ReportView({ detail, onBack, onPrint, addToast }: { detail: SessionDetail; onBack: () => void; onPrint: () => void; addToast: (type: string, title: string, message: string) => void }) {
  const [workers, setWorkers] = useState<WorkerRecord[]>([]);

  useEffect(() => {
    let cancelled = false;
    apiFetch('/api/workers')
      .then((res) => (res.ok ? res.json() : []))
      .then((data: WorkerRecord[]) => {
        if (!cancelled) setWorkers(data);
      })
      .catch(() => { if (!cancelled) setWorkers([]); });
    return () => { cancelled = true; };
  }, []);

  const worker = workers.find((w) => w.worker_id === detail.worker_id);
  const hasWorkerData = !!worker;

  const handleExportCsv = () => {
    const rows: string[] = [];
    rows.push('# ' + EXPORT_DISCLAIMER.replace(/\s+/g, ' ').trim());
    rows.push('');
    rows.push('Field,Value');
    rows.push(`Session ID,${detail.id}`);
    rows.push(`Session Timestamp,${detail.session_timestamp}`);
    rows.push(`Duration (seconds),${detail.session_duration_seconds}`);
    rows.push(`Total Frames,${detail.total_frames}`);
    rows.push(`Risk LOW (%),${detail.risk_percentages.LOW}`);
    rows.push(`Risk MEDIUM (%),${detail.risk_percentages.MEDIUM}`);
    rows.push(`Risk HIGH (%),${detail.risk_percentages.HIGH}`);
    rows.push(`Highest Risk Level,${detail.highest_risk_level}`);
    rows.push(`Highest Risk Timestamp,${detail.highest_risk_timestamp ?? ''}`);
    rows.push(`Most Frequent Issue,${detail.most_frequent_issue ?? ''}`);
    rows.push(`Most Frequent Issue Count,${detail.most_frequent_issue_count}`);
    rows.push(`Avg Neck Flexion (deg),${detail.avg_neck_flexion}`);
    rows.push(`Avg Trunk Flexion (deg),${detail.avg_trunk_flexion}`);
    rows.push(`Avg Shoulder Symmetry (%),${detail.avg_shoulder_symmetry}`);
    rows.push(`Avg Knee Angle (deg),${detail.avg_knee_angle}`);
    rows.push('');
    rows.push('Alerts');
    rows.push('ID,Frame,Severity,State,Title,Message,Trigger Rule,Confidence,Created At');
    for (const a of detail.alerts) {
      rows.push(`${a.id},${a.frame_number},${a.severity},${a.state},"${a.title}","${a.message}",${a.trigger_rule},${a.confidence},${a.created_at}`);
    }
    const blob = new Blob([rows.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `session-report-${detail.id}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const handleExportJson = () => {
    const payload = { _disclaimer: EXPORT_DISCLAIMER, ...detail };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `session-report-${detail.id}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const ts = detail.session_timestamp || '';
  const dateDisplay = (() => {
    if (!ts) return '—';
    const match = ts.match(/(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})/);
    if (match) return `${match[1]}-${match[2]}-${match[3]} ${match[4]}:${match[5]}:${match[6]}`;
    return ts;
  })();

  return (
    <div className="p-lg space-y-lg pb-32 print:p-0 print:space-y-4">
      {/* Print-only header */}
      <style>{`@media print { body { margin: 0; } .no-print { display: none !important; } .print-only { display: block !important; } } .print-only { display: none; }`}</style>

      <div className="print-only mb-4">
        <h1 className="text-2xl font-bold">ErgoVigilance — Session Report</h1>
        <p className="text-sm text-gray-500">Generated {formatISTFull(new Date())}</p>
      </div>

      {/* Controls */}
      <div className="flex items-center justify-between no-print">
        <button onClick={onBack} className="flex items-center gap-sm text-body-sm text-on-surface-variant hover:text-on-surface transition-colors">
          <ArrowLeft className="w-4 h-4" /> Back to Reports
        </button>
        <div className="flex items-center gap-md flex-wrap justify-end">
          <button onClick={handleExportCsv} className="flex items-center gap-sm text-body-sm text-on-surface-variant hover:text-on-surface transition-colors">
            <FileSpreadsheet className="w-4 h-4" /> Export CSV
          </button>
          <button onClick={handleExportJson} className="flex items-center gap-sm text-body-sm text-on-surface-variant hover:text-on-surface transition-colors">
            <FileJson className="w-4 h-4" /> Export JSON
          </button>
          <button onClick={onPrint} className="flex items-center gap-sm text-body-sm text-on-surface-variant hover:text-on-surface transition-colors">
            <Download className="w-4 h-4" /> Export PDF
          </button>
        </div>
      </div>

      {/* Title */}
      <div>
        <h1 className="text-display-lg font-bold text-on-surface">Session Report</h1>
        <p className="text-body-sm text-on-surface-variant mt-xs">{detail.id}</p>
      </div>

      {/* Session Metadata */}
      <section className="bg-surface-container border border-outline-variant rounded-xl p-lg space-y-md">
        <h2 className="text-title-sm font-bold text-on-surface">Session Metadata</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-md text-body-sm">
          <div>
            <span className="text-on-surface-variant">Session ID</span>
            <p className="font-medium text-on-surface mt-0.5">{detail.id}</p>
          </div>
          <div>
            <span className="text-on-surface-variant">Date</span>
            <p className="font-medium text-on-surface mt-0.5">{dateDisplay}</p>
          </div>
          <div>
            <span className="text-on-surface-variant">Duration</span>
            <p className="font-medium text-on-surface mt-0.5">{formatDuration(detail.session_duration_seconds)}</p>
          </div>
          <div>
            <span className="text-on-surface-variant">Total Frames</span>
            <p className="font-medium text-on-surface mt-0.5">{detail.total_frames.toLocaleString()}</p>
          </div>
        </div>

        {/* Worker fields */}
        <div className="border-t border-outline-variant pt-md grid grid-cols-2 md:grid-cols-4 gap-md text-body-sm">
          <div>
            <span className="text-on-surface-variant">Worker Name {!hasWorkerData && <span className="text-[10px] text-on-surface-variant/60">*</span>}</span>
            <p className="font-medium text-on-surface mt-0.5">{worker?.name || '—'}</p>
          </div>
          <div>
            <span className="text-on-surface-variant">Department {!hasWorkerData && <span className="text-[10px] text-on-surface-variant/60">*</span>}</span>
            <p className="font-medium text-on-surface mt-0.5">{worker?.department || '—'}</p>
          </div>
          <div>
            <span className="text-on-surface-variant">Shift {!hasWorkerData && <span className="text-[10px] text-on-surface-variant/60">*</span>}</span>
            <p className="font-medium text-on-surface mt-0.5">{worker?.shift || '—'}</p>
          </div>
          <div>
            <span className="text-on-surface-variant">Workstation <span className="text-[10px] text-on-surface-variant/60">*</span></span>
            <p className="font-medium text-on-surface mt-0.5">—</p>
          </div>
        </div>
        {!hasWorkerData && <p className="text-[10px] text-on-surface-variant/50">* Worker data will appear once sessions are assigned to workers</p>}
      </section>

      {/* Risk Breakdown */}
      <section className="bg-surface-container border border-outline-variant rounded-xl p-lg space-y-md">
        <h2 className="text-title-sm font-bold text-on-surface">Risk Breakdown</h2>
        <div className="grid grid-cols-3 gap-md">
          {(['LOW', 'MEDIUM', 'HIGH'] as const).map((level) => {
            const pct = detail.risk_percentages[level] ?? 0;
            const color = riskColor(level);
            return (
              <div key={level} className="text-center">
                <p className={`text-title-lg font-bold ${color}`}>{pct.toFixed(1)}%</p>
                <p className="text-body-sm text-on-surface-variant">{level}</p>
              </div>
            );
          })}
        </div>
        <div className="grid grid-cols-2 gap-md text-body-sm">
          <div>
            <span className="text-on-surface-variant">Highest Risk Level</span>
            <p className={`font-medium mt-0.5 ${riskColor(detail.highest_risk_level)}`}>{detail.highest_risk_level}</p>
          </div>
          <div>
            <span className="text-on-surface-variant">Most Frequent Issue</span>
            <p className="font-medium text-on-surface mt-0.5">{detail.most_frequent_issue || 'None'} ({detail.most_frequent_issue_count})</p>
          </div>
        </div>
      </section>

      {/* Average Features */}
      <section className="bg-surface-container border border-outline-variant rounded-xl p-lg space-y-md">
        <h2 className="text-title-sm font-bold text-on-surface">Average Ergonomic Features</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-md text-body-sm">
          <div>
            <span className="text-on-surface-variant">Neck Flexion</span>
            <p className="font-medium text-on-surface mt-0.5">{detail.avg_neck_flexion.toFixed(1)}°</p>
          </div>
          <div>
            <span className="text-on-surface-variant">Trunk Flexion</span>
            <p className="font-medium text-on-surface mt-0.5">{detail.avg_trunk_flexion.toFixed(1)}°</p>
          </div>
          <div>
            <span className="text-on-surface-variant">Shoulder Symmetry</span>
            <p className="font-medium text-on-surface mt-0.5">{detail.avg_shoulder_symmetry.toFixed(1)}%</p>
          </div>
          <div>
            <span className="text-on-surface-variant">Knee Angle</span>
            <p className="font-medium text-on-surface mt-0.5">{detail.avg_knee_angle.toFixed(1)}°</p>
          </div>
        </div>
      </section>

      {/* Alert Timeline */}
      {detail.alerts.length > 0 && (
        <section className="bg-surface-container border border-outline-variant rounded-xl p-lg space-y-md">
          <h2 className="text-title-sm font-bold text-on-surface">Alert Timeline ({detail.alerts.length} alerts)</h2>
          <div className="space-y-sm">
            {detail.alerts.map((alert) => (
              <div key={alert.id} className="flex items-start gap-md p-sm bg-surface-container-highest/50 rounded-lg">
                {alert.severity === 'LOW' ? (
                  <CheckCircle className="w-4 h-4 text-green-400 shrink-0 mt-0.5" />
                ) : (
                  <AlertTriangle className={`w-4 h-4 shrink-0 mt-0.5 ${severityColor(alert.severity)}`} />
                )}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-sm">
                    <span className="text-body-sm font-medium text-on-surface">{alert.title}</span>
                    <span className={`text-[10px] font-bold uppercase ${severityColor(alert.severity)}`}>{alert.severity}</span>
                  </div>
                  <p className="text-[10px] text-on-surface-variant mt-0.5">{alert.message}</p>
                  <div className="flex items-center gap-md mt-1 text-[10px] text-on-surface-variant">
                    <span>Frame {alert.frame_number}</span>
                    <span>{formatTimestamp(alert.created_at)}</span>
                    <span>Rule: {alert.trigger_rule}</span>
                    <span>Confidence: {(alert.confidence * 100).toFixed(0)}%</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {detail.alerts.length === 0 && (
        <section className="bg-surface-container border border-outline-variant rounded-xl p-lg">
          <h2 className="text-title-sm font-bold text-on-surface">Alert Timeline</h2>
          <p className="text-body-sm text-on-surface-variant mt-sm">No alerts recorded during this session.</p>
        </section>
      )}
    </div>
  );
}

function trendIcon(trend: string) {
  if (trend === 'Improving') return <ChevronUp className="w-4 h-4 text-green-400" />;
  if (trend === 'Deteriorating') return <ChevronDown className="w-4 h-4 text-red-400" />;
  return <Minus className="w-4 h-4 text-yellow-400" />;
}

function trendColor(trend: string): string {
  if (trend === 'Improving') return 'text-green-400';
  if (trend === 'Deteriorating') return 'text-red-400';
  return 'text-yellow-400';
}

async function downloadPdf(url: string, filename: string, addToast: (type: string, title: string, msg: string) => void) {
  const token = getStoredToken();
  try {
    const res = await fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
    if (!res.ok) throw new Error(`PDF generation failed (${res.status})`);
    const blob = await res.blob();
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(link.href);
  } catch (err) {
    addToast('error', 'Download failed', err instanceof Error ? err.message : 'Could not download PDF.');
  }
}

function RiskTrendView({ data, onBack, addToast }: { data: RiskTrendResponse; onBack: () => void; addToast: (type: string, title: string, msg: string) => void }) {
  const dateDisplay = (ts: string) => {
    const match = ts.match(/(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})/);
    if (match) return `${match[1]}-${match[2]}-${match[3]} ${match[4]}:${match[5]}:${match[6]}`;
    return ts;
  };

  return (
    <div className="p-lg space-y-lg pb-32">
      <div className="flex items-center justify-between">
        <button onClick={onBack} className="flex items-center gap-sm text-body-sm text-on-surface-variant hover:text-on-surface transition-colors">
          <ArrowLeft className="w-4 h-4" /> Back to Reports
        </button>
        <button
          onClick={() => downloadPdf('/api/reports/risk-trend/pdf', 'risk-trend-report.pdf', addToast)}
          className="flex items-center gap-sm text-body-sm text-on-surface-variant hover:text-on-surface transition-colors"
        >
          <Download className="w-4 h-4" /> Download PDF
        </button>
      </div>

      <div>
        <h1 className="text-display-lg font-bold text-on-surface">Risk Trend Report</h1>
        <p className="text-body-sm text-on-surface-variant mt-xs">
          {data.total_sessions} sessions from {dateDisplay(data.earliest_session)} to {dateDisplay(data.latest_session)}
        </p>
      </div>

      {/* Risk Distribution */}
      <section className="bg-surface-container border border-outline-variant rounded-xl p-lg space-y-md">
        <h2 className="text-title-sm font-bold text-on-surface">Risk Distribution (Cross-Session Average)</h2>
        <div className="grid grid-cols-3 gap-md">
          {(['LOW', 'MEDIUM', 'HIGH'] as const).map((level) => {
            const key = level.toLowerCase() + '_pct' as keyof typeof data.risk_distribution;
            const pct = data.risk_distribution[key] ?? 0;
            return (
              <div key={level} className="text-center">
                <p className={`text-title-lg font-bold ${riskColor(level)}`}>{pct.toFixed(1)}%</p>
                <p className="text-body-sm text-on-surface-variant">{level}</p>
              </div>
            );
          })}
        </div>
        <div className="grid grid-cols-2 gap-md text-body-sm">
          <div>
            <span className="text-on-surface-variant">Most Common Highest Risk</span>
            <p className={`font-medium mt-0.5 ${riskColor(data.most_common_highest_risk)}`}>{data.most_common_highest_risk}</p>
          </div>
          <div>
            <span className="text-on-surface-variant">Most Frequent Issue</span>
            <p className="font-medium text-on-surface mt-0.5">{data.most_common_issue || 'None'} ({data.most_common_issue_count})</p>
          </div>
        </div>
      </section>

      {/* Per-Metric Trend */}
      <section className="bg-surface-container border border-outline-variant rounded-xl p-lg space-y-md">
        <h2 className="text-title-sm font-bold text-on-surface">Metric Trends</h2>
        <div className="space-y-sm">
          {data.metrics.map((m) => (
            <div key={m.name} className="flex items-center justify-between p-sm bg-surface-container-highest/50 rounded-lg">
              <div>
                <p className="text-body-sm font-medium text-on-surface">{m.label}</p>
                <p className="text-[10px] text-on-surface-variant">
                  Average: {m.average.toFixed(1)}{m.unit}
                </p>
              </div>
              <div className="flex items-center gap-sm">
                {trendIcon(m.trend)}
                <span className={`text-body-sm font-bold ${trendColor(m.trend)}`}>{m.trend}</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Overall Trend */}
      <section className="bg-surface-container border border-outline-variant rounded-xl p-lg space-y-md">
        <h2 className="text-title-sm font-bold text-on-surface">Overall Trend</h2>
        <div className="flex items-center gap-md">
          {trendIcon(data.overall_trend)}
          <span className={`text-title-md font-bold ${trendColor(data.overall_trend)}`}>{data.overall_trend}</span>
        </div>
      </section>
    </div>
  );
}

function SafetyReportView({ data, onBack, addToast }: { data: SafetyReportResponse; onBack: () => void; addToast: (type: string, title: string, msg: string) => void }) {
  const dateDisplay = (ts: string) => {
    const match = ts.match(/(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})/);
    if (match) return `${match[1]}-${match[2]}-${match[3]} ${match[4]}:${match[5]}:${match[6]}`;
    return ts;
  };

  const sevColors: Record<string, string> = {
    CRITICAL: 'text-red-400',
    HIGH: 'text-orange-400',
    MEDIUM: 'text-yellow-400',
    WARNING: 'text-yellow-300',
    LOW: 'text-green-400',
  };

  if (data.total_sessions_with_alerts === 0) {
    return (
      <div className="p-lg space-y-lg pb-32">
        <div className="flex items-center justify-between">
          <button onClick={onBack} className="flex items-center gap-sm text-body-sm text-on-surface-variant hover:text-on-surface transition-colors">
            <ArrowLeft className="w-4 h-4" /> Back to Reports
          </button>
        </div>
        <EmptyState title="No Alert Data" message={data.coverage_statement} />
      </div>
    );
  }

  return (
    <div className="p-lg space-y-lg pb-32">
      <div className="flex items-center justify-between">
        <button onClick={onBack} className="flex items-center gap-sm text-body-sm text-on-surface-variant hover:text-on-surface transition-colors">
          <ArrowLeft className="w-4 h-4" /> Back to Reports
        </button>
        <button
          onClick={() => downloadPdf('/api/reports/safety-report/pdf', 'safety-report.pdf', addToast)}
          className="flex items-center gap-sm text-body-sm text-on-surface-variant hover:text-on-surface transition-colors"
        >
          <Download className="w-4 h-4" /> Download PDF
        </button>
      </div>

      <div>
        <h1 className="text-display-lg font-bold text-on-surface">Safety Report</h1>
        <p className="text-body-sm text-on-surface-variant mt-xs">
          {dateDisplay(data.earliest_session)} to {dateDisplay(data.latest_session)}
        </p>
      </div>

      {/* Coverage disclosure */}
      <div className="bg-surface-container border border-orange-500/30 rounded-xl p-md">
        <p className="text-body-sm text-on-surface-variant">{data.coverage_statement}</p>
      </div>

      {/* Alert Volume */}
      <section className="bg-surface-container border border-outline-variant rounded-xl p-lg space-y-md">
        <h2 className="text-title-sm font-bold text-on-surface">Alert Volume</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-md text-center">
          <div>
            <p className="text-title-lg font-bold text-on-surface">{data.total_alerts}</p>
            <p className="text-body-sm text-on-surface-variant">Total Alerts</p>
          </div>
          <div>
            <p className="text-title-lg font-bold text-on-surface">{data.alert_density.avg_per_session}</p>
            <p className="text-body-sm text-on-surface-variant">Avg per Session</p>
          </div>
          <div>
            <p className="text-title-lg font-bold text-on-surface">{data.alert_density.alerts_per_hour.toFixed(0)}</p>
            <p className="text-body-sm text-on-surface-variant">Alerts per Hour</p>
          </div>
          <div>
            <p className="text-title-lg font-bold text-on-surface">{data.total_sessions_with_alerts}</p>
            <p className="text-body-sm text-on-surface-variant">Sessions with Alerts</p>
          </div>
        </div>
      </section>

      {/* Severity Breakdown */}
      <section className="bg-surface-container border border-outline-variant rounded-xl p-lg space-y-md">
        <h2 className="text-title-sm font-bold text-on-surface">Severity Breakdown</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-md text-center">
          {Object.entries(data.severity_breakdown).map(([sev, count]) => (
            <div key={sev}>
              <p className={`text-title-lg font-bold ${sevColors[sev] || 'text-on-surface'}`}>{count}</p>
              <p className="text-body-sm text-on-surface-variant">{sev}</p>
            </div>
          ))}
        </div>
        <div className="grid grid-cols-2 gap-md text-body-sm pt-sm border-t border-outline-variant">
          <div>
            <span className="text-on-surface-variant">CRITICAL + HIGH</span>
            <p className="text-title-sm font-bold text-red-400 mt-0.5">{data.high_severity_total} ({data.total_alerts > 0 ? ((data.high_severity_total / data.total_alerts) * 100).toFixed(0) : 0}%)</p>
          </div>
          <div>
            <span className="text-on-surface-variant">WARNING + LOW</span>
            <p className="text-title-sm font-bold text-green-400 mt-0.5">{data.low_severity_total} ({data.total_alerts > 0 ? ((data.low_severity_total / data.total_alerts) * 100).toFixed(0) : 0}%)</p>
          </div>
        </div>
      </section>

      {/* Trigger Rules */}
      <section className="bg-surface-container border border-outline-variant rounded-xl p-lg space-y-md">
        <h2 className="text-title-sm font-bold text-on-surface">Trigger Rules</h2>
        <div className="space-y-sm">
          {data.trigger_rule_breakdown.map((t) => (
            <div key={t.rule} className="flex items-center gap-md">
              <div className="flex-1">
                <div className="flex justify-between mb-1">
                  <span className="text-body-sm font-medium text-on-surface">{t.rule.replace(/_/g, ' ')}</span>
                  <span className="text-body-sm text-on-surface-variant">{t.count} ({t.pct}%)</span>
                </div>
                <div className="h-2 bg-surface-container-highest rounded-full overflow-hidden">
                  <div className="h-full bg-primary rounded-full" style={{ width: `${t.pct}%` }} />
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Density */}
      <section className="bg-surface-container border border-outline-variant rounded-xl p-lg space-y-md">
        <h2 className="text-title-sm font-bold text-on-surface">Alert Density</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-md text-body-sm">
          <div>
            <span className="text-on-surface-variant">Total Monitor Time</span>
            <p className="font-medium text-on-surface mt-0.5">{data.alert_density.total_monitored_hours.toFixed(1)} hours</p>
          </div>
          <div>
            <span className="text-on-surface-variant">Avg Session Duration</span>
            <p className="font-medium text-on-surface mt-0.5">{formatDuration(data.alert_density.avg_session_duration_seconds)}</p>
          </div>
          <div>
            <span className="text-on-surface-variant">Range per Session</span>
            <p className="font-medium text-on-surface mt-0.5">{data.alert_density.min_alerts_per_session} – {data.alert_density.max_alerts_per_session}</p>
          </div>
        </div>
      </section>

      {/* Top Sessions by Alert Count */}
      <section className="bg-surface-container border border-outline-variant rounded-xl p-lg space-y-md">
        <h2 className="text-title-sm font-bold text-on-surface">Top Sessions by Alert Count</h2>
        <div className="space-y-sm">
          {data.top_sessions_by_alerts.map((s, i) => (
            <div key={s.session_timestamp} className="flex items-center justify-between p-sm bg-surface-container-highest/50 rounded-lg">
              <div className="flex items-center gap-md">
                <span className="text-body-sm font-bold text-on-surface-variant w-6">#{i + 1}</span>
                <div>
                  <p className="text-body-sm font-medium text-on-surface">{dateDisplay(s.session_timestamp)}</p>
                  <p className={`text-[10px] font-bold uppercase ${riskColor(s.highest_risk_level)}`}>{s.highest_risk_level} Risk</p>
                </div>
              </div>
              <span className="text-body-sm font-bold text-on-surface">{s.alert_count}</span>
            </div>
          ))}
        </div>
      </section>

      {/* Most Frequent Issues */}
      <section className="bg-surface-container border border-outline-variant rounded-xl p-lg space-y-md">
        <h2 className="text-title-sm font-bold text-on-surface">Most Frequent Issues (Alert Sessions)</h2>
        <div className="space-y-sm">
          {data.most_frequent_issues.map((iss) => (
            <div key={iss.issue} className="flex items-center justify-between p-sm bg-surface-container-highest/50 rounded-lg">
              <span className="text-body-sm font-medium text-on-surface">{iss.issue}</span>
              <span className="text-body-sm font-bold text-on-surface-variant">{iss.count} sessions</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function WorkerTrendsView({ data, onBack, addToast }: { data: WorkerTrendsResponse; onBack: () => void; addToast: (type: string, title: string, msg: string) => void }) {
  return (
    <div className="p-lg space-y-lg pb-32">
      <div className="flex items-center justify-between">
        <button onClick={onBack} className="flex items-center gap-sm text-body-sm text-on-surface-variant hover:text-on-surface transition-colors">
          <ArrowLeft className="w-4 h-4" /> Back to Reports
        </button>
        <button
          onClick={() => downloadPdf('/api/reports/worker-trends/pdf', 'worker-trends-report.pdf', addToast)}
          className="flex items-center gap-sm text-body-sm text-on-surface-variant hover:text-on-surface transition-colors"
        >
          <Download className="w-4 h-4" /> Download PDF
        </button>
      </div>

      <div>
        <h1 className="text-display-lg font-bold text-on-surface">Worker Trends Report</h1>
        <p className="text-body-sm text-on-surface-variant mt-xs">
          Per-worker fatigue trends across {data.total_workers_with_data} workers with session data
        </p>
      </div>

      {/* Summary */}
      <section className="bg-surface-container border border-outline-variant rounded-xl p-lg space-y-md">
        <h2 className="text-title-sm font-bold text-on-surface">Summary</h2>
        <div className="grid grid-cols-4 gap-md text-center">
          <div>
            <p className="text-title-lg font-bold text-on-surface">{data.total_workers}</p>
            <p className="text-body-sm text-on-surface-variant">Registered Workers</p>
          </div>
          <div>
            <p className="text-title-lg font-bold text-on-surface">{data.total_workers_with_data}</p>
            <p className="text-body-sm text-on-surface-variant">Workers with Data</p>
          </div>
          <div>
            <p className="text-title-lg font-bold text-on-surface">{data.departments.length}</p>
            <p className="text-body-sm text-on-surface-variant">Departments</p>
          </div>
          <div>
            <p className="text-title-lg font-bold text-on-surface">{data.station_analysis.length}</p>
            <p className="text-body-sm text-on-surface-variant">Stations</p>
          </div>
        </div>
      </section>

      {/* Per-Department Summary */}
      <section className="bg-surface-container border border-outline-variant rounded-xl p-lg space-y-md">
        <h2 className="text-title-sm font-bold text-on-surface">Department Patterns</h2>
        <div className="space-y-sm">
          {data.departments.map((dept) => (
            <div key={dept.department} className="flex items-center justify-between p-sm bg-surface-container-highest/50 rounded-lg">
              <div>
                <p className="text-body-sm font-medium text-on-surface">{dept.department}</p>
                <p className="text-[10px] text-on-surface-variant">{dept.worker_count} worker{dept.worker_count !== 1 ? 's' : ''}</p>
              </div>
              <div className="flex items-center gap-md">
                <div className="text-right">
                  <p className={`text-body-sm font-bold ${dept.avg_risk_score >= 70 ? 'text-red-400' : dept.avg_risk_score >= 40 ? 'text-orange-400' : 'text-green-400'}`}>
                    {dept.avg_risk_score.toFixed(1)}
                  </p>
                  <p className="text-[10px] text-on-surface-variant">avg risk</p>
                </div>
                {dept.high_risk_count > 0 && (
                  <span className="text-[10px] font-bold text-red-400 bg-red-500/10 px-sm py-0.5 rounded">
                    {dept.high_risk_count} HIGH
                  </span>
                )}
                <div className="flex items-center gap-xs">
                  {trendIcon(dept.trend)}
                  <span className={`text-body-sm font-bold ${trendColor(dept.trend)}`}>{dept.trend}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Per-Worker Details */}
      <section className="bg-surface-container border border-outline-variant rounded-xl p-lg space-y-md">
        <h2 className="text-title-sm font-bold text-on-surface">Worker Details</h2>
        <div className="space-y-sm">
          {data.workers.map((w) => (
            <div key={w.worker_id} className="p-sm bg-surface-container-highest/50 rounded-lg space-y-sm">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-body-sm font-medium text-on-surface">{w.name}</p>
                  <p className="text-[10px] text-on-surface-variant">{w.department} · {w.shift} · {w.sessions} sessions</p>
                </div>
                <div className="flex items-center gap-md">
                  <div className="text-right">
                    <p className={`text-body-sm font-bold ${w.avg_risk_score >= 70 ? 'text-red-400' : w.avg_risk_score >= 40 ? 'text-orange-400' : 'text-green-400'}`}>
                      {w.avg_risk_score.toFixed(1)}
                    </p>
                    <p className="text-[10px] text-on-surface-variant">avg risk</p>
                  </div>
                  <span className={`text-[10px] font-bold uppercase ${riskColor(w.latest_risk_level)} bg-surface-container-highest px-sm py-0.5 rounded`}>
                    {w.latest_risk_level}
                  </span>
                  <div className="flex items-center gap-xs">
                    {trendIcon(w.trend)}
                    <span className={`text-body-sm font-bold ${trendColor(w.trend)}`}>{w.trend}</span>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Temporal Curves (Weekly Risk per Worker) */}
      {data.temporal_curves.length > 0 && (
        <section className="bg-surface-container border border-outline-variant rounded-xl p-lg space-y-md">
          <h2 className="text-title-sm font-bold text-on-surface">Weekly Risk Trends</h2>
          <p className="text-[10px] text-on-surface-variant">Average risk score per week for workers with 2+ weeks of data</p>
          <div className="space-y-lg">
            {data.temporal_curves.map((curve) => (
              <div key={curve.worker_id} className="space-y-sm">
                <div className="flex items-center gap-sm">
                  <span className="text-body-sm font-medium text-on-surface">{curve.name}</span>
                  <span className="text-[10px] text-on-surface-variant">({curve.department})</span>
                </div>
                <div className="flex items-end gap-xs h-20">
                  {curve.points.map((pt) => {
                    const height = Math.max(8, (pt.avg_risk_score / 100) * 80);
                    const color = pt.avg_risk_score >= 70 ? 'bg-red-400' : pt.avg_risk_score >= 40 ? 'bg-orange-400' : 'bg-green-400';
                    return (
                      <div key={pt.week} className="flex flex-col items-center gap-1 flex-1 min-w-0">
                        <span className="text-[9px] text-on-surface-variant">{pt.avg_risk_score.toFixed(0)}</span>
                        <div className={`w-full rounded-t ${color}`} style={{ height: `${height}px` }} />
                        <span className="text-[8px] text-on-surface-variant truncate w-full text-center">{pt.week}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Station Analysis */}
      {data.station_analysis.length > 0 && (
        <section className="bg-surface-container border border-outline-variant rounded-xl p-lg space-y-md">
          <h2 className="text-title-sm font-bold text-on-surface">Station Risk Patterns</h2>
          <p className="text-[10px] text-on-surface-variant">Risk analysis grouped by camera/station (17 of 139 sessions have station data)</p>
          <div className="space-y-sm">
            {data.station_analysis.map((station) => (
              <div key={station.station_id} className="flex items-center justify-between p-sm bg-surface-container-highest/50 rounded-lg">
                <div>
                  <p className="text-body-sm font-medium text-on-surface">{station.display_name}</p>
                  <p className="text-[10px] text-on-surface-variant">{station.sessions} sessions · {station.worker_count} worker{station.worker_count !== 1 ? 's' : ''}</p>
                </div>
                <div className="flex items-center gap-md">
                  <div className="text-right">
                    <p className={`text-body-sm font-bold ${station.avg_risk_score >= 70 ? 'text-red-400' : station.avg_risk_score >= 40 ? 'text-orange-400' : 'text-green-400'}`}>
                      {station.avg_risk_score.toFixed(1)}
                    </p>
                    <p className="text-[10px] text-on-surface-variant">avg risk</p>
                  </div>
                  {station.high_risk_count > 0 && (
                    <span className="text-[10px] font-bold text-red-400 bg-red-500/10 px-sm py-0.5 rounded">
                      {station.high_risk_count} HIGH
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
