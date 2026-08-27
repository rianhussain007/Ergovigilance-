import { useState, useEffect } from 'react';
import { BarChart3, TrendingUp, TrendingDown, AlertTriangle, CheckCircle } from 'lucide-react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, PieChart, Pie, Cell } from 'recharts';
import { LoadingCard, ErrorCard, SectionHeader, EmptyState, PredictiveInsightsCard, BenchmarkCard } from '@/src/components/common';
import { getAnalytics } from '@/src/services/dashboardService';
import { NeckTrunkTrendChart } from '@/src/components/charts/NeckTrunkTrendChart';
import { chartTooltipStyle, chartTick, chartColors, riskLevelColor } from '@/src/components/charts/chartTheme';
import type { AnalyticsResponse } from '@/src/types/api';

export default function AnalyticsPage() {
  const [analytics, setAnalytics] = useState<AnalyticsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAnalytics = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getAnalytics();
      setAnalytics(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load analytics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchAnalytics(); }, []);

  if (error) return <div className="flex items-center justify-center h-full p-lg"><ErrorCard message={error} onRetry={fetchAnalytics} /></div>;

  const summary = analytics?.summary;
  const weeklyRiskTrend = analytics?.weekly_risk_trend ?? [];
  const distData = analytics?.risk_distribution ?? [];
  const issueFreq = analytics?.issue_frequency ?? [];
  const neckTrunkTrend = analytics?.neck_trunk_trend ?? [];

  // Sessions started this week vs the previous week (from real weekly data) —
  // gives the Sessions card a genuine comparison, or nothing when unavailable.
  const sessionsDelta =
    weeklyRiskTrend.length >= 2
      ? (weeklyRiskTrend[weeklyRiskTrend.length - 1].sessions ?? 0) - (weeklyRiskTrend[weeklyRiskTrend.length - 2].sessions ?? 0)
      : null;

  return (
    <div className="p-lg space-y-lg pb-32">
      <div>
        <h1 className="text-display-lg font-bold text-slate-900 dark:text-on-surface">Analytics</h1>
        <p className="text-body-sm text-slate-500 dark:text-on-surface-variant mt-xs">Comprehensive ergonomic data overview</p>
      </div>

      {/* Predictive forecast for the most recent session (advisory) */}
      <PredictiveInsightsCard mode="session" />

      {/* De-identified posture percentile baseline */}
      <BenchmarkCard />

      <div className="grid grid-cols-1 md:grid-cols-4 gap-md">
        <div className="bg-white dark:bg-surface-container border border-slate-200 dark:border-outline-variant rounded-2xl p-md shadow-sm dark:shadow-none">
          <div className="flex items-center justify-between mb-sm"><span className="font-label-caps text-label-caps text-slate-400 dark:text-on-surface-variant uppercase tracking-widest">Avg Risk Score</span><BarChart3 className="w-5 h-5 text-blue-600 dark:text-primary" /></div>
          <span className="text-display-lg font-bold text-slate-900 dark:text-slate-900 dark:text-on-surface">{summary ? `${summary.avg_risk_score.toFixed(1)}` : '—'}</span>
        </div>
        <div className="bg-white dark:bg-surface-container border border-slate-200 dark:border-outline-variant rounded-2xl p-md shadow-sm dark:shadow-none">
          <div className="flex items-center justify-between mb-sm">
            <span className="font-label-caps text-label-caps text-slate-400 dark:text-on-surface-variant uppercase tracking-widest">Sessions</span>
            {sessionsDelta !== null && sessionsDelta !== 0 ? (
              <span className={`flex items-center gap-1 text-[11px] font-bold ${sessionsDelta > 0 ? 'text-green-400' : 'text-red-400'}`}>
                {sessionsDelta > 0 ? <TrendingUp className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}
                {sessionsDelta > 0 ? '+' : ''}{sessionsDelta} vs last week
              </span>
            ) : null}
          </div>
          <span className="text-display-lg font-bold text-slate-900 dark:text-slate-900 dark:text-on-surface">{summary?.total_sessions || '—'}</span>
        </div>
        <div className="bg-surface-container border border-orange-500/30 rounded-2xl p-md shadow-sm dark:shadow-none">
          <div className="flex items-center justify-between mb-sm"><span className="font-label-caps text-label-caps text-slate-400 dark:text-on-surface-variant uppercase tracking-widest">Incidents</span><AlertTriangle className="w-5 h-5 text-orange-400" /></div>
          <span className="text-display-lg font-bold text-amber-500 dark:text-orange-400">{summary ? summary.deteriorating : '—'}</span>
        </div>
        <div className="bg-surface-container border border-green-500/30 rounded-2xl p-md shadow-sm dark:shadow-none">
          <div className="flex items-center justify-between mb-sm"><span className="font-label-caps text-label-caps text-slate-400 dark:text-on-surface-variant uppercase tracking-widest">Improving</span><CheckCircle className="w-5 h-5 text-green-400" /></div>
          <span className="text-display-lg font-bold text-emerald-500 dark:text-green-400">{summary ? summary.improving : '—'}</span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-lg">
        <div className="bg-white dark:bg-surface-container border border-slate-200 dark:border-outline-variant rounded-2xl p-lg shadow-sm dark:shadow-none">
          <SectionHeader title="Weekly Risk Trend" />
          {loading ? <LoadingCard height="h-64" /> : weeklyRiskTrend.length === 0 ? <EmptyState message="No trend data available" /> : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={weeklyRiskTrend}>
                  <XAxis dataKey="week" tick={chartTick} axisLine={false} tickLine={false} />
                  <YAxis tick={chartTick} axisLine={false} tickLine={false} />
                  {/* Explicit cursor keeps hover from flashing the default gray rectangle */}
                  <Tooltip contentStyle={chartTooltipStyle} cursor={{ fill: 'rgba(77, 142, 255, 0.12)' }} />
                  <Bar dataKey="averageRisk" name="Average Risk" fill={chartColors.blue} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        <div className="bg-white dark:bg-surface-container border border-slate-200 dark:border-outline-variant rounded-2xl p-lg shadow-sm dark:shadow-none">
          <SectionHeader title="Risk Distribution" />
          {loading ? <LoadingCard height="h-64" /> : distData.length === 0 ? <EmptyState message="No distribution data" /> : (
            <div className="h-64 flex items-center justify-center">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={distData} cx="50%" cy="50%" outerRadius={80} dataKey="value" label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                    {distData.map((entry, i) => <Cell key={i} fill={riskLevelColor(entry.name)} />)}
                  </Pie>
                  <Tooltip contentStyle={chartTooltipStyle} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        <div className="bg-white dark:bg-surface-container border border-slate-200 dark:border-outline-variant rounded-2xl p-lg shadow-sm dark:shadow-none">
          <SectionHeader title="Issue Frequency" />
          {loading ? <LoadingCard height="h-64" /> : issueFreq.length === 0 ? <EmptyState message="No issue data available" /> : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={issueFreq} layout="vertical">
                  <XAxis type="number" tick={chartTick} axisLine={false} tickLine={false} />
                  <YAxis dataKey="name" type="category" tick={chartTick} axisLine={false} tickLine={false} width={100} />
                  <Tooltip contentStyle={chartTooltipStyle} />
                  <Bar dataKey="count" name="Occurrences" fill={chartColors.orange} radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        <div className="bg-white dark:bg-surface-container border border-slate-200 dark:border-outline-variant rounded-2xl p-lg shadow-sm dark:shadow-none">
          <SectionHeader title="Neck & Trunk Trend" />
          {loading ? <LoadingCard height="h-64" /> : neckTrunkTrend.length === 0 ? <EmptyState message="No trend data available" /> : (
            <div className="h-64">
              <NeckTrunkTrendChart data={neckTrunkTrend} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
