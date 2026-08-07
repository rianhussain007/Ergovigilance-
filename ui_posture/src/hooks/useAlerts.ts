import { useState, useEffect, useCallback, useRef } from 'react';
import type { AlertsResponse } from '@/src/types/api';
import { getAlerts } from '@/src/services/dashboardService';
import { getStoredToken } from '@/src/auth/AuthContext';
import { useAlertsWS } from './useWebSocket';

export interface UseAlertsReturn {
  alerts: AlertsResponse;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

const EMPTY_ALERTS: AlertsResponse = {
  active: [],
  history: [],
  summary: {
    total_fired: 0,
    active_count: 0,
    critical_count: 0,
    acknowledged_count: 0,
    consecutive_high: 0,
  },
};

/**
 * Hook for consuming alert data from the Alert Engine.
 *
 * Uses WebSocket for real-time alert updates when a session is active.
 * Falls back to polling for initial load and session-inactive state.
 */
export function useAlerts(): UseAlertsReturn {
  const [alerts, setAlerts] = useState<AlertsResponse>(EMPTY_ALERTS);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);
  const { data: wsAlerts } = useAlertsWS();

  const fetchData = useCallback(async (isInitial = false) => {
    if (isInitial) {
      setLoading(true);
      setError(null);
    }
    if (!getStoredToken()) {
      if (!mountedRef.current) return;
      setAlerts(EMPTY_ALERTS);
      if (isInitial) {
        setError(null);
        setLoading(false);
      }
      return;
    }
    try {
      const data = await getAlerts();
      if (!mountedRef.current) return;
      setAlerts((prev) => {
        if (JSON.stringify(prev) === JSON.stringify(data)) return prev;
        return data;
      });
      if (isInitial) setError(null);
    } catch (err) {
      if (!mountedRef.current) return;
      if (isInitial) setError(err instanceof Error ? err.message : 'Failed to load alerts');
    } finally {
      if (isInitial && mountedRef.current) setLoading(false);
    }
  }, []);

  // Apply WebSocket alert updates
  useEffect(() => {
    if (!wsAlerts) return;
    setAlerts((prev) => ({
      ...prev,
      active: wsAlerts.alerts as unknown as AlertsResponse['active'],
      summary: {
        ...prev.summary,
        active_count: wsAlerts.active_count,
      },
    }));
  }, [wsAlerts]);

  useEffect(() => {
    mountedRef.current = true;
    fetchData(true);
    const interval = setInterval(() => fetchData(false), 10000);
    return () => {
      mountedRef.current = false;
      clearInterval(interval);
    };
  }, [fetchData]);

  return { alerts, loading, error, refetch: () => fetchData(true) };
}
