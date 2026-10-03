import { FormEvent, useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router';
import { Building2, Mail, Lock, User, Loader2, AlertTriangle, CheckCircle, Eye, EyeOff, ArrowRight } from 'lucide-react';
import { useAuth, type AuthUser } from '@/src/auth/AuthContext';
import { resetActivation } from '@/src/services/activation';
import { IndustrialBackdrop } from '@/src/components/common';
import Logo from '../components/common/Logo';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const INDUSTRIES = [
  'Manufacturing',
  'Automotive',
  'Electronics',
  'Pharmaceuticals',
  'Food & Beverage',
  'Construction',
  'Logistics & Warehousing',
  'Healthcare',
  'Other',
];

const COUNTRIES = [
  { code: 'IN', label: 'India 🇮🇳' },
  { code: 'US', label: 'United States 🇺🇸' },
  { code: 'DE', label: 'Germany 🇩🇪' },
  { code: 'JP', label: 'Japan 🇯🇵' },
  { code: 'GB', label: 'United Kingdom 🇬🇧' },
  { code: 'CN', label: 'China 🇨🇳' },
  { code: 'BR', label: 'Brazil 🇧🇷' },
  { code: 'OTHER', label: 'Other' },
];

export default function SignupPage() {
  const { user, adoptSession } = useAuth();
  const navigate = useNavigate();
  const [orgName, setOrgName] = useState('');
  const [industry, setIndustry] = useState('Manufacturing');
  const [country, setCountry] = useState('IN');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [agreeTerms, setAgreeTerms] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (user) return <Navigate to="/dashboard" replace />;

  const passwordStrength = (pw: string): { label: string; color: string; width: string } => {
    let score = 0;
    if (pw.length >= 8) score++;
    if (pw.length >= 12) score++;
    if (/[A-Z]/.test(pw)) score++;
    if (/[0-9]/.test(pw)) score++;
    if (/[^A-Za-z0-9]/.test(pw)) score++;
    if (score <= 1) return { label: 'Weak', color: 'bg-red-500', width: '20%' };
    if (score <= 2) return { label: 'Fair', color: 'bg-orange-500', width: '40%' };
    if (score <= 3) return { label: 'Good', color: 'bg-yellow-500', width: '60%' };
    if (score <= 4) return { label: 'Strong', color: 'bg-blue-500', width: '80%' };
    return { label: 'Very Strong', color: 'bg-green-500', width: '100%' };
  };

  const pw = passwordStrength(password);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!orgName.trim()) { setError('Organization name is required.'); return; }
    if (!EMAIL_RE.test(email.trim())) { setError('Enter a valid email address.'); return; }
    if (password.length < 8) { setError('Password must be at least 8 characters.'); return; }
    if (!agreeTerms) { setError('You must agree to the Terms of Service.'); return; }

    setError(null);
    setLoading(true);
    try {
      const res = await fetch('/api/auth/signup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          organization_name: orgName.trim(),
          industry,
          country,
          email: email.trim(),
          password,
          full_name: fullName.trim(),
          agree_terms: agreeTerms,
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || 'Signup failed. Please try again.');
      }
      const data = await res.json();
      // Adopt the returned session through AuthContext (the canonical
      // `ergovigilance_auth` record). Writing legacy keys here used to leave
      // the app state null, so the guard bounced the new admin back to /login.
      adoptSession(data.token, data.user as AuthUser);
      // A fresh organization must see first-run onboarding: clear the
      // activation state a previous account left in this browser (audit
      // F-UX-17 — this is the one activation store all journeys read).
      resetActivation();
      navigate('/onboarding', { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Signup failed.');
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
      <IndustrialBackdrop accentLine />

      <main className="relative w-[480px] max-w-[95vw] animate-fade-in" id="main-content">
        <form onSubmit={handleSubmit} noValidate aria-label="Create your ErgoVigilance account" className="rounded-2xl border border-slate-200 dark:border-outline-variant/60 bg-white dark:bg-surface-container shadow-xl shadow-slate-200/50 dark:shadow-2xl dark:shadow-black/20 overflow-hidden">
          {/* Brand header */}
          <div className="px-xl pt-xl pb-md space-y-md">
            <Link to="/" className="flex items-center gap-sm group w-fit">
              <Logo className="h-11 w-auto" variant="light" />
            </Link>
            <div>
              <h1 className="text-headline-md font-bold text-slate-900 dark:text-on-surface">Create your account</h1>
              <p className="text-body-sm text-slate-500 dark:text-on-surface-variant mt-1">
                Start your free pilot — 4 cameras, 50 workers, no credit card required.
              </p>
            </div>
          </div>

          <div className="px-xl pb-xl space-y-md">
            {/* Organization Name */}
            <div className="space-y-xs">
              <label htmlFor="signup-org" className="block font-label-caps text-[10px] uppercase tracking-widest text-slate-400 dark:text-on-surface-variant">
                Organization Name
              </label>
              <div className="relative">
                <Building2 className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                <input
                  id="signup-org"
                  type="text"
                  autoFocus
                  value={orgName}
                  onChange={(e) => { setOrgName(e.target.value); if (error) setError(null); }}
                  placeholder="e.g. Acme Manufacturing"
                  className={`${inputClass(!!error && !orgName)} pl-10`}
                />
              </div>
            </div>

            {/* Full Name */}
            <div className="space-y-xs">
              <label htmlFor="signup-name" className="block font-label-caps text-[10px] uppercase tracking-widest text-slate-400 dark:text-on-surface-variant">
                Your Name
              </label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                <input
                  id="signup-name"
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="e.g. Rajesh Kumar"
                  className={`${inputClass(false)} pl-10`}
                />
              </div>
            </div>

            {/* Email */}
            <div className="space-y-xs">
              <label htmlFor="signup-email" className="block font-label-caps text-[10px] uppercase tracking-widest text-slate-400 dark:text-on-surface-variant">
                Work Email
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                <input
                  id="signup-email"
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => { setEmail(e.target.value); if (error) setError(null); }}
                  placeholder="you@company.com"
                  className={`${inputClass(!!error && (!email || !EMAIL_RE.test(email)))} pl-10`}
                />
              </div>
            </div>

            {/* Password */}
            <div className="space-y-xs">
              <label htmlFor="signup-password" className="block font-label-caps text-[10px] uppercase tracking-widest text-slate-400 dark:text-on-surface-variant">
                Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                <input
                  id="signup-password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => { setPassword(e.target.value); if (error) setError(null); }}
                  placeholder="At least 8 characters"
                  className={`${inputClass(!!error && password.length < 8)} pl-10 pr-10`}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(v => !v)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-md text-slate-400 hover:text-slate-600 dark:hover:text-on-surface hover:bg-slate-100 dark:hover:bg-surface-variant/40 transition-colors"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {password.length > 0 && (
                <div className="flex items-center gap-2 mt-1">
                  <div className="flex-1 h-1.5 rounded-full bg-slate-200 dark:bg-surface-variant overflow-hidden">
                    <div className={`h-full rounded-full transition-all duration-300 ${pw.color}`} style={{ width: pw.width }} />
                  </div>
                  <span className="text-[10px] font-medium text-slate-400">{pw.label}</span>
                </div>
              )}
            </div>

            {/* Industry + Country row */}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-xs">
                <label htmlFor="signup-industry" className="block font-label-caps text-[10px] uppercase tracking-widest text-slate-400 dark:text-on-surface-variant">
                  Industry
                </label>
                <select
                  id="signup-industry"
                  value={industry}
                  onChange={(e) => setIndustry(e.target.value)}
                  className={inputClass(false)}
                >
                  {INDUSTRIES.map(i => <option key={i} value={i}>{i}</option>)}
                </select>
              </div>
              <div className="space-y-xs">
                <label htmlFor="signup-country" className="block font-label-caps text-[10px] uppercase tracking-widest text-slate-400 dark:text-on-surface-variant">
                  Country
                </label>
                <select
                  id="signup-country"
                  value={country}
                  onChange={(e) => setCountry(e.target.value)}
                  className={inputClass(false)}
                >
                  {COUNTRIES.map(c => <option key={c.code} value={c.code}>{c.label}</option>)}
                </select>
              </div>
            </div>

            {/* Terms checkbox */}
            <label className="flex items-start gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={agreeTerms}
                onChange={(e) => { setAgreeTerms(e.target.checked); if (error) setError(null); }}
                className="mt-1 h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
              />
              <span className="text-xs text-slate-500 dark:text-on-surface-variant leading-relaxed">
                I agree to the{' '}
                <Link to="/legal" className="text-blue-600 dark:text-primary hover:underline">Terms of Service</Link>
                {' '}and{' '}
                <Link to="/legal" className="text-blue-600 dark:text-primary hover:underline">Privacy Policy</Link>.
                This is a safety screening tool — not a medical device.
              </span>
            </label>

            {/* Error */}
            {error && (
              <div role="alert" className="flex items-start gap-sm rounded-xl border border-red-200 dark:border-danger/40 bg-red-50 dark:bg-danger/10 px-md py-sm">
                <AlertTriangle className="h-4 w-4 text-red-500 dark:text-danger shrink-0 mt-0.5" />
                <p className="text-body-sm text-red-600 dark:text-danger">{error}</p>
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              className="w-full h-12 rounded-xl bg-blue-600 dark:bg-primary text-white dark:text-on-primary text-body-sm font-semibold hover:bg-blue-700 dark:hover:shadow-lg dark:hover:shadow-primary/25 disabled:opacity-60 disabled:hover:shadow-none flex items-center justify-center gap-sm transition-all active:scale-[0.98]"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
              {loading ? 'Creating your account…' : 'Start Free Pilot'}
            </button>

            <div className="pt-md border-t border-slate-100 dark:border-outline-variant/60">
              <p className="text-center text-body-sm text-slate-500 dark:text-on-surface-variant">
                Already have an account?{' '}
                <Link to="/login" className="inline-flex items-center gap-0.5 font-semibold text-blue-600 dark:text-primary hover:underline">
                  Sign in <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </p>
            </div>
          </div>
        </form>

        <p className="mt-lg text-center text-[11px] text-slate-400 dark:text-on-surface-variant/60">
          Free pilot · No credit card · 4 cameras · 50 workers · Local processing
        </p>
      </main>
    </div>
  );
}
