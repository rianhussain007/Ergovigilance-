import { useState, useEffect, useCallback, useRef } from 'react';
import type { RecommendationsBundleResponse } from '@/src/types/api';
import { getRecommendations } from '@/src/services/dashboardService';
import { getStoredToken } from '@/src/auth/AuthContext';

export interface UseRecommendationsReturn {
  data: RecommendationsBundleResponse;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

const EMPTY_DATA: RecommendationsBundleResponse = {
  bundle: null,
  total_generated: 0,
};

/**
 * Hook for consuming Recommendation Engine data.
 *
 * Polls every 10s. Returns empty bundle when no session is active.
 * Initial mount shows loading; subsequent polls are silent.
 */
export function useRecommendations(): UseRecommendationsReturn {
  const [data, setData] = useState<RecommendationsBundleResponse>(EMPTY_DATA);
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
      const result = await getRecommendations();
      if (!mountedRef.current) return;
      setData((prev) => {
        if (JSON.stringify(prev) === JSON.stringify(result)) return prev;
        return result;
      });
      if (isInitial) setError(null);
    } catch (err) {
      if (!mountedRef.current) return;
      if (isInitial) setError(err instanceof Error ? err.message : 'Failed to load recommendations');
    } finally {
      if (isInitial && mountedRef.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    fetchData(true);
    const interval = setInterval(() => fetchData(false), 10000);
    return () => {
      mountedRef.current = false;
      clearInterval(interval);
    };
  }, [fetchData]);

  return { data, loading, error, refetch: () => fetchData(true) };
}
