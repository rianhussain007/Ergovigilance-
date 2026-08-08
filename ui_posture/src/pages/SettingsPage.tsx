import React, { useEffect, useState } from 'react';
import { Sun, Moon, Monitor, Camera, RefreshCw, Bell, Save, HardDrive, AlertTriangle } from 'lucide-react';
import { useTheme } from '@/src/hooks/useTheme';
import { useToast } from '@/src/hooks/useToast';
import { useAuth } from '@/src/auth/AuthContext';
import { useSettings } from '@/src/hooks/useSettings';
import { getCameras, getRetentionStats, updateRetentionConfig } from '@/src/services/dashboardService';
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
    setMode(settings.theme);
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
    <div className="p-lg space-y-lg pb-32 max-w-3xl">
      <div>
        <h1 className="text-display-lg font-bold text-on-surface">Settings</h1>
        <p className="text-body-sm text-on-surface-variant mt-xs">Configure your dashboard and deployment preferences</p>
      </div>

      <div className="space-y-md">
        <SettingSection icon={Sun} title="Theme">
          <div className="flex gap-sm flex-wrap">
            {(['dark', 'light', 'system'] as const).map((t) => {
              const Icon = t === 'dark' ? Moon : t === 'light' ? Sun : Monitor;
              return (
                <button key={t} onClick={() => updateSetting('theme', t)} className={`flex items-center gap-sm px-md py-sm rounded-lg border text-body-sm font-medium transition-all ${settings.theme === t ? 'border-primary/50 bg-primary/10 text-primary' : 'border-outline-variant text-on-surface-variant hover:text-on-surface'}`}>
                  <Icon className="w-4 h-4" />{t.charAt(0).toUpperCase() + t.slice(1)}
                </button>
              );
            })}
          </div>
        </SettingSection>

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
        </SettingSection>

        <SettingSection icon={RefreshCw} title="Refresh Interval">
          <select value={settings.refreshInterval} onChange={(e) => updateSetting('refreshInterval', Number(e.target.value))} className="bg-surface-container-high border border-outline-variant rounded-lg px-md py-sm text-body-sm text-on-surface outline-none focus:border-primary/50">
            <option value={10}>10 seconds</option>
            <option value={30}>30 seconds</option>
            <option value={60}>1 minute</option>
            <option value={300}>5 minutes</option>
          </select>
        </SettingSection>

        <SettingSection icon={Bell} title="Notifications">
          <button onClick={() => updateSetting('notifications', !settings.notifications)} className={`relative w-12 h-6 rounded-full transition-colors ${settings.notifications ? 'bg-primary' : 'bg-surface-container-highest'}`}>
            <div className={`absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform ${settings.notifications ? 'translate-x-6' : 'translate-x-0.5'}`} />
          </button>
          <span className="text-body-sm text-on-surface-variant">{settings.notifications ? 'Enabled' : 'Disabled'}</span>
        </SettingSection>

        {canEditSystemSettings && (
          <>
            <div className="border-t border-outline-variant/30 pt-md">
              <div className="flex items-center gap-sm">
                <h2 className="text-headline-md font-bold text-on-surface">Workplace Controls</h2>
              </div>
            </div>

            <SettingSection icon={AlertTriangle} title="Alert Threshold">
              <p className="text-[10px] text-on-surface-variant w-full mb-xs">Sets the minimum severity shown in the Live Monitoring alerts panel.</p>
              <div className="flex gap-sm">
                {(['low', 'moderate', 'high'] as const).map((t) => (
                  <button key={t} onClick={() => updateSetting('alertThreshold', t)} className={`px-md py-sm rounded-lg border text-body-sm font-medium transition-all ${settings.alertThreshold === t ? 'border-primary/50 bg-primary/10 text-primary' : 'border-outline-variant text-on-surface-variant hover:text-on-surface'}`}>
                    {t.charAt(0).toUpperCase() + t.slice(1)}
                  </button>
                ))}
              </div>
            </SettingSection>

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
