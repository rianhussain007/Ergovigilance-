# Sell-Readiness Audit — assessment-led funnel (2026-09-26)

Goal: can we sell ErgoVigilance *today* without overclaiming or
under-delivering? Motion under review: paid assessment → free 2-week pilot
→ paid Cloud (`docs/ASSESSMENT_PRICING.md:31-33`). Method: code reads
(billing, orgs, signup, ingest) + sweep of every customer-facing surface
against the Safe Claims Sheet. Verdicts: **BLOCKER** (do not sell until
fixed), **FIX** (should fix, S2), **NOTE** (business call / watch),
**CLEAN**. Owner tags: **[A1]** this session, **[A2]** Agent 2 (owns
`ui_posture/**` writes — `.tsx` fixes are routed, not taken).

## 1. Pricing ↔ code truth

| # | Promise | Code reality | Verdict |
|---|---|---|---|
| F-01 | Tier camera/worker caps (4 / 20 / 50+) | `max_cameras`/`max_workers` are stored only (`organizations.py:25-26`, `database.py:180-186`) and **never checked**: `add_camera` (`yolo_cloud/api.py:102-129`) has no limit check, `CAMERA_SOURCES` env (`config.py:82`) is unlimited, no middleware gates anything | **FIX** [A1]: enforce or officially honor-system |
| F-02 | Canonical tiers starter/cloud/enterprise | Signup mints `plan="pilot"` (`signup.py:114`) — not a canonical tier — with `max_cameras=3` (`signup.py:117,187`) vs Starter's 4 (`PricingPage.tsx:21`); only other plan in code is the `"enterprise"` demo seed (`database.py:177`) | **FIX** [A1]: align 3↔4 and model real tiers |
| F-03 | "14-day free trial" (`PricingPage.tsx:104`, button `:241`) | Trial exists only inside Stripe (`trial_period_days` `billing.py:122`); the product has **no trial clock**, and webhooks are log-only (`billing.py:241-252`) — cancel/expiry changes nothing, the product keeps working | **FIX** [A1]: wire downgrade or reword the promise |
| F-04 | Checkout works | Without live keys, checkout 503s and the page falls back to `/request-pilot` (`PricingPage.tsx:121-129`) — graceful | **NOTE**: live `STRIPE_*` keys required before selling Cloud |

## 2. Claims sweep (Safe Claims Sheet)

| # | Location | Claim | Verdict |
|---|---|---|---|
| F-05 | `MARKETING_ONE_PAGER.md:12,84` | "before injuries happen" / "Preventing injuries before they happen" | **BLOCKER** [A1]: forbidden family — screening language only |
| F-06 | `MARKETING_ONE_PAGER.md:26,55` | "30+ FPS" / "✅ 30 FPS" (incl. competitive claim) | **BLOCKER** [A1]: never measured; 10 FPS/stream itself unmet on CPU 4-stream |
| F-07 | `MARKETING_ONE_PAGER.md:27-28` | "88.6% accuracy" + "86.4% accuracy" on HIGH/LOW/MEDIUM | **BLOCKER** [A1]: banned vintages as *accuracy*, on HIGH |
| F-08 | `MARKETING_ONE_PAGER.md:29` | "unlimited cameras" | **BLOCKER** [A1]: contradicts caps, scale unmeasured |
| F-09 | `MARKETING_ONE_PAGER.md:65,67` | "40% reduction" unhedged; "2-hour ROI" | **BLOCKER** [A1]: hedge like handbook, or drop; ROI timing unmeasured |
| F-10 | `MARKETING_ONE_PAGER.md:66` vs one-pager `$42k` | $15,000/injury vs $42k/injury | **FIX** [A1]: single sourced figure (business call Q3) |
| F-11 | `DEMO_SCRIPT.md:5,15` | "prevents workplace injuries" ×2 | **BLOCKER** [A1] |
| F-12 | `DEMO_SCRIPT.md:38` | "Real-time pose detection (30 FPS)" | **BLOCKER** [A1] |
| F-13 | `DEMO_SCRIPT.md:145-146` | Research-track 88.6/86.4 F1s in the sales script | **FIX** [A1]: label research-only + MEDIUM weakness, or drop |
| F-14 | `PricingPage.tsx:99-100` | "Cloud (YOLO) achieves 94.1% cross-validated F1" on the pricing page | **BLOCKER** [A2]: Sheet bans the vintage — replace with 87.6% + pilot line |
| F-15 | `README.md:38,126-127,237-238` | 97.6% / 94.1% "accuracy" on the root README + model tree | **BLOCKER** [A1] |
| F-16 | `README.md:84` | "Real-time pose estimation at 30 FPS" | **BLOCKER** [A1] |
| F-17 | `README.md:288` | "91.8% holdout accuracy" headline-adjacent | **FIX** [A1]: demote to provenance note (register: advisory only) |
| F-18 | `PricingPage.tsx:53` | "99.5% uptime target" | **NOTE**: the word "target" saves it — keep, revisit post-pilot |
| F-19 | `PricingPage.tsx:77` | Enterprise "SLA with 4-hour response" | **FIX** [A1+user]: no SLA terms doc exists (only `sla_monitor.py`) — write minimal terms or drop the line |
| F-20 | `ValidationPage.tsx` | Honest ladder, caveats, no-claim section | **CLEAN**; nit `ValidationPage.tsx:125` "230+ test suite" is stale-low → routed [A2] |
| F-21 | `SALES_DECK_3SLIDES.md` | Self-policing (DRAFT banner + claim checklist `:70-77`); slide 2 "100% offline" is true in its on-prem context (`:30-34`) | **CLEAN**; checklist `:77` "evaluation still pending" is stale → allow 87.6%-with-caveats [A1] |
| F-22 | `SALES_ONE_PAGER.md`, `PILOT_OUTREACH.md`, one-pagers, handbook | 87.6%-with-caveats discipline held; handbook hedges industry figures | **CLEAN** |

## 3. Funnel walk (assessment-led)

Signup → `plan="pilot"` org (3 cams/50 workers, no expiry) → onboarding
wizard → demo tour → first report: the loop runs, but nothing converts or
expires it (F-01–F-03). Assessment product is the coherent front door:
tiers `ASSESSMENT_PRICING.md:15-17`, 50% conversion credit `:19`, honest
terms `:24-28`, conversion path `:31-33` ("free 2-week pilot → Cloud /
Enterprise; never auto-enrolls"). Three parallel offers exist (free pilot
CTA on `/validation`, paid assessment, trial button) — each honest alone;
**NOTE**: publish one funnel map so sales never mixes them in a quote.

## 4. Contract pack

`DPA_TEMPLATE.md` ✓ (blanks normal for a template); worker consent form +
one-pager ✓; `SECURITY_QUESTIONNAIRE.md` exists (freshness re-check after
Agent 2's TRL-8 lane — NOTE). Missing: customer-facing **SLA terms doc**
(F-19). `ASSESSMENT_PRICING.md:26` requires lawyer review *before first
paid engagement* — **user action**, confirm before selling.

## 5. Business questions (need answers before S2 builds policy)

- **Q1** Entitlements: hard-enforce caps in code, or honor-system + contract terms?
- **Q2** Signup default: 3 cameras → 4 to match Starter, or keep 3 as the pilot grant?
- **Q3** Injury figure: $15k or $42k (single sourced number)?
- **Q4** Enterprise SLA line: write minimal terms now, or drop until TRL-8?
- **Q5** Lawyer review of DPA/assessment terms: done?
- **Q6** Keep all three offers (free pilot / paid assessment / trial button) with a funnel map, or consolidate?

## 6. S2 preview (scoped by this audit, pending answers)

| Fix | Owner | Shape |
|---|---|---|
| F-01/F-02/F-03 entitlements + plans + webhook downgrade | [A1] | `billing.py`/`organizations.py`/`signup.py` + ingest check + targeted pytest (new `test_entitlements.py`-style file) |
| F-05–F-09, F-11–F-13, F-15–F-17, F-21 | [A1] | `.md` claim patches to Sheet language |
| F-14, F-20 nit | [A2] | `.tsx` fixes in its frontend lane |
| F-19 SLA terms | [A1] draft + user sign-off | new `docs/SLA_TERMS.md` (minimal, hedged) or drop the PricingPage line via [A2] |

## Rules obeyed

- Safe Claims Sheet untouched; this audit fixes copy *toward* it.
- Every cite is `file:line` verified at HEAD (`5d71cc0`) this session.
- No product code changed; no Agent 2 / deploy-session files touched.
