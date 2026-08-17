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
import { beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../App';
import { ThemeProvider } from '../hooks/useTheme';
import { ToastProvider } from '../hooks/useToast';
import { AuthProvider } from '../auth/AuthContext';
import { SettingsProvider } from '../hooks/useSettings';
import { AlertsProvider } from '../hooks/useAlertsContext';
import { createFetchMock } from './fixtures';

function renderApp() {
  return render(
    <ThemeProvider>
      <ToastProvider>
        <AuthProvider>
          <SettingsProvider>
            <AlertsProvider>
              <App />
            </AlertsProvider>
          </SettingsProvider>
        </AuthProvider>
      </ToastProvider>
    </ThemeProvider>,
  );
}

describe('frontend smoke', () => {
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
    renderApp();

    // /login renders the sign-in form (no stored auth).
    await screen.findByRole('heading', { name: /sign in/i }, { timeout: 10000 });

    await user.click(screen.getByRole('button', { name: /sign in/i }));

    // After the mocked login, the form navigates to /dashboard. The route
    // pages are code-split (React.lazy), so the first navigation loads the
    // dashboard chunk dynamically — give it generous time in CI (smoke tests
    // routinely see 4-6s chunk loads on a loaded dev machine).
    await waitFor(
      () => {
        expect(screen.getByRole('heading', { name: /my dashboard/i })).toBeInTheDocument();
      },
      { timeout: 10000 },
    );
  });

  it('shows the live monitoring page for a signed-in operator', async () => {
    const user = userEvent.setup();
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
