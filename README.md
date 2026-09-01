# ErgoVigilance — AI-Powered Industrial Ergonomics Platform

> Real-time posture risk detection, live monitoring, alerts, and reporting for factory floors — powered by computer vision and biomechanical analysis.

<p align="center">
  <img src="ui_posture/public/images/dashboard-operator.png" alt="ErgoVigilance Dashboard" width="700" />
  <br/>
  <em>Live monitoring dashboard with real-time risk scoring, ergonomic feature analysis, and AI-powered recommendations</em>
</p>

## Screenshots

| Dashboard | Live Monitoring | Reports |
|---|---|---|
| ![Dashboard](ui_posture/public/images/dashboard-operator.png) | ![Live Camera](ui_posture/public/images/live_camera.png) | ![History](ui_posture/public/images/history.png) |

| Multi-Camera | Landing Page | AI Assistant |
|---|---|---|
| ![Command Center](ui_posture/public/images/command-center-monitors.png) | ![Hero](ui_posture/public/images/hero-factory-worker.png) | ![Tablet](ui_posture/public/images/tablet-skeleton-assessment.png) |

## What It Does

ErgoVigilance watches a worker through an ordinary webcam, detects body pose in real time using MediaPipe, converts the skeleton into biomechanical risk scores (RULA/REBA), and gives:

- **Operators** — live posture feedback, plain-language guidance, stretch reminders
- **Supervisors** — worker risk summaries, department heatmaps, trend charts
- **Safety Managers** — alert management, audit trail, PDF safety reports
- **Admins** — system health, user management, camera configuration, deployment monitoring

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | React 19, TypeScript, Vite, Tailwind CSS, Recharts |
| **Backend API** | FastAPI (Python 3.11+), Pydantic, SQLite/PostgreSQL |
| **AI Core (On-Premise)** | MediaPipe Pose (33 keypoints), YOLOv8 (person detection), YuNet (face), SFace (identity) |
| **AI Core (Cloud)** | YOLOv8-pose (17 keypoints COCO), ByteTrack (worker tracking), RTSP stream ingestion |
| **ML Models** | HistGradientBoosting (task + risk classification, 97.6% accuracy, 7 task classes) |
| **Deployment** | Docker Compose (4 services), Windows Service scripts, `.env`-driven config |

## Quick Start

### Option A: Docker (recommended for demos)

```bash
# Clone and start
git clone https://github.com/rianhussain007/Ergovigilance-.git
cd Ergovigilance-
docker compose up -d --build

# Open
# Frontend: http://localhost:8080
# API docs: http://localhost:8000/docs
# Login: admin@example.local / AdminPass123!
```

### Option B: Local Development

```bash
# Backend
cd backend_api
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload  # API on :8000

# Frontend
cd ui_posture
npm install
npm run dev                    # Vite on :5173
```

### Option C: Demo Mode (no camera needed)

```bash
# Starts with synthetic data pre-loaded — perfect for customer presentations
DEMO_MODE=true docker compose up -d
# Or locally: set DEMO_MODE=true in your .env
```

## Key Features

### Live Monitoring
- Real-time pose estimation at 30 FPS
- 12 biomechanical features (neck, trunk, shoulders, knees, wrists, stance)
- RULA/REBA standard-method risk scoring
- Temporal hysteresis (level dwell) to prevent alert flickering
- Task classification (Assembly, Lifting, Inspection, Reaching, etc.)
- AI-powered plain-language explanations (Ollama integration)

### Worker Identity & Consent
- Badge/QR code identity assignment
- Face recognition for automatic worker identification
- Consent-first architecture — no face matching without explicit consent
- Worker onboarding flow with intake tracker

### Alerts & Recommendations
- Automatic alert firing on sustained risk posture
- Acknowledge/resolve lifecycle with audit trail
- Context-aware recommendations (worker + supervisor guidance)
- Alert toast notifications in the UI

### Reporting & Analytics
- Session history with calendar view
- Risk trend charts (per-worker, per-department)
- Safety report PDF export (Playwright-rendered)
- Session replay with recorded video
- Benchmark percentiles (de-identified)

### Video Review
- Upload and analyze recorded videos
- Frame-by-frame pose analysis with temporal smoothing
- Keypoint interpolation for smooth skeleton overlay
- Risk timeline with region-level breakdown

### Multi-Camera Support
- USB webcam auto-detection (DSHOW backend)
- IP/RTSP camera configuration
- Multi-Camera dashboard view
- Camera setup wizard (framing, lighting, face checks)

### YOLO Cloud Core (SaaS)
- RTSP CCTV stream ingestion via FFmpeg
- YOLOv8-pose inference (17 COCO keypoints)
- ByteTrack worker tracking across frames
- ML-trained risk classifier (94.1% accuracy)
- ML-trained task classifier (97.6% accuracy, 7 classes)
- Real-time WebSocket camera data streaming
- PDF/CSV report generation (daily/weekly)
- Model versioning with export/import/rollback
- Docker GPU support (NVIDIA CUDA)

### Dual-Core Architecture
- **On-Premise Core**: MediaPipe (33 keypoints), USB webcam, gateway PC required
- **Cloud Core**: YOLOv8-pose (17 keypoints), RTSP CCTV, zero on-site hardware
- Same dashboard, same reports, same alerts
- Choose based on factory needs: privacy-first vs. easy installation

### New Pages (31 total)
- YOLO Demo — Upload image → see pose + risk overlay
- Model Dashboard — YOLO vs MediaPipe comparison + versioning
- ROI Analytics — Cost savings, compliance scores, business case
- System Health — Service status, storage, live metrics
- Onboarding — 10-step factory setup checklist
- Cloud Cameras — Camera management with health monitoring
- Cloud Settings — YOLO model config + RTSP connection tester
- Pricing — 3-tier pricing (Starter/Cloud/Enterprise)

### Deployment & Operations
- Docker Compose with `.env`-driven ports (4 services)
- Windows Service scripts (`deploy/`)
- Health probes (`/healthz`, `/readyz`, `/metrics`)
- Data retention policy (session age, recording age, disk cap)
- Crash-safe session recovery from checkpoints
- CSP security headers, rate limiting, non-root Docker

## API Surface

112+ REST endpoints across 40+ modules:

### Backend API (87 endpoints)
| Module | Endpoints | Description |
|---|---|---|
| Auth | login, register, refresh, me | JWT authentication |
| Dashboard | /dashboard, /supervisor-summary, /admin-summary | Role-gated dashboards |
| Sessions | list, detail, stop, delete | Session lifecycle |
| Alerts | list, resolve, acknowledge | Alert management |
| Reports | safety-report, risk-trend, session-report, PDF export | Report generation |
| Video | analyze, status, download, recording-analysis | Video analysis pipeline |
| Workers | CRUD, face samples, identity | Worker management |
| Users | CRUD, invite, roles | User management |
| Cameras | detect, configure | Camera management |
| Settings | GET/PUT | System configuration |
| Deployment | status, metrics | Infrastructure health |
| Assistant | chat, corpus | AI assistant (Ollama) |

### YOLO Cloud Core (25 endpoints)
| Module | Endpoints | Description |
|---|---|---|
| Camera | CRUD, start, stop | RTSP camera management |
| Dashboard | /dashboard, /alerts | Cloud monitoring dashboard |
| Sessions | list, detail | Cloud session management |
| Alerts | list, acknowledge | Cloud alert management |
| Reports | daily, weekly, PDF, CSV | Report generation |
| Models | metrics, compare, versions | Model management |
| Inference | /detect | Real-time pose detection |
| WebSocket | /ws | Live camera data streaming |

Full API docs at `/docs` (Swagger UI) or `/openapi.json`.

## Project Structure

```
posture_analysis/
├── backend/                    # AI core engines (on-premise)
│   ├── context/                #   Context Intelligence Engine
│   ├── services/               #   Pose, features, risk, alerts, tasks
│   └── core/                   #   Constants, types
├── backend_api/                # FastAPI application (on-premise)
│   ├── app/
│   │   ├── api/                #   41 endpoint modules
│   │   ├── core/               #   Auth, config, database, health
│   │   ├── repositories/       #   Data access (Live, Base)
│   │   ├── schemas/            #   Pydantic models (API contracts)
│   │   └── services/           #   Session cache, live monitor, reports
│   └── tests/                  #   59 test files (93+ tests)
├── yolo_cloud/                 # YOLO Cloud Core (SaaS)
│   ├── api.py                  #   25 REST + WebSocket endpoints
│   ├── pose_engine.py          #   YOLOv8-pose + ByteTrack + ML inference
│   ├── ingestion.py            #   Multi-camera orchestrator
│   ├── rtsp_manager.py         #   RTSP stream manager (FFmpeg)
│   ├── model_registry.py       #   Model versioning, export/import
│   ├── reports.py              #   PDF/CSV report generation
│   ├── training/               #   10 training scripts
│   │   ├── build_yolo_features.py
│   │   ├── train_yolo_risk_model.py
│   │   ├── train_yolo_task_model.py
│   │   ├── fine_tune_yolo.py
│   │   └── prepare_yolo_dataset.py
│   ├── Dockerfile              #   GPU + CPU support
│   └── tests/                  #   24 tests (all passing)
├── ui_posture/                 # React 19 SPA (31 pages)
│   ├── src/
│   │   ├── pages/              #   31 route pages (lazy-loaded)
│   │   │   ├── YoloDemoPage    #     Upload image → pose + risk overlay
│   │   │   ├── ModelDashboard  #     YOLO vs MediaPipe comparison
│   │   │   ├── ROIAnalytics    #     Cost savings, compliance scores
│   │   │   ├── SystemHealth    #     Service status, metrics
│   │   │   ├── Onboarding      #     10-step factory setup checklist
│   │   │   └── ...             #     26 more pages
│   │   ├── components/         #   Shared UI components
│   │   ├── hooks/              #   Data-fetching hooks
│   │   ├── services/           #   API client
│   │   └── auth/               #   Auth context + providers
│   └── vitest.config.ts        #   7 smoke tests
├── models/                     # ML model files
│   ├── yolo_risk_model.pkl     #   Risk classifier (94.1% accuracy)
│   ├── yolo_task_model.pkl     #   Task classifier (97.6% accuracy)
│   ├── best_model.pkl          #   MediaPipe risk model
│   └── task_model_v3.pkl       #   MediaPipe task model
├── scripts/                    # Training, labeling, evaluation
├── docs/                       # DEPLOYMENT.md, consent form, API docs
├── deploy/                     # Windows service scripts
├── tests/                      # Load test script
├── outputs/                    # Sessions, recordings, reports
└── docker-compose.yml          # 4 services (db, backend, frontend, cloud-core)
```

## Configuration

All configuration via environment variables (`.env` file or Docker env):

| Variable | Default | Description |
|---|---|---|
| `DEMO_MODE` | `false` | Seed synthetic data for presentations |
| `SESSIONS_DIR` | `outputs/sessions` | Where session JSON files are stored |
| `POSE_MODEL_PATH` | `models/pose_landmarker_lite.task` | MediaPipe pose model |
| `AUTH_JWT_SECRET` | (dev default) | JWT signing secret — **change in production** |
| `CAMERA_SOURCES` | `[]` | JSON array of IP/RTSP cameras |
| `DATABASE_URL` | `""` | PostgreSQL URL (optional, falls back to SQLite) |
| `RECORDINGS_MAX_GB` | `20` | Disk cap for video recordings |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server for AI assistant |

See `backend_api/.env.production.example` for the full reference.

## Testing

```bash
# Backend (233 tests)
cd backend_api && pytest -q

# Frontend (7 smoke tests)
cd ui_posture && npm test

# Typecheck
cd ui_posture && npx tsc --noEmit

# Production build
cd ui_posture && npm run build
```

## Model Accuracy

**Ground-truth accuracy: 87.6%** — evaluated against 500 human-labeled frames from real session recordings. Every score traces to a measured joint angle and a documented RULA/REBA-informed threshold.

- **Risk scoring**: Rule-based RULA/REBA-informed thresholds on 12 biomechanical features (not a black box)
- **Task classifier**: HistGradientBoosting, 76.9% self-consistency on held-out split (training labels are auto-generated)
- **Risk calibration**: HistGradientBoosting → REBA band, 91.8% holdout accuracy

The Validation Page (`/validation`) presents these numbers honestly to customers, including what we do and don't claim. See `results/ground_truth_evaluation.json` for the full evaluation.

The old 97.97% figure (circular, from auto-generated labels) has been removed from all user-facing surfaces.

## Deployment

### Docker (one command)
```bash
docker compose up -d --build
```

### Windows Service
```powershell
deploy\install_service.ps1    # Install as Windows service
deploy\start.bat              # Or start manually
```

### Environment Setup
1. Copy `backend_api/.env.production.example` to `.env`
2. Set `AUTH_JWT_SECRET` to a strong random string
3. Set `CAMERA_SOURCES` if using IP cameras
4. Set `DEMO_MODE=true` for presentations without a camera

## Documentation

| Document | Description |
|---|---|
| [System Architecture](docs/SYSTEM_ARCHITECTURE_PRESENTATION.md) | Full architecture, wireframes, presentation guide |
| [Delivery Checklist](docs/DELIVERY_CHECKLIST.md) | Factory pilot readiness tracker |
| [Data Collection Guide](docs/DATA_COLLECTION_GUIDE.md) | Ground-truth labeling workflow |
| [Pilot Guide](docs/PILOT_GUIDE.md) | On-site deployment instructions |
| [Ops Runbook](docs/OPS_RUNBOOK.md) | Operations and troubleshooting |
| [Current State](docs/CURRENT_STATE.md) | Feature inventory and model details |

## License

Internal use — GGS Internship Project.
