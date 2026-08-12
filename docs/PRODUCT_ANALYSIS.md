# ErgoVigilance — Product Analysis & Go-To-Market Assessment

**Prepared:** 2026-08-08
**Audience:** Rian (founder/developer), AI reviewers, potential investors/advisors
**Purpose:** Give a brutally honest, evidence-based answer to: *What do we have? What is it worth? Is there a market? Can we sell it? What's left? Should we change the stack?*

---

## 0. Executive Summary (read this if you read nothing else)

**ErgoVigilance today is a working, demoable, offline-first AI ergonomics monitoring platform — one of the most complete student/research projects in this space — but it is not yet a sellable product.** It is arguably a **validated MVP with a real architecture and a real pipeline**, and it sits 60–70% of the way to a minimum sellable product.

The one-line verdict:

> **The tech is real. The need is real. The market is real. The product is not finished — but the gap between where it is and where it sells is well-defined and closable.**

What you have that most projects in this space do **not** have:

| Asset | Why it matters |
|---|---|
| A **working end-to-end pipeline** (camera → MediaPipe pose → biomechanical features → risk engine → alerts → recommendations → session recording → replay → reports) | Competitors' demos are slides. Yours runs on a webcam. |
| **Offline-first architecture** (local SQLite + local Ollama, zero cloud dependency) | Rare and actually valuable for factories with no internet / privacy rules |
| **Role-based auth, audit trails, per-worker data deletion (right-to-erasure), retention policies** | This is *regulatory-readiness* — most MVPs in this space have none of it |
| **Trained ML models** (task classifier + REBA-calibrated risk overlay, 30,698 labeled poses) | Most student projects use raw thresholds only |
| **A 25-file pytest suite + 22 legacy engine test scripts + CI with model-checksum governance** | Institutional-grade discipline for a student project |
| **PDF/CSV/JSON report exports + PDF rendering via Playwright** | Real deliverable artifacts that safety managers can file |

What you **don't** have yet (the honest gap):

- **Multi-person tracking** — one webcam tracks one person. Factories have many workers per camera view.
- **Clinical validation** — thresholds are tuned against a REBA dataset, but no ergonomist has validated them. You cannot make medical-grade claims yet.
- **Cloud/multi-site** — it's a single-machine deployment. No fleet management, no central dashboard for a safety manager across 5 plants.
- **Deployment hardening** — no tested multi-worker server deployment, no real TLS test, no auto-updates, no installers.
- **Real customer feedback** — zero customers, zero pilot sites, zero usage data beyond your own testing.
- **Marketing/sales surface** — no pricing, no sales deck, no case study, no landing page beyond the app itself.

**Market verdict:** Yes, there is a demonstrated need (WMSDs cost employers real money, OSHA records it, existing tools are manual/expensive), and yes, the differentiation (real-time, camera-only, offline, affordable, explainable) is compelling. But the buyers (safety managers) buy on **trust, evidence, and integration** — not on demos. The path to a first sale is a **pilot with one real customer**, which this codebase is genuinely ready to attempt.

---

## 1. What Is Built Today (the verified inventory)

Everything below is backed by code inspection, running tests, or runtime evidence. 25 pytest files + 22 legacy engine scripts + 17 React pages.

### 1.1 The AI/CV Core (`backend/`)

| Module | What it does | Verified? |
|---|---|---|
| **PoseEngine** | MediaPipe PoseLandmarker (33 landmarks, VIDEO mode), 1280×720/640×480 negotiation, ~15–20 FPS on CPU, lite model default, full model optional | ✅ live sessions + video analysis |
| **Feature extraction** | 9 ergonomic features from the 33 landmarks (neck flexion, trunk flexion, left/right shoulder elevation, shoulder symmetry, alignment deviation, knee angle, wrist velocity, head tilt, etc.) with EMA smoothing | ✅ unit-tested |
| **ContextIntelligenceEngine** | 0–100 risk score: per-feature linear scoring → base risk → context modifiers (task, fatigue, exposure, confidence) → hysteresis safety states (SAFE/OBSERVE/RECOVERY/CRITICAL) | ✅ verified on 16,904-frame session |
| **Fatigue model** | Exponential fatigue curve + exposure accumulator with body-region weighting | ✅ |
| **Alert Engine** | 3 rules (high_risk, critical_risk, recovery) with cooldowns, ACTIVE→RESOLVED lifecycle, SQLite persistence | ✅ 143 alerts in one 30-min session |
| **Recommendation Engine** | 12 explainable templates (posture, break, workstation, training, supervisor, medical) — each traces to the feature/threshold that triggered it | ✅ |
| **History Engine** | Tiered storage (full res 5 min, then 10× downsample), 50k cap | ✅ |
| **Task Recognition** | 5 task classes (Neutral Standing, Assembly, Reaching, Lifting, Inspection) via Gaussian scoring + temporal smoothing + confidence-gated ML model (HistGradientBoosting) | ✅ 76.9% accuracy on synthetic; needs real data |
| **AI Assistant** | Local Ollama RAG (qwen2.5:1.5b + embeddings) over knowledge corpus + live session-data tool-calling | ✅ end-to-end verified |
| **REBA risk calibration** | HGB model trained on 30,698 REBA-labeled poses as a risk overlay | ✅ |
| **Wrist velocity** | px/s computation for the Reaching classifier (the fix that made Reaching work in production) | ✅ unit-tested |

### 1.2 The API Layer (`backend_api/`)

- **~35 endpoint modules**: auth, dashboard, sessions, reports, alerts, video feed (MJPEG), video analysis (upload ≤200 MB → background job), recordings, replay, analytics, worker trends, risk trends, safety reports, audit trail, pilot requests, settings, retention, privacy, observations/override (new), assistant, cameras, workstations, deployment, manager, users, workers, task config.
- **Auth**: SQLite + bcrypt + JWT, 4 roles enforced server-side (403s), login rate-limit/lockout, mandatory `AUTH_JWT_SECRET` outside debug, fail-closed live mode (503 instead of mock data).
- **Observability**: `/healthz`, `/readyz`, `/metrics` (Prometheus), structured logging.
- **Persistence**: sessions → JSON files + CSV index; recordings → MP4 + timeline.json + summary.json + observations.json; video-analysis jobs → SQLite (survive restarts); alerts → SQLite.
- **Retention**: age-based + disk-cap guardrail, manual run endpoint.
- **Privacy**: per-worker right-to-erasure endpoint.
- **WebSockets**: `/ws/dashboard`, `/ws/alerts`, `/ws/camera`.

### 1.3 The Frontend (`ui_posture/` — React 19 + Vite 6 + Tailwind 4)

**17 pages**, all rendering real backend data (no mock pages remain — the last hardcoded placeholders were replaced in 2026-08):

Dashboard (role-differentiated), Live Monitoring (camera + overlay toggle + risk gauge + telemetry + timeline + Override/Log buttons), Video Review (upload + analysis), Session History + Replay (video + synced timeline + notes + export), Analytics, Reports (risk trend, safety, worker trends — PDF/CSV/JSON), Sessions, Workers, Users, Multi-Camera, Manager, Deployment, Audit Trail, Pilot Requests, Settings, AI Assistant panel.

### 1.4 DevOps & Governance

- Docker Compose (backend + nginx frontend), Dockerfiles, healthchecks.
- CI (GitHub Actions): frontend lint+build+audit, backend pytest + 22 legacy scripts + pip-audit + **model manifest checksum verification** — green.
- `docs/`: CURRENT_STATE, VISION_AND_ROADMAP, PRIVACY, OPS_RUNBOOK, module HLDs.
- Model governance: `models/MANIFEST.json` + `verify_models.py`.

### 1.5 Data Assets

| Dataset | Rows | Source | Use |
|---|---|---|---|
| `data/processed/reba_features.csv` | **30,699** | REBA-labeled poses (downloaded rebapose corpus) | Risk-calibration model + threshold tuning |
| `data/processed/dataset_final.csv` | 5,921 | Synthetic task clips | Task classifier v2 |
| `outputs/sessions/` | 71+ real session files | Your own testing | Reports, trends, replay |

---

## 2. The Market — Is There a Need? Will People Buy It?

### 2.1 The problem is real and expensive

- **Work-related musculoskeletal disorders (WMSDs)** are the #1 cause of lost workdays in manufacturing/warehousing worldwide. In the US alone, they account for roughly **30% of all workers' comp costs** and millions of lost workdays per year (OSHA/BLS data).
- Employers are **legally and financially exposed**: OSHA recordkeeping, workers' comp premiums, and in some jurisdictions **ergonomic standards/regulations** (e.g., California's Cal/OSHA ergonomics standard, EU directives).
- The **cost per serious WMSD case** can reach $30k–$100k+ in comp + lost productivity.

### 2.2 The incumbent tools are weak

| Category | Example | Weakness ErgoVigilance attacks |
|---|---|---|
| **Manual checklists** | RULA/REBA/OWAS pen-and-paper | Point-in-time, requires a trained assessor physically present, can't run a full shift |
| **Wearable sensors** | Upright, Kinvent, dorsaVi | Per-worker hardware cost ($100s/worker), workers refuse to wear them, battery/charging logistics |
| **Premium camera systems** | Soter Analytics, Ethos, Velvet | **$10k–$50k+ per site**, require consultants, closed ecosystems |
| **DIY/LLM advice** | "ChatGPT my posture" | Not evidence-backed, not auditable, no reporting |

**ErgoVigilance's wedge:** a camera-only system using hardware the factory *already owns* (webcams/IP cameras), running continuously across a shift, producing **auditable, evidence-backed reports** — at a price point an SME can afford. The offline-first design means it works on factory floors where cloud connectivity is poor or forbidden.

### 2.3 Who would buy it, and what do they pay for?

| Buyer | What they actually pay for | Willingness to pay |
|---|---|---|
| **Safety manager at a mid-size manufacturer (50–500 workers)** | Proof of risk reduction + OSHA/insurance documentation + "we're doing something" | $500–$3,000/mo per site |
| **EHS consultant** | A tool that generates reports faster than manual REBA assessments (they bill hours) | Subscription per assessment |
| **Insurance carrier / workers' comp** | Risk reduction across policyholders | Partnership/licensing |
| **Universities/research** | A validated research instrument | Grant-funded licenses |
| **Warehouse/logistics operators** | Fewer comp claims, less turnover | Per-seat/per-camera |

### 2.4 Honest competitive assessment

| Dimension | ErgoVigilance | Soter (market leader) | DIY |
|---|---|---|---|
| Real-time continuous monitoring | ✅ | ✅ | ❌ |
| Camera-only (no wearables) | ✅ | ❌ (wearable) | ✅ |
| Offline / on-prem | ✅ | ❌ (cloud) | ✅ |
| Explainable alerts (why, which joint, which threshold) | ✅ | partial | ❌ |
| Role-based dashboards + audit trail | ✅ | partial | ❌ |
| Report exports (PDF/CSV/JSON) | ✅ | ✅ | ❌ |
| Multi-person tracking | ❌ | ✅ | ❌ |
| Clinical/ergonomist validation | ❌ | ✅ | ❌ |
| Sales/marketing/enterprise polish | ❌ | ✅ | — |

**Verdict:** You win on **price, privacy, explainability, and offline operation**. You lose on **multi-person, validation, and polish**. The first two are the correct next engineering bets; the third is a packaging/sales problem, not an engineering one.

---

## 3. Can We Sell It? — The Honest Three-Path Verdict

**Path A — Sell it as-is (a product):** ❌ **Not yet.** Single-person tracking and no clinical validation are disqualifying for serious buyers. No customer references. You'd get "impressive demo, can you call back in a year."

**Path B — Sell it as a service (you + an ergonomist deliver assessments):** ✅ **Closest to revenue today.** Use the tool to generate REBA-style assessment reports for real clients. The tool becomes your leverage; the ergonomist provides the validation/credibility. This is how many ergo-consultants actually operate. **You can start this in weeks, not months.**

**Path C — Pivot/leverage into a funded startup:** 🟡 **Possible, with a specific plan.** The differentiators (offline, camera-only, explainable, affordable) are real. VCs in industrial-tech/health-safety will want: multi-person tracking, a pilot customer, and a validation partner (university ergonomics lab or an EHS consultancy). This is a 6–12 month path.

**My recommendation:** **B now, A/C later.** Land one paid pilot (or one unpaid-but-real factory trial) using the current system with one camera per worker. Collect real usage data. That data + a validation partnership is what converts B into A/C.

---

## 4. What's Left — The Production Gap, Prioritized

### Tier 1 — Must-have before ANY paying customer (engineering)

| # | Item | Why | Effort |
|---|---|---|---|
| 1 | **Multi-person tracking** (2–4 workers per camera) | The #1 objection from every real buyer. MediaPipe supports `num_poses>1`; the state model is the work (per-person sessions, per-person analytics) | 2–4 weeks |
| 2 | **Multi-camera / multi-session management** (N cameras → one backend, per-camera sessions) | Factories need 5–20 cameras, not 1. The raw-feed manager exists; session orchestration doesn't | 2–3 weeks |
| 3 | **Pilot-friendly deployment** (one-command installer, IP-camera support, Windows service) | You can't sell "run uvicorn in a terminal." RTSP/IP camera support is essential (webcam-only limits you to a demo) | 2–3 weeks |
| 4 | **Threshold/validation documentation** (provenance + limitation statements) | Legal exposure. Every report should carry "heuristic thresholds, not clinically validated" until it is | 3–5 days |
| 5 | **Real TLS deployment test** (the nginx.tls.conf path, end-to-end) | README says "optional"; a buyer's IT dept will demand it | 2–3 days |

### Tier 2 — Strongly recommended for a real pilot

| # | Item | Why |
|---|---|---|
| 6 | **Multi-worker dashboard** (supervisor view across N cameras/sessions) | The single-session dashboard doesn't answer "what's happening on line 2 right now" |
| 7 | **Scheduled/automated reports** (nightly risk digest emailed/exported) | Safety managers want zero-touch evidence |
| 8 | **Shift/break modeling** (real shift schedules, rest recovery windows) | Fatigue model assumes continuous monitoring; real shifts have breaks |
| 9 | **IP/RTSP camera support** | Webcam-only is the single biggest demo-to-deployment gap |
| 10 | **Anonymous demographic baseline data** (de-identified, opt-in) | Lets you say "your neck-flexion rates are in the 78th percentile of similar assembly lines" — a huge selling point |

### Tier 3 — Cloud / multi-site (the "make it cloud-based" question — see §6)

| # | Item | Why |
|---|---|---|
| 11 | **Central fleet dashboard** (N plants, M cameras, one safety manager view) | Enterprise buyers require it |
| 12 | **Cloud sync (optional, opt-in)** | Offline-first stays; sync sessions/alerts to a central store when connectivity exists |
| 13 | **SSO / LDAP / Azure AD** | Enterprise IT requirement |
| 14 | **Billing/tenant management** (if SaaS) | Only if you go SaaS route |

### Tier 4 — The "someday" list (don't do yet)

- Wearable integration, face-recognition-based worker ID (privacy risk; do badge/QR instead), ML replacement of the context engine (keep it explainable), mobile apps.

---

## 5. Tech Stack — Should We Change Anything?

### 5.1 The "make it cloud-based" question — my honest recommendation

**Not yet — and here's the reasoning.** Your current stack (SQLite + local files + local Ollama) is a *feature*, not a deficiency:

1. **It's the privacy story.** Factories are terrified of video leaving the premises (unions, GDPR, works-council rules). "Your video never leaves your network" is a *sales weapon*. If you move to cloud-first, you lose the one thing that differentiates you from Soter.
2. **It's the cost story.** No cloud bill = the $500/mo price point is actually viable. Cloud video storage is expensive.
3. **You have no scale problem.** SQLite handles single-site data easily. You don't have a database problem; you have a *deployment* problem.

**The right architecture is hybrid, and only when customers demand it:**
- **Edge/on-prem stays the default** (the current stack — it's fine).
- **Optional cloud sync** (postgres or the same SQLite files synced, or a thin central API) — sessions, alerts, reports sync up; raw video stays on-prem by default. Opt-in per site.
- **Central fleet view** can be a *thin* cloud layer that aggregates synced session JSONs — you don't need to rewrite the core.

**Concrete stack recommendations when you do go multi-site:**

| Layer | Today | Recommendation when scaling |
|---|---|---|
| Database | SQLite (local_auth.db, job store) | Keep SQLite at edge. Central: **PostgreSQL** (managed, familiar, relational — sessions/workers/alerts map perfectly). NOT MongoDB — you don't need it |
| File storage | Local filesystem | Edge: local disk. Central: **S3-compatible** (MinIO on-prem or AWS S3), never raw video by default |
| Auth | Local JWT | Keep local JWT at edge; add **OIDC/SSO** (Keycloak or Azure AD) at central for enterprise |
| LLM | Local Ollama | Keep local at edge (privacy). Central: your choice of hosted model for fleet-level analytics only, never raw video |
| Deployment | Docker Compose | **Kubernetes only when you have >1 paying customer and a reason.** Until then, docker-compose + systemd is correct and cheaper |
| Frontend | React SPA + Vite | Fine. Keep it. Add PWA/service-worker later for kiosk mode |

**The one stack change I *would* make before a pilot:** add **RTSP/IP camera support** (OpenCV handles it, ~2 days of work) and package the backend as a **Windows service** (your pilot customer will run Windows). These are worth more than any database change.

### 5.2 What NOT to change (resist these temptations)

- ❌ Don't rewrite the two-backend split (`backend/` + `backend_api/`). It's a legitimate architecture (engines decoupled from HTTP) and works. Merging is churn with zero user value.
- ❌ Don't swap SQLite for a "real database" pre-scale. You'll add ops burden and lose the offline story.
- ❌ Don't replace the deterministic context engine with ML. Explainability is your differentiator; ML should be an *additional signal*, never a replacement.
- ❌ Don't migrate to a different frontend framework. React 19 + Vite + Tailwind is mainstream, hiring-friendly, and already built.

---

## 6. The 90-Day Plan (what I recommend building, in order)

### Phase 1 (Weeks 1–2): Pilot-readiness engineering
1. IP/RTSP camera support + Windows service packaging.
2. Multi-person tracking *or* clear per-camera sessions (decide with first pilot: if 1 worker per camera is acceptable, skip multi-person for now).
3. TLS deployment test end-to-end; one-command pilot installer (scripted docker-compose or a .bat/.sh launcher).
4. Threshold-provenance documentation baked into report PDFs.

### Phase 2 (Weeks 3–6): Find a pilot
5. Pick ONE real factory/warehouse (or an EHS consultant) willing to trial the system for free/cheap.
6. Deploy, monitor 1–2 cameras per shift for 2–4 weeks, collect real data.
7. Deliver a real assessment report using the tool. Ask for feedback on: what's useful, what's missing, would they pay.

### Phase 3 (Weeks 7–10): Build from pilot feedback
8. Implement the top 3 things the pilot asked for (predictable: multi-worker dashboard, scheduled reports, IP cameras).
9. Add de-identified baseline analytics (anonymous percentile benchmarking).
10. Get a validation partnership (university ergonomics lab, or a practicing ergonomist) — this is the credibility multiplier.

### Phase 4 (Weeks 11–13): Packaging
11. Pricing page, sales one-pager, case study from the pilot, demo video.
12. Decide: SaaS (central sync) vs. on-prem license vs. assessment-service. Start with on-prem license + assessment service — least infra, fastest revenue.

---

## 7. What I Need From You (to keep building)

- **Access to a real camera + a second camera** for multi-camera/multi-person work (I can build it, but live verification needs hardware).
- **A target pilot customer** (even a friend's workshop) — the product is ready to try; it needs a real floor.
- **A decision on scope**: 1 worker/camera (fastest to pilot) vs. multi-person per camera (bigger engineering, better demo).
- **Your call on the Ollama model** (already moved to qwen2.5:1.5b) and whether you want scheduled report emails (needs an SMTP relay — or do file-drop only).

---

## 8. Bottom Line

1. **You have a genuinely impressive, working, well-engineered MVP** — the pipeline is real, the tests are real, the docs are real. 90% of "AI posture" projects never reach this state.
2. **The market need is real and documented** (WMSD costs, manual-tool gap, premium-competitor price gap).
3. **You cannot sell it as a finished product today** — single-person, unvalidated, no customers.
4. **You CAN sell it as a service this quarter**, and you can **reach product-sale territory in 3–6 months** with: IP cameras + multi-worker view + one real pilot + a validation partnership.
5. **Don't change the stack to cloud-first.** Keep the edge/offline architecture (it's your moat), add opt-in cloud sync only when a buyer demands it.

> **The single most valuable next action is not more code — it's one real factory trial.** The code is ready enough to learn from reality, and reality will tell you exactly what to build next. I can build everything in the 90-day plan; you provide the floor, the camera, and the customer.
