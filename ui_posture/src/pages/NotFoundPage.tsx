import { Link, useLocation } from 'react-router';
import { Compass, Search } from 'lucide-react';

/**
 * In-shell 404. Without a `path="*"` route React Router renders nothing for an
 * unknown URL, so a mistyped or stale link showed a blank screen with no way
 * back. This keeps the app chrome (nav, search, help) and explains what
 * happened.
 */
export default function NotFoundPage() {
  const location = useLocation();

  return (
    <div className="p-lg flex items-center justify-center min-h-[60vh]">
      <div className="w-full max-w-[32rem] rounded-2xl border border-outline-variant bg-surface-container p-xl text-center space-y-md">
        <div className="mx-auto w-12 h-12 rounded-full bg-primary/10 text-primary grid place-items-center">
          <Compass className="w-6 h-6" />
        </div>
        <h1 className="text-headline-md font-bold text-on-surface">Page not found</h1>
        <p className="text-body-sm text-on-surface-variant">
          <span className="font-label-mono text-on-surface break-all">{location.pathname}</span> is not a page in
          ErgoVigilance. It may have moved, or the link may be out of date.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-sm pt-xs">
          <Link
            to="/dashboard"
            className="h-10 px-md rounded-lg bg-primary text-on-primary text-body-sm font-semibold inline-flex items-center"
          >
            Go to Dashboard
          </Link>
          <button
            type="button"
            onClick={() => window.dispatchEvent(new CustomEvent('opensearch'))}
            className="h-10 px-md rounded-lg border border-outline-variant text-on-surface-variant text-body-sm font-semibold inline-flex items-center gap-sm hover:text-on-surface hover:border-primary/40 transition-colors"
          >
            <Search className="w-4 h-4" />
            Search (Ctrl+K)
          </button>
        </div>
      </div>
    </div>
  );
}
