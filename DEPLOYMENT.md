# ErgoVigilance — Deployment Guide

## Quick Start (Docker)

```bash
# 1. Clone the repository
git clone https://github.com/rianhussain007/Ergovigilance-.git
cd Ergovigilance-

# 2. Copy and edit environment file
cp backend_api/.env backend_api/.env
# Edit backend_api/.env — set AUTH_JWT_SECRET to a strong random value

# 3. Start all services
docker compose up -d

# 4. Access the application
# Frontend: http://localhost:8080
# Backend API: http://localhost:8001
# API Docs: http://localhost:8001/docs
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Docker Compose                        │
│                                                         │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Frontend │  │   Backend    │  │   PostgreSQL     │  │
│  │ (Nginx)  │──│  (FastAPI)   │──│  (Port 5432)     │  │
│  │ :8080    │  │  :8000       │  │                  │  │
│  └──────────┘  └──────────────┘  └──────────────────┘  │
│       │              │                                  │
│       │         ┌────┴────┐                             │
│       │         │ SQLite  │  ← Session JSON files       │
│       │         │ :/data/ │                             │
│       │         └─────────┘                             │
└─────────────────────────────────────────────────────────┘
```

## Services

| Service | Port | Purpose |
|---------|------|---------|
| **Frontend** | 8080 | React dashboard (Vite + Nginx) |
| **Backend** | 8001 | FastAPI REST API + WebSocket |
| **Database** | 5433 | PostgreSQL 16 (telemetry store) |

## Configuration

### Environment Variables (backend_api/.env)

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG` | `false` | Set `true` for development |
| `AUTH_JWT_SECRET` | *(required)* | JWT signing secret (min 32 chars) |
| `DATABASE_URL` | `postgresql://...` | PostgreSQL connection string |
| `SESSIONS_DIR` | `/data/sessions` | Path to session JSON files |
| `POSE_MODEL_PATH` | `models/pose_landmarker_lite.task` | MediaPipe pose model |
| `DEMO_MODE` | `false` | Enable demo mode with synthetic data |
| `RATE_LIMIT_MAX_REQUESTS` | `100` | Max API requests per minute per IP |
| `RATE_LIMIT_AUTH_MAX` | `10` | Max auth attempts per minute per IP |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama AI assistant URL |
| `LOG_LEVEL` | `INFO` | Logging level |

### Production Setup

```bash
# Generate a secure JWT secret
python -c "import secrets; print(secrets.token_hex(32))"

# Set in .env
AUTH_JWT_SECRET=<your-generated-secret>
DEBUG=false
DEMO_MODE=false
```

## Model Files

The following models are required (shipped in `models/`):

| Model | Size | Purpose |
|-------|------|---------|
| `pose_landmarker_lite.task` | 5.7 MB | Real-time pose detection (33 landmarks) |
| `task_model_v3.pkl` | ~3 MB | Task classification (7 classes) |
| `risk_calibration_model.pkl` | ~300 KB | Risk band calibration |
| `risk_forecaster.pkl` | ~300 KB | Per-joint risk forecasting |
| `face_landmarker.task` | 3.7 MB | Face detection for worker ID |
| `face_recognition_sface_2021dec.onnx` | 38 MB | Face recognition model |

## API Endpoints

### Health & System
- `GET /health` — Health check (no auth)
- `GET /healthz` — Kubernetes liveness probe
- `GET /readyz` — Kubernetes readiness probe

### Core
- `GET /api/sessions` — List all sessions
- `GET /api/deployment` — Deployment metrics
- `GET /api/manager` — Manager summary
- `POST /api/sessions/start` — Start live monitoring
- `POST /api/sessions/stop` — Stop live monitoring

### Reports
- `GET /api/reports/pdf/:sessionId` — Generate PDF report
- `GET /api/reports/csv/:sessionId` — Export CSV

## Troubleshooting

### Backend returns 503
- Check if the pose model exists: `ls models/pose_landmarker_lite.task`
- Check Docker logs: `docker logs ergovigilance-backend`

### Sessions not loading
- Verify volume mount: `docker exec ergovigilance-backend ls /data/sessions/`
- Check session files exist: `ls outputs/sessions/`

### Database connection failed
- Verify PostgreSQL is running: `docker compose ps db`
- Check connection: `docker exec ergovigilance-backend python -c "import psycopg2; psycopg2.connect('postgresql://ergovigilance:ergovigilance@db:5432/ergovigilance')"`

### Frontend not loading
- Check Nginx config: `docker exec ergovigilance-frontend cat /etc/nginx/conf.d/default.conf`
- Verify backend proxy: `curl http://localhost:8080/api/health`

## Development

```bash
# Start without Docker
cd backend_api && python -m uvicorn app.main:app --reload --port 8000
cd ui_posture && npx vite --port 5173

# Run tests
cd backend_api && python -m pytest
cd ui_posture && npx vitest
```

## Security Notes

- Never commit `.env` files with real secrets
- Use `DEBUG=false` in production
- Set strong `AUTH_JWT_SECRET` (min 32 chars)
- Rate limiting is enabled by default (100 req/min)
- CORS is configured for specific origins
- All API endpoints require JWT authentication (except health checks)
