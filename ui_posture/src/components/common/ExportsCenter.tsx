import { useState } from 'react';
import { FileJson, FileSpreadsheet, FileDown, Mail, Share2, Check, X } from 'lucide-react';
import { useToast } from '@/src/hooks/useToast';
import { apiFetch } from '@/src/services/apiClient';
import type { TimelineEntry, DashboardResponse } from '@/src/types/api';

interface ExportsCenterProps {
  onClose?: () => void;
  timeline?: TimelineEntry[];
  dashboard?: DashboardResponse | null;
}

export function ExportsCenter({ onClose, timeline, dashboard }: ExportsCenterProps) {
  const { addToast } = useToast();
  const [exporting, setExporting] = useState<string | null>(null);

  const downloadBlob = (content: string, filename: string, mime: string) => {
    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const exportCSV = () => {
    if (!timeline || timeline.length === 0) {
      addToast('warning', 'No timeline data', 'Start a monitoring session first.');
      return;
    }
    const featureKeys = Object.keys(timeline[0]?.features || {});
    const headers = ['timestamp', 'risk_score', 'risk_level', 'confidence', ...featureKeys];
    const rows = timeline.map((e) => {
      const vals = featureKeys.map((k) => e.features[k] ?? '');
      return [e.timestamp, e.risk_score, e.risk_level, e.confidence, ...vals].join(',');
    });
    const csv = [headers.join(','), ...rows].join('\n');
    downloadBlob(csv, `export-${Date.now()}.csv`, 'text/csv');
    addToast('success', 'CSV exported', `${timeline.length} rows`);
  };

  const exportJSON = () => {
    if (!timeline || timeline.length === 0) {
      addToast('warning', 'No timeline data', 'Start a monitoring session first.');
      return;
    }
    const payload = {
      exportedAt: new Date().toISOString(),
      sessionId: dashboard?.session?.id || null,
      workerName: dashboard?.session?.workerName || null,
      entries: timeline,
    };
    const json = JSON.stringify(payload, null, 2);
    downloadBlob(json, `export-${Date.now()}.json`, 'application/json');
    addToast('success', 'JSON exported', `${timeline.length} entries`);
  };

  const exportPDF = async () => {
    const sessionId = dashboard?.session?.id;
    if (!sessionId) {
      addToast('warning', 'No session to export', 'Start a monitoring session first.');
      return;
    }
    try {
      const res = await apiFetch(`/api/reports/session/${encodeURIComponent(sessionId)}/pdf`);
      if (res.status === 404) {
        addToast('warning', 'Report not ready', 'The session report is generated once the session is saved. Open the Reports page to export it.');
        return;
      }
      if (!res.ok) {
        addToast('error', 'PDF export failed', `Server responded with ${res.status}`);
        return;
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `session-report-${sessionId}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      addToast('success', 'PDF exported', `Report saved as session-report-${sessionId}.pdf`);
    } catch {
      addToast('error', 'PDF export failed', 'Could not reach the report service.');
    }
  };

  const buildSummary = () => {
    const sessionId = dashboard?.session?.id || 'no-active-session';
    const worker = dashboard?.session?.workerName || 'unknown worker';
    const entries = timeline?.length ?? 0;
    const highRisk = (dashboard?.riskHistory ?? []).filter((p) => p.value >= 60).length;
    return {
      subject: `ErgoVigilance report — ${worker} (${sessionId})`,
      body: [
        'ErgoVigilance monitoring report',
        '',
        `Worker: ${worker}`,
        `Session: ${sessionId}`,
        `Timeline entries: ${entries}`,
        `High-risk readings: ${highRisk}`,
        '',
        'Full data is available in the ErgoVigilance dashboard.',
      ].join('\n'),
    };
  };

  const exportEmail = () => {
    const { subject, body } = buildSummary();
    window.location.href = `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
    addToast('success', 'Email draft opened', 'A report summary email was composed in your mail client.');
  };

  const exportShare = async () => {
    // Build the share payload: reuse the JSON export so stakeholders receive data.
    if (!timeline || timeline.length === 0) {
      addToast('warning', 'No timeline data', 'Start a monitoring session first.');
      return;
    }
    const payload = {
      exportedAt: new Date().toISOString(),
      sessionId: dashboard?.session?.id || null,
      workerName: dashboard?.session?.workerName || null,
      entries: timeline,
    };
    const json = JSON.stringify(payload, null, 2);
    const file = new File([json], `ergovigilance-export-${Date.now()}.json`, {
      type: 'application/json',
    });
    const nav = navigator as Navigator & {
      share?: (data: { files?: File[]; title?: string; text?: string }) => Promise<void>;
      canShare?: (data: { files: File[] }) => boolean;
    };
    if (nav.share) {
      try {
        const shareData = { files: [file], title: 'ErgoVigilance export' };
        if (nav.canShare?.(shareData)) {
          await nav.share(shareData);
          addToast('success', 'Export shared', 'The report was shared via your system share sheet.');
          return;
        }
      } catch {
        // user cancelled — fall through silently
      }
    }
    // Fallback: copy a share-ready summary to the clipboard.
    const summary = buildSummary();
    try {
      await navigator.clipboard.writeText(`${summary.body}\n\nShare this session in ErgoVigilance to collaborate.`);
      addToast('success', 'Summary copied', 'Share this text with stakeholders.');
    } catch {
      addToast('error', 'Share unavailable', 'Your browser cannot share or copy on this device.');
    }
  };

  const handleExport = async (format: string, label: string) => {
    setExporting(format);
    try {
      if (format === 'CSV') exportCSV();
      else if (format === 'JSON') exportJSON();
      else if (format === 'PDF') await exportPDF();
      else if (format === 'email') exportEmail();
      else if (format === 'link') await exportShare();
      else {
        addToast('info', `${label} coming soon`, 'This feature requires backend infrastructure not yet available.');
      }
    } finally {
      setExporting(null);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-lg">
        <h3 className="text-title-md font-bold text-on-surface">Exports Center</h3>
        {onClose && (
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-surface-container-higher text-on-surface-variant transition-colors">
            <X className="w-4 h-4" />
          </button>
        )}
      </div>
      <div className="space-y-sm">
        <ExportButton
          icon={FileDown}
          label="Export as PDF"
          desc="Session report (saved sessions)"
          format="PDF"
          exporting={exporting}
          onClick={() => handleExport('PDF', 'Export as PDF')}
        />
        <ExportButton
          icon={FileSpreadsheet}
          label="Export as CSV"
          desc="Raw data table from live timeline"
          format="CSV"
          exporting={exporting}
          onClick={() => handleExport('CSV', 'Export as CSV')}
        />
        <ExportButton
          icon={FileJson}
          label="Export as JSON"
          desc="Machine-readable timeline data"
          format="JSON"
          exporting={exporting}
          onClick={() => handleExport('JSON', 'Export as JSON')}
        />
        <ExportButton
          icon={Mail}
          label="Email Report"
          desc="Compose a summary email for stakeholders"
          format="email"
          exporting={exporting}
          onClick={() => handleExport('email', 'Email Report')}
        />
        <ExportButton
          icon={Share2}
          label="Share Export"
          desc="Share the data via the system share sheet"
          format="link"
          exporting={exporting}
          onClick={() => handleExport('link', 'Share Export')}
        />
      </div>
    </div>
  );
}

function ExportButton({
  icon: Icon, label, desc, format, exporting, onClick, placeholder,
}: {
  icon: typeof FileDown; label: string; desc: string; format: string;
  exporting: string | null; onClick: () => void; placeholder?: boolean;
}) {
  const isBusy = exporting !== null;
  return (
    <button
      onClick={onClick}
      disabled={isBusy}
      className="w-full grid grid-cols-[auto_1fr_auto] items-center gap-md p-md rounded-lg border border-outline-variant bg-surface-container hover:bg-surface-container-higher transition-all disabled:opacity-60 text-left group"
    >
      <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center shrink-0 group-hover:bg-primary/20 transition-colors">
        {exporting === format ? (
          <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
        ) : (
          <Icon className="w-4 h-4 text-primary" />
        )}
      </div>
      <div className="min-w-0">
        <p className="text-body-sm font-medium text-on-surface">
          {label}
          {placeholder && <span className="ml-1 text-[10px] font-normal text-on-surface-variant/60">*</span>}
        </p>
        <p className="text-[10px] text-on-surface-variant mt-0.5">{desc}</p>
      </div>
      {exporting === format ? (
        <Check className="w-4 h-4 text-green-400 shrink-0" />
      ) : (
        <div className="w-2 h-2 rounded-full bg-outline-variant shrink-0" />
      )}
    </button>
  );
}
