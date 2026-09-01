import { useState, useEffect } from 'react';
import { Link } from 'react-router';
import { CheckCircle, Circle, Rocket, Camera, Users, Bell, FileText, X } from 'lucide-react';

interface ChecklistItem {
  id: string;
  label: string;
  description: string;
  route: string;
  icon: typeof Camera;
  completed: boolean;
}

const CHECKLIST_KEY = 'ergovigilance_getting_started';

export function GettingStarted() {
  const [dismissed, setDismissed] = useState(() => {
    return localStorage.getItem(`${CHECKLIST_KEY}_dismissed`) === 'true';
  });
  const [items, setItems] = useState<ChecklistItem[]>(() => {
    const saved = localStorage.getItem(CHECKLIST_KEY);
    const completedIds: Set<string> = saved ? new Set(JSON.parse(saved)) : new Set();
    return [
      { id: 'onboarding', label: 'Complete Factory Setup', description: 'Walk through the 10-step onboarding checklist', route: '/onboarding', icon: Rocket, completed: completedIds.has('onboarding') },
      { id: 'cameras', label: 'Add Your First Camera', description: 'Connect a USB webcam or RTSP camera', route: '/monitoring', icon: Camera, completed: completedIds.has('cameras') },
      { id: 'workers', label: 'Register Workers', description: 'Add worker profiles for tracking', route: '/workers', icon: Users, completed: completedIds.has('workers') },
      { id: 'alerts', label: 'Configure Alerts', description: 'Set up email/Slack notifications', route: '/settings', icon: Bell, completed: completedIds.has('alerts') },
      { id: 'reports', label: 'Generate First Report', description: 'Run a session and download the report', route: '/reports', icon: FileText, completed: completedIds.has('reports') },
    ];
  });

  const completedCount = items.filter(i => i.completed).length;
  const allDone = completedCount === items.length;

  const toggleItem = (id: string) => {
    setItems(prev => {
      const next = prev.map(i => i.id === id ? { ...i, completed: !i.completed } : i);
      const completedIds = next.filter(i => i.completed).map(i => i.id);
      localStorage.setItem(CHECKLIST_KEY, JSON.stringify(completedIds));
      return next;
    });
  };

  const dismiss = () => {
    setDismissed(true);
    localStorage.setItem(`${CHECKLIST_KEY}_dismissed`, 'true');
  };

  if (dismissed || allDone) return null;

  return (
    <div className="bg-gradient-to-r from-blue-500/[0.08] to-cyan-500/[0.05] border border-blue-500/20 rounded-xl p-5 mb-lg">
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-blue-500/20 flex items-center justify-center">
            <Rocket className="w-5 h-5 text-blue-400" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white">Getting Started</h3>
            <p className="text-xs text-slate-400">{completedCount}/{items.length} steps completed</p>
          </div>
        </div>
        <button onClick={dismiss} className="text-slate-500 hover:text-white transition-colors">
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Progress bar */}
      <div className="h-1.5 rounded-full bg-white/5 mb-4 overflow-hidden">
        <div
          className="h-full rounded-full bg-gradient-to-r from-blue-500 to-cyan-400 transition-all duration-500"
          style={{ width: `${(completedCount / items.length) * 100}%` }}
        />
      </div>

      {/* Checklist */}
      <div className="space-y-2">
        {items.map((item) => {
          const Icon = item.icon;
          return (
            <Link
              key={item.id}
              to={item.route}
              onClick={() => toggleItem(item.id)}
              className={`flex items-center gap-3 p-2.5 rounded-lg transition-all ${
                item.completed
                  ? 'bg-green-500/5 border border-green-500/10'
                  : 'bg-white/[0.02] border border-white/5 hover:bg-white/[0.04] hover:border-white/10'
              }`}
            >
              {item.completed ? (
                <CheckCircle className="w-5 h-5 text-green-400 shrink-0" />
              ) : (
                <Circle className="w-5 h-5 text-slate-500 shrink-0" />
              )}
              <Icon className={`w-4 h-4 shrink-0 ${item.completed ? 'text-green-400' : 'text-slate-400'}`} />
              <div className="min-w-0">
                <p className={`text-sm font-medium ${item.completed ? 'text-green-300 line-through' : 'text-white'}`}>
                  {item.label}
                </p>
                <p className="text-[11px] text-slate-500 truncate">{item.description}</p>
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
