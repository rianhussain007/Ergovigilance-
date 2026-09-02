import { useEffect } from 'react';
import { useLocation } from 'react-router';

/**
 * Moves keyboard focus to #main-content on route change so screen readers
 * announce the new page. WCAG 2.1 SC 2.4.1 and SC 3.2.3.
 */
export function useFocusOnNavigate() {
  const { pathname } = useLocation();

  useEffect(() => {
    const el = document.getElementById('main-content');
    if (el) {
      el.focus({ preventScroll: false });
    }
  }, [pathname]);
}
