import React from 'react';

interface SectionHeaderProps {
  title: string;
  action?: React.ReactNode;
}

export function SectionHeader({ title, action }: SectionHeaderProps) {
  return (
    <div className="flex items-center justify-between mb-md">
      <h2 className="font-label-caps text-label-caps text-on-surface uppercase tracking-widest">{title}</h2>
      {action && <div>{action}</div>}
    </div>
  );
}
