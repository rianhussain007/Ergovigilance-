import { afterEach, describe, expect, it, vi } from 'vitest';
import { AUTH_INVALID_EVENT } from '../auth/AuthContext';
import {
  ApiError,
  REQUEST_TIMEOUT_MS,
  apiFetch,
  apiFetchJson,
  apiFetchWithRetry,
  authHeaders,
  friendlyHttpError,
  toApiError,
} from '../services/apiClient';

/**
 * apiClient (sell-readiness QA: none of the auth plumbing was covered).
 *
 * Every page fetches through apiFetch, so its two contracts matter:
 *   1. the stored JWT is attached as a bearer header,
 *   2. a 401 clears the session and broadcasts AUTH_INVALID_EVENT exactly
 *      once (a strict 403 must NOT log the user out),
 *   3. a stalled request aborts and surfaces as an ApiError('timeout') rather
 *      than hanging a page forever, and
 *   4. transient GET failures retry with backoff while POSTs never do.
 */

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
  localStorage.clear();
});

const AUTH_STORAGE_KEY = 'ergovigilance_auth';

function storeToken(token = 'jwt-abc') {
  localStorage.setItem(
    AUTH_STORAGE_KEY,
    JSON.stringify({ token, user: { id: 1, email: 'op@example.com', role: 'operator' } })
  );
}

describe('authHeaders', () => {
  it('adds nothing when there is no stored token', () => {
    expect(authHeaders().has('Authorization')).toBe(false);
  });

  it('attaches the stored JWT as a bearer header', () => {
    storeToken();
    expect(authHeaders().get('Authorization')).toBe('Bearer jwt-abc');
  });

  it('preserves caller headers (e.g. Content-Type)', () => {
    storeToken();
    const headers = authHeaders({ 'Content-Type': 'application/json' });
    expect(headers.get('Content-Type')).toBe('application/json');
    expect(headers.get('Authorization')).toBe('Bearer jwt-abc');
  });
});

describe('apiFetch', () => {
  it('passes the response through and attaches the bearer token', async () => {
    storeToken();
    const mockFetch = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => new Response('{}', { status: 200 }));
    vi.stubGlobal('fetch', mockFetch);

    const res = await apiFetch('/api/workers', { method: 'GET' });

    expect(res.status).toBe(200);
    const init = mockFetch.mock.calls[0][1] as RequestInit;
    const headers = new Headers(init.headers);
    expect(headers.get('Authorization')).toBe('Bearer jwt-abc');
  });

  it('clears the stored session and emits AUTH_INVALID_EVENT on 401', async () => {
    storeToken();
    const listener = vi.fn();
    window.addEventListener(AUTH_INVALID_EVENT, listener);
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 401 })));

    try {
      await apiFetch('/api/dashboard');
      expect(localStorage.getItem(AUTH_STORAGE_KEY)).toBeNull();
      expect(listener).toHaveBeenCalledTimes(1);
    } finally {
      window.removeEventListener(AUTH_INVALID_EVENT, listener);
    }
  });

  it('keeps the session on a 403 (permission, not invalidity)', async () => {
    storeToken();
    const listener = vi.fn();
    window.addEventListener(AUTH_INVALID_EVENT, listener);
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 403 })));

    try {
      await apiFetch('/api/users');
      expect(localStorage.getItem(AUTH_STORAGE_KEY)).not.toBeNull();
      expect(listener).not.toHaveBeenCalled();
    } finally {
      window.removeEventListener(AUTH_INVALID_EVENT, listener);
    }
  });
});

describe('apiFetch timeouts', () => {
  it('aborts a stalled request and throws ApiError(kind="timeout")', async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      'fetch',
      vi.fn(
        (_input: RequestInfo | URL, init?: RequestInit) =>
          new Promise<Response>((_resolve, reject) => {
            init?.signal?.addEventListener('abort', () =>
              reject(new DOMException('Aborted', 'AbortError')),
            );
          }),
      ),
    );

    const promise = apiFetch('/api/dashboard', { timeoutMs: 1000 });
    const assertion = expect(promise).rejects.toMatchObject({ name: 'ApiError', kind: 'timeout' });
    await vi.advanceTimersByTimeAsync(1001);
    await assertion;
  });

  it('surfaces a network failure as ApiError(kind="network")', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('Failed to fetch'); }));
    await expect(apiFetch('/api/dashboard')).rejects.toMatchObject({ kind: 'network' });
  });

  it('honours an external abort signal without reporting a timeout', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        (_input: RequestInfo | URL, init?: RequestInit) =>
          new Promise<Response>((_resolve, reject) => {
            init?.signal?.addEventListener('abort', () =>
              reject(new DOMException('Aborted', 'AbortError')),
            );
          }),
      ),
    );
    const controller = new AbortController();
    const promise = apiFetch('/api/dashboard', { signal: controller.signal, timeoutMs: 60_000 });
    controller.abort();
    await expect(promise).rejects.toBeInstanceOf(ApiError);
    await expect(promise).rejects.not.toMatchObject({ kind: 'timeout' });
  });

  it('uses a documented default timeout', () => {
    expect(REQUEST_TIMEOUT_MS).toBeGreaterThanOrEqual(5000);
    expect(REQUEST_TIMEOUT_MS).toBeLessThanOrEqual(60_000);
  });
});

describe('apiFetchWithRetry', () => {
  it('retries a 5xx GET once, then returns the failure response', async () => {
    const mockFetch = vi.fn(async () => new Response('{}', { status: 503 }));
    vi.stubGlobal('fetch', mockFetch);

    const res = await apiFetchWithRetry('/api/workers', { retryBackoffMs: 1 });

    expect(res.status).toBe(503);
    expect(mockFetch).toHaveBeenCalledTimes(2);
  });

  it('never retries a non-idempotent request', async () => {
    const mockFetch = vi.fn(async () => new Response('{}', { status: 500 }));
    vi.stubGlobal('fetch', mockFetch);

    const res = await apiFetchWithRetry('/api/workers', { method: 'POST', retryBackoffMs: 1 });

    expect(res.status).toBe(500);
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it('recovers when a retry succeeds', async () => {
    const mockFetch = vi
      .fn()
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce(new Response('{"ok":true}', { status: 200 }));
    vi.stubGlobal('fetch', mockFetch);

    const res = await apiFetchWithRetry('/api/workers', { retryBackoffMs: 1 });
    expect(res.status).toBe(200);
  });
});

describe('apiFetchJson', () => {
  it('parses JSON and labels the resource in typed errors', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{"count":2}', { status: 200 })));
    await expect(apiFetchJson<{ count: number }>('/api/workers', {}, 'Workers')).resolves.toEqual({
      count: 2,
    });

    vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 403 })));
    await expect(apiFetchJson('/api/workers', {}, 'Workers')).rejects.toMatchObject({
      kind: 'forbidden',
      status: 403,
    });
  });
});

describe('toApiError', () => {
  it('passes ApiError instances through untouched', () => {
    const original = new ApiError('boom', { kind: 'server', status: 500 });
    expect(toApiError(original, 'Reports')).toBe(original);
  });

  it('translates raw fetch TypeErrors into a labelled network message', () => {
    const err = toApiError(new TypeError('Failed to fetch'), 'Reports');
    expect(err.kind).toBe('network');
    expect(err.message).toContain('Reports');
    expect(err.message).toContain('cannot reach the server');
  });
});

describe('friendlyHttpError', () => {
  it('tells the operator how to start a missing backend on 503', () => {
    expect(friendlyHttpError(503, 'Sessions')).toContain('backend server is not running');
    expect(friendlyHttpError(503, 'Sessions')).toContain('uvicorn app.main:app');
  });

  it('maps 500 / 401 / 403 / 404 / other to distinct, labelled messages', () => {
    expect(friendlyHttpError(500, 'Reports')).toBe('Reports — server error. Check backend logs.');
    expect(friendlyHttpError(401, 'Users')).toBe('Users — authentication failed. Please log in again.');
    expect(friendlyHttpError(403, 'Users')).toBe(
      'Users — your role does not have permission for this. Ask an administrator if you need access.',
    );
    expect(friendlyHttpError(404, 'Workers')).toBe('Workers — not found.');
    expect(friendlyHttpError(418, 'Teapot')).toBe('Teapot — request failed (418).');
  });
});
