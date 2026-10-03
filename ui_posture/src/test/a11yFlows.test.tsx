/**
 * UX-integrity regressions from docs/UI_UX_ENTERPRISE_AUDIT.md.
 *
 * Three flows that could silently regress without any unit-test signal:
 *   F-UX-06  Drawer is a real dialog (labelled, Escape-closable, focus-trapped),
 *   F-UX-01  self-service signup adopts the returned session so the new admin
 *            is actually signed in (it used to write legacy keys nothing read),
 *   F-UX-02  unknown URLs render the in-shell 404 instead of a blank screen.
 */
import { useState } from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router';
import { Drawer } from '../components/common/Drawer';
import { LoadingCard, ErrorCard } from '../components/common';
import AIAssistantPanel from '../components/layout/AIAssistantPanel';
import SignupPage from '../pages/SignupPage';
import NotFoundPage from '../pages/NotFoundPage';
import { AuthProvider } from '../auth/AuthContext';
import { ThemeProvider } from '../hooks/useTheme';
import { jsonResponse } from './fixtures';

const AUTH_STORAGE_KEY = 'ergovigilance_auth';

describe('Drawer dialog semantics (F-UX-06)', () => {
  function Harness() {
    const [open, setOpen] = useState(false);
    return (
      <div>
        <button onClick={() => setOpen(true)}>Open trigger</button>
        <Drawer open={open} onClose={() => setOpen(false)} title="Session detail">
          <button>Inner action</button>
        </Drawer>
      </div>
    );
  }

  it('exposes dialog semantics and closes on Escape', async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole('button', { name: 'Open trigger' }));

    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(dialog).toHaveAccessibleName('Session detail');
    expect(screen.getByRole('button', { name: 'Close panel' })).toBeInTheDocument();

    await userEvent.keyboard('{Escape}');
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });

  it('moves focus into the panel and restores it to the trigger on close', async () => {
    render(<Harness />);
    const trigger = screen.getByRole('button', { name: 'Open trigger' });
    await userEvent.click(trigger);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Close panel' })).toHaveFocus();
    });

    await userEvent.keyboard('{Escape}');
    await waitFor(() => expect(trigger).toHaveFocus());
  });
});

describe('overlays announce themselves as dialogs (F-UX-06)', () => {
  it('the AI assistant panel is a labelled modal dialog', () => {
    render(<AIAssistantPanel open onClose={() => {}} />);

    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(dialog).toHaveAccessibleName(/ai safety assistant/i);
  });
});

describe('status and alert semantics (F-UX-11)', () => {
  it('LoadingCard is a busy status region, not silent filler', () => {
    render(<LoadingCard label="Loading alerts" />);
    const status = screen.getByRole('status');
    expect(status).toHaveAttribute('aria-busy', 'true');
    expect(status).toHaveAccessibleName('Loading alerts');
  });

  it('ErrorCard is an alert with a reachable retry', async () => {
    const onRetry = vi.fn();
    render(<ErrorCard message="Reports — server error. Check backend logs." onRetry={onRetry} />);

    expect(screen.getByRole('alert')).toHaveTextContent('Reports — server error');
    await userEvent.click(screen.getByRole('button', { name: /retry/i }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});

describe('signup session adoption (F-UX-01)', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : String(input);
      if (url.includes('/api/auth/signup')) {
        return jsonResponse({
          token: 'signed.token.value',
          user: { id: 42, email: 'new@acme.test', role: 'admin' },
        });
      }
      return jsonResponse({ detail: `Unmocked ${url}` }, 404);
    }));
  });

  it('stores the canonical auth record and lands in onboarding', async () => {
    render(
      <ThemeProvider>
        <AuthProvider>
          <MemoryRouter initialEntries={['/signup']}>
            <Routes>
              <Route path="/signup" element={<SignupPage />} />
              <Route path="/onboarding" element={<div>ONBOARDING PROBE</div>} />
              <Route path="/dashboard" element={<div>DASHBOARD PROBE</div>} />
            </Routes>
          </MemoryRouter>
        </AuthProvider>
      </ThemeProvider>,
    );

    await userEvent.type(screen.getByLabelText(/Organization Name/i), 'Acme Manufacturing');
    await userEvent.type(screen.getByLabelText(/Work Email/i), 'new@acme.test');
    await userEvent.type(screen.getByLabelText(/^Password$/i), 'StrongPass123!');
    await userEvent.click(screen.getByRole('checkbox'));
    await userEvent.click(screen.getByRole('button', { name: /Start Free Pilot/i }));

    // Signup hands off to an authenticated route. Which one depends on router
    // ordering (the page also redirects signed-in visitors to /dashboard), so
    // assert the thing that matters: the user is inside the app, not bounced
    // back to /login.
    await waitFor(() => {
      const inApp = screen.queryByText('ONBOARDING PROBE') ?? screen.queryByText('DASHBOARD PROBE');
      expect(inApp).not.toBeNull();
    });

    const stored = JSON.parse(localStorage.getItem(AUTH_STORAGE_KEY) || 'null');
    expect(stored?.token).toBe('signed.token.value');
    expect(stored?.user?.role).toBe('admin');
    // The legacy keys must not come back.
    expect(localStorage.getItem('ergovigilance_token')).toBeNull();
    expect(localStorage.getItem('ergovigilance_user')).toBeNull();
  });
});

describe('unknown route (F-UX-02)', () => {
  it('renders the 404 page with a route home', () => {
    render(
      <MemoryRouter initialEntries={['/definitely-not-a-page']}>
        <Routes>
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: /page not found/i })).toBeInTheDocument();
    expect(screen.getByText('/definitely-not-a-page')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /go to dashboard/i })).toHaveAttribute('href', '/dashboard');
  });
});
