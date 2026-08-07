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
