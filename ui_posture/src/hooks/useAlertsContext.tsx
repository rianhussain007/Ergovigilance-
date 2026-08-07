import React, { createContext, useContext, useMemo } from 'react';
import { useAlerts, type UseAlertsReturn } from './useAlerts';
import type { AlertsResponse } from '@/src/types/api';

interface AlertsContextValue {
  alerts: AlertsResponse;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

const AlertsContext = createContext<AlertsContextValue | null>(null);

export function AlertsProvider({ children }: { children: React.ReactNode }) {
  const { alerts, loading, error, refetch } = useAlerts();
  const value = useMemo(
    () => ({ alerts, loading, error, refetch }),
    [alerts, loading, error, refetch],
  );
  return <AlertsContext.Provider value={value}>{children}</AlertsContext.Provider>;
}

export function useAlertsContext(): AlertsContextValue {
  const ctx = useContext(AlertsContext);
  if (!ctx) throw new Error('useAlertsContext must be used within AlertsProvider');
  return ctx;
}
