import { useEffect } from 'react';
import type { AlertsResponse } from '@/src/types/api';
import { getAlerts } from '@/src/services/dashboardService';
import { useAlertsWS } from './useWebSocket';
import { usePolledResource } from './usePolling';

export interface UseAlertsReturn {
  alerts: AlertsResponse;
  loading: boolean;
  error: string | null;
  /** A later poll failed: the alerts shown may be stale. */
  degraded: boolean;
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
 * Polls every 10 s through the shared polled-resource primitive (paused while
 * the tab is hidden, backs off when the backend is away) and merges real-time
 * WebSocket pushes on top.
 */
export function useAlerts(): UseAlertsReturn {
  const { data: alerts, loading, error, degraded, refetch, mutate } = usePolledResource(getAlerts, {
    initial: EMPTY_ALERTS,
    intervalMs: 10000,
    label: 'Alerts',
  });
  const { data: wsAlerts } = useAlertsWS();

  // Apply WebSocket alert updates on top of the polled snapshot.
  useEffect(() => {
    if (!wsAlerts) return;
    mutate((prev) => ({
      ...prev,
      active: wsAlerts.alerts as unknown as AlertsResponse['active'],
      summary: {
        ...prev.summary,
        active_count: wsAlerts.active_count,
      },
    }));
  }, [wsAlerts, mutate]);

  return { alerts, loading, error, degraded, refetch };
}
