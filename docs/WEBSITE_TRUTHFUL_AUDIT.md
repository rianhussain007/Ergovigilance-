# Website Audit — truthful rating and the plan to 10/10

**Date:** 2026-10-02 · **Scope:** the public website a visitor actually sees (`/`, `/pricing`,
`/validation`, `/request-pilot`, `/login`, `/signup`, `/legal`, `/status`) plus spot-checks of the
authenticated app (demo mode), evaluated live at `localhost:3000` against the running backend,
cross-checked against source and the repository's own evidence files.

**Method:** browser walkthrough at 1440×900 and 390×844 (screenshots + accessibility tree + DOM
probes), console/network log inspection, source reads, and a fresh run of every automated gate.
No score below is softened and none is inflated: this rates the **website as a visitor experiences
it today**, which is a different surface from the app-side enterprise scorecard in
[`UI_UX_ENTERPRISE_AUDIT.md`](UI_UX_ENTERPRISE_AUDIT.md).

---

## 1. Verdict

> ### Overall: **6.9 / 10** — a strong product story held back by marketing-site truth gaps,
> marketing-side accessibility, and SEO basics. Not an 8 yet, and not a 6 either.

| # | Dimension | Score | One-line justification |
|---|---|---|---|
| 1 | Visual design / first impression | **7.5** | Cohesive dark theme, strong hero, consistent cards; stock/AI imagery and oversized section gaps keep it from 8+ |
| 2 | **Truthfulness of claims** | **6.0** | Core positioning is unusually honest, but 6 concrete overclaims/inconsistencies are live (see §3) |
| 3 | Accessibility (marketing surfaces) | **5.5** | App is ~8 (skip link, dialogs, tests); marketing pages fail on landmarks, names, form labels, contrast |
| 4 | Performance & technical quality | **8.0** | Entry 40 kB gzip, total 456 kB, budget gate in CI, clean console; no field/Lighthouse data yet |
| 5 | SEO & shareability | **5.5** | Full meta tag set, but identical titles across routes, relative `og:image`, no canonical/JSON-LD |
| 6 | Conversion funnel | **7.0** | Working no-login demo, clear CTAs, graceful trial fallback; unlabeled pilot form, no owned proof |
| 7 | Trust & compliance UX | **7.0** | Screening-aid lines, honest legal draft, live status page; "Full GDPR compliance" claim contradicts the legal page |
| 8 | Consistency & polish | **6.5** | Same-page number contradictions (7 vs 5 task classes; 87 vs 87.6), Log In/Sign In wording drift |
| 9 | Mobile / responsive | **7.5** | No horizontal overflow at 390 px, working hamburger + drawer, cards stack cleanly; unnamed toggle |
| 10 | Engineering gates | **8.5** | tsc clean · **275/275** tests · ux_guards 0 violations · bundle budget green — re-verified this date |

**Re-verified 2026-10-02 (all from `ui_posture/`):** `npx tsc --noEmit` clean · `npx vitest run`
**275/275, 14 files** · `node scripts/ux_guards.mjs` 0 violations (141 files) ·
`node scripts/check_bundle_budget.mjs` within budget (62 chunks, 1605 kB raw / 456 kB gzip,
entry 40 kB gzip) · browser console: 0 errors, 0 failed requests · no horizontal overflow at 390 px.

**Re-verified 2026-10-03 (after the T1/F1 fix pass):** `tsc` clean · vitest **276/276**
(275 + the new `/validation` claims guard) · ux_guards 0 violations · bundle 456 kB gzip ·
full browser E2E **27/27** with B6 (the T1 qualifier check) green.

---

## 2. What is genuinely good (keep — do not regress)

1. **The honest core.** The landing stats footnote carries the full safe claim —
   "87.6% agreement with human assessors on 500 labeled frames (LOW/MEDIUM risk). HIGH-risk …
   ongoing … screening aid, not a medical device". The pricing FAQ repeats it correctly.
2. **`/legal` is exemplary.** "Draft — pending legal review … not reviewed by counsel … does not
   describe certifications we do not hold." This is the tone the whole site should have.
3. **Demo honesty.** "Try Demo — No Login Required" actually works, and the app banner says
   "DEMO MODE — Showing synthetic data. No real camera or workers are connected."
4. **`/status` reports real health** (showed Backend operational, cloud core degraded, database
   degraded — matching the actual environment), not a fake green wall.
5. **Pricing matches canonical pricing** ($299/mo per 10 cameras, $239 annual ≈ Save 20%, Starter
   = 4 USB cameras which matches the backend pilot entitlement enforced by `claims.test.ts`).
6. **Checkout degrades honestly** (`PricingPage.tsx:113–139`): anonymous or Stripe-unconfigured →
   redirect to `/request-pilot` instead of a dead 401.
7. **Reduced-motion is global** (`index.css:226`) and `*:focus-visible` styles exist.
8. **Gates are real** — the claims/ux-guards/bundle gates run in CI and all pass today.

---

## 3. Findings — truthfulness (the score-killer)

| ID | Sev | Finding | Evidence | Fix |
|---|---|---|---|---|
| T1 | **HIGH** → ✅ **RESOLVED 2026-10-03** | The Validation page — the page whose job is honest accuracy — shows a bare **"87.6% overall accuracy"**: no *500 frames*, no *LOW/MEDIUM only*, no *HIGH unvalidated*. "Overall" is exactly the wording the Safe Claims sheet forbids | Original: DOM probe of `/validation`: `has500=false, hasLOWMED=false, hasHIGH=false`. **Now fixed:** hero subtitle reads "agreement with human assessors on 500 labeled frames" + scope line (LOW/MEDIUM only, HIGH not yet validated, single-site, screening aid) | **Done:** `ValidationPage.tsx` qualifier added; `claims.test.ts` gained `qualifies the dynamically rendered accuracy headline on ValidationPage`. Verified live: E2E journey **B6 ✅** (browser), vitest 276/276 |
| T2 | **HIGH** | Same landing page claims **7** "Task Classes Recognized" (hero) and **5** "Task Classes" (stats band); changelog says 5 work classes | `LandingPage.tsx:50` vs `LandingPage.tsx:912` | Pick the true number (5), fix the other, add a number-consistency test |
| T3 | MED | "Real screenshots from the platform" caption sits over mixed stock/AI art; the hero image contains unrelated **"APEX" branding** | `LandingPage.tsx:75` (caption), hero image overlay | Use real product screenshots (exists: `public/images/dashboard-*.png`, `readme-*.png`); drop or crop third-party-branded art |
| T4 | MED | "**Scales to 100+ cameras** across factories" — TRL-8 says even the 50-camera load qualification needs a cluster + feeds (item 5 PARTIAL-INREPO) | `LandingPage.tsx:719` vs `TRL8_QUALIFICATION_EVIDENCE.md` §3 | "Designed for multi-camera sites; fleet-scale load qualification in progress" |
| T5 | MED | "**Real-time processing <100ms latency**" is unproven: proving <100 ms is listed as a *to-do* in `SELLABLE_PRODUCT_ASSESSMENT.md:74`; the SLA target is p95 < 200 ms | `LandingPage.tsx:720`, `sla_monitor.py:11` | "Sub-200 ms end-to-end (target)" or cite a measured number |
| T6 | **HIGH** | Pricing FAQ claims "**Full GDPR compliance**" while `/legal` explicitly says the product holds no certifications and TRL8-2 (DPIA/DPA/SOC2) is EXTERNAL-PENDING | `PricingPage` FAQ vs `LegalPage.tsx` intro, `TRL8_...` §3 | "GDPR-aligned: erasure, retention controls, DPAs available — certification pending" |
| T7 | MED | Testimonials use **named people from TuMeke case studies with outcome stats** ("91% reduction in sprains & strains") under a heading that reads like customer proof; a source note exists but is small | `LandingPage` INDUSTRY INSIGHT section, note "Source: TuMeke case studies" | Relabel loudly as "Industry examples — third-party case studies", or replace with pilot data (preferred) |
| T8 | LOW | "**Proprietary** spatial computing engine processes **millions** of positional data points per second" — the engine is MediaPipe-based; 33 landmarks × 30 fps ≈ 990 points/s/camera | `LandingPage.tsx:113` | "Our pose pipeline…" / "hundreds of measurements per second" |
| T9 | LOW | Cloud card says "Monthly SaaS subscription **per camera**" vs canonical **$299 per 10 cameras** | `LandingPage` YOLO card vs `PricingPage.tsx` | "$299/mo per 10 cameras" |
| T10 | MED | FAQ promises "14-day free trial … **start monitoring immediately** after signing up" but Stripe keys are not live, so the CTA silently reroutes to `/request-pilot` | `PricingPage.tsx:113–139`, `DEEP_AUDIT_REPORT` (billing needs live keys) | Either wire Stripe or reword: "Cloud trial on request while self-serve billing is in beta" |
| T11 | LOW | "Deploy in **under 10 minutes**" (pricing) vs "**~30-min** laptop install" (pilot copy) | pricing CTA vs `PILOT_OUTREACH.md` | One number everywhere |
| T12 | LOW | Stats band shows **87%** while the footnote directly below says **87.6%** | `LandingPage.tsx:911` vs stats footnote | Show 87.6% or drop the band figure |

## 4. Findings — accessibility (marketing surfaces)

| ID | Sev | Finding | Evidence | Fix |
|---|---|---|---|---|
| A1 | HIGH | Landing page has **no `<main>` landmark and no skip link** (login and the app do) | a11y tree: nav → content → contentinfo only | Wrap page body in `<main id="main">` + skip link like the app's |
| A2 | HIGH | **Request-a-Pilot form: 6/6 fields have no programmatic label** — no `label[for]`, no wrapping label, no aria-label. This is the conversion form | DOM probe on `/request-pilot` | `htmlFor`/`id` on every field; add an `ux_guards` rule `form-labels` |
| A3 | MED | **Hamburger button has no accessible name** (icon only); mobile menu opens correctly but SRs announce "button" | `LandingPage.tsx:~357`, a11y tree `button [focusable]` unnamed | `aria-label="Open menu"` + `aria-expanded` |
| A4 | MED | **3 carousel dot buttons unnamed** | `LandingPage.tsx:274–281` | `aria-label={`Show slide ${i+1}`}` + `aria-current` |
| A5 | MED | Small text below WCAG AA 4.5:1: excluded pricing features `text-slate-600` on `#0b0f14` ≈ **2.6:1**; testimonial outcome lines 10 px @ 60 % opacity | computed styles on `/pricing`, `/` | Raise to ≥ slate-400 at ≥ 4.5:1; verify with axe |
| A6 | LOW | Animated counters expose **"0"** to assistive tech until they intersect | a11y tree (`"0" Task Classes…`) | Render final value in DOM, animate a visual overlay, or `aria-hidden` the animation |
| A7 | MED | **No axe-core automation** — `ux_guards.mjs` is a string-lint, not an accessibility engine | CI config | Add `@axe-core/playwright` (or vitest-axe) for landing/pricing/validation/pilot/login |

Positives to keep: `*:focus-visible` styles, global reduced-motion, app skip link, dialog
semantics, one `<h1>` per page (42-page test), descriptive image alts on the hero/feature shots.

## 5. Findings — SEO / shareability / funnel

- **S1** Every marketing route ships the same `<title>` ("ErgoVigilance — AI-Powered Ergonomic
  Risk Monitoring") and description; only app pages set per-page titles. → unique title+meta per
  marketing route.
- **S2** `og:image` / `twitter:image` are **relative paths** (`/images/landing-hero.png`) — social
  scrapers need absolute URLs. → `https://ergovigilance.com/images/…`.
- **S3** No canonical link, no JSON-LD (`SoftwareApplication`/`FAQPage`), `sitemap.xml` not
  verified. → add all three.
- **S4** Fonts load from **fonts.gstatic.com** on every visit — a third-party request from a
  product that markets "video never leaves your building"; also a GDPR nit and a perf cost.
  → self-host the Inter woff2 subset.
- **F1** No owned social proof: the only testimonials are a competitor's; no pilot results, logos,
  or case study. The fastest true upgrade is a real pilot quote (see plan).
- **F2** `contact@ergovigilance.com` in the footer is unverified; the one-pager still carries
  `[ADD CONTACT EMAIL]`.
- **F3** Demo failure path uses `window.alert` (`LandingPage.tsx` `handleTryDemo`) — jarring and
  inaccessible; use an inline error state.
- **F4** Pilot form success/error states were not exercised (input harness died during the
  walkthrough); needs an E2E test with a clearly-marked test record.

---

## 6. Plan to 10/10

Everything below is in-repo work unless marked **EXTERNAL**. Each item has an acceptance
criterion that is machine-checked — the point of 10/10 is that the score can no longer drift.

### P0 — Truth and legal (do first; these are liability, not polish)

1. **Fix T1** ✅ **DONE 2026-10-03**: full qualifier under the Validation hero number —
   now reads "87.6% agreement with human assessors on 500 labeled frames" with the scope line
   "LOW/MEDIUM risk only, HIGH not yet validated, single-site".
   *Accept (met):* `claims.test.ts` asserts the qualifier on `/validation` and fails if removed
   — test `qualifies the dynamically rendered accuracy headline on ValidationPage` is green,
   and E2E journey B6 passes against the live page.
2. **Resolve every number contradiction (T2, T12, T11, T9)**: one canonical fact table
   (task classes, accuracy, install time, price unit) consumed by landing/pricing/outreach docs.
   *Accept:* a `facts.test.ts` parses LandingPage + PricingPage and fails on drift.
3. **Kill the unproven claims (T4, T5)**: `<100ms` and `100+ cameras` reworded to measured or
   aspirational-but-labeled language. *Accept:* `ux_guards.mjs` gains rules banning
   `<100ms`/`100+ cameras` on marketing pages (ratchet allowlist for docs).
4. **Fix the GDPR claim (T6)** to "GDPR-aligned … certification pending", matching `/legal`.
   *Accept:* guard rule bans "Full GDPR compliance" until TRL8-2 closes (**EXTERNAL**: counsel).
5. **Reframe third-party testimonials (T7)** with an unmistakable "industry examples, source:
   TuMeke case studies — not ErgoVigilance customers" label, or delete until own proof exists.
6. **Honest trial copy (T10)**: match what the button actually does today.

### P0 — Accessibility on the funnel

7. `<main>` + skip link on landing (A1); labels on all six pilot-form fields (A2); accessible
   names on hamburger + dots (A3/A4); contrast lift (A5); counters a11y (A6).
   *Accept:* new `ux_guards` rules (`form-labels`, `button-names`) + axe run in CI with
   **0 serious/critical violations** on `/`, `/pricing`, `/validation`, `/request-pilot`,
   `/login`.

### P1 — SEO and sharing

8. Unique `<title>` + meta description per marketing route; absolute `og:image`; canonical;
   `sitemap.xml` + `robots.txt`; JSON-LD (`SoftwareApplication` + `FAQPage`).
   *Accept:* a test iterates marketing routes and fails on duplicate titles or relative
   `og:image` — plus a Lighthouse SEO ≥ 95 on each route (**EXTERNAL**: real deployment).

### P1 — Conversion and proof

9. Replace stock/AI art with real product screenshots (T3, hero "APEX" artifact removed).
10. Ship one **real** proof unit: pilot result, screenshot-backed case study, or a signed quote —
    then feature it above the TuMeke quotes. (**EXTERNAL**: needs the first pilot site.)
11. Inline error instead of `alert()` (F3); E2E test of pilot-form submit + success state (F4).
12. Verify the contact address; remove every `[PLACEHOLDER]` from visitor-facing surfaces.

### P1 — Performance

13. Self-host fonts (drop `fonts.gstatic.com`), `loading="lazy"` + explicit dimensions on all
    below-fold images, keep the existing bundle budget gate.
    *Accept:* Lighthouse Performance ≥ 95 and Accessibility ≥ 95 on the deployed site
    (**EXTERNAL**: RUM from a real deployment).

### P2 — Visual polish

14. Tighten section rhythm (several landing sections have 500 px+ empty gaps), one imagery
    language, fix the "Analytics-highlighted-while-on-Settings" hover ambiguity spotted in the
    app shell, unify Log In / Sign In wording.

### P2 — Keep it true (gates)

15. CI additions: axe job, `facts.test.ts`, extended `ux_guards` rules above, and a Playwright
    smoke that walks landing → demo, landing → validation, pricing → pilot CTA.
    *Accept:* all run on every PR; a planted violation exits non-zero (probe test, as with
    `ux_guards.mjs` today).

### Definition of "10/10" (all must be true and machine-checked)

- **0** axe serious/critical violations on the six funnel routes.
- **0** numeric or claim contradictions — enforced by `facts.test.ts` + extended `claims.test.ts`.
- Lighthouse ≥ **95** performance / accessibility / SEO / best-practices on production.
- Unique titles + working social preview cards per route.
- Every visitor-facing claim traced to a file in this repo or explicitly labeled as a target.
- ≥ 1 piece of **own** social proof live; contact and legal surfaces final.
- All external items closed or visibly labeled as pending: counsel review, first pilot,
  pen-test, DPIA (**EXTERNAL** — nothing in-repo substitutes for these).

**Honest bottom line:** the product and its evidence machinery are already better than the
marketing site admits in places and better than it claims in others. Fix the six truth gaps, the
four accessibility failures on the funnel, and the SEO basics, and this score moves from **6.9 to
≈8.5**; the last stretch to 10 depends on external proof — a real pilot, counsel sign-off, and
field data — that no amount of in-repo work can fake.
