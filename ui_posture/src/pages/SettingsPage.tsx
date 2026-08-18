import React, { useEffect, useState } from 'react';
import { 
  Sun, Moon, Monitor, Camera, RefreshCw, Bell, Save, HardDrive, 
  AlertTriangle, Brain, Activity, Cpu, Zap, FileText, BarChart3, 
  Users, Settings as SettingsIcon, ToggleLeft, ToggleRight
} from 'lucide-react';
import { useTheme } from '@/src/hooks/useTheme';
import { useToast } from '@/src/hooks/useToast';
import { useAuth } from '@/src/auth/AuthContext';
import { useSettings } from '@/src/hooks/useSettings';
import { getCameras, getRetentionStats, updateRetentionConfig } from '@/src/services/dashboardService';
import ModelDiagnosticsCard from '@/src/components/common/ModelDiagnosticsCard';
import type { CameraInfo } from '@/src/types/api';

export default function SettingsPage() {
  const { setMode } = useTheme();
  const { addToast } = useToast();
  const { user } = useAuth();
  const { settings, updateSetting, saveSettings, dirty } = useSettings();
  const canEditSystemSettings = user?.role === 'admin';
  const [cameras, setCameras] = useState<CameraInfo[]>([]);
  const [loadingCameras, setLoadingCameras] = useState(true);
  const [retentionDays, setRetentionDays] = useState<number | null>(null);
  const [retentionDirty, setRetentionDirty] = useState(false);
  const [retentionBusy, setRetentionBusy] = useState(false);

  // Load cameras for dropdown
  useEffect(() => {
    let cancelled = false;
    getCameras()
      .then((data) => {
        if (!cancelled) {
          setCameras(data);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setCameras([]);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingCameras(false);
        }
      });
    return () => { cancelled = true; };
  }, []);

  // Load the real retention policy from the backend so the admin control
  // reflects the actual enforcement value (not a stale local pref).
  useEffect(() => {
    if (!canEditSystemSettings) return;
    let cancelled = false;
    getRetentionStats()
      .then((stats) => {
        if (!cancelled && stats?.policy?.session_retention_days != null) {
          setRetentionDays(stats.policy.session_retention_days);
        }
      })
      .catch(() => { /* backend may be offline — keep local pref */ });
    return () => { cancelled = true; };
  }, [canEditSystemSettings]);

  const handleSave = async () => {
    // Theme is already applied in real-time via setMode() in the onClick handler.
    saveSettings();

    // Push the retention policy to the backend when the admin changed it.
    if (canEditSystemSettings && retentionDirty && retentionDays != null) {
      setRetentionBusy(true);
      try {
        const resp = await updateRetentionConfig({ session_retention_days: retentionDays, recording_retention_days: retentionDays });
        setRetentionDirty(false);
        addToast('success', 'Settings saved', `Data retention policy updated to ${resp.policy.session_retention_days} days`);
      } catch (e) {
        addToast('error', 'Retention update failed', e instanceof Error ? e.message : 'Could not reach the backend');
      } finally {
        setRetentionBusy(false);
      }
      return;
    }
    addToast('success', 'Settings saved');
  };

  return (
    <div className="p-lg space-y-lg pb-32 max-w-4xl">
      <div>
        <h1 className="text-display-lg font-bold text-on-surface">Settings</h1>
        <p className="text-body-sm text-on-surface-variant mt-xs">Configure your dashboard, monitoring, and deployment preferences</p>
      </div>

      <div className="space-y-md">
        {/* ── Appearance Section ──────────────────────────────── */}
        <div className="border-b border-outline-variant/30 pb-md">
          <div className="flex items-center gap-sm mb-md">
            <SettingsIcon className="w-5 h-5 text-primary" />
            <h2 className="text-headline-md font-bold text-on-surface">Appearance</h2>
          </div>
        </div>

        <SettingSection icon={Sun} title="Theme">
          <div className="flex gap-sm flex-wrap">
            {(['dark', 'light', 'system'] as const).map((t) => {
              const Icon = t === 'dark' ? Moon : t === 'light' ? Sun : Monitor;
              return (
                <button key={t} onClick={() => {
                  updateSetting('theme', t);
                  setMode(t);  // Apply theme immediately
                }} className={`flex items-center gap-sm px-md py-sm rounded-lg border text-body-sm font-medium transition-all ${settings.theme === t ? 'border-primary/50 bg-primary/10 text-primary' : 'border-outline-variant text-on-surface-variant hover:text-on-surface'}`}>
                  <Icon className="w-4 h-4" />{t.charAt(0).toUpperCase() + t.slice(1)}
                </button>
              );
            })}
          </div>
        </SettingSection>

        <SettingSection icon={BarChart3} title="Display">
          <div className="space-y-sm w-full">
            <div className="flex items-center justify-between">
              <span className="text-body-sm text-on-surface-variant">Chart Animations</span>
              <button onClick={() => updateSetting('chartAnimation', !settings.chartAnimation)} className="relative w-12 h-6 rounded-full transition-colors">
                {settings.chartAnimation ? (
                  <ToggleRight className="w-12 h-6 text-primary" />
                ) : (
                  <ToggleLeft className="w-12 h-6 text-on-surface-variant" />
                )}
              </button>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-body-sm text-on-surface-variant">Timeline Granularity</span>
              <select
                value={settings.timelineGranularity}
                onChange={(e) => updateSetting('timelineGranularity', e.target.value as 'seconds' | 'minutes' | 'hours')}
                className="bg-surface-container-high border border-outline-variant rounded-lg px-md py-sm text-body-sm text-on-surface outline-none focus:border-primary/50"
              >
                <option value="seconds">Seconds</option>
                <option value="minutes">Minutes</option>
                <option value="hours">Hours</option>
              </select>
            </div>
          </div>
        </SettingSection>

        {/* ── Monitoring Section ──────────────────────────────── */}
        <div className="border-b border-outline-variant/30 pt-md pb-md">
          <div className="flex items-center gap-sm mb-md">
            <Camera className="w-5 h-5 text-primary" />
            <h2 className="text-headline-md font-bold text-on-surface">Monitoring</h2>
          </div>
        </div>

        <SettingSection icon={Camera} title="Camera">
          {loadingCameras ? (
            <div className="text-body-sm text-on-surface-variant">Loading cameras...</div>
          ) : (
            <select value={settings.cameraId} onChange={(e) => updateSetting('cameraId', e.target.value)} className="bg-surface-container-high border border-outline-variant rounded-lg px-md py-sm text-body-sm text-on-surface outline-none focus:border-primary/50">
              {cameras.length === 0 ? (
                <option value="0">No cameras detected</option>
              ) : (
                cameras.map((cam) => (
                  <option key={cam.id} value={cam.id}>
                    {cam.name} — {cam.fps}fps
                  </option>
                ))
              )}
            </select>
          )}
          <a
            href="/setup"
            className="mt-sm inline-flex items-center gap-sm rounded-lg border border-primary/40 bg-primary/10 px-md py-sm text-body-sm font-bold text-primary hover:bg-primary/20 transition-colors"
          >
            <Camera className="w-4 h-4" />
            Open Camera Setup Wizard
          </a>
        </SettingSection>

        <SettingSection icon={Activity} title="Performance">
          <div className="space-y-sm w-full">
            <div className="flex items-center justify-between">
              <span className="text-body-sm text-on-surface-variant">Target FPS</span>
              <select
                value={settings.targetFps}
                onChange={(e) => updateSetting('targetFps', Number(e.target.value))}
                className="bg-surface-container-high border border-outline-variant rounded-lg px-md py-sm text-body-sm text-on-surface outline-none focus:border-primary/50"
              >
                <option value={5}>5 FPS (Low CPU)</option>
                <option value={10}>10 FPS (Balanced)</option>
                <option value={15}>15 FPS (Default)</option>
                <option value={20}>20 FPS (High)</option>
                <option value={30}>30 FPS (Maximum)</option>
              </select>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-body-sm text-on-surface-variant">Feature Smoothing</span>
              <div className="flex items-center gap-2">
                <input
                  type="range"
                  min="0.1"
                  max="1.0"
                  step="0.1"
                  value={settings.featureSmoothing}
                  onChange={(e) => updateSetting('featureSmoothing', Number(e.target.value))}
                  className="w-24 accent-primary"
                />
                <span className="text-body-sm text-on-surface-variant w-8">{settings.featureSmoothing}</span>
              </div>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-body-sm text-on-surface-variant">Kalman Filter</span>
              <button onClick={() => updateSetting('kalmanFilter', !settings.kalmanFilter)} className="relative w-12 h-6 rounded-full transition-colors">
                {settings.kalmanFilter ? (
                  <ToggleRight className="w-12 h-6 text-primary" />
                ) : (
                  <ToggleLeft className="w-12 h-6 text-on-surface-variant" />
                )}
              </button>
            </div>
          </div>
        </SettingSection>

        <SettingSection icon={RefreshCw} title="Refresh Interval">
          <select value={settings.refreshInterval} onChange={(e) => updateSetting('refreshInterval', Number(e.target.value))} className="bg-surface-container-high border border-outline-variant rounded-lg px-md py-sm text-body-sm text-on-surface outline-none focus:border-primary/50">
            <option value={10}>10 seconds</option>
            <option value={30}>30 seconds</option>
            <option value={60}>1 minute</option>
            <option value={300}>5 minutes</option>
          </select>
        </SettingSection>

        {/* ── Notifications Section ──────────────────────────────── */}
        <div className="border-b border-outline-variant/30 pt-md pb-md">
          <div className="flex items-center gap-sm mb-md">
            <Bell className="w-5 h-5 text-primary" />
            <h2 className="text-headline-md font-bold text-on-surface">Notifications</h2>
          </div>
        </div>

        <SettingSection icon={Bell} title="Alerts">
          <div className="space-y-sm w-full">
            <div className="flex items-center justify-between">
              <span className="text-body-sm text-on-surface-variant">Enable Notifications</span>
              <button onClick={() => updateSetting('notifications', !settings.notifications)} className="relative w-12 h-6 rounded-full transition-colors">
                {settings.notifications ? (
                  <ToggleRight className="w-12 h-6 text-primary" />
                ) : (
                  <ToggleLeft className="w-12 h-6 text-on-surface-variant" />
                )}
              </button>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-body-sm text-on-surface-variant">Alert Threshold</span>
              <select
                value={settings.alertThreshold}
                onChange={(e) => updateSetting('alertThreshold', e.target.value as 'low' | 'moderate' | 'high')}
                className="bg-surface-container-high border border-outline-variant rounded-lg px-md py-sm text-body-sm text-on-surface outline-none focus:border-primary/50"
              >
                <option value="low">Low (All alerts)</option>
                <option value="moderate">Moderate (Medium+)</option>
                <option value="high">High (Critical/High only)</option>
              </select>
            </div>
          </div>
        </SettingSection>

        {/* ── AI & Analytics Section ──────────────────────────────── */}
        <div className="border-b border-outline-variant/30 pt-md pb-md">
          <div className="flex items-center gap-sm mb-md">
            <Brain className="w-5 h-5 text-primary" />
            <h2 className="text-headline-md font-bold text-on-surface">AI & Analytics</h2>
          </div>
        </div>

        <SettingSection icon={Brain} title="AI Assistant">
          <div className="space-y-sm w-full">
            <div className="flex items-center justify-between">
              <span className="text-body-sm text-on-surface-variant">Enable AI Explanations</span>
              <button onClick={() => updateSetting('aiExplanation', !settings.aiExplanation)} className="relative w-12 h-6 rounded-full transition-colors">
                {settings.aiExplanation ? (
                  <ToggleRight className="w-12 h-6 text-primary" />
                ) : (
                  <ToggleLeft className="w-12 h-6 text-on-surface-variant" />
                )}
              </button>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-body-sm text-on-surface-variant">Ollama Model</span>
              <select
                value={settings.ollamaModel}
                onChange={(e) => updateSetting('ollamaModel', e.target.value)}
                className="bg-surface-container-high border border-outline-variant rounded-lg px-md py-sm text-body-sm text-on-surface outline-none focus:border-primary/50"
              >
                <option value="qwen2.5:1.5b">Qwen 2.5 1.5B (Fast)</option>
                <option value="qwen2.5:7b">Qwen 2.5 7B (Balanced)</option>
                <option value="llama3.2:3b">Llama 3.2 3B (Balanced)</option>
                <option value="gemma2:2b">Gemma 2 2B (Fast)</option>
              </select>
            </div>
          </div>
        </SettingSection>

        {/* ── Export Section ──────────────────────────────── */}
        <div className="border-b border-outline-variant/30 pt-md pb-md">
          <div className="flex items-center gap-sm mb-md">
            <FileText className="w-5 h-5 text-primary" />
            <h2 className="text-headline-md font-bold text-on-surface">Export</h2>
          </div>
        </div>

        <SettingSection icon={FileText} title="Export Options">
          <div className="space-y-sm w-full">
            <div className="flex items-center justify-between">
              <span className="text-body-sm text-on-surface-variant">Default Format</span>
              <select
                value={settings.defaultExportFormat}
                onChange={(e) => updateSetting('defaultExportFormat', e.target.value as 'pdf' | 'csv' | 'json')}
                className="bg-surface-container-high border border-outline-variant rounded-lg px-md py-sm text-body-sm text-on-surface outline-none focus:border-primary/50"
              >
                <option value="pdf">PDF Report</option>
                <option value="csv">CSV Data</option>
                <option value="json">JSON Raw</option>
              </select>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-body-sm text-on-surface-variant">Auto-Export After Session</span>
              <button onClick={() => updateSetting('autoExport', !settings.autoExport)} className="relative w-12 h-6 rounded-full transition-colors">
                {settings.autoExport ? (
                  <ToggleRight className="w-12 h-6 text-primary" />
                ) : (
                  <ToggleLeft className="w-12 h-6 text-on-surface-variant" />
                )}
              </button>
            </div>
          </div>
        </SettingSection>

        {/* ── Worker Section ──────────────────────────────── */}
        <div className="border-b border-outline-variant/30 pt-md pb-md">
          <div className="flex items-center gap-sm mb-md">
            <Users className="w-5 h-5 text-primary" />
            <h2 className="text-headline-md font-bold text-on-surface">Worker</h2>
          </div>
        </div>

        <SettingSection icon={Users} title="Worker Settings">
          <div className="space-y-sm w-full">
            <div className="flex items-center justify-between">
              <span className="text-body-sm text-on-surface-variant">Default Worker ID</span>
              <input
                type="text"
                value={settings.defaultWorkerId}
                onChange={(e) => updateSetting('defaultWorkerId', e.target.value)}
                placeholder="e.g., EMP-001"
                className="bg-surface-container-high border border-outline-variant rounded-lg px-md py-sm text-body-sm text-on-surface outline-none focus:border-primary/50 w-32"
              />
            </div>
            <div className="flex items-center justify-between">
              <span className="text-body-sm text-on-surface-variant">Auto-Assign Worker</span>
              <button onClick={() => updateSetting('autoAssignWorker', !settings.autoAssignWorker)} className="relative w-12 h-6 rounded-full transition-colors">
                {settings.autoAssignWorker ? (
                  <ToggleRight className="w-12 h-6 text-primary" />
                ) : (
                  <ToggleLeft className="w-12 h-6 text-on-surface-variant" />
                )}
              </button>
            </div>
          </div>
        </SettingSection>

        {/* ── Admin Section ──────────────────────────────── */}
        {canEditSystemSettings && (
          <>
            <div className="border-b border-outline-variant/30 pt-md pb-md">
              <div className="flex items-center gap-sm mb-md">
                <HardDrive className="w-5 h-5 text-primary" />
                <h2 className="text-headline-md font-bold text-on-surface">System (Admin)</h2>
              </div>
            </div>

            <SettingSection icon={HardDrive} title="Data Retention">
              <p className="text-[10px] text-on-surface-variant w-full mb-xs">How long session files and recordings are kept before automatic cleanup.</p>
              <select
                value={retentionDays ?? settings.dataRetention}
                onChange={(e) => { setRetentionDays(Number(e.target.value)); setRetentionDirty(true); }}
                disabled={retentionBusy}
                className="bg-surface-container-high border border-outline-variant rounded-lg px-md py-sm text-body-sm text-on-surface outline-none focus:border-primary/50 disabled:opacity-60"
              >
                <option value={7}>7 days</option>
                <option value={30}>30 days</option>
                <option value={60}>60 days</option>
                <option value={90}>90 days</option>
                <option value={180}>180 days</option>
                <option value={365}>1 year</option>
              </select>
              {retentionDays !== null && retentionDays !== settings.dataRetention && (
                <span className="text-[10px] text-amber-400 w-full">Save to apply the new retention policy.</span>
              )}
            </SettingSection>

            <div className="rounded-xl border border-outline-variant bg-surface-container p-lg">
              <div className="flex items-center gap-md mb-md">
                <Brain className="w-5 h-5 text-primary" />
                <h3 className="text-headline-md font-bold text-on-surface">Model Diagnostics</h3>
              </div>
              <p className="text-[11px] text-on-surface-variant mb-md">
                Internal training metrics for the deployed risk model — visible to admins only.
              </p>
              <ModelDiagnosticsCard />
            </div>
          </>
        )}
      </div>

      <button onClick={handleSave} disabled={!dirty && !retentionDirty} className={`flex items-center gap-sm px-lg py-md rounded-lg font-body-md font-bold transition-all ${dirty || retentionDirty ? 'bg-primary text-on-primary hover:brightness-110' : 'bg-surface-container-high text-on-surface-variant cursor-not-allowed'}`}>
        <Save className="w-5 h-5" /> Save Settings
      </button>
    </div>
  );
}

function SettingSection({ icon: Icon, title, children }: { icon: typeof Sun; title: string; children: React.ReactNode }) {
  return (
    <div className="bg-surface-container border border-outline-variant rounded-xl p-lg">
      <div className="flex items-center gap-md mb-md">
        <Icon className="w-5 h-5 text-primary" />
        <h3 className="text-headline-md font-bold text-on-surface">{title}</h3>
      </div>
      <div className="flex items-center gap-md flex-wrap">{children}</div>
    </div>
  );
}
