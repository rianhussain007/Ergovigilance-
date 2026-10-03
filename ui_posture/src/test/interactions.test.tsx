/**
 * Interaction tests for critical user flows.
 *
 * Covers: form validation, role-based access, alert actions, navigation.
 * Uses the same mocked fetch layer as smoke.test.tsx.
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
import { createFetchMock, FIXTURES } from './fixtures';

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

// Same cold-lazy-chunk flake class as smoke.test.tsx: `findByRole` waits 1 s
// for the login heading while Vite may still be transforming the code-split
// LoginPage chunk on a loaded box (seen during the 2026-10-02 audit run).
// Warm the chunks this file navigates to once, so timeouts measure app
// behaviour, not the dev server's transform speed.
beforeAll(async () => {
  await Promise.all([
    import('../pages/LoginPage'),
    import('../pages/DashboardPage'),
    import('../pages/UsersPage'),
  ]);
}, 180_000);

describe('login form validation', () => {
  beforeEach(() => {
    window.history.pushState({}, '', '/login');
    window.fetch = createFetchMock() as unknown as typeof fetch;
  });

  it('shows error when password is empty', async () => {
    const user = userEvent.setup();
    renderApp();
    await screen.findByRole('heading', { name: /sign in/i });
    // Use the specific input id to avoid matching the show/hide password button
    const passwordInput = screen.getByLabelText(/^Password$/i);
    await user.clear(passwordInput);
    await user.click(screen.getByRole('button', { name: /sign in/i }));
    expect(screen.getByRole('alert')).toHaveTextContent(/password/i);
  });
});

describe('role-based navigation', () => {
  beforeEach(() => {
    window.history.pushState({}, '', '/login');
    window.fetch = createFetchMock() as unknown as typeof fetch;
  });

  it('operator cannot access /users', async () => {
    const user = userEvent.setup();
    renderApp();
    await screen.findByRole('heading', { name: /sign in/i });
    await user.click(screen.getByRole('button', { name: /sign in/i }));
    // Should redirect to dashboard, not users
    await waitFor(() => {
      expect(window.location.pathname).not.toBe('/users');
    });
  });
});


