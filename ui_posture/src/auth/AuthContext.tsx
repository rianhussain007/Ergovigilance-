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
  logout: () => void;
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
    const next = { token: data.token, user: data.user as AuthUser };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
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
    logout,
  }), [auth]);

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
