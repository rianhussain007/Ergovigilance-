import { useState } from 'react';
import { Link } from 'react-router';
import { 
  ArrowLeft, Server, Database, Camera, Cloud, Brain, Shield, 
  Monitor, Wifi, Cpu, HardDrive, Network, ArrowRight,
  ChevronDown, ChevronUp, ExternalLink
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';

interface ArchitectureNode {
  id: string;
  label: string;
  sublabel: string;
  icon: typeof Server;
  color: string;
  borderColor: string;
  details: string[];
}

const CORE_NODES: ArchitectureNode[] = [
  {
    id: 'frontend',
    label: 'Frontend',
    sublabel: 'React 19 + Vite 6',
    icon: Monitor,
    color: 'bg-blue-500/10',
    borderColor: 'border-blue-500/30',
    details: [
      '34 pages with lazy loading',
      'i18n: English, Hindi, Chinese',
      'PWA installable on tablets',
      'Real-time WebSocket updates',
      'Animated risk gauge',
      'Keyboard shortcuts (Ctrl+K search)',
    ],
  },
  {
    id: 'backend',
    label: 'Backend API',
    sublabel: 'FastAPI + Python 3.12',
    icon: Server,
    color: 'bg-emerald-500/10',
    borderColor: 'border-emerald-500/30',
    details: [
      '92 REST endpoints',
      'JWT auth with 4 roles',
      'Stripe billing integration',
      'SQLite + PostgreSQL',
      'Health endpoints (/healthz, /readyz, /metrics)',
      'Versioned schema migrations',
    ],
  },
  {
    id: 'ai-core',
    label: 'AI Core',
    sublabel: 'MediaPipe + RULA/REBA',
    icon: Brain,
    color: 'bg-purple-500/10',
    borderColor: 'border-purple-500/30',
    details: [
      '33-point pose estimation',
      '7-feature extraction',
      'Context intelligence engine',
      'Task recognition (7 classes)',
      'Alert engine with escalation',
      'Recommendation engine',
      'Fatigue & exposure models',
      'Worker identity (SFace + YOLO)',
      'Anti-spoof liveness detection',
    ],
  },
  {
    id: 'cloud-core',
    label: 'YOLO Cloud Core',
    sublabel: 'YOLOv8-pose + RTSP',
    icon: Cloud,
    color: 'bg-cyan-500/10',
    borderColor: 'border-cyan-500/30',
    details: [
      'Multi-camera RTSP ingestion',
      'Tenant-isolated storage',
      'PostgreSQL persistent storage',
      'API key authentication',
      'Webhook delivery (HMAC-SHA256)',
      'Email/Slack notifications',
      'Data retention policies',
      'Live frame snapshots',
      'GPU acceleration (optional)',
    ],
  },
];

const DATA_FLOWS = [
  { from: 'frontend', to: 'backend', label: 'HTTP/WebSocket', protocol: 'REST API + WS' },
  { from: 'frontend', to: 'cloud-core', label: '/cloud-api/', protocol: 'REST API' },
  { from: 'backend', to: 'ai-core', label: 'In-process', protocol: 'Python calls' },
  { from: 'ai-core', to: 'backend', label: 'Results', protocol: 'Pose data + alerts' },
  { from: 'cloud-core', to: 'frontend', label: 'Frame snapshots', protocol: 'JPEG' },
];

const STORAGE = [
  { name: 'SQLite', purpose: 'Sessions, alerts, audit trail', icon: Database },
  { name: 'PostgreSQL', purpose: 'Cloud sessions, cameras, API keys', icon: Database },
  { name: 'File System', purpose: 'Recordings, exports, evidence packages', icon: HardDrive },
  { name: 'Models', purpose: 'YOLO weights, face recognition, task classifier', icon: Cpu },
];

export default function ArchitecturePage() {
  const [expandedNode, setExpandedNode] = useState<string | null>(null);

  return (
    <div className="p-lg space-y-lg pb-32 max-w-6xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-display-lg font-bold text-on-surface">System Architecture</h1>
          <p className="text-body-sm text-on-surface-variant mt-xs">Dual-core design for on-premise + cloud deployment</p>
        </div>
        <Link 
          to="/system-health" 
          className="flex items-center gap-sm text-body-sm text-on-surface-variant hover:text-on-surface transition-colors"
        >
          <ArrowLeft className="w-4 h-4" /> System Health
        </Link>
      </div>

      {/* Architecture Overview */}
      <section className="bg-surface-container border border-outline-variant rounded-2xl p-lg shadow-sm">
        <div className="flex items-center gap-sm mb-md">
          <Network className="w-5 h-5 text-primary" />
          <h2 className="text-title-sm font-bold text-on-surface">Dual-Core Architecture</h2>
        </div>
        <p className="text-body-sm text-on-surface-variant mb-6">
          ErgoVigilance uses two independent processing cores — an on-premise MediaPipe engine for local webcam monitoring, 
          and a cloud YOLO engine for factory CCTV integration. Both share the same frontend dashboard.
        </p>

        {/* Architecture Diagram */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {CORE_NODES.map((node) => (
            <motion.div
              key={node.id}
              className={`relative border ${node.borderColor} ${node.color} rounded-xl p-4 cursor-pointer hover:shadow-md transition-shadow`}
              onClick={() => setExpandedNode(expandedNode === node.id ? null : node.id)}
              whileHover={{ scale: 1.02 }}
            >
              <div className="flex items-center gap-3 mb-3">
                <div className="w-10 h-10 rounded-lg bg-white/50 dark:bg-black/20 flex items-center justify-center">
                  <node.icon className="w-5 h-5 text-on-surface" />
                </div>
                <div>
                  <h3 className="text-body-md font-bold text-on-surface">{node.label}</h3>
                  <p className="text-[10px] text-on-surface-variant">{node.sublabel}</p>
                </div>
              </div>

              <AnimatePresence>
                {expandedNode === node.id && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="overflow-hidden"
                  >
                    <ul className="space-y-1 mt-2 pt-2 border-t border-outline-variant/50">
                      {node.details.map((detail) => (
                        <li key={detail} className="text-[10px] text-on-surface-variant flex items-start gap-1.5">
                          <span className="text-primary mt-0.5">•</span>
                          {detail}
                        </li>
                      ))}
                    </ul>
                  </motion.div>
                )}
              </AnimatePresence>

              <div className="flex items-center justify-end mt-2">
                {expandedNode === node.id ? (
                  <ChevronUp className="w-3 h-3 text-on-surface-variant" />
                ) : (
                  <ChevronDown className="w-3 h-3 text-on-surface-variant" />
                )}
              </div>
            </motion.div>
          ))}
        </div>

        {/* Data Flow Arrows */}
        <div className="mt-6 pt-4 border-t border-outline-variant/50">
          <h3 className="text-body-sm font-bold text-on-surface mb-3">Data Flow</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
            {DATA_FLOWS.map((flow) => (
              <div key={`${flow.from}-${flow.to}`} className="flex items-center gap-2 text-[10px] text-on-surface-variant bg-surface-container-high rounded-lg px-3 py-2">
                <span className="font-mono text-primary">{flow.from}</span>
                <ArrowRight className="w-3 h-3 text-on-surface-variant" />
                <span className="font-mono text-primary">{flow.to}</span>
                <span className="ml-auto text-on-surface-variant/60">{flow.protocol}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Storage Layer */}
      <section className="bg-surface-container border border-outline-variant rounded-2xl p-lg shadow-sm">
        <div className="flex items-center gap-sm mb-md">
          <HardDrive className="w-5 h-5 text-primary" />
          <h2 className="text-title-sm font-bold text-on-surface">Storage Layer</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {STORAGE.map((store) => (
            <div key={store.name} className="bg-surface-container-high rounded-xl p-4 border border-outline-variant/50">
              <div className="flex items-center gap-2 mb-2">
                <store.icon className="w-4 h-4 text-primary" />
                <h3 className="text-body-sm font-bold text-on-surface">{store.name}</h3>
              </div>
              <p className="text-[10px] text-on-surface-variant">{store.purpose}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Deployment Options */}
      <section className="bg-surface-container border border-outline-variant rounded-2xl p-lg shadow-sm">
        <div className="flex items-center gap-sm mb-md">
          <Shield className="w-5 h-5 text-primary" />
          <h2 className="text-title-sm font-bold text-on-surface">Deployment Options</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-surface-container-high rounded-xl p-4 border border-outline-variant/50">
            <h3 className="text-body-md font-bold text-on-surface mb-2">On-Premise</h3>
            <ul className="space-y-1 text-[10px] text-on-surface-variant">
              <li>• Docker Compose deployment</li>
              <li>• Windows Service (NSSM)</li>
              <li>• SQLite or PostgreSQL</li>
              <li>• Local webcam monitoring</li>
              <li>• No internet required</li>
            </ul>
          </div>
          <div className="bg-surface-container-high rounded-xl p-4 border border-cyan-500/30">
            <h3 className="text-body-md font-bold text-on-surface mb-2">Cloud (YOLO)</h3>
            <ul className="space-y-1 text-[10px] text-on-surface-variant">
              <li>• RTSP camera ingestion</li>
              <li>• PostgreSQL persistent storage</li>
              <li>• API key authentication</li>
              <li>• Multi-tenant isolation</li>
              <li>• GPU acceleration available</li>
            </ul>
          </div>
          <div className="bg-surface-container-high rounded-xl p-4 border border-outline-variant/50">
            <h3 className="text-body-md font-bold text-on-surface mb-2">Hybrid</h3>
            <ul className="space-y-1 text-[10px] text-on-surface-variant">
              <li>• Both cores active simultaneously</li>
              <li>• Shared frontend dashboard</li>
              <li>• Unified alert system</li>
              <li>• Camera-level routing</li>
              <li>• Best of both worlds</li>
            </ul>
          </div>
        </div>
      </section>

      {/* Security */}
      <section className="bg-surface-container border border-outline-variant rounded-2xl p-lg shadow-sm">
        <div className="flex items-center gap-sm mb-md">
          <Shield className="w-5 h-5 text-primary" />
          <h2 className="text-title-sm font-bold text-on-surface">Security & Privacy</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-body-sm">
          <div className="space-y-2">
            <h3 className="font-bold text-on-surface">Data Protection</h3>
            <ul className="space-y-1 text-[10px] text-on-surface-variant">
              <li>• Video never leaves your building (on-premise mode)</li>
              <li>• GDPR-compliant consent workflow</li>
              <li>• Per-worker right-to-erasure</li>
              <li>• Encrypted JWT tokens</li>
              <li>• HMAC-SHA256 webhook signing</li>
            </ul>
          </div>
          <div className="space-y-2">
            <h3 className="font-bold text-on-surface">Access Control</h3>
            <ul className="space-y-1 text-[10px] text-on-surface-variant">
              <li>• 4 roles: Operator, Supervisor, Safety Manager, Admin</li>
              <li>• API key authentication for cloud core</li>
              <li>• Rate limiting on login endpoints</li>
              <li>• Audit trail for all admin actions</li>
              <li>• Worker identity with face recognition</li>
            </ul>
          </div>
        </div>
      </section>

      {/* Tech Stack */}
      <section className="bg-surface-container border border-outline-variant rounded-2xl p-lg shadow-sm">
        <div className="flex items-center gap-sm mb-md">
          <Cpu className="w-5 h-5 text-primary" />
          <h2 className="text-title-sm font-bold text-on-surface">Technology Stack</h2>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-body-sm">
          <div>
            <h3 className="font-bold text-on-surface mb-1">Frontend</h3>
            <ul className="space-y-0.5 text-[10px] text-on-surface-variant">
              <li>React 19</li>
              <li>Vite 6</li>
              <li>TypeScript</li>
              <li>Tailwind CSS</li>
              <li>Framer Motion</li>
            </ul>
          </div>
          <div>
            <h3 className="font-bold text-on-surface mb-1">Backend</h3>
            <ul className="space-y-0.5 text-[10px] text-on-surface-variant">
              <li>FastAPI</li>
              <li>Python 3.12</li>
              <li>MediaPipe</li>
              <li>SQLite / PostgreSQL</li>
              <li>Uvicorn</li>
            </ul>
          </div>
          <div>
            <h3 className="font-bold text-on-surface mb-1">ML/CV</h3>
            <ul className="space-y-0.5 text-[10px] text-on-surface-variant">
              <li>YOLOv8-pose</li>
              <li>MediaPipe Pose</li>
              <li>OpenCV</li>
              <li>scikit-learn</li>
              <li>InsightFace (SFace)</li>
            </ul>
          </div>
          <div>
            <h3 className="font-bold text-on-surface mb-1">Infrastructure</h3>
            <ul className="space-y-0.5 text-[10px] text-on-surface-variant">
              <li>Docker / Docker Compose</li>
              <li>Nginx reverse proxy</li>
              <li>GitHub Actions CI</li>
              <li>Windows Service (NSSM)</li>
              <li>Prometheus metrics</li>
            </ul>
          </div>
        </div>
      </section>
    </div>
  );
}
