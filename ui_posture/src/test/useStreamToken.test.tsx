import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { useStreamToken } from '../hooks/useStreamToken';

/**
 * Stream-token hook (sell-readiness QA: the API-JWT-in-query fix).
 * The mint endpoint needs no DB — these run fully hermetic with a
 * stubbed fetch.
 */
function stubFetchOnce(response: { ok: boolean; token?: string }) {
  return vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({
      ok: response.ok,
      json: async () => ({ token: response.token }),
    }))
  );
}

describe('useStreamToken', () => {
  beforeEach(() => {
    localStorage.setItem(
      'ergovigilance_auth',
      JSON.stringify({ token: 'api-jwt-for-mint-only', user: { id: 1, email: 't@x.com', role: 'admin' } })
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it('mints a token when active', async () => {
    stubFetchOnce({ ok: true, token: 'stream-abc' });
    const { result } = renderHook(() => useStreamToken(true));
    await waitFor(() => expect(result.current).toBe('stream-abc'));
    expect(fetch).toHaveBeenCalledWith(
      '/video/stream-token',
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('returns null when the mint call fails', async () => {
    stubFetchOnce({ ok: false });
    const { result } = renderHook(() => useStreamToken(true));
    await act(async () => {
      await Promise.resolve();
    });
    expect(result.current).toBeNull();
  });

  it('never fetches and stays null when inactive', async () => {
    const spy = vi.fn(async () => ({ ok: true, json: async () => ({ token: 'x' }) }));
    vi.stubGlobal('fetch', spy);
    const { result } = renderHook(() => useStreamToken(false));
    await act(async () => {
      await Promise.resolve();
    });
    expect(result.current).toBeNull();
    expect(spy).not.toHaveBeenCalled();
  });

  it('sends the API JWT as bearer for the mint call', async () => {
    let headers: Record<string, string> = {};
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_url: string, init?: RequestInit) => {
        headers = Object.fromEntries(new Headers(init?.headers).entries());
        return { ok: true, json: async () => ({ token: 't' }) };
      })
    );
    const { result } = renderHook(() => useStreamToken(true));
    await waitFor(() => expect(result.current).toBe('t'));
    expect(headers['authorization']).toBe('Bearer api-jwt-for-mint-only');
  });
});
