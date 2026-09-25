import { useState } from 'react';
import {
  Book, Key, Shield, Clock, AlertTriangle, ChevronRight, ChevronDown,
  Copy, Check, ExternalLink, Server, Zap, Code,
} from 'lucide-react';

/* ── Types ────────────────────────────────────────────────────────── */

type HttpMethod = 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH' | 'WS';

interface Endpoint {
  method: HttpMethod;
  path: string;
  description: string;
  auth?: boolean;
  tags?: string[];
  request?: string;
  response?: string;
}

interface EndpointGroup {
  name: string;
  description: string;
  icon: typeof Server;
  endpoints: Endpoint[];
}

/* ── Endpoint Data ────────────────────────────────────────────────── */

const ENDPOINT_GROUPS: EndpointGroup[] = [
  {
    name: 'Authentication',
    description: 'Login, demo mode, and token management',
    icon: Key,
    endpoints: [
      { method: 'POST', path: '/api/auth/login', description: 'Login with email + password. Returns JWT token.', auth: false, request: '{"email": "user@example.com", "password": "..." }', response: '{"token": "eyJ...", "user": {"id": 1, "email": "...", "role": "operator"}}' },
      { method: 'POST', path: '/api/auth/demo', description: 'Start demo mode with synthetic data. No credentials required.', auth: false, response: '{"token": "demo-...", "user": {"id": 0, "email": "demo@ergovigilance.com", "role": "supervisor"}}' },
    ],
  },
  {
    name: 'Dashboard',
    description: 'Real-time risk scores, session analytics, and worker status',
    icon: Zap,
    endpoints: [
      { method: 'GET', path: '/api/dashboard', description: 'Current risk score, session info, ergonomic features, issues, and trend analysis.' },
      { method: 'GET', path: '/api/dashboard/supervisor', description: 'Supervisor summary: worker count, sessions today, open alerts, average risk.' },
      { method: 'GET', path: '/api/dashboard/admin', description: 'Admin summary: total users, sessions, system health, role distribution.' },
    ],
  },
  {
    name: 'Live Monitoring',
    description: 'Session control, camera feeds, and real-time analysis',
    icon: Server,
    endpoints: [
      { method: 'POST', path: '/api/session/start', description: 'Start a live monitoring session with a camera.' },
      { method: 'POST', path: '/api/session/stop', description: 'Stop the current monitoring session and save results.' },
      { method: 'GET', path: '/api/context/snapshot', description: 'Current context-aware risk: fatigue, exposure, RULA/REBA scores.' },
      { method: 'GET', path: '/api/recommendations', description: 'AI-generated corrective action suggestions based on current posture.' },
      { method: 'GET', path: '/api/alerts/history', description: 'Recent alerts with severity, title, and frame number.' },
      { method: 'GET', path: '/api/live-timeline', description: 'Frame-by-frame timeline data for the current session.' },
    ],
  },
  {
    name: 'Sessions & Reports',
    description: 'Session history, PDF reports, CSV exports, and evidence packages',
    icon: Book,
    endpoints: [
      { method: 'GET', path: '/api/sessions', description: 'List all recorded sessions with metadata.' },
      { method: 'GET', path: '/api/sessions/{id}', description: 'Detailed session data: averages, issues, timeline.' },
      { method: 'GET', path: '/api/reports/pdf/{sessionId}', description: 'Generate PDF report for a session (Playwright-rendered).' },
      { method: 'GET', path: '/api/reports/csv/{sessionId}', description: 'Export session data as CSV.' },
      { method: 'GET', path: '/api/evidence/{sessionId}', description: 'Download evidence package (ZIP) with video, frames, report.' },
      { method: 'GET', path: '/api/reports/risk-trend', description: 'Cross-session risk trend analysis.' },
      { method: 'GET', path: '/api/reports/safety', description: 'Safety report with issue frequency, worker stats.' },
    ],
  },
  {
    name: 'Workers & Users',
    description: 'Worker profiles, face enrollment, user management',
    icon: Shield,
    endpoints: [
      { method: 'GET', path: '/api/workers', description: 'List all registered workers.' },
      { method: 'POST', path: '/api/workers', description: 'Register a new worker.' },
      { method: 'GET', path: '/api/users', description: 'List all system users (admin only).' },
      { method: 'POST', path: '/api/users', description: 'Create a new user account (admin only).' },
      { method: 'GET', path: '/api/worker-summary/{userId}', description: 'Worker self-view: personal risk data and session history.' },
    ],
  },
  {
    name: 'System',
    description: 'Health checks, deployment metrics, and configuration',
    icon: AlertTriangle,
    endpoints: [
      { method: 'GET', path: '/health', description: 'Health check (no auth required). Returns DB, model, and session status.', auth: false },
      { method: 'GET', path: '/api/deployment', description: 'Deployment metrics: disk usage, session count, camera status.' },
      { method: 'GET', path: '/api/settings', description: 'User settings (alert threshold, preferences).' },
      { method: 'PUT', path: '/api/settings', description: 'Update user settings.' },
      { method: 'GET', path: '/api/demo-mode', description: 'Check if demo mode is active.', auth: false },
    ],
  },
];

/* ── Rate Limits ──────────────────────────────────────────────────── */

const RATE_LIMITS = [
  { category: 'General API', limit: '100 requests/min', window: 'Per IP address' },
  { category: 'Authentication', limit: '10 attempts/min', window: 'Per IP address, /auth/login + /auth/demo' },
  { category: 'WebSocket', limit: '1 connection/user', window: 'Persistent connection for live data' },
  { category: 'File Upload', limit: '10 MB max', window: 'Per request (video, images)' },
];

const ERROR_CODES = [
  { code: 200, meaning: 'Success', description: 'Request completed successfully' },
  { code: 400, meaning: 'Bad Request', description: 'Invalid request body or parameters' },
  { code: 401, meaning: 'Unauthorized', description: 'Missing or expired JWT token' },
  { code: 403, meaning: 'Forbidden', description: 'Insufficient permissions for this role' },
  { code: 404, meaning: 'Not Found', description: 'Resource does not exist' },
  { code: 429, meaning: 'Rate Limited', description: 'Too many requests — slow down' },
  { code: 500, meaning: 'Server Error', description: 'Internal error (check backend logs)' },
  { code: 503, meaning: 'Unavailable', description: 'Service temporarily unavailable (model not loaded)' },
];

/* ── Copy Button ──────────────────────────────────────────────────── */

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <button onClick={handleCopy} className="text-slate-500 hover:text-white transition-colors" title="Copy">
      {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
    </button>
  );
}

/* ── Method Badge ─────────────────────────────────────────────────── */

function MethodBadge({ method }: { method: HttpMethod }) {
  const colors: Record<HttpMethod, string> = {
    GET: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    POST: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
    PUT: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    DELETE: 'bg-red-500/15 text-red-400 border-red-500/30',
    PATCH: 'bg-purple-500/15 text-purple-400 border-purple-500/30',
    WS: 'bg-cyan-500/15 text-cyan-400 border-cyan-500/30',
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border ${colors[method]}`}>
      {method}
    </span>
  );
}

/* ── Collapsible Endpoint Group ───────────────────────────────────── */

function EndpointGroupCard({ group }: { group: EndpointGroup }) {
  const [expanded, setExpanded] = useState(false);
  const Icon = group.icon;

  return (
    <div className="border border-white/5 rounded-xl overflow-hidden bg-white/[0.02] hover:bg-white/[0.04] transition-colors">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-5 py-4 text-left"
      >
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center">
            <Icon className="w-4 h-4 text-blue-400" />
          </div>
          <div>
            <p className="text-sm font-bold text-white">{group.name}</p>
            <p className="text-xs text-slate-500">{group.description}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-600">{group.endpoints.length} endpoints</span>
          <ChevronDown className={`w-4 h-4 text-slate-500 transition-transform ${expanded ? 'rotate-180' : ''}`} />
        </div>
      </button>

      {expanded && (
        <div className="border-t border-white/5">
          {group.endpoints.map((ep) => (
            <div key={`${ep.method}-${ep.path}`} className="px-5 py-4 border-b border-white/5 last:border-0 hover:bg-white/[0.02]">
              <div className="flex items-start gap-3">
                <MethodBadge method={ep.method} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <code className="text-sm font-mono text-cyan-300">{ep.path}</code>
                    {!ep.auth && (
                      <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">No auth</span>
                    )}
                  </div>
                  <p className="text-xs text-slate-400 mt-1">{ep.description}</p>

                  {/* Request example */}
                  {ep.request && (
                    <div className="mt-3">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[10px] text-slate-500 uppercase tracking-wider">Request</span>
                        <CopyButton text={ep.request} />
                      </div>
                      <pre className="bg-black/40 rounded-lg p-3 text-xs text-slate-300 font-mono overflow-x-auto border border-white/5">
                        {ep.request}
                      </pre>
                    </div>
                  )}

                  {/* Response example */}
                  {ep.response && (
                    <div className="mt-3">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[10px] text-slate-500 uppercase tracking-wider">Response</span>
                        <CopyButton text={ep.response} />
                      </div>
                      <pre className="bg-black/40 rounded-lg p-3 text-xs text-slate-300 font-mono overflow-x-auto border border-white/5">
                        {ep.response}
                      </pre>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── Main Page ────────────────────────────────────────────────────── */

export default function ApiDocsPage() {
  const [activeTab, setActiveTab] = useState<'endpoints' | 'auth' | 'limits'>('endpoints');

  return (
    <div className="p-lg space-y-lg pb-32 max-w-5xl">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3 mb-2">
          <Code className="w-6 h-6 text-blue-400" />
          <h1 className="text-display-lg font-bold text-on-surface">API Reference</h1>
        </div>
        <p className="text-body-sm text-on-surface-variant mt-xs">
          Complete REST API documentation for ErgoVigilance. Use these endpoints to integrate with your factory systems.
        </p>
        <div className="flex items-center gap-4 mt-4">
          <a
            href="/docs"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 text-sm font-bold text-white hover:bg-blue-500 transition-all"
          >
            <ExternalLink className="w-3.5 h-3.5" />
            Interactive Swagger UI
          </a>
          <a
            href="/openapi.json"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-white/10 text-sm text-slate-400 hover:text-white hover:border-white/20 transition-all"
          >
            <ExternalLink className="w-3.5 h-3.5" />
            OpenAPI Spec (JSON)
          </a>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-white/5">
        {[
          { id: 'endpoints' as const, label: 'Endpoints', icon: Server },
          { id: 'auth' as const, label: 'Authentication', icon: Key },
          { id: 'limits' as const, label: 'Rate Limits & Errors', icon: Shield },
        ].map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium transition-colors border-b-2 ${
              activeTab === id
                ? 'border-blue-500 text-blue-400'
                : 'border-transparent text-slate-500 hover:text-slate-300'
            }`}
          >
            <Icon className="w-4 h-4" />
            {label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === 'endpoints' && (
        <div className="space-y-3">
          {ENDPOINT_GROUPS.map((group) => (
            <EndpointGroupCard key={group.name} group={group} />
          ))}
        </div>
      )}

      {activeTab === 'auth' && (
        <div className="space-y-6">
          <div className="bg-white/[0.03] border border-white/10 rounded-xl p-6 space-y-4">
            <h3 className="text-lg font-bold text-white">JWT Authentication</h3>
            <p className="text-sm text-slate-400 leading-relaxed">
              All API endpoints (except health checks) require a valid JWT token in the <code className="bg-black/40 px-1.5 py-0.5 rounded text-cyan-300 text-xs">Authorization</code> header.
            </p>
            <div className="space-y-3">
              <div>
                <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">Login</p>
                <pre className="bg-black/40 rounded-lg p-3 text-xs text-slate-300 font-mono border border-white/5">
{`curl -X POST http://localhost:8000/api/auth/login \\
  -H "Content-Type: application/json" \\
  -d '{"email": "admin@example.local", "password": "AdminPass123!"}'`}
                </pre>
              </div>
              <div>
                <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">Using the Token</p>
                <pre className="bg-black/40 rounded-lg p-3 text-xs text-slate-300 font-mono border border-white/5">
{`curl http://localhost:8000/api/dashboard \\
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."`}
                </pre>
              </div>
              <div>
                <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">Demo Mode (No Auth)</p>
                <pre className="bg-black/40 rounded-lg p-3 text-xs text-slate-300 font-mono border border-white/5">
{`curl -X POST http://localhost:8000/api/auth/demo`}
                </pre>
              </div>
            </div>
          </div>

          <div className="bg-white/[0.03] border border-white/10 rounded-xl p-6 space-y-4">
            <h3 className="text-lg font-bold text-white">User Roles</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {[
                { role: 'operator', access: 'Own data, monitoring, self-view' },
                { role: 'supervisor', access: 'Team data, alerts, reports' },
                { role: 'safety_mgr', access: 'All sessions, audit, manager dashboard' },
                { role: 'admin', access: 'Full access: users, settings, deployment' },
              ].map(({ role, access }) => (
                <div key={role} className="p-3 rounded-lg bg-white/[0.03] border border-white/5">
                  <p className="text-xs font-bold text-blue-400 uppercase tracking-wider">{role}</p>
                  <p className="text-xs text-slate-500 mt-1">{access}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {activeTab === 'limits' && (
        <div className="space-y-6">
          <div className="bg-white/[0.03] border border-white/10 rounded-xl p-6 space-y-4">
            <h3 className="text-lg font-bold text-white">Rate Limits</h3>
            <p className="text-sm text-slate-400">
              Rate limits are enforced per IP address. Exceeding the limit returns HTTP 429.
            </p>
            <div className="space-y-2">
              {RATE_LIMITS.map(({ category, limit, window }) => (
                <div key={category} className="flex items-center justify-between p-3 rounded-lg bg-white/[0.03] border border-white/5">
                  <span className="text-sm text-slate-300">{category}</span>
                  <div className="text-right">
                    <span className="text-sm font-mono text-cyan-300">{limit}</span>
                    <p className="text-[10px] text-slate-500">{window}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-white/[0.03] border border-white/10 rounded-xl p-6 space-y-4">
            <h3 className="text-lg font-bold text-white">HTTP Error Codes</h3>
            <div className="space-y-2">
              {ERROR_CODES.map(({ code, meaning, description }) => (
                <div key={code} className="flex items-center gap-4 p-3 rounded-lg bg-white/[0.03] border border-white/5">
                  <span className={`text-sm font-mono font-bold ${
                    code < 400 ? 'text-emerald-400' : code < 500 ? 'text-amber-400' : 'text-red-400'
                  }`}>{code}</span>
                  <span className="text-sm text-white font-medium w-28">{meaning}</span>
                  <span className="text-xs text-slate-500">{description}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-white/[0.03] border border-white/10 rounded-xl p-6 space-y-4">
            <h3 className="text-lg font-bold text-white">WebSocket Connection</h3>
            <p className="text-sm text-slate-400 leading-relaxed">
              Real-time data is available via WebSocket at <code className="bg-black/40 px-1.5 py-0.5 rounded text-cyan-300 text-xs">ws://localhost:8000/ws/dashboard</code>. 
              Connect with a valid JWT token as a query parameter.
            </p>
            <pre className="bg-black/40 rounded-lg p-3 text-xs text-slate-300 font-mono border border-white/5">
{`const ws = new WebSocket(
  'ws://localhost:8000/ws/dashboard?token=YOUR_JWT_TOKEN'
);

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // data.risk_score, data.alerts, data.session, etc.
};`}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
