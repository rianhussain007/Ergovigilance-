# UI/UX Enterprise Readiness Audit — `ui_posture/` (whole website flow)

**Date:** 2026-10-02
**Scope:** every user-facing surface in `ui_posture/` — public marketing pages, auth, first-run onboarding,
the authenticated app shell, monitoring/data/admin pages, cloud-camera surfaces — and the cross-cutting
systems that make those flows work (routing/guards, data layer, theming/tokens, i18n, accessibility,
error surfacing, assets, quality gates).
**Audience:** engineering + product owner preparing the product for enterprise pilots and procurement review.
**Status of this document:** audit + target blueprint + prioritized plan. It is *not* a claim that the UI is
enterprise-ready today. The Wave-1 quick wins are implemented with this audit (see §8.1); everything else is planned
and listed with acceptance criteria.

**Related, do not duplicate:**
[`docs/DEEP_AUDIT_REPORT.md`](DEEP_AUDIT_REPORT.md) (repo-wide audit, TRL register, §12 P1 plan),
[`docs/SELL_READINESS_AUDIT.md`](SELL_READINESS_AUDIT.md) (claims/pricing truth, F-01…F-22),
[`docs/TRL8_QUALIFICATION_EVIDENCE.md`](TRL8_QUALIFICATION_EVIDENCE.md) (in-repo TRL-8 gates),
[`ui_posture/README_ARCHITECTURE.md`](ui_posture/README_ARCHITECTURE.md) (component map),
[`ui_posture/FRONTEND_ASSET_AUDIT.md`](ui_posture/FRONTEND_ASSET_AUDIT.md) (**stale** — describes the pre-router tab app; flagged in F-UX-19).

---

## 0. Executive summary

The frontend is a real, broad application: 39 page files, 40 routes, ~57 shared components, four roles with a
single-source permission map, code-split routes, a light/dark token theme, an i18n layer, and 106 unit tests that
gate CI (110 after the Wave-1 additions in this pass). The product demo path works (login → dashboard → live monitoring → cloud cameras, verified in this repo's
QA runs and TRL-8 evidence). What separates it from "enterprise" is not page count — it is **flow integrity,
permission honesty, state discipline, and the absence of enforceable UX gates**.

| Dimension | Today | Enterprise bar | Verdict |
|---|---|---|---|
| Route/flow integrity | 40 routes, lazy chunks, guard map `auth/routes.ts` | No dead ends, explicit 404/deny states, deep links survive | **Weak** — unknown URLs rendered nothing (`App.tsx` had no `path="*"`); in the live walk 17 operator and 10 safety-manager route visits silently bounced to `/dashboard` (F-UX-02) |
| Account lifecycle | login/MFA/demo/logout solid; signup broken | Signup → org created → guided activation → first session | **Broken** — signup writes legacy storage keys nothing reads, landing the new admin signed-out (F-UX-01) |
| First-run / activation | 4 parallel setup journeys | One activation model with resumable, skippable steps | **Fragmented** (F-UX-07) |
| Permission UX | Nav is role-filtered; API enforces RBAC | Pages never call endpoints the role can't use; deny states explain *why* | **Weak** — 403s arrive as console noise, raw codes, or silently empty widgets (F-UX-03) |
| Data/state discipline | ~30 hand-rolled `setInterval` pollers, no abort/timeout | One data layer: caching, retry/backoff, visibility-aware polling, typed errors | **Weak** (F-UX-04) |
| Accessibility | SkipLink, focus-visible ring, login form is good; reduced-motion absent; dialogs not dialogs | WCAG 2.2 AA, keyboard/TalkBack-tested flows, reduced motion, dialog semantics | **Partial** (F-UX-06, F-UX-12) |
| i18n | 3 languages, 4 consumers, 145-key file | Complete or absent — no partial promise | **Cosmetic** (F-UX-09) |
| Design system | Token theme + shared primitives exist | Primitives are the *only* way to build UI; light/dark everywhere | **Partial** — raw palette + dark-only public pages/modals (F-UX-10) |
| Responsive | `lg:`-driven grids; some 384–400 px fixed panels | 360 px → 4K with no horizontal scroll | **Partial** (F-UX-11) |
| Error/observability | Shared ErrorCard; console-only boundaries | Error IDs, user-copyable reference, frontend RUM, on-call signal | **Weak** (F-UX-13, F-UX-14) |
| Trust/claims in UI | 87.6% used correctly on Validation/Model Card; demo banner honest | Every number traceable; claims guard enforced in CI | **Partial** — ROI math renders nonsense on thin data (F-UX-18); claims guard is not in CI (F-UX-17) |
| Quality gates | `tsc → vitest → build` (CI) | + lint, a11y, visual regression, e2e flows, bundle/perf budgets | **Weak** (F-UX-17) |

### Top 10 findings by severity

| # | Finding | ID | Severity |
|---|---|---|---|
| 1 | Signup writes `ergovigilance_token`/`ergovigilance_user`; auth reads `ergovigilance_auth` → new customers land signed-out | F-UX-01 | **P0** |
| 2 | No 404 route; forbidden routes silently redirect to `/dashboard` (no reason surfaced) | F-UX-02 | **P0** |
| 3 | Pages call endpoints the signed-in role cannot use; users see raw `(403)`, console storms, or empty panels | F-UX-03 | **P0** |
| 4 | No request timeout/abort/cancel; ~30 independent pollers that ignore tab visibility | F-UX-04 | **P0** |
| 5 | JWT placed in query strings for media (video feed/recordings), leaking tokens into logs/history | F-UX-05 | **P0** |
| 6 | Only one modal has dialog semantics; Drawer (used app-wide) has no role/Escape/focus trap; destructive actions use `window.confirm` | F-UX-06 | **P0/P1** |
| 7 | Four competing setup journeys (modal, 5-step, 6-step cloud, camera wizard, dashboard checklist) | F-UX-07 | **P1** |
| 8 | Partial i18n shipped as a product promise (3 locales, 4 consumers, "switch between English, Hindi, and Chinese") | F-UX-09 | **P1** |
| 9 | Claims/ROI surfaces can render unbusinesslike numbers (`$2,100` savings for 0 hours monitored) and banned accuracy vintages have no CI guard | F-UX-18, F-UX-17 | **P1** |
| 10 | Asset/repo hygiene: 3 unused demo MP4s (one 4K50), a scraped iStock HTML page with a CSRF token, broken `og-image`/app-icon references | F-UX-15 | **P1** |

Also **P0 for procurement**: the signup form requires agreeing to a Terms of Service and a Privacy Policy that both
link to `/legal`, a route that does not exist (F-UX-20) — no customer can lawfully accept terms that cannot be read.

---

## 1. Method and evidence base

Sources used, in order of strength:

1. **Source read** of `ui_posture/src` (App shell, `auth/`, `hooks/`, `services/`, `i18n/`, `pages/`, `components/`,
   `index.css`, `index.html`, `vite.config.ts`, `vitest.config.ts`, `nginx.conf`) on 2026-10-02, branch `master`.
   All `file:line` citations in this document point at the working tree at that time.
2. **Live browser-flow evidence** from this repo's QA pass: `results/qa-pass/evidence.jsonl` (per-role route walks,
   auth lifecycle, resilience up/down, model-card claims check, settings round-trip). Gitignored working data,
   dated 26–27 Sept 2026 — cited as `evidence.jsonl:<line>`.
3. **Existing verified runs**: `docs/TRL8_QUALIFICATION_EVIDENCE.md` (frontend rows: typecheck, 106 unit tests, build),
   `docs/DEEP_AUDIT_REPORT.md` (page/route counts 39/40, honesty matrix), `docs/SELL_READINESS_AUDIT.md`.
4. **Static inventories** (`glob`, `code_search`) for counts of patterns: 30 `setInterval` sites in `src/`, 51 raw
   `fetch(` call sites, 151 silent-catch sites, 28 `animate-spin` sites, 1 `role="dialog"`, 7 `aria-live/aria-busy/…`
   occurrences (6 of them in LoginPage), 3 `useI18n` consumers.

Known limits of this audit: no external usability testing with operators, no formal WCAG audit tooling run
(no axe/Pa11y in the repo), and the live QA evidence is from a Sept 2026 build — where a finding was fixed after
that run, the source is cited and the live evidence is marked "pre-fix".

---

## 2. Flow map (as-is)

### 2.1 Route inventory — verified

`ui_posture/src/App.tsx`: 39 page files in `src/pages/`, 40 `<Route>` entries (1 is a redirect `/trends → /reports?view=risk-trend`).

- **Public (outside the app shell):** `/` (Landing or redirect to `/dashboard` when signed in), `/request-pilot`,
  `/validation`, `/login`, `/forgot-password`, `/signup`, `/pricing`, `/status`.
- **Authenticated (inside `Layout`):** 32 routes — Dashboard, Live Monitoring, Video Review, `/replay/:sessionId`,
  Analytics, Sessions, Reports, Settings, Manager, Deployment, Multi-Camera, Audit Trail, Workers, My Posture, Users,
  Pilot Requests, Setup wizard, API Docs, Cloud Cameras, Cloud Settings, Cloud Onboarding, Model Dashboard, YOLO Demo,
  ROI Analytics, System Health, Architecture, Webcam Demo, Model Card, Pilot Checklist, Onboarding, Consent.
- **Providers** (`main.tsx`): Theme → Toast → I18n → Auth → Settings → Alerts. Note `SearchModal` lives *outside*
  `Layout` in `App.tsx` (router-wide command palette).

### 2.2 Personas and their real journeys

| Persona | Intended journey | What the audit found |
|---|---|---|
| **Visitor** | Landing → Validation → Pricing/Request pilot → signup | Landing/Validation are strong; **signup is a dead end** (F-UX-01); `/pricing` uses full-page `window.location.href` navigation (F-UX-13); `/status` is public but styled dark-only (F-UX-10) |
| **New org admin** | Signup → onboarding wizard → camera → workers → first session | After F-UX-01 is fixed, admin lands in the 5-step `/onboarding` wizard; three *other* setup entry points compete for the same job (F-UX-07) |
| **Operator** | Login → My Posture / dashboard → monitor own posture | Login works and is the best-built form in the app; but 22 routes silently bounce to `/dashboard`, `/setup` is reachable yet 403s, and the Webcam demo/demo sessions generate 403 storms (F-UX-02, F-UX-03) |
| **Supervisor / Safety manager** | Team dashboard → live monitoring → sessions → reports → audit/consent | Core flow works (verified: sessions, reports, audit, consent pages render with data); Reports/Settings call admin-only endpoints and log 403s (F-UX-03) |
| **Admin** | Everything + users, deployment, cloud, model ops | Broadest surface; cloud pages are the best "degraded/honest" examples in the app (`Cloud core unreachable — camera list unavailable`, no fake zeros — `evidence.jsonl:156`) |

### 2.3 Session lifecycle (the product's spine)

`MonitoringControls` (header cluster) → `useSessionLifecycle` (`POST /api/session/start|stop`, 2 s `GET /api/session/status`)
→ WebSocket dashboard feed (`useWebSocket`) → dashboard gauges/alerts → session saved → `/sessions`, `/reports`,
`/replay/:id`. This path works end-to-end; its weaknesses are state-layer ones (F-UX-04) and error phrasing (F-UX-13).

---

## 3. Findings register

Severity: **P0** = blocks a credible enterprise demo/procurement; **P1** = visible in a 30-minute evaluation;
**P2** = polish/scale.

### 3.1 Account lifecycle

**F-UX-01 — Signup lands the new administrator signed-out (P0, fixed in this pass)**
`SignupPage.tsx:94-96` writes `ergovigilance_token` / `ergovigilance_user` / `ergovigilance_onboarded='false'`.
`AuthContext.tsx:43` (`STORAGE_KEY = 'ergovigilance_auth'`) is the only key the app reads, and `Layout.tsx` redirects
to `/login` when `!user`. The string `'false'` is also truthy for the gate at `Layout.tsx:116`
(`!localStorage.getItem('ergovigilance_onboarded')`), so even after the storage fix the first-run wizard would be
skipped. The existing QA harness checked the same wrong keys (`evidence.jsonl:145,214`), which is why this survived.
*Fix shipped:* `AuthContext` now exposes `adoptSession(token, user)` and `SignupPage` uses it; the stale keys are
removed. *Verification:* `signupFlow` unit test (see `src/test/a11yFlows.test.tsx`).

**F-UX-02 — No 404 page; forbidden routes redirect silently (P0)**
`App.tsx` defined no `path="*"`; an unknown URL while signed out renders `Layout`'s redirect (fine), but while signed
in nothing matched and React Router rendered **an empty screen** (`<Routes>` → null). The guard in `Layout.tsx:196-199`
bounces any path outside `rolePaths[role]` to `/dashboard` with no explanation. Live evidence: 17 operator routes
(`evidence.jsonl:104-124`) and 10 safety-manager routes (`:65-85`) returned `httpStatus 200, finalUrl /dashboard`
with no message. An enterprise
user who follows a colleague's link cannot tell whether the feature moved, the link is wrong, or they lack access.
*Fix shipped:* an in-shell 404 route (`pages/NotFoundPage.tsx`) with links to Dashboard / search / support.
*Planned:* replace silent redirects with an access-denied surface naming the required role.

**F-UX-03 — Permission contract mismatch between pages and APIs (P0)**
The nav is role-filtered, but pages still call endpoints their role can't use, so evaluations see raw 403s:

| Role/session | Page | Failed calls (live evidence) | User-visible result |
|---|---|---|---|
| operator | `/setup` | `/api/setup/status` ×3 (`evidence.jsonl:112`) | literal text `Setup status failed (403)` (`SetupWizardPage.tsx:65`) |
| operator | `/reports` | `/api/reports/digest` ×2 (`:102`) | Nightly Risk Digest panel stays empty, console noise |
| operator | `/settings` | `/api/cameras` ×2 (`:103`) | camera dropdown silently empty |
| supervisor (Webcam demo session) | `/webcam-demo` | `/api/dashboard`, `/api/alerts`, `/api/session/status` ×16 (`:149`) | 16 console 403s per visit |
| operator | login | `/api/setup/status` ×2 (`:8`) | onboarding probe 403 (now role-gated in `OnboardingFlow.tsx:63-111`) |

Also: `OnboardingFlow` and `/setup` are in `rolePaths.operator` (`auth/routes.ts`) although the underlying
endpoints are supervisor+ — reachable UI that can never work for that role.
*Planned fix:* page-level capability map (one hook: `useCapabilities()`), hide/disable role-incompatible sections,
and a shared 403 -> "your role can't view this; ask <role>" mapper in the API client.

**F-UX-04 — No data layer: no timeout, no abort, no shared cache, poller sprawl (P0)**
`apiClient.ts:11-20` is a bare `fetch` + 401 hook; nothing sets `AbortSignal.timeout`, and no hook cancels in-flight
requests on unmount (React 19 StrictMode double-invokes every effect). 30 `setInterval` pollers run in `src/`
(10 s dashboard, 5 s admin summary ×2 roles, 2 s session status, 3 s cloud thumbnails, 15 s system health ×4,
3 s live timeline, 4 s history, 10 s alerts/recommendations/context, 30 s manager/cameras/status, …). None pause when
the tab is hidden, and most swallow failures (`useDashboard.ts:66-71` sessions; `DashboardPage.tsx` analytics;
`SystemHealthPage.tsx:354-443` four duplicated silent polls). A stalled backend leaves a page in its loading state
indefinitely; a dropped network shows stale numbers as if live.
*Planned fix:* TanStack Query (or an equivalent thin layer) with per-endpoint `staleTime`, timeouts, retry/backoff
on idempotent GETs, `refetchOnWindowFocus`, `refetchIntervalInBackground: false`, and a typed error shape.
Acceptance: kill the backend mid-session — every page shows a consistent degraded state within 5 s, no infinite spinners.

**F-UX-05 — JWT in query strings for media (P0)**
`dashboardService.ts` `getRecordingVideoUrl()` / `getRecordingRawVideoUrl()` append `?token=<JWT>`;
`SetupWizardPage.tsx:~100` falls back to `token=` in the `<img>` src. Live evidence shows the token in a failing
request URL: `/video/feed?overlay=true&token=eyJhbGciOi…` (`evidence.jsonl:32,72`). Tokens in URLs land in access logs,
browser history, and referrers, and break any future signed-media review. There *is* a proper mechanism —
`useStreamToken` (`GET /video/stream-token`, 8-minute refresh) — and recordings should use the same short-lived,
purpose-scoped token path. *Planned fix:* issue per-asset short-lived tokens, never the session JWT.

### 3.2 Navigation, IA and first-run

**F-UX-06 — Dialog semantics only exist in one component (P0/P1)**
`SearchModal.tsx:167` is the only `role="dialog"` in the app. `Drawer.tsx` — the detail panel behind sessions,
reports, workers — has no `role="dialog"`, `aria-modal`, `aria-labelledby`, no Escape handling, no focus trap, no
focus restore, and its close button has no accessible name (`Drawer.tsx:38-50`). `Layout.tsx:266-282` notification
drawer and `AIAssistantPanel.tsx:292` have the same issues. Destructive actions use `window.confirm`
(`CloudCamerasPage.tsx:159`, `ConsentPage.tsx:122`) — untranslatable, untestable, and visually off-brand.
*Fix shipped:* `Drawer` now has dialog semantics, Escape-to-close, focus trap/restore, and a labelled close button.
*Planned:* a shared `<Modal>/<ConfirmDialog>` primitive and migration of the remaining overlays.

**F-UX-07 — Four competing setup journeys (P1)**
`OnboardingFlow` modal (shown by `Layout.tsx:116` on first login), `/onboarding` 5-step wizard, `/cloud-onboarding`
6-step cloud wizard, `/setup` camera wizard, plus the `GettingStarted` checklist card on the dashboard
(`DashboardPage.tsx`). Live evidence shows two different "Welcome" headings for `/onboarding` and `/cloud-onboarding`
(`evidence.jsonl:36,45`). Nothing tracks completion across them (`ergovigilance_onboarded` is a single flag);
an evaluator cannot answer "how far along am I?".
*Planned fix:* one activation model — a persisted step state (org → camera → worker → consent → first session) with
three entry points that all read/write it; delete or demote the duplicates to deep links.

**F-UX-08 — Demo/tour ergonomics (P2)**
The demo brochure path is genuinely good (`Try Demo`, amber DEMO banner `Layout.tsx:98-116`, tour auto-start
`Layout.tsx:132-140`), but `LoginPage.tsx:19-20` pre-fills `operator@example.local / OperatorPass123!`, which reads
as sloppy to a security reviewer and hides the empty-state validation path in every demo.
*Planned:* keep the demo button, drop pre-filled credentials (or gate prefill to `DEMO_MODE` only).

**F-UX-09 — i18n shipped as a promise, implemented as a stub (P1)**
`t()` is consumed only by `Sidebar.tsx:75`, `LiveMonitoring.tsx:634`, `SettingsPage.tsx:22`, plus the provider.
`en.json` is 145 lines (nav + a few page strings) versus 39 pages of hardcoded English. Settings promises
"Operator-facing labels and posture guidance will appear in the selected language" and the tour says
"switch between English, Hindi, and Chinese" (`ProductTour.tsx:153`). Dates are hardcoded to `en-IN`/IST
(`utils/formatTime.ts`) with no locale-aware formatting, no pluralisation, no interpolation, and Google Fonts are
loaded from a CDN (`index.css:1`) which fails on air-gapped plants.
*Planned:* decide honestly — either (a) finish i18n (ICU messages, `Intl.*`, self-hosted fonts, per-locale snapshot
tests), or (b) label the switcher "Beta — navigation only" and stop promising full localisation.

### 3.3 Accessibility, theming, responsive

**F-UX-10 — Token system exists, but it is not the only way to style (P1)**
`index.css` defines a full M3-style token set with light overrides (lines 8-45, 345-470), plus a note that
`max-w-*` is broken by the spacing scale (lines 58-63). In practice: raw `slate/blue/red/emerald` utilities are used
everywhere, `LandingPage.tsx:318` and `PricingPage.tsx:140` hardcode dark backgrounds (`bg-[#10131a]`,
`bg-[#0b0f14]`), `CloudCamerasPage.tsx:476` hardcodes `#1a1a2e`, and `RouteErrorBoundary.tsx:34` hardcodes `#0b0f14`
so the error screen stays dark in light mode. Local helpers are duplicated instead of shared
(`riskColor` in 5 files, `formatDuration` in 3). *Planned:* primitives-only rule for new UI (Button/Card/Badge/Modal…
in `components/common/`), lint rule against raw hex, and one shared formatting module. (Note: the older
`FRONTEND_ASSET_AUDIT.md` section on tokens is obsolete.)

**F-UX-11 — Fixed-width chrome breaks small viewports (P1)**
`SearchModal.tsx:169` uses `w-[720px] max-w-[90vw] min-w-[400px]` — `min-w` wins, so a 360 px phone scrolls
horizontally. `Layout.tsx:272` (notification drawer) and `AIAssistantPanel.tsx:292` are `w-96` (384 px) with no
`max-w-[100vw]`. The recorder's own finding `docs/QA_PHASE1_FINDINGS.md:67` flagged 9–11 px telemetry text and
small targets on LiveMonitoring for a "tired/older/gloved-operator persona" — partly fixed, but no mobile/tablet
regression gate exists. *Planned:* viewport matrix in Playwright (360/768/1280/1920) as a gate.

**F-UX-12 — Accessibility gaps beyond dialogs (P1)**
No `prefers-reduced-motion` handling anywhere (`code_search` = 0 hits) while the app animates page transitions,
shimmer skeletons, pulses and stagger entrances — a WCAG 2.3.3 problem and a real issue on cheap factory PCs.
`LoadingCard` has no `role="status"`/`aria-busy`; only `Layout.tsx:253` has an `aria-live` region and nothing
uses it; `EmptyState` is used for *errors* in `AuditTrail.tsx:199` and `ReportsPage.tsx:404` (screen-reader users
hear "no data" for a failure); page H1s drift (`/monitoring`'s first heading is "ERGONOMIC FEATURES",
`/workers`' is "WORKERS"), so document outlines vary by page. LoginPage remains the model to copy:
`aria-invalid`/`aria-describedby`, `role="alert"`, labelled inputs (`LoginPage.tsx:150-215`).
*Fix shipped:* global `prefers-reduced-motion` support.

**F-UX-13 — Error surfacing is inconsistent and sometimes raw (P1)**
`friendlyHttpError` (`apiClient.ts:22-27`) is used in a handful of pages, while `dashboardService.ts` throws
`Failed to fetch X: 500` strings, `SetupWizardPage.tsx:65` renders `Setup status failed (403)`, and
`MonitoringControls.tsx:121` truncates the session error to 200 px with a `title` tooltip. Retry does a full page
reload in `SessionHistory.tsx:243` rather than refetching. Only `SetupWizardPage`/`OnboardingChecklistPage` phrase
recovery as an action ("see docs/DEV_START.md"). *Planned:* one error taxonomy (network/offline, auth, permission,
not-found, server, rate-limited) rendered by shared components with a retry that refetches, plus a copyable
reference id.

**F-UX-14 — No frontend observability (P1)**
`ErrorBoundary.tsx` and `RouteErrorBoundary.tsx` log to console only; no error id, no reporting endpoint, no
Web Vitals/RUM, no way for a plant IT contact to file a triageable incident. *Planned:* error boundary posts to a
`/api/client-errors` endpoint with a short id shown to the user; add `web-vitals` reporting and a simple
"diagnostics" panel on `/system-health`.

### 3.4 Assets, performance, claims, gates

**F-UX-15 — Asset and repo hygiene on the user-facing surface (P1)**
`ui_posture/public/videos/` ships three unused demo MP4s (including `13386601_3840_2160_50fps.mp4`; a repo-wide
search finds no reference) into the frontend image; `public/Hackathon_MVP.pptx` ships as a downloadable file;
`public/images/Lifting_Heavy_box.htm` is a **scraped iStock/ Getty page** containing a `csrf-token` meta value and
third-party tracking payloads (`Lifting_Heavy_box.htm:57`), and two stock JPGs (`Man_Epereincing_back_pain.jpg` —
also misspelled). `index.html` references `/og-image.png`, `/favicon-32x32.png`, `/favicon-16x16.png`,
`/apple-touch-icon.png` that do not exist in `public/` (404s on every visit; broken social previews), repeats the
`theme-color`/apple meta block twice (lines 33-40), and loads Plausible analytics from the internet
(`index.html:52-53`) — data egress that contradicts the on-premise privacy story unless it is made opt-in.
*Planned:* move media out of `public/` (object storage or `docs/`), delete the scraped page and the deck, fix or
remove the dead icon/meta references, make analytics an explicit deployment toggle.

**F-UX-16 — Public-site delivery for air-gapped/regulated plants (P2)**
Google Fonts `@import` (`index.css:1`) plus `preconnect` in `index.html` means first paint depends on the public
internet and leaks a request to Google (GDPR-sensitive in the EU). `nginx.conf` CSP allows `'unsafe-eval'` and
`connect-src https:`. *Planned:* self-host Inter/JetBrains Mono subsets, tighten CSP after removing inline scripts.

**F-UX-17 — Quality gates don't cover UX (P1)**
`.github/workflows/ci.yml` frontend job runs `tsc --noEmit`, `vitest run`, `npm run build`. There is no ESLint or
Prettier config in the repo, no axe/a11y test, no Playwright e2e, no visual regression, no bundle-size or Lighthouse
budget. Measured at audit time (production build): entry `index-*.js` 521 kB (161 kB gzip) plus a 345 kB (103 kB gzip)
shared charting chunk, and Vite warns about chunks > 500 kB — with no budget in CI, this can only grow. The one automated claims guard (`flows.mjs:92,187`, asserting forbidden 94.1/97.6 vintages) lives in the
gitignored `results/qa-pass/`, so it cannot fail a PR.
*Planned:* add gates in this order: ESLint (+ react-hooks, jsx-a11y) → axe assertions in vitest → Playwright smoke of
the 5 core flows × 4 roles at 2 viewports → bundle budget (`dist/assets` < target, per-route chunk report) →
claims guard ported into `ui_posture/src/test/claims.test.ts`.

**F-UX-18 — Business-value surfaces can render implausible numbers (P1)**
Live evidence: `/roi-analytics` showed "Estimated Annual Savings $2,100 … 0 hours monitored", "Injury Prevention $0
(0 injuries prevented)", "Compliance Savings $2,100 (0 violations prevented)" (`evidence.jsonl:79`;
`ROIAnalyticsPage.tsx:133-235`). For an EHS buyer this reads as fabricated math. There is no minimum-data gate.
A second copy/entitlement drift sits on the same path: the signup footer promises "3 cameras" (`SignupPage.tsx:305`)
while the backend grants the pilot org `max_cameras: 4` (`backend_api/app/api/signup.py:117-118`) and the Starter tier
says 4 (`PricingPage.tsx:21`) — see `docs/SELL_READINESS_AUDIT.md` F-02.
*Planned:* require ≥ N sessions and ≥ H hours before showing a currency figure; below that, show the method and a
"not enough data yet" state (matching the honest degraded banners used by Cloud Cameras / Model Dashboard).

**F-UX-20 — Terms of Service / Privacy Policy pages do not exist (P0 for procurement)**
`SignupPage.tsx:266-268` asks the buyer to agree to a Terms of Service and a Privacy Policy, both `<Link to="/legal">`.
There is no `/legal` route in `App.tsx` (before this pass the link rendered a blank screen; the new catch-all at least
shows the 404 page). Repo policy text exists (`docs/PRIVACY.md`, `docs/DPA_TEMPLATE.md`) but is never served in the
product. *Fix:* render the policy documents in-app (versioned, dated) and link them from signup, login footer,
Settings and the consent flow.

**F-UX-19 — Docs drift that procurement will read (P2)**
`ui_posture/README.md` still documents the tab-era app (routes table with `/trends`, `TrendAnalysisPage.tsx`, `mock/`,
`usePolling`) and `FRONTEND_ASSET_AUDIT.md` describes "6 screens, no router, no tests". Root `README.md` routes to
`docs/CURRENT_STATE.md`, which is current, but the frontend READMEs are not. *Planned:* rewrite both to point at this
audit + `README_ARCHITECTURE.md`, or archive them.

---

## 4. What is already enterprise-grade (keep and build on it)

- **Route code-splitting with a shared Suspense fallback** (`App.tsx:26-70`) — deliberate for slow factory PCs.
- **Single-source RBAC map + regression test** (`auth/routes.ts`, `src/test/routes.test.ts`) — the guard/sidebar/tour
  drift bug class is closed and CI-enforced.
- **Shared state primitives** (`LoadingCard`, `ErrorCard`, `EmptyState`, `StatusBadge`, `Drawer`, `SectionHeader`)
  with honest copy — the pattern to extend, not replace.
- **Theme token system with real light overrides** (`index.css:8-45, 345-470`) plus chart theme module.
- **Login page**: MFA challenge flow (`AuthContext.MfaRequiredError`), token-expiry pruning on load, field-level
  a11y, graceful rate-limit messaging.
- **Honesty by design on degraded services**: Cloud Cameras "Cloud core unreachable — camera list unavailable"
  with a start-here hint, no fake zeros; Model Dashboard "Research track — not product accuracy" labelling
  (`ModelDashboardPage.tsx:156-161`); Model Card 87.6%-with-caveats.
- **Demo-mode separation**: amber banner, tour reset per demo entry, no real data claims.
- **A real QA harness from the prior pass** (`results/qa-pass/qa.mjs`, `flows.mjs`, `resilience.mjs`) — the
  beginning of e2e coverage; it just needs to move into CI.

---

## 5. Enterprise target blueprint

### 5.1 App shell and navigation
1. Explicit route outcomes: `404` page, `403`-access-denied page (names required role), and a "no access yet —
   request access" path. No silent redirects except `/` for signed-in users.
2. Page header contract: every page renders one `<h1>` (title + role hint + primary action), breadcrumbs for
   nested flows (`/replay/:id` → Sessions).
3. Capability-aware nav: nav items, page sections and buttons derive from one capability map
   (`role → capability → route/API`), tested against the backend permission matrix.
4. Global search palette filtered by role (currently all 17 nav items are listed for every role,
   `SearchModal.tsx:24-43`).

### 5.2 Data and state
5. One data layer (TanStack Query recommended; already a React 19 + Vite app) providing: timeouts (10 s default),
   typed errors, retry with jittered backoff for GETs, cache + dedupe, `refetchOnWindowFocus`,
   visibility-aware polling, and `keepPreviousData` for tables.
6. A connectivity/degraded banner (reusing the Cloud Cameras pattern) driven by a single health probe, plus
   optimistic mutations with rollback for settings/session actions.

### 5.3 Design system
7. `components/common/` becomes the only public API for UI: `Button`, `Card`, `Modal`, `ConfirmDialog`, `Table`,
   `Tabs`, `Field`, `Badge`, `Toast`, `Drawer`. Add Storybook (or a `/styleguide` route) with light/dark stories.
8. Token discipline: no raw palette/hex in feature code (ESLint rule + review), semantic tokens for
   success/warning/danger/info (already present) and data-viz.
9. Visual regression baseline (Playwright screenshots) for the 12 highest-value screens × light/dark.

### 5.4 Accessibility and inclusion
10. WCAG 2.2 AA: dialog semantics + focus management everywhere; `aria-live` for async status; reduced motion
    (shipped); keyboard paths for tour/help/drawers; ≥ 24×24 px targets (44 px on operator-facing live screens);
    visible text ≥ 12 px with 4.5:1 contrast verified by axe.
11. Document language and text scale: `lang` follows locale, support 125–150 % browser zoom without clipping.

### 5.5 Internationalisation
12. ICU message format with interpolation/plurals, `Intl.DateTimeFormat/NumberFormat` (keep IST as a *timezone*,
    not a locale), locale-aware number/currency, self-hosted fonts, RTL-ready layout rules (`dir` on `<html>`).
    Either complete this for the shipped locales or narrow the public promise.

### 5.6 Trust, claims and compliance UX
13. Claims guard in CI: a test that scans rendered public/authed surfaces for banned vintages
    (`94.1/97.6/88.6/86.4/76.9`), enforces "screening aid, not a medical device" on risk-bearing pages, and
    requires the 87.6 % LOW/MEDIUM phrasing where an accuracy figure appears.
14. Minimum-data gates for money/ROI/trend surfaces; every estimate labelled with its method and inputs.
15. Consent/erasure/unsubscribe flows reachable from the global footer for any user, with audit-trail receipts.

### 5.7 Observability and release engineering
16. Error boundaries report to the backend with a user-visible reference id; Web Vitals (LCP/INP/CLS) collected from
    real deployments; `/system-health` shows the frontend build SHA + API contract version.
17. UX gates in CI: ESLint (+jsx-a11y), axe unit assertions, Playwright flow suite, bundle budget, Lighthouse
    budget on the public pages; extend the TRL-8 qualification battery with these rows so one command still
    re-proves everything (`scripts/qualification/run_qualification.py`).

---

## 6. Roadmap

### Wave 1 — Flow integrity (0–2 weeks, no new dependencies)
- [x] F-UX-01 signup session adoption (+ test) — **done in this pass**
- [x] F-UX-02 in-shell 404 route (+ test) — **done in this pass**
- [x] F-UX-06 Drawer dialog semantics/Escape/focus trap (+ test) — **done in this pass**
- [x] F-UX-12 reduced-motion global support — **done in this pass**
- [ ] F-UX-03 capability map + 403 mapper; remove `/setup` from operator (`auth/routes.ts`) or gate the page
- [ ] F-UX-13 error taxonomy + "retry refetches" (kill `window.location.reload` in `SessionHistory.tsx`)
- [ ] F-UX-15 delete scraped HTML/deck/MP4s, fix `index.html` icon/OG/meta, analytics as a toggle
- [ ] F-UX-20 serve Terms of Service + Privacy Policy in-app and link them from every acceptance point
- [ ] F-UX-17 ESLint (+react-hooks, jsx-a11y) and axe assertions in CI
- Acceptance: `npx tsc --noEmit`, `npx vitest run`, `npm run build`, ESLint clean; a scripted 4-role walk shows zero
  console errors and zero silent redirects for reachable routes.

### Wave 2 — Data layer and accessibility (2–6 weeks)
- [ ] F-UX-04 TanStack Query migration page-by-page (start: Dashboard, LiveMonitoring, CloudCameras, SystemHealth)
- [ ] F-UX-05 short-lived media tokens; remove session JWT from URLs
- [ ] F-UX-07 unified activation model with persisted progress
- [ ] F-UX-11 responsive matrix (360/768/1280/1920) + Playwright flow suite × 4 roles
- [ ] F-UX-12 dialog/modal primitive rollout; aria-live for async status; H1/outline normalisation
- [ ] F-UX-14 error ids + `/api/client-errors` + Web Vitals
- Acceptance: backend killed mid-flow → consistent degraded state in ≤ 5 s; Playwright suite green in CI; axe reports
  0 serious/critical on the 12 core screens.

### Wave 3 — Design system, i18n, enterprise packaging (6–12 weeks)
- [ ] F-UX-10 component library + token lint + light/dark visual regression
- [ ] F-UX-09 finish or narrow i18n; self-host fonts; `Intl` formatting
- [ ] F-UX-18 minimum-data gates on ROI/analytics; claims guard in CI
- [ ] F-UX-16 CSP tightening + air-gap mode (no external requests, `docs/DEPLOYMENT_TOPOLOGY.md` aligned)
- [ ] F-UX-19 frontend READMEs rewritten; `/styleguide` route published for customer IT
- [ ] Extend `scripts/qualification/run_qualification.py` with `frontend-lint`, `frontend-a11y`,
  `frontend-e2e`, `frontend-bundle-budget` rows so TRL evidence covers UX gates.
- Acceptance: a customer IT admin can deploy, verify and operate without a developer; every claim on a screen is
  traceable to a measured artifact.

---

## 7. Enterprise UX acceptance checklist (the "done" ruler)

| Area | Done means |
|---|---|
| Flows | Every route has a defined outcome (render / 403 state / 404 state); no silent bounce |
| Auth | Signup → first session in one sitting; MFA, reset, demo each with dedicated states; no credentials in source |
| Permissions | UI affordances derive from one capability map; no page calls an endpoint its role cannot use |
| States | Every data surface implements loading / empty / error / degraded / stale explicitly |
| A11y | axe clean on core screens; full keyboard path for every flow; reduced motion; dialog semantics |
| i18n | Either complete (ICU + `Intl` + fonts + tests) or clearly labelled partial |
| Trust | One accuracy figure (87.6 % LOW/MEDIUM) machine-enforced; money/trend surfaces gated on minimum data |
| Observability | Every caught error has an id a user can quote; Web Vitals visible for the deployment |
| Assets | Frontend image contains only used assets; no third-party scrape; no external runtime dependency by default |
| Gates | typecheck, lint, unit, a11y, e2e, claims, bundle budget — all in CI, all re-runnable by one command |

---

## 8. Appendix

### 8.1 Changes shipped with this audit

| File | Change | Reason |
|---|---|---|
| `ui_posture/src/auth/AuthContext.tsx` | new `adoptSession(token, user)` that writes the canonical `ergovigilance_auth` record and updates state | F-UX-01 |
| `ui_posture/src/pages/SignupPage.tsx` | adopt the signup token through `adoptSession`; remove the legacy keys and the truthy `'false'` flag | F-UX-01 |
| `ui_posture/src/components/common/Drawer.tsx` | `role="dialog"`, `aria-modal`, `aria-labelledby`, Escape to close, focus trap, focus restore, labelled close button | F-UX-06 |
| `ui_posture/src/index.css` | global `@media (prefers-reduced-motion: reduce)` handling for animations/transitions/smooth scroll | F-UX-12 |
| `ui_posture/src/pages/NotFoundPage.tsx` + `App.tsx` | in-shell 404 route (`path="*"`) with links home/search | F-UX-02 |
| `ui_posture/src/pages/SessionHistory.tsx` | retry refetches instead of `window.location.reload()` | F-UX-13 |
| `ui_posture/src/pages/SetupWizardPage.tsx` | 403 on setup status becomes a role-explaining message, not `(403)` | F-UX-03 |
| `ui_posture/src/pages/AuditTrail.tsx`, `ReportsPage.tsx` | error states use `ErrorCard` (not `EmptyState`) | F-UX-12 |
| `ui_posture/index.html` | remove duplicated meta block; point icons/OG at files that exist | F-UX-15 |
| `ui_posture/src/test/a11yFlows.test.tsx` | regression tests: Drawer semantics/Escape/focus, signup session adoption, 404 route | gates for the above |
| `ui_posture/src/test/interactions.test.tsx` | `beforeAll` chunk warm-up for Login/Dashboard/Users pages | flake found during this audit: the same cold-lazy-chunk timeout class fixed for `smoke.test.tsx`; `interactions` failed once under load with only the Suspense spinner in the DOM |

Verification for this pass (all run in `ui_posture/`, from the working tree): `npx tsc --noEmit` clean,
`npx vitest run` **110/110 passing** (9 files; 106 before this pass), `npm run build` succeeds (Vite still warns
about the >500 kB charting chunk — see F-UX-17).

### 8.1b Wave 2 — the "every dimension ≥ 8" program (see [`UX_SCORE_8_PROGRAM.md`](UX_SCORE_8_PROGRAM.md))

| Workstream | Shipped | Evidence |
|---|---|---|
| W1 data layer | `apiClient` timeouts + typed `ApiError` + retry/backoff; `usePolledResource` / `useVisibilityAwareInterval`; every data poller migrated (SystemHealth's 5 `/health` polls collapsed to 1; `setInterval` data pollers now 0 outside the primitive) | `src/services/apiClient.ts`, `src/hooks/usePolling.ts`, `src/test/apiClient.test.ts` (18), `src/test/usePolling.test.tsx` (hidden-tab pause, backoff, degraded-with-last-good, signed-out short-circuit) |
| W2 permission contract | `src/auth/capabilities.ts` (capabilities + endpoint role matrix mirrored from the backend `require_roles(...)` and pinned by test), `useCapability`/`useEndpointAccess`, in-shell `AccessDenied` replacing the silent redirect, role-filtered command palette, `/reports` digest gated for operators/supervisors | `src/test/capabilities.test.ts` (10), `src/test/guards.test.tsx`, `src/test/routes.test.ts` (+141 route-existence cases) |
| W3 activation + trust | one persisted activation store (`ergovigilance_activation`) written by the modal, the first-login wizard and signup reset; in-app `/legal` (draft, marked pending counsel); signup 4-camera copy pinned to `backend_api/app/api/signup.py`; ROI dollar figures gated behind 10 sessions / 5 monitored hours with an assumptions panel; banned accuracy vintages removed from the landing changelog | `src/services/activation.ts`, `src/pages/LegalPage.tsx`, `src/test/activation.test.ts` (8), `src/test/claims.test.ts` (7) |
| W4 a11y mechanics | dialog semantics on every overlay (AI panel, tour, keyboard help, notification drawer, add-camera, camera capture, onboarding); `LoadingCard` = `role="status"`+`aria-busy`, `ErrorCard` = `role="alert"`; route changes announce through `#a11y-announcer` and set the document title; exactly one `<h1>` on every page (5 pages gained one, incl. Live monitoring) | `src/hooks/useFocusOnNavigate.ts`, `src/utils/announce.ts`, `src/test/headings.test.ts` (42), `src/test/a11yFlows.test.tsx` |
| W5 gates | `scripts/ux_guards.mjs` (8 rules incl. claims, `window.confirm`, full reload, hex-colour ratchet, `?token=`, `<img>` alt, dialog semantics, ad-hoc `setInterval`) with a reasoned allowlist; `scripts/check_bundle_budget.mjs`; both wired into the frontend CI job | planted-violation proof: a probe file produced 5 violations/exit 1; clean tree → exit 0. CI job steps added in `.github/workflows/ci.yml` |
| W6 performance/visual | `manualChunks` (vendor-react/charts/motion/icons/ai); entry chunk 521 kB → 139 kB raw (161 → 41 kB gzip), no Vite >500 kB warning; `ConfirmDialog` replaces `window.confirm` in camera removal + consent withdrawal; add-camera modal tokenised | budget gate output: 62 chunks, 456 kB gzip total, entry 40 kB gzip, 0 chunks >500 kB |

Wave 2 verification (from `ui_posture/`): `npx tsc --noEmit` clean · `npx vitest run` **275/275 in 14 files**
(106 at audit time) · `npm run build` succeeds with no >500 kB warning · `node scripts/ux_guards.mjs` 0 violations ·
`node scripts/check_bundle_budget.mjs` within budget.

Still open after Wave 2 (not claimed as done): 24 px touch-target audit on the operator live screen; raw-hex
debt is ratcheted, not eliminated (ceiling list in `scripts/ux_guards_allowlist.json`); `?token=` media URLs remain
the documented F-UX-05 debt; `docs/legal` still needs counsel; no timer/break-down metric on the operator screen.

### 8.2 Evidence commands

```bash
# inventory (from repo root)
rg -n "setInterval\(" ui_posture/src | wc -l          # 30 poller sites at audit time → 10 today, all in 9 allowlisted files (clocks, animation counters, the polling primitive itself)
rg -n "await fetch\(" ui_posture/src                  # 51 raw fetch call sites
rg -n 'role="dialog"' ui_posture/src                  # 1 at audit time → 11 occurrences across 9 files (Drawer, SearchModal, 6 overlays, ConfirmDialog, camera modal)
rg -n "prefers-reduced-motion" ui_posture/src         # 0 at audit time (fixed in this pass)
rg -n "window\.confirm|location\.reload" ui_posture/src  # 3 real call sites at audit time → 0 (ConfirmDialog + refetch); only explanatory comments remain
rg -n "setInterval\(" ui_posture/src --glob '!*test*'  # the data-polling layer uses usePolledResource / useVisibilityAwareInterval instead
# frontend gates (all four run in CI)
cd ui_posture && npx tsc --noEmit && npx vitest run && node scripts/ux_guards.mjs && npm run build && node scripts/check_bundle_budget.mjs
```

### 8.3 Live-evidence index (`results/qa-pass/evidence.jsonl`, gitignored)

| Line(s) | What it shows |
|---|---|
| 8 | Operator login triggers role-gated `/api/setup/status` 403s |
| 32, 72, 149 | `/video/feed?...token=<JWT>` requests, 401s, demo-session 403 storm |
| 102-124 | Operator route walk: 17 paths silently resolve to `/dashboard`; raw `Setup status failed (403)` (safety walk `:65-85` adds 10 more) |
| 36, 45 | Two "Welcome" wizards (`/cloud-onboarding`, `/onboarding`) |
| 79 | ROI page: `$2,100` savings with `0 hours monitored` |
| 150 | Model Dashboard still contained banned 94.1/97.6 vintages in that build (source now labels them research-track) |
| 156 | Resilience-down: honest degraded banners, no fake zeros (the pattern to copy) |

### 8.4 Terminology

- **Silent redirect**: route guard bounce with no user-visible explanation.
- **Permission contract**: the agreement that a page only calls endpoints its role may use.
- **Degraded state**: an explicit "service unreachable, here is what to do" UI, as opposed to empty or fake data.
- **Claims guard**: an automated test that fails when a banned accuracy vintage or non-caveated claim appears.
- **Capability**: a named permission (`manage_users`, `view_system_health`) resolved through the same
  `rolePaths` table the router guard uses — the UI cannot answer "can I?" differently from the guard.
- **Endpoint role matrix**: the mirrored `require_roles(...)` sets for calls that live inside a page a broader
  role set can open (e.g. the risk digest on `/reports`), pinned to the backend source by test.
- **Ratchet**: a per-file budget that a change may lower but not raise (hex-colour debt, bundle size).
