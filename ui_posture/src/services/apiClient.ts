import { AUTH_INVALID_EVENT, clearStoredAuth, getStoredToken } from '@/src/auth/AuthContext';

export function authHeaders(init?: HeadersInit): Headers {
  const headers = new Headers(init);
  const token = getStoredToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  return headers;
}

export async function apiFetch(input: RequestInfo | URL, init: RequestInit = {}) {
  const res = await fetch(input, {
    ...init,
    headers: authHeaders(init.headers),
  });
  if (res.status === 401) {
    clearStoredAuth();
    window.dispatchEvent(new CustomEvent(AUTH_INVALID_EVENT));
  }
  return res;
}

export function friendlyHttpError(status: number, label: string): string {
  if (status === 503) return `${label} — backend server is not running. Start it with: cd backend_api && python -m uvicorn app.main:app --reload`;
  if (status === 500) return `${label} — server error. Check backend logs.`;
  if (status === 401 || status === 403) return `${label} — authentication failed. Please log in again.`;
  if (status === 404) return `${label} — not found.`;
  return `${label} — request failed (${status}).`;
}
