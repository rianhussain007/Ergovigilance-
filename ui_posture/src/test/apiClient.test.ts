import { describe, expect, it, vi } from 'vitest';
import { AUTH_INVALID_EVENT } from '../auth/AuthContext';
import { apiFetch, authHeaders, friendlyHttpError } from '../services/apiClient';

/**
 * apiClient (sell-readiness QA: none of the auth plumbing was covered).
 *
 * Every page fetches through apiFetch, so its two contracts matter:
 *   1. the stored JWT is attached as a bearer header, and
 *   2. a 401 clears the session and broadcasts AUTH_INVALID_EVENT exactly
 *      once (a strict 403 must NOT log the user out).
 */

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

describe('friendlyHttpError', () => {
  it('tells the operator how to start a missing backend on 503', () => {
    expect(friendlyHttpError(503, 'Sessions')).toContain('backend server is not running');
    expect(friendlyHttpError(503, 'Sessions')).toContain('uvicorn app.main:app');
  });

  it('maps 500 / 401 / 403 / 404 / other to distinct, labelled messages', () => {
    expect(friendlyHttpError(500, 'Reports')).toBe('Reports — server error. Check backend logs.');
    expect(friendlyHttpError(401, 'Users')).toBe('Users — authentication failed. Please log in again.');
    expect(friendlyHttpError(403, 'Users')).toBe('Users — authentication failed. Please log in again.');
    expect(friendlyHttpError(404, 'Workers')).toBe('Workers — not found.');
    expect(friendlyHttpError(418, 'Teapot')).toBe('Teapot — request failed (418).');
  });
});
