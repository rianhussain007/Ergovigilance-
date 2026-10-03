/**
 * Frontend smoke tests (P0-2 from docs/DELIVERY_CHECKLIST.md).
 *
 * Covers the day-one flow: login → dashboard renders → sessions list loads
 * → alert center loads. Uses a mocked fetch layer (ui_posture/src/test/
 * fixtures.ts) with the real providers + routing, so it verifies the actual
 * component tree renders — not just unit-tested helpers.
 */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../App';
import { ThemeProvider } from '../hooks/useTheme';
import { ToastProvider } from '../hooks/useToast';
import { AuthProvider } from '../auth/AuthContext';
import { SettingsProvider } from '../hooks/useSettings';
import { AlertsProvider } from '../hooks/useAlertsContext';
import { I18nProvider } from '../i18n';
import { createFetchMock } from './fixtures';

function renderApp() {
  return render(
    <ThemeProvider>
      <ToastProvider>
        <I18nProvider>
          <AuthProvider>
            <SettingsProvider>
              <AlertsProvider>
                <App />
              </AlertsProvider>
            </SettingsProvider>
          </AuthProvider>
        </I18nProvider>
      </ToastProvider>
    </ThemeProvider>,
  );
}

describe('frontend smoke', () => {
  // Cold code-split chunks are the slowest part of this file: the 2026-09-28
  // qualification run spent ~52s in imports overall, and the first test below
  // timed out at its 10s waitFor while the dashboard chunk was still
  // transforming on a loaded box (the identical navigation passed in 927ms
  // once the module was warm). Warm the chunks this file navigates to once,
  // so each test's timeout measures app behaviour instead of Vite's cold
  // transform speed. Failing to warm up still fails this hook loudly.
  beforeAll(async () => {
    await Promise.all([
      import('../pages/DashboardPage'),
      import('../pages/LiveMonitoring'),
      import('../pages/SessionHistory'),
      import('../pages/ReportsPage'),
      import('../pages/SettingsPage'),
    ]);
  }, 180_000);

  beforeEach(() => {
    // Start at the login page: unauthenticated / renders the landing page,
    // not the auth form.
    window.history.pushState({}, '', '/login');
    vi.stubGlobal('fetch', createFetchMock());
    // The WebSocket hooks attempt real connections; stub them as inert.
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

  it('renders the login page and signs in to the dashboard', async () => {
    const user = userEvent.setup();
    localStorage.setItem('ergovigilance_onboarded', 'true');
    renderApp();

    // /login renders the sign-in form (no stored auth).
    await screen.findByRole('heading', { name: /sign in/i }, { timeout: 10000 });

    await user.click(screen.getByRole('button', { name: /sign in/i }));

    // After the mocked login, the form navigates to /dashboard. The route
    // pages are code-split (React.lazy); the chunks are pre-warmed in
    // beforeAll above, so this wait only needs to cover the login + render.
    await waitFor(
      () => {
        expect(screen.getByRole('heading', { name: /my dashboard/i })).toBeInTheDocument();
      },
      { timeout: 10000 },
    );
  });

  it('shows the live monitoring page for a signed-in operator', async () => {
    const user = userEvent.setup();
    localStorage.setItem('ergovigilance_onboarded', 'true');
    renderApp();
    await screen.findByRole('heading', { name: /sign in/i }, { timeout: 10000 });
    await user.click(screen.getByRole('button', { name: /sign in/i }));
    await screen.findByRole('heading', { name: /my dashboard/i }, { timeout: 10000 });

    await user.click(screen.getByRole('link', { name: /live monitoring/i }));
    await waitFor(
      () => {
        expect(screen.getByText(/live monitoring/i)).toBeInTheDocument();
      },
      { timeout: 10000 },
    );
  });

  it('loads the sessions list', async () => {
    const user = userEvent.setup();
    localStorage.setItem('ergovigilance_onboarded', 'true');
    renderApp();
    await screen.findByRole('heading', { name: /sign in/i }, { timeout: 10000 });
    await user.click(screen.getByRole('button', { name: /sign in/i }));
    await screen.findByRole('heading', { name: /my dashboard/i }, { timeout: 10000 });

    await user.click(screen.getByRole('link', { name: /sessions/i }));
    // The mocked sessions fixture has one completed session. The ID may
    // appear in more than one row/column, so assert at least one match.
    // Generous timeout: the lazy chunk loads on first navigation.
    await waitFor(
      () => {
        expect(screen.getAllByText(/SESH-2026-06-30-001/i).length).toBeGreaterThan(0);
      },
      { timeout: 10000 },
    );
  });

  it('renders the alert center with no-alerts state', async () => {
    const user = userEvent.setup();
    localStorage.setItem('ergovigilance_onboarded', 'true');
    renderApp();
    await screen.findByRole('heading', { name: /sign in/i }, { timeout: 10000 });
    await user.click(screen.getByRole('button', { name: /sign in/i }));
    await screen.findByRole('heading', { name: /my dashboard/i }, { timeout: 10000 });

    // The operator dashboard shows the alerts feed card (empty state).
    await waitFor(
      () => {
        expect(screen.getByText(/no alerts visible for your current scope/i)).toBeInTheDocument();
      },
      { timeout: 10000 },
    );
  });

  it('renders the settings page', async () => {
    const user = userEvent.setup();
    localStorage.setItem('ergovigilance_onboarded', 'true');
    renderApp();
    await screen.findByRole('heading', { name: /sign in/i }, { timeout: 10000 });
    await user.click(screen.getByRole('button', { name: /sign in/i }));
    await screen.findByRole('heading', { name: /my dashboard/i }, { timeout: 10000 });

    await user.click(screen.getByRole('link', { name: /settings/i }));
    await waitFor(
      () => {
        expect(screen.getByText(/settings/i)).toBeInTheDocument();
      },
      { timeout: 10000 },
    );
  });

  it('renders the reports page', async () => {
    const user = userEvent.setup();
    localStorage.setItem('ergovigilance_onboarded', 'true');
    renderApp();
    await screen.findByRole('heading', { name: /sign in/i }, { timeout: 10000 });
    await user.click(screen.getByRole('button', { name: /sign in/i }));
    await screen.findByRole('heading', { name: /my dashboard/i }, { timeout: 10000 });

    await user.click(screen.getByRole('link', { name: /reports/i }));
    // Reports page has a 'Generate Now' button and digest section
    await waitFor(
      () => {
        expect(screen.getByText(/generate, search, and download/i)).toBeInTheDocument();
      },
      { timeout: 10000 },
    );
  });

  it('shows a friendly error when the backend is unreachable', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(JSON.stringify({ detail: 'unreachable' }), { status: 503 })),
    );
    const user = userEvent.setup();
    renderApp();
    await screen.findByRole('heading', { name: /sign in/i }, { timeout: 10000 });
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    // Login failure surfaces the backend's message without crashing.
    await waitFor(
      () => {
        expect(screen.getByRole('alert')).toBeInTheDocument();
      },
      { timeout: 10000 },
    );
  });
});
