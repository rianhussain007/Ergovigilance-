/**
 * Shared, theme-aware styles for recharts tooltips, ticks, and chart colors.
 * Uses CSS custom properties so tooltips/tick labels/chart series follow the
 * app's light/dark theme instead of hardcoded dark-tuned hex values.
 */
import type { CSSProperties } from 'react';

export const chartTooltipStyle: CSSProperties = {
  background: 'var(--color-surface-container-high)',
  border: '1px solid var(--color-outline-variant)',
  borderRadius: '8px',
  fontSize: '12px',
  color: 'var(--color-on-surface)',
  boxShadow: '0 4px 12px rgba(0, 0, 0, 0.25)',
};

export const chartTick = { fill: 'var(--color-outline)', fontSize: 10 };

/** Theme-aware chart series palette (light variants defined in index.css). */
export const chartColors = {
  blue: 'var(--color-chart-blue)',
  orange: 'var(--color-chart-orange)',
  green: 'var(--color-chart-green)',
  red: 'var(--color-chart-red)',
} as const;

/** Map a risk level name (Low/Medium/High, LOW/MEDIUM/HIGH) to its color token. */
export function riskLevelColor(level: string): string {
  const l = (level || '').toLowerCase();
  if (l.includes('high') || l === 'critical') return chartColors.red;
  if (l.includes('med') || l.includes('mod')) return chartColors.orange;
  return chartColors.green;
}

/** Map a status tone to its semantic color token. */
export function toneColor(tone: 'success' | 'warning' | 'danger' | 'info'): string {
  const map = {
    success: 'var(--color-success)',
    warning: 'var(--color-warning)',
    danger: 'var(--color-danger)',
    info: 'var(--color-info)',
  } as const;
  return map[tone];
}
