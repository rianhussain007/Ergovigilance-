import { useState, useEffect, useCallback } from 'react';
import {
  Cloud,
  Wifi,
  WifiOff,
  CheckCircle,
  XCircle,
  RefreshCw,
  Cpu,
  Camera,
  Gauge,
  Activity,
  Server,
  Shield,
  Zap,
  AlertTriangle,
  Info,
  Save,
  Play,
  Square,
  Eye,
} from 'lucide-react';

// Cloud settings are fetched from the cloud-core health endpoint
interface CloudHealth {
  status: string;
  engine: string;
  model: string;
  device: string;
  cameras_configured: number;
  cameras_active: number;
}

interface CloudSettingsState {
  yoloModel: string;
  yoloDevice: string;
  yoloConfidence: number;
  inferenceFps: number;
  rtspTransport: string;
  rtspTimeout: number;
  rtspReconnectDelay: number;
  sessionIdleTimeout: number;
  // Connection tester
  testRtspUrl: string;
  testResult: 'idle' | 'testing' | 'success' | 'error';
  testMessage: string;
}

const YOLO_MODELS = [
  { value: 'yolov8n-pose.pt', label: 'YOLOv8n-pose (Nano)', desc: 'Fastest, lowest accuracy' },
  { value: 'yolov8s-pose.pt', label: 'YOLOv8s-pose (Small)', desc: 'Best speed/accuracy balance' },
  { value: 'yolov8m-pose.pt', label: 'YOLOv8m-pose (Medium)', desc: 'Higher accuracy, slower' },
  { value: 'yolov8l-pose.pt', label: 'YOLOv8l-pose (Large)', desc: 'High accuracy, slow' },
  { value: 'yolov8x-pose.pt', label: 'YOLOv8x-pose (XLarge)', desc: 'Highest accuracy, slowest' },
];

const DEVICES = [
  { value: 'cpu', label: 'CPU', desc: 'No GPU required, slower inference' },
  { value: '0', label: 'GPU 0 (CUDA)', desc: 'First NVIDIA GPU' },
  { value: '1', label: 'GPU 1 (CUDA)', desc: 'Second NVIDIA GPU' },
  { value: 'cuda:0', label: 'CUDA:0', desc: 'Explicit CUDA device 0' },
];

const RTSP_TRANSPORTS = [
  { value: 'tcp', label: 'TCP', desc: 'Reliable, higher latency' },
  { value: 'udp', label: 'UDP', desc: 'Lower latency, may lose frames' },
];

export default function CloudSettingsPage() {
  const [health, setHealth] = useState<CloudHealth | null>(null);
  const [settings, setSettings] = useState<CloudSettingsState>({
    yoloModel: 'yolov8s-pose.pt',
    yoloDevice: 'cpu',
    yoloConfidence: 0.5,
    inferenceFps: 10,
    rtspTransport: 'tcp',
    rtspTimeout: 5,
    rtspReconnectDelay: 2.0,
    sessionIdleTimeout: 60,
    testRtspUrl: '',
    testResult: 'idle',
    testMessage: '',
  });
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState('');
  const [cameraCount, setCameraCount] = useState(0);

  const fetchHealth = useCallback(async () => {
    try {
      const res = await fetch('/cloud-api/cloud/health');
      if (res.ok) {
        const data = await res.json();
        setHealth(data);
        setSettings((prev) => ({
          ...prev,
          yoloModel: data.model || prev.yoloModel,
          yoloDevice: data.device || prev.yoloDevice,
        }));
      }
    } catch {
      setHealth(null);
    }
  }, []);

  const fetchCameras = useCallback(async () => {
    try {
      const res = await fetch('/cloud-api/cloud/cameras');
      if (res.ok) {
        const data = await res.json();
        setCameraCount(data.cameras?.length || 0);
      }
    } catch {
      // Cloud core not running
    }
  }, []);

  useEffect(() => {
    fetchHealth();
    fetchCameras();
    const interval = setInterval(() => {
      fetchHealth();
      fetchCameras();
    }, 10000);
    return () => clearInterval(interval);
  }, [fetchHealth, fetchCameras]);

  const handleSave = async () => {
    // Persisted to the cloud core (config/cloud_settings.json); every knob
    // needs a service restart — the confirmation says so explicitly.
    setSaveError('');
    try {
      const res = await fetch('/cloud-api/cloud/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          YOLO_MODEL: settings.yoloModel,
          YOLO_DEVICE: settings.yoloDevice,
          YOLO_CONFIDENCE: settings.yoloConfidence,
          INFERENCE_FPS: settings.inferenceFps,
          RTSP_TRANSPORT: settings.rtspTransport,
          RTSP_TIMEOUT: settings.rtspTimeout,
          RTSP_RECONNECT_DELAY: settings.rtspReconnectDelay,
          SESSION_IDLE_TIMEOUT: settings.sessionIdleTimeout,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Save failed' }));
        setSaveError(err.detail || 'Save failed. Is the cloud core running?');
        return;
      }
      setSaved(true);
      setTimeout(() => setSaved(false), 5000);
    } catch {
      setSaveError('Cloud core unreachable — settings not saved.');
    }
  };

  const handleTestConnection = async () => {
    if (!settings.testRtspUrl.trim()) return;

    setSettings((prev) => ({ ...prev, testResult: 'testing', testMessage: 'Testing RTSP connection...' }));

    try {
      // Try to add camera temporarily to test connectivity
      const res = await fetch('/cloud-api/cloud/cameras', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: `test-${Date.now()}`,
          name: 'Connection Test',
          url: settings.testRtspUrl.trim(),
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setSettings((prev) => ({
          ...prev,
          testResult: 'success',
          testMessage: `Connected! Camera started (ID: ${data.camera_id || 'unknown'}). Streams ${data.frames_per_second || '?'} FPS.`,
        }));
        // Remove test camera after 3 seconds
        setTimeout(async () => {
          try {
            await fetch(`/cloud-api/cloud/cameras/test-${Date.now() - 5000}`, { method: 'DELETE' });
          } catch {
            // Ignore cleanup errors
          }
        }, 3000);
      } else {
        const errData = await res.json().catch(() => ({ detail: 'Connection failed' }));
        setSettings((prev) => ({
          ...prev,
          testResult: 'error',
          testMessage: errData.detail || 'Failed to connect. Check the RTSP URL and network.',
        }));
      }
    } catch (err) {
      setSettings((prev) => ({
        ...prev,
        testResult: 'error',
        testMessage: `Cloud core unreachable. Is the service running? (${err instanceof Error ? err.message : 'unknown error'})`,
      }));
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <Cloud className="w-7 h-7 text-cyan-400" />
            Cloud Core Settings
          </h1>
          <p className="text-slate-400 mt-1">
            Configure the YOLO Cloud inference engine for RTSP camera streams
          </p>
        </div>
        <button
          onClick={handleSave}
          className="flex items-center gap-2 px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg transition-colors"
        >
          <Save className="w-4 h-4" />
          {saved ? 'Saved — restart core to apply' : 'Save Settings'}
        </button>
      </div>
      {saveError && (
        <p className="mt-2 text-sm text-red-400">{saveError}</p>
      )}

      {/* Health Status */}
      <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-5">
        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Activity className="w-5 h-5 text-green-400" />
          Service Status
        </h2>
        {health ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatusCard
              icon={<Server className="w-4 h-4" />}
              label="Status"
              value={health.status === 'healthy' ? 'Online' : 'Degraded'}
              color={health.status === 'healthy' ? 'green' : 'amber'}
            />
            <StatusCard
              icon={<Cpu className="w-4 h-4" />}
              label="Engine"
              value={health.engine}
              color="cyan"
            />
            <StatusCard
              icon={<Zap className="w-4 h-4" />}
              label="Device"
              value={health.device === 'cpu' ? 'CPU' : `GPU ${health.device}`}
              color={health.device === 'cpu' ? 'slate' : 'green'}
            />
            <StatusCard
              icon={<Camera className="w-4 h-4" />}
              label="Cameras"
              value={`${health.cameras_active} / ${health.cameras_configured}`}
              color="blue"
            />
          </div>
        ) : (
          <div className="flex items-center gap-3 text-amber-400 bg-amber-500/10 rounded-lg p-4">
            <AlertTriangle className="w-5 h-5" />
            <span>Cloud core service is not running. Start it with: <code className="bg-black/30 px-2 py-0.5 rounded text-sm">docker compose up cloud-core</code></span>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* YOLO Model Settings */}
        <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-5">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Cpu className="w-5 h-5 text-cyan-400" />
            Inference Engine
          </h2>

          <div className="space-y-4">
            {/* Model Selection */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1.5">YOLO Model</label>
              <select
                value={settings.yoloModel}
                onChange={(e) => setSettings((prev) => ({ ...prev, yoloModel: e.target.value }))}
                className="w-full bg-slate-900/50 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:border-cyan-500 focus:outline-none"
              >
                {YOLO_MODELS.map((m) => (
                  <option key={m.value} value={m.value}>
                    {m.label} — {m.desc}
                  </option>
                ))}
              </select>
              <p className="text-xs text-slate-500 mt-1">
                Larger models = higher accuracy but slower inference. Start with Small.
              </p>
            </div>

            {/* Device */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1.5">Compute Device</label>
              <select
                value={settings.yoloDevice}
                onChange={(e) => setSettings((prev) => ({ ...prev, yoloDevice: e.target.value }))}
                className="w-full bg-slate-900/50 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:border-cyan-500 focus:outline-none"
              >
                {DEVICES.map((d) => (
                  <option key={d.value} value={d.value}>
                    {d.label} — {d.desc}
                  </option>
                ))}
              </select>
            </div>

            {/* Confidence Threshold */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1.5">
                Confidence Threshold: {(settings.yoloConfidence * 100).toFixed(0)}%
              </label>
              <input
                type="range"
                min="0.1"
                max="0.95"
                step="0.05"
                value={settings.yoloConfidence}
                onChange={(e) => setSettings((prev) => ({ ...prev, yoloConfidence: parseFloat(e.target.value) }))}
                className="w-full accent-cyan-500"
              />
              <div className="flex justify-between text-xs text-slate-500">
                <span>10% (detect more)</span>
                <span>95% (higher precision)</span>
              </div>
            </div>

            {/* Inference FPS */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1.5">
                Inference FPS: {settings.inferenceFps}
              </label>
              <input
                type="range"
                min="1"
                max="30"
                step="1"
                value={settings.inferenceFps}
                onChange={(e) => setSettings((prev) => ({ ...prev, inferenceFps: parseInt(e.target.value) }))}
                className="w-full accent-cyan-500"
              />
              <div className="flex justify-between text-xs text-slate-500">
                <span>1 FPS (low CPU)</span>
                <span>30 FPS (real-time)</span>
              </div>
              <p className="text-xs text-slate-500 mt-1">
                Lower = less CPU/GPU usage. 10 FPS is recommended for risk scoring.
              </p>
            </div>
          </div>
        </div>

        {/* RTSP Settings */}
        <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-5">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Camera className="w-5 h-5 text-blue-400" />
            RTSP Ingestion
          </h2>

          <div className="space-y-4">
            {/* Transport Protocol */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1.5">Transport Protocol</label>
              <div className="grid grid-cols-2 gap-2">
                {RTSP_TRANSPORTS.map((t) => (
                  <button
                    key={t.value}
                    onClick={() => setSettings((prev) => ({ ...prev, rtspTransport: t.value }))}
                    className={`p-3 rounded-lg border text-left transition-colors ${
                      settings.rtspTransport === t.value
                        ? 'border-cyan-500 bg-cyan-500/10 text-white'
                        : 'border-slate-600 bg-slate-900/30 text-slate-400 hover:border-slate-500'
                    }`}
                  >
                    <div className="font-medium text-sm">{t.label}</div>
                    <div className="text-xs text-slate-500 mt-0.5">{t.desc}</div>
                  </button>
                ))}
              </div>
            </div>

            {/* Timeout */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1.5">
                Connection Timeout: {settings.rtspTimeout}s
              </label>
              <input
                type="range"
                min="2"
                max="30"
                step="1"
                value={settings.rtspTimeout}
                onChange={(e) => setSettings((prev) => ({ ...prev, rtspTimeout: parseInt(e.target.value) }))}
                className="w-full accent-blue-500"
              />
            </div>

            {/* Reconnect Delay */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1.5">
                Reconnect Delay: {settings.rtspReconnectDelay}s
              </label>
              <input
                type="range"
                min="0.5"
                max="10"
                step="0.5"
                value={settings.rtspReconnectDelay}
                onChange={(e) => setSettings((prev) => ({ ...prev, rtspReconnectDelay: parseFloat(e.target.value) }))}
                className="w-full accent-blue-500"
              />
            </div>

            {/* Session Idle Timeout */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1.5">
                Session Idle Timeout: {settings.sessionIdleTimeout}s
              </label>
              <input
                type="range"
                min="30"
                max="300"
                step="30"
                value={settings.sessionIdleTimeout}
                onChange={(e) => setSettings((prev) => ({ ...prev, sessionIdleTimeout: parseInt(e.target.value) }))}
                className="w-full accent-blue-500"
              />
              <p className="text-xs text-slate-500 mt-1">
                Auto-close session after this many seconds of no persons detected.
              </p>
            </div>

            {/* Info box */}
            <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-3 flex gap-2 text-sm text-blue-300">
              <Info className="w-4 h-4 mt-0.5 shrink-0" />
                <span>
                  <strong>{cameraCount}</strong> camera{cameraCount !== 1 ? 's' : ''} configured.
                  Each RTSP stream consumes ~2-8 Mbps of network bandwidth depending on resolution.
                </span>
            </div>
          </div>
        </div>
      </div>

      {/* Connection Tester */}
      <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-5">
        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Wifi className="w-5 h-5 text-green-400" />
          RTSP Connection Tester
        </h2>
        <p className="text-sm text-slate-400 mb-4">
          Test an RTSP camera URL before adding it to the monitoring fleet.
          Paste your camera's RTSP stream URL and click Test.
        </p>

        <div className="flex gap-3">
          <input
            type="text"
            value={settings.testRtspUrl}
            onChange={(e) => setSettings((prev) => ({ ...prev, testRtspUrl: e.target.value }))}
            placeholder="rtsp://admin:password@192.168.1.100:554/stream1"
            className="flex-1 bg-slate-900/50 border border-slate-600 rounded-lg px-4 py-2.5 text-white text-sm font-mono placeholder-slate-600 focus:border-green-500 focus:outline-none"
            onKeyDown={(e) => e.key === 'Enter' && handleTestConnection()}
          />
          <button
            onClick={handleTestConnection}
            disabled={settings.testResult === 'testing' || !settings.testRtspUrl.trim()}
            className="flex items-center gap-2 px-5 py-2.5 bg-green-600 hover:bg-green-500 disabled:bg-slate-600 disabled:cursor-not-allowed text-white rounded-lg transition-colors text-sm font-medium"
          >
            {settings.testResult === 'testing' ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                Testing...
              </>
            ) : (
              <>
                <Play className="w-4 h-4" />
                Test Connection
              </>
            )}
          </button>
        </div>

        {/* Test Result */}
        {settings.testResult !== 'idle' && settings.testResult !== 'testing' && (
          <div
            className={`mt-4 rounded-lg p-4 flex items-start gap-3 text-sm ${
              settings.testResult === 'success'
                ? 'bg-green-500/10 border border-green-500/20 text-green-300'
                : 'bg-red-500/10 border border-red-500/20 text-red-300'
            }`}
          >
            {settings.testResult === 'success' ? (
              <CheckCircle className="w-5 h-5 mt-0.5 shrink-0" />
            ) : (
              <XCircle className="w-5 h-5 mt-0.5 shrink-0" />
            )}
            <span>{settings.testMessage}</span>
          </div>
        )}

        {/* Common RTSP URL formats */}
        <div className="mt-4 text-xs text-slate-500">
          <p className="font-medium text-slate-400 mb-1">Common RTSP URL formats:</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-1">
            <code className="bg-black/20 px-2 py-0.5 rounded">rtsp://admin:pass@192.168.1.100:554/stream1</code>
            <code className="bg-black/20 px-2 py-0.5 rounded">rtsp://192.168.1.100:554/CH001</code>
            <code className="bg-black/20 px-2 py-0.5 rounded">rtsp://user:pass@camera.local/live</code>
            <code className="bg-black/20 px-2 py-0.5 rounded">rtmp://camera.local/live/stream</code>
          </div>
        </div>
      </div>

      {/* Webhooks */}
      <WebhookSection />

      {/* Deployment Tips */}
      <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-5">
        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Shield className="w-5 h-5 text-purple-400" />
          Deployment Notes
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm text-slate-300">
          <div className="space-y-2">
            <h3 className="font-medium text-white">Hardware Requirements</h3>
            <ul className="space-y-1 text-slate-400">
              <li>• <strong>CPU-only:</strong> 4+ cores to start; validate camera count on your hardware (unmeasured)</li>
              <li>• <strong>NVIDIA T4 / A10:</strong> GPU helps, but no GPU capacity numbers have been measured — pilot your stream count first</li>
              <li>• <strong>RAM:</strong> 2 GB base + 200 MB per active camera</li>
            </ul>
          </div>
          <div className="space-y-2">
            <h3 className="font-medium text-white">Network Requirements</h3>
            <ul className="space-y-1 text-slate-400">
              <li>• Each 1080p stream: ~4-8 Mbps</li>
              <li>• Each 720p stream: ~2-4 Mbps</li>
              <li>• Use VLAN/isolation for camera traffic</li>
              <li>• Cloud core should be in same datacenter as cameras</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}

function WebhookSection() {
  const [webhooks, setWebhooks] = useState<any[]>([]);
  const [showAdd, setShowAdd] = useState(false);
  const [newWebhook, setNewWebhook] = useState({ name: '', url: '' });
  const [testResult, setTestResult] = useState<'idle' | 'testing' | 'success' | 'error'>('idle');
  const [testMessage, setTestMessage] = useState('');

  const fetchWebhooks = async () => {
    try {
      const res = await fetch('/cloud-api/cloud/webhooks');
      if (res.ok) {
        const data = await res.json();
        setWebhooks(data.webhooks || []);
      }
    } catch {
      // Cloud core not running
    }
  };

  useEffect(() => { fetchWebhooks(); }, []);

  const handleAdd = async () => {
    if (!newWebhook.url) return;
    try {
      const res = await fetch('/cloud-api/cloud/webhooks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: newWebhook.name || 'Webhook',
          url: newWebhook.url,
          events: ['alert.fired'],
        }),
      });
      if (res.ok) {
        setNewWebhook({ name: '', url: '' });
        setShowAdd(false);
        fetchWebhooks();
      }
    } catch {
      // ignore
    }
  };

  const handleTest = async (url: string) => {
    setTestResult('testing');
    setTestMessage('');
    try {
      const res = await fetch('/cloud-api/cloud/webhooks/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      });
      const data = await res.json();
      setTestResult(data.success ? 'success' : 'error');
      setTestMessage(data.message);
    } catch {
      setTestResult('error');
      setTestMessage('Network error');
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await fetch(`/cloud-api/cloud/webhooks/${id}`, { method: 'DELETE' });
      fetchWebhooks();
    } catch {
      // ignore
    }
  };

  return (
    <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-white flex items-center gap-2">
          <Zap className="w-5 h-5 text-amber-400" />
          Webhooks
        </h2>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="text-xs px-3 py-1.5 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400 hover:bg-amber-500/20 transition"
        >
          {showAdd ? 'Cancel' : '+ Add Webhook'}
        </button>
      </div>
      <p className="text-sm text-slate-400 mb-4">
        Receive HTTP POST notifications when alerts are fired. Webhooks include HMAC-SHA256 signatures for verification.
      </p>

      {showAdd && (
        <div className="mb-4 p-4 rounded-lg bg-slate-900/50 border border-slate-600/30 space-y-3">
          <input
            value={newWebhook.name}
            onChange={e => setNewWebhook({ ...newWebhook, name: e.target.value })}
            placeholder="Webhook name (e.g., Slack, PagerDuty)"
            className="w-full px-3 py-2 rounded-lg bg-black/40 border border-white/10 text-white text-sm focus:outline-none focus:border-amber-500"
          />
          <input
            value={newWebhook.url}
            onChange={e => setNewWebhook({ ...newWebhook, url: e.target.value })}
            placeholder="https://hooks.slack.com/services/..."
            className="w-full px-3 py-2 rounded-lg bg-black/40 border border-white/10 text-white text-sm font-mono focus:outline-none focus:border-amber-500"
          />
          <div className="flex gap-2">
            <button onClick={handleAdd} disabled={!newWebhook.url} className="px-4 py-2 rounded-lg bg-amber-500 text-white text-sm font-medium hover:bg-amber-400 transition disabled:opacity-50">Save Webhook</button>
            <button onClick={() => { if (newWebhook.url) handleTest(newWebhook.url); }} disabled={!newWebhook.url || testResult === 'testing'} className="px-4 py-2 rounded-lg bg-slate-600 text-white text-sm hover:bg-slate-500 transition disabled:opacity-50">Test</button>
          </div>
          {testResult !== 'idle' && testResult !== 'testing' && (
            <p className={`text-xs ${testResult === 'success' ? 'text-green-400' : 'text-red-400'}`}>{testMessage}</p>
          )}
        </div>
      )}

      {webhooks.length === 0 ? (
        <p className="text-sm text-slate-500 py-4">No webhooks configured.</p>
      ) : (
        <div className="space-y-2">
          {webhooks.map((wh) => (
            <div key={wh.webhook_id} className="flex items-center justify-between p-3 rounded-lg bg-slate-900/30 border border-slate-700/30">
              <div className="min-w-0">
                <p className="text-sm text-white font-medium">{wh.name || 'Unnamed'}</p>
                <p className="text-xs text-slate-500 font-mono truncate">{wh.url}</p>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <button onClick={() => handleTest(wh.url)} className="text-xs px-2 py-1 rounded bg-slate-600 text-slate-300 hover:bg-slate-500 transition">Test</button>
                <button onClick={() => handleDelete(wh.webhook_id)} className="text-xs px-2 py-1 rounded bg-red-500/10 text-red-400 hover:bg-red-500/20 transition">Delete</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function StatusCard({
  icon,
  label,
  value,
  color,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  color: string;
}) {
  const colorMap: Record<string, string> = {
    green: 'text-green-400 bg-green-500/10',
    cyan: 'text-cyan-400 bg-cyan-500/10',
    blue: 'text-blue-400 bg-blue-500/10',
    amber: 'text-amber-400 bg-amber-500/10',
    red: 'text-red-400 bg-red-500/10',
    slate: 'text-slate-400 bg-slate-500/10',
  };

  return (
    <div className="bg-slate-900/50 rounded-lg p-3 border border-slate-700/30">
      <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
        {icon}
        {label}
      </div>
      <div className={`font-semibold text-sm ${colorMap[color]?.split(' ')[0] || 'text-white'}`}>
        {value}
      </div>
    </div>
  );
}
