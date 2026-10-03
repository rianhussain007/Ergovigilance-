/**
 * Screen-reader announcements (audit F-UX-11).
 *
 * Layout renders a single visually hidden `aria-live="polite"` region
 * (`#a11y-announcer`). Route changes, permission denials and poll failures are
 * invisible to a screen reader otherwise. Re-setting the text in a microtask
 * means the same message twice (e.g. a retry that fails again) is announced
 * again instead of being swallowed as "no change".
 */
export function announce(message: string): void {
  if (typeof document === 'undefined' || !message) return;
  const region = document.getElementById('a11y-announcer');
  if (!region) return;
  region.textContent = '';
  window.setTimeout(() => {
    region.textContent = message;
  }, 40);
}
