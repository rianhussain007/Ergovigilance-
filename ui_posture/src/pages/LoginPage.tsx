import { FormEvent, useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router';
import { Activity, Lock, Eye, EyeOff, Loader2, AlertTriangle, ArrowRight } from 'lucide-react';
import { useAuth } from '@/src/auth/AuthContext';
import { IndustrialBackdrop } from '@/src/components/common';
import Logo from '../components/common/Logo';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('operator@example.local');
  const [password, setPassword] = useState('OperatorPass123!');
  const [showPassword, setShowPassword] = useState(false);
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (user) return <Navigate to="/dashboard" replace />;

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const trimmed = email.trim();
    if (!trimmed) {
      setFieldError('Enter your email address.');
      return;
    }
    if (!EMAIL_RE.test(trimmed)) {
      setFieldError('Enter a valid email address, e.g. name@company.com.');
      return;
    }
    if (!password) {
      setFieldError('Enter your password.');
      return;
    }
    setFieldError(null);
    setServerError(null);
    setLoading(true);
    try {
      await login(trimmed, password);
      navigate('/dashboard', { replace: true });
    } catch (err) {
      setServerError(err instanceof Error ? err.message : 'Sign in failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const inputClass = (invalid: boolean) =>
    `w-full h-11 rounded-xl border bg-slate-50 dark:bg-surface px-md text-body-sm text-slate-900 dark:text-on-surface outline-none transition-all ${
      invalid
        ? 'border-red-300 dark:border-danger/60 focus:border-red-500 focus:ring-2 focus:ring-red-500/20'
        : 'border-slate-200 dark:border-outline-variant/80 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/15 hover:border-slate-300 dark:hover:border-outline'
    }`;

  return (
    <div className="relative min-h-screen bg-slate-50 dark:bg-surface text-slate-900 dark:text-on-surface grid place-items-center p-lg overflow-hidden">
      {/* Industrial backdrop — shared with every public page */}
      <IndustrialBackdrop accentLine />

      <main className="relative w-[400px] max-w-[90vw] animate-fade-in">
        <form onSubmit={handleSubmit} noValidate className="rounded-2xl border border-slate-200 dark:border-outline-variant/60 bg-white dark:bg-surface-container shadow-xl shadow-slate-200/50 dark:shadow-2xl dark:shadow-black/20 overflow-hidden">
          {/* Brand header — wordmark links back to the marketing homepage */}
          <div className="px-xl pt-xl pb-md space-y-md">
            <Link to="/" className="flex items-center gap-sm group w-fit">
              <Logo className="h-11 w-auto" variant="auto" />
            </Link>
            <div>
              <h1 className="text-headline-md font-bold text-slate-900 dark:text-on-surface">Sign in</h1>
              <p className="text-body-sm text-slate-500 dark:text-on-surface-variant mt-1">Sign in with your assigned role.</p>
            </div>
          </div>

          <div className="px-xl pb-xl space-y-md">
            <div className="space-y-xs">
              <label htmlFor="login-email" className="block font-label-caps text-[10px] uppercase tracking-widest text-slate-400 dark:text-on-surface-variant">
                Email
              </label>
              <input
                id="login-email"
                type="email"
                autoComplete="username"
                autoFocus
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  if (fieldError) setFieldError(null);
                }}
                className={inputClass(!!fieldError)}
                aria-invalid={!!fieldError}
                aria-describedby={fieldError ? 'login-field-error' : undefined}
              />
            </div>

            <div className="space-y-xs">
              <label htmlFor="login-password" className="block font-label-caps text-[10px] uppercase tracking-widest text-slate-400 dark:text-on-surface-variant">
                Password
              </label>
              <div className="relative">
                <input
                  id="login-password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    if (fieldError) setFieldError(null);
                  }}
                  className={`${inputClass(!!fieldError)} pr-10`}
                  aria-invalid={!!fieldError}
                  aria-describedby={fieldError ? 'login-field-error' : undefined}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-md text-slate-400 dark:text-on-surface-variant hover:text-slate-600 dark:hover:text-on-surface hover:bg-slate-100 dark:hover:bg-surface-variant/40 transition-colors"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              <div className="flex justify-end">
                <Link to="/forgot-password" className="text-body-sm text-slate-500 dark:text-on-surface-variant hover:text-blue-600 dark:hover:text-primary transition-colors">
                  Forgot password?
                </Link>
              </div>
            </div>

            {/* Error region — inline under the form; role=alert announces to
                screen readers. Server messages are the backend's own generic
                strings ("Invalid email or password", lockout notices). */}
            {(fieldError || serverError) && (
              <div
                id="login-field-error"
                role="alert"
                className="flex items-start gap-sm rounded-xl border border-red-200 dark:border-danger/40 bg-red-50 dark:bg-danger/10 px-md py-sm"
              >
                <AlertTriangle className="h-4 w-4 text-red-500 dark:text-danger shrink-0 mt-0.5" />
                <p className="text-body-sm text-red-600 dark:text-danger">{fieldError ?? serverError}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full h-12 rounded-xl bg-blue-600 dark:bg-primary text-white dark:text-on-primary text-body-sm font-semibold hover:bg-blue-700 dark:hover:shadow-lg dark:hover:shadow-primary/25 disabled:opacity-60 disabled:hover:shadow-none flex items-center justify-center gap-sm transition-all active:scale-[0.98]"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Lock className="h-4 w-4" />}
              {loading ? 'Signing in…' : 'Sign In'}
            </button>

            <div className="pt-md border-t border-slate-100 dark:border-outline-variant/60">
              <p className="text-center text-body-sm text-slate-500 dark:text-on-surface-variant">
                Don’t have access yet?{' '}
                <Link to="/request-pilot" className="inline-flex items-center gap-0.5 font-semibold text-blue-600 dark:text-primary hover:underline">
                  Request a pilot <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </p>
            </div>
          </div>
        </form>

        <p className="mt-lg text-center text-[11px] text-slate-400 dark:text-on-surface-variant/60">
          Heuristic risk thresholds · Not a medical device · Video never leaves your building
        </p>
      </main>
    </div>
  );
}
