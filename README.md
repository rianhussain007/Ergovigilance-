# ErgoVigilance — AI Ergonomic Posture & Movement Monitoring

ErgoVigilance is an AI-powered industrial ergonomics monitoring platform. It watches workers through a webcam, detects posture and movement in real time using MediaPipe pose estimation, converts the skeleton into biomechanical features, and produces context-aware risk scores, alerts, recommendations, fatigue/exposure tracking, session recording, replay, and evidence-backed reports for operators, supervisors, and safety managers.

```
Camera → Pose Estimation → Feature Extraction → Context Risk Engine
        → Task Recognition → Alert Engine → Recommendations → History/Trends
        → Reports (PDF/CSV/JSON) → Role-based Dashboards
```

---

## Architecture

ErgoVigilance is split into three layers, deliberately decoupled:

```
┌──────────────────────────── ui_posture/ (React SPA, port 3000 / 8080)
│  Live monitoring, role dashboards, session history, replay,
│  video review, workers/users admin, alerts, AI assistant
│        │  HTTP / WebSocket  (/api, /video, /ws)
│        ▼
┌──────────────────────────── backend_api/ (FastAPI, port 8000)
│  API routes, auth (JWT), request/response schemas,
│  LiveMonitoringService — owns and drives the AI engines
│        │  in-process calls
│        ▼
┌──────────────────────────── backend/ (AI core — no HTTP)
│  PoseEngine (MediaPipe), feature extraction, Context Intelligence,
│  Task Recognition, Alert Engine, Recommendation Engine, History,
│  EventBus, Fatigue & Exposure models, AI Assistant
```

> **`backend/` is the product. `backend_api/` is how the product talks to a browser. `ui_posture/` is the browser.**
> The old Streamlit app (`frontend/app.py`) is a legacy internal validation tool, **not** part of the product architecture.

### Repository layout

| Path | What it is |
|---|---|
| `backend/` | AI core — pose engine, 9-feature extraction, context intelligence, alerts, events, history, recommendations, fatigue/exposure, task recognition, AI assistant |
| `backend_api/` | FastAPI service — `app/main.py` entry point, `app/api/*.py` endpoint modules, `app/core/` (config, auth, database), `app/repositories/`, `app/services/live_monitor.py`, WebSockets |
| `ui_posture/` | React 19 + Vite 6 + Tailwind 4 single-page app (17 pages) |
| `models/` | `pose_landmarker_lite.task` (MediaPipe pose model), `best_model.pkl` (Random Forest risk classifier), `svm_model.pkl` |
| `knowledge/` | Markdown corpus for the AI Assistant (RULA/REBA reference, thresholds, FAQ, alert rules) |
| `docs/` | `CURRENT_STATE.md` (authoritative — what is built & verified), `VISION_AND_ROADMAP.md`, module HLDs & reports |
| `scripts/` | Training, evaluation, and test scripts |
| `outputs/`, `recordings/`, `results/` | Runtime data — sessions, recordings, analysis results (gitignored where appropriate) |

### Key design facts

- **Auth is fully local** — SQLite + bcrypt + JWT (HS256). No cloud dependency; login works offline. Roles are enforced server-side (403s), not just hidden in the UI.
- **Every alert references a concrete posture event** (frame, timestamp, risk snapshot) and **every recommendation traces back to the feature/threshold that triggered it** (explainable AI).
- **Offline-first**: runs for a full shift without internet; Ollama (local LLM) powers the AI Assistant.

---

## Prerequisites

- **Python 3.11–3.13** with `pip`
- **Node.js 20+** with `npm`
- **A webcam** for live monitoring (not required for demo/mock mode)
- *(Optional)* **Ollama** installed locally for the AI Assistant
- *(Optional)* **Docker + Docker Compose** for the containerized stack

---

## Quick start with Docker (easiest)

```bash
docker compose up --build
```

| Service | URL |
|---|---|
| Frontend (nginx) | http://localhost:8080 |
| Backend API | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |

The backend runs with `USE_MOCK_REPOSITORY=true` by default (mock data, no camera needed). Set `USE_MOCK_REPOSITORY=false` for the live camera pipeline. The auth DB is persisted in a Docker volume (`ergovigilance-db`).

---

## Local development setup

### 1. Backend (`backend_api/`)

```bash
cd backend_api
python -m venv .venv                     # optional but recommended
pip install -r requirements.txt
# PDF export needs the Playwright browser (one-time):
playwright install chromium
```

Start the API:

```bash
cd backend_api
python -m uvicorn app.main:app --reload --port 8000
```

On startup the backend:
1. Creates the local SQLite database (users, workers, alerts, audit log, settings, pilot requests).
2. **Seeds the four role accounts and two demo workers** (see [Authentication](#authentication--seed-credentials)).
3. Writes `backend_api/SEED_CREDENTIALS.local.txt` (gitignored) with those credentials on first run.
4. Loads the AI Assistant corpus, initializes the live monitoring service (if `models/pose_landmarker_lite.task` exists), and launches Playwright for PDF export — all failures here are non-fatal.

> Convenience script: `python start_backend.py` from the repo root starts the same server detached and writes `backend.pid`.

### 2. Frontend (`ui_posture/`)

```bash
cd ui_posture
npm install
npm run dev          # http://localhost:3000
```

In dev, Vite proxies `/api`, `/video/` and `/ws` to `http://localhost:8000`, so no CORS config is needed. CORS is also configured for `http://localhost:3000`, `http://localhost:5173`, and `http://localhost`.

> Convenience script: `python start_frontend.py` from the repo root starts Vite on port **5173** instead. Either works; the canonical dev script is port 3000.

### 3. Open it

Visit **http://localhost:3000** and log in with one of the seeded accounts below.

---

## Configuration

### Backend environment variables (`backend_api/.env` or shell)

| Variable | Default | Purpose |
|---|---|---|
| `HOST` / `PORT` | `0.0.0.0` / `8000` | Bind address |
| `DEBUG` | `true` | FastAPI debug mode |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:5173,http://localhost` | Comma-separated allowed origins |
| `USE_MOCK_REPOSITORY` | `false` | `true` = serve mock data (no camera), `false` = live pipeline |
| `MOCK_DATA_DIR` | `app/utils/mock_data` | Mock JSON source |
| `AUTH_DB_PATH` | `backend_api/local_auth.db` | SQLite path (Docker: `/data/local_auth.db`) |
| `AUTH_JWT_SECRET` | dev default | **Change in any real deployment** |
| `AUTH_JWT_TTL_SECONDS` | `28800` (8 h) | JWT expiry |
| `LOG_LEVEL` | `INFO` | Logging level |
| `POSE_MODEL_PATH` | `models/pose_landmarker_lite.task` | MediaPipe pose model |
| `SESSIONS_DIR` | `outputs/sessions` | Where recorded sessions are stored |
| `OLLAMA_HOST` | `http://localhost:11434` | Local LLM endpoint for the AI Assistant |

### Frontend environment (`ui_posture/.env`)

| Variable | Purpose |
|---|---|
| `VITE_API_URL` | Optional API base URL override. Defaults to same-origin, which in dev is proxied to `:8000` by Vite |

---

## Authentication & seed credentials

Authentication is **local SQLite + bcrypt + JWT**. On first backend startup the following accounts are created automatically:

| Email | Password | Role |
|---|---|---|
| `operator@example.local` | `OperatorPass123!` | `operator` |
| `supervisor@example.local` | `SupervisorPass123!` | `supervisor` |
| `safety@example.local` | `SafetyPass123!` | `safety_mgr` |
| `admin@example.local` | `AdminPass123!` | `admin` |

Demo workers seeded: `worker-001 / Asha Patel / Assembly / Day` and `worker-002 / Rohan Mehta / Inspection / Evening`.

- Log in via `POST /api/auth/login` → returns a JWT bearer token (8-hour TTL).
- Send it as `Authorization: Bearer <token>` on all subsequent requests.
- Permissions (operator / supervisor / safety_mgr / admin) are enforced server-side; unauthorized calls return 403.
- Passwords are bcrypt-hashed; the plaintext list is written only to `backend_api/SEED_CREDENTIALS.local.txt`, which is **gitignored — never commit it**.
- Set `AUTH_JWT_SECRET` to a strong value in any deployment that isn't a local demo.

---

## API overview

Interactive docs: **http://localhost:8000/docs** (Swagger) / `/redoc`.

| Area | Example endpoints |
|---|---|
| Auth | `POST /api/auth/login`, users, settings |
| Live monitoring | `GET /api/dashboard`, `POST /api/session/start` / `end`, `GET /api/session/latest`, `/video/feed` (MJPEG) |
| Context intelligence | `GET /api/context/snapshot`, recommendations |
| Alerts | `GET /api/alerts` (active + history), acknowledge/resolve |
| Sessions & history | `GET /api/sessions`, session reports, risk trends |
| Video | `POST /api/video/analyze` (≤200 MB upload), recordings, replay |
| Workers / tasks | `GET/POST/PUT/DELETE /api/workers`, task config |
| Reports | risk trend, safety report, session report (PDF/CSV/JSON) |
| Analytics | session analytics, worker trends, live timeline, audit log |
| WebSockets | `/ws/dashboard`, `/ws/alerts`, `/ws/camera` |

---

## Optional components

- **AI Assistant** — RAG over the `knowledge/` corpus using a local **Ollama** instance. The API auto-starts Ollama if it's installed at the default location. Without Ollama the assistant endpoint is unavailable (the rest of the system is unaffected).
- **PDF export** — requires `playwright install chromium` (backend venv). Export failures are non-fatal and degrade gracefully.

---

## Testing

Backend module tests live in `scripts/test_*.py` (engine-level: context, alerts, history, recommendations, task recognition, sessions, safety reporting…) and `backend_api/tests/` (live monitor, multi-camera). With `pytest` installed in the backend venv:

```bash
cd backend_api && pytest tests -q
python scripts/test_context_engine.py
```

---

## Documentation

- `docs/CURRENT_STATE.md` — **authoritative** snapshot of what is built and verified (as of 2026-07), including known issues and limitations
- `docs/VISION_AND_ROADMAP.md` — product vision and phase roadmap
- `docs/HLD_COVERAGE_MAP.md`, module reports — high-level design for the pose, context, alert, safety, analytics, and recommendation modules
- `results/POSE_MODULE_HANDOFF.md` — pose-estimation module handoff ("ready for system integration")
- `pose_estimation_status.md` / `pose_estimation_status_report.md` — engineering status of the pose module
- `ui_posture/README*.md` — frontend architecture, demo mode, and deployment notes

---

## Notes & known limitations

- Single-person tracking only (`num_poses=1`), CPU-only inference (~15–20 FPS at 640×480).
- Risk thresholds are open-source defaults, not clinically validated; the RULA-informed score is a lower-bound estimate (wrist angle/twist, force/load and muscle-use adjustments are defaulted).
- The whole pipeline has so far been validated by one person in one room/camera setup — see `docs/CURRENT_STATE.md` for the full, honest list of gaps and next steps.
