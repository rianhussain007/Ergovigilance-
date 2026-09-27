import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router';
import OnboardingChecklistPage from '../pages/OnboardingChecklistPage';
import { AuthProvider } from '../auth/AuthContext';
import { jsonResponse } from './fixtures';

/**
 * Onboarding wizard logic (sell-readiness QA: fabricated results and a
 * wrong endpoint). The wizard is the first thing a new pilot sees, so the
 * contracts under test are:
 *   - webcam needs no network; RTSP registers with the cloud core,
 *   - a failed step stays on that step with the real reason (never a fake
 *     "ready" / fake LOW result),
 *   - worker creation and the test session hit the real endpoints, and
 *   - finishing (or skipping) marks the install onboarded and lands on the
 *     dashboard.
 */

type FetchHandler = (init?: RequestInit) => Response;

function stubFetch(routes: Record<string, FetchHandler>) {
  const mock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const key = `${(init?.method ?? 'GET').toUpperCase()} ${String(input)}`;
    const handler = routes[key];
    if (!handler) return jsonResponse({ detail: `unmocked ${key}` }, 404);
    return handler(init);
  });
  vi.stubGlobal('fetch', mock);
  return mock;
}

function renderWizard() {
  return render(
    <MemoryRouter initialEntries={['/onboarding']}>
      <AuthProvider>
        <Routes>
          <Route path="/onboarding" element={<OnboardingChecklistPage />} />
          <Route path="/dashboard" element={<div>DASHBOARD PROBE</div>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

async function toCameraStep(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('button', { name: /get started/i }));
  await screen.findByRole('heading', { name: 'First Camera' });
}

async function toWorkerStep(user: ReturnType<typeof userEvent.setup>) {
  await toCameraStep(user);
  await user.click(screen.getByRole('button', { name: /use webcam/i }));
  await screen.findByRole('heading', { name: 'First Worker' });
}

async function toMonitorStep(user: ReturnType<typeof userEvent.setup>) {
  await toWorkerStep(user);
  await user.type(screen.getByPlaceholderText(/e\.g\. Rajesh Kumar/i), 'Rajesh Kumar');
  await user.click(screen.getByRole('button', { name: /add worker/i }));
  await screen.findByRole('heading', { name: 'Start Monitoring' });
}

const WORKER_OK: Record<string, FetchHandler> = {
  'POST /api/workers': () => jsonResponse({ worker_id: 'worker-9' }),
};

describe('onboarding wizard', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('walks welcome → camera and remembers the chosen department', async () => {
    stubFetch({});
    const user = userEvent.setup();
    renderWizard();

    await screen.findByRole('heading', { name: 'Welcome' });
    await user.click(screen.getByRole('button', { name: 'Assembly' }));
    await toCameraStep(user);

    expect(screen.getByText('Step 2 of 5')).toBeInTheDocument();
  });

  it('uses the webcam without touching the network', async () => {
    const mock = stubFetch({});
    const user = userEvent.setup();
    renderWizard();

    await toWorkerStep(user);

    expect(mock).not.toHaveBeenCalled();
  });

  it('keeps a failed RTSP registration on the camera step with the reason', async () => {
    const mock = stubFetch({
      'POST /cloud-api/cloud/cameras': () => jsonResponse({ detail: 'bad url' }, 500),
    });
    const user = userEvent.setup();
    renderWizard();

    await toCameraStep(user);
    await user.click(screen.getByRole('button', { name: /rtsp camera/i }));
    const urlInput = screen.getByPlaceholderText(/rtsp:\/\/admin/);
    await user.clear(urlInput);
    await user.type(urlInput, 'rtsp://cam.local:554/stream');
    await user.click(screen.getByRole('button', { name: /connect camera/i }));

    await screen.findByText(/Could not add the camera/);
    // Still on step 2 — no silent advance on a failed registration.
    expect(screen.getByRole('heading', { name: 'First Camera' })).toBeInTheDocument();

    const init = mock.mock.calls[0][1] as RequestInit;
    expect(String(mock.mock.calls[0][0])).toBe('/cloud-api/cloud/cameras');
    expect(JSON.parse(String(init.body))).toEqual({
      id: 'main-station',
      name: 'Main Station',
      url: 'rtsp://cam.local:554/stream',
    });
  });

  it('requires a worker name before any request', async () => {
    const mock = stubFetch({});
    const user = userEvent.setup();
    renderWizard();

    await toWorkerStep(user);
    await user.click(screen.getByRole('button', { name: /add worker/i }));

    await screen.findByText('Enter a worker name');
    expect(mock).not.toHaveBeenCalled();
  });

  it('creates the worker on /api/workers and advances', async () => {
    const mock = stubFetch(WORKER_OK);
    const user = userEvent.setup();
    renderWizard();

    await toWorkerStep(user);
    await user.type(screen.getByPlaceholderText(/e\.g\. Rajesh Kumar/i), 'Rajesh Kumar');
    await user.click(screen.getByRole('button', { name: /add worker/i }));

    await screen.findByRole('heading', { name: 'Start Monitoring' });
    const init = mock.mock.calls[0][1] as RequestInit;
    expect(String(mock.mock.calls[0][0])).toBe('/api/workers');
    const body = JSON.parse(String(init.body));
    expect(body.name).toBe('Rajesh Kumar');
    expect(body.department).toBe('Production');
    expect(body.shift).toBe('Day');
    expect(body.employee_id).toMatch(/^EMP-[A-Z0-9]{4}$/);
  });

  it('reports a 503 test session honestly instead of faking a result', async () => {
    stubFetch({
      ...WORKER_OK,
      'POST /api/session/start': () => jsonResponse({ detail: 'no camera' }, 503),
    });
    const user = userEvent.setup();
    renderWizard();

    await toMonitorStep(user);
    await user.click(screen.getByRole('button', { name: /start test session/i }));

    await screen.findByText(/No camera available for a live session/);
    expect(screen.getByRole('heading', { name: 'Start Monitoring' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Dashboard' })).not.toBeInTheDocument();
  });

  it('shows the real session and finishes on the dashboard', async () => {
    stubFetch({
      ...WORKER_OK,
      'POST /api/session/start': () => jsonResponse({ id: 'SESS-REAL-1', status: 'active' }),
    });
    const user = userEvent.setup();
    renderWizard();

    await toMonitorStep(user);
    await user.click(screen.getByRole('button', { name: /start test session/i }));

    await screen.findByRole('heading', { name: 'Dashboard' });
    expect(screen.getByText(/Setup complete!/)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /go to dashboard/i }));
    await screen.findByText('DASHBOARD PROBE');
    expect(localStorage.getItem('ergovigilance_onboarded')).toBe('true');
  });

  it('skip setup marks the install onboarded and lands on the dashboard', async () => {
    stubFetch({});
    const user = userEvent.setup();
    renderWizard();

    await screen.findByRole('heading', { name: 'Welcome' });
    await user.click(screen.getByRole('button', { name: /skip setup/i }));

    await screen.findByText('DASHBOARD PROBE');
    expect(localStorage.getItem('ergovigilance_onboarded')).toBe('true');
  });
});
