import { useState, useEffect, useCallback, useRef } from 'react';
import type { DashboardResponse, SessionRecord } from '@/src/types/api';
import { getDashboardData, getSessions } from '@/src/services/dashboardService';
import { getStoredToken } from '@/src/auth/AuthContext';
import { useSettings } from './useSettings';
import { useDashboardWS } from './useWebSocket';

export interface UseDashboardReturn {
  dashboard: DashboardResponse | null;
  sessions: SessionRecord[];
  loading: boolean;
  error: string | null;
  refetch: () => void;
  refetchSessions: () => void;
}

/**
 * Default hook — reads from the real API.
 *
 * Dashboard data polls at settings.refreshInterval.
 * Sessions load once on mount and only refetch on explicit action (refetchSessions).
 * This avoids scanning 140 session files on every poll cycle.
 *
 * Pass enabled=false to skip the fetch, poll, and WebSocket entirely —
 * prevents duplicate polls/sockets per page from Layout + page subscribing
 * independently.
 */
export function useDashboard(enabled: boolean = true): UseDashboardReturn {
  const { settings } = useSettings();
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [sessions, setSessions] = useState<SessionRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);
  const sessionsLoadedRef = useRef(false);
  const { data: wsData } = useDashboardWS(enabled);

  const fetchDashboard = useCallback(async () => {
    if (!getStoredToken()) {
      if (!mountedRef.current) return;
      setDashboard(null);
      setError(null);
      setLoading(false);
      return;
    }
    try {
      const dash = await getDashboardData();
      if (!mountedRef.current) return;
      setDashboard(dash);
      setError(null);
    } catch (err) {
      if (!mountedRef.current) return;
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  }, []);

  const fetchSessions = useCallback(async () => {
    if (!getStoredToken()) return;
    try {
      const resp = await getSessions(1, 25);
      if (!mountedRef.current) return;
      setSessions(resp.sessions);
      sessionsLoadedRef.current = true;
    } catch {
      // Silent — sessions are non-critical for dashboard
    }
  }, []);

  // Apply WebSocket live data to dashboard when available
  // NOTE: dashboard deliberately excluded from deps — the functional updater
  // form of setDashboard always receives the latest state, and including
  // dashboard here creates an infinite loop (setDashboard → new ref → effect fires again).
  useEffect(() => {
    if (!wsData) return;
    setDashboard((prev) => {
      if (!prev || !prev.liveStatus || !wsData.session_active) return prev;
      return {
        ...prev,
        liveStatus: {
          ...prev.liveStatus,
          riskLevel: (wsData.risk_level?.toLowerCase() as 'low' | 'moderate' | 'high') ?? prev.liveStatus.riskLevel,
          riskScore: wsData.risk_score ?? prev.liveStatus.riskScore,
          confidence: wsData.confidence ?? prev.liveStatus.confidence,
          currentTask: wsData.task_name ?? prev.liveStatus.currentTask,
          workerStatus: wsData.person_detected ? 'Person Detected' : 'No Person',
        },
        session: prev.session ? {
          ...prev.session,
          id: wsData.session_id ?? prev.session.id,
          duration: wsData.task_duration_seconds ? Math.round(wsData.task_duration_seconds) : prev.session.duration,
          cameraStatus: wsData.camera_status ?? prev.session.cameraStatus,
        } : prev.session,
      };
    });
  }, [wsData]);

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }
    mountedRef.current = true;
    // Load dashboard immediately, sessions once
    fetchDashboard();
    if (!sessionsLoadedRef.current) {
      fetchSessions();
    }
    // Dashboard polls at refreshInterval; sessions do NOT poll
    const interval = setInterval(fetchDashboard, settings.refreshInterval * 1000);
    return () => {
      mountedRef.current = false;
      clearInterval(interval);
    };
  }, [fetchDashboard, fetchSessions, settings.refreshInterval, enabled]);

  return {
    dashboard,
    sessions,
    loading,
    error,
    refetch: fetchDashboard,
    refetchSessions: fetchSessions,
  };
}
