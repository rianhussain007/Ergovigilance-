import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { CameraPanel } from '../components/charts/CameraPanel';
import { ToastProvider } from '../hooks/useToast';

/**
 * Regression: a live session whose MJPEG stream fails must show an honest
 * "Camera feed unavailable" state — never a broken <img> whose alt text
 * ("Live camera feed") gets painted inside the frame area.
 */
describe('CameraPanel feed failure', () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('replaces the broken stream with a feed-unavailable state once retries are exhausted', async () => {
    vi.useFakeTimers();
    // Stream-token mint call.
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => ({ token: 't' }) })));

    render(
      <ToastProvider>
        <CameraPanel status="active" workerName="Asha Patel" task="Unknown" fps={0} />
      </ToastProvider>,
    );

    expect(screen.queryByAltText('Live camera feed')).not.toBeNull();

    // Drive consecutive stream errors until the retry budget (5) is spent.
    // Each error is fired, then effects are allowed to settle, then the retry
    // timer is advanced — otherwise the freshly scheduled timer is created
    // after the advance and the next retry never runs.
    for (let i = 0; i < 12; i++) {
      const img = document.querySelector('img');
      if (!img) break;
      await act(async () => {
        fireEvent.error(img);
      });
      await act(async () => {
        await vi.advanceTimersByTimeAsync(20000);
      });
    }
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60000);
    });

    expect(screen.getByText('Camera feed unavailable')).toBeInTheDocument();
    // The broken image (and its leaked alt text) must be gone.
    expect(document.querySelector('img')).toBeNull();
    expect(screen.queryByAltText('Live camera feed')).toBeNull();
  });

  it('shows the real FPS when provided and an em-dash when there is none', () => {
    const { rerender } = render(
      <ToastProvider>
        <CameraPanel status="active" workerName="W" fps={27.4} />
      </ToastProvider>,
    );
    expect(screen.getByText('27.4')).toBeInTheDocument();

    rerender(
      <ToastProvider>
        <CameraPanel status="active" workerName="W" fps={0} />
      </ToastProvider>,
    );
    expect(screen.getByText('—')).toBeInTheDocument();
  });
});
