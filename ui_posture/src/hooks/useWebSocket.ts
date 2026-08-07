import { useCallback, useEffect, useRef, useState } from 'react';

type WSStatus = 'connecting' | 'connected' | 'disconnected';

interface DashboardUpdate {
  type: 'dashboard_update';
  data: {
    session_active: boolean;
    session_id?: string;
    risk_level?: string;
    risk_score?: number;
    confidence?: number;
    person_detected?: boolean;
    task_name?: string;
    task_confidence?: number;
    task_duration_seconds?: number;
    issues?: string[];
    worker_recommendation?: string;
    supervisor_recommendation?: string;
    fps?: number;
    inference_latency_ms?: number;
    timestamp?: string;
    camera_status?: string;
    frame_width?: number;
    frame_height?: number;
    features?: Record<string, unknown>;
  };
  timestamp: string;
}

interface AlertsUpdate {
  type: 'alerts_update';
  data: {
    active_count: number;
    alerts: Array<Record<string, unknown>>;
  };
  timestamp: string;
}

interface CameraUpdate {
  type: 'camera_update';
  data: {
    camera_status: string;
    fps?: number;
    frame_width?: number;
    frame_height?: number;
    person_detected?: boolean;
    inference_latency_ms?: number;
  };
  timestamp: string;
}

type WSMessage = DashboardUpdate | AlertsUpdate | CameraUpdate;

function getWSUrl(path: string): string {
  const base = import.meta.env.VITE_API_URL ?? '';
  const protocol = base.startsWith('https') ? 'wss' : 'ws';
  const host = base.replace(/^https?:\/\//, '') || window.location.host;
  return `${protocol}://${host}${path}`;
}

function useWSConnection<T extends WSMessage>(
  path: string,
  enabled: boolean = true,
): { data: T['data'] | null; status: WSStatus } {
  const [data, setData] = useState<T['data'] | null>(null);
  const [status, setStatus] = useState<WSStatus>('disconnected');
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const retryCount = useRef(0);
  const everConnected = useRef(false);

  const connect = useCallback(() => {
    if (!enabled) return;
    setStatus('connecting');
    const ws = new WebSocket(getWSUrl(path));
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus('connected');
      everConnected.current = true;
      retryCount.current = 0;
    };

    ws.onmessage = (event) => {
      try {
        const msg: T = JSON.parse(event.data);
        if (msg.type) {
          setData(msg.data);
        }
      } catch {
        // ignore malformed messages
      }
    };

    ws.onclose = () => {
      setStatus('disconnected');
      wsRef.current = null;
      if (enabled) {
        retryCount.current += 1;
        const delay = Math.min(3000 * Math.pow(2, Math.min(retryCount.current - 1, 4)), 48000);
        reconnectTimer.current = setTimeout(connect, delay);
      }
    };

    ws.onerror = () => {
      wsRef.current = null;
    };
  }, [path, enabled]);

  useEffect(() => {
    const initialDelay = everConnected.current ? 0 : 2000;
    const timer = setTimeout(connect, initialDelay);
    return () => {
      clearTimeout(timer);
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { data, status };
}

export function useDashboardWS(enabled: boolean = true) {
  return useWSConnection<DashboardUpdate>('/ws/dashboard', enabled);
}

export function useAlertsWS(enabled: boolean = true) {
  return useWSConnection<AlertsUpdate>('/ws/alerts', enabled);
}

export function useCameraWS(enabled: boolean = true) {
  return useWSConnection<CameraUpdate>('/ws/camera', enabled);
}

export type { DashboardUpdate, AlertsUpdate, CameraUpdate, WSStatus };
