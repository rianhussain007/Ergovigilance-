import { useState, useEffect } from 'react';
import { BarChart3, TrendingUp, AlertTriangle, CheckCircle } from 'lucide-react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, PieChart, Pie, Cell, AreaChart, Area } from 'recharts';
import { LoadingCard, ErrorCard, SectionHeader, EmptyState } from '@/src/components/common';
import { getAnalytics } from '@/src/services/dashboardService';
import type { AnalyticsResponse } from '@/src/types/api';

const tooltipStyle = { background: '#1d2027', border: '1px solid #424754', borderRadius: '8px', fontSize: '12px', color: '#e1e2ec' };

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

  return (
    <div className="p-lg space-y-lg pb-32">
      <div>
        <h1 className="text-display-lg font-bold text-on-surface">Analytics</h1>
        <p className="text-body-sm text-on-surface-variant mt-xs">Comprehensive ergonomic data overview</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-md">
        <div className="bg-surface-container border border-outline-variant rounded-xl p-md">
          <div className="flex items-center justify-between mb-sm"><span className="font-label-caps text-label-caps text-on-surface-variant uppercase tracking-widest">Avg Risk Score</span><BarChart3 className="w-5 h-5 text-primary" /></div>
          <span className="text-display-lg font-bold text-on-surface">{summary ? `${summary.avg_risk_score.toFixed(1)}` : '—'}</span>
        </div>
        <div className="bg-surface-container border border-outline-variant rounded-xl p-md">
          <div className="flex items-center justify-between mb-sm"><span className="font-label-caps text-label-caps text-on-surface-variant uppercase tracking-widest">Sessions</span><TrendingUp className="w-5 h-5 text-primary" /></div>
          <span className="text-display-lg font-bold text-on-surface">{summary?.total_sessions || '—'}</span>
        </div>
        <div className="bg-surface-container border border-orange-500/30 rounded-xl p-md">
          <div className="flex items-center justify-between mb-sm"><span className="font-label-caps text-label-caps text-on-surface-variant uppercase tracking-widest">Incidents</span><AlertTriangle className="w-5 h-5 text-orange-400" /></div>
          <span className="text-display-lg font-bold text-orange-400">{summary ? summary.deteriorating : '—'}</span>
        </div>
        <div className="bg-surface-container border border-green-500/30 rounded-xl p-md">
          <div className="flex items-center justify-between mb-sm"><span className="font-label-caps text-label-caps text-on-surface-variant uppercase tracking-widest">Improving</span><CheckCircle className="w-5 h-5 text-green-400" /></div>
          <span className="text-display-lg font-bold text-green-400">{summary ? summary.improving : '—'}</span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-lg">
        <div className="bg-surface-container border border-outline-variant rounded-xl p-lg">
          <SectionHeader title="Weekly Risk Trend" />
          {loading ? <LoadingCard height="h-64" /> : weeklyRiskTrend.length === 0 ? <EmptyState message="No trend data available" /> : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={weeklyRiskTrend}>
                  <XAxis dataKey="week" tick={{ fill: '#8c909f', fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: '#8c909f', fontSize: 10 }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Bar dataKey="averageRisk" fill="#4d8eff" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        <div className="bg-surface-container border border-outline-variant rounded-xl p-lg">
          <SectionHeader title="Risk Distribution" />
          {loading ? <LoadingCard height="h-64" /> : distData.length === 0 ? <EmptyState message="No distribution data" /> : (
            <div className="h-64 flex items-center justify-center">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={distData} cx="50%" cy="50%" outerRadius={80} dataKey="value" label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                    {distData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                  </Pie>
                  <Tooltip contentStyle={tooltipStyle} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        <div className="bg-surface-container border border-outline-variant rounded-xl p-lg">
          <SectionHeader title="Issue Frequency" />
          {loading ? <LoadingCard height="h-64" /> : issueFreq.length === 0 ? <EmptyState message="No issue data available" /> : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={issueFreq} layout="vertical">
                  <XAxis type="number" tick={{ fill: '#8c909f', fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis dataKey="name" type="category" tick={{ fill: '#8c909f', fontSize: 10 }} axisLine={false} tickLine={false} width={100} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Bar dataKey="count" fill="#f97316" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        <div className="bg-surface-container border border-outline-variant rounded-xl p-lg">
          <SectionHeader title="Neck & Trunk Trend" />
          {loading ? <LoadingCard height="h-64" /> : neckTrunkTrend.length === 0 ? <EmptyState message="No trend data available" /> : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={neckTrunkTrend}>
                  <defs>
                    <linearGradient id="neckGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#4d8eff" stopOpacity={0.3} /><stop offset="100%" stopColor="#4d8eff" stopOpacity={0} /></linearGradient>
                    <linearGradient id="trunkGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#f97316" stopOpacity={0.3} /><stop offset="100%" stopColor="#f97316" stopOpacity={0} /></linearGradient>
                  </defs>
                  <XAxis dataKey="week" tick={{ fill: '#8c909f', fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: '#8c909f', fontSize: 10 }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Area type="monotone" dataKey="neck" name="Neck" stroke="#4d8eff" strokeWidth={2} fill="url(#neckGrad)" />
                  <Area type="monotone" dataKey="trunk" name="Trunk" stroke="#f97316" strokeWidth={2} fill="url(#trunkGrad)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
