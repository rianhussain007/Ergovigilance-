import { Link } from 'react-router';
import { ArrowLeft, FileText, ShieldCheck } from 'lucide-react';
import Logo from '../components/common/Logo';

/**
 * In-app legal page (audit F-UX-08): the signup form linked to /legal, which
 * had no route — visitors hit the app's error boundary or a blank screen at the
 * exact moment they were asked to accept terms.
 *
 * The copy below is a working draft that describes what the product actually
 * does today (on-premise pose analysis, role-based access, no medical claims).
 * It is deliberately not presented as a finished agreement: it must be reviewed
 * by counsel before commercial use, and the page says so in the UI rather than
 * in a comment.
 */
export default function LegalPage() {
  return (
    <div className="min-h-screen bg-[#0b0f14] text-slate-300">
      <nav className="border-b border-white/5 bg-[#0b0f14]/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-4">
          <Link to="/" className="flex items-center gap-3">
            <Logo className="h-8 w-auto" variant="light" />
          </Link>
          <Link
            to="/signup"
            className="flex items-center gap-2 text-xs text-slate-400 transition-colors hover:text-white"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to sign up
          </Link>
        </div>
      </nav>

      <main className="mx-auto max-w-4xl space-y-8 px-6 py-12">
        <header className="space-y-3">
          <h1 className="text-3xl font-bold text-white">Terms &amp; Privacy</h1>
          <p className="text-sm text-slate-400">
            What ErgoVigilance does with your data, and what it is — and is not — responsible for.
          </p>
        </header>

        <div
          role="note"
          className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-200"
        >
          <p className="font-bold">Draft — pending legal review</p>
          <p className="mt-1 text-amber-200/80">
            This document is a working draft prepared by the product team. It is <em>not</em> a
            binding agreement, it has not been reviewed by counsel, and it does not describe
            certifications we do not hold. A reviewed version will replace it before commercial use;
            pilot deployments should use the signed pilot agreement instead.
          </p>
        </div>

        <section className="space-y-3">
          <h2 className="flex items-center gap-2 text-xl font-bold text-white">
            <FileText className="h-5 w-5 text-cyan-400" />
            Terms of service (draft)
          </h2>
          <ul className="list-disc space-y-2 pl-5 text-sm leading-relaxed">
            <li>
              <strong className="text-slate-200">Screening aid, not a medical device.</strong>{' '}
              ErgoVigilance analyses posture from camera frames and reports ergonomic risk bands. It
              does not diagnose, treat or prevent any medical condition, and its output is not a
              substitute for a qualified ergonomist, safety officer or clinician.
            </li>
            <li>
              <strong className="text-slate-200">Pilot use.</strong> Pilot accounts are provisioned
              for evaluation inside a single facility. Availability, accuracy and feature scope during
              a pilot may change without notice, and pilot data may be reset on request.
            </li>
            <li>
              <strong className="text-slate-200">Your responsibilities.</strong> You are responsible
              for lawful camera placement, for notifying workers whose posture is monitored, for
              obtaining any consent your jurisdiction requires, and for acting (or not acting) on the
              risk bands the system reports.
            </li>
            <li>
              <strong className="text-slate-200">No numeric accuracy guarantee.</strong> Published
              model figures describe a specific evaluation set (see the Validation page and model
              card). Field accuracy depends on camera angle, lighting, clothing and body type.
            </li>
          </ul>
        </section>

        <section className="space-y-3">
          <h2 className="flex items-center gap-2 text-xl font-bold text-white">
            <ShieldCheck className="h-5 w-5 text-emerald-400" />
            Privacy policy (draft)
          </h2>
          <ul className="list-disc space-y-2 pl-5 text-sm leading-relaxed">
            <li>
              <strong className="text-slate-200">Where processing happens.</strong> The on-premise
              engine runs on your own hardware; pose analysis happens locally and raw video is not
              uploaded to us. If you configure cloud cameras, their stream is processed by the cloud
              core you deploy, in infrastructure you control.
            </li>
            <li>
              <strong className="text-slate-200">What is stored.</strong> Per-session posture
              metrics (risk band, counts, timings), keypoints where configured, worker identifiers you
              create, review notes and audit-log entries. Video recordings are retained only under the
              retention window configured on your deployment and can be deleted from the UI.
            </li>
            <li>
              <strong className="text-slate-200">Who can see it.</strong> Access is role-based
              (operator, supervisor, safety manager, admin) and every privileged action is written to
              the audit trail. You administer your own users.
            </li>
            <li>
              <strong className="text-slate-200">Retention and deletion.</strong> We do not sell
              posture data or use it to train third-party models. Ask your pilot contact to export or
              delete a worker&rsquo;s data, or remove it from the dashboard; deletions cascade to
              sessions, alerts and derived analytics.
            </li>
            <li>
              <strong className="text-slate-200">Security.</strong> Tokens are scoped and expire,
              traffic is authenticated, and actions are logged. We do not claim third-party
              certifications (for example SOC 2 or ISO 27001) that have not been completed — a
              security questionnaire response is available on request.
            </li>
          </ul>
        </section>

        <section className="space-y-3">
          <h2 className="text-xl font-bold text-white">Questions</h2>
          <p className="text-sm leading-relaxed">
            Data-handling questions, deletion requests and security questionnaires:{' '}
            <Link to="/request-pilot" className="text-cyan-400 hover:underline">
              contact the team
            </Link>
            .
          </p>
        </section>

        <p className="border-t border-white/10 pt-6 text-xs text-slate-500">
          Last updated: October 2026 · Draft version 0.1 · reviewed by counsel: no
        </p>
      </main>
    </div>
  );
}
