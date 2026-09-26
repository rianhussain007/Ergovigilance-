# CURRENT_STATE.md

Snapshot of ErgoVigilance as of **2026-09-01**. Every statement below is backed by
code inspection or runtime evidence.

---

## Architecture (unchanged)

```
┌──────────────────────────────── ui_posture/ (React 19 + Vite 6, port 3000 / 8080)
│  34 pages: live monitoring, role dashboards, session history, replay,
│  video review, workers/users admin, alerts, AI assistant, setup wizard,
│  pilot requests, validation page, landing flow, cloud cameras,
│  cloud onboarding, cloud settings, YOLO demo, ROI analytics,
│  model dashboard, system health, API docs, status page,
│  onboarding, search, billing, pricing, request pilot
│  + i18n (English / Hindi), animated risk gauge, product tour,
│  keyboard shortcuts, PWA manifest, network status indicator
│        │  HTTP / WebSocket  (/api, /video, /ws, /cloud-api)
│        ▼
┌──────────────────────────────── backend_api/ (FastAPI, port 8000)
│  ~92 endpoints, JWT auth (4 roles), versioned SQLite migrations,
│  LiveMonitoringService — owns and drives the AI engines,
│  Stripe billing, search API, settings API, retention policy
│        │  in-process calls
│        ▼
┌──────────────────────────────── backend/ (AI core — no HTTP)
│  PoseEngine (MediaPipe), 7-feature extraction, Context Intelligence,
│  Task Recognition, Alert Engine, Recommendation Engine, History,
│  EventBus, Fatigue & Exposure models, AI Assistant,
│  Worker Identity Engine (SFace + YOLO), Liveness anti-spoof,
│  Camera Setup Wizard, Crash-safe session checkpoints
├──────────────────────────────── yolo_cloud/ (YOLO Cloud Core, port 8100)
│  YOLOv8-pose inference, RTSP stream ingestion, tenant isolation,
│  PostgreSQL storage, API key auth, webhooks, email/Slack alerts,
│  data retention, onboarding wizard, live frame snapshots
```

> **`backend/` is the on-premise AI core. `yolo_cloud/` is the cloud CCTV core.
> `backend_api/` bridges both to the browser.**

---

## What's New Since July 2026

The following features shipped between 2026-07-07 and 2026-08-20 (80+ commits):

### Worker Identity & Liveness
- **YOLO person detection + SFace face recognition** — every person in frame gets a bounding box and a face match against enrolled workers
- **Consent-first identity engine** — three modes per worker: face camera (with signed consent), badge/QR scan, or anonymous. Denied consent removes the worker from face matching at the code level
- **Anti-photo-spoof liveness** — blink + motion detection prevents presenting a photo or screen; 2D-vs-3D planarity check catches moving photos; unverified faces show amber VERIFYING status with skeleton suppressed
- **Employee ID tags** — workers carry visible ID badges in the UI overlay
- **Per-person risk tracking** — every worker at a station gets scored, not just the primary person

### Camera & Setup
- **Camera setup wizard** — guided first-run positioning with live framing, lighting assessment, and face detection checks
- **Camera detection** — `POST /api/cameras/detect` enumerates available cameras

### Demo & Sales
- **Replay demo mode** — replay a recorded session through the live pipeline with no camera needed (sales demos in any environment)
- **Incident evidence package** — one-click zip export with session data, alerts, recommendations, and MP4 for OSHA/insurance review
- **De-identified posture percentile baseline** — benchmark data for sales comparisons

### Operator Experience
- **Plain-language layer** — big posture status display, de-jargon'd titles, post-stop report prompt
- **Nightly risk digest** — automated end-of-shift summary
- **Crash-safe session checkpoints** — periodic saves during live sessions so a crash loses minutes, not hours

### Video Review & Labeling
- **In-browser video analysis** — upload up to 200 MB video, background job queue with progress tracking
- **Skeleton overlay on replay** — pose landmarks rendered over the original video
- **Ground-truth labeling tool** — extract frames, pre-label with risk engine, human confirms/corrects, feeds back into evaluation
- **Risk labeler** — overlay risk text when timeline has no keypoints; store keypoints in future recordings

### Delivery Hardening
- **Versioned SQLite schema migrations** — `PRAGMA user_version` runner
- **Health endpoints** — `/healthz`, `/readyz`, `/metrics` (Prometheus), `/health`
- **Data retention** — age-based session/recording cleanup + 20 GB disk cap
- **Per-worker right-to-erasure** — `POST /api/privacy/delete-worker-data/{id}`
- **Docker compose** — `.env`-driven ports, Playwright for PDF in containers
- **Windows service scripts** — `deploy/install_windows_service.ps1`
- **Validation page** — customer-facing status page (`/validation`)

---

## Endpoints (as of 2026-09-01)

| Area | Key endpoints |
|------|---------------|
| Auth | `POST /api/auth/login`, user CRUD, password reset |
| Operations | `/healthz`, `/readyz`, `/metrics`, `/health` |
| Live monitoring | `GET /api/dashboard`, session start/stop/status, `/video/feed` (MJPEG) |
| Context intelligence | `/api/context/snapshot`, `/api/recommendations` |
| Alerts | `/api/alerts`, acknowledge, resolve, history |
| Sessions & history | `/api/sessions`, session detail, `/api/history` |
| Video | `POST /api/video/analyze` (≤200 MB), recordings, replay, timeline |
| Workers / identity | Full CRUD + identity mode + badge/QR + face enroll/remove |
| Reports | Risk trend, safety report, session report, worker trends (PDF/CSV/JSON) |
| Analytics | Session analytics, live timeline, audit trail |
| AI Assistant | `POST /api/assistant/chat` (Ollama RAG) |
| Benchmark | Posture percentile baseline |
| Pilot | `POST /api/pilot-requests`, pilot intake tracking |
| Retention | Stats + manual trigger (admin only) |
| Privacy | Per-worker data deletion (admin only) |
| Task config | `/api/task-modifiers` |
| Search | `GET /api/search?q=` |
| Billing | `POST /api/billing/checkout`, `/subscription`, `/portal`, `/webhook` |
| Settings | `GET /api/settings`, `/api/settings/retention` |

### Cloud Core (YOLO) Endpoints

| Area | Key endpoints |
|------|---------------|
| Cameras | CRUD for RTSP cameras, live snapshot JPEG |
| Sessions | Start/stop/list cloud monitoring sessions |
| Alerts | List/acknowledge cloud alerts |
| API Keys | Create/list API keys for tenant auth |
| Webhooks | CRUD + test webhook delivery (HMAC-SHA256) |
| Retention | Cleanup old sessions/alerts |
| Storage Stats | Session/alert/camera counts per tenant |
| Inference | `POST /api/inference/detect` for YOLO pose detection |
| Health | `/healthz` with storage mode indicator |

---

## Frontend Pages (34 pages, lazy-loaded)

| Page | Route | Data source |
|------|-------|-------------|
| Landing | `/` | Static marketing / demo entry |
| Login | `/login` | Auth API |
| Live Monitoring | `/live` | Polling (2s) — dashboard, history, alerts, context |
| Session History | `/sessions` | Live polling |
| Video Review | `/video-review` | Upload + background job |
| Replay | `/replay/:id` | Recording playback + skeleton overlay |
| Reports | `/reports` | Risk trend, safety, session, worker PDFs |
| Analytics | `/analytics` | Session analytics + charts |
| Manager Dashboard | `/manager` | Aggregate worker stats |
| Workers | `/workers` | CRUD + identity + consent + badge QR |
| Users | `/users` | Admin user management |
| Settings | `/settings` | Config + retention |
| Deployment | `/deployment` | Infra metrics |
| Multi-Camera | `/cameras` | Camera feed grid |
| Audit Trail | `/audit` | Audit log |
| AI Assistant | `/assistant` | Chat with Ollama RAG |
| Setup Wizard | `/setup` | Camera positioning guide |
| Validation | `/validation` | Customer-facing status page |
| Pilot Requests | `/pilot-requests` | Pilot intake |
| Request Pilot | `/request-pilot` | Public pilot signup |
| Forgot Password | `/forgot-password` | Auth flow |
| Dashboard (Operator) | `/dashboard` | Personal risk gauge + session data |
| Dashboard (Supervisor) | `/dashboard` | Team overview + worker alerts |
| Cloud Cameras | `/cloud-cameras` | RTSP camera management + live thumbnails |
| Cloud Onboarding | `/cloud-onboarding` | 6-step guided camera setup wizard |
| Cloud Settings | `/cloud-settings` | YOLO model config + webhooks + RTSP tester |
| YOLO Demo | `/yolo-demo` | Image upload + live webcam inference |
| ROI Analytics | `/roi-analytics` | Cost savings calculator |
| Model Dashboard | `/model-dashboard` | Training metrics + per-class F1 scores |
| System Health | `/system-health` | Service health, storage, DB connections |
| API Docs | `/api-docs` | OpenAPI explorer |
| Status Page | `/status` | Public uptime status (no auth) |
| Onboarding | `/onboarding` | Getting started checklist |
| My Posture | `/my-posture` | Personal posture history |
| Pricing | `/pricing` | Cloud tier pricing + Stripe checkout |

---

## SaaS Features (Cloud Core)

| Feature | Status | Details |
|---------|--------|---------|
| PostgreSQL storage | ✅ | Sessions, alerts, cameras, API keys persist |
| API key auth | ✅ | `X-API-Key` header validation with dev-mode bypass |
| Multi-tenancy | ✅ | Tenant isolation on all cloud queries |
| Stripe billing | ✅ | Checkout, subscription, portal, webhook events |
| Live camera preview | ✅ | JPEG snapshot endpoint + frontend thumbnails |
| Alert notifications | ✅ | Self-contained email/Slack delivery |
| Webhook system | ✅ | Customer-configurable HTTP delivery with HMAC signing |
| Data retention | ✅ | Configurable cleanup for sessions/alerts |
| Onboarding wizard | ✅ | 6-step guided camera setup |
| Pricing → checkout | ✅ | Stripe integration on Pricing page |
| Hindi language | ✅ | 120+ operator-facing translations |

## Test Baseline

| Suite | Count | What it covers |
|-------|-------|----------------|
| `pytest backend_api/tests` | 55 test files, 425 passed (1 skipped, 1 deselected) | Auth, alerts, settings, privacy, pilot requests, users, retention, migrations, live monitor, API smoke, integration |
| `pytest yolo_cloud/tests` | 6 test files, 134 passed | RTSP ingest, clip moov guard, WebSocket events, identity/badge binds, soak harness, TRL-6 blockers |
| Legacy `scripts/test_*.py` | 22 scripts | Context engine, alerts, history, recommendations, trend/safety reports, persistence, sprint integrations |
| `vitest` (ui_posture) | 9 tests (7 smoke + 2 interaction) | Login → dashboard → sessions → alerts → Settings page → Reports page → backend-down error + empty-form validation + RBAC route guard |
| **Total** | **568 automated tests + 22 scripts** (425 backend + 134 cloud + 9 vitest) | |

CI runs on every push/PR via GitHub Actions (`.github/workflows/ci.yml`):
- **Frontend**: `npm ci` → `npm run lint` (tsc) → `npm run build` → `npm audit`
- **Backend**: `verify_models.py` → `pytest` → all 22 legacy scripts → `pip-audit`

---

## Known Limitations (honest list)

1. **Single-person tracking** — `num_poses=1` default; multi-person reads bounding boxes but only the primary person is scored. Per-worker isolation is the follow-up.
2. **CPU-only inference** — ~15-20 FPS at 640×480 on a laptop CPU (MediaPipe lite). Full model is 2-4× slower.
3. **Heuristic thresholds** — risk bands are tuned against a 30,698-pose REBA dataset but **not clinically validated**. Ground-truth accuracy is **87.6%** (500 human-labeled frames, `results/ground_truth_evaluation.json`).
4. **One room / one camera** — the on-premise pipeline has been validated by one person in one setup. Cloud core (YOLO) enables multi-camera via RTSP.
5. **WebSocket integration** — frontend WebSocket hooks are wired with HTTP polling fallback. Both paths work.
6. **Alert persistence** — alerts are persisted to SQLite (on-premise) or PostgreSQL (cloud core).
7. **Stripe billing** — integration is built but requires live API keys to activate. Works in free-tier mode without keys.
8. **Hindi translation** — 120+ operator-facing strings translated. Admin/supervisor pages still English-only.
9. **YOLO task classifier** — predicts mostly "Seated Work" with zero recall on minority classes. Risk scoring works independently of task label.
8. **Single-backend design** — one `LiveMonitoringService` singleton per process. Multi-camera = multiple backend processes.
