export interface SystemPerformanceData {
  systemHealth: 'healthy' | 'degraded' | 'critical';
  cpuUsage: number;
  memoryUsage: number;
  fps: number;
  cameraStatus: 'active' | 'degraded' | 'offline';
  cameraLatency: number;
  detectionLatency: number;
  processedFrames: number;
  droppedFrames: number;
  avgProcessingTime: number;
  peakMemory: number;
  uptime: number;
  gpuUtilization: number;
  aiModelConfidence: number;
  inferenceTime: number;
  lastModelUpdate: string;
  timeline: { time: string; value: number; label: string }[];
}

interface SystemPerformanceCardProps {
  data: SystemPerformanceData;
}

const healthColors: Record<string, string> = {
  healthy: 'text-green-400 border-green-500/30 bg-green-500/10',
  degraded: 'text-orange-400 border-orange-500/30 bg-orange-500/10',
  critical: 'text-red-400 border-red-500/30 bg-red-500/10',
};
const healthIcons: Record<string, string> = {
  healthy: '\u2713',
  degraded: '\u26A0',
  critical: '\u2716',
};
const camColors: Record<string, string> = {
  active: 'text-green-400',
  degraded: 'text-orange-400',
  offline: 'text-red-400',
};

function Bar({ value, max = 100, color = 'bg-primary' }: { value: number; max?: number; color?: string }) {
  const pct = Math.min((value / max) * 100, 100);
  return (
    <div className="w-full h-1.5 bg-surface-container-higher rounded-full overflow-hidden">
      <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

function Metric({ label, value, unit, color }: { label: string; value: string | number; unit?: string; color?: string }) {
  return (
    <div className="flex items-center justify-between py-1">
      <span className="text-[11px] text-on-surface-variant">{label}</span>
      <span className={`text-label-mono text-[11px] font-medium ${color || 'text-on-surface'}`}>{value}{unit}</span>
    </div>
  );
}

function MiniTimeline({ data }: { data: { time: string; value: number; label: string }[] }) {
  if (data.length === 0) {
    return <p className="text-[10px] text-on-surface-variant italic py-2">No timeline data yet</p>;
  }
  const maxV = Math.max(...data.map((d) => d.value), 1);
  return (
    <div className="flex items-end gap-[2px] h-12 py-1">
      {data.map((d, i) => (
        <div key={i} className="flex-1 flex flex-col items-center group relative">
          <div
            className="w-full bg-primary/60 rounded-t-sm transition-all hover:bg-primary"
            style={{ height: `${(d.value / maxV) * 100}%`, minHeight: 2 }}
          />
          <span className="text-[7px] text-on-surface-variant mt-0.5 truncate w-full text-center">{d.time}</span>
          <div className="absolute bottom-full mb-1 hidden group-hover:block bg-surface-container-higher border border-outline-variant rounded px-1.5 py-0.5 whitespace-nowrap z-10">
            <span className="text-[9px] text-on-surface">{d.label}: {d.value}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

export default function SystemPerformanceCard({ data }: SystemPerformanceCardProps) {
  return (
    <div className="bg-surface-container border border-outline-variant rounded-xl overflow-hidden">
      <div className="px-md py-sm border-b border-outline-variant/50 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-bold uppercase tracking-widest text-on-surface-variant">System Performance</span>
        </div>
        <span className={`text-[10px] px-2 py-0.5 rounded-full border font-medium ${healthColors[data.systemHealth] || healthColors.healthy}`}>
          {healthIcons[data.systemHealth] || healthIcons.healthy} {data.systemHealth.charAt(0).toUpperCase() + data.systemHealth.slice(1)}
        </span>
      </div>

      <div className="p-md space-y-md">

        {/* Section 1 — System Health */}
        <div>
          <p className="text-[9px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">System Health</p>
          <div className="bg-surface-container-higher rounded-lg p-sm space-y-1">
            <Metric label="Overall Status" value={data.systemHealth.charAt(0).toUpperCase() + data.systemHealth.slice(1)} color={healthColors[data.systemHealth].split(' ')[0]} />
            <Metric label="AI Model Confidence" value={data.aiModelConfidence} unit="%" color="text-primary" />
            <Metric label="Last Model Update" value={data.lastModelUpdate} />
          </div>
        </div>

        {/* Section 2 — Live Performance */}
        <div>
          <p className="text-[9px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">Live Performance</p>
          <div className="bg-surface-container-higher rounded-lg p-sm space-y-1">
            <div>
              <div className="flex items-center justify-between">
                <span className="text-[11px] text-on-surface-variant">CPU</span>
                <span className="text-label-mono text-[11px] font-medium text-on-surface">{data.cpuUsage}%</span>
              </div>
              <Bar value={data.cpuUsage} max={100} color={data.cpuUsage > 70 ? 'bg-red-400' : data.cpuUsage > 50 ? 'bg-orange-400' : 'bg-primary'} />
            </div>
            <div>
              <div className="flex items-center justify-between">
                <span className="text-[11px] text-on-surface-variant">Memory</span>
                <span className="text-label-mono text-[11px] font-medium text-on-surface">{data.memoryUsage}%</span>
              </div>
              <Bar value={data.memoryUsage} max={100} color={data.memoryUsage > 70 ? 'bg-red-400' : data.memoryUsage > 50 ? 'bg-orange-400' : 'bg-primary'} />
            </div>
            <div>
              <div className="flex items-center justify-between">
                <span className="text-[11px] text-on-surface-variant">FPS</span>
                <span className="text-label-mono text-[11px] font-medium text-on-surface">{data.fps}</span>
              </div>
              <Bar value={data.fps} max={30} color={data.fps < 20 ? 'bg-red-400' : data.fps < 25 ? 'bg-orange-400' : 'bg-primary'} />
            </div>
          </div>
        </div>

        {/* Section 3 — Camera Status */}
        <div>
          <p className="text-[9px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">Camera Status</p>
          <div className="bg-surface-container-higher rounded-lg p-sm space-y-1">
            <div className="flex items-center justify-between py-1">
              <span className="text-[11px] text-on-surface-variant">Camera</span>
              <span className={`text-label-mono text-[11px] font-medium ${camColors[data.cameraStatus] || camColors.active}`}>
                {data.cameraStatus === 'offline' ? '\u25CB' : data.cameraStatus === 'degraded' ? '\u25D0' : '\u25CF'} {data.cameraStatus.charAt(0).toUpperCase() + data.cameraStatus.slice(1)}
              </span>
            </div>
            <Metric label="Camera Latency" value={data.cameraLatency} unit="ms" />
            <Metric label="Detection Latency" value={data.detectionLatency} unit="ms" />
          </div>
        </div>

        {/* Section 4 — Session Metrics */}
        <div>
          <p className="text-[9px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">Session Metrics</p>
          <div className="bg-surface-container-higher rounded-lg p-sm space-y-1">
            <Metric label="Frames Processed" value={data.processedFrames.toLocaleString()} />
            <Metric label="Frames Dropped" value={data.droppedFrames.toLocaleString()} color={data.droppedFrames > 30 ? 'text-red-400' : 'text-on-surface'} />
            <Metric label="Avg Processing Time" value={data.avgProcessingTime} unit="ms" />
            <Metric label="Peak Memory" value={data.peakMemory} unit="%" color={data.peakMemory > 75 ? 'text-red-400' : 'text-on-surface'} />
            <Metric label="Uptime" value={data.uptime > 3600 ? `${(data.uptime / 3600).toFixed(1)}h` : `${Math.round(data.uptime / 60)}m`} />
          </div>
        </div>

        {/* Section 5 — Resource Monitor */}
        <div>
          <p className="text-[9px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">Resource Monitor</p>
          <div className="bg-surface-container-higher rounded-lg p-sm space-y-1">
            <Metric label="GPU Utilization" value={data.gpuUtilization} unit="%" />
            <Metric label="AI Inference Time" value={data.inferenceTime} unit="ms" />
            <Metric label="AI Confidence" value={data.aiModelConfidence} unit="%" color="text-primary" />
            <Metric label="Model Version" value={data.lastModelUpdate} />
          </div>
        </div>

        {/* Section 6 — Performance Timeline */}
        <div>
          <p className="text-[9px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">Performance Timeline</p>
          <div className="bg-surface-container-higher rounded-lg p-sm">
            <MiniTimeline data={data.timeline} />
          </div>
        </div>

        {/* Section 7 — AI Performance Summary */}
        <div>
          <p className="text-[9px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">AI Performance Summary</p>
          <div className="bg-surface-container-higher rounded-lg p-sm grid grid-cols-2 gap-x-3 gap-y-1">
            <Metric label="Model Confidence" value={data.aiModelConfidence} unit="%" color="text-primary" />
            <Metric label="Inference Time" value={data.inferenceTime} unit="ms" />
            <Metric label="FPS (Live)" value={data.fps} />
            <Metric label="Dropped Frames" value={data.droppedFrames.toLocaleString()} color={data.droppedFrames > 30 ? 'text-red-400' : 'text-on-surface'} />
            <Metric label="Avg Processing" value={data.avgProcessingTime} unit="ms" />
            <Metric label="Detection Latency" value={data.detectionLatency} unit="ms" />
          </div>
        </div>

      </div>
    </div>
  );
}
