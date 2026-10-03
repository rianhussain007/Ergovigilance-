import type { TimelineEntry } from '@/src/types/api';
import { getLiveTimeline } from '@/src/services/dashboardService';
import { usePolledResource } from './usePolling';

export interface UseLiveTimelineReturn {
  timeline: TimelineEntry[];
  loading: boolean;
  error: string | null;
  /** A later poll failed: the timeline shown may be stale. */
  degraded: boolean;
  refetch: () => void;
}

/**
 * Live session timeline. Polls every 3 s while the tab is visible; returns an
 * empty timeline (no fabricated events) when no session is active.
 */
export function useLiveTimeline(): UseLiveTimelineReturn {
  const { data: timeline, loading, error, degraded, refetch } = usePolledResource(
    () => getLiveTimeline(200).then((res) => res.timeline),
    { initial: [], intervalMs: 3000, label: 'Live timeline' },
  );
  return { timeline, loading, error, degraded, refetch };
}
