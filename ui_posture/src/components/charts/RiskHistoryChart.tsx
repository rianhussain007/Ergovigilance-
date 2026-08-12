import { AreaChart, XAxis, YAxis, Tooltip, ResponsiveContainer, Area } from 'recharts';
import { chartTooltipStyle, chartTick, chartColors } from './chartTheme';
import type { RiskDataPoint } from '@/src/types/api';

interface RiskHistoryChartProps {
  data: RiskDataPoint[];
}

export function RiskHistoryChart({ data }: RiskHistoryChartProps) {
  return (
    <div className="bg-surface-container border border-outline-variant rounded-xl p-lg">
      <div className="flex items-center justify-between mb-lg">
        <h3 className="font-label-caps text-label-caps text-on-surface uppercase tracking-widest">Risk History (30s intervals)</h3>
        <div className="flex items-center gap-xs">
          <span className="w-2 h-2 rounded-full bg-orange-400"></span>
          <span className="font-label-mono text-[10px] text-on-surface-variant">Risk Score</span>
        </div>
      </div>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 8, right: 8, left: -15, bottom: 4 }}>
            <defs>
              <linearGradient id="riskGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" style={{ stopColor: chartColors.orange }} stopOpacity={0.3} />
                <stop offset="100%" style={{ stopColor: chartColors.orange }} stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis dataKey="time" tick={chartTick} axisLine={false} tickLine={false} dy={4} />
            <YAxis tick={chartTick} axisLine={false} tickLine={false} domain={[0, 60]} dx={-4} />
            <Tooltip
              contentStyle={chartTooltipStyle}
              formatter={(value: number) => [`${value}`, 'Risk Score']}
              labelStyle={{ color: 'var(--color-on-surface-variant)', fontWeight: 500 }}
              itemStyle={{ color: chartColors.orange }}
            />
            <Area type="monotone" dataKey="value" stroke={chartColors.orange} strokeWidth={2} fill="url(#riskGradient)" animationDuration={400} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
