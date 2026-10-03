interface LoadingCardProps {
  lines?: number;
  height?: string;
  /** Screen-reader label, e.g. "Loading alerts". */
  label?: string;
}

export function LoadingCard({ lines = 3, height = 'h-48', label = 'Loading content' }: LoadingCardProps) {
  // Announced as a live status region so a screen reader knows the page is
  // working rather than empty (audit F-UX-11).
  return (
    <div
      role="status"
      aria-busy="true"
      aria-label={label}
      className={`bg-surface-container border border-outline-variant/60 rounded-xl p-lg ${height} flex flex-col justify-center gap-md overflow-hidden relative`}
    >
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="flex flex-col gap-sm">
          <div className="h-3 bg-surface-container-highest/70 rounded-md w-1/3 shimmer" />
          <div className="h-5 bg-surface-container-highest/70 rounded-md w-2/3 shimmer" style={{ animationDelay: `${i * 0.1}s` }} />
        </div>
      ))}
    </div>
  );
}
