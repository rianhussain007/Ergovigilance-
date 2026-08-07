import React, { useState, useEffect } from 'react';
import { useDemo } from '@/src/demo/DemoProvider';
import { Fullscreen, Camera, Monitor, Maximize, Cpu } from 'lucide-react';

const poses = [
  <svg key="good" viewBox="0 0 200 280" className="w-full h-full">
    <circle cx="100" cy="30" r="18" fill="#4ade80" opacity="0.3" />
    <circle cx="100" cy="30" r="18" fill="none" stroke="#4ade80" strokeWidth="1.5" />
    <line x1="100" y1="48" x2="100" y2="130" stroke="#4ade80" strokeWidth="2.5" strokeLinecap="round" />
    <line x1="100" y1="75" x2="65" y2="100" stroke="#4ade80" strokeWidth="2" strokeLinecap="round" />
    <line x1="100" y1="75" x2="135" y2="100" stroke="#4ade80" strokeWidth="2" strokeLinecap="round" />
    <line x1="100" y1="130" x2="75" y2="200" stroke="#4ade80" strokeWidth="2.5" strokeLinecap="round" />
    <line x1="100" y1="130" x2="125" y2="200" stroke="#4ade80" strokeWidth="2.5" strokeLinecap="round" />
    <line x1="75" y1="200" x2="60" y2="260" stroke="#4ade80" strokeWidth="2" strokeLinecap="round" />
    <line x1="125" y1="200" x2="140" y2="260" stroke="#4ade80" strokeWidth="2" strokeLinecap="round" />
    <circle cx="65" cy="100" r="3" fill="#4ade80" opacity="0.6" />
    <circle cx="135" cy="100" r="3" fill="#4ade80" opacity="0.6" />
    <text x="100" y="276" textAnchor="middle" fill="#4ade80" fontSize="8" opacity="0.6">Good Posture</text>
  </svg>,
  <svg key="neck" viewBox="0 0 200 280">
    <circle cx="100" cy="38" r="18" fill="#f97316" opacity="0.3" />
    <circle cx="100" cy="38" r="18" fill="none" stroke="#f97316" strokeWidth="1.5" />
    <line x1="100" y1="56" x2="100" y2="130" stroke="#f97316" strokeWidth="2.5" strokeLinecap="round" />
    <line x1="100" y1="56" x2="95" y2="48" stroke="#f97316" strokeWidth="2" strokeLinecap="round" />
    <line x1="100" y1="75" x2="70" y2="100" stroke="#f97316" strokeWidth="2" strokeLinecap="round" />
    <line x1="100" y1="75" x2="130" y2="100" stroke="#f97316" strokeWidth="2" strokeLinecap="round" />
    <line x1="100" y1="130" x2="75" y2="200" stroke="#f97316" strokeWidth="2.5" strokeLinecap="round" />
    <line x1="100" y1="130" x2="125" y2="200" stroke="#f97316" strokeWidth="2.5" strokeLinecap="round" />
    <line x1="75" y1="200" x2="60" y2="260" stroke="#f97316" strokeWidth="2" strokeLinecap="round" />
    <line x1="125" y1="200" x2="140" y2="260" stroke="#f97316" strokeWidth="2" strokeLinecap="round" />
    <path d="M 85 42 Q 92 35 100 38" fill="none" stroke="#f97316" strokeWidth="1" />
    <text x="100" y="276" textAnchor="middle" fill="#f97316" fontSize="8" opacity="0.6">Neck Flexion 28°</text>
  </svg>,
  <svg key="trunk" viewBox="0 0 200 280">
    <circle cx="100" cy="25" r="18" fill="#ef4444" opacity="0.3" />
    <circle cx="100" cy="25" r="18" fill="none" stroke="#ef4444" strokeWidth="1.5" />
    <line x1="100" y1="43" x2="95" y2="35" stroke="#ef4444" strokeWidth="2" strokeLinecap="round" />
    <line x1="100" y1="43" x2="115" y2="120" stroke="#ef4444" strokeWidth="2.5" strokeLinecap="round" />
    <line x1="115" y1="75" x2="85" y2="95" stroke="#ef4444" strokeWidth="2" strokeLinecap="round" />
    <line x1="115" y1="75" x2="145" y2="95" stroke="#ef4444" strokeWidth="2" strokeLinecap="round" />
    <line x1="115" y1="120" x2="95" y2="190" stroke="#ef4444" strokeWidth="2.5" strokeLinecap="round" />
    <line x1="115" y1="120" x2="135" y2="190" stroke="#ef4444" strokeWidth="2.5" strokeLinecap="round" />
    <line x1="95" y1="190" x2="80" y2="260" stroke="#ef4444" strokeWidth="2" strokeLinecap="round" />
    <line x1="135" y1="190" x2="150" y2="260" stroke="#ef4444" strokeWidth="2" strokeLinecap="round" />
    <path d="M 100 43 Q 108 80 115 120" fill="none" stroke="#ef4444" strokeWidth="1" strokeDasharray="3,2" />
    <text x="100" y="276" textAnchor="middle" fill="#ef4444" fontSize="8" opacity="0.6">Trunk Flexion 38°</text>
  </svg>,
  <svg key="shoulder" viewBox="0 0 200 280">
    <circle cx="100" cy="30" r="18" fill="#f97316" opacity="0.3" />
    <circle cx="100" cy="30" r="18" fill="none" stroke="#f97316" strokeWidth="1.5" />
    <line x1="100" y1="48" x2="100" y2="130" stroke="#f97316" strokeWidth="2.5" strokeLinecap="round" />
    <line x1="100" y1="70" x2="60" y2="90" stroke="#f97316" strokeWidth="2" strokeLinecap="round" />
    <line x1="100" y1="70" x2="140" y2="85" stroke="#f97316" strokeWidth="2" strokeLinecap="round" />
    <line x1="100" y1="130" x2="75" y2="200" stroke="#f97316" strokeWidth="2.5" strokeLinecap="round" />
    <line x1="100" y1="130" x2="125" y2="200" stroke="#f97316" strokeWidth="2.5" strokeLinecap="round" />
    <line x1="75" y1="200" x2="60" y2="260" stroke="#f97316" strokeWidth="2" strokeLinecap="round" />
    <line x1="125" y1="200" x2="140" y2="260" stroke="#f97316" strokeWidth="2" strokeLinecap="round" />
    <circle cx="60" cy="90" r="5" fill="#f97316" opacity="0.4" />
    <circle cx="140" cy="85" r="5" fill="#f97316" opacity="0.4" />
    <text x="100" y="276" textAnchor="middle" fill="#f97316" fontSize="8" opacity="0.6">Shoulder Elevation</text>
  </svg>,
  <svg key="recovery" viewBox="0 0 200 280">
    <circle cx="100" cy="30" r="18" fill="#22d3ee" opacity="0.3" />
    <circle cx="100" cy="30" r="18" fill="none" stroke="#22d3ee" strokeWidth="1.5" />
    <line x1="100" y1="48" x2="100" y2="130" stroke="#22d3ee" strokeWidth="2.5" strokeLinecap="round" />
    <line x1="100" y1="75" x2="65" y2="100" stroke="#22d3ee" strokeWidth="2" strokeLinecap="round" />
    <line x1="100" y1="75" x2="135" y2="100" stroke="#22d3ee" strokeWidth="2" strokeLinecap="round" />
    <line x1="100" y1="130" x2="75" y2="200" stroke="#22d3ee" strokeWidth="2.5" strokeLinecap="round" />
    <line x1="100" y1="130" x2="125" y2="200" stroke="#22d3ee" strokeWidth="2.5" strokeLinecap="round" />
    <line x1="75" y1="200" x2="60" y2="260" stroke="#22d3ee" strokeWidth="2" strokeLinecap="round" />
    <line x1="125" y1="200" x2="140" y2="260" stroke="#22d3ee" strokeWidth="2" strokeLinecap="round" />
    <text x="100" y="276" textAnchor="middle" fill="#22d3ee" fontSize="8" opacity="0.6">Posture Corrected</text>
  </svg>,
];

export default function CameraPlayback({ workerName }: { workerName?: string }) {
  const { state } = useDemo();
  const [fullscreen, setFullscreen] = useState(false);
  const [poseIndex, setPoseIndex] = useState(0);

  useEffect(() => {
    if (!state.active) return;
    const interval = setInterval(() => {
      setPoseIndex((prev) => (prev + 1) % poses.length);
    }, 3000 / state.speed);
    return () => clearInterval(interval);
  }, [state.active, state.speed]);

  const riskColor = state.dashboard.liveStatus.riskLevel === 'high' ? 'text-red-400' : state.dashboard.liveStatus.riskLevel === 'moderate' ? 'text-orange-400' : 'text-green-400';

  return (
    <div className={`relative bg-surface-container-lowest rounded-xl border border-outline-variant overflow-hidden ${fullscreen ? 'fixed inset-0 z-50' : ''}`}>
      <div className="aspect-video relative bg-black/80">
        <div className="absolute inset-0 flex items-center justify-center p-lg">
          <div className="w-full h-full max-w-[300px] max-h-[280px]">
            {poses[poseIndex]}
          </div>
        </div>

        <div className="absolute inset-0 pointer-events-none opacity-[0.04]" style={{ backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(255,255,255,0.08) 2px, rgba(255,255,255,0.08) 4px)' }} />

        <div className="absolute top-3 left-3 flex items-center gap-sm">
          <div className="flex items-center gap-1.5 bg-red-500/20 px-2 py-0.5 rounded">
            <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
            <span className="text-[9px] font-bold text-red-400 uppercase">REC</span>
          </div>
          <span className="text-[9px] font-label-mono text-white/50">{new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })}</span>
        </div>

        <div className="absolute top-3 right-3">
          <span className="flex items-center gap-1 bg-blue-500/20 text-blue-400 px-2 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider border border-blue-500/30">
            <Cpu className="w-3 h-3" />
            Simulation
          </span>
        </div>

        <div className="absolute bottom-3 left-3 flex items-center gap-md">
          <span className="text-[9px] font-label-mono text-white/60 bg-black/40 px-1.5 py-0.5 rounded">FPS 30</span>
          <span className="text-[9px] font-label-mono text-white/60 bg-black/40 px-1.5 py-0.5 rounded">1280×720</span>
          <span className={`text-[9px] font-label-mono bg-black/40 px-1.5 py-0.5 rounded ${riskColor}`}>
            Risk: {state.dashboard.liveStatus.riskLevel.toUpperCase()}
          </span>
        </div>

        <div className="absolute bottom-3 right-3 flex gap-sm">
          <button onClick={() => setFullscreen(!fullscreen)} className="p-1 rounded bg-black/40 text-white/60 hover:text-white transition-colors">
            {fullscreen ? <Minimize className="w-3.5 h-3.5" /> : <Maximize className="w-3.5 h-3.5" />}
          </button>
        </div>

        <div className="absolute inset-0 pointer-events-none">
          <svg viewBox="0 0 200 280" className="w-full h-full opacity-[0.15]">
            <line x1="100" y1="30" x2="100" y2="130" stroke="#60a5fa" strokeWidth="1" />
            <line x1="100" y1="75" x2="65" y2="100" stroke="#60a5fa" strokeWidth="0.8" />
            <line x1="100" y1="75" x2="135" y2="100" stroke="#60a5fa" strokeWidth="0.8" />
            <line x1="100" y1="130" x2="75" y2="200" stroke="#60a5fa" strokeWidth="1" />
            <line x1="100" y1="130" x2="125" y2="200" stroke="#60a5fa" strokeWidth="1" />
            <line x1="75" y1="200" x2="60" y2="260" stroke="#60a5fa" strokeWidth="0.8" />
            <line x1="125" y1="200" x2="140" y2="260" stroke="#60a5fa" strokeWidth="0.8" />
            <circle cx="100" cy="30" r="18" fill="none" stroke="#60a5fa" strokeWidth="0.8" />
          </svg>
        </div>
      </div>

      <div className="flex items-center justify-between px-lg py-sm bg-surface-container">
        <div className="flex items-center gap-md">
          <Camera className="w-4 h-4 text-on-surface-variant" />
          <span className="text-body-sm font-medium text-on-surface">{workerName || 'Worker'}</span>
          {!state.presentationMode && (
            <span className="text-[10px] text-on-surface-variant bg-blue-500/10 text-blue-400 px-1.5 py-0.5 rounded font-label-mono">Simulation Feed</span>
          )}
        </div>
        <div className="flex items-center gap-sm">
          <Monitor className="w-3.5 h-3.5 text-on-surface-variant" />
          <span className="font-label-mono text-[10px] text-on-surface-variant">{state.dashboard.session.currentTime.substring(11, 19)}</span>
        </div>
      </div>
    </div>
  );
}

function Minimize(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <polyline points="4 14 10 14 10 20" /><polyline points="20 10 14 10 14 4" /><line x1="14" y1="10" x2="21" y2="3" /><line x1="3" y1="21" x2="10" y2="14" />
    </svg>
  );
}
