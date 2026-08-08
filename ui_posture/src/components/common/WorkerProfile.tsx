import { useState, useEffect } from 'react';
import { User, Hash, Building2, Clock, Shield } from 'lucide-react';
import type { SessionInfo, LiveStatus, WorkerRecord } from '@/src/types/api';
import { apiFetch } from '@/src/services/apiClient';

interface WorkerProfileProps {
  session: SessionInfo | null;
  liveStatus: LiveStatus | null;
}

export function WorkerProfile({ session, liveStatus }: WorkerProfileProps) {
  const [workers, setWorkers] = useState<WorkerRecord[]>([]);

  useEffect(() => {
    let cancelled = false;
    apiFetch('/api/workers')
      .then((res) => (res.ok ? res.json() : []))
      .then((data: WorkerRecord[]) => {
        if (!cancelled) setWorkers(data);
      })
      .catch(() => { if (!cancelled) setWorkers([]); });
    return () => { cancelled = true; };
  }, []);

  if (!session) return null;

  const worker = workers.find(
    (w) => w.worker_id === session.workerId || w.name === session.workerName
  );
  const hasWorkerData = !!worker;

  const compliance = liveStatus ? Math.max(70, 100 - liveStatus.riskScore * 0.6) : 92;

  return (
    <div className="bg-surface-container border border-outline-variant rounded-xl p-lg space-y-md">
      <div className="flex items-center gap-md">
        <div className="w-14 h-14 rounded-full bg-primary/20 flex items-center justify-center text-primary font-bold text-xl shrink-0">
          {session.workerName?.charAt(0) || 'W'}
        </div>
        <div className="min-w-0">
          <p className="text-body-md font-bold text-on-surface truncate">
            {session.workerName}
            {!hasWorkerData && <span className="ml-1 text-[10px] font-normal text-on-surface-variant/60 align-super">*</span>}
          </p>
          <p className="font-label-mono text-[10px] text-on-surface-variant uppercase tracking-widest">{session.workerId}</p>
        </div>
      </div>

      <div className="space-y-sm">
        <Row icon={Hash} label="Employee ID" value={worker?.employee_id || 'N/A'} placeholder={!worker} />
        <Row icon={Building2} label="Department" value={worker?.department || 'N/A'} placeholder={!worker} />
        <Row icon={Clock} label="Shift" value={worker?.shift || 'N/A'} placeholder={!worker} />
        <Row icon={Shield} label="Current Task" value={liveStatus?.currentTask || 'N/A'} />
      </div>

      <div className="pt-md border-t border-outline-variant space-y-sm">
        <div className="flex justify-between items-center">
          <span className="text-body-sm text-on-surface-variant">Risk Score</span>
          <span className={`font-label-mono font-bold ${liveStatus?.riskLevel === 'high' ? 'text-red-400' : liveStatus?.riskLevel === 'moderate' ? 'text-orange-400' : 'text-green-400'}`}>{liveStatus?.riskScore || '—'}</span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-body-sm text-on-surface-variant">Compliance</span>
          <span className="font-label-mono font-bold text-primary">{compliance.toFixed(0)}%</span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-body-sm text-on-surface-variant">Monitored Today</span>
          <span className="font-label-mono font-bold text-on-surface">{session.duration ? `${Math.floor(session.duration / 3600)}h ${Math.floor((session.duration % 3600) / 60)}m` : '—'}</span>
        </div>
        {!hasWorkerData && (
          <p className="text-[10px] text-on-surface-variant/50 pt-xs">
            * No worker record matches this session — add the worker in the Workers page to link their profile.
          </p>
        )}
      </div>
    </div>
  );
}

function Row({ icon: Icon, label, value, placeholder }: { icon: typeof User; label: string; value: string; placeholder?: boolean }) {
  return (
    <div className="flex items-center gap-sm text-body-sm">
      <Icon className="w-4 h-4 text-on-surface-variant shrink-0" />
      <span className="text-on-surface-variant min-w-[100px]">{label}</span>
      <span className="text-on-surface font-medium truncate">
        {value}
        {placeholder && <span className="ml-1 text-[10px] font-normal text-on-surface-variant/60 align-super">*</span>}
      </span>
    </div>
  );
}
