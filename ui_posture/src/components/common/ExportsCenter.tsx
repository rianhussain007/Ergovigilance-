import { useState } from 'react';
import { FileJson, FileSpreadsheet, FileDown, Mail, Share2, Check, X } from 'lucide-react';
import { useToast } from '@/src/hooks/useToast';
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

  const exportPDF = () => {
    addToast('info', 'PDF coming soon', 'Full report export will be available in a future update.');
  };

  const handleExport = async (format: string, label: string) => {
    setExporting(format);
    try {
      if (format === 'CSV') exportCSV();
      else if (format === 'JSON') exportJSON();
      else if (format === 'PDF') exportPDF();
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
          desc="Full report including charts"
          format="PDF"
          exporting={exporting}
          onClick={() => handleExport('PDF', 'Export as PDF')}
          placeholder
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
          desc="Send to stakeholders"
          format="email"
          exporting={exporting}
          onClick={() => handleExport('email', 'Email Report')}
          placeholder
        />
        <ExportButton
          icon={Share2}
          label="Share Link"
          desc="Create a shareable link"
          format="link"
          exporting={exporting}
          onClick={() => handleExport('link', 'Share Link')}
          placeholder
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
