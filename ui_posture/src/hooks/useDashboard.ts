import { useEffect } from 'react';
import type { DashboardResponse, SessionRecord } from '@/src/types/api';
import { getDashboardData, getSessions } from '@/src/services/dashboardService';
import { useSettings } from './useSettings';
import { useDashboardWS } from './useWebSocket';
import { usePolledResource } from './usePolling';

export interface UseDashboardReturn {
  dashboard: DashboardResponse | null;
  sessions: SessionRecord[];
  loading: boolean;
  error: string | null;
  /** A later poll failed while data is on screen: what you see may be stale. */
  degraded: boolean;
  refetch: () => void;
  refetchSessions: () => void;
}

/**
 * Dashboard data with WebSocket live merging.
 *
 * Dashboard polls at `settings.refreshInterval` (floor 5 s) and pauses while
 * the tab is hidden. Sessions load once and only refetch on explicit action —
 * the backend scans session files per page, so polling them would be wasteful.
 *
 * Pass enabled=false to skip fetching, polling and the WebSocket entirely.
 */
export function useDashboard(enabled: boolean = true): UseDashboardReturn {
  const { settings } = useSettings();
  const pollSeconds = Math.max(5, Number(settings.refreshInterval) || 30);

  const {
    data: dashboard,
    loading,
    error,
    degraded,
    refetch,
    mutate,
  } = usePolledResource(getDashboardData, {
    initial: null,
    intervalMs: pollSeconds * 1000,
    enabled,
    label: 'Dashboard',
  });

  const {
    data: sessions,
    refetch: refetchSessions,
  } = usePolledResource(
    () => getSessions(1, 25).then((resp) => resp.sessions),
    { initial: [], intervalMs: null, enabled, label: 'Sessions' },
  );

  const { data: wsData } = useDashboardWS(enabled);

  // Apply WebSocket live data on top of the polled snapshot. The functional
  // updater receives the latest state; `dashboard` is intentionally not a dep.
  useEffect(() => {
    if (!wsData) return;
    mutate((prev) => {
      if (!prev || !prev.liveStatus || !wsData.session_active) return prev;
      return {
        ...prev,
        liveStatus: {
          ...prev.liveStatus,
          riskLevel: (wsData.risk_level?.toLowerCase() as 'low' | 'moderate' | 'high') ?? prev.liveStatus.riskLevel,
          riskScore: wsData.risk_score ?? prev.liveStatus.riskScore,
          confidence: wsData.confidence ?? prev.liveStatus.confidence,
          // Keep the feed's FPS badge honest between REST polls — otherwise it
          // shows "—" (or a stale value) while frames are actually flowing.
          fps: wsData.fps ?? prev.liveStatus.fps,
          currentTask: wsData.task_name ?? prev.liveStatus.currentTask,
          workerStatus: wsData.person_detected ? 'Person Detected' : 'No Person',
        },
        session: prev.session ? {
          ...prev.session,
          id: wsData.session_id ?? prev.session.id,
          duration: wsData.task_duration_seconds ? Math.round(wsData.task_duration_seconds) : prev.session.duration,
          cameraStatus: wsData.camera_status ?? prev.session.cameraStatus,
          cameraReconnecting: wsData.camera_reconnecting ?? prev.session.cameraReconnecting,
        } : prev.session,
      };
    });
  }, [wsData, mutate]);

  return { dashboard, sessions, loading, error, degraded, refetch, refetchSessions };
}
