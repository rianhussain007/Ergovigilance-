import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { usePolledResource, useVisibilityAwareInterval } from '../hooks/usePolling';

/**
 * Polling primitives (audit F-UX-04).
 *
 * The pre-existing hand-rolled pollers had no shared contract, so the
 * behaviours asserted here — pause while hidden, backoff on repeated failure,
 * and a `degraded` flag that keeps last-good data — are what stops a flaky
 * backend from blanking a monitoring screen or hammering it in a loop.
 */

const AUTH_STORAGE_KEY = 'ergovigilance_auth';

function storeToken() {
  localStorage.setItem(
    AUTH_STORAGE_KEY,
    JSON.stringify({ token: 'jwt-abc', user: { id: 1, email: 'op@example.com', role: 'operator' } })
  );
}

function setVisibility(state: 'visible' | 'hidden') {
  Object.defineProperty(document, 'visibilityState', {
    configurable: true,
    get: () => state,
  });
  document.dispatchEvent(new Event('visibilitychange'));
}

afterEach(() => {
  delete (document as unknown as Record<string, unknown>).visibilityState;
  localStorage.clear();
  vi.useRealTimers();
});

describe('usePolledResource', () => {
  it('loads on mount and exposes the fetched value', async () => {
    storeToken();
    const fetcher = vi.fn().mockResolvedValue({ count: 3 });

    const { result } = renderHook(() =>
      usePolledResource(fetcher, { initial: { count: 0 }, label: 'Workers' })
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toEqual({ count: 3 });
    expect(result.current.error).toBeNull();
    expect(result.current.degraded).toBe(false);
  });

  it('surfaces a first-load failure as an error', async () => {
    storeToken();
    const fetcher = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'));

    const { result } = renderHook(() =>
      usePolledResource(fetcher, { initial: [], label: 'Alerts' })
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toContain('Alerts');
    expect(result.current.degraded).toBe(true);
  });

  it('keeps last-good data and flags degraded when a later poll fails', async () => {
    vi.useFakeTimers();
    storeToken();
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce({ ok: true })
      .mockRejectedValue(new TypeError('Failed to fetch'));

    const { result } = renderHook(() =>
      usePolledResource(fetcher, { initial: { ok: false }, intervalMs: 1000, label: 'Sessions' })
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(result.current.data).toEqual({ ok: true });
    expect(result.current.error).toBeNull();
    expect(result.current.degraded).toBe(false);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1100);
    });
    expect(result.current.data).toEqual({ ok: true });
    expect(result.current.error).toBeNull();
    expect(result.current.degraded).toBe(true);
  });

  it('backs off after consecutive failures instead of hammering the backend', async () => {
    vi.useFakeTimers();
    storeToken();
    const fetcher = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'));

    renderHook(() =>
      usePolledResource(fetcher, { initial: 0, intervalMs: 1000, maxBackoffMultiplier: 4 })
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(fetcher).toHaveBeenCalledTimes(1);

    // Failure #1 → next attempt is 2× the interval away (t = 2000).
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(fetcher).toHaveBeenCalledTimes(1);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1100);
    });
    expect(fetcher).toHaveBeenCalledTimes(2);

    // Failure #2 → 4× the interval (t = 6000).
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
    expect(fetcher).toHaveBeenCalledTimes(2);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1100);
    });
    expect(fetcher).toHaveBeenCalledTimes(3);
  });

  it('does not fetch while the tab is hidden, then refreshes once on return', async () => {
    storeToken();
    setVisibility('hidden');
    const fetcher = vi.fn().mockResolvedValue('fresh');

    const { result } = renderHook(() =>
      usePolledResource(fetcher, { initial: 'initial', intervalMs: 1000 })
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(fetcher).not.toHaveBeenCalled();
    expect(result.current.data).toBe('initial');

    act(() => setVisibility('visible'));
    await waitFor(() => expect(result.current.data).toBe('fresh'));
  });

  it('skips fetching while signed out and never renders an error for it', async () => {
    const fetcher = vi.fn().mockResolvedValue('should-not-load');

    const { result } = renderHook(() =>
      usePolledResource(fetcher, { initial: 'initial', label: 'Alerts' })
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(fetcher).not.toHaveBeenCalled();
    expect(result.current.data).toBe('initial');
    expect(result.current.error).toBeNull();
    expect(result.current.degraded).toBe(false);
  });

  it('refetch triggers an immediate reload', async () => {
    vi.useFakeTimers();
    storeToken();
    const fetcher = vi.fn().mockResolvedValueOnce(1).mockResolvedValueOnce(2);

    const { result } = renderHook(() => usePolledResource(fetcher, { initial: 0, intervalMs: null }));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(result.current.data).toBe(1);

    act(() => result.current.refetch());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(result.current.data).toBe(2);
  });
});

describe('useVisibilityAwareInterval', () => {
  it('stops ticking while hidden and fires immediately when visible again', async () => {
    vi.useFakeTimers();
    const callback = vi.fn();

    renderHook(() => useVisibilityAwareInterval(callback, 1000));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
    expect(callback).toHaveBeenCalledTimes(3);

    act(() => setVisibility('hidden'));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(callback).toHaveBeenCalledTimes(3);

    act(() => setVisibility('visible'));
    expect(callback).toHaveBeenCalledTimes(4);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(callback).toHaveBeenCalledTimes(5);
  });

  it('is inert when the interval is null', async () => {
    vi.useFakeTimers();
    const callback = vi.fn();

    renderHook(() => useVisibilityAwareInterval(callback, null));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(callback).not.toHaveBeenCalled();
  });
});
