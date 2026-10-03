import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';

export type Role = 'operator' | 'supervisor' | 'safety_mgr' | 'admin';

export interface AuthUser {
  id: number;
  email: string;
  role: Role;
}

interface AuthState {
  token: string;
  user: AuthUser;
}

interface AuthContextValue {
  token: string | null;
  user: AuthUser | null;
  login: (email: string, password: string) => Promise<void>;
  completeMfaLogin: (pendingToken: string, code: string) => Promise<void>;
  demoLogin: () => Promise<void>;
  /**
   * Adopt a token+user that was minted outside this provider (self-service
   * signup returns a ready session). Without this, signup could only write
   * storage directly and the in-memory auth state stayed null — the Layout
   * guard then bounced the brand-new admin straight back to /login.
   */
  adoptSession: (token: string, user: AuthUser) => void;
  logout: () => void;
  /**
   * True only when the BACKEND reports demo mode (`GET /api/demo-mode`). This is
   * what the "synthetic data" banner renders from — never a client-side guess.
   */
  isDemoMode: boolean;
  /**
   * True when THIS browser session was started with the Try Demo button. It is
   * a UX signal only (guided tour, onboarding suppression) and must never be
   * used to make a claim about what data the server is serving.
   */
  isDemoSession: boolean;
}

/**
 * Thrown by {@link AuthContextValue.login} when the password was correct but
 * the account has MFA enrolled. Carries the single-use challenge token the
 * code step must redeem — no access token is issued at this point.
 */
export class MfaRequiredError extends Error {
  readonly pendingToken: string;
  readonly expiresInSeconds: number;

  constructor(pendingToken: string, expiresInSeconds: number) {
    super('Two-factor code required');
    this.name = 'MfaRequiredError';
    this.pendingToken = pendingToken;
    this.expiresInSeconds = expiresInSeconds;
  }
}

const STORAGE_KEY = 'ergovigilance_auth';
export const AUTH_INVALID_EVENT = 'ergovigilance-auth-invalid';
const AuthContext = createContext<AuthContextValue | null>(null);

/** Decode a JWT's `exp` claim (epoch ms). Returns null when unreadable. */
export function getTokenExpiry(token: string): number | null {
  try {
    const payloadPart = token.split('.')[1];
    if (!payloadPart) return null;
    const normalized = payloadPart.replace(/-/g, '+').replace(/_/g, '/');
    const padded = normalized + '='.repeat((4 - (normalized.length % 4)) % 4);
    const payload = JSON.parse(atob(padded)) as { exp?: number };
    return typeof payload.exp === 'number' ? payload.exp * 1000 : null;
  } catch {
    return null;
  }
}

function loadStoredAuth(): AuthState | null {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as AuthState;
    const valid =
      typeof parsed?.token === 'string'
      && parsed.token.length > 0
      && typeof parsed?.user?.email === 'string'
      && typeof parsed?.user?.role === 'string';
    // Drop tokens that already expired so a stale session never survives a reload.
    const expiry = typeof parsed?.token === 'string' ? getTokenExpiry(parsed.token) : null;
    const expired = expiry !== null && expiry <= Date.now();
    if (!valid || expired) {
      localStorage.removeItem(STORAGE_KEY);
      return null;
    }
    return parsed;
  } catch {
    localStorage.removeItem(STORAGE_KEY);
    return null;
  }
}

export function clearStoredAuth() {
  localStorage.removeItem(STORAGE_KEY);
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [auth, setAuth] = useState<AuthState | null>(() => loadStoredAuth());

  React.useEffect(() => {
    const handleInvalidAuth = () => {
      clearStoredAuth();
      setAuth(null);
    };
    window.addEventListener(AUTH_INVALID_EVENT, handleInvalidAuth);
    return () => window.removeEventListener(AUTH_INVALID_EVENT, handleInvalidAuth);
  }, []);

  // `demo` in local storage records only that THIS session was started through
  // the Try Demo button. It is NOT evidence that the backend is serving
  // synthetic data — the backend reads DEMO_MODE once at import time, so a
  // server booted without it keeps answering with real rows. The banner in
  // Layout must therefore key off the server's answer (see demoModeConfirmed
  // below), never off this flag alone.
  const [demoLoginUsed, setDemoLoginUsed] = useState(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        return parsed?.demo === true;
      }
    } catch {}
    return false;
  });

  // Server-authoritative: does the backend actually report demo mode? Null
  // until answered; a failed probe is treated as "not demo" so the app never
  // claims synthetic data it cannot prove.
  const [demoModeConfirmed, setDemoModeConfirmed] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch('/api/demo-mode')
      .then((res) => (res.ok ? res.json() : null))
      .then((body) => {
        if (!cancelled) setDemoModeConfirmed(body?.demo_mode === true);
      })
      .catch(() => {
        if (!cancelled) setDemoModeConfirmed(false);
      });
    return () => {
      cancelled = true;
    };
  }, [auth?.token]);

  const isDemoMode = demoModeConfirmed === true;

  const login = async (email: string, password: string) => {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: email.trim(), password }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: 'Login failed' }));
      throw new Error(body.detail || `Login failed (${res.status})`);
    }
    const data = await res.json();
    // Password proved but MFA is enrolled: hand back the challenge instead of
    // storing anything — the caller switches to the code step.
    if (data.mfa_required) {
      throw new MfaRequiredError(data.pending_token, data.expires_in ?? 300);
    }
    const next = { token: data.token, user: data.user as AuthUser };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    setDemoLoginUsed(false);
    setAuth(next);
  };

  const completeMfaLogin = async (pendingToken: string, code: string) => {
    const res = await fetch('/api/auth/login/mfa', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pending_token: pendingToken, code: code.trim() }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: 'Verification failed' }));
      throw new Error(body.detail || `Verification failed (${res.status})`);
    }
    const data = await res.json();
    const next = { token: data.token, user: data.user as AuthUser };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    setDemoLoginUsed(false);
    setAuth(next);
  };

  const demoLogin = async () => {
    const res = await fetch('/api/auth/demo', { method: 'POST' });
    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: 'Demo login failed' }));
      throw new Error(body.detail || `Demo login failed (${res.status})`);
    }
    const data = await res.json();
    const next = { token: data.token, user: data.user as AuthUser, demo: true };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    // Every "Try Demo" must start with the guided tour — never carry over a
    // dismissal from a previous demo or real session.
    localStorage.removeItem('ergovigilance_tour_dismissed_at');
    setDemoLoginUsed(true);
    // Re-probe /api/demo-mode so the banner matches what the server is actually
    // serving (a fresh token changes the probe key).
    setDemoModeConfirmed(null);
    setAuth(next);
  };

  const adoptSession = (token: string, user: AuthUser) => {
    const next = { token, user };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    setDemoLoginUsed(false);
    setDemoModeConfirmed(null);
    setAuth(next);
  };

  const logout = () => {
    clearStoredAuth();
    setDemoLoginUsed(false);
    setDemoModeConfirmed(null);
    setAuth(null);
  };

  const value = useMemo<AuthContextValue>(() => ({
    token: auth?.token ?? null,
    user: auth?.user ?? null,
    login,
    completeMfaLogin,
    demoLogin,
    adoptSession,
    logout,
    isDemoMode,
    isDemoSession: demoLoginUsed,
  }), [auth, isDemoMode, demoLoginUsed]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}

export function getStoredToken(): string | null {
  return loadStoredAuth()?.token ?? null;
}
