import { useState, useEffect, useCallback, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Plus, Pencil, Trash2, X, Search, Camera, CheckCircle2, Loader2, QrCode, ShieldCheck } from 'lucide-react';
import { SectionHeader, EmptyState } from '@/src/components/common';
import { useAuth } from '@/src/auth/AuthContext';
import { apiFetch } from '@/src/services/apiClient';

interface Worker {
  worker_id: string;
  employee_id: string;
  name: string;
  department: string;
  shift: string;
  identity_mode?: string;
  consent_status?: string;
  badge_id?: string | null;
}

interface FaceStatus {
  worker_id: string;
  enrolled: boolean;
  enrolled_at?: string;
}

interface FormData {
  employee_id: string;
  name: string;
  department: string;
  shift: string;
}

const MANAGER_ROLES = new Set(['supervisor', 'safety_mgr', 'admin']);

const emptyForm = (): FormData => ({ employee_id: '', name: '', department: '', shift: '' });

export default function WorkersPage() {
  const { user } = useAuth();
  const isManager = user ? MANAGER_ROLES.has(user.role) : false;

  const [workers, setWorkers] = useState<Worker[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [search, setSearch] = useState('');

  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState<FormData>(emptyForm());
  const [editingId, setEditingId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [deleteTarget, setDeleteTarget] = useState<Worker | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  // Face enrollment state: worker_id -> status, plus in-flight uploads.
  const [faceStatus, setFaceStatus] = useState<Record<string, FaceStatus>>({});
  const [faceUploading, setFaceUploading] = useState<Record<string, boolean>>({});
  const [faceError, setFaceError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [faceTargetId, setFaceTargetId] = useState<string | null>(null);

  // Identity mode / consent / badge config.
  const [identityTarget, setIdentityTarget] = useState<Worker | null>(null);
  const [identityMode, setIdentityMode] = useState('face');
  const [consentStatus, setConsentStatus] = useState('pending');
  const [badgeId, setBadgeId] = useState('');
  const [identitySaving, setIdentitySaving] = useState(false);
  const [identityError, setIdentityError] = useState<string | null>(null);
  const [qrWorker, setQrWorker] = useState<Worker | null>(null);
  const [qrSvg, setQrSvg] = useState<Record<string, string>>({});
  const [qrError, setQrError] = useState<string | null>(null);

  const fetchWorkers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch('/api/workers');
      if (!res.ok) throw new Error(`Failed to load workers (${res.status})`);
      setWorkers(await res.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchWorkers(); }, [fetchWorkers]);

  const fetchFaceStatus = useCallback(async (workerId: string) => {
    try {
      const res = await apiFetch(`/api/workers/${workerId}/face`);
      if (res.ok) {
        const data = (await res.json()) as FaceStatus;
        setFaceStatus((prev) => ({ ...prev, [workerId]: data }));
      }
    } catch {
      // Non-fatal: face enrollment is an enhancement; ignore status errors.
    }
  }, []);

  useEffect(() => {
    if (workers.length > 0) workers.forEach((w) => fetchFaceStatus(w.worker_id));
  }, [workers, fetchFaceStatus]);

  // Fetch the QR SVG whenever the QR modal opens for a worker (cached per worker).
  useEffect(() => {
    if (!qrWorker) return;
    if (qrSvg[qrWorker.worker_id]) return;
    setQrError(null);
    apiFetch(`/api/workers/${qrWorker.worker_id}/badge/qr`)
      .then((res) => {
        if (!res.ok) throw new Error(`QR fetch failed (${res.status})`);
        return res.text();
      })
      .then((svg) => setQrSvg((prev) => ({ ...prev, [qrWorker.worker_id]: svg })))
      .catch((err: unknown) => setQrError(err instanceof Error ? err.message : 'QR fetch failed'));
  }, [qrWorker, qrSvg]);

  const openFacePicker = (workerId: string) => {
    setFaceTargetId(workerId);
    setFaceError(null);
    // Reuse a single hidden input; clicking it opens the file dialog.
    window.setTimeout(() => fileInputRef.current?.click(), 0);
  };

  const handleFaceFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = ''; // allow re-selecting the same file
    if (!file || !faceTargetId) return;
    const workerId = faceTargetId;
    setFaceUploading((prev) => ({ ...prev, [workerId]: true }));
    setFaceError(null);
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await apiFetch(`/api/workers/${workerId}/face`, {
        method: 'POST',
        body: form,
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Face upload failed (${res.status})`);
      }
      const data = (await res.json()) as FaceStatus;
      setFaceStatus((prev) => ({ ...prev, [workerId]: data }));
    } catch (err: unknown) {
      setFaceError(err instanceof Error ? err.message : 'Face upload failed');
    } finally {
      setFaceUploading((prev) => ({ ...prev, [workerId]: false }));
      setFaceTargetId(null);
    }
  };

  const openIdentity = (w: Worker) => {
    setIdentityTarget(w);
    setIdentityMode(w.identity_mode || 'face');
    setConsentStatus(w.consent_status || 'pending');
    setBadgeId(w.badge_id || '');
    setIdentityError(null);
  };

  const saveIdentity = async () => {
    if (!identityTarget) return;
    setIdentitySaving(true);
    setIdentityError(null);
    try {
      const res = await apiFetch(`/api/workers/${identityTarget.worker_id}/identity`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ identity_mode: identityMode, consent_status: consentStatus }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Identity update failed (${res.status})`);
      }
      // Assign/clear the badge in the same save when the field changed.
      const nextBadge = badgeId.trim() || null;
      if (nextBadge !== (identityTarget.badge_id || null)) {
        if (nextBadge) {
          const bres = await apiFetch(`/api/workers/${identityTarget.worker_id}/badge`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ badge_id: nextBadge }),
          });
          if (!bres.ok) {
            const body = await bres.json().catch(() => ({}));
            throw new Error(body.detail || `Badge assignment failed (${bres.status})`);
          }
        } else {
          await apiFetch(`/api/workers/${identityTarget.worker_id}/badge`, { method: 'DELETE' });
        }
      }
      setIdentityTarget(null);
      await fetchWorkers();
    } catch (e: unknown) {
      setIdentityError(e instanceof Error ? e.message : 'Identity update failed');
    } finally {
      setIdentitySaving(false);
    }
  };

  const removeFace = async (workerId: string) => {
    setFaceError(null);
    try {
      const res = await apiFetch(`/api/workers/${workerId}/face`, { method: 'DELETE' });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Removal failed (${res.status})`);
      }
      setFaceStatus((prev) => ({ ...prev, [workerId]: { worker_id: workerId, enrolled: false } }));
    } catch (err: unknown) {
      setFaceError(err instanceof Error ? err.message : 'Removal failed');
    }
  };

  const filtered = search
    ? workers.filter(
        (w) =>
          w.name.toLowerCase().includes(search.toLowerCase()) ||
          w.employee_id.toLowerCase().includes(search.toLowerCase()) ||
          w.department.toLowerCase().includes(search.toLowerCase()),
      )
    : workers;

  const openAdd = () => {
    setEditingId(null);
    setFormData(emptyForm());
    setFormError(null);
    setShowForm(true);
  };

  const openEdit = (w: Worker) => {
    setEditingId(w.worker_id);
    setFormData({ employee_id: w.employee_id, name: w.name, department: w.department, shift: w.shift });
    setFormError(null);
    setShowForm(true);
  };

  const closeForm = () => {
    setShowForm(false);
    setEditingId(null);
    setFormData(emptyForm());
    setFormError(null);
  };

  const handleSave = async () => {
    if (!formData.employee_id.trim() || !formData.name.trim() || !formData.department.trim() || !formData.shift.trim()) {
      setFormError('All fields are required.');
      return;
    }
    setSaving(true);
    setFormError(null);
    try {
      if (editingId) {
        const res = await apiFetch(`/api/workers/${editingId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: formData.name.trim(), department: formData.department.trim(), shift: formData.shift.trim() }),
        });
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.detail || `Update failed (${res.status})`);
        }
      } else {
        const res = await apiFetch('/api/workers', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            employee_id: formData.employee_id.trim(),
            name: formData.name.trim(),
            department: formData.department.trim(),
            shift: formData.shift.trim(),
          }),
        });
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.detail || `Create failed (${res.status})`);
        }
      }
      closeForm();
      await fetchWorkers();
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const confirmDelete = (w: Worker) => {
    setDeleteTarget(w);
    setDeleteError(null);
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      const res = await apiFetch(`/api/workers/${deleteTarget.worker_id}`, { method: 'DELETE' });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Delete failed (${res.status})`);
      }
      setDeleteTarget(null);
      await fetchWorkers();
    } catch (e: unknown) {
      setDeleteError(e instanceof Error ? e.message : 'Delete failed');
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="p-lg space-y-lg">
      <div className="flex items-center justify-between">
        <SectionHeader title="Workers" />
        {isManager && (
          <button onClick={openAdd} className="flex items-center gap-sm px-md py-sm rounded-lg text-body-sm font-medium bg-primary text-on-primary hover:bg-primary/90 transition-colors">
            <Plus className="w-4 h-4" />
            Add Worker
          </button>
        )}
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-on-surface-variant" />
        <input
          type="text"
          placeholder="Search workers..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full pl-10 pr-4 py-sm rounded-lg bg-surface-container border border-outline-variant text-on-surface text-body-sm placeholder:text-on-surface-variant focus:outline-none focus:border-primary"
        />
      </div>

      {loading ? (
        <div className="text-center text-on-surface-variant py-xl">Loading workers...</div>
      ) : error ? (
        <div className="text-center text-red-400 py-xl">{error}</div>
      ) : filtered.length === 0 ? (
        <EmptyState title={search ? 'No workers match your search' : 'No workers found'} message={search ? 'Try a different search term.' : 'Click "Add Worker" to create the first entry.'} />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-body-sm">
            <thead>
              <tr className="border-b border-outline-variant text-on-surface-variant text-[10px] uppercase tracking-wider">
                <th className="text-left py-sm px-md font-medium" title="HR-facing employee number">Employee ID</th>
                <th className="text-left py-sm px-md font-medium">Name</th>
                <th className="text-left py-sm px-md font-medium">Department</th>
                <th className="text-left py-sm px-md font-medium">Shift</th>
                <th className="text-left py-sm px-md font-medium" title="Face recognition enrollment">Face ID</th>
                <th className="text-left py-sm px-md font-medium" title="How this worker is identified + consent state">Identity</th>
                {isManager && <th className="text-right py-sm px-md font-medium">Actions</th>}
              </tr>
            </thead>
            <tbody>
              {filtered.map((w) => (
                <tr key={w.worker_id} className="border-b border-outline-variant/30 hover:bg-surface-container-higher/50 transition-colors">
                  <td className="py-sm px-md" title={`Employee ID: ${w.employee_id} · Internal worker ID: ${w.worker_id}`}>
                    <span className="font-mono text-on-surface">{w.employee_id}</span>
                    <span className="block font-mono text-[11px] text-on-surface-variant/70 mt-0.5">{w.worker_id}</span>
                  </td>
                  <td className="py-sm px-md text-on-surface">{w.name}</td>
                  <td className="py-sm px-md text-on-surface">{w.department}</td>
                  <td className="py-sm px-md text-on-surface">{w.shift}</td>
                  <td className="py-sm px-md">
                    {faceUploading[w.worker_id] ? (
                      <span className="inline-flex items-center gap-xs text-on-surface-variant text-body-sm">
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Enrolling…
                      </span>
                    ) : faceStatus[w.worker_id]?.enrolled ? (
                      <button
                        onClick={() => removeFace(w.worker_id)}
                        className="inline-flex items-center gap-xs text-body-sm text-green-400 hover:text-red-400 transition-colors"
                        title={`Enrolled ${faceStatus[w.worker_id]?.enrolled_at ? new Date(faceStatus[w.worker_id]!.enrolled_at!).toLocaleString() : ''} — click to remove`}
                      >
                        <CheckCircle2 className="w-4 h-4" />
                        Enrolled
                      </button>
                    ) : (
                      <button
                        onClick={() => openFacePicker(w.worker_id)}
                        disabled={!isManager}
                        className="inline-flex items-center gap-xs text-body-sm text-on-surface-variant hover:text-primary transition-colors disabled:opacity-40"
                        title={isManager ? 'Upload a face photo to enable recognition' : 'Supervisor or admin can enroll a face'}
                      >
                        <Camera className="w-4 h-4" />
                        Enroll
                      </button>
                    )}
                  </td>
                  <td className="py-sm px-md">
                    <button
                      onClick={() => openIdentity(w)}
                      disabled={!isManager}
                      className="inline-flex items-center gap-xs text-body-sm hover:text-primary transition-colors disabled:cursor-default"
                      title={isManager ? 'Configure identity mode, consent, and badge/QR' : 'Identity settings'}
                    >
                      <ShieldCheck className="w-4 h-4 text-on-surface-variant" />
                      <span className="capitalize text-on-surface">{(w.identity_mode || 'face').toLowerCase()}</span>
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                          w.consent_status === 'granted'
                            ? 'bg-green-500/15 text-green-400'
                            : w.consent_status === 'denied'
                              ? 'bg-red-500/15 text-red-400'
                              : 'bg-amber-500/15 text-amber-400'
                        }`}
                      >
                        {w.consent_status || 'pending'}
                      </span>
                      {w.badge_id && (
                        <QrCode className="w-3.5 h-3.5 text-on-surface-variant" />
                      )}
                    </button>
                  </td>
                  {isManager && (
                    <td className="py-sm px-md text-right">
                      <div className="flex items-center justify-end gap-sm">
                        <button onClick={() => openEdit(w)} className="p-1.5 rounded-md text-on-surface-variant hover:text-primary hover:bg-primary/10 transition-colors" title="Edit">
                          <Pencil className="w-4 h-4" />
                        </button>
                        <button onClick={() => confirmDelete(w)} className="p-1.5 rounded-md text-on-surface-variant hover:text-red-400 hover:bg-red-500/10 transition-colors" title="Delete">
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showForm && createPortal(
        <div style={{ position: 'fixed', inset: 0, zIndex: 50, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.4)' }} onClick={closeForm}>
          <div style={{ background: 'var(--color-surface-container)', width: '100%', maxWidth: '28rem', margin: '0 24px', borderRadius: '12px', border: '1px solid var(--color-outline-variant)', boxShadow: '0 25px 50px -12px rgba(0,0,0,0.5)', padding: '24px' }} onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
              <h3 className="font-label-caps text-label-caps text-on-surface uppercase tracking-widest">
                {editingId ? 'Edit Worker' : 'Add Worker'}
              </h3>
              <button onClick={closeForm} style={{ padding: '4px', borderRadius: '6px' }} className="text-on-surface-variant hover:text-on-surface hover:bg-surface-container-higher transition-colors">
                <X className="w-4 h-4" />
              </button>
            </div>

            {formError && (
              <div className="mb-md p-sm rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-body-sm">{formError}</div>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div>
                <label className="block text-[10px] uppercase tracking-wider text-on-surface-variant mb-xs font-medium">Employee ID</label>
                <input
                  type="text"
                  value={formData.employee_id}
                  onChange={(e) => setFormData({ ...formData, employee_id: e.target.value })}
                  disabled={!!editingId}
                  style={{ width: '100%', padding: '8px 16px', borderRadius: '8px', border: '1px solid var(--color-outline-variant)', background: 'var(--color-surface-container-high)', color: 'var(--color-on-surface)', fontSize: '13px' }}
                  className="placeholder:text-on-surface-variant focus:outline-none focus:border-primary"
                  placeholder="e.g. EMP-003"
                />
                {editingId && <p className="text-[10px] text-on-surface-variant mt-xs">Employee ID cannot be changed after creation.</p>}
              </div>
              <div>
                <label className="block text-[10px] uppercase tracking-wider text-on-surface-variant mb-xs font-medium">Name</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  style={{ width: '100%', padding: '8px 16px', borderRadius: '8px', border: '1px solid var(--color-outline-variant)', background: 'var(--color-surface-container-high)', color: 'var(--color-on-surface)', fontSize: '13px' }}
                  className="placeholder:text-on-surface-variant focus:outline-none focus:border-primary"
                  placeholder="Full name"
                />
              </div>
              <div>
                <label className="block text-[10px] uppercase tracking-wider text-on-surface-variant mb-xs font-medium">Department</label>
                <input
                  type="text"
                  value={formData.department}
                  onChange={(e) => setFormData({ ...formData, department: e.target.value })}
                  style={{ width: '100%', padding: '8px 16px', borderRadius: '8px', border: '1px solid var(--color-outline-variant)', background: 'var(--color-surface-container-high)', color: 'var(--color-on-surface)', fontSize: '13px' }}
                  className="placeholder:text-on-surface-variant focus:outline-none focus:border-primary"
                  placeholder="e.g. Assembly, Inspection"
                />
              </div>
              <div>
                <label className="block text-[10px] uppercase tracking-wider text-on-surface-variant mb-xs font-medium">Shift</label>
                <input
                  type="text"
                  value={formData.shift}
                  onChange={(e) => setFormData({ ...formData, shift: e.target.value })}
                  style={{ width: '100%', padding: '8px 16px', borderRadius: '8px', border: '1px solid var(--color-outline-variant)', background: 'var(--color-surface-container-high)', color: 'var(--color-on-surface)', fontSize: '13px' }}
                  className="placeholder:text-on-surface-variant focus:outline-none focus:border-primary"
                  placeholder="e.g. Day, Evening, Night"
                />
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '16px', marginTop: '24px' }}>
              <button onClick={closeForm} style={{ padding: '8px 16px', borderRadius: '8px', fontSize: '13px', fontWeight: 500 }} className="text-on-surface-variant hover:text-on-surface hover:bg-surface-container-higher transition-colors">
                Cancel
              </button>
              <button onClick={handleSave} disabled={saving} style={{ padding: '8px 16px', borderRadius: '8px', fontSize: '13px', fontWeight: 500, background: 'var(--color-primary)', color: 'var(--color-on-primary)', opacity: saving ? 0.5 : 1 }}>
                {saving ? 'Saving...' : editingId ? 'Update Worker' : 'Create Worker'}
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}

      {faceError && (
        <div className="p-sm rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-body-sm">{faceError}</div>
      )}

      {/* Hidden file input reused for any worker's face upload. */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="hidden"
        onChange={handleFaceFile}
      />

      {identityTarget && createPortal(
        <div style={{ position: 'fixed', inset: 0, zIndex: 50, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.4)' }} onClick={() => !identitySaving && setIdentityTarget(null)}>
          <div style={{ background: 'var(--color-surface-container)', width: '100%', maxWidth: '30rem', margin: '0 24px', borderRadius: '12px', border: '1px solid var(--color-outline-variant)', boxShadow: '0 25px 50px -12px rgba(0,0,0,0.5)', padding: '24px' }} onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
              <h3 className="font-label-caps text-label-caps text-on-surface uppercase tracking-widest">Identity & Consent — {identityTarget.name}</h3>
              <button onClick={() => !identitySaving && setIdentityTarget(null)} style={{ padding: '4px', borderRadius: '6px' }} className="text-on-surface-variant hover:text-on-surface hover:bg-surface-container-higher transition-colors">
                <X className="w-4 h-4" />
              </button>
            </div>

            {identityError && (
              <div className="mb-md p-sm rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-body-sm">{identityError}</div>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div>
                <label className="block text-[10px] uppercase tracking-wider text-on-surface-variant mb-xs font-medium">How is this worker identified?</label>
                <div style={{ display: 'flex', gap: '8px' }}>
                  {(['face', 'badge', 'off'] as const).map((mode) => (
                    <button
                      key={mode}
                      onClick={() => setIdentityMode(mode)}
                      style={{
                        flex: 1, padding: '10px 8px', borderRadius: '8px', border: '1px solid',
                        borderColor: identityMode === mode ? 'var(--color-primary)' : 'var(--color-outline-variant)',
                        background: identityMode === mode ? 'var(--color-primary/10)' : 'var(--color-surface-container-high)',
                        color: 'var(--color-on-surface)', fontSize: '12px', fontWeight: identityMode === mode ? 600 : 400,
                      }}
                    >
                      {mode === 'face' ? 'Face camera' : mode === 'badge' ? 'Badge / QR' : 'No identification'}
                    </button>
                  ))}
                </div>
                <p className="text-[11px] text-on-surface-variant mt-xs">
                  {identityMode === 'face' && 'Camera face recognition — needs consent and an enrolled photo.'}
                  {identityMode === 'badge' && 'Badge/QR scan only — face recognition is disabled for this worker.'}
                  {identityMode === 'off' && 'Never identified automatically — sessions stay anonymous.'}
                </p>
              </div>

              <div>
                <label className="block text-[10px] uppercase tracking-wider text-on-surface-variant mb-xs font-medium">Consent status</label>
                <div style={{ display: 'flex', gap: '8px' }}>
                  {(['granted', 'pending', 'denied'] as const).map((status) => (
                    <button
                      key={status}
                      onClick={() => setConsentStatus(status)}
                      style={{
                        flex: 1, padding: '10px 8px', borderRadius: '8px', border: '1px solid',
                        borderColor: consentStatus === status ? 'var(--color-primary)' : 'var(--color-outline-variant)',
                        background: consentStatus === status ? 'var(--color-primary/10)' : 'var(--color-surface-container-high)',
                        color: 'var(--color-on-surface)', fontSize: '12px', fontWeight: consentStatus === status ? 600 : 400,
                      }}
                    >
                      {status}
                    </button>
                  ))}
                </div>
                {consentStatus === 'denied' && (
                  <p className="text-[11px] text-red-400 mt-xs">Denied consent immediately removes this worker from face recognition — their stored embedding is never matched.</p>
                )}
              </div>

              <div>
                <label className="block text-[10px] uppercase tracking-wider text-on-surface-variant mb-xs font-medium">Badge / QR identifier</label>
                <input
                  type="text"
                  value={badgeId}
                  onChange={(e) => setBadgeId(e.target.value)}
                  style={{ width: '100%', padding: '8px 16px', borderRadius: '8px', border: '1px solid var(--color-outline-variant)', background: 'var(--color-surface-container-high)', color: 'var(--color-on-surface)', fontSize: '13px' }}
                  className="placeholder:text-on-surface-variant focus:outline-none focus:border-primary"
                  placeholder="e.g. BADGE-1042 (leave empty to remove)"
                />
                <p className="text-[11px] text-on-surface-variant mt-xs">
                  The badge can be printed as a QR code for scan-based check-in — no camera identity needed.
                </p>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '24px' }}>
              <button
                onClick={() => setQrWorker(identityTarget)}
                disabled={!badgeId.trim()}
                style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 12px', borderRadius: '8px', fontSize: '13px', fontWeight: 500, border: '1px solid var(--color-outline-variant)' }}
                className="text-on-surface-variant hover:text-on-surface hover:bg-surface-container-higher transition-colors disabled:opacity-40"
                title={badgeId.trim() ? 'Show this badge as a QR code' : 'Assign a badge ID first'}
              >
                <QrCode className="w-4 h-4" />
                Show QR
              </button>
              <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                <button onClick={() => !identitySaving && setIdentityTarget(null)} disabled={identitySaving} style={{ padding: '8px 16px', borderRadius: '8px', fontSize: '13px', fontWeight: 500 }} className="text-on-surface-variant hover:text-on-surface hover:bg-surface-container-higher transition-colors disabled:opacity-50">
                  Cancel
                </button>
                <button onClick={saveIdentity} disabled={identitySaving} style={{ padding: '8px 16px', borderRadius: '8px', fontSize: '13px', fontWeight: 500, background: 'var(--color-primary)', color: 'var(--color-on-primary)', opacity: identitySaving ? 0.5 : 1 }}>
                  {identitySaving ? 'Saving...' : 'Save Identity'}
                </button>
              </div>
            </div>
          </div>
        </div>,
        document.body
      )}

      {qrWorker && createPortal(
        <div style={{ position: 'fixed', inset: 0, zIndex: 60, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.4)' }} onClick={() => setQrWorker(null)}>
          <div style={{ background: 'var(--color-surface-container)', width: '100%', maxWidth: '22rem', margin: '0 24px', borderRadius: '12px', border: '1px solid var(--color-outline-variant)', boxShadow: '0 25px 50px -12px rgba(0,0,0,0.5)', padding: '24px', textAlign: 'center' }} onClick={(e) => e.stopPropagation()}>
            <h3 className="font-label-caps text-label-caps text-on-surface uppercase tracking-widest" style={{ marginBottom: '8px' }}>Badge QR — {qrWorker.employee_id}</h3>
            <p className="text-body-sm text-on-surface-variant" style={{ marginBottom: '16px' }}>
              Print this code on the worker's badge. Scanning it identifies them — no camera needed.
            </p>
            {qrError ? (
              <div className="text-red-400 text-body-sm mb-md">{qrError}</div>
            ) : (
              <div
                style={{ display: 'inline-flex', padding: '12px', background: '#fff', borderRadius: '8px' }}
                dangerouslySetInnerHTML={{ __html: qrSvg[qrWorker.worker_id] || '' }}
              />
            )}
            <div style={{ marginTop: '16px' }}>
              <button
                onClick={() => setQrWorker(null)}
                style={{ padding: '8px 20px', borderRadius: '8px', fontSize: '13px', fontWeight: 500, background: 'var(--color-primary)', color: 'var(--color-on-primary)' }}
              >
                Done
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}

      {deleteTarget && createPortal(
        <div style={{ position: 'fixed', inset: 0, zIndex: 50, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.4)' }} onClick={() => !deleting && setDeleteTarget(null)}>
          <div style={{ background: 'var(--color-surface-container)', width: '100%', maxWidth: '24rem', margin: '0 24px', borderRadius: '12px', border: '1px solid var(--color-outline-variant)', boxShadow: '0 25px 50px -12px rgba(0,0,0,0.5)', padding: '24px' }} onClick={(e) => e.stopPropagation()}>
            <h3 className="font-label-caps text-label-caps text-on-surface uppercase tracking-widest" style={{ marginBottom: '8px' }}>Delete Worker</h3>
            <p className="text-body-sm text-on-surface-variant" style={{ marginBottom: '16px' }}>
              Are you sure you want to delete <span className="text-on-surface font-medium">{deleteTarget.name}</span> ({deleteTarget.employee_id})?
            </p>

            {deleteError && (
              <div className="mb-md p-sm rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-body-sm">{deleteError}</div>
            )}

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '16px' }}>
              <button onClick={() => !deleting && setDeleteTarget(null)} disabled={deleting} style={{ padding: '8px 16px', borderRadius: '8px', fontSize: '13px', fontWeight: 500 }} className="text-on-surface-variant hover:text-on-surface hover:bg-surface-container-higher transition-colors disabled:opacity-50">
                Cancel
              </button>
              <button onClick={handleDelete} disabled={deleting} style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 16px', borderRadius: '8px', fontSize: '13px', fontWeight: 500, background: '#dc2626', color: '#fff' }} className="hover:bg-red-500 transition-colors disabled:opacity-50">
                {deleting ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}
