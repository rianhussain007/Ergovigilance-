import { useEffect, useRef } from 'react';
import { useAlerts } from './useAlerts';
import { useToast } from './useToast';

const SEVERITY_TOAST_MAP: Record<string, 'error' | 'warning' | 'info'> = {
  CRITICAL: 'error',
  HIGH: 'warning',
  WARNING: 'info',
};

const SUSTAINED_MS = 15_000;
const EPISODE_RESET_MS = 5_000;
const TOAST_DURATION_MS = 6_000;

interface Episode {
  firstSeenAt: number;
  lastSeenAt: number;
  toastedThisEpisode: boolean;
}

/**
 * Side-effect hook: polls alerts and auto-shows toast pop-ups for sustained
 * alert conditions.
 *
 * Tracks "episodes" per trigger_rule. A toast fires only when the same rule
 * has been continuously present in active alerts for >= 15s. A gap of >= 5s
 * between sightings resets the episode (the condition cleared and came back).
 * Only one toast per episode — no repeat toasts for the same sustained event.
 * Severity controls toast color; the 15s gate applies uniformly to all.
 */
export function useAlertToasts(onToastClick?: () => void) {
  const { alerts } = useAlerts();
  const { addToast } = useToast();
  const episodes = useRef<Map<string, Episode>>(new Map());

  useEffect(() => {
    const now = Date.now();

    // ── Prune stale episodes ──────────────────────────────────
    for (const [rule, ep] of episodes.current) {
      if (now - ep.lastSeenAt >= EPISODE_RESET_MS) {
        episodes.current.delete(rule);
      }
    }

    // ── Process active alerts only ────────────────────────────
    for (const alert of alerts.active) {
      const toastType = SEVERITY_TOAST_MAP[alert.severity];
      if (!toastType) continue;

      let ep = episodes.current.get(alert.trigger_rule);

      if (!ep) {
        // Start a new episode
        ep = { firstSeenAt: now, lastSeenAt: now, toastedThisEpisode: false };
        episodes.current.set(alert.trigger_rule, ep);
      } else {
        // Extend the ongoing episode
        ep.lastSeenAt = now;
      }

      if (!ep.toastedThisEpisode && now - ep.firstSeenAt >= SUSTAINED_MS) {
        ep.toastedThisEpisode = true;
        addToast(toastType, alert.title, alert.message, TOAST_DURATION_MS, onToastClick);
      }
    }
  }, [alerts, addToast, onToastClick]);
}
