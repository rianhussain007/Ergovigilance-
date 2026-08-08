# ErgoVigilance — AI Ergonomic Posture & Movement Monitoring

[![CI](https://github.com/rianhussain007/Ergovigilance-/actions/workflows/ci.yml/badge.svg)](https://github.com/rianhussain007/Ergovigilance-/actions/workflows/ci.yml)

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
| `models/` | `pose_landmarker_lite.task` (MediaPipe pose model — the runtime model), `best_model.pkl` (archived classifier), `svm_model.pkl` (training-only), plus `MANIFEST.json` with SHA-256 checksums (verified in CI) |
| `knowledge/` | Markdown corpus for the AI Assistant (RULA/REBA reference, thresholds, FAQ, alert rules) |
| `docs/` | `CURRENT_STATE.md` (authoritative — what is built & verified), `PRIVACY.md` (data handling & deletion), `VISION_AND_ROADMAP.md`, module HLDs & reports |
| `scripts/` | Training, evaluation, test scripts, and `verify_models.py` (model governance) |
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
pip install -r requirements-dev.txt      # production deps + pytest/pip-audit
# PDF export needs the Playwright browser (one-time):
playwright install chromium
```

Start the API:

```bash
cd backend_api
python -m uvicorn app.main:app --reload --port 8000
```

On startup the backend:
1. Applies **versioned schema migrations** (`backend_api/app/core/migrations/*.sql`, tracked via SQLite `PRAGMA user_version`) and **seeds the four role accounts and two demo workers** (see [Authentication](#authentication--seed-credentials)).
2. Writes `backend_api/SEED_CREDENTIALS.local.txt` (gitignored) with those credentials on first run.
3. Initializes the live monitoring service (if `models/pose_landmarker_lite.task` exists) and starts the retention loop. The AI corpus and Ollama probe run in the background, and the Playwright browser is launched **lazily on first PDF export** — startup never blocks on optional components.

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
| `AUTH_JWT_SECRET` | dev default | **Required when `DEBUG=false`** — the server refuses to start without a strong secret (and rejects the known dev default). Generate: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `AUTH_JWT_TTL_SECONDS` | `28800` (8 h) | JWT expiry |
| `TRUST_PROXY_HEADERS` | `false` | Set `true` only behind a trusted proxy (e.g. the nginx frontend) so `X-Forwarded-For` is honored for rate limiting; otherwise the socket IP is used to prevent header spoofing |
| `LOG_LEVEL` | `INFO` | Logging level |
| `POSE_MODEL_PATH` | `models/pose_landmarker_lite.task` | MediaPipe pose model — set to `pose_landmarker_full.task` for cluttered industrial scenes (≈2-4× slower inference, better occlusion/scale robustness); lite is ~15-20 FPS on CPU and is the default for webcam real-time monitoring |
| `SESSIONS_DIR` | `outputs/sessions` | Where recorded session summaries are stored |
| `SESSION_RETENTION_DAYS` | `30` | Delete session summaries older than this many days (`0` disables) |
| `RECORDING_RETENTION_DAYS` | `30` | Delete recording session dirs older than this many days (`0` disables) |
| `RECORDINGS_MAX_GB` | `20` | Hard cap on the recordings tree; oldest sessions evicted first when exceeded (`0` disables) |
| `RETENTION_INTERVAL_HOURS` | `6` | How often the background retention pass runs |
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

- Log in via `POST /api/auth/login` → returns a JWT bearer token (8-hour TTL, configurable via `AUTH_JWT_TTL_SECONDS`) with `expires_in`/`expires_at`. The frontend drops expired tokens immediately on reload instead of waiting for a 401.
- Send it as `Authorization: Bearer <token>` on all subsequent requests.
- Permissions (operator / supervisor / safety_mgr / admin) are enforced server-side; unauthorized calls return 403.
- Passwords are bcrypt-hashed; the plaintext list is written only to `backend_api/SEED_CREDENTIALS.local.txt`, which is **gitignored — never commit it**.
- **Brute-force protection is built in**: 5 failed attempts per account or 10 per IP within 15 minutes locks that account/IP for 15 minutes (HTTP 429 with `Retry-After`). Trade-off: anyone can deliberately lock a known email for 15 minutes — monitor `login_locked` audit events and consider CAPTCHA in high-risk deployments.
- Set `AUTH_JWT_SECRET` to a strong value in any deployment that isn't a local demo — the server **refuses to start** without it when `DEBUG=false`.
- In live mode (`USE_MOCK_REPOSITORY=false`) the API **fails closed**: if the monitoring service is unavailable, requests return HTTP 503 rather than silently serving mock data.

---

## API overview

Interactive docs: **http://localhost:8000/docs** (Swagger) / `/redoc`.

| Area | Example endpoints |
|---|---|
| Auth | `POST /api/auth/login`, users, settings |
| Operations | `GET /healthz` (liveness), `GET /readyz` (readiness), `GET /metrics` (Prometheus), `GET /health` — root-level, no auth |
| Live monitoring | `GET /api/dashboard`, `POST /api/session/start` / `end`, `GET /api/session/latest`, `/video/feed` (MJPEG) |
| Context intelligence | `GET /api/context/snapshot`, recommendations |
| Alerts | `GET /api/alerts` (active + history), acknowledge/resolve |
| Sessions & history | `GET /api/sessions`, session reports, risk trends |
| Video | `POST /api/video/analyze` (≤200 MB upload), recordings, replay |
| Workers / tasks | `GET/POST/PUT/DELETE /api/workers`, task config |
| Reports | risk trend, safety report, session report (PDF/CSV/JSON) |
| Analytics | session analytics, worker trends, live timeline, audit log |
| Retention (admin) | `GET /api/retention/stats`, `POST /api/retention/run` — storage usage + manual retention pass |
| Privacy (admin) | `POST /api/privacy/delete-worker-data/{worker_id}` — per-worker right-to-erasure (recordings + alerts) |
| WebSockets | `/ws/dashboard`, `/ws/alerts`, `/ws/camera` |

---

## Optional components

- **AI Assistant** — RAG over the `knowledge/` corpus using a local **Ollama** instance. The API auto-starts Ollama if it's installed at the default location. Without Ollama the assistant endpoint is unavailable (the rest of the system is unaffected).
- **PDF export** — requires `playwright install chromium` (backend venv). Export failures are non-fatal and degrade gracefully.

---

## Security, TLS & privacy

- **TLS**: the Docker stack serves plain HTTP on :8080 (frontend) with the API on loopback only. For production, terminate TLS at the nginx proxy — see `ui_posture/nginx.tls.conf.example` (mount certs + config, map :443). The base `nginx.conf` sets `client_max_body_size 200m` (the 1 MB default would reject the API's 200 MB video uploads), security headers, and proxy timeouts.
- **Network**: the backend port binds to `127.0.0.1` in docker-compose; nginx reaches it over the internal Docker network. Never publish :8000 publicly.
- **Model governance**: `models/MANIFEST.json` records SHA-256 + provenance for every artifact; `python scripts/verify_models.py` verifies them (also runs in CI), so a corrupted or unapproved model swap fails the build. Replace a model → update the manifest in the same commit.
- **Privacy**: see `docs/PRIVACY.md` — offline-first (no cloud uploads; the AI Assistant uses a local Ollama), age + disk-cap retention, admin-only per-worker data deletion, and operational recommendations (notice/consent, DPIA) for workplace rollout.

---

## Data retention

A background task (every `RETENTION_INTERVAL_HOURS`, plus on startup) enforces the retention policy:

- **Session summaries** — `outputs/sessions/session_*.json` older than `SESSION_RETENTION_DAYS` are deleted.
- **Recordings** — `recordings/<worker>/<session>` dirs older than `RECORDING_RETENTION_DAYS` are deleted.
- **Disk guardrail** — if the recordings tree exceeds `RECORDINGS_MAX_GB`, the oldest sessions are evicted until it fits.

Admins can inspect current usage and trigger a pass on demand via `GET /api/retention/stats` and `POST /api/retention/run`. Set any knob to `0` to disable that check. The UI's per-user "Data Retention" selector is a client preference; the server policy is the one that actually enforces cleanup.

---

## Testing & CI

The pytest suite in `backend_api/tests/` is the primary suite (live monitor, retention, migrations, privacy, and an API smoke layer that regression-tests auth, lockout, and the fail-closed 503 path). It is fully isolated — tests run against a temp SQLite DB and temp retention dirs, never your real data:

```bash
cd backend_api && pytest          # 36 tests, ~35 s
pytest -m hardware                # opt-in hardware tests (real cameras, 30 s FPS benchmark)
```

Hardware-gated tests (physical cameras / pose model) are marked `hardware` and excluded by default. The engine-level scripts in `scripts/test_*.py` (context, alerts, history, recommendations, trend/safety/persistence, sprint integrations, …) run standalone with `python scripts/test_<name>.py` — the full 22-script suite runs in CI. `test_ai_assistant_live.py` is a browser E2E test that skips itself (exit 0) when the dev stack isn't running.

Frontend validation (in `ui_posture/`): `npm run lint` (TypeScript) and `npm run build` (production bundle).

**GitHub Actions** (`.github/workflows/ci.yml`) runs on every push/PR:

- **Frontend job**: `npm ci` → `npm run lint` → `npm run build` → `npm audit --omit=dev` (fails on known vulnerabilities).
- **Backend job**: install `backend_api/requirements-dev.txt` → `python scripts/verify_models.py` (model checksums) → `pytest backend_api/tests -q` → all 22 legacy `scripts/test_*.py` → `pip-audit -r backend_api/requirements.txt` (fails on known vulnerabilities).

CI is green (first verified run 2026-08-07). See `ROADMAP.md` for the prioritized list of remaining work (CI polish, dev-tooling repairs, hardware-gated validations, P2 product decisions).

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
- Risk thresholds are open-source defaults tuned against a 30,698-pose REBA-labeled dataset (see `reports/risk_calibration_report.md` and `scripts/tune_risk_thresholds.py`): the tuned cutoffs raise the weight-shift/symmetry over-alarm features while keeping **zero REBA-HIGH poses scored LOW** (agreement 34% → 36.9%, κ 0.085 → 0.107, HIGH-rate 80% → 73.5%). They are not clinically validated; the RULA-informed score is a lower-bound estimate (wrist angle/twist, force/load and muscle-use adjustments are defaulted).
- The whole pipeline has so far been validated by one person in one room/camera setup — see `docs/CURRENT_STATE.md` for the full, honest list of gaps and next steps.
- Legacy Streamlit-era artifacts (`frontend/`, `streamlit_app.py`, `packages.txt`, `run_frontend.bat`, `.streamlit/`) were removed in 2026-08 — they imported deleted pre-pivot modules and could no longer run. They remain in git history (`git log --all`) for reference. The old root `requirements.txt` now simply redirects to `backend_api/requirements.txt`.
