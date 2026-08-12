interface LoadingCardProps {
  lines?: number;
  height?: string;
}

export function LoadingCard({ lines = 3, height = 'h-48' }: LoadingCardProps) {
  return (
    <div className={`bg-surface-container border border-outline-variant/60 rounded-xl p-lg ${height} flex flex-col justify-center gap-md overflow-hidden relative`}>
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="flex flex-col gap-sm">
          <div className="h-3 bg-surface-container-highest/70 rounded-md w-1/3 shimmer" />
          <div className="h-5 bg-surface-container-highest/70 rounded-md w-2/3 shimmer" style={{ animationDelay: `${i * 0.1}s` }} />
        </div>
      ))}
    </div>
  );
}
