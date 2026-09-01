import { useState } from 'react';
import { CheckCircle2, Circle, Camera, Wifi, Users, Shield, Play, FileText, Settings, ArrowRight, ChevronDown, ChevronUp } from 'lucide-react';

interface ChecklistItem {
  id: string;
  title: string;
  description: string;
  category: string;
  estimated_time: string;
  details: string[];
}

const CHECKLIST: ChecklistItem[] = [
  {
    id: 'network',
    title: 'Verify Network Connectivity',
    description: 'Ensure all cameras and the server are on the same network',
    category: 'Network',
    estimated_time: '15 min',
    details: [
      'Ping each camera IP from the server: ping 192.168.1.100',
      'Verify RTSP port (554) is open: telnet 192.168.1.100 554',
      'Check firewall rules allow camera traffic',
      'Test internet connectivity for cloud features',
    ],
  },
  {
    id: 'cameras',
    title: 'Configure CCTV Cameras',
    description: 'Add RTSP stream URLs for each monitoring station',
    category: 'Cameras',
    estimated_time: '10 min per camera',
    details: [
      'Get RTSP URL from camera settings or NVR system',
      'Format: rtsp://username:password@ip:port/stream',
      'Test stream: ffplay rtsp://admin:pass@192.168.1.100:554/live',
      'Add cameras via Cloud Cameras page or .env file',
    ],
  },
  {
    id: 'placement',
    title: 'Camera Placement',
    description: 'Position cameras for optimal worker visibility',
    category: 'Cameras',
    estimated_time: '20 min per station',
    details: [
      'Mount 2-3 meters from the worker',
      'Angle: 15-30 degrees above eye level',
      'Ensure full body is visible (head to knees minimum)',
      'Avoid backlighting (windows behind the worker)',
      'Use the Setup Wizard for live positioning feedback',
    ],
  },
  {
    id: 'lighting',
    title: 'Verify Lighting Conditions',
    description: 'Ensure adequate lighting for pose detection',
    category: 'Environment',
    estimated_time: '10 min per station',
    details: [
      'Brightness should be 60-200 out of 255',
      'Avoid harsh shadows on workers',
      'Consistent lighting across the shift',
      'Use the Setup Wizard brightness indicator',
    ],
  },
  {
    id: 'consent',
    title: 'Collect Worker Consent Forms',
    description: 'Distribute and collect signed consent forms',
    category: 'Compliance',
    estimated_time: '5 min per worker',
    details: [
      'Print consent forms from docs/worker_consent_form.html',
      'Explain what the system monitors (posture, not identity)',
      'Explain data retention (30 days keypoints, 1 year scores)',
      'Collect signed forms and store with worker records',
      'Workers may opt-out at any time',
    ],
  },
  {
    id: 'workers',
    title: 'Register Workers',
    description: 'Add worker profiles to the system',
    category: 'Setup',
    estimated_time: '2 min per worker',
    details: [
      'Go to Workers page → Add Worker',
      'Enter Employee ID, Name, Department, Shift',
      'Assign to monitoring stations',
      'Workers can view their own data via My Posture page',
    ],
  },
  {
    id: 'admin',
    title: 'Create Admin Account',
    description: 'Set up the primary administrator account',
    category: 'Setup',
    estimated_time: '5 min',
    details: [
      'Register the first account (becomes admin)',
      'Set a strong AUTH_JWT_SECRET in .env',
      'Create supervisor and safety manager accounts',
      'Configure email/Slack for alerts in .env',
    ],
  },
  {
    id: 'test-session',
    title: 'Run Test Monitoring Session',
    description: 'Start a 5-minute test session to verify everything works',
    category: 'Testing',
    estimated_time: '10 min',
    details: [
      'Go to Live Monitoring → Start Session',
      'Have a worker perform normal tasks',
      'Verify pose detection and risk scoring',
      'Check that alerts fire for poor posture',
      'Stop session and verify report generates',
    ],
  },
  {
    id: 'alerts',
    title: 'Configure Alert Rules',
    description: 'Set up email/Slack notifications for safety events',
    category: 'Alerts',
    estimated_time: '15 min',
    details: [
      'Configure SMTP settings in .env for email alerts',
      'Configure SLACK_WEBHOOK_URL for Slack notifications',
      'Set alert thresholds (risk level, duration)',
      'Test alerts with a deliberate poor posture',
      'Verify notifications reach safety managers',
    ],
  },
  {
    id: 'backup',
    title: 'Set Up Backup Schedule',
    description: 'Configure automatic backups of session data',
    category: 'Operations',
    estimated_time: '20 min',
    details: [
      'Schedule daily database backups',
      'Archive old session data (>30 days)',
      'Test restore procedure',
      'Document backup location and credentials',
    ],
  },
];

const CATEGORIES = ['Network', 'Cameras', 'Environment', 'Compliance', 'Setup', 'Testing', 'Alerts', 'Operations'];

export default function OnboardingChecklistPage() {
  const [completed, setCompleted] = useState<Set<string>>(new Set());
  const [expandedItem, setExpandedItem] = useState<string | null>(null);
  const [activeCategory, setActiveCategory] = useState<string | null>(null);

  const toggleItem = (id: string) => {
    setCompleted(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const progress = Math.round((completed.size / CHECKLIST.length) * 100);
  const filteredItems = activeCategory
    ? CHECKLIST.filter(item => item.category === activeCategory)
    : CHECKLIST;

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="rounded-lg bg-primary/10 p-2">
          <CheckCircle2 className="h-6 w-6 text-primary" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-white">Factory Onboarding</h1>
          <p className="text-sm text-slate-400">
            Step-by-step checklist for setting up ErgoVigilance at your factory
          </p>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="rounded-xl border border-white/10 bg-white/5 p-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm text-slate-400">
            {completed.size} of {CHECKLIST.length} steps completed
          </span>
          <span className="text-sm font-bold text-white">{progress}%</span>
        </div>
        <div className="h-3 rounded-full bg-white/10">
          <div
            className="h-full rounded-full bg-primary transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
        {progress === 100 && (
          <div className="mt-3 flex items-center gap-2 text-green-400 text-sm">
            <CheckCircle2 className="h-4 w-4" />
            <span className="font-medium">Factory setup complete! Ready for production monitoring.</span>
          </div>
        )}
      </div>

      {/* Category Filter */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => setActiveCategory(null)}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
            activeCategory === null
              ? 'bg-primary text-white'
              : 'bg-white/5 text-slate-400 hover:bg-white/10'
          }`}
        >
          All Steps
        </button>
        {CATEGORIES.map(cat => (
          <button
            key={cat}
            onClick={() => setActiveCategory(activeCategory === cat ? null : cat)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
              activeCategory === cat
                ? 'bg-primary text-white'
                : 'bg-white/5 text-slate-400 hover:bg-white/10'
            }`}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* Checklist Items */}
      <div className="space-y-3">
        {filteredItems.map((item, i) => {
          const isCompleted = completed.has(item.id);
          const isExpanded = expandedItem === item.id;

          return (
            <div
              key={item.id}
              className={`rounded-xl border transition ${
                isCompleted
                  ? 'border-green-500/20 bg-green-500/5'
                  : 'border-white/10 bg-white/5 hover:bg-white/[0.07]'
              }`}
            >
              <div
                className="flex items-center gap-3 p-4 cursor-pointer"
                onClick={() => setExpandedItem(isExpanded ? null : item.id)}
              >
                <button
                  onClick={(e) => { e.stopPropagation(); toggleItem(item.id); }}
                  className="flex-shrink-0"
                >
                  {isCompleted ? (
                    <CheckCircle2 className="h-5 w-5 text-green-400" />
                  ) : (
                    <Circle className="h-5 w-5 text-slate-500 hover:text-primary" />
                  )}
                </button>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <h3 className={`font-medium ${isCompleted ? 'text-green-400 line-through' : 'text-white'}`}>
                      {item.title}
                    </h3>
                    <span className="rounded-full bg-white/10 px-2 py-0.5 text-[10px] text-slate-400">
                      {item.category}
                    </span>
                    <span className="rounded-full bg-white/10 px-2 py-0.5 text-[10px] text-slate-400">
                      ~{item.estimated_time}
                    </span>
                  </div>
                  <p className="text-sm text-slate-400 mt-0.5">{item.description}</p>
                </div>
                {isExpanded ? (
                  <ChevronUp className="h-4 w-4 text-slate-500" />
                ) : (
                  <ChevronDown className="h-4 w-4 text-slate-500" />
                )}
              </div>

              {isExpanded && (
                <div className="border-t border-white/5 px-4 pb-4 pt-3">
                  <ul className="space-y-2">
                    {item.details.map((detail, j) => (
                      <li key={j} className="flex items-start gap-2 text-sm text-slate-300">
                        <ArrowRight className="mt-0.5 h-3 w-3 flex-shrink-0 text-primary" />
                        <span>{detail}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Quick Links */}
      <div className="rounded-xl border border-white/10 bg-white/5 p-6">
        <h2 className="mb-3 text-lg font-semibold text-white">Quick Links</h2>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <a href="/cloud-cameras" className="flex items-center gap-2 text-cyan-400 hover:text-cyan-300">
            <Camera className="h-4 w-4" /> Cloud Cameras
          </a>
          <a href="/setup" className="flex items-center gap-2 text-cyan-400 hover:text-cyan-300">
            <Settings className="h-4 w-4" /> Setup Wizard
          </a>
          <a href="/workers" className="flex items-center gap-2 text-cyan-400 hover:text-cyan-300">
            <Users className="h-4 w-4" /> Workers
          </a>
          <a href="/monitoring" className="flex items-center gap-2 text-cyan-400 hover:text-cyan-300">
            <Play className="h-4 w-4" /> Live Monitoring
          </a>
          <a href="/reports" className="flex items-center gap-2 text-cyan-400 hover:text-cyan-300">
            <FileText className="h-4 w-4" /> Reports
          </a>
          <a href="/system-health" className="flex items-center gap-2 text-cyan-400 hover:text-cyan-300">
            <Shield className="h-4 w-4" /> System Health
          </a>
        </div>
      </div>
    </div>
  );
}
