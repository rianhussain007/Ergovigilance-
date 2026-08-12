import { useId } from 'react';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip } from 'recharts';
import { chartTooltipStyle, chartTick, chartColors } from './chartTheme';

export interface NeckTrunkPoint {
  week: string;
  neck: number;
  trunk: number;
}

interface NeckTrunkTrendChartProps {
  data: NeckTrunkPoint[];
  height?: number | string;
}

/**
 * Shared Neck & Trunk weekly trend chart with the Neck/Trunk color legend
 * inline, so every page that renders this chart shows the same legend and
 * theme-aware tooltip (single source of truth for both the Dashboard and
 * Analytics pages).
 */
export function NeckTrunkTrendChart({ data, height = '100%' }: NeckTrunkTrendChartProps) {
  const uid = useId().replace(/[^a-zA-Z0-9]/g, '');
  return (
    <>
      <div className="mb-sm flex items-center gap-lg text-[11px] text-on-surface-variant">
        <span className="flex items-center gap-1.5"><span className="w-3 h-0.5 rounded-full" style={{ backgroundColor: chartColors.blue }} /> Neck</span>
        <span className="flex items-center gap-1.5"><span className="w-3 h-0.5 rounded-full" style={{ backgroundColor: chartColors.orange }} /> Trunk</span>
      </div>
      <div style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data}>
            <defs>
              <linearGradient id={`neck-${uid}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" style={{ stopColor: chartColors.blue }} stopOpacity={0.3} />
                <stop offset="100%" style={{ stopColor: chartColors.blue }} stopOpacity={0} />
              </linearGradient>
              <linearGradient id={`trunk-${uid}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" style={{ stopColor: chartColors.orange }} stopOpacity={0.3} />
                <stop offset="100%" style={{ stopColor: chartColors.orange }} stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis dataKey="week" tick={chartTick} axisLine={false} tickLine={false} />
            <YAxis tick={chartTick} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={chartTooltipStyle} />
            <Area type="monotone" dataKey="neck" name="Neck" stroke={chartColors.blue} strokeWidth={2} fill={`url(#neck-${uid})`} />
            <Area type="monotone" dataKey="trunk" name="Trunk" stroke={chartColors.orange} strokeWidth={2} fill={`url(#trunk-${uid})`} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </>
  );
}
