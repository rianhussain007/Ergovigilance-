/**
 * Skip-to-content link — first focusable element on every page.
 * Visually hidden until focused with Tab, then slides into view.
 * Critical for WCAG 2.1 AA compliance (SC 2.4.1).
 */
export default function SkipLink() {
  return (
    <a
      href="#main-content"
      className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[9999] focus:px-md focus:py-sm focus:rounded-lg focus:bg-primary focus:text-on-primary focus:text-body-sm focus:font-bold focus:shadow-lg focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2"
    >
      Skip to main content
    </a>
  );
}
