import { useEffect, useState } from 'react';
import { useSessionLifecycle, SessionStatus } from '@/src/hooks/useSessionLifecycle';
import { useSettings } from '@/src/hooks/useSettings';
import { Camera, Play, Square, Loader2, Wifi } from 'lucide-react';
import { apiFetch } from '@/src/services/apiClient';
import type { WorkerRecord } from '@/src/types/api';

const statusLabels: Record<SessionStatus, string> = {
  idle: 'Start Monitoring',
  starting: 'Starting...',
  monitoring: 'Stop Monitoring',
  stopping: 'Stopping...',
  error: 'Start Monitoring',
};

const statusColors: Record<SessionStatus, string> = {
  idle: 'bg-primary text-on-primary hover:brightness-110 shadow-md shadow-primary/25',
  starting: 'bg-amber-500 text-on-primary cursor-wait',
  monitoring: 'bg-red-500 text-on-primary hover:bg-red-600 shadow-md shadow-red-500/20',
  stopping: 'bg-amber-500 text-on-primary cursor-wait',
  error: 'bg-red-500 text-on-primary hover:bg-red-600 shadow-md shadow-red-500/20',
};

export default function MonitoringControls() {
  const { status, error, startSession, stopSession } = useSessionLifecycle();
  const { settings } = useSettings();
  const [workers, setWorkers] = useState<WorkerRecord[]>([]);
  const [selectedWorkerId, setSelectedWorkerId] = useState('');
  const isMonitoring = status === 'monitoring';
  const isBusy = status === 'starting' || status === 'stopping';

  useEffect(() => {
    let cancelled = false;
    apiFetch('/api/workers')
      .then((res) => (res.ok ? res.json() : []))
      .then((data: WorkerRecord[]) => {
        if (cancelled) return;
        setWorkers(data);
        if (!selectedWorkerId && data.length > 0) setSelectedWorkerId(data[0].worker_id);
      })
      .catch(() => {
        if (!cancelled) setWorkers([]);
      });
    return () => { cancelled = true; };
  }, [selectedWorkerId]);

  const handleClick = () => {
    if (isBusy) return;
    if (isMonitoring) {
      stopSession();
    } else {
      startSession(selectedWorkerId);
    }
  };

  return (
    <div className="flex items-center gap-md">
      {!isMonitoring && (
        <>
          {/* Session setup cluster: worker + camera selection */}
          <div className="flex items-center gap-sm px-sm py-1.5 rounded-lg border border-outline-variant bg-surface-container">
            <select
              value={selectedWorkerId}
              onChange={(e) => setSelectedWorkerId(e.target.value)}
              disabled={isBusy || workers.length === 0}
              className="h-8 rounded-md border border-transparent bg-transparent px-1 text-xs text-on-surface outline-none focus:border-primary disabled:opacity-60"
              title="Worker for new monitoring session"
            >
              {workers.length === 0 ? (
                <option value="">No workers</option>
              ) : workers.map((worker) => (
                <option key={worker.worker_id} value={worker.worker_id}>
                  {worker.name} ({worker.employee_id})
                </option>
              ))}
            </select>
            <span className="w-px h-5 bg-outline-variant/60" />
            <span className="h-8 flex items-center px-1 text-xs text-on-surface-variant" title="Camera ID for this session">
              <Camera className="w-3.5 h-3.5 mr-1" /> cam {settings.cameraId || '0'}
            </span>
          </div>
        </>
      )}
      <button
        onClick={handleClick}
        disabled={isBusy || (!isMonitoring && !selectedWorkerId)}
        className={`flex items-center gap-2 h-11 px-6 rounded-lg text-sm font-bold transition-all ${statusColors[status]}`}
      >
        {status === 'starting' || status === 'stopping' ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : isMonitoring ? (
          <Square className="w-4 h-4" />
        ) : (
          <Play className="w-4 h-4" />
        )}
        <span>{statusLabels[status]}</span>
      </button>

      {isMonitoring && (
        <div className="flex items-center gap-1.5 text-xs text-green-600 font-medium">
          <Wifi className="w-3.5 h-3.5 animate-pulse" />
          <span>Live</span>
        </div>
      )}

      {error && (
        <span className="text-xs text-red-500 max-w-[200px] truncate" title={error}>
          {error}
        </span>
      )}
    </div>
  );
}
