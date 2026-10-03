/**
 * Layout route-guard coverage (sell-readiness QA: the redirect-to-dashboard
 * bug). routes.test.ts checks the sidebar↔rolePaths contract; this file
 * drives the actual guard inside the real Layout with lightweight probe
 * routes, so it asserts the redirect behaviour itself:
 *   - signed out → /login,
 *   - role without the path → silently redirected to /dashboard,
 *   - role with the path → the page renders where it stands.
 */
import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router';
import Layout from '../components/Layout';
import { ThemeProvider } from '../hooks/useTheme';
import { ToastProvider } from '../hooks/useToast';
import { AuthProvider } from '../auth/AuthContext';
import { SettingsProvider } from '../hooks/useSettings';
import { AlertsProvider } from '../hooks/useAlertsContext';
import { I18nProvider } from '../i18n';
import { createFetchMock } from './fixtures';

const AUTH_STORAGE_KEY = 'ergovigilance_auth';

function signInAs(role: 'operator' | 'admin') {
  localStorage.setItem(
    AUTH_STORAGE_KEY,
    JSON.stringify({
      token: 'header.payload.signature',
      user: { id: 1, email: `${role}@example.local`, role },
    }),
  );
}

function renderGuard(path: string) {
  return render(
    <ThemeProvider>
      <ToastProvider>
        <I18nProvider>
          <AuthProvider>
            <SettingsProvider>
              <AlertsProvider>
                <MemoryRouter initialEntries={[path]}>
                  <Routes>
                    <Route element={<Layout />}>
                      <Route path="/dashboard" element={<div>DASHBOARD PROBE</div>} />
                      <Route path="/users" element={<div>USERS PROBE</div>} />
                    </Route>
                    <Route path="/login" element={<div>LOGIN PROBE</div>} />
                  </Routes>
                </MemoryRouter>
              </AlertsProvider>
            </SettingsProvider>
          </AuthProvider>
        </I18nProvider>
      </ToastProvider>
    </ThemeProvider>,
  );
}

describe('Layout route guard', () => {
  beforeEach(() => {
    localStorage.setItem('ergovigilance_onboarded', 'true');
    vi.stubGlobal('fetch', createFetchMock());
    vi.stubGlobal('WebSocket', class {
      static CONNECTING = 0;
      static OPEN = 1;
      static CLOSING = 2;
      static CLOSED = 3;
      readyState = 3;
      onopen: unknown = null;
      onmessage: unknown = null;
      onerror: unknown = null;
      onclose: unknown = null;
      close() {}
      send() {}
    });
  });

  it('bounces a signed-out visitor to /login', async () => {
    renderGuard('/dashboard');

    await screen.findByText('LOGIN PROBE');
    expect(screen.queryByText('DASHBOARD PROBE')).not.toBeInTheDocument();
  });

  it('explains the refusal on the admin-only /users route instead of redirecting', async () => {
    signInAs('operator');
    renderGuard('/users');

    const denial = await screen.findByTestId('access-denied');
    expect(denial).toHaveTextContent('/users');
    expect(denial).toHaveTextContent(/Operator role/i);
    expect(denial).toHaveTextContent(/available to Admin/i);
    // The restricted page must not mount — this is what stops the operator
    // 403 spikes on pages like /users and /setup.
    expect(screen.queryByText('USERS PROBE')).not.toBeInTheDocument();
    // …and navigation stays usable.
    expect(screen.getByRole('link', { name: /go to dashboard/i })).toBeInTheDocument();

    // The denial reaches the shared live region, so a screen-reader user hears
    // why the page changed instead of landing on unexplained content.
    await waitFor(() => {
      expect(document.getElementById('a11y-announcer')?.textContent).toMatch(/access denied/i);
    });
  });

  it('lets an admin stay on /users', async () => {
    signInAs('admin');
    renderGuard('/users');

    await screen.findByText('USERS PROBE');
    expect(screen.queryByText('DASHBOARD PROBE')).not.toBeInTheDocument();
  });
});
