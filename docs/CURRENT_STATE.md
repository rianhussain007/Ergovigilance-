# CURRENT_STATE.md

Snapshot of ErgoVigilance as of **2026-08-20**. Every statement below is backed by
code inspection or runtime evidence.

---

## Architecture (unchanged)

```
┌──────────────────────────────── ui_posture/ (React 19 + Vite 6, port 3000 / 8080)
│  21 pages: live monitoring, role dashboards, session history, replay,
│  video review, workers/users admin, alerts, AI assistant, setup wizard,
│  pilot requests, validation page, landing flow
│        │  HTTP / WebSocket  (/api, /video, /ws)
│        ▼
┌──────────────────────────────── backend_api/ (FastAPI, port 8000)
│  ~70 endpoints, JWT auth (4 roles), versioned SQLite migrations,
│  LiveMonitoringService — owns and drives the AI engines
│        │  in-process calls
│        ▼
┌──────────────────────────────── backend/ (AI core — no HTTP)
│  PoseEngine (MediaPipe), 7-feature extraction, Context Intelligence,
│  Task Recognition, Alert Engine, Recommendation Engine, History,
│  EventBus, Fatigue & Exposure models, AI Assistant,
│  Worker Identity Engine (SFace + YOLO), Liveness anti-spoof,
│  Camera Setup Wizard, Crash-safe session checkpoints
```

> **`backend/` is the product. `backend_api/` is how the product talks to a browser.**

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

## Endpoints (as of 2026-08-20)

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

---

## Frontend Pages (21 pages, lazy-loaded)

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

---

## Test Baseline

| Suite | Count | What it covers |
|-------|-------|----------------|
| `pytest backend_api/tests` | 36 | Auth, live monitor, retention, migrations, privacy, API smoke |
| Legacy `scripts/test_*.py` | 22 scripts | Context engine, alerts, history, recommendations, trend/safety reports, persistence, sprint integrations |
| `vitest` (ui_posture) | 5 smoke tests | Login → dashboard → sessions → alerts → backend-down error |
| **Total** | **63 automated tests + 22 scripts** | |

CI runs on every push/PR via GitHub Actions (`.github/workflows/ci.yml`):
- **Frontend**: `npm ci` → `npm run lint` (tsc) → `npm run build` → `npm audit`
- **Backend**: `verify_models.py` → `pytest` → all 22 legacy scripts → `pip-audit`

---

## Known Limitations (honest list)

1. **Single-person tracking** — `num_poses=1` default; multi-person reads bounding boxes but only the primary person is scored. Per-worker isolation is the follow-up.
2. **CPU-only inference** — ~15-20 FPS at 640×480 on a laptop CPU (MediaPipe lite). Full model is 2-4× slower.
3. **Heuristic thresholds** — risk bands are tuned against a 30,698-pose REBA dataset but **not clinically validated**. The accuracy claim (76.86%) is model-vs-threshold self-consistency, not human ground truth. Ground-truth labeling is in progress.
4. **One room / one camera** — the whole pipeline has been validated by one person in one setup. Multi-site generalizability is unproven.
5. **No WebSocket consumption** — the React frontend uses HTTP polling (1-2 s intervals). WebSocket endpoints exist but are unused.
6. **Static fallback pages** — Multi-Camera, Audit Trail, and some Deployment widgets still show placeholder data.
7. **In-memory alerts** — alerts are lost on backend restart; not persisted across sessions.
8. **Single-backend design** — one `LiveMonitoringService` singleton per process. Multi-camera = multiple backend processes.
