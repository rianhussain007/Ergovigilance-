import { useState, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { Plus, Pencil, Trash2, X, Search } from 'lucide-react';
import { SectionHeader, EmptyState } from '@/src/components/common';
import { useAuth } from '@/src/auth/AuthContext';
import { apiFetch } from '@/src/services/apiClient';

interface Worker {
  worker_id: string;
  employee_id: string;
  name: string;
  department: string;
  shift: string;
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
                <th className="text-left py-sm px-md font-medium">Employee ID</th>
                <th className="text-left py-sm px-md font-medium">Name</th>
                <th className="text-left py-sm px-md font-medium">Department</th>
                <th className="text-left py-sm px-md font-medium">Shift</th>
                <th className="text-left py-sm px-md font-medium">Worker ID</th>
                {isManager && <th className="text-right py-sm px-md font-medium">Actions</th>}
              </tr>
            </thead>
            <tbody>
              {filtered.map((w) => (
                <tr key={w.worker_id} className="border-b border-outline-variant/30 hover:bg-surface-container-higher/50 transition-colors">
                  <td className="py-sm px-md font-mono text-on-surface">{w.employee_id}</td>
                  <td className="py-sm px-md text-on-surface">{w.name}</td>
                  <td className="py-sm px-md text-on-surface">{w.department}</td>
                  <td className="py-sm px-md text-on-surface">{w.shift}</td>
                  <td className="py-sm px-md text-on-surface-variant font-mono text-[11px]">{w.worker_id}</td>
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
          <div style={{ background: '#1d2027', width: '100%', maxWidth: '28rem', margin: '0 24px', borderRadius: '12px', border: '1px solid #424754', boxShadow: '0 25px 50px -12px rgba(0,0,0,0.5)', padding: '24px' }} onClick={(e) => e.stopPropagation()}>
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
                  style={{ width: '100%', padding: '8px 16px', borderRadius: '8px', border: '1px solid #424754', background: '#272a31', color: '#e1e2ec', fontSize: '13px' }}
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
                  style={{ width: '100%', padding: '8px 16px', borderRadius: '8px', border: '1px solid #424754', background: '#272a31', color: '#e1e2ec', fontSize: '13px' }}
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
                  style={{ width: '100%', padding: '8px 16px', borderRadius: '8px', border: '1px solid #424754', background: '#272a31', color: '#e1e2ec', fontSize: '13px' }}
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
                  style={{ width: '100%', padding: '8px 16px', borderRadius: '8px', border: '1px solid #424754', background: '#272a31', color: '#e1e2ec', fontSize: '13px' }}
                  className="placeholder:text-on-surface-variant focus:outline-none focus:border-primary"
                  placeholder="e.g. Day, Evening, Night"
                />
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '16px', marginTop: '24px' }}>
              <button onClick={closeForm} style={{ padding: '8px 16px', borderRadius: '8px', fontSize: '13px', fontWeight: 500 }} className="text-on-surface-variant hover:text-on-surface hover:bg-surface-container-higher transition-colors">
                Cancel
              </button>
              <button onClick={handleSave} disabled={saving} style={{ padding: '8px 16px', borderRadius: '8px', fontSize: '13px', fontWeight: 500, background: '#adc6ff', color: '#002e6a', opacity: saving ? 0.5 : 1 }}>
                {saving ? 'Saving...' : editingId ? 'Update Worker' : 'Create Worker'}
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}

      {deleteTarget && createPortal(
        <div style={{ position: 'fixed', inset: 0, zIndex: 50, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.4)' }} onClick={() => !deleting && setDeleteTarget(null)}>
          <div style={{ background: '#1d2027', width: '100%', maxWidth: '24rem', margin: '0 24px', borderRadius: '12px', border: '1px solid #424754', boxShadow: '0 25px 50px -12px rgba(0,0,0,0.5)', padding: '24px' }} onClick={(e) => e.stopPropagation()}>
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
