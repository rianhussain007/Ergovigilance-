import type { ContextSnapshot } from '@/src/types/api';
import { getContextSnapshot } from '@/src/services/dashboardService';
import { usePolledResource } from './usePolling';

export interface UseContextSnapshotReturn {
  snapshot: ContextSnapshot | null;
  loading: boolean;
  error: string | null;
  /** A later poll failed: the snapshot shown may be stale. */
  degraded: boolean;
  refetch: () => void;
}

/**
 * Context Intelligence snapshot. When no session is active the API returns
 * null and the UI shows "no active session" — no synthesized values.
 */
export function useContextSnapshot(): UseContextSnapshotReturn {
  const { data: snapshot, loading, error, degraded, refetch } = usePolledResource(getContextSnapshot, {
    initial: null,
    intervalMs: 10000,
    label: 'Context snapshot',
  });
  return { snapshot, loading, error, degraded, refetch };
}
