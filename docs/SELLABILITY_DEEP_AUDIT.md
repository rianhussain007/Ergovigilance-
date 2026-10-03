# ErgoVigilance — Deep Sellability Audit

**Date:** 2026-10-03 · **Scope:** "what is still missing before this can be sold" — a product/commercial
audit, not another code-quality pass. **Method:** source reads, live HTTP probes against a
production-mode backend (`DEBUG=false`, strong `AUTH_JWT_SECRET`, port 8077), a browser walkthrough of
the public funnel, and reconciliation against the existing evidence artefacts (`results/`, `outputs/`).
Every finding below is reproducible from the cited file/command.

**How to read the verdicts:** **BLOCKER** = do not take money until fixed. **P1** = will cost deals in
the first serious evaluation. **P2** = costs polish. **EXTERNAL** = cannot be closed in-repo (counsel,
first pilot, pen-test vendor) — the only honest path is to label it pending in the collateral.

---

## 1. Verdict

**The engineering is further along than the commercial surface, and the commercial surface is the
weakest link.** The qualification harness is genuinely strong — `outputs/qualification/latest.json`
verdict **QUALIFIED**, 14 pass / 0 fail / 2 opt-in skip, 765 tests, backup-restore drill and TLS
drill green. That is a real asset.

But selling means answering four questions a buyer's technical evaluator will ask in week one:

| Buyer question | Honest answer today | Blocks a deal? |
|---|---|---|
| "Who can log into this box?" | **Anyone on the network, with no credentials** (§3.1) | **YES** |
| "Where is your accuracy evidence and who produced it?" | **Not reproducible; labeler recorded as `unknown`** (§3.2) | **YES** |
| "Show me the demo." | Works, but the banner **lies about what you're seeing** (§3.3) | **YES** |
| "What does it cost / how do I start?" | Tiers exist; Stripe is not live; **nothing notifies you of a lead** (§4.2) | No — but it wastes every lead |

The single largest commercial risk is **not** the technology. It is that the three claims a buyer
verifies first — access control, accuracy provenance, and demo honesty — are the three that do not
currently survive scrutiny.

---

## 2. What is genuinely ready (do not regress)

1. **Evidence machinery.** `scripts/qualify.py` → `outputs/qualification/latest.json` with a
   machine-readable verdict, per-criterion IDs (TRL7-C4, TRL8-3…), host load captured. This is
   better than most commercial products have.
2. **Contract pack.** `DPA_TEMPLATE.md`, `PRIVACY.md`, `SLA_TERMS.md`, `worker_consent_form.html`,
   `PENTEST_SCOPE.md` — a real pen-test scope pack ready to send to a vendor.
3. **Ops drills.** `deploy/backup_restore_drill.sh`, `deploy/tls_handshake_drill.sh`,
   `deploy/backup.sh`/`restore.sh`, `deploy/k8s/` (ingress, HPA, network policy, pinned secrets
   template), `docs/UPGRADE_RUNBOOK.md` with no-down-migration rollback by design.
4. **Supply chain.** Trivy config/secret/vuln jobs + SBOM in `.github/workflows/ci.yml`;
   `gitleaks` config present; non-root containers.
5. **Secure-by-default posture.** `config.py:39` refuses to boot with `DEBUG=false` and a weak/absent
   `AUTH_JWT_SECRET`; `HOST` defaults to loopback; `TRUST_PROXY_HEADERS` is off by default; per-IP
   rate limiting with a separate 10/min auth bucket; `DUMMY_PASSWORD_HASH` prevents user-enumeration
   timing; no per-account lockout by design (documented anti-DoS choice).
6. **Honesty culture.** `/legal` leads with "Draft — pending legal review … does not describe
   certifications we do not hold." `/status` reports real degraded components rather than a green
   wall. `DATA_COLLECTION_GUIDE.md:185` documents the prelabel circularity trap *before* anyone
   could accuse you of it. Keep all of this — it is the actual differentiator.

---

## 3. BLOCKERS

### 3.1 `POST /api/auth/demo` is an unauthenticated backdoor that stops live monitoring

**Severity: BLOCKER (security + availability + privacy).** Verified in production mode.

`backend_api/app/api/auth.py:264-315` — the route has **no `Depends(get_current_user)`**, no
credentials, and no environment gate. It is rate-limited to 10/min per IP, which is irrelevant:
10 requests is more than enough.

Reproduced against a `DEBUG=false` backend with a strong `AUTH_JWT_SECRET` (the documented production
posture, `config.py:37-39`):

```
$ curl -X POST http://127.0.0.1:8077/api/auth/demo      # no token, no credentials
{"token": "eyJ…", "token_type":"bearer", "expires_in":28800,
 "user":{"id":1,"email":"operator@example.local","role":"operator"}}

$ curl -H "Authorization: Bearer $T" …/api/sessions    -> 200  (9 real sessions)
$ curl -H "Authorization: Bearer $T" …/api/workers     -> 200  (5 workers, incl. real names,
                                                             employee IDs, departments,
                                                             consent_status, identity_mode)
$ curl -H "Authorization: Bearer $T" …/api/alerts       -> 200
$ curl -H "Authorization: Bearer $T" …/api/reports/risk-trend -> 200
```

Three distinct problems, all buyer-visible:

- **Unauthenticated data access.** Anyone who can reach the API gets an 8-hour `operator` token and
  reads worker names, employee IDs, departments and consent status. `/api/users` and `/api/audit`
  correctly 403 (role gate works), but the ergonomic data a factory considers sensitive does not.
- **Availability.** `auth.py:279-283` calls `service.stop_session()` on *any* running session before
  issuing the token. Proven end-to-end:

  ```
  BEFORE anonymous call: {'active': True, 'session_id': 'SESH-2026-10-03_11-39-37', 'fps': 11.61}
  POST /api/auth/demo   (anonymous, no credentials)
  AFTER  anonymous call: {'active': None, 'session_id': None, 'fps': None}
  ```

  A monitoring session a paying customer is relying on is killed by one unauthenticated request. The
  session is saved as a stub, so the shift's monitoring is lost. This is a denial-of-service on the
  product's core function, and it is *the* function being sold.
- **No kill switch.** There is no `ENABLE_DEMO` / `ALLOW_DEMO` / `DISABLE_DEMO` anywhere in the repo
  (verified by grep over `backend_api/app`, tests, scripts, compose, env examples). `.env` ships
  `DEMO_MODE=true`; `docker-compose*.yml` never sets `DEMO_MODE` at all. An operator cannot turn the
  behaviour off in a customer deployment.

**Fix (must be one of these, not a doc note):**

1. Gate the route on an explicit opt-in: return 404 unless `ENABLE_DEMO=true` (default **off**).
   Set it only on the public demo deployment and in the local `.env`.
2. Never call `stop_session()` from an unauthenticated route. If the demo deployment needs a clean
   slate, the demo *start* path should own the reset, behind auth.
3. In production, have `/auth/demo` mint a **demo-scoped** token: a role that can read only
   synthetic/seeded data and cannot touch a live session.

**Acceptance:** `ENABLE_DEMO` unset ⇒ `POST /api/auth/demo` → 404, proven by a new
`backend_api/tests/test_demo_login_gate.py`; a test that starts a session and asserts an anonymous
`/auth/demo` cannot stop it; the compose file sets `ENABLE_DEMO` explicitly.

---

### 3.2 The 87.6% headline number is not reproducible, and its own metadata contradicts the claim

**Severity: BLOCKER (credibility).** This is the product's single most-quoted figure — it appears on
`/`, `/pricing`, `/validation`, and in `ModelCardPage.tsx`.

What the artefacts actually say:

| Claim (customer-facing) | Artefact evidence |
|---|---|
| "agreement with **human assessors** on 500 labeled frames" | `results/ground_truth_evaluation.json` → `"labeler": "unknown"` |
| `ModelCardPage.tsx:23` — "Ground truth: **manual annotation by specialist**" | the only label file on disk: `"labeler": "unknown"`, `"prelabel_source": "timeline.json (provisional, needs human review)"` |
| "500 labeled frames" | the cited label file **does not exist**: `recordings/worker-001/20260812_…/ground_truth_risk.json` → `Labels file not found` |
| reproducible on demand | re-running the eval against the label file that *does* exist yields **`344 labels, 0 matched within 1.0s`** → *"No frames matched — no metrics computed"* |

So the 87.6% currently rests on a source file that is gone, was attributed to a human when its own
metadata says `unknown`, and was seeded from the engine's **own** predictions (`prelabel_source:
timeline.json`) — which `DATA_COLLECTION_GUIDE.md:185` explicitly calls the *"self-consistency trap …
yields ~100% accuracy that means nothing."*

Three further weaknesses a competent evaluator will find immediately, from the confusion matrix:

```
rows = true LOW / MEDIUM      cols = predicted LOW / MEDIUM
[[ 83,  62],
 [  0, 355]]
true LOW    : 145 frames ->  62 called MEDIUM  = 42.8% false-positive rate on safe postures
true MEDIUM : 355 frames ->   0 called LOW
HIGH frames in the evaluation: 0  (the class the product exists to catch is untested)
label distribution: LOW 145 / MEDIUM 355 — no HIGH rows exist to learn from
```

- **42.8% of genuinely safe postures are flagged MEDIUM.** `ModelCardPage.tsx:21-22` states the
  direction ("LOW recall 57% … conservative bias") but not the consequence. An EHS manager will read
  "we flag 4 out of 10 safe postures as a risk" — and that is alert fatigue, the fastest way to get a
  pilot cancelled. There is no measured alert-fatigue / per-shift false-alert rate anywhere.
- **Zero HIGH frames** means the claim rests entirely on the two easier classes. Correctly disclosed
  on `/validation` — keep that.
- **The join is loose.** `evaluate_ground_truth.py:57-58` uses `DEFAULT_FPS = 30.0` with a 1.0 s
  tolerance; measured join error is median **0.279 s**, p90 **0.587 s**, and the max sits exactly on
  the 1.0 s boundary (12% of pairs > 0.5 s). Comparing a prediction to a human label up to 30 frames
  away inflates agreement when posture changes — the product is scored on a blurred target.
- **One session, one site.** Already disclosed; good.

**This does not mean the product is bad. It means the proof is thinner than the sentence claiming it.**

**Fix, in order:**
1. **Either** re-label a proper sample with a *named* labeler (ideally a certified ergonomist — this
   is also the exact deliverable the ₹19,999 assessment tier sells), **or** restate the claim to what
   the artefact supports. Today the defensible sentence is closer to: *"500 frames from one session;
   the label file records the annotator as unknown and the labels were seeded from engine predictions
   pending human review."*
2. **Restore the missing source file** or re-run the evaluation end-to-end so `87.6%` is
   reproducible by a third party in one command. A number a buyer cannot regenerate is a liability.
3. Make the eval script **refuse to publish metrics** when `labeler == "unknown"` or when
   `prelabel_source` names the pipeline — the tool already knows; it just doesn't act on it.
4. Publish the **false-alert rate on safe postures (42.8%)** and the per-shift alert volume. A
   conservative bias is defensible *if declared*; a hidden one is not.

**Acceptance:** `python scripts/evaluate_ground_truth.py --labels <file>` reproduces the published
number from a file present in the repo; the eval refuses `labeler: unknown`; `/validation`,
`ModelCardPage`, `LandingPage`, `PricingPage` and `docs/ASSESSMENT_PRICING.md` all carry the identical
sentence, enforced by an existing-style claims test.

---

### 3.3 The "Try Demo" banner says synthetic while the screen shows real data

**Severity: BLOCKER (trust — the exact failure mode this repo prides itself on avoiding).**

`backend/services/demo_seeding.py:24` reads `DEMO_MODE` **once at import time** as a module constant.
`backend_api/app/api/auth.py:272` sets `os.environ["DEMO_MODE"] = "true"` **at request time**. Setting
an environment variable after a module has been imported does not change the already-bound constant.

Proven:

```
$ curl …/api/demo-mode          -> {"demo_mode": false}     # before
$ curl -X POST …/api/auth/demo  -> 200 + operator token
$ curl …/api/demo-mode          -> {"demo_mode": false}     # AFTER — still false
```

Meanwhile the **frontend sets `demo: true` unconditionally** in local storage
(`AuthContext.tsx:165`), so the app shows `Layout.tsx:81`:
`"DEMO MODE — Showing synthetic data. No real camera or workers are connected."`

But the dashboard it displays is the **real** database. Browser walkthrough after clicking Try Demo:

```
banner text present : "DEMO MODE — Showing synthetic data…"
backend /api/demo-mode : false
real worker names on screen : Asha Patel, Rohan Mehta, Praneeth, Rian, Charan
```

A prospect is told "synthetic data, no real workers" while looking at named workers, and the badge on
the top bar reads a real session ID. This is worse than having no demo: it is the one screen where a
buyer's guard is down, and it teaches them your labels do not mean what they say. In a customer
deployment it is also a privacy incident — a visitor sees real worker names.

**Fix:** make the demo banner **server-authoritative** — render it from `GET /api/demo-mode` (and a
real `source: "demo"` field on the dashboard payload), not from a client-side flag. Either genuinely
switch the repository to synthetic data, or drop the banner and label the screen for what it is.

**Acceptance:** with the backend reporting `demo_mode: false`, no "synthetic data" banner renders; a
vitest asserts the banner is driven by the server response; the walkthrough shows the banner only when
the dashboard payload is genuinely `source: "demo"`.

---

## 4. P1 — will cost deals

### 4.1 The public funnel still carries every claim the website audit flagged

`docs/WEBSITE_TRUTHFUL_AUDIT.md` is dated 2026-10-02 and rates the site 6.9/10. Only T1 (validation
qualifier) is closed. Verified still live on `/` today:

| ID | Still present on the landing page | Where |
|---|---|---|
| T2 | hero **"7 Task Classes Recognized"** vs stats band **"5 Task Classes"** — and both animate from `0` for screen readers | `LandingPage.tsx:50` vs `:914` |
| T3 | "Real screenshots from the platform" caption over stock/AI art | `LandingPage.tsx:75` |
| T4 | **"Scales to 100+ cameras across factories"** — TRL8 item 5 is `PARTIAL-INREPO`; 50-camera qualification needs a cluster | `LandingPage.tsx:764` |
| T5 | **"Real-time processing <100ms latency"** — measured p95 is **379–448 ms** (`outputs/qualification/probe/load_test_results.json`) | `LandingPage.tsx:722` |
| T6 | Pricing FAQ **"Full GDPR compliance"** vs `/legal` "does not describe certifications we do not hold" and TRL8-2 `EXTERNAL-PENDING` | `PricingPage.tsx:97` |
| T8 | "**millions** of positional data points per second" on a MediaPipe engine (33 landmarks × ~12 fps ≈ 400/s) | `LandingPage.tsx:600` |
| T9 | "Monthly SaaS subscription **per camera**" vs canonical **$299/mo per 10 cameras** | `LandingPage.tsx:772` |
| T12 | stats band "87%" vs footnote "87.6%" | `LandingPage.tsx:911` |
| A1 | no `<main>`, no skip link on `/` (confirmed by DOM probe) | `LandingPage.tsx` |
| S1/S2/S3 | one shared `<title>` on all marketing routes; `og:image` is relative `/images/landing-hero.png`; no canonical | confirmed by DOM probe |

**T5 is the one that will actually fail an evaluation**, because you have your own load-test number
saying otherwise. Every one of these is cheap to fix and expensive to be caught on.

### 4.2 Nothing tells the seller a lead arrived

`POST /api/pilot-requests` (`backend_api/app/api/pilot_requests.py:35-45`) writes a SQLite row and
returns 201. There is **no email, no Slack, no webhook, no audit entry** — and the prospect's only
feedback is `"Your pilot request has been submitted successfully. We will contact you shortly."`
(`RequestPilot.tsx:66`), with **no stated response time**. The lead is visible only to an admin who
knows to open `/pilot-requests` and check. A notification service already exists
(`services/notifications.py`, email + Slack, circuit-broken) — wiring it is an afternoon.

**Fix:** notify on submit; state a real response window (e.g. "we reply within 1 business day");
add a status field so follow-up is trackable rather than memory-based.

### 4.3 Three offers, no funnel — and the priced one has no product behind it

`docs/SELL_READINESS_AUDIT.md:7` mapped this and it is unchanged: free 2-week pilot, paid assessment
(₹19,999–79,999), and a 14-day trial button. The trial now degrades gracefully to `/request-pilot`
when Stripe is unconfigured (`PricingPage.tsx:113-139`) — good. But:

- **No `/assessment` page, route, or order form exists.** The assessment tier is the best-positioned
  offer (it is *underpriced on purpose*, per `ASSESSMENT_PRICING.md:9`) and it has a real deliverable
  engine (`backend/services/standard_assessment.py`). It exists only as a markdown price sheet with
  `[contact email] · [phone]` in the contact line.
- `ASSESSMENT_PRICING.md:26` requires **lawyer review before the first paid engagement**, and no
  signed terms exist. You cannot invoice against this sheet today.
- **Prices are un-reconciled.** `ASSESSMENT_PRICING.md` is INR-only; `PricingPage` is USD-only; the
  audit's open Q3 ("$15,000 vs $42,000 per injury") is still open.

### 4.4 No owned proof, and the only social proof is a competitor's

`WEBSITE_TRUTHFUL_AUDIT.md` F1. Testimonials on `/` are TuMeke case studies ("91% reduction in sprains
& strains") attributed in small type. A buyer who reads the source line and discovers the testimonial
is not about you has been actively misled — worse than having no testimonials. Remove or relabel
until the first pilot produces a real quote.

### 4.5 The security questionnaire makes claims the repo cannot support

`docs/SECURITY_QUESTIONNAIRE.md` is the document an enterprise infosec reviewer reads. Verified
against the code:

| Claim | Reality |
|---|---|
| "Cloud Tier: **Encrypted at rest (AES-256)**" | no `aes`/`fernet`/encryption code in `backend_api/app` (grep, 0 hits) |
| "**Kubernetes**: Network policies, pod isolation, HPA" | ✅ true (`deploy/k8s/`) — keep |
| "Audit trail: **SOC2 compliant**" | SOC 2 is an audit, not a feature; no SOC 2 exists (TRL8-2 `EXTERNAL-PENDING`) |
| "Automated backups: **Daily**" | `deploy/backup.sh` exists but daily scheduling is an operator cron, not shipped |
| "DPO contact: **[Insert DPO email]**", "Emergency: **+1-XXX-XXX-XXXX**" | unfilled placeholders in a document sent to security reviewers |
| "4-hour response for critical issues (Enterprise tier)" | matches the SLA copy but no delivery commitment exists |
| (not mentioned) | **§3.1 backdoor** — a reviewer who runs one curl finds it |

Fix before this document is sent anywhere. A questionnaire that is caught overstating is worse than
no questionnaire.

### 4.6 Single-process single-camera — fine, but the packaging implies otherwise

`get_live_service()` returns a module-level singleton (`live_monitor.py:1589-1595`); `get_cameras`
(`repositories/live.py:598-628`) marks only the one camera driving the active session as
`streaming`. So `/cameras` shows a grid where **at most one tile is live**. Load evidence is
20 concurrent users / 41.9 rps / **p95 448 ms** (`load_test_results.json`) — HTTP concurrency, not
camera concurrency. TRL8 item 5 is honestly `PARTIAL-INREPO`. Nothing here is a defect; it is a
**packaging** problem: "$299/mo per 10 cameras" implies a fleet product, and the on-prem tier ships
one. Either scope the tiers to what the pipeline does, or state the multi-camera path explicitly
(`yolo_cloud` RTSP + one backend process per camera, `CURRENT_STATE.md:212`).

---

## 5. P2 — polish that pays

| # | Gap | Evidence / fix |
|---|---|---|
| P2-1 | **Deck is a hackathon artefact.** `Hackathon_MVP.pptx` is the only binary; the sales deck is `docs/SALES_DECK_3SLIDES.md`, and `ui_posture/scripts/generate_pptx.cjs` (41 KB) has never been run — `pptxgenjs` is in root `node_modules`, not `ui_posture/package.json`. | Run/build it, or retire the script |
| P2-2 | **Version numbers disagree three ways:** `CHANGELOG.md` "1.0.0 — production-ready", `package.json` `0.0.0`, `config.py` `0.1.0`, `/health` returns `0.1.0`. | One source of truth; `/health` should agree with the release |
| P2-3 | **27-item sidebar** in the operator app (`Sidebar.tsx`) — demo surfaces (YOLO Demo, Webcam Demo, Architecture, Model Dashboard) sit beside production nav. | Role/group the nav; a supervisor should see ~6 items |
| P2-4 | **Support contacts are fictional.** `support@`/`security@`/`privacy@ergovigilance.com` in `SECURITY_QUESTIONNAIRE.md:115-118` and `DEPLOYMENT.md:510`; `[contact email]`/`[phone]` in `ASSESSMENT_PRICING.md:37`, `ONE_PAGER_RECONCILED.md:50`, `PILOT_OUTREACH.md:27`, `[ADD CONTACT EMAIL]` in `ErgoVigilance_OnePager.md:36`. | A buyer emailing a dead address is a lost deal. Verify or route to a real inbox |
| P2-5 | **`alert()` on demo failure** (`LandingPage.tsx:311`) — the known F3 finding, still open. | Inline error |
| P2-6 | **Pilot form success/error path untested** (F4). One E2E test closes it. | E2E journey |
| P2-7 | **No accessibility automation.** `ux_guards.mjs` is a string lint; A7 recommends axe. | `@axe-core/playwright`, 0 serious/critical on the 6 funnel routes |
| P2-8 | **Fonts from `fonts.gstatic.com`** (S4) — third-party request from a product selling "video never leaves your building". | Self-host |

---

## 6. EXTERNAL — cannot be closed in code

Track these as **pending** in every document that touches them. Do not paper over them.

| # | Item | Owner | Current status |
|---|---|---|---|
| E1 | **Pen-test + remediation** | external vendor | scope pack ready (`PENTEST_SCOPE.md`), not executed |
| E2 | **DPIA + signed DPA/SCCs, SOC 2** | counsel + auditor | templates + endpoints ready; TRL8-2 `EXTERNAL-PENDING` |
| E3 | **First pilot + ergonomist-labelled accuracy re-measure** | customer site | TRL8-9 `SITE-DEPENDENT`; this is what makes 87.6%→real |
| E4 | **50-camera / horizontal scale qualification** | cluster + feeds | TRL8-5 `PARTIAL-INREPO` |
| E5 | **Lawyer review of assessment terms** | counsel | required by `ASSESSMENT_PRICING.md:26` **before first paid engagement** |
| E6 | **Live Stripe keys** | account | billing code is complete; checkout 503s → `/request-pilot` fallback |
| E7 | **Offsite backup replication** | operator policy | drill + RTO measured in-repo |

**E5 is the one with a hard deadline**: it is a stated pre-condition of the *only* offer that does not
need the product to work.

---

## 7. Sequenced plan

### Week 1 — cannot take money without these
1. **Gate `/api/auth/demo`** (§3.1): `ENABLE_DEMO` default off, no `stop_session()` from an
   unauthenticated path, test `test_demo_login_gate.py`. *Highest risk reduction in the repo.*
2. **Fix the demo banner** (§3.3): server-authoritative `demo_mode` / `source: "demo"`.
3. **Fix the 87.6% provenance** (§3.2): restore the missing label file **or** restate the claim; make
   the eval refuse `labeler: unknown`; publish the 42.8% false-alert rate and per-shift alert volume.
4. **Correct §4.1 on the landing page** — especially `<100ms` (T5) and `100+ cameras` (T4), which your
   own evidence contradicts.

### Week 2 — first serious evaluation
5. Notify on pilot-request submit + state a real response time (§4.2).
6. Correct `SECURITY_QUESTIONNAIRE.md` against the code; fill or remove every placeholder (§4.5).
7. Reconcile claims across `/`, `/pricing`, `/validation`, `ModelCardPage`, one-pagers and
   `ASSESSMENT_PRICING.md` — one sentence, enforced by a test, as T1 already does for the qualifier.
8. Unify version numbers (§P2-2); verify or replace support contacts (§P2-4).

### Before the first paid engagement
9. **E5 lawyer review** — then either build `/assessment` order flow (§4.3) or drop the tier from
   collateral until it exists. Publishing a price sheet with no way to buy is a credibility cost.
10. Relabel or remove the TuMeke testimonials (§4.4); ship the deck (§P2-1).
11. Scope tiers to measured capability (§4.6).

### Post-pilot
12. E1–E4 as they unblock. The pilot is the only thing that converts §3.2 from a weakness into the
    strongest asset the product has.

---

## 8. Bottom line

The product works, the tests are real, and the honesty discipline is genuinely unusual — this repo
documents its own circularity trap before anyone could weaponise it. What is missing is not build; it
is **verification hygiene at the three points a buyer touches first**.

Fix §3.1–§3.3 and the product can be shown to a technical evaluator without an ambush. Fix §4.1–§4.2
and a lead has a chance of becoming revenue. Everything else is sequencing.

**The honest one-liner:** the evidence machinery is better than the marketing site admits, and the
three load-bearing claims are weaker than the marketing site claims. Both halves of that sentence are
fixable this week.

---

### Rules obeyed
- `docs/P0_REVERPTION.md` and `docs/TRL7_QUALIFICATION_PLAN.md` untouched.
- Nothing committed; no product code changed by this audit.
- Safe-claim discipline preserved: 87.6% / 500 frames / LOW-MEDIUM only / HIGH unvalidated, screening
  aid not a medical device. No banned vintage introduced.
- `results/ground_truth_evaluation.json` was briefly overwritten by a reproduction attempt and
  **restored from git** — verified byte-identical (`git status` clean for that path).