import { useState, useEffect, useCallback } from 'react';
import { Shield, Check, X, Clock, FileText, Download, Users, AlertTriangle, Eye, EyeOff, Trash2 } from 'lucide-react';
import { useAuth } from '@/src/auth/AuthContext';
import { apiFetch } from '@/src/services/apiClient';
import { EmptyState, SectionHeader, LoadingCard } from '@/src/components/common';
import { useToast } from '@/src/hooks/useToast';

interface WorkerConsent {
  worker_id: string;
  name: string;
  department: string;
  consent_status: 'granted' | 'denied' | 'pending' | 'withdrawn';
  consent_date: string | null;
  consent_expiry: string | null;
  consent_version: string;
  purpose: string;
  data_categories: string[];
  retention_days: number;
  withdrawal_date: string | null;
  consent_proof: string | null;
}

interface ConsentPolicy {
  version: string;
  title: string;
  description: string;
  purposes: string[];
  data_categories: string[];
  retention_days: number;
  rights: string[];
  last_updated: string;
}

const CONSENT_PURPOSES = [
  'Ergonomic posture risk assessment',
  'Workplace safety monitoring',
  'Incident investigation and prevention',
  'Regulatory compliance reporting',
  'Worker health and wellness analytics',
];

const DATA_CATEGORIES = [
  'Body pose keypoints (2D)',
  'Posture risk scores (estimated)',
  'Session metadata (timestamps, duration)',
  'Worker identification (employee ID)',
  'Alert history (risk events)',
];

const WORKER_RIGHTS = [
  'Right to access your monitoring data',
  'Right to withdraw consent at any time',
  'Right to request data deletion',
  'Right to data portability (export)',
  'Right to be informed about processing',
  'Right to object to automated decisions',
];

export default function ConsentPage() {
  const { user } = useAuth();
  const { addToast } = useToast();
  const [workers, setWorkers] = useState<WorkerConsent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [policy, setPolicy] = useState<ConsentPolicy | null>(null);
  const [showPolicy, setShowPolicy] = useState(false);
  const [filter, setFilter] = useState<string>('all');
  const [bulkAction, setBulkAction] = useState<string | null>(null);

  const fetchConsents = useCallback(async () => {
    try {
      setLoading(true);
      const res = await apiFetch('/api/consent/worker-consents');
      if (!res.ok) throw new Error('Failed to load consent data');
      const data = await res.json();
      setWorkers(data.workers ?? []);
      setPolicy(data.policy ?? null);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load consent data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchConsents();
  }, [fetchConsents]);

  const handleGrantConsent = async (workerId: string) => {
    try {
      const res = await apiFetch(`/api/consent/worker-consents/${workerId}/grant`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          purposes: CONSENT_PURPOSES,
          data_categories: DATA_CATEGORIES,
        }),
      });
      if (!res.ok) throw new Error('Failed to grant consent');
      addToast('success', 'Consent Granted', 'Worker consent has been recorded.');
      fetchConsents();
    } catch (err) {
      addToast('error', 'Error', err instanceof Error ? err.message : 'Could not grant consent.');
    }
  };

  const handleDenyConsent = async (workerId: string) => {
    try {
      const res = await apiFetch(`/api/consent/worker-consents/${workerId}/deny`, {
        method: 'POST',
      });
      if (!res.ok) throw new Error('Failed to deny consent');
      addToast('success', 'Consent Denied', 'Worker has been marked as not consenting.');
      fetchConsents();
    } catch (err) {
      addToast('error', 'Error', err instanceof Error ? err.message : 'Could not deny consent.');
    }
  };

  const handleWithdrawConsent = async (workerId: string) => {
    if (!confirm('Are you sure? This will stop monitoring for this worker and delete their session data after retention period.')) return;
    try {
      const res = await apiFetch(`/api/consent/worker-consents/${workerId}/withdraw`, {
        method: 'POST',
      });
      if (!res.ok) throw new Error('Failed to withdraw consent');
      addToast('success', 'Consent Withdrawn', 'Worker consent has been withdrawn. Data will be purged after retention period.');
      fetchConsents();
    } catch (err) {
      addToast('error', 'Error', err instanceof Error ? err.message : 'Could not withdraw consent.');
    }
  };

  const handleExportConsent = () => {
    const csv = ['Worker ID,Name,Department,Status,Consent Date,Expiry,Version,Purpose,Retention Days'];
    for (const w of workers) {
      csv.push([
        w.worker_id, w.name, w.department, w.consent_status,
        w.consent_date ?? '', w.consent_expiry ?? '', w.consent_version,
        `"${w.purpose}"`, String(w.retention_days),
      ].join(','));
    }
    const blob = new Blob([csv.join('\n')], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `consent-records-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    addToast('success', 'Exported', 'Consent records exported as CSV.');
  };

  const filtered = workers.filter((w) => {
    if (filter === 'all') return true;
    return w.consent_status === filter;
  });

  const stats = {
    total: workers.length,
    granted: workers.filter((w) => w.consent_status === 'granted').length,
    denied: workers.filter((w) => w.consent_status === 'denied').length,
    pending: workers.filter((w) => w.consent_status === 'pending').length,
    withdrawn: workers.filter((w) => w.consent_status === 'withdrawn').length,
  };

  const statusColor = (status: string) => {
    switch (status) {
      case 'granted': return 'bg-green-500/15 text-green-400 border-green-500/30';
      case 'denied': return 'bg-red-500/15 text-red-400 border-red-500/30';
      case 'pending': return 'bg-amber-500/15 text-amber-400 border-amber-500/30';
      case 'withdrawn': return 'bg-gray-500/15 text-gray-400 border-gray-500/30';
      default: return 'bg-slate-500/15 text-slate-400 border-slate-500/30';
    }
  };

  const statusIcon = (status: string) => {
    switch (status) {
      case 'granted': return <Check className="w-4 h-4" />;
      case 'denied': return <X className="w-4 h-4" />;
      case 'pending': return <Clock className="w-4 h-4" />;
      case 'withdrawn': return <AlertTriangle className="w-4 h-4" />;
      default: return null;
    }
  };

  if (loading) {
    return (
      <div className="p-lg space-y-lg pb-32">
        <h1 className="text-display-lg font-bold text-on-surface">Consent Management</h1>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-md">
          <LoadingCard height="h-24" />
          <LoadingCard height="h-24" />
          <LoadingCard height="h-24" />
          <LoadingCard height="h-24" />
        </div>
      </div>
    );
  }

  return (
    <div className="p-lg space-y-lg pb-32" data-tour="consent-content">
      <div className="flex items-center justify-between flex-wrap gap-md">
        <div>
          <h1 className="text-display-lg font-bold text-on-surface">Consent Management</h1>
          <p className="text-body-sm text-on-surface-variant mt-xs">
            GDPR/CCPA compliant worker consent tracking and management
          </p>
        </div>
        <div className="flex items-center gap-sm">
          <button
            onClick={() => setShowPolicy(!showPolicy)}
            className="flex items-center gap-sm rounded-lg border border-outline-variant bg-surface-container px-md py-sm text-body-sm text-on-surface-variant hover:bg-surface-container-highest transition-colors"
          >
            <FileText className="w-4 h-4" />
            {showPolicy ? 'Hide Policy' : 'View Policy'}
          </button>
          <button
            onClick={handleExportConsent}
            className="flex items-center gap-sm rounded-lg border border-outline-variant bg-surface-container px-md py-sm text-body-sm text-on-surface-variant hover:bg-surface-container-highest transition-colors"
          >
            <Download className="w-4 h-4" />
            Export CSV
          </button>
        </div>
      </div>

      {/* Privacy Policy Card */}
      {showPolicy && policy && (
        <section className="rounded-2xl border border-outline-variant bg-surface-container p-lg space-y-md">
          <div className="flex items-center gap-sm">
            <Shield className="w-5 h-5 text-primary" />
            <h2 className="text-title-sm font-bold text-on-surface">{policy.title}</h2>
            <span className="text-[10px] font-mono text-on-surface-variant">v{policy.version}</span>
          </div>
          <p className="text-body-sm text-on-surface-variant">{policy.description}</p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-md">
            <div>
              <h3 className="text-body-sm font-bold text-on-surface mb-sm">Data Collection Purposes</h3>
              <ul className="space-y-xs">
                {policy.purposes.map((p) => (
                  <li key={p} className="flex items-start gap-sm text-body-sm text-on-surface-variant">
                    <Check className="w-3.5 h-3.5 text-green-400 mt-0.5 shrink-0" />
                    {p}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h3 className="text-body-sm font-bold text-on-surface mb-sm">Data Categories Collected</h3>
              <ul className="space-y-xs">
                {policy.data_categories.map((c) => (
                  <li key={c} className="flex items-start gap-sm text-body-sm text-on-surface-variant">
                    <Eye className="w-3.5 h-3.5 text-blue-400 mt-0.5 shrink-0" />
                    {c}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <div>
            <h3 className="text-body-sm font-bold text-on-surface mb-sm">Your Rights</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-sm">
              {policy.rights.map((r) => (
                <div key={r} className="flex items-center gap-sm text-body-sm text-on-surface-variant bg-surface-container-low rounded-lg px-sm py-1.5">
                  <Shield className="w-3.5 h-3.5 text-primary shrink-0" />
                  {r}
                </div>
              ))}
            </div>
          </div>

          <p className="text-[10px] text-on-surface-variant/60">Last updated: {policy.last_updated} · Retention: {policy.retention_days} days</p>
        </section>
      )}

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-md">
        {[
          { label: 'Total Workers', value: stats.total, color: 'text-on-surface' },
          { label: 'Consented', value: stats.granted, color: 'text-green-400' },
          { label: 'Denied', value: stats.denied, color: 'text-red-400' },
          { label: 'Pending', value: stats.pending, color: 'text-amber-400' },
          { label: 'Withdrawn', value: stats.withdrawn, color: 'text-gray-400' },
        ].map((stat) => (
          <div key={stat.label} className="rounded-xl border border-outline-variant bg-surface-container p-md text-center">
            <p className={`text-title-lg font-bold ${stat.color}`}>{stat.value}</p>
            <p className="text-body-sm text-on-surface-variant">{stat.label}</p>
          </div>
        ))}
      </div>

      {/* Filter */}
      <div className="flex items-center gap-sm">
        {['all', 'granted', 'denied', 'pending', 'withdrawn'].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-md py-sm rounded-lg text-body-sm font-medium transition-colors ${
              filter === f
                ? 'bg-primary text-on-primary'
                : 'bg-surface-container border border-outline-variant text-on-surface-variant hover:bg-surface-container-highest'
            }`}
          >
            {f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
        <span className="ml-auto text-[11px] text-on-surface-variant">{filtered.length} worker{filtered.length !== 1 ? 's' : ''}</span>
      </div>

      {/* Worker List */}
      {error ? (
        <EmptyState title="Error" message={error} />
      ) : filtered.length === 0 ? (
        <EmptyState
          title="No Consent Records"
          message="Add workers to begin tracking consent status."
        />
      ) : (
        <div className="space-y-sm">
          {filtered.map((worker) => (
            <div
              key={worker.worker_id}
              className="rounded-xl border border-outline-variant bg-surface-container p-md"
            >
              <div className="flex items-center justify-between flex-wrap gap-md">
                <div className="flex items-center gap-md">
                  <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                    <Users className="w-5 h-5 text-primary" />
                  </div>
                  <div>
                    <p className="text-body-sm font-bold text-on-surface">{worker.name}</p>
                    <p className="text-[11px] text-on-surface-variant">{worker.worker_id} · {worker.department}</p>
                  </div>
                </div>

                <div className="flex items-center gap-sm flex-wrap">
                  {/* Status badge */}
                  <span className={`flex items-center gap-xs px-sm py-1 rounded-lg text-[11px] font-bold border ${statusColor(worker.consent_status)}`}>
                    {statusIcon(worker.consent_status)}
                    {worker.consent_status.toUpperCase()}
                  </span>

                  {/* Consent date */}
                  {worker.consent_date && (
                    <span className="text-[10px] text-on-surface-variant">
                      {new Date(worker.consent_date).toLocaleDateString()}
                    </span>
                  )}

                  {/* Actions */}
                  <div className="flex items-center gap-xs">
                    {worker.consent_status !== 'granted' && (
                      <button
                        onClick={() => handleGrantConsent(worker.worker_id)}
                        className="px-sm py-1 rounded-lg bg-green-500/10 border border-green-500/30 text-green-400 text-[11px] font-bold hover:bg-green-500/20 transition-colors"
                        aria-label={`Grant consent for ${worker.name}`}
                      >
                        Grant
                      </button>
                    )}
                    {worker.consent_status !== 'denied' && (
                      <button
                        onClick={() => handleDenyConsent(worker.worker_id)}
                        className="px-sm py-1 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-[11px] font-bold hover:bg-red-500/20 transition-colors"
                        aria-label={`Deny consent for ${worker.name}`}
                      >
                        Deny
                      </button>
                    )}
                    {worker.consent_status === 'granted' && (
                      <button
                        onClick={() => handleWithdrawConsent(worker.worker_id)}
                        className="px-sm py-1 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-400 text-[11px] font-bold hover:bg-amber-500/20 transition-colors"
                        aria-label={`Withdraw consent for ${worker.name}`}
                      >
                        Withdraw
                      </button>
                    )}
                  </div>
                </div>
              </div>

              {/* Consent details */}
              {worker.consent_status === 'granted' && (
                <div className="mt-md pt-md border-t border-outline-variant/50 grid grid-cols-2 md:grid-cols-4 gap-sm text-[11px] text-on-surface-variant">
                  <div>
                    <span className="text-on-surface-variant/60">Version</span>
                    <p className="font-medium text-on-surface">{worker.consent_version}</p>
                  </div>
                  <div>
                    <span className="text-on-surface-variant/60">Retention</span>
                    <p className="font-medium text-on-surface">{worker.retention_days} days</p>
                  </div>
                  <div>
                    <span className="text-on-surface-variant/60">Expiry</span>
                    <p className="font-medium text-on-surface">{worker.consent_expiry ? new Date(worker.consent_expiry).toLocaleDateString() : 'No expiry'}</p>
                  </div>
                  <div>
                    <span className="text-on-surface-variant/60">Categories</span>
                    <p className="font-medium text-on-surface">{worker.data_categories.length} types</p>
                  </div>
                </div>
              )}

              {/* Withdrawal info */}
              {worker.consent_status === 'withdrawn' && worker.withdrawal_date && (
                <div className="mt-md pt-md border-t border-outline-variant/50 text-[11px] text-on-surface-variant flex items-center gap-sm">
                  <Trash2 className="w-3.5 h-3.5 text-amber-400" />
                  Consent withdrawn on {new Date(worker.withdrawal_date).toLocaleDateString()}. Session data scheduled for deletion.
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Compliance Footer */}
      <section className="rounded-xl border border-outline-variant/60 bg-surface-container-low p-md">
        <div className="flex items-start gap-md">
          <Shield className="w-5 h-5 text-primary shrink-0 mt-0.5" />
          <div>
            <h3 className="text-body-sm font-bold text-on-surface">Privacy Compliance</h3>
            <p className="text-[11px] text-on-surface-variant mt-1">
              This system complies with GDPR (Articles 6, 7, 17, 20), CCPA §1798.100-120, and India's Digital Personal Data Protection Act 2023.
              All posture data is processed locally and never leaves the premises. Worker consent is required before monitoring begins.
              Consent can be withdrawn at any time, triggering automatic data deletion after the configured retention period.
            </p>
            <div className="flex flex-wrap gap-md mt-sm">
              <span className="text-[10px] font-mono text-on-surface-variant/60">GDPR Art. 6(1)(a) — Consent</span>
              <span className="text-[10px] font-mono text-on-surface-variant/60">GDPR Art. 7 — Conditions for Consent</span>
              <span className="text-[10px] font-mono text-on-surface-variant/60">GDPR Art. 17 — Right to Erasure</span>
              <span className="text-[10px] font-mono text-on-surface-variant/60">CCPA §1798.100</span>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
