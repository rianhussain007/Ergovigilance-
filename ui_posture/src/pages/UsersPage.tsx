import { useState, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { Plus, Pencil, Trash2, X, Search, KeyRound, Eye, EyeOff } from 'lucide-react';
import { SectionHeader, EmptyState } from '@/src/components/common';
import { useAuth } from '@/src/auth/AuthContext';
import { apiFetch } from '@/src/services/apiClient';

interface User {
  id: number;
  email: string;
  role: string;
  created_at: string;
}

const ROLES = ['operator', 'supervisor', 'safety_mgr', 'admin'] as const;
type Role = typeof ROLES[number];

const ROLE_LABELS: Record<Role, string> = {
  operator: 'Operator',
  supervisor: 'Supervisor',
  safety_mgr: 'Safety Manager',
  admin: 'Admin',
};

const ROLE_BADGE_CLASSES: Record<Role, string> = {
  operator: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
  supervisor: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
  safety_mgr: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  admin: 'bg-red-500/15 text-red-400 border-red-500/30',
};

function passwordStrength(pw: string): { score: number; label: string; color: string } {
  let score = 0;
  if (pw.length >= 8) score++;
  if (pw.length >= 12) score++;
  if (/[A-Z]/.test(pw)) score++;
  if (/[a-z]/.test(pw)) score++;
  if (/[0-9]/.test(pw)) score++;
  if (/[^A-Za-z0-9]/.test(pw)) score++;

  if (score <= 2) return { score, label: 'Weak', color: 'bg-red-500' };
  if (score <= 4) return { score, label: 'Fair', color: 'bg-amber-500' };
  return { score, label: 'Strong', color: 'bg-emerald-500' };
}

export default function UsersPage() {
  const { user: currentUser } = useAuth();
  const isAdmin = currentUser?.role === 'admin';

  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [search, setSearch] = useState('');

  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({ email: '', password: '', role: 'operator' as Role });
  const [editingId, setEditingId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);

  const [deleteTarget, setDeleteTarget] = useState<User | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const [resetTarget, setResetTarget] = useState<User | null>(null);
  const [resetting, setResetting] = useState(false);
  const [resetError, setResetError] = useState<string | null>(null);
  const [resetResult, setResetResult] = useState<string | null>(null);

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch('/api/users');
      if (!res.ok) throw new Error(`Failed to load users (${res.status})`);
      setUsers(await res.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchUsers(); }, [fetchUsers]);

  const filtered = search
    ? users.filter(
        (u) =>
          u.email.toLowerCase().includes(search.toLowerCase()) ||
          u.role.toLowerCase().includes(search.toLowerCase()),
      )
    : users;

  const openAdd = () => {
    setEditingId(null);
    setFormData({ email: '', password: '', role: 'operator' });
    setFormError(null);
    setShowPassword(false);
    setShowForm(true);
  };

  const openEdit = (u: User) => {
    setEditingId(u.id);
    setFormData({ email: u.email, password: '', role: u.role as Role });
    setFormError(null);
    setShowForm(true);
  };

  const closeForm = () => {
    setShowForm(false);
    setEditingId(null);
    setFormData({ email: '', password: '', role: 'operator' });
    setFormError(null);
    setShowPassword(false);
  };

  const handleSave = async () => {
    if (editingId) {
      if (!formData.role) {
        setFormError('Role is required.');
        return;
      }
    } else {
      if (!formData.email.trim()) {
        setFormError('Email is required.');
        return;
      }
      if (formData.password.length < 8) {
        setFormError('Password must be at least 8 characters.');
        return;
      }
    }

    setSaving(true);
    setFormError(null);
    try {
      if (editingId) {
        const res = await apiFetch(`/api/users/${editingId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ role: formData.role }),
        });
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.detail || `Update failed (${res.status})`);
        }
      } else {
        const res = await apiFetch('/api/users', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email: formData.email.trim(),
            password: formData.password,
            role: formData.role,
          }),
        });
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.detail || `Create failed (${res.status})`);
        }
      }
      closeForm();
      await fetchUsers();
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const confirmDelete = (u: User) => {
    if (u.id === currentUser?.id) return;
    setDeleteTarget(u);
    setDeleteError(null);
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      const res = await apiFetch(`/api/users/${deleteTarget.id}`, { method: 'DELETE' });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Delete failed (${res.status})`);
      }
      setDeleteTarget(null);
      await fetchUsers();
    } catch (e: unknown) {
      setDeleteError(e instanceof Error ? e.message : 'Delete failed');
    } finally {
      setDeleting(false);
    }
  };

  const openReset = (u: User) => {
    setResetTarget(u);
    setResetError(null);
    setResetResult(null);
  };

  const handleResetPassword = async (newPassword?: string) => {
    if (!resetTarget) return;
    setResetting(true);
    setResetError(null);
    setResetResult(null);
    try {
      const body: Record<string, string> = {};
      if (newPassword) body.password = newPassword;
      const res = await apiFetch(`/api/users/${resetTarget.id}/reset-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        throw new Error(b.detail || `Reset failed (${res.status})`);
      }
      const data = await res.json();
      setResetResult(data.new_password);
    } catch (e: unknown) {
      setResetError(e instanceof Error ? e.message : 'Reset failed');
    } finally {
      setResetting(false);
    }
  };

  const strength = passwordStrength(formData.password);

  return (
    <div className="p-lg space-y-lg">
      <div className="flex items-center justify-between">
        <SectionHeader title="Users" />
        {isAdmin && (
          <button onClick={openAdd} className="flex items-center gap-sm px-md py-sm rounded-lg text-body-sm font-medium bg-primary text-on-primary hover:bg-primary/90 transition-colors">
            <Plus className="w-4 h-4" />
            Add User
          </button>
        )}
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-on-surface-variant" />
        <input
          type="text"
          placeholder="Search users..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full pl-10 pr-4 py-sm rounded-lg bg-surface-container border border-outline-variant text-on-surface text-body-sm placeholder:text-on-surface-variant focus:outline-none focus:border-primary"
        />
      </div>

      {loading ? (
        <div className="text-center text-on-surface-variant py-xl">Loading users...</div>
      ) : error ? (
        <div className="text-center text-red-400 py-xl">{error}</div>
      ) : filtered.length === 0 ? (
        <EmptyState title={search ? 'No users match your search' : 'No users found'} message={search ? 'Try a different search term.' : 'Click "Add User" to create the first entry.'} />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-body-sm">
            <thead>
              <tr className="border-b border-outline-variant text-on-surface-variant text-[10px] uppercase tracking-wider">
                <th className="text-left py-sm px-md font-medium">Email</th>
                <th className="text-left py-sm px-md font-medium">Role</th>
                <th className="text-left py-sm px-md font-medium">Created</th>
                <th className="text-left py-sm px-md font-medium">User ID</th>
                {isAdmin && <th className="text-right py-sm px-md font-medium">Actions</th>}
              </tr>
            </thead>
            <tbody>
              {filtered.map((u) => {
                const isSelf = u.id === currentUser?.id;
                return (
                  <tr key={u.id} className="border-b border-outline-variant/30 hover:bg-surface-container-higher/50 transition-colors">
                    <td className="py-sm px-md text-on-surface font-medium">{u.email}</td>
                    <td className="py-sm px-md">
                      <span className={`inline-block px-xs py-0.5 rounded text-[11px] font-medium border ${ROLE_BADGE_CLASSES[u.role as Role] || 'bg-gray-500/15 text-gray-400 border-gray-500/30'}`}>
                        {ROLE_LABELS[u.role as Role] || u.role}
                      </span>
                    </td>
                    <td className="py-sm px-md text-on-surface-variant text-[11px]">{new Date(u.created_at).toLocaleDateString()}</td>
                    <td className="py-sm px-md text-on-surface-variant font-mono text-[11px]">{u.id}</td>
                    {isAdmin && (
                      <td className="py-sm px-md text-right">
                        <div className="flex items-center justify-end gap-sm">
                          <button onClick={() => openEdit(u)} className="p-1.5 rounded-md text-on-surface-variant hover:text-primary hover:bg-primary/10 transition-colors" title="Edit role">
                            <Pencil className="w-4 h-4" />
                          </button>
                          <button onClick={() => openReset(u)} className="p-1.5 rounded-md text-on-surface-variant hover:text-amber-400 hover:bg-amber-500/10 transition-colors" title="Reset password">
                            <KeyRound className="w-4 h-4" />
                          </button>
                          {!isSelf && (
                            <button onClick={() => confirmDelete(u)} className="p-1.5 rounded-md text-on-surface-variant hover:text-red-400 hover:bg-red-500/10 transition-colors" title="Delete">
                              <Trash2 className="w-4 h-4" />
                            </button>
                          )}
                        </div>
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {showForm && createPortal(
        <div style={{ position: 'fixed', inset: 0, zIndex: 50, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.4)' }} onClick={closeForm}>
          <div style={{ background: '#1d2027', width: '100%', maxWidth: '28rem', margin: '0 24px', borderRadius: '12px', border: '1px solid #424754', boxShadow: '0 25px 50px -12px rgba(0,0,0,0.5)', padding: '24px' }} onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
              <h3 className="font-label-caps text-label-caps text-on-surface uppercase tracking-widest">
                {editingId ? 'Edit User' : 'Add User'}
              </h3>
              <button onClick={closeForm} style={{ padding: '4px', borderRadius: '6px' }} className="text-on-surface-variant hover:text-on-surface hover:bg-surface-container-higher transition-colors">
                <X className="w-4 h-4" />
              </button>
            </div>

            {formError && (
              <div className="p-sm rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-body-sm" style={{ marginBottom: '16px' }}>{formError}</div>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {!editingId && (
                <div>
                  <label className="block text-[10px] uppercase tracking-wider text-on-surface-variant font-medium" style={{ marginBottom: '4px' }}>Email</label>
                  <input
                    type="email"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    style={{ width: '100%', padding: '8px 16px', borderRadius: '8px', border: '1px solid #424754', background: '#272a31', color: '#e1e2ec', fontSize: '13px' }}
                    className="placeholder:text-on-surface-variant focus:outline-none focus:border-primary"
                    placeholder="user@example.com"
                  />
                </div>
              )}

              {!editingId && (
                <div>
                  <label className="block text-[10px] uppercase tracking-wider text-on-surface-variant font-medium" style={{ marginBottom: '4px' }}>Password</label>
                  <div style={{ position: 'relative' }}>
                    <input
                      type={showPassword ? 'text' : 'password'}
                      value={formData.password}
                      onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                      style={{ width: '100%', padding: '8px 16px', paddingRight: '40px', borderRadius: '8px', border: '1px solid #424754', background: '#272a31', color: '#e1e2ec', fontSize: '13px' }}
                      className="placeholder:text-on-surface-variant focus:outline-none focus:border-primary"
                      placeholder="Minimum 8 characters"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      style={{ position: 'absolute', right: '8px', top: '50%', transform: 'translateY(-50%)', padding: '4px', borderRadius: '4px' }}
                      className="text-on-surface-variant hover:text-on-surface transition-colors"
                    >
                      {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                  {formData.password.length > 0 && (
                    <div style={{ marginTop: '4px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginBottom: '2px' }}>
                        <div style={{ display: 'flex', gap: '2px', flex: 1 }}>
                          {[1, 2, 3].map((i) => (
                            <div
                              key={i}
                              style={{ height: '4px', flex: 1, borderRadius: '9999px', transition: 'background-color 0.2s', backgroundColor: formData.password.length >= i * 4 ? undefined : 'rgba(194,198,214,0.2)' }}
                              className={formData.password.length >= i * 4 ? strength.color : ''}
                            />
                          ))}
                        </div>
                        <span className="text-[10px] text-on-surface-variant">{strength.label}</span>
                      </div>
                    </div>
                  )}
                  <p className="text-[10px] text-on-surface-variant" style={{ marginTop: '4px' }}>Must include uppercase, lowercase, numbers, and special characters.</p>
                </div>
              )}

              <div>
                <label className="block text-[10px] uppercase tracking-wider text-on-surface-variant font-medium" style={{ marginBottom: '4px' }}>Role</label>
                <select
                  value={formData.role}
                  onChange={(e) => setFormData({ ...formData, role: e.target.value as Role })}
                  style={{ width: '100%', padding: '8px 16px', borderRadius: '8px', border: '1px solid #424754', background: '#272a31', color: '#e1e2ec', fontSize: '13px' }}
                  className="focus:outline-none focus:border-primary"
                >
                  {ROLES.map((r) => (
                    <option key={r} value={r}>{ROLE_LABELS[r]}</option>
                  ))}
                </select>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '16px', marginTop: '24px' }}>
              <button onClick={closeForm} style={{ padding: '8px 16px', borderRadius: '8px', fontSize: '13px', fontWeight: 500 }} className="text-on-surface-variant hover:text-on-surface hover:bg-surface-container-higher transition-colors">
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                style={{ padding: '8px 16px', borderRadius: '8px', fontSize: '13px', fontWeight: 500, background: '#adc6ff', color: '#002e6a', opacity: saving ? 0.5 : 1 }}
              >
                {saving ? 'Saving...' : editingId ? 'Update User' : 'Create User'}
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}

      {deleteTarget && createPortal(
        <div style={{ position: 'fixed', inset: 0, zIndex: 50, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.4)' }} onClick={() => !deleting && setDeleteTarget(null)}>
          <div style={{ background: '#1d2027', width: '100%', maxWidth: '24rem', margin: '0 24px', borderRadius: '12px', border: '1px solid #424754', boxShadow: '0 25px 50px -12px rgba(0,0,0,0.5)', padding: '24px' }} onClick={(e) => e.stopPropagation()}>
            <h3 className="font-label-caps text-label-caps text-on-surface uppercase tracking-widest" style={{ marginBottom: '8px' }}>Delete User</h3>
            <p className="text-body-sm text-on-surface-variant" style={{ marginBottom: '8px' }}>
              Are you sure you want to delete <span className="text-on-surface font-medium">{deleteTarget.email}</span>?
            </p>
            <p className="text-[10px] text-on-surface-variant" style={{ marginBottom: '16px' }}>
              Sessions created by this user will become orphaned (no owner). They will still exist but won't be linked to any active user account.
            </p>

            {deleteError && (
              <div className="p-sm rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-body-sm" style={{ marginBottom: '16px' }}>{deleteError}</div>
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

      {resetTarget && createPortal(
        <div style={{ position: 'fixed', inset: 0, zIndex: 50, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.4)' }} onClick={() => { if (!resetting) { setResetTarget(null); setResetResult(null); setResetError(null); } }}>
          <div style={{ background: '#1d2027', width: '100%', maxWidth: '24rem', margin: '0 24px', borderRadius: '12px', border: '1px solid #424754', boxShadow: '0 25px 50px -12px rgba(0,0,0,0.5)', padding: '24px' }} onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
              <h3 className="font-label-caps text-label-caps text-on-surface uppercase tracking-widest">Reset Password</h3>
              <button onClick={() => { setResetTarget(null); setResetResult(null); setResetError(null); }} style={{ padding: '4px', borderRadius: '6px' }} className="text-on-surface-variant hover:text-on-surface hover:bg-surface-container-higher transition-colors">
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-body-sm text-on-surface-variant" style={{ marginBottom: '16px' }}>
              Reset password for <span className="text-on-surface font-medium">{resetTarget.email}</span>
            </p>

            {resetError && (
              <div className="p-sm rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-body-sm" style={{ marginBottom: '16px' }}>{resetError}</div>
            )}

            {resetResult ? (
              <div style={{ marginBottom: '16px' }}>
                <p className="text-body-sm text-on-surface-variant" style={{ marginBottom: '8px' }}>New password generated:</p>
                <div style={{ padding: '8px', borderRadius: '8px', background: '#272a31', border: '1px solid #424754', fontFamily: 'monospace', color: '#e1e2ec', fontSize: '13px', wordBreak: 'break-all' }}>{resetResult}</div>
                <p className="text-[10px] text-on-surface-variant" style={{ marginTop: '4px' }}>Copy this password now. It will not be shown again.</p>
              </div>
            ) : (
              <div style={{ marginBottom: '16px' }}>
                <button
                  onClick={() => handleResetPassword()}
                  disabled={resetting}
                  style={{ width: '100%', padding: '8px 16px', borderRadius: '8px', fontSize: '13px', fontWeight: 500, background: '#272a31', border: '1px solid #424754', color: '#e1e2ec' }}
                  className="hover:bg-surface-container-higher transition-colors disabled:opacity-50"
                >
                  {resetting ? 'Generating...' : 'Generate Random Password'}
                </button>
              </div>
            )}

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '16px' }}>
              <button onClick={() => { setResetTarget(null); setResetResult(null); setResetError(null); }} disabled={resetting} style={{ padding: '8px 16px', borderRadius: '8px', fontSize: '13px', fontWeight: 500 }} className="text-on-surface-variant hover:text-on-surface hover:bg-surface-container-higher transition-colors disabled:opacity-50">
                {resetResult ? 'Done' : 'Cancel'}
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}
