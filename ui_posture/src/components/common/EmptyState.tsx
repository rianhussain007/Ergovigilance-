import { Inbox } from 'lucide-react';

interface EmptyStateProps {
  title?: string;
  message?: string;
}

export function EmptyState({
  title = 'No data available',
  message = 'There is nothing to display yet.',
}: EmptyStateProps) {
  return (
    <div className="bg-surface-container border border-outline-variant rounded-xl p-lg flex flex-col items-center justify-center gap-md text-center min-h-[160px]">
      <div className="w-10 h-10 rounded-full bg-surface-container-highest flex items-center justify-center">
        <Inbox className="w-5 h-5 text-on-surface-variant" />
      </div>
      <p className="text-body-sm font-medium text-on-surface-variant">{title}</p>
      <p className="text-[11px] text-on-surface-variant/60">{message}</p>
    </div>
  );
}
