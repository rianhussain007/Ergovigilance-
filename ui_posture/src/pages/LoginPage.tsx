import { FormEvent, useState } from 'react';
import { Navigate, useNavigate } from 'react-router';
import { Activity, Lock } from 'lucide-react';
import { useAuth } from '@/src/auth/AuthContext';

export default function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('operator@example.local');
  const [password, setPassword] = useState('OperatorPass123!');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (user) return <Navigate to="/dashboard" replace />;

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await login(email, password);
      navigate('/dashboard', { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-surface text-on-surface grid place-items-center p-lg">
      <form onSubmit={handleSubmit} style={{ width: '400px', maxWidth: '90vw' }} className="rounded-lg border border-outline-variant bg-surface-container p-xl shadow-2xl space-y-lg">
        <div className="space-y-sm">
          <div className="h-11 w-11 rounded-lg bg-primary/15 text-primary grid place-items-center">
            <Activity className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-headline-md font-bold text-on-surface">ErgoVigilance</h1>
            <p className="text-body-sm text-on-surface-variant">Sign in with your assigned role.</p>
          </div>
        </div>

        <label className="block space-y-xs">
          <span className="font-label-caps text-[10px] uppercase tracking-widest text-on-surface-variant">Email</span>
          <input
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full h-10 rounded border border-outline-variant bg-surface px-md text-body-sm text-on-surface outline-none focus:border-primary"
            autoComplete="username"
          />
        </label>

        <label className="block space-y-xs">
          <span className="font-label-caps text-[10px] uppercase tracking-widest text-on-surface-variant">Password</span>
          <input
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            type="password"
            className="w-full h-10 rounded border border-outline-variant bg-surface px-md text-body-sm text-on-surface outline-none focus:border-primary"
            autoComplete="current-password"
          />
        </label>

        {error && <p className="text-body-sm text-red-400">{error}</p>}

        <button
          disabled={loading}
          className="w-full h-10 rounded bg-primary text-on-primary text-body-sm font-semibold hover:bg-primary-hover disabled:opacity-60 flex items-center justify-center gap-sm"
        >
          <Lock className="h-4 w-4" />
          {loading ? 'Signing in...' : 'Sign In'}
        </button>
      </form>
    </div>
  );
}
