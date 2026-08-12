import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { apiFetch } from '@/src/services/apiClient';
import { getStoredToken } from '@/src/auth/AuthContext';

export interface Settings {
  theme: 'dark' | 'light' | 'system';
  cameraId: string; // index of selected camera (as string)
  refreshInterval: number; // in seconds
  notifications: boolean;
  // Deployment configuration (coming soon)
  cameraMapping: string;
  workstationMapping: string;
  alertThreshold: 'low' | 'moderate' | 'high';
  dataRetention: number;
  // Live monitoring settings
  targetFps: number; // target frame rate for pose processing
  featureSmoothing: number; // EMA smoothing factor (0.1-1.0)
  kalmanFilter: boolean; // enable/disable Kalman smoothing
  // AI Assistant settings
  ollamaModel: string; // Ollama model name
  aiExplanation: boolean; // enable/disable AI explanations
  // Export settings
  defaultExportFormat: 'pdf' | 'csv' | 'json';
  autoExport: boolean; // auto-export after session
  // Display settings
  timelineGranularity: 'seconds' | 'minutes' | 'hours';
  chartAnimation: boolean; // enable/disable chart animations
  // Worker settings
  defaultWorkerId: string; // default worker ID for sessions
  autoAssignWorker: boolean; // auto-assign worker to session
}

const STORAGE_KEY = 'ergo_settings';
const DEFAULT_SETTINGS: Settings = {
  theme: 'dark',
  cameraId: '0',
  refreshInterval: 30,
  notifications: true,
  cameraMapping: 'zone',
  workstationMapping: 'auto',
  alertThreshold: 'moderate',
  dataRetention: 90,
  // Live monitoring settings
  targetFps: 15,
  featureSmoothing: 0.7,
  kalmanFilter: true,
  // AI Assistant settings
  ollamaModel: 'qwen2.5:1.5b',
  aiExplanation: true,
  // Export settings
  defaultExportFormat: 'pdf',
  autoExport: false,
  // Display settings
  timelineGranularity: 'seconds',
  chartAnimation: true,
  // Worker settings
  defaultWorkerId: '',
  autoAssignWorker: false,
};

function loadLocalSettings(): Settings {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      return { ...DEFAULT_SETTINGS, ...JSON.parse(stored) };
    }
  } catch {
    // ignore errors
  }
  return DEFAULT_SETTINGS;
}

function saveLocalSettings(settings: Settings) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  } catch {
    // ignore
  }
}

interface SettingsContextValue {
  settings: Settings;
  updateSetting: <K extends keyof Settings>(key: K, value: Settings[K]) => void;
  saveSettings: () => void;
  dirty: boolean;
}

const SettingsContext = createContext<SettingsContextValue | null>(null);

export function SettingsProvider({ children }: { children: React.ReactNode }) {
  const [settings, setSettings] = useState<Settings>(loadLocalSettings);
  const [dirty, setDirty] = useState(false);

  // Load settings from backend on mount
  useEffect(() => {
    if (!getStoredToken()) return;
    let cancelled = false;
    apiFetch('/api/settings')
      .then((res) => (res.ok ? res.json() : null))
      .then((data: Record<string, unknown> | null) => {
        if (!cancelled && data && typeof data === 'object' && Object.keys(data).length > 0) {
          setSettings((prev) => ({ ...prev, ...data }));
        }
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const updateSetting = useCallback(<K extends keyof Settings>(key: K, value: Settings[K]) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
    setDirty(true);
  }, []);

  const saveSettings = useCallback(() => {
    saveLocalSettings(settings);
    // Sync to backend (fire and forget)
    if (getStoredToken()) {
      apiFetch('/api/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings),
      }).catch(() => {});
    }
    setDirty(false);
  }, [settings]);

  return (
    <SettingsContext.Provider value={{ settings, updateSetting, saveSettings, dirty }}>
      {children}
    </SettingsContext.Provider>
  );
}

export function useSettings(): SettingsContextValue {
  const ctx = useContext(SettingsContext);
  if (!ctx) throw new Error('useSettings must be used within a SettingsProvider');
  return ctx;
}
