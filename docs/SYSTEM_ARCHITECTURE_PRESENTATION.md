# ErgoVigilance — System Architecture, Wireframe Walkthrough & Customer-Presentation Guide

**Version:** 1.0 · **Date:** 2026-08-15 · **Audience:** Engineering team, founders, and anyone presenting ErgoVigilance to a factory customer.

> This document is grounded in the actual codebase (routes from `ui_posture/src/App.tsx`, nav from `ui_posture/src/components/Sidebar.tsx`, API modules from `backend_api/app/api/router.py`). It describes **what exists today**, how it fits together, and a prioritized plan to make the demo unforgettable for a factory customer.

---

## Table of Contents

1. [Product in One Sentence](#1-product-in-one-sentence)
2. [The Three-Layer Architecture](#2-the-three-layer-architecture)
3. [How the Data Flows (Pipeline)](#3-how-the-data-flows-pipeline)
4. [Roles & Access Control](#4-roles--access-control)
5. [Wireframe-by-Wireframe Walkthrough](#5-wireframe-by-wireframe-walkthrough)
6. [API Surface Summary](#6-api-surface-summary)
7. [The Customer Journey (Who Sees What)](#7-the-customer-journey-who-sees-what)
8. [What Is Already Presentation-Ready](#8-what-is-already-presentation-ready)
9. [What Would Make It Best-in-Class for a Customer Demo (Prioritized)](#9-what-would-make-it-best-in-class-for-a-customer-demo-prioritized)
10. [Demo Script Outline (15 Minutes)](#10-demo-script-outline-15-minutes)
11. [Appendix — Repository Map](#appendix--repository-map)

---

## 1. Product in One Sentence

**ErgoVigilance is an AI-powered industrial ergonomics platform that watches a worker through an ordinary webcam, detects posture and movement in real time (MediaPipe pose estimation), converts the skeleton into biomechanical risk scores, and gives operators live feedback while giving supervisors and safety managers alerts, recommendations, evidence-backed reports, and PDF exports — all through a polished web app.**

```
Camera → Pose Estimation → Feature Extraction → Context Risk Engine
        → Task Recognition → Alert Engine → Recommendations → History/Trends
        → Reports (PDF/CSV/JSON) → Role-based Dashboards
```

---

## 2. The Three-Layer Architecture

The product is deliberately split into three decoupled layers:

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ui_posture/  (React SPA · TypeScript · Vite · port 3000 dev / 8080 prod)│
│                                                                         │
│  Landing page, live monitoring, dashboards, video review, replay,       │
│  analytics, sessions, reports, workers/users admin, alerts,            │
│  AI assistant, multi-camera, deployment, audit, pilot requests          │
│        │  HTTP + WebSocket  (/api, /video, /ws)                         │
│        ▼                                                                │
┌─────────────────────────────────────────────────────────────────────────┐
│  backend_api/  (FastAPI · Python · port 8000)                           │
│                                                                         │
│  API routes (≈72 endpoints), JWT auth, request/response schemas,        │
│  LiveMonitoringService (owns & drives the AI engines), session cache,   │
│  pose overlay renderer, video-analysis job queue, alert persistence     │
│        │  in-process calls                                              │
│        ▼                                                                │
┌─────────────────────────────────────────────────────────────────────────┐
│  backend/  (AI core — no HTTP)                                          │
│                                                                         │
│  PoseEngine (MediaPipe), feature extraction, Context Intelligence       │
│  Engine (risk scoring), RULA/REBA standard assessment, task             │
│  recognition, alert engine, recommendation engine, fatigue & exposure   │
│  models, trend/safety analysis, AI assistant, drift monitor, Kalman     │
│  smoothing, framing-quality intelligence                                │
└─────────────────────────────────────────────────────────────────────────┘
```

> **The mantra:** `backend/` is the product. `backend_api/` is how the product talks to a browser. `ui_posture/` is the browser. The old Streamlit app is legacy tooling, not part of the product.

### Layer responsibilities in detail

| Layer | What lives here | Why it's separated |
|---|---|---|
| **`backend/` (AI core)** | `pose_engine.py` (MediaPipe), `features.py` (12 biomechanical features), `context/engine.py` (Context Intelligence — risk scoring, task modifiers, fatigue, exposure, level dwell), `standard_assessment.py` (RULA/REBA), `task_recognition.py` (HistGradientBoosting classifier + Gaussian fallback), `issue_detection.py`, `recommendation_engine.py`, `trend_analysis.py`, `safety_report.py`, `report_pdf.py` (Playwright PDF), `framing_quality.py`, `kalman.py`, `drift_monitor.py` | No HTTP, no persistence — pure computation. Testable in isolation, swappable, and shareable between the API server and CLI tools (`scripts/label_frames.py`). |
| **`backend_api/` (API + services)** | FastAPI app, `app/api/*.py` (33 route modules), `app/services/live_monitor.py` (owns the camera capture thread + processing thread + WS state), `app/services/session_cache.py` (TTL cache over session files), `pose_overlay.py` (skeleton drawing), `retention.py` (data retention policy), job queue for video analysis | The single integration point the browser talks to. Persistence (SQLite/Postgres/JSON) and auth live here. |
| **`ui_posture/` (SPA)** | React + TypeScript + Vite, 18 pages, ~30 shared components, role-gated sidebar, `apiClient`/`DashboardRepository` pattern | Thick client with optimistic state, WebSocket live feed, canvas skeleton overlays. |

---

## 3. How the Data Flows (Pipeline)

### 3.1 Live monitoring path (the heart of the product)

```
USB/IP Webcam ──► capture thread (bounded queue, maxlen=8, latest-wins)
                     │
                     ▼
              PoseEngine.process_frame(frame)        [backend/services/pose_engine.py]
              • MediaPipe Pose Landmarker (VIDEO mode, up to 4 people, primary = largest bbox)
              • 33 normalized landmarks → pixel keypoints
              • Kalman smoother (removes per-joint jitter at the source)
              • 12 features: neck/trunk flexion, shoulder elevation/symmetry,
                alignment, knee angle, forward head, head tilt, wrist deviation,
                stance stability, weight shift
              • Task recognition (Assembly Work / Reaching / Lifting / Inspection / ...)
              • RULA/REBA standard-method assessment (authoritative risk gate)
              • Framing-quality intelligence (profile view / cropped body / occlusion)
                     │
                     ▼
              ContextIntelligenceEngine.evaluate()    [backend/context/engine.py]
              • Task-conditional thresholds
              • Uncertainty-aware scoring (P(rule violated) via per-joint sigma)
              • Exposure duration penalty + fatigue modifier
              • Risk level = LOW / MEDIUM / HIGH with level-dwell hysteresis
              • Active-rule explainability + optional Ollama AI explanation
                     │
                     ▼
              LiveMonitoringService  [backend_api/app/services/live_monitor.py]
              • Risk snapshot → WebSocket payload (NaN-safe)
              • Alert engine (thresholds, persistence to SQLite)
              • Recommendations (task/posture-specific, 30s cooldown)
              • Timeline buffer (capped 20,000), recording (MP4 at 15 fps)
              • MJPEG video feed with live skeleton overlay
                     │
                     ▼
              Browser: Live Monitoring screen
              • MJPEG camera panel + canvas overlay
              • Risk gauge, telemetry sidebar, live timeline, alert center
```

### 3.2 Offline / recorded path

```
Recorded session (original.mp4 + timeline.json)
   │
   ├─► Replay page (/replay/:sessionId) — scrubs the recorded timeline
   │
   ├─► Video Review (/video-review)
   │     │  upload MP4 or pick a recording
   │     ▼
   │     POST /api/video/analyze  → background job (VIDJOB-*)
   │     • processes EVERY frame (force_process, temporal tracking warm)
   │     • stores one analysis record per frame_step (default 10)
   │     • burns an overlay MP4 (sample retention → zero flicker)
   │     ▼
   │     GET /api/video/analyze/{job_id} → poll → result.frames[]
   │     Browser draws interpolated skeleton on a canvas over the video
   │
   └─► Reports (/reports) — risk-trend, safety-report, session PDF exports
```

### 3.3 Persistence

| Store | What | Notes |
|---|---|---|
| `outputs/sessions/*.json` | One JSON per session (summary, risk percentages, alerts) | File-mode; TTL cache in `session_cache.py` |
| `outputs/recordings/{worker}/{timestamp}/` | `original.mp4`, `overlay.mp4`, `timeline.json`, `summary.json` | FPS-capped (15) to bound encode cost |
| SQLite (`local_auth.db`) | Users, roles, alert history, audit log, video-analysis jobs | Seed user: `admin@example.local / AdminPass123!` |
| Postgres (optional, `DATABASE_URL`) | Tier-1 telemetry store | Falls back to JSON-file mode when unset |
| `models/` | `pose_landmarker_lite.task`, `task_model_v2.pkl`, risk forecasters | Guarded by `MANIFEST.json` |

---

## 4. Roles & Access Control

Four roles gate the UI (sidebar items filter by role) and the API (`require_roles`).

| Role | Purpose | Can see | Cannot see |
|---|---|---|---|
| **operator** | The worker on the floor | Dashboard, Live Monitoring, Video Review, Analytics, Reports, Sessions, Settings | Workers, Multi-Camera, Manager, Deployment, Audit, Users, Pilot Requests |
| **supervisor** | Line supervisor | Everything operator sees **plus** Workers, Multi-Camera | Manager, Deployment, Audit, Users, Pilot Requests |
| **safety_mgr** | EHS manager | Everything above **plus** Manager dashboard, Audit Trail | Deployment, Users, Pilot Requests |
| **admin** | Deployer/operator of the system | Everything | — |

---

## 5. Wireframe-by-Wireframe Walkthrough

All routes come from `ui_posture/src/App.tsx`. Nav groups come from `Sidebar.tsx` (Monitoring / Data / Admin).

### 5.0 Public pages (no auth)

#### `/` — Landing Page (`LandingPage.tsx`)
The customer-facing pitch. Industrial backdrop, hero ("musculoskeletal injury is **preventable**"), live-looking skeleton readout, "Is this you?" pain-point section, a builder's note ("why the pilots are free"), a 4-step "How the Risk Assessment Works", a live feature readout card, and a CTA to **request a free pilot**.

- **Wireframe:** full-bleed hero → pain points → how-it-works steps → feature readout → pilot CTA. Dark industrial theme, animated skeleton accent.
- **Key components:** `IndustrialBackdrop`, hero skeleton graphic, stat cards.

#### `/request-pilot` — Pilot Request (`RequestPilot.tsx`)
A lead-capture form (factory name, contact, shift info). Feeds the **Pilot Requests** admin queue.

#### `/login` + `/forgot-password`
JWT login with seeded credentials; password reset flow.

### 5.1 Monitoring group

#### `/dashboard` — Executive Dashboard (`DashboardPage.tsx`)
The post-login home. A one-screen health summary of the whole plant.

- **Wireframe:** KPI cards across the top (active workers, current risk, alerts today, health score), a live snapshot card, and shared components below.
- **Key components:** `ExecutiveDashboardCard`, `HealthScore`, `SystemPerformanceCard`, `ShiftSummary`, `AIInsights`, `PredictiveInsightsCard`, `ModelDiagnosticsCard`.
- **Data:** `/api/dashboard/*`, `/api/manager`, `/api/predictions`, `/api/alerts`.

#### `/monitoring` — Live Monitoring (`LiveMonitoring.tsx`) ⭐ THE demo screen
The operator screen. Real-time camera feed with a skeleton overlay, live risk gauge, telemetry, and controls.

- **Wireframe (left→right):**
  - **Camera panel** (MJPEG feed + skeleton overlay, framing-quality badge, "Reconnecting…" state)
  - **Risk gauge** (LOW/MEDIUM/HIGH needle) + live risk level with dwell smoothing
  - **Telemetry sidebar** — per-feature readouts (neck flexion, trunk flexion, …), task + confidence, lower-body confidence
  - **Controls** — Start/Stop session, worker selector, alert threshold, log/override buttons
  - **Below the fold** — live timeline, alert center, AI assistant panel, digital twin visualization
- **Key components:** `MonitoringControls`, `CameraPanel`, `DigitalTwin`, `AlertCenter`, `LiveAlerts`, `LiveTimeline`, `ContextAwareRiskCard`, `RecommendationsCard`, `AIAssistantPanel`, `AlertToast`.
- **Data:** MJPEG `/video/feed`, WebSocket `/ws/live`, `/api/context`, `/api/recommendations`, `/api/session/*`.

#### `/video-review` — Video Review (`VideoReviewPage.tsx`)
Upload any MP4 (or re-analyze a recorded session) and get the full ML pipeline output.

- **Wireframe:** upload dropzone + "Review a Recorded Session" panel (calendar, filters) on the left; on the right a calendar, then the result: video player with **canvas skeleton overlay** (interpolated for smoothness), current-frame feature panel, interactive **Risk Over Time** SVG chart, risk distribution bars, feature averages, frame-sample table (jump-to-frame), and **Download with Overlay** (burned MP4) + Download Data (JSON).
- **Key components:** `SessionCalendar`, canvas `drawSkeleton`, `RiskBar`, risk path chart.
- **This screen is the single most persuasive artifact in the demo** — it turns "trust me, the AI works" into "watch the skeleton track this person frame-by-frame."

### 5.2 Data group

#### `/analytics` — Analytics (`AnalyticsPage.tsx`)
Cross-session aggregations: risk distributions over time, feature averages, session analytics, trend breakdowns.

#### `/reports` — Reports (`ReportsPage.tsx`)
Risk-trend report, safety report, session report, worker trends — with **PDF export** (Playwright-rendered), CSV export, and JSON. `/trends` redirects here (`view=risk-trend`).

#### `/sessions` — Sessions / History (`SessionHistory.tsx`)
Paginated session list with a **calendar heatmap** (`SessionCalendar`), filters (worker, risk, date, load level), session detail, and jump-to-replay.

#### `/workers` — Workers (`WorkersPage.tsx`)
Worker profiles — per-worker risk history, exposure, and `WorkerProfile` cards. Supervisor+ only.

#### `/cameras` — Multi-Camera (`MultiCameraView.tsx`)
Grid of live camera feeds (one `LiveMonitoringService` per backend today; multi-camera session isolation is roadmap Tier 3). Supervisor+ only.

### 5.3 Admin group

#### `/manager` — Manager Dashboard (`ManagerDashboard.tsx`)
Plant-level summary for the safety manager: aggregate risk, open alerts, degraded-mode banner (honest about data source), supervisor summaries. `safety_mgr`/`admin` only.

#### `/deployment` — Deployment Center (`DeploymentCenter.tsx`)
Admin-only deployment/ops metrics: model status, retention stats, API health.

#### `/audit` — Audit Trail (`AuditTrail.tsx`)
Immutable action log (who did what, when) — valuable for compliance conversations with EHS teams.

#### `/users` — Users (`UsersPage.tsx`)
Create/manage users, assign roles. Admin only.

#### `/pilot-requests` — Pilot Requests (`PilotRequestsPage.tsx`)
Admin queue of incoming pilot leads from the landing page. Admin only.

#### `/settings` — Settings (`SettingsPage.tsx`)
Thresholds (calibration profiles), retention policy, model diagnostics (`ModelDiagnosticsCard` — honest 76.9% accuracy), worker/task config.

### 5.4 Shared UI infrastructure

| Component | Where it's used | Purpose |
|---|---|---|
| `Layout` + `Sidebar` | Every authed page | Role-filtered nav, collapsible |
| `SearchModal` | Global (mounted in `App.tsx`) | Cmd-K style search across sessions/workers |
| `ErrorBoundary` | Global | Catches React tree crashes instead of blank screens |
| `AlertToast` / `NotificationCenter` | Global | Real-time alert surfacing |
| `ExportsCenter` | Reports | One-click PDF/CSV/JSON |
| `IndustrialBackdrop` | Landing + auth | Consistent industrial visual identity |
| `EmptyState` / `LoadingCard` / `ErrorCard` | Everywhere | Honest loading/empty/error states |

---

## 6. API Surface Summary

~72 endpoint decorators across 33 route modules (`backend_api/app/api/router.py`):

| Tag | Example endpoints |
|---|---|
| Auth | `POST /api/auth/login`, password reset |
| Dashboard | `GET /api/dashboard`, `/api/dashboard/supervisor-summary`, `/api/dashboard/admin-summary` |
| Sessions | `GET /api/sessions` (paginated), session detail |
| Session Lifecycle | `POST /api/session/start`, `/api/session/stop`, timeline, observations |
| Live | `GET /video/feed` (MJPEG), `GET /api/context`, `/api/recommendations`, WS live |
| Alerts | `GET /api/alerts`, `PATCH /api/alerts/{id}/resolve`, acknowledge |
| Reports | `GET /api/reports`, `/api/reports/risk-trend`, `/api/reports/safety-report`, session PDF, worker-trends PDF |
| Video Analysis | `POST /api/video/analyze`, `/api/video/analyze/recording/{id}`, `GET /api/video/analyze/{job}`, `.../{job}/download` |
| Recordings | `GET /api/recordings`, per-session video/timeline/summary |
| Cameras | `GET /api/cameras`, `POST /api/cameras/detect` |
| Workers/Users | CRUD + role assignment |
| Admin | Deployment, retention config, audit, privacy, pilot requests, task config, predictions |

**Auth:** JWT bearer tokens, role-checked dependencies (`require_roles`), bcrypt hashing offloaded to a threadpool (no event-loop blocking).

---

## 7. The Customer Journey (Who Sees What)

| Persona | First screen | What wins them |
|---|---|---|
| **Plant Manager** (decision maker) | Landing → Dashboard | "How many of my people are at risk right now?" at a glance. Pilot-request CTA. |
| **EHS / Safety Manager** (champion) | Landing → Dashboard → Manager → Reports | Alerts, audit trail, evidence-backed PDFs, honest model diagnostics. "This replaces our paper logs and gives us a compliance paper trail." |
| **Supervisor** | Dashboard → Live Monitoring → Workers | Real-time per-worker risk, workers list, multi-camera. "I can see the line without walking it." |
| **Operator** (the person on camera) | Live Monitoring | Immediate feedback loop: "Watch your back" in real time. Big touch targets, plain-language risk. |
| **IT / Ops** (technical gate) | Deployment → Settings | Runs standalone on a laptop, no cloud, no IT integration, Docker deployable, data stays on-premise. |

---

## 8. What Is Already Presentation-Ready

Verified by the QA pass (2026-08-13/15) — all real, none aspirational:

- ✅ **233 backend tests pass** (1 skipped) · frontend `tsc --noEmit` clean · production `vite build` succeeds
- ✅ **Live overlay** — real MediaPipe skeleton on the MJPEG feed, per-region risk coloring, framing-quality badge
- ✅ **Video Review** — real pipeline output, smooth interpolated skeleton, interactive risk chart, burned-overlay MP4 download (verified 200 OK end-to-end)
- ✅ **PDF exports** — safety report (61 KB), session report (132 KB locally / 99 KB in Docker), all valid `%PDF-`
- ✅ **Login works** in the Docker container with seed credentials; data persists across down/up cycles
- ✅ **Alert lifecycle** — persist, resolve, acknowledge; 404/503 hardening verified
- ✅ **Honest metrics** — Settings shows the real 76.9% model accuracy; the circular 97.97% figure is gone from user-facing surfaces
- ✅ **Ground-truth labeling pipeline** exists (`scripts/label_frames.py` + `apply_human_labels.py`) — the honest-accuracy path is built and waiting for human labels
- ✅ **Robustness** — corrupt session files don't 500 reports, NaN-safe WS payloads, RTSP camera reconnect with backoff, bounded memory in the live pipeline
- ✅ **A real customer-facing landing page** with a free-pilot CTA feeding an admin queue

---

## 9. What Would Make It Best-in-Class for a Customer Demo (Prioritized)

### 🔴 P0 — Do before any customer meeting

| # | Improvement | Why it matters for the sale | Effort |
|---|---|---|---|
| 1 | **One-click demo mode** — a `DEMO_MODE=1` env flag that: seeds 3 realistic workers + 30 days of varied session data, plays a looped sample video through the live pipeline, and pre-fills every chart. | Right now the dashboard shows *whatever data exists locally*; a customer meeting with an empty dashboard kills the demo before it starts. Demo mode makes the product look alive every single time. | Medium |
| 2 | **Product-name + logo polish on the landing/auth pages** and a favicon/OG meta set. | First impressions. The favicon is currently a placeholder asset. | Low |
| 3 | **The 48-frame human labeling session** (already built, human-gated) → publish the first honest accuracy number. | "76.9% on what?" — being able to say "76.9% measured against 48 human-labeled frames from a real session" turns a vulnerability into a differentiator. | Human time (20–40 min) |
| 4 | **A "pilot agreement" one-pager + privacy/consent sheet** (worker consent already drafted in `docs/pilot/WORKER_CONSENT_ONEPAGER.md` — finish the agreement). | Factory customers require consent paperwork. Having it printed removes the #1 stall objection. | Low |
| 5 | **Stabilize a single reference laptop build** (run_live_demo.bat) and rehearse it offline. | Demos fail on hotel Wi-Fi. A fully offline laptop build is the difference between "wow" and "sorry, the internet". | Medium |

### 🟠 P1 — Strong differentiation in the demo

| # | Improvement | Why | Effort |
|---|---|---|---|
| 6 | **Plain-language operator layer** — replace "RULA/REBA 4" with "Posture: OK / Watch your back / STOP", big 44px+ touch targets (audit already flagged 9–11px text). | The operator persona test flagged this; it also demos better — a non-technical plant manager instantly understands it. | Medium |
| 7 | **Side-by-side injury-prevention case study card** — a static visual: "Same worker, same task: before (paper logs, injury after 6 months) vs. after (alert at minute 12, posture corrected)". | Customers buy outcomes, not features. One compelling story card beats ten charts. | Low |
| 8 | **Cost-savings calculator on the landing page** — 3 inputs (workers, shifts, avg injury cost) → estimated annual savings. | Instant ROI math in the room is the strongest close in industrial sales. | Medium |
| 9 | **Multi-person / multi-camera foundation surfaced honestly** — the engine already detects up to 4 people and reports `person_count`; add a "2 workers in view" badge on the camera panel. | Shows the tech ceiling without overclaiming (per-worker isolation is still roadmap). | Low |
| 10 | **Export the demo artifacts** — pre-generate the safety-report PDF, a video-review overlay MP4, and a trend chart PNG so the meeting has physical takeaways to leave behind. | Printed PDFs left on the desk get read on Monday. | Low |

### 🟡 P2 — Deeper product bets (post-pilot feedback)

| # | Improvement | Why |
|---|---|---|
| 11 | **Per-worker session isolation + analytics** (roadmap Tier 3) | The biggest honest gap vs. "fleet" claims. |
| 12 | **Crash recovery** — resume a session in progress after power loss (raw MP4 is already written continuously; wire a resume path). | Factory power dips are guaranteed; the edge-case matrix flags it. |
| 13 | **NTP/clock handling + timezone-safe reports** | 12-hour shifts and midnight rollovers currently rely on local time string sorts. |
| 14 | **Real lighting-condition calibration** | Profile view / glare are the top false-positive sources on a floor. |
| 15 | **Fleet API** (multi-site) | The natural enterprise upsell once one plant says yes. |

---

## 10. Demo Script Outline (15 Minutes)

1. **0:00–2:00 — The problem (don't show software yet).** "Musculoskeletal injuries are the #1 source of lost-time injuries in manufacturing, and paper posture logs are filled out once a shift and never read."
2. **2:00–4:00 — The landing page.** Walk the pain points and the "How it works" 4 steps. Say the pilot pitch: *free, no IT setup, we install and remove it ourselves.*
3. **4:00–7:00 — Live monitoring.** Start the demo-mode camera, point at yourself or the sample video: "Watch the skeleton. Now I'm going to slouch… watch the gauge go MEDIUM→HIGH and the alert fire." ⭐
4. **7:00–9:00 — Video Review.** Analyze a recording live: "This is a real session from [date]. Every frame was processed — the skeleton tracks the person frame by frame. Here's the risk over time; here's the exact second the posture broke."
5. **9:00–11:00 — The report.** Open the safety report, export the PDF: "This is evidence you can hand to an insurer or an auditor."
6. **11:00–13:00 — Manager + audit trail.** "As safety manager you see the whole plant; every alert is logged and attributable."
7. **13:00–15:00 — Close.** "Two weeks, zero cost, we handle everything. If you don't see value, we remove it. Can we start next Monday?" → hand over the one-pager + printed PDF.

---

## Appendix — Repository Map

```
posture_analysis/
├── backend/                     AI core (no HTTP)
│   ├── context/                 Context Intelligence Engine, exposure, fatigue
│   ├── core/                    constants, types, utils
│   └── services/                pose_engine, features, task_recognition,
│                                standard_assessment, issue_detection,
│                                recommendation_engine, trend/safety analysis,
│                                report_pdf, framing_quality, kalman, drift_monitor
├── backend_api/                 FastAPI server (port 8000)
│   ├── app/
│   │   ├── api/                 33 route modules (≈72 endpoints)
│   │   ├── core/                auth, config, database, postgres
│   │   ├── repositories/        live, session cache
│   │   ├── schemas/             pydantic request/response models
│   │   └── services/            live_monitor, pose_overlay, retention,
│   │                            session_cache, manager_metrics, worker_trends
│   └── tests/                   233 tests
├── ui_posture/                  React SPA (port 3000 / 8080)
│   ├── src/
│   │   ├── pages/               18 pages
│   │   ├── components/          layout, cards, charts, common (~30 shared)
│   │   ├── services/            apiClient, dashboardService, repositories
│   │   ├── auth/                AuthContext (JWT)
│   │   └── types/               TS API contracts
│   └── public/                  static assets
├── models/                      pose_landmarker_lite.task, task_model_v2.pkl, MANIFEST.json
├── outputs/                     sessions/, recordings/, video_review/ (runtime data)
├── scripts/                     label_frames, apply_human_labels, live_demo,
│                                training/eval scripts
├── docs/                        vision/roadmap, QA findings, pilot kit, guides
├── docker-compose.yml           db + backend + frontend (nginx)
└── docker-compose.verify.yml    standalone verification stack (free ports 5433/8001/8080)
```

---

*Questions this document answers with evidence: routes, roles, endpoints, pipeline stages, persistence, and a prioritized plan to present ErgoVigilance to a factory customer. Generated from the live codebase 2026-08-15.*
