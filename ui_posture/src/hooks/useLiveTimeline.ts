import { useState, useEffect, useCallback, useRef } from 'react';
import type { TimelineEntry } from '@/src/types/api';
import { getLiveTimeline } from '@/src/services/dashboardService';
import { getStoredToken } from '@/src/auth/AuthContext';

export interface UseLiveTimelineReturn {
  timeline: TimelineEntry[];
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

/**
 * Hook for consuming live session timeline data.
 *
 * Polls every 1.5s. Returns empty array when no session is active.
 * Initial mount shows loading; subsequent polls are silent.
 */
export function useLiveTimeline(): UseLiveTimelineReturn {
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
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
      setTimeline([]);
      if (isInitial) {
        setError(null);
        setLoading(false);
      }
      return;
    }
    try {
      const result = await getLiveTimeline(200);
      if (!mountedRef.current) return;
      setTimeline((prev) => {
        if (JSON.stringify(prev) === JSON.stringify(result.timeline)) return prev;
        return result.timeline;
      });
      if (isInitial) setError(null);
    } catch (err) {
      if (!mountedRef.current) return;
      if (isInitial) setError(err instanceof Error ? err.message : 'Failed to load timeline');
    } finally {
      if (isInitial && mountedRef.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    fetchData(true);
    const interval = setInterval(() => fetchData(false), 3000);
    return () => {
      mountedRef.current = false;
      clearInterval(interval);
    };
  }, [fetchData]);

  return { timeline, loading, error, refetch: () => fetchData(true) };
}
