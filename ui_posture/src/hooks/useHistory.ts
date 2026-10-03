import type { HistoryResponse } from '@/src/types/api';
import { getHistory } from '@/src/services/dashboardService';
import { usePolledResource } from './usePolling';

export interface UseHistoryReturn {
  data: HistoryResponse;
  loading: boolean;
  error: string | null;
  /** A later poll failed: the history shown may be stale. */
  degraded: boolean;
  refetch: () => void;
}

const EMPTY_DATA: HistoryResponse = {
  points: [],
  statistics: {
    frames_stored: 0,
    session_duration_seconds: 0,
    average_risk: 0,
    maximum_risk: 0,
    minimum_risk: 0,
    average_fatigue: 0,
    average_exposure: 0,
  },
};

/**
 * Risk History Engine data for the live session chart. Polls every 4 s while
 * the tab is visible (this is the hottest poller in the app, so it also gets
 * the shared pause/backoff behaviour).
 */
export function useHistory(): UseHistoryReturn {
  const { data, loading, error, degraded, refetch } = usePolledResource(getHistory, {
    initial: EMPTY_DATA,
    intervalMs: 4000,
    label: 'Risk history',
  });
  return { data, loading, error, degraded, refetch };
}
