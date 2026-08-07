import { useState, useEffect, useCallback, useRef } from 'react';
import type { ContextSnapshot } from '@/src/types/api';
import { getContextSnapshot } from '@/src/services/dashboardService';
import { getStoredToken } from '@/src/auth/AuthContext';

export interface UseContextSnapshotReturn {
  snapshot: ContextSnapshot | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

/**
 * Hook for consuming the Context Intelligence snapshot.
 *
 * Returns the latest ContextSnapshot from the live pipeline.
 * When no session is active, snapshot is null (no fake values).
 *
 * Polling: initial mount shows loading; subsequent polls at 10s intervals.
 */
export function useContextSnapshot(): UseContextSnapshotReturn {
  const [snapshot, setSnapshot] = useState<ContextSnapshot | null>(null);
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
      setSnapshot(null);
      if (isInitial) {
        setError(null);
        setLoading(false);
      }
      return;
    }
    try {
      const data = await getContextSnapshot();
      if (!mountedRef.current) return;
      setSnapshot((prev) => {
        if (JSON.stringify(prev) === JSON.stringify(data)) return prev;
        return data;
      });
      if (isInitial) setError(null);
    } catch (err) {
      if (!mountedRef.current) return;
      if (isInitial) setError(err instanceof Error ? err.message : 'Failed to load context snapshot');
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

  return { snapshot, loading, error, refetch: () => fetchData(true) };
}
