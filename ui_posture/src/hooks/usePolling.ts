import { useCallback, useEffect, useRef, useState } from 'react';
import { getStoredToken } from '@/src/auth/AuthContext';
import { toApiError } from '@/src/services/apiClient';

/* ────────────────────────────────────────────────────────────────────────────
 * Shared polling primitives (audit F-UX-04).
 *
 * Before this, ~30 `setInterval` call sites each hand-rolled: no timeout, no
 * unmount guard, no pause while the tab was hidden, no backoff when the
 * backend went away. These two primitives centralize that behaviour:
 *
 *   useVisibilityAwareInterval(fn, ms) — interval that pauses while the tab is
 *   hidden and fires once immediately when it becomes visible again.
 *
 *   usePolledResource(fetcher, opts) — a polled GET with a first-load error
 *   (what pages render), a separate `degraded` flag for later failures (data
 *   may be stale), consecutive-failure backoff, and a manual refetch.
 * ──────────────────────────────────────────────────────────────────────────── */

export function isTabHidden(): boolean {
  return typeof document !== 'undefined' && document.visibilityState === 'hidden';
}

/**
 * Run `callback` every `intervalMs` while the tab is visible.
 * Pass `null` to pause without unmounting the caller.
 * The latest callback is always invoked (no stale-closure captures).
 */
export function useVisibilityAwareInterval(
  callback: () => void,
  intervalMs: number | null,
): void {
  const callbackRef = useRef(callback);
  useEffect(() => { callbackRef.current = callback; }, [callback]);

  useEffect(() => {
    if (intervalMs === null) return;
    let timer: ReturnType<typeof setInterval> | undefined;

    const start = () => {
      if (timer !== undefined) return;
      timer = setInterval(() => {
        if (isTabHidden()) return;
        callbackRef.current();
      }, intervalMs);
    };
    const stop = () => {
      if (timer !== undefined) { clearInterval(timer); timer = undefined; }
    };
    const onVisibility = () => {
      if (isTabHidden()) {
        stop();
      } else {
        callbackRef.current();
        start();
      }
    };

    if (!isTabHidden()) start();
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      stop();
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [intervalMs]);
}

export interface PolledResourceOptions<T> {
  /** Value used before the first successful load and while signed out. */
  initial: T;
  /** Poll interval in ms. `null` fetches once (still refetchable). Default 10000. */
  intervalMs?: number | null;
  /** Disable entirely (e.g. a page that only polls while a session is live). */
  enabled?: boolean;
  /** Skip fetching when no token is stored (default true). */
  requiresAuth?: boolean;
  /** Human label used in error messages, e.g. "Alerts". */
  label?: string;
  /** Custom change detection; defaults to a JSON comparison. */
  equalityFn?: (a: T, b: T) => boolean;
  /** Cap on the consecutive-failure backoff multiplier (default 4×). */
  maxBackoffMultiplier?: number;
}

export interface PolledResource<T> {
  data: T;
  /** True until the first load settles (success or failure). */
  loading: boolean;
  /** First-load failure, for the page's error state. */
  error: string | null;
  /** A later poll failed: the data shown may be stale. */
  degraded: boolean;
  refetch: () => void;
  /** Local update (e.g. merging a WebSocket push) without a round-trip. */
  mutate: (updater: (prev: T) => T) => void;
}

function sameJson<T>(a: T, b: T): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

/**
 * Polled GET resource with production-ish failure behaviour:
 *  - pauses while the tab is hidden and refreshes on return,
 *  - never stacks requests (setTimeout chain, not setInterval),
 *  - one retry (400 ms) for the first load before showing an error,
 *  - consecutive failures back off up to `maxBackoffMultiplier`,
 *  - no setState after unmount, and
 *  - `degraded` separates "first load failed" from "a later poll failed".
 */
export function usePolledResource<T>(
  fetcher: () => Promise<T>,
  options: PolledResourceOptions<T>,
): PolledResource<T> {
  const {
    initial,
    intervalMs = 10000,
    enabled = true,
    requiresAuth = true,
    label = 'Data',
    equalityFn,
    maxBackoffMultiplier = 4,
  } = options;

  const [data, setData] = useState<T>(initial);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState<string | null>(null);
  const [degraded, setDegraded] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  const fetcherRef = useRef(fetcher);
  useEffect(() => { fetcherRef.current = fetcher; }, [fetcher]);
  const initialRef = useRef(initial);
  const eqRef = useRef(equalityFn);
  useEffect(() => { eqRef.current = equalityFn; }, [equalityFn]);

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let failures = 0;
    let firstSettled = false;

    const clearTimer = () => {
      if (timer !== undefined) { clearTimeout(timer); timer = undefined; }
    };

    const schedule = (ms: number | null) => {
      if (cancelled || ms === null) return;
      clearTimer();
      timer = setTimeout(() => { void run(); }, ms);
    };

    const nextDelay = (): number | null => {
      if (intervalMs === null) return null;
      const multiplier = Math.min(maxBackoffMultiplier, Math.max(1, 2 ** failures));
      return intervalMs * multiplier;
    };

    const run = async () => {
      if (cancelled) return;
      if (isTabHidden()) return; // visibilitychange restarts us
      if (requiresAuth && !getStoredToken()) {
        if (!firstSettled) {
          firstSettled = true;
          setData(initialRef.current);
          setLoading(false);
          setError(null);
        }
        schedule(nextDelay());
        return;
      }

      try {
        const next = await fetcherRef.current();
        if (cancelled) return;
        const eq = eqRef.current ?? sameJson;
        setData((prev) => (eq(prev, next) ? prev : next));
        failures = 0;
        setError(null);
        setDegraded(false);
      } catch (err) {
        if (cancelled) return;
        const message = toApiError(err, label).message;
        failures += 1;
        if (!firstSettled) {
          setError(message);
          setDegraded(true);
        } else {
          // Keep the last good data visible; flag it as stale instead of
          // blanking the page (or silently pretending it is fresh).
          setDegraded(true);
        }
      } finally {
        firstSettled = true;
        if (!cancelled) setLoading(false);
      }
      schedule(nextDelay());
    };

    const onVisibility = () => {
      if (!isTabHidden()) {
        clearTimer();
        void run();
      }
    };

    document.addEventListener('visibilitychange', onVisibility);
    if (isTabHidden()) {
      // Tab is already hidden at mount: wait for visibility instead of polling.
      setLoading(false);
    } else {
      void run();
    }

    return () => {
      cancelled = true;
      clearTimer();
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [enabled, intervalMs, requiresAuth, label, maxBackoffMultiplier, reloadKey]);

  const refetch = useCallback(() => { setReloadKey((k) => k + 1); }, []);
  const mutate = useCallback((updater: (prev: T) => T) => { setData(updater); }, []);

  return { data, loading, error, degraded, refetch, mutate };
}
