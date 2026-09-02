import { useState } from 'react';
import { CheckCircle, Circle, AlertTriangle } from 'lucide-react';

interface ChecklistItem {
  id: string;
  phase: string;
  title: string;
  description: string;
  owner: string;
  critical: boolean;
}

const CHECKLIST: ChecklistItem[] = [
  { id: 'p1-1', phase: 'Pre-Installation', title: 'Site survey completed', description: 'Visit factory floor, identify camera mounting points', owner: 'Implementation Team', critical: true },
  { id: 'p1-2', phase: 'Pre-Installation', title: 'Camera hardware procured', description: 'USB webcam or IP camera with RTSP. Min 720p 30fps', owner: 'Customer IT', critical: true },
  { id: 'p1-3', phase: 'Pre-Installation', title: 'Workstation PC provisioned', description: 'Min: 4-core CPU, 8GB RAM, 50GB SSD', owner: 'Customer IT', critical: true },
  { id: 'p1-4', phase: 'Pre-Installation', title: 'Network access confirmed', description: 'PC can reach internet. Ports 8000/3000 open', owner: 'Customer IT', critical: true },
  { id: 'p1-5', phase: 'Pre-Installation', title: 'Worker consent forms prepared', description: 'GDPR-compliant consent in local language', owner: 'Safety Manager', critical: true },
  { id: 'p2-1', phase: 'Installation', title: 'Software deployed', description: 'docker compose up -d. Verify all services healthy', owner: 'Implementation Team', critical: true },
  { id: 'p2-2', phase: 'Installation', title: 'Camera mounted and tested', description: 'Full worker body visible. Frame rate >= 15fps', owner: 'Implementation Team', critical: true },
  { id: 'p2-3', phase: 'Installation', title: 'Workers enrolled', description: 'Create profiles, assign IDs/departments/shifts', owner: 'Safety Manager', critical: false },
  { id: 'p2-4', phase: 'Installation', title: 'Alert thresholds configured', description: 'Adjust sensitivity per workstation type', owner: 'Safety Manager', critical: false },
  { id: 'p2-5', phase: 'Installation', title: 'Notifications set up', description: 'Configure SMTP or Slack webhook', owner: 'Customer IT', critical: false },
  { id: 'p3-1', phase: 'Validation', title: 'Demo session recorded', description: '5-min session with known good/bad postures', owner: 'Implementation Team', critical: true },
  { id: 'p3-2', phase: 'Validation', title: 'Alert firing verified', description: 'Trigger bad posture. Alert in <30s', owner: 'Implementation Team', critical: true },
  { id: 'p3-3', phase: 'Validation', title: 'Report export tested', description: 'Export PDF/CSV. Verify branding and disclaimer', owner: 'Implementation Team', critical: false },
  { id: 'p3-4', phase: 'Validation', title: 'Recovery tested', description: 'Restart backend. Dashboard reconnects in <30s', owner: 'Implementation Team', critical: true },
  { id: 'p4-1', phase: 'Go-Live', title: 'Pilot duration agreed', description: 'Min 2 weeks, recommended 30 days', owner: 'Safety Manager + Vendor', critical: true },
  { id: 'p4-2', phase: 'Go-Live', title: 'Daily check-in scheduled', description: '15-min daily sync for first week', owner: 'Implementation Team', critical: false },
  { id: 'p4-3', phase: 'Go-Live', title: 'Escalation path defined', description: 'Who to call if system goes down', owner: 'Vendor', critical: true },
  { id: 'p4-4', phase: 'Go-Live', title: 'Success criteria documented', description: '<5% false positive, 90%+ worker acceptance', owner: 'Safety Manager', critical: false },
];

const PHASES = ['Pre-Installation', 'Installation', 'Validation', 'Go-Live'];
const PHASE_COLORS: Record<string, string> = {
  'Pre-Installation': 'bg-blue-500/15 text-blue-400 border-blue-500/30',
  'Installation': 'bg-green-500/15 text-green-400 border-green-500/30',
  'Validation': 'bg-amber-500/15 text-amber-400 border-amber-500/30',
  'Go-Live': 'bg-purple-500/15 text-purple-400 border-purple-500/30',
};

export default function PilotChecklistPage() {
  const [checked, setChecked] = useState<Set<string>>(() => {
    try { return new Set(JSON.parse(localStorage.getItem('pilot_checklist') || '[]')); } catch { return new Set(); }
  });

  const toggle = (id: string) => {
    setChecked(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      localStorage.setItem('pilot_checklist', JSON.stringify([...next]));
      return next;
    });
  };

  const totalCritical = CHECKLIST.filter(i => i.critical).length;
  const checkedCritical = CHECKLIST.filter(i => i.critical && checked.has(i.id)).length;
  const progress = Math.round((checked.size / CHECKLIST.length) * 100);

  return (
    <div className="p-lg space-y-lg pb-32">
      <div>
        <h1 className="text-display-lg font-bold text-on-surface">On-Site Pilot Checklist</h1>
        <p className="text-body-sm text-on-surface-variant mt-xs">Step-by-step guide for deploying ErgoVigilance at a factory</p>
      </div>

      <section className="rounded-2xl border border-outline-variant bg-surface-container p-lg">
        <div className="flex items-center justify-between mb-md">
          <div>
            <p className="text-title-sm font-bold text-on-surface">Progress</p>
            <p className="text-body-sm text-on-surface-variant">{checked.size}/{CHECKLIST.length} completed</p>
          </div>
          <div className="text-right">
            <p className="text-title-lg font-bold text-on-surface">{progress}%</p>
            <p className="text-[10px] text-on-surface-variant">{checkedCritical}/{totalCritical} critical done</p>
          </div>
        </div>
        <div className="h-3 rounded-full bg-surface-container-highest overflow-hidden">
          <div className="h-full rounded-full bg-primary transition-all" style={{ width: progress + '%' }} />
        </div>
        {checkedCritical < totalCritical && (
          <div className="mt-md flex items-center gap-sm text-[11px] text-amber-400">
            <AlertTriangle className="w-3.5 h-3.5" />
            {totalCritical - checkedCritical} critical items remaining
          </div>
        )}
      </section>

      {PHASES.map(phase => {
        const items = CHECKLIST.filter(i => i.phase === phase);
        const done = items.filter(i => checked.has(i.id)).length;
        return (
          <section key={phase} className="rounded-2xl border border-outline-variant bg-surface-container p-lg space-y-md">
            <div className="flex items-center gap-md">
              <span className={`px-sm py-1 rounded-lg text-[11px] font-bold border ${PHASE_COLORS[phase]}`}>{phase}</span>
              <span className="text-body-sm text-on-surface-variant">{done}/{items.length}</span>
            </div>
            <div className="space-y-sm">
              {items.map(item => (
                <button key={item.id} onClick={() => toggle(item.id)}
                  className={`w-full text-left rounded-xl border p-md transition-colors ${checked.has(item.id) ? 'bg-primary/5 border-primary/20' : 'bg-surface-container-low border-outline-variant hover:border-primary/30'}`}>
                  <div className="flex items-start gap-md">
                    {checked.has(item.id) ? <CheckCircle className="w-5 h-5 text-primary shrink-0 mt-0.5" /> : <Circle className="w-5 h-5 text-on-surface-variant/40 shrink-0 mt-0.5" />}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-sm">
                        <p className={`text-body-sm font-bold ${checked.has(item.id) ? 'text-primary' : 'text-on-surface'}`}>{item.title}</p>
                        {item.critical && <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-red-500/15 text-red-400">CRITICAL</span>}
                      </div>
                      <p className="text-[11px] text-on-surface-variant mt-1">{item.description}</p>
                      <p className="text-[10px] text-on-surface-variant/60 mt-1">Owner: {item.owner}</p>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}
