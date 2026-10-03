import type { RecommendationsBundleResponse } from '@/src/types/api';
import { getRecommendations } from '@/src/services/dashboardService';
import { usePolledResource } from './usePolling';

export interface UseRecommendationsReturn {
  data: RecommendationsBundleResponse;
  loading: boolean;
  error: string | null;
  /** A later poll failed: the recommendations shown may be stale. */
  degraded: boolean;
  refetch: () => void;
}

const EMPTY_DATA: RecommendationsBundleResponse = {
  bundle: null,
  total_generated: 0,
};

/**
 * Recommendation Engine data. Polls every 10 s while the tab is visible;
 * consecutive failures back off instead of hammering a down backend.
 */
export function useRecommendations(): UseRecommendationsReturn {
  const { data, loading, error, degraded, refetch } = usePolledResource(getRecommendations, {
    initial: EMPTY_DATA,
    intervalMs: 10000,
    label: 'Recommendations',
  });
  return { data, loading, error, degraded, refetch };
}
