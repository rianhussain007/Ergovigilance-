import { AUTH_INVALID_EVENT, clearStoredAuth, getStoredToken } from '@/src/auth/AuthContext';

/** Default per-request budget. Long enough for slow factory PCs, short enough
 *  that a stalled backend surfaces as an error instead of an infinite spinner. */
export const REQUEST_TIMEOUT_MS = 15000;

export type ApiErrorKind =
  | 'timeout'
  | 'network'
  | 'auth'
  | 'forbidden'
  | 'not_found'
  | 'server'
  | 'unavailable'
  | 'rate_limited'
  | 'client'
  | 'unknown';

/**
 * Normalized request failure. Every layer that calls the API can rely on
 * `kind` (what went wrong), `status` (when there was an HTTP response) and a
 * `message` that is safe to show a user — instead of raw "Failed to fetch
 * X: 500" strings leaking into the UI (audit F-UX-13).
 */
export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status?: number;

  constructor(message: string, options: { kind: ApiErrorKind; status?: number; cause?: unknown }) {
    super(message, options.cause !== undefined ? { cause: options.cause } : undefined);
    this.name = 'ApiError';
    this.kind = options.kind;
    this.status = options.status;
  }
}

export interface ApiRequestInit extends RequestInit {
  /** Override the per-request timeout (ms). */
  timeoutMs?: number;
  /** Extra attempts after the first failure. Defaults to 1 for idempotent GETs, 0 otherwise. */
  retries?: number;
  /** Base backoff between attempts (ms). Defaults to 300; doubles per attempt. */
  retryBackoffMs?: number;
}

export function authHeaders(init?: HeadersInit): Headers {
  const headers = new Headers(init);
  const token = getStoredToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  return headers;
}

/**
 * Fetch with a timeout, bearer auth, and the 401 → logout contract.
 *
 * A strict 403 (permission) never clears the session — only a 401 does.
 */
export async function apiFetch(input: RequestInfo | URL, init: ApiRequestInit = {}): Promise<Response> {
  const { timeoutMs = REQUEST_TIMEOUT_MS, signal, headers, ...rest } = init;
  // Bearer auth is injected here (unless a caller set Authorization itself) so
  // no call site can accidentally ship an unauthenticated request.
  const mergedHeaders = authHeaders(headers);

  const controller = new AbortController();
  let timedOut = false;
  const timer = timeoutMs > 0
    ? setTimeout(() => { timedOut = true; controller.abort(); }, timeoutMs)
    : undefined;

  const onExternalAbort = () => controller.abort();
  if (signal) {
    if (signal.aborted) controller.abort();
    else signal.addEventListener('abort', onExternalAbort, { once: true });
  }

  try {
    const res = await fetch(input, { ...rest, headers: mergedHeaders, signal: controller.signal });
    if (res.status === 401) {
      clearStoredAuth();
      window.dispatchEvent(new CustomEvent(AUTH_INVALID_EVENT));
    }
    return res;
  } catch (err) {
    if (timedOut) {
      throw new ApiError(
        `Request timed out after ${Math.round(timeoutMs / 1000)}s — the server did not answer. Check that the backend is running and try again.`,
        { kind: 'timeout', cause: err },
      );
    }
    if (signal?.aborted) {
      throw new ApiError('Request cancelled.', { kind: 'unknown', cause: err });
    }
    throw new ApiError(
      'Cannot reach the server — check that the backend is running and the network is up.',
      { kind: 'network', cause: err },
    );
  } finally {
    if (timer) clearTimeout(timer);
    signal?.removeEventListener('abort', onExternalAbort);
  }
}

function kindForStatus(status: number): ApiErrorKind {
  if (status === 401) return 'auth';
  if (status === 403) return 'forbidden';
  if (status === 404) return 'not_found';
  if (status === 408) return 'timeout';
  if (status === 429) return 'rate_limited';
  if (status === 503) return 'unavailable';
  if (status >= 500) return 'server';
  if (status >= 400) return 'client';
  return 'unknown';
}

function delay(ms: number) {
  return new Promise<void>((resolve) => setTimeout(resolve, ms));
}

function defaultRetries(method: string | undefined): number {
  const verb = (method ?? 'GET').toUpperCase();
  return verb === 'GET' || verb === 'HEAD' ? 1 : 0;
}

/**
 * `apiFetch` + retry with backoff for idempotent requests and transient
 * failures (timeout, network drop, 5xx). Non-GET requests are never retried.
 */
export async function apiFetchWithRetry(
  input: RequestInfo | URL,
  init: ApiRequestInit = {},
): Promise<Response> {
  const {
    retries = defaultRetries(init.method),
    retryBackoffMs = 300,
    ...rest
  } = init;

  let lastError: unknown;
  for (let attempt = 0; attempt <= retries; attempt += 1) {
    try {
      const res = await apiFetch(input, rest);
      if (res.status >= 500 && attempt < retries) {
        await delay(retryBackoffMs * 2 ** attempt);
        continue;
      }
      return res;
    } catch (err) {
      lastError = err;
      const retryable = err instanceof ApiError && (err.kind === 'timeout' || err.kind === 'network');
      if (!retryable || attempt >= retries) throw err;
      await delay(retryBackoffMs * 2 ** attempt);
    }
  }
  throw lastError;
}

/** Fetch + parse JSON, throwing a typed, user-message-safe `ApiError`. */
export async function apiFetchJson<T>(
  input: RequestInfo | URL,
  init: ApiRequestInit = {},
  label = 'Request',
): Promise<T> {
  const res = await apiFetchWithRetry(input, init);
  if (!res.ok) {
    throw new ApiError(friendlyHttpError(res.status, label), {
      kind: kindForStatus(res.status),
      status: res.status,
    });
  }
  return (await res.json()) as T;
}

/**
 * Normalize any thrown value into an `ApiError` whose message is safe to show.
 * Use this at the edge of hooks/components so users never see "TypeError:
 * Failed to fetch" or a bare status code.
 */
export function toApiError(err: unknown, label = 'Request'): ApiError {
  if (err instanceof ApiError) return err;
  if (err instanceof DOMException && (err.name === 'AbortError' || err.name === 'TimeoutError')) {
    return new ApiError(`${label} — the request took too long. Try again.`, { kind: 'timeout', cause: err });
  }
  if (err instanceof TypeError) {
    return new ApiError(
      `${label} — cannot reach the server. Check that the backend is running and the network is up.`,
      { kind: 'network', cause: err },
    );
  }
  return new ApiError(err instanceof Error ? err.message : `${label} — unexpected error.`, {
    kind: 'unknown',
    cause: err,
  });
}

export function friendlyHttpError(status: number, label: string): string {
  if (status === 503) return `${label} — backend server is not running. Start it with: cd backend_api && python -m uvicorn app.main:app --reload`;
  if (status === 500) return `${label} — server error. Check backend logs.`;
  if (status === 401) return `${label} — authentication failed. Please log in again.`;
  if (status === 403) return `${label} — your role does not have permission for this. Ask an administrator if you need access.`;
  if (status === 404) return `${label} — not found.`;
  if (status === 429) return `${label} — too many requests. Wait a moment and try again.`;
  return `${label} — request failed (${status}).`;
}
