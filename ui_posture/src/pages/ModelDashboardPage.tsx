import { useEffect, useRef, useState } from 'react';
import { Brain, BarChart3, Target, Layers, CheckCircle2, AlertTriangle, Download, Upload, History, RotateCcw } from 'lucide-react';

interface ModelMetrics {
  cv_f1_mean: number;
  cv_f1_std: number;
  test_accuracy: number;
  test_f1: number;
  n_samples: number;
  n_features?: number;
}

interface ComparisonData {
  yolo_cloud: {
    risk: ModelMetrics;
    task: ModelMetrics;
    keypoints: number;
    model: string;
    runtime: string;
  };
  mediapipe_on_premise: {
    accuracy: number | null;
    n_samples: number | null;
    keypoints: number;
    model: string;
    runtime: string;
  };
}

interface ModelDetail {
  features?: string[];
  classes?: string[];
  confusion_matrix?: number[][];
}

export default function ModelDashboardPage() {
  const [comparison, setComparison] = useState<ComparisonData | null>(null);
  const [yoloDetail, setYoloDetail] = useState<Record<string, ModelDetail>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      fetch('/cloud-api/cloud/models/compare').then(r => r.json()),
      fetch('/cloud-api/cloud/models/metrics').then(r => r.json()),
    ])
      .then(([comp, detail]) => {
        setComparison(comp);
        setYoloDetail(detail);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-4xl p-8">
        <div className="rounded-xl border border-red-500/20 bg-red-500/10 p-6 text-red-400">
          <AlertTriangle className="mb-2 h-5 w-5" />
          <p>Failed to load model metrics: {error}</p>
          <p className="mt-2 text-sm text-red-400/70">
            Make sure the YOLO cloud core is running on port 8100.
          </p>
        </div>
      </div>
    );
  }

  const riskMetrics = comparison?.yolo_cloud?.risk;
  const taskMetrics = comparison?.yolo_cloud?.task;
  const mpMetrics = comparison?.mediapipe_on_premise;
  const riskDetail = yoloDetail?.yolo_risk || {};
  const taskDetail = yoloDetail?.yolo_task || {};

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="rounded-lg bg-primary/10 p-2">
          <Brain className="h-6 w-6 text-primary" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-white">Model Dashboard</h1>
          <p className="text-sm text-slate-400">
            YOLO Cloud Core ML model performance and comparison
          </p>
        </div>
      </div>

      {/* Model Comparison Cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {/* YOLO Cloud */}
        <div className="rounded-xl border border-primary/20 bg-gradient-to-br from-primary/5 to-primary/10 p-6">
          <div className="mb-4 flex items-center gap-2">
            <Layers className="h-5 w-5 text-primary" />
            <h2 className="text-lg font-semibold text-white">YOLO Cloud Core</h2>
            <span className="rounded-full bg-primary/20 px-2 py-0.5 text-xs text-primary">
              CLOUD
            </span>
          </div>
          <div className="space-y-3">
            <InfoRow label="Model" value={comparison?.yolo_cloud?.model || 'YOLOv8-pose'} />
            <InfoRow label="Keypoints" value={`${comparison?.yolo_cloud?.keypoints || 17} (COCO)`} />
            <InfoRow label="Runtime" value={comparison?.yolo_cloud?.runtime || 'Cloud (RTSP)'} />
            <InfoRow
              label="Risk Accuracy"
              value={riskMetrics ? `${(riskMetrics.test_accuracy * 100).toFixed(1)}%` : 'N/A'}
              highlight
            />
            <InfoRow
              label="Risk CV F1"
              value={riskMetrics ? `${riskMetrics.cv_f1_mean.toFixed(4)} ± ${riskMetrics.cv_f1_std.toFixed(4)}` : 'N/A'}
            />
            <InfoRow
              label="Task Accuracy"
              value={taskMetrics ? `${(taskMetrics.test_accuracy * 100).toFixed(1)}%` : 'N/A'}
              highlight
            />
            <InfoRow
              label="Task CV F1"
              value={taskMetrics ? `${taskMetrics.cv_f1_mean.toFixed(4)} ± ${taskMetrics.cv_f1_std.toFixed(4)}` : 'N/A'}
            />
            <InfoRow
              label="Training Samples"
              value={riskMetrics ? riskMetrics.n_samples.toLocaleString() : 'N/A'}
            />
          </div>
        </div>

        {/* MediaPipe On-Premise */}
        <div className="rounded-xl border border-emerald-500/20 bg-gradient-to-br from-emerald-500/5 to-emerald-500/10 p-6">
          <div className="mb-4 flex items-center gap-2">
            <Target className="h-5 w-5 text-emerald-400" />
            <h2 className="text-lg font-semibold text-white">MediaPipe Core</h2>
            <span className="rounded-full bg-emerald-500/20 px-2 py-0.5 text-xs text-emerald-400">
              ON-PREMISE
            </span>
          </div>
          <div className="space-y-3">
            <InfoRow label="Model" value={mpMetrics?.model || 'MediaPipe Pose'} />
            <InfoRow label="Keypoints" value={`${mpMetrics?.keypoints || 33} (MediaPipe)`} />
            <InfoRow label="Runtime" value={mpMetrics?.runtime || 'On-premise (USB webcam)'} />
            <InfoRow
              label="Ground-Truth Accuracy"
              value={mpMetrics?.accuracy ? `${(mpMetrics.accuracy * 100).toFixed(1)}%` : 'N/A'}
              highlight
            />
            <InfoRow
              label="Labeled Samples"
              value={mpMetrics?.n_samples?.toLocaleString() || 'N/A'}
            />
            <InfoRow label="Risk Model" value="HistGradientBoosting" />
            <InfoRow label="Task Model" value="HistGradientBoosting v3" />
            <InfoRow label="Calibration" value="RISK_CALIBRATION (relaxed)" />
          </div>
        </div>
      </div>

      {/* Feature Importance */}
      {riskDetail.features && (
        <div className="rounded-xl border border-white/10 bg-white/5 p-6">
          <div className="mb-4 flex items-center gap-2">
            <BarChart3 className="h-5 w-5 text-amber-400" />
            <h2 className="text-lg font-semibold text-white">Risk Model — Feature Importance</h2>
          </div>
          <div className="grid grid-cols-2 gap-2 md:grid-cols-3 lg:grid-cols-4">
            {riskDetail.features.map((f, i) => (
              <div key={f} className="rounded-lg border border-white/5 bg-white/5 px-3 py-2">
                <span className="text-xs text-slate-400">{f.replace(/_/g, ' ')}</span>
                <div className="mt-1 h-1.5 rounded-full bg-white/10">
                  <div
                    className="h-full rounded-full bg-primary"
                    style={{ width: `${Math.max(10, 100 - i * 8)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Task Model Classes */}
      {taskDetail.classes && (
        <div className="rounded-xl border border-white/10 bg-white/5 p-6">
          <div className="mb-4 flex items-center gap-2">
            <CheckCircle2 className="h-5 w-5 text-green-400" />
            <h2 className="text-lg font-semibold text-white">Task Model — Supported Classes</h2>
          </div>
          <div className="flex flex-wrap gap-2">
            {taskDetail.classes.map(cls => (
              <span
                key={cls}
                className="rounded-full border border-green-500/20 bg-green-500/10 px-3 py-1 text-sm text-green-400"
              >
                {cls}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Confusion Matrix */}
      {riskDetail.confusion_matrix && (
        <div className="rounded-xl border border-white/10 bg-white/5 p-6">
          <div className="mb-4 flex items-center gap-2">
            <BarChart3 className="h-5 w-5 text-blue-400" />
            <h2 className="text-lg font-semibold text-white">Risk Model — Confusion Matrix</h2>
          </div>
          <ConfusionMatrix matrix={riskDetail.confusion_matrix} labels={['LOW', 'MEDIUM', 'HIGH']} />
        </div>
      )}

      {/* Architecture Comparison */}
      <div className="rounded-xl border border-white/10 bg-white/5 p-6">
        <h2 className="mb-4 text-lg font-semibold text-white">Architecture Comparison</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/10">
                <th className="px-4 py-2 text-left text-slate-400">Feature</th>
                <th className="px-4 py-2 text-left text-primary">YOLO Cloud</th>
                <th className="px-4 py-2 text-left text-emerald-400">MediaPipe Core</th>
              </tr>
            </thead>
            <tbody className="text-slate-300">
              <TableRow feature="Pose Estimator" yolo="YOLOv8-pose" mp="MediaPipe Pose" />
              <TableRow feature="Keypoints" yolo="17 (COCO)" mp="33 (Full body)" />
              <TableRow feature="Feature Extraction" yolo="Shared (COCO_17 map)" mp="Shared (MediaPipe_33)" />
              <TableRow feature="Task Classifier" yolo="HistGradientBoosting" mp="HistGradientBoosting v3" />
              <TableRow feature="Risk Scorer" yolo="HistGradientBoosting" mp="Calibrated REBA/RULA" />
              <TableRow feature="Input Source" yolo="RTSP CCTV streams" mp="USB webcam / local video" />
              <TableRow feature="Installation" yolo="Zero (cloud SaaS)" mp="Gateway PC required" />
              <TableRow feature="Latency" yolo="200-500ms (cloud)" mp="<100ms (local)" />
              <TableRow feature="Tracking" yolo="ByteTrack" mp="Frame-by-frame" />
              <TableRow feature="Scalability" yolo="100+ cameras" mp="1 camera per gateway" />
            </tbody>
          </table>
        </div>
      </div>

      {/* Model Versioning & Export/Import */}
      <ModelVersioningSection />
    </div>
  );
}

function InfoRow({ label, value, highlight = false }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm text-slate-400">{label}</span>
      <span className={`text-sm font-medium ${highlight ? 'text-white' : 'text-slate-300'}`}>
        {value}
      </span>
    </div>
  );
}

function TableRow({ feature, yolo, mp }: { feature: string; yolo: string; mp: string }) {
  return (
    <tr className="border-b border-white/5">
      <td className="px-4 py-2 font-medium">{feature}</td>
      <td className="px-4 py-2">{yolo}</td>
      <td className="px-4 py-2">{mp}</td>
    </tr>
  );
}

function ConfusionMatrix({ matrix, labels }: { matrix: number[][]; labels: string[] }) {
  const maxVal = Math.max(...matrix.flat());
  return (
    <div className="overflow-x-auto">
      <table className="mx-auto text-sm">
        <thead>
          <tr>
            <th className="px-3 py-1 text-slate-500">Actual ↓ / Pred →</th>
            {labels.map(l => (
              <th key={l} className="px-3 py-1 text-center text-slate-400">{l}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.map((row, i) => (
            <tr key={i}>
              <td className="px-3 py-1 font-medium text-slate-400">{labels[i]}</td>
              {row.map((val, j) => {
                const isDiag = i === j;
                const intensity = val / maxVal;
                return (
                  <td
                    key={j}
                    className={`px-3 py-1 text-center font-mono ${
                      isDiag
                        ? 'bg-green-500/20 text-green-400'
                        : val > 0
                        ? 'bg-red-500/10 text-red-400'
                        : 'text-slate-600'
                    }`}
                    style={{ opacity: 0.3 + intensity * 0.7 }}
                  >
                    {val.toLocaleString()}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ModelVersioningSection() {
  const [versions, setVersions] = useState<any[]>([]);
  const [saving, setSaving] = useState(false);
  const [importing, setImporting] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetch('/cloud-api/cloud/models/versions')
      .then(r => r.json())
      .then(data => setVersions(data.versions || []))
      .catch(() => {});
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      const resp = await fetch('/cloud-api/cloud/models/versions/save', { method: 'POST' });
      const data = await resp.json();
      setVersions(prev => [{
        version_id: data.version_id,
        timestamp: data.timestamp,
        description: 'Manual snapshot',
        files: data.files,
      }, ...prev]);
    } finally {
      setSaving(false);
    }
  };

  const handleExport = async () => {
    const resp = await fetch('/cloud-api/cloud/models/export');
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `yolo_models_${new Date().toISOString().slice(0,10)}.zip`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      await fetch('/cloud-api/cloud/models/import', { method: 'POST', body: formData });
      // Refresh versions
      const resp = await fetch('/cloud-api/cloud/models/versions');
      const data = await resp.json();
      setVersions(data.versions || []);
    } finally {
      setImporting(false);
    }
  };

  const handleRollback = async (versionId: string) => {
    await fetch(`/cloud-api/cloud/models/versions/${versionId}/rollback`, { method: 'POST' });
  };

  return (
    <div className="rounded-xl border border-white/10 bg-white/5 p-6">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <History className="h-5 w-5 text-purple-400" />
          <h2 className="text-lg font-semibold text-white">Model Versioning</h2>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-1.5 rounded-lg bg-primary/20 px-3 py-1.5 text-xs font-medium text-primary hover:bg-primary/30 disabled:opacity-50"
          >
            <Download className="h-3.5 w-3.5" />
            {saving ? 'Saving...' : 'Snapshot'}
          </button>
          <button
            onClick={handleExport}
            className="flex items-center gap-1.5 rounded-lg bg-emerald-500/20 px-3 py-1.5 text-xs font-medium text-emerald-400 hover:bg-emerald-500/30"
          >
            <Download className="h-3.5 w-3.5" />
            Export .zip
          </button>
          <button
            onClick={() => fileRef.current?.click()}
            className="flex items-center gap-1.5 rounded-lg bg-amber-500/20 px-3 py-1.5 text-xs font-medium text-amber-400 hover:bg-amber-500/30"
          >
            <Upload className="h-3.5 w-3.5" />
            {importing ? 'Importing...' : 'Import .zip'}
          </button>
          <input ref={fileRef} type="file" accept=".zip" onChange={handleImport} className="hidden" />
        </div>
      </div>

      {versions.length === 0 ? (
        <p className="text-sm text-slate-500">No versions saved yet. Click Snapshot to save the current models.</p>
      ) : (
        <div className="space-y-2">
          {versions.map(v => (
            <div key={v.version_id} className="flex items-center justify-between rounded-lg border border-white/5 bg-white/5 px-4 py-2">
              <div>
                <span className="font-mono text-sm text-white">{v.version_id}</span>
                <span className="ml-2 text-xs text-slate-500">{v.description || 'Auto snapshot'}</span>
                <span className="ml-2 text-xs text-slate-600">
                  ({v.files?.length || 0} files)
                </span>
              </div>
              <button
                onClick={() => handleRollback(v.version_id)}
                className="flex items-center gap-1 rounded px-2 py-1 text-xs text-slate-400 hover:bg-white/5 hover:text-white"
              >
                <RotateCcw className="h-3 w-3" />
                Rollback
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
