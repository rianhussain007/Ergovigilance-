import React from 'react';

interface SectionHeaderProps {
  title: string;
  action?: React.ReactNode;
  /**
   * Heading level. Use `h1` when this header *is* the page title (a screen
   * with no other heading) so every page exposes exactly one top-level
   * heading (WCAG 1.3.1 / 2.4.6); sections stay `h2`.
   */
  as?: 'h1' | 'h2';
}

export function SectionHeader({ title, action, as: Tag = 'h2' }: SectionHeaderProps) {
  return (
    <div className="flex items-center justify-between mb-md">
      <Tag className="font-label-caps text-label-caps text-on-surface uppercase tracking-widest">{title}</Tag>
      {action && <div>{action}</div>}
    </div>
  );
}
