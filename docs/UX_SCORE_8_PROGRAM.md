# Program: every UI/UX dimension ≥ 8/10

**Date:** 2026-10-02 · **Owner:** engineering · **Companion:** [`docs/UI_UX_ENTERPRISE_AUDIT.md`](UI_UX_ENTERPRISE_AUDIT.md) (findings F-UX-01…20, evidence)

## Goal

The audit scored ten dimensions. Six sit below 8. This program takes each below-8 dimension to ≥ 8 with
machine-checkable acceptance criteria, and states plainly which dimensions **cannot** be closed by repository work.

| Dimension | Audit | Target | Closed by this program? |
|---|---|---|---|
| Feature breadth | 8.0 | ≥ 8 | already there — keep it (regression gate: route/sidebar test) |
| Engineering & verification | 7.5 | 8.5 | yes — gates in CI (§W5) |
| Core flow (login → monitor → report) | 6.0 | 8.5 | yes — F-UX-01/02/03 fixes + tests (§W1, §W2) |
| IA / navigation | 5.0 | 8.0 | mostly — access-denied states, palette filtering, one activation model (§W2, §W3) |
| Visual design | 6.5 | 8.0 | partly — tokens-only rule + dark-surface fixes; brand/design investment still needed (§W6) |
| Accessibility | 4.0 | 8.0 | yes for code (WCAG A/AA mechanics + axe-style gates); needs one assisted user test for 9+ (§W4) |
| State / data robustness | 3.0 | 8.5 | yes — in-repo data layer, visibility-aware polling, timeouts, degraded states (§W1) |
| Performance | 5.5 | 8.0 | yes — chunking + measured budgets (§W6) |
| Trust / compliance UX | 5.0 | 8.0 | code side yes (§W3); signed DPIA/legal review remains external |
| Enterprise readiness | 3.0 | 8.0 | roll-up of the above + external items below |

**External, cannot be closed in-repo (stays honest on the scorecard):** usability testing with real operators
(raises Accessibility and IA confidence beyond 8), legal counsel review of Terms/Privacy/DPA, third-party
pen-test, and a real customer deployment for performance/RUM evidence.

## Status — shipped 2026-10-02

| Workstream | Status | Gate that proves it |
|---|---|---|
| W1 data layer | **shipped** | `apiClient.test.ts` (18) + `usePolling.test.tsx` (9): timeout→`ApiError('timeout')`, retry/backoff, hidden-tab pause, degraded-with-last-good, signed-out short-circuit. Data `setInterval` sites: 30 → 0 outside the primitive (remaining 11 are clocks/animations, allowlisted). |
| W2 permissions | **shipped** | `capabilities.test.ts` (10) incl. a test that parses `backend_api/app/api/report_digest.py` and fails if the mirrored role set drifts; `routes.test.ts` (+141) asserts every `rolePaths` entry is a declared `<Route>`; `guards.test.tsx` asserts the refusal is explained and announced. |
| W3 activation + trust | **shipped** | `activation.test.ts` (8) incl. legacy-flag migration and locale key parity; `claims.test.ts` (7) incl. banned vintages, 87.6% qualifier, signup-vs-backend camera entitlement, ROI gate. |
| W4 accessibility | **shipped (code)** | `headings.test.ts` (42 pages, one `<h1>` each); `a11yFlows.test.tsx` (dialog semantics, status/alert roles, announcer). |
| W5 gates | **shipped** | `ux_guards.mjs`: planted-violation probe produced 5 violations and exit 1; clean tree exits 0. `check_bundle_budget.mjs` in CI with the frontend job. |
| W6 performance/visual | **shipped (measured)** | Entry chunk 521 → 139 kB raw (161 → 41 kB gzip); no Vite >500 kB warning; total 456 kB gzip; budget gate green. |
| W7 usability evidence | **not started (external)** | needs a real operator session — nothing in the repo can substitute. |

Post-wave verification: `npx tsc --noEmit` clean · `npx vitest run` **275/275, 14 files** (106 at audit) ·
`npm run build` clean · `node scripts/ux_guards.mjs` 0 violations · `node scripts/check_bundle_budget.mjs` within budget.

Honest gaps after this pass (do not score these as done): the 24 px touch-target audit on the operator live
screen; raw-hex debt is ratcheted rather than removed; `?token=` media URLs remain the F-UX-05 debt (allowlisted,
no new call sites); Terms/Privacy still need counsel; RUM comes from a real deployment.

## Workstreams

### W1 — Data layer and state robustness (state 3.0 → 8.5)
- `apiClient`: per-request timeout (15 s), typed `ApiError` (kind: timeout/network/auth/forbidden/not-found/
  server/rate-limited/unknown), `userMessage` mapping, 401 handling preserved; `friendlyHttpError` delegates.
- `usePolledResource<T>` hook replacing five copy-pasted poll hooks: first-load retry with backoff, consecutive-
  failure backoff (cap 4×), **pause while the tab is hidden** + immediate refresh on return, no interval stacking
  (setTimeout chain), unmount safety, `degraded` flag separated from first-load `error`.
- Migrate `useAlerts`, `useRecommendations`, `useContextSnapshot`, `useHistory`, `useLiveTimeline`,
  `useDashboard`, `useSessionLifecycle` (status polling), plus page-level pollers (SystemHealth ×4,
  CloudCameras ×2, Status, WorkerSelfView, ManagerDashboard, MultiCamera, DeploymentCenter, SetupWizard,
  OnboardingFlow, DashboardPage summary) onto the shared primitives.
- Acceptance: vitest proves timeout→ApiError kind, hidden-tab pause, failure backoff, degraded-without-crash;
  killing the backend shows a degraded/error state, never an infinite spinner.

### W2 — Permission contract and navigation (core flow 6.0 → 8.5, IA 5.0 → 7)
- `src/auth/capabilities.ts`: one capability map (`capability → roles`) + `useCapability` hook, tested against
  `rolePaths` and the backend permission matrix at the page level.
- Gate the mismatched calls found in F-UX-03: `/setup` wizard, Reports nightly digest, Settings camera section;
  remove `/setup` from operator's allowed paths **or** render the capability-denied state (chosen: deny state,
  so the page explains itself instead of 403-polling).
- Replace the silent `Layout` bounce with an in-shell **access-denied** page naming the required role and the
  request-access path; keep `/` → `/dashboard` for signed-in users; unknown URLs keep the 404.
- Command palette list becomes role-filtered (`SearchModal`).
- Acceptance: route walk for all 4 roles has zero silent redirects and zero console 403s on reachable pages
  (scripted assertion in the frontend test suite).

### W3 — One activation model + trust surfaces (IA + trust)
- Single persisted activation state (`ergovigilance_activation`) written by the existing wizard/checklist
  entry points; `/onboarding` and the modal read it; duplicate journeys become deep links (no new wizard).
- `/legal` served in-app: Terms + Privacy, clearly marked **Draft pending counsel review**, containing the
  product's real commitments (pose keypoints only, on-prem video, retention, erasure, consent, not a medical
  device). Signup/Login link here; signup "3 cameras" → 4 (matches pilot entitlement).
- ROI/Analytics minimum-data gate: currency/ROI figures only with a real dataset — **shipped as ≥ 10 sessions and
  ≥ 5 monitored hours** (`MIN_SESSIONS_FOR_ROI` / `MIN_HOURS_FOR_ROI`); below that the page shows the counts it
  does have, the thresholds, and the method + assumptions behind the estimate.
- i18n honesty: Settings + tour copy states exact coverage until full localisation lands.
- Acceptance: `claims.test.ts` fails the build on any banned vintage (94.1/97.6/88.6/86.4/76.9) or a
  risk-bearing page missing "screening aid, not a medical device"; `/legal` reachable from every acceptance point.

### W4 — Accessibility mechanics (4.0 → 8.0)
- Dialog semantics for every overlay (notification drawer, AI panel, tour, keyboard help, exports/alerts panels):
  `role="dialog"`, `aria-modal`, labelled, Escape, focus trap/restore (Drawer already done).
- `LoadingCard` → `role="status"`/`aria-busy`; `ErrorCard` → `role="alert"`; route changes announced via the
  existing `#a11y-announcer`; one `<h1>` per page (LiveMonitoring/Workers currently start at h2/eyebrow).
- ≥ 24 px targets audit on the operator live screen; text floor 11 px non-interactive / 13 px body.
- Acceptance: `a11yFlows.test.tsx` extended (dialog semantics, announcer, single h1), plus a static rule that
  every `src/pages/*.tsx` renders exactly one `<h1>`; manual keyboard pass documented.

### W5 — Gates that keep the above true (engineering 7.5 → 8.5)
- `ui_posture/scripts/ux_guards.mjs` (zero-dependency static gate): banned claims; `window.confirm`;
  `window.location.reload`; raw hex in `pages/`+`components/` (allowlist with written reasons); `?token=` media
  URLs (allowlisted until short-lived media tokens land); `<img>` without `alt`; `role="dialog"` overlays without
  `aria-modal`; `setInterval(` outside the approved polling helper.
- `ui_posture/scripts/check_bundle_budget.mjs`: per-chunk and total gzip budgets computed from `dist/`.
- CI frontend job runs: typecheck → vitest → ux_guards → build → bundle budget.
- Acceptance: each gate fails on a planted violation (verified locally) and passes on `master`.

### W6 — Visual system and performance (visual 6.5 → 8, perf 5.5 → 8)
- Remove the remaining hardcoded dark surfaces (`RouteErrorBoundary`, `CloudCamerasPage` modal, public dark-only
  pages get a documented light-mode story), enforce tokens via W5's hex guard.
- `vite.config.ts` `manualChunks`: vendor-react / vendor-charts / vendor-motion / vendor-icons; measured budget.
- Acceptance: entry chunk gzip under budget and Vite's >500 kB warning gone; budget gate in CI.

### W7 — Activation usability evidence (optional, external)
- Operator test script (5 tasks × 3 operators, timings + incidents) feeding `docs/pilot/`; moves Accessibility
  and IA from "code-complete" to "proven".

## Sequencing and definition of done

1. W1 (data layer) → W2 (permissions) → W3 (trust) → W4 (a11y) → W5 (gates) → W6 (perf/visual).
2. Definition of done per workstream: code + tests + gate + evidence line in
   [`docs/UI_UX_ENTERPRISE_AUDIT.md`](UI_UX_ENTERPRISE_AUDIT.md) updated from "planned" to "shipped".
3. Phase 1 (this session): W1, W2, W3, W4 core, W5, W6 — with `tsc --noEmit`, `vitest run`, `npm run build`,
   `node scripts/ux_guards.mjs`, `node scripts/check_bundle_budget.mjs` all green.
4. Scores are re-stated only from evidence: a dimension moves to ≥ 8 when its gate exists and passes, not when
   the code merely changed.

## Honest residual risks

- W1's "no infinite spinner" is proven against a stopped backend locally; distributed network partitions still
  need a real deployment to measure.
- W4's 8.0 is WCAG-mechanics + static gates; 9+ needs the assisted user test (W7).
- W3's legal pages are *drafts*; procurement will still require counsel review. The program does not change any
  Safe Claims language.
