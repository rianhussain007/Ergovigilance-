import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ConsentPage from '../pages/ConsentPage';
import { AuthProvider } from '../auth/AuthContext';
import { ToastProvider } from '../hooks/useToast';
import { jsonResponse } from './fixtures';

/**
 * Consent interactions (sell-readiness QA: consent actions).
 *
 * The QA pass found consent clicks acting on the wrong record, so these
 * tests pin the frontend half of that contract: every grant / deny /
 * withdraw must address the worker whose row was clicked, and a cancelled
 * withdrawal must not call the API at all.
 */

interface WorkerRow {
  worker_id: string;
  name: string;
  department: string;
  consent_status: 'granted' | 'denied' | 'pending' | 'withdrawn';
  consent_date: string | null;
  consent_expiry: string | null;
  consent_version: string;
  purpose: string;
  data_categories: string[];
  retention_days: number;
  withdrawal_date: string | null;
  consent_proof: string | null;
}

function worker(overrides: Partial<WorkerRow> & Pick<WorkerRow, 'worker_id' | 'name' | 'consent_status'>): WorkerRow {
  return {
    department: 'Assembly',
    consent_date: null,
    consent_expiry: null,
    consent_version: 'v2.1',
    purpose: 'Ergonomic posture risk assessment',
    data_categories: ['Body pose keypoints (2D)'],
    retention_days: 365,
    withdrawal_date: null,
    consent_proof: null,
    ...overrides,
  };
}

const WORKERS: WorkerRow[] = [
  worker({ worker_id: 'worker-001', name: 'Asha Patel', consent_status: 'pending' }),
  worker({ worker_id: 'worker-002', name: 'Rohan Mehta', consent_status: 'granted', consent_date: '2026-08-01' }),
  worker({ worker_id: 'worker-003', name: 'Meera Iyer', consent_status: 'denied', department: 'Packaging' }),
];

const POLICY = {
  version: '2.1',
  title: 'Worker Monitoring Consent Policy',
  description: 'Posture monitoring consent for pilot sites.',
  purposes: ['Ergonomic posture risk assessment'],
  data_categories: ['Body pose keypoints (2D)'],
  retention_days: 365,
  rights: ['Right to withdraw consent at any time'],
  last_updated: '2026-08-01',
};

function stubFetch() {
  const mock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = (init?.method ?? 'GET').toUpperCase();
    if (method === 'GET' && url === '/api/consent/worker-consents') {
      return jsonResponse({ workers: WORKERS, policy: POLICY });
    }
    if (method === 'POST' && /^\/api\/consent\/worker-consents\/[^/]+\/(grant|deny|withdraw)$/.test(url)) {
      return jsonResponse({ ok: true });
    }
    return jsonResponse({ detail: `unmocked ${method} ${url}` }, 404);
  });
  vi.stubGlobal('fetch', mock);
  return mock;
}

function renderConsentPage() {
  return render(
    <AuthProvider>
      <ToastProvider>
        <ConsentPage />
      </ToastProvider>
    </AuthProvider>,
  );
}

function postedUrls(mock: ReturnType<typeof stubFetch>, suffix: string) {
  return mock.mock.calls.map(([url]) => String(url)).filter((url) => url.endsWith(suffix));
}

describe('consent page interactions', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('renders the consent records with aggregate stats', async () => {
    stubFetch();
    renderConsentPage();

    await screen.findByText('Asha Patel');
    expect(screen.getByText('Total Workers').previousElementSibling).toHaveTextContent('3');
    expect(screen.getByText('Consented').previousElementSibling).toHaveTextContent('1');
    expect(screen.getByText('Meera Iyer')).toBeInTheDocument();
  });

  it('grants the worker whose row was clicked, never the first row', async () => {
    const mock = stubFetch();
    const user = userEvent.setup();
    renderConsentPage();

    await screen.findByText('Meera Iyer');
    await user.click(screen.getByRole('button', { name: 'Grant consent for Meera Iyer' }));

    await waitFor(() => expect(postedUrls(mock, '/grant')).toContain('/api/consent/worker-consents/worker-003/grant'));
    expect(postedUrls(mock, '/grant')).not.toContain('/api/consent/worker-consents/worker-001/grant');

    const call = mock.mock.calls.find(([url]) => String(url) === '/api/consent/worker-consents/worker-003/grant')!;
    const init = call[1] as RequestInit;
    expect(init.method).toBe('POST');
    const body = JSON.parse(String(init.body));
    expect(body.purposes).toContain('Ergonomic posture risk assessment');
    expect(body.data_categories).toContain('Body pose keypoints (2D)');
  });

  it('denies the worker whose row was clicked', async () => {
    const mock = stubFetch();
    const user = userEvent.setup();
    renderConsentPage();

    await screen.findByText('Asha Patel');
    await user.click(screen.getByRole('button', { name: 'Deny consent for Asha Patel' }));

    await waitFor(() => expect(postedUrls(mock, '/deny')).toContain('/api/consent/worker-consents/worker-001/deny'));
  });

  it('withdraws only after confirmation, and for the chosen worker', async () => {
    const mock = stubFetch();
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);
    const user = userEvent.setup();
    renderConsentPage();

    await screen.findByText('Rohan Mehta');
    await user.click(screen.getByRole('button', { name: 'Withdraw consent for Rohan Mehta' }));

    await waitFor(() => expect(confirmSpy).toHaveBeenCalled());
    // Cancelled: nothing was sent.
    expect(postedUrls(mock, '/withdraw')).toEqual([]);

    confirmSpy.mockReturnValue(true);
    await user.click(screen.getByRole('button', { name: 'Withdraw consent for Rohan Mehta' }));
    await waitFor(() => expect(postedUrls(mock, '/withdraw')).toContain('/api/consent/worker-consents/worker-002/withdraw'));
  });

  it('filters the list by status', async () => {
    stubFetch();
    const user = userEvent.setup();
    renderConsentPage();

    await screen.findByText('Asha Patel');
    await user.click(screen.getByRole('button', { name: 'Granted' }));

    expect(screen.queryByText('Asha Patel')).not.toBeInTheDocument();
    expect(screen.getByText('Rohan Mehta')).toBeInTheDocument();
    expect(screen.getByText('1 worker')).toBeInTheDocument();
  });

  it('exports every record to a CSV blob', async () => {
    let blob: Blob | null = null;
    Object.defineProperty(URL, 'createObjectURL', {
      writable: true,
      value: vi.fn((b: Blob) => { blob = b; return 'blob:mock'; }),
    });
    Object.defineProperty(URL, 'revokeObjectURL', { writable: true, value: vi.fn() });
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});

    stubFetch();
    const user = userEvent.setup();
    renderConsentPage();

    await screen.findByText('Asha Patel');
    await user.click(screen.getByRole('button', { name: /export csv/i }));

    await waitFor(() => expect(blob).not.toBeNull());
    const csv = await blob!.text();
    expect(csv.split('\n')[0]).toContain('Worker ID,Name,Department');
    expect(csv).toContain('worker-001');
    expect(csv).toContain('worker-003');
  });

  it('shows the load failure instead of an empty table', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse({ detail: 'boom' }, 500)));
    renderConsentPage();

    await screen.findByText('Failed to load consent data');
  });
});
