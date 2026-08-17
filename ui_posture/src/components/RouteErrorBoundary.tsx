import { Component, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

/**
 * Catches render/import errors inside lazy-loaded route chunks so a single
 * failing page (or a chunk that fails to load on a slow factory network)
 * never unmounts the whole app. Shows a recoverable message instead, with a
 * reload action. Also makes failures visible in tests instead of silently
 * blanking the tree.
 */
export class RouteErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: unknown) {
    // Keep the failure in the console for diagnosability.
    console.error('[RouteErrorBoundary] caught:', error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex min-h-screen items-center justify-center bg-[#0b0f14] p-lg">
          <div className="max-w-md rounded-xl border border-red-500/30 bg-red-500/10 p-lg text-center">
            <p className="text-body-md font-medium text-red-400">Something went wrong loading this page</p>
            <p className="mt-xs text-body-sm text-on-surface-variant">
              {this.state.error.message || 'An unexpected error occurred.'}
            </p>
            <button
              onClick={() => this.setState({ error: null })}
              className="mt-md inline-flex items-center gap-sm rounded-lg bg-primary px-md py-sm text-body-sm font-medium text-on-primary hover:bg-primary/90"
            >
              Try again
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
