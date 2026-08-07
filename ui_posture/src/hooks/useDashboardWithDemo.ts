import { useDemo } from '@/src/demo/DemoProvider';
import { useDashboard } from './useDashboard';
import type { UseDashboardReturn } from './useDashboard';

/**
 * Drop-in replacement for useDashboard() that respects Demo Mode.
 * When demo mode is active, returns demo data instead of repository data.
 * When demo mode is inactive, delegates to the real useDashboard().
 */
export function useDashboardWithDemo(): UseDashboardReturn {
  const demo = useDemo();
  const real = useDashboard();

  if (demo.state.active) {
    return {
      dashboard: demo.state.dashboard,
      sessions: demo.state.sessions,
      loading: false,
      error: null,
      refetch: demo.restart,
      refetchSessions: demo.restart,
    };
  }

  return real;
}
