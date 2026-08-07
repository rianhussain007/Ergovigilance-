import { useState, useEffect, useCallback, useRef } from 'react';
import type { HistoryResponse } from '@/src/types/api';
import { getHistory } from '@/src/services/dashboardService';
import { getStoredToken } from '@/src/auth/AuthContext';

export interface UseHistoryReturn {
  data: HistoryResponse;
  loading: boolean;
  error: string | null;
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
 * Hook for consuming Risk History Engine data.
 *
 * Polls every 1s. Returns empty history when no session is active.
 * Initial mount shows loading; subsequent polls are silent.
 */
export function useHistory(): UseHistoryReturn {
  const [data, setData] = useState<HistoryResponse>(EMPTY_DATA);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  const fetchData = useCallback(async (isInitial = false) => {
    if (isInitial) {
      setLoading(true);
      setError(null);
    }
    if (!getStoredToken()) {
      if (!mountedRef.current) return;
      setData(EMPTY_DATA);
      if (isInitial) {
        setError(null);
        setLoading(false);
      }
      return;
    }
    try {
      const result = await getHistory();
      if (!mountedRef.current) return;
      setData((prev) => {
        if (JSON.stringify(prev) === JSON.stringify(result)) return prev;
        return result;
      });
      if (isInitial) setError(null);
    } catch (err) {
      if (!mountedRef.current) return;
      if (isInitial) setError(err instanceof Error ? err.message : 'Failed to load history');
    } finally {
      if (isInitial && mountedRef.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    fetchData(true);
    const interval = setInterval(() => fetchData(false), 2000);
    return () => {
      mountedRef.current = false;
      clearInterval(interval);
    };
  }, [fetchData]);

  return { data, loading, error, refetch: () => fetchData(true) };
}
