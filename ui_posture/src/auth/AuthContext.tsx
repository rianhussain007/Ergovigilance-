import React, { createContext, useContext, useMemo, useState } from 'react';

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
  logout: () => void;
  isDemoMode: boolean;
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

  const [isDemoMode, setIsDemoMode] = useState(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        return parsed?.demo === true;
      }
    } catch {}
    return false;
  });

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
    setIsDemoMode(false);
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
    setIsDemoMode(false);
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
    setIsDemoMode(true);
    setAuth(next);
  };

  const logout = () => {
    clearStoredAuth();
    setAuth(null);
  };

  const value = useMemo<AuthContextValue>(() => ({
    token: auth?.token ?? null,
    user: auth?.user ?? null,
    login,
    completeMfaLogin,
    demoLogin,
    logout,
    isDemoMode,
  }), [auth, isDemoMode]);

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
