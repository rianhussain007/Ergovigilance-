import { Link } from 'react-router';
import { Activity, ArrowLeft, ArrowRight, UserCog } from 'lucide-react';
import { IndustrialBackdrop } from '@/src/components/common';

export default function ForgotPassword() {
  return (
    <div className="relative min-h-screen bg-surface text-on-surface grid place-items-center p-lg overflow-hidden">
      {/* Industrial backdrop — shared with every public page */}
      <IndustrialBackdrop accentLine />

      <main className="relative w-[420px] max-w-[90vw] animate-fade-in">
        <div className="rounded-xl border border-outline-variant bg-surface-container shadow-2xl overflow-hidden">
          <div className="px-xl pt-xl pb-md space-y-md">
            <Link to="/" className="flex items-center gap-sm group w-fit">
              <div className="h-11 w-11 rounded-lg bg-primary/15 text-primary grid place-items-center group-hover:bg-primary/25 transition-colors">
                <Activity className="h-5 w-5" />
              </div>
              <span className="text-headline-md font-bold text-on-surface">ErgoVigilance</span>
            </Link>
            <div>
              <h1 className="text-headline-md font-bold text-on-surface">Forgot your password?</h1>
              <p className="text-body-sm text-on-surface-variant mt-1">
                Resets are handled on your own network — no email, no third party.
              </p>
            </div>
          </div>

          <div className="px-xl pb-xl space-y-md">
            <div className="rounded-lg border border-outline-variant bg-surface px-md py-sm flex items-start gap-sm">
              <UserCog className="h-4 w-4 text-primary shrink-0 mt-0.5" />
              <p className="text-body-sm text-on-surface-variant leading-relaxed">
                Ask your ErgoVigilance administrator to reset your password — they can do it
                from the Users page in a few seconds. That keeps access control entirely
                on your site.
              </p>
            </div>

            <Link
              to="/login"
              className="w-full h-11 rounded-lg bg-primary text-on-primary text-body-sm font-semibold hover:opacity-90 flex items-center justify-center gap-sm transition-opacity"
            >
              <ArrowLeft className="h-4 w-4" /> Back to Sign In
            </Link>

            <p className="text-center text-body-sm text-on-surface-variant">
              Don’t have access yet?{' '}
              <Link to="/request-pilot" className="inline-flex items-center gap-0.5 font-semibold text-primary hover:underline">
                Request a pilot <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </p>
          </div>
        </div>

        <p className="mt-lg text-center text-[11px] text-on-surface-variant/80">
          Heuristic risk thresholds · Not a medical device · Video never leaves your building
        </p>
      </main>
    </div>
  );
}
