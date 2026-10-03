import { useEffect } from 'react';
import { useLocation } from 'react-router';
import { announce } from '@/src/utils/announce';

/**
 * Moves keyboard focus to #main-content on route change so screen readers
 * announce the new page, names the document, and pushes the destination
 * through the shared live region (WCAG 2.1 SC 2.4.1, 2.4.2, 3.2.3).
 */
export function useFocusOnNavigate() {
  const { pathname } = useLocation();

  useEffect(() => {
    const el = document.getElementById('main-content');
    if (el) {
      el.focus({ preventScroll: false });
    }

    // The route content mounts with the animation, so read the heading on the
    // next frame rather than racing the render. (jsdom without
    // pretendToBeVisual has no rAF — fall back to a timer.)
    const schedule =
      typeof window.requestAnimationFrame === 'function'
        ? window.requestAnimationFrame.bind(window)
        : (callback: FrameRequestCallback) => window.setTimeout(() => callback(0), 16);
    const unschedule =
      typeof window.cancelAnimationFrame === 'function'
        ? window.cancelAnimationFrame.bind(window)
        : window.clearTimeout;

    const frame = schedule(() => {
      const heading = el?.querySelector('h1, h2')?.textContent?.replace(/\s+/g, ' ').trim();
      if (heading) {
        document.title = `${heading} · ErgoVigilance`;
        announce(`Navigated to ${heading}`);
      } else {
        announce('Page loaded');
      }
    });
    return () => unschedule(frame);
  }, [pathname]);
}
