import React from 'react';
import { Users, Activity, AlertTriangle, Bell, ClipboardCheck, Shield } from 'lucide-react';
import { useDemo } from '@/src/demo/DemoProvider';
import { useDashboardWithDemo } from '@/src/hooks/useDashboardWithDemo';

interface KpiCardProps {
  icon: React.ElementType;
  label: string;
  value: string | number;
  accent?: boolean;
}

function KpiCard({ icon: Icon, label, value, accent }: KpiCardProps) {
  return (
    <div className={`flex items-center gap-md px-lg py-md rounded-lg border ${accent ? 'border-primary/30 bg-primary/5' : 'border-outline-variant bg-surface-container'} min-w-0`}>
      <div className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${accent ? 'bg-primary/15' : 'bg-surface-container-highest'}`}>
        <Icon className={`w-4 h-4 ${accent ? 'text-primary' : 'text-on-surface-variant'}`} />
      </div>
      <div className="min-w-0">
        <p className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant truncate">{label}</p>
        <p className="text-title-sm font-bold text-on-surface truncate">{value}</p>
      </div>
    </div>
  );
}

export default function KpiRow() {
  const { state } = useDemo();
  const { dashboard, sessions } = useDashboardWithDemo();

  if (!state.active) return null;

  const ws = dashboard?.session?.workerName || '—';
  const compliance = dashboard ? Math.round(100 - dashboard.liveStatus.riskScore * 0.5) : '—';
  const highRiskCount = dashboard?.issues.filter((i) => i.severity === 'high').length || 0;
  const alertCount = dashboard?.issues.length || 0;
  const sessionCount = sessions.length;
  const healthScore = dashboard ? Math.round(100 - dashboard.liveStatus.riskScore * 1.2) : '—';

  return (
    <div className="flex items-center gap-md overflow-x-auto pb-xs scrollbar-thin">
      <KpiCard icon={Users} label="Worker" value={ws} />
      <KpiCard icon={Activity} label="Compliance" value={`${compliance}%`} accent />
      <KpiCard icon={AlertTriangle} label="High Risk" value={highRiskCount} />
      <KpiCard icon={Bell} label="Alerts" value={alertCount} />
      <KpiCard icon={ClipboardCheck} label="Sessions" value={sessionCount} />
      <KpiCard icon={Shield} label="Health Score" value={healthScore} />
    </div>
  );
}
