import { useState, useEffect } from 'react';
import { Link } from 'react-router';
import {
  CheckCircle, XCircle, AlertTriangle, RefreshCw, Clock,
  Server, Database, Globe, Cpu, Shield
} from 'lucide-react';
import Logo from '../components/common/Logo';

interface ServiceStatus {
  name: string;
  status: 'operational' | 'degraded' | 'down' | 'unknown';
  latency: number | null;
  lastCheck: string;
  details?: string;
}

export default function StatusPage() {
  const [services, setServices] = useState<ServiceStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<string>('');

  const checkServices = async () => {
    const now = new Date().toLocaleTimeString();
    const results: ServiceStatus[] = [];

    // Check Backend API
    try {
      const start = Date.now();
      const res = await fetch('/health', { signal: AbortSignal.timeout(5000) });
      const latency = Date.now() - start;
      results.push({
        name: 'Backend API',
        status: res.ok ? 'operational' : 'degraded',
        latency,
        lastCheck: now,
        details: res.ok ? 'All systems normal' : 'Health check returned error',
      });
    } catch {
      results.push({
        name: 'Backend API',
        status: 'down',
        latency: null,
        lastCheck: now,
        details: 'Could not reach backend',
      });
    }

    // Check Cloud Core
    try {
      const start = Date.now();
      const res = await fetch('/cloud-api/cloud/health', { signal: AbortSignal.timeout(5000) });
      const latency = Date.now() - start;
      results.push({
        name: 'YOLO Cloud Core',
        status: res.ok ? 'operational' : 'degraded',
        latency,
        lastCheck: now,
        details: res.ok ? 'YOLOv8-pose engine running' : 'Health check returned error',
      });
    } catch {
      results.push({
        name: 'YOLO Cloud Core',
        status: 'down',
        latency: null,
        lastCheck: now,
        details: 'Could not reach cloud core',
      });
    }

    // Check Frontend
    results.push({
      name: 'Web Dashboard',
      status: 'operational',
      latency: 0,
      lastCheck: now,
      details: 'This page is loading — dashboard is operational',
    });

    // Check Database
    try {
      const res = await fetch('/api/settings', { signal: AbortSignal.timeout(5000) });
      results.push({
        name: 'Database',
        status: res.ok ? 'operational' : 'degraded',
        latency: null,
        lastCheck: now,
        details: res.ok ? 'Connected' : 'Connection issue',
      });
    } catch {
      results.push({
        name: 'Database',
        status: 'unknown',
        latency: null,
        lastCheck: now,
        details: 'Could not verify',
      });
    }

    setServices(results);
    setLastUpdated(now);
    setLoading(false);
  };

  useEffect(() => {
    checkServices();
    const interval = setInterval(checkServices, 30000);
    return () => clearInterval(interval);
  }, []);

  const overallStatus = services.every(s => s.status === 'operational')
    ? 'operational'
    : services.some(s => s.status === 'down')
      ? 'down'
      : 'degraded';

  const statusColors = {
    operational: 'text-green-400',
    degraded: 'text-amber-400',
    down: 'text-red-400',
    unknown: 'text-slate-400',
  };

  const statusBg = {
    operational: 'bg-green-500/10 border-green-500/20',
    degraded: 'bg-amber-500/10 border-amber-500/20',
    down: 'bg-red-500/10 border-red-500/20',
    unknown: 'bg-slate-500/10 border-slate-500/20',
  };

  const StatusIcon = ({ status }: { status: string }) => {
    switch (status) {
      case 'operational': return <CheckCircle className="w-5 h-5 text-green-400" />;
      case 'degraded': return <AlertTriangle className="w-5 h-5 text-amber-400" />;
      case 'down': return <XCircle className="w-5 h-5 text-red-400" />;
      default: return <Clock className="w-5 h-5 text-slate-400" />;
    }
  };

  return (
    <div className="min-h-screen bg-[#0b0f14] text-white">
      {/* Header */}
      <nav className="border-b border-white/5 bg-[#0b0f14]/80 backdrop-blur-xl">
        <div className="max-w-4xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3">
            <Logo className="h-8 w-auto" variant="light" />
          </Link>
          <span className="text-xs text-slate-500">System Status</span>
        </div>
      </nav>

      <div className="max-w-4xl mx-auto px-6 py-12">
        {/* Overall Status */}
        <div className={`rounded-2xl border p-8 mb-8 ${statusBg[overallStatus]}`}>
          <div className="flex items-center gap-4">
            <StatusIcon status={overallStatus} />
            <div>
              <h1 className="text-2xl font-bold text-white">
                {overallStatus === 'operational' ? 'All Systems Operational' :
                 overallStatus === 'degraded' ? 'Partial System Degradation' :
                 'System Outage'}
              </h1>
              <p className="text-sm text-slate-400 mt-1">
                Last updated: {lastUpdated || 'Checking...'}
              </p>
            </div>
          </div>
        </div>

        {/* Services */}
        <div className="space-y-3">
          <h2 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-4">Services</h2>
          {loading ? (
            <div className="text-center py-8">
              <RefreshCw className="w-6 h-6 text-slate-500 animate-spin mx-auto" />
              <p className="text-sm text-slate-500 mt-2">Checking services...</p>
            </div>
          ) : (
            services.map((service) => (
              <div
                key={service.name}
                className="flex items-center justify-between p-4 rounded-xl bg-white/[0.02] border border-white/5 hover:border-white/10 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <StatusIcon status={service.status} />
                  <div>
                    <h3 className="text-sm font-medium text-white">{service.name}</h3>
                    <p className="text-xs text-slate-500">{service.details}</p>
                  </div>
                </div>
                <div className="text-right">
                  <span className={`text-xs font-medium ${statusColors[service.status]}`}>
                    {service.status === 'operational' ? 'Operational' :
                     service.status === 'degraded' ? 'Degraded' :
                     service.status === 'down' ? 'Down' : 'Unknown'}
                  </span>
                  {service.latency !== null && service.latency > 0 && (
                    <p className="text-[10px] text-slate-600 mt-0.5">{service.latency}ms</p>
                  )}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Refresh */}
        <div className="text-center mt-8">
          <button
            onClick={() => { setLoading(true); checkServices(); }}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-white/5 border border-white/10 text-sm text-slate-400 hover:text-white hover:border-white/20 transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh Status
          </button>
        </div>

        {/* Footer */}
        <div className="mt-12 pt-8 border-t border-white/5 text-center">
          <p className="text-xs text-slate-600">
            Powered by ErgoVigilance • <Link to="/" className="text-slate-500 hover:text-white">Back to Dashboard</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
