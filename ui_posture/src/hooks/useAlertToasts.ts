import { useEffect, useRef, useCallback } from 'react';
import { useAlerts } from './useAlerts';
import { useToast } from './useToast';

const SEVERITY_TOAST_MAP: Record<string, 'error' | 'warning' | 'info'> = {
  CRITICAL: 'error',
  HIGH: 'warning',
  WARNING: 'info',
  MEDIUM: 'info',
  LOW: 'info',
};

const SUSTAINED_MS = 10_000;  // Reduced from 15s to 10s for faster response
const EPISODE_RESET_MS = 5_000;
const TOAST_DURATION_MS = 8_000;  // Increased from 6s to 8s for better readability

interface Episode {
  firstSeenAt: number;
  lastSeenAt: number;
  toastedThisEpisode: boolean;
  severity: string;
}

/**
 * Side-effect hook: polls alerts and auto-shows toast pop-ups for sustained
 * alert conditions.
 *
 * Tracks "episodes" per trigger_rule. A toast fires only when the same rule
 * has been continuously present in active alerts for >= 10s. A gap of >= 5s
 * between sightings resets the episode (the condition cleared and came back).
 * Only one toast per episode — no repeat toasts for the same sustained event.
 * Severity controls toast color and priority; the 10s gate applies uniformly.
 */
export function useAlertToasts(onToastClick?: () => void) {
  const { alerts } = useAlerts();
  const { addToast } = useToast();
  const episodes = useRef<Map<string, Episode>>(new Map());

  const handleToastClick = useCallback(() => {
    onToastClick?.();
  }, [onToastClick]);

  useEffect(() => {
    const now = Date.now();

    // ── Prune stale episodes ──────────────────────────────────
    for (const [rule, ep] of episodes.current) {
      if (now - ep.lastSeenAt >= EPISODE_RESET_MS) {
        episodes.current.delete(rule);
      }
    }

    // ── Process active alerts only ────────────────────────────
    // Sort by severity (CRITICAL first) to ensure critical alerts are shown
    const sortedAlerts = [...alerts.active].sort((a, b) => {
      const order = { CRITICAL: 0, HIGH: 1, WARNING: 2, MEDIUM: 3, LOW: 4 };
      return (order[a.severity as keyof typeof order] ?? 5) - (order[b.severity as keyof typeof order] ?? 5);
    });

    for (const alert of sortedAlerts) {
      const toastType = SEVERITY_TOAST_MAP[alert.severity];
      if (!toastType) continue;

      let ep = episodes.current.get(alert.trigger_rule);

      if (!ep) {
        // Start a new episode
        ep = { firstSeenAt: now, lastSeenAt: now, toastedThisEpisode: false, severity: alert.severity };
        episodes.current.set(alert.trigger_rule, ep);
      } else {
        // Extend the ongoing episode
        ep.lastSeenAt = now;
        // Update severity if it changed (escalation)
        if (alert.severity !== ep.severity) {
          ep.severity = alert.severity;
          ep.toastedThisEpisode = false;  // Re-toast on severity change
        }
      }

      if (!ep.toastedThisEpisode && now - ep.firstSeenAt >= SUSTAINED_MS) {
        ep.toastedThisEpisode = true;
        addToast(toastType, alert.title, alert.message, TOAST_DURATION_MS, handleToastClick);
      }
    }
  }, [alerts, addToast, handleToastClick]);
}
