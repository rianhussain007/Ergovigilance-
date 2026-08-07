import type { StatusType } from '@/src/types/api';

const cfg: Record<StatusType, { color: string; bg: string; label: string }> = {
  active: { color: 'text-green-400', bg: 'bg-green-500/10', label: 'Active' },
  completed: { color: 'text-blue-400', bg: 'bg-blue-500/10', label: 'Completed' },
  interrupted: { color: 'text-red-400', bg: 'bg-red-500/10', label: 'Interrupted' },
};

export function StatusBadge({ status }: { status: StatusType }) {
  const c = cfg[status] || cfg.completed;
  return (
    <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded ${c.bg} ${c.color}`}>
      {c.label}
    </span>
  );
}
