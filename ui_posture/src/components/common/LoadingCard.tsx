interface LoadingCardProps {
  lines?: number;
  height?: string;
}

export function LoadingCard({ lines = 3, height = 'h-48' }: LoadingCardProps) {
  return (
    <div className={`bg-surface-container border border-outline-variant rounded-xl p-lg ${height} flex flex-col justify-center gap-md animate-pulse`}>
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="flex flex-col gap-sm">
          <div className="h-3 bg-surface-container-highest rounded w-1/3" />
          <div className="h-5 bg-surface-container-highest rounded w-2/3" />
        </div>
      ))}
    </div>
  );
}
