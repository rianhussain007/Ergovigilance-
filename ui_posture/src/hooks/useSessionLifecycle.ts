import { useState, useEffect, useCallback, useRef } from 'react';
import { getStoredToken } from '@/src/auth/AuthContext';
import { apiFetch } from '@/src/services/apiClient';
import { useSettings } from './useSettings';

export type SessionStatus = 'idle' | 'starting' | 'monitoring' | 'stopping' | 'error';

export interface UseSessionLifecycleReturn {
  status: SessionStatus;
  sessionId: string | null;
  error: string | null;
  startSession: (workerId?: string) => Promise<void>;
  stopSession: () => Promise<void>;
}

/**
 * Hook for managing the live monitoring session lifecycle.
 *
 * Controls POST /api/session/start and POST /api/session/stop.
 * Polls GET /api/session/status to stay in sync.
 */
export function useSessionLifecycle(): UseSessionLifecycleReturn {
  const [status, setStatus] = useState<SessionStatus>('idle');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const errorTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const clearError = useCallback(() => {
    if (errorTimerRef.current) {
      clearTimeout(errorTimerRef.current);
      errorTimerRef.current = null;
    }
    setError(null);
  }, []);

  const setErrorAutoClear = useCallback((msg: string) => {
    if (errorTimerRef.current) {
      clearTimeout(errorTimerRef.current);
    }
    setError(msg);
    errorTimerRef.current = setTimeout(() => {
      if (mountedRef.current) {
        setError(null);
      }
    }, 6000);
  }, []);

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  const pollStatus = useCallback(async () => {
    if (!getStoredToken()) {
      if (!mountedRef.current) return;
      setSessionId(null);
      setStatus('idle');
      stopPolling();
      return;
    }
    try {
      const res = await apiFetch('/api/session/status');
      if (!res.ok) return;
      const data = await res.json();
      if (!mountedRef.current) return;

      if (data.active) {
        setSessionId(data.session_id);
        setStatus('monitoring');
      } else {
        setSessionId(null);
        setStatus('idle');
        clearError();
        stopPolling();
      }
    } catch {
      // Silently ignore poll errors
    }
  }, [stopPolling, clearError]);

  const startPolling = useCallback(() => {
    stopPolling();
    pollingRef.current = setInterval(pollStatus, 2000);
  }, [pollStatus, stopPolling]);

  const { settings } = useSettings();
  
  const startSession = useCallback(async (workerId?: string) => {
    if (status === 'starting' || status === 'monitoring') return;

    setStatus('starting');
    clearError();

    try {
      const res = await apiFetch('/api/session/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ worker_id: workerId ?? null, camera_id: settings.cameraId }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        const detail = Array.isArray(body?.detail)
          ? body.detail.map((e: { msg?: string }) => e.msg).join('; ')
          : body?.detail ?? `HTTP ${res.status}`;
        throw new Error(detail);
      }

      const data = await res.json();
      if (!mountedRef.current) return;

      setSessionId(data.id);
      setStatus('monitoring');
      startPolling();
    } catch (err) {
      if (!mountedRef.current) return;
      const msg = err instanceof Error ? err.message : 'Failed to start session';
      setErrorAutoClear(msg);
      setStatus('idle');
    }
  }, [status, startPolling, clearError, setErrorAutoClear, settings.cameraId]);

  const stopSession = useCallback(async () => {
    if (status === 'stopping' || status === 'idle') return;

    setStatus('stopping');
    clearError();
    stopPolling();

    try {
      const res = await apiFetch('/api/session/stop', { method: 'POST' });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        const detail = Array.isArray(body?.detail)
          ? body.detail.map((e: { msg?: string }) => e.msg).join('; ')
          : body?.detail ?? `HTTP ${res.status}`;
        throw new Error(detail);
      }

      if (!mountedRef.current) return;
      setSessionId(null);
      setStatus('idle');
    } catch (err) {
      if (!mountedRef.current) return;
      const msg = err instanceof Error ? err.message : 'Failed to stop session';
      setErrorAutoClear(msg);
      pollStatus();
    }
  }, [status, stopPolling, clearError, setErrorAutoClear, pollStatus]);

  // On mount, check if a session is already running
  useEffect(() => {
    mountedRef.current = true;
    pollStatus();
    return () => {
      mountedRef.current = false;
      if (errorTimerRef.current) clearTimeout(errorTimerRef.current);
      stopPolling();
    };
  }, [pollStatus, stopPolling]);

  return { status, sessionId, error, startSession, stopSession };
}
