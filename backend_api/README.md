# ErgoVigilance API

FastAPI backend for the ErgoVigilance AI ergonomic monitoring platform.

---

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the development server
uvicorn app.main:app --reload --port 8000

# Open API docs
open http://localhost:8000/docs
```

---

## Project Structure

```
backend_api/
├── app/
│   ├── main.py                    # FastAPI application entry point
│   ├── api/
│   │   ├── router.py              # Aggregates all endpoint modules
│   │   ├── dashboard.py           # GET /api/dashboard, /api/session/latest
│   │   ├── sessions.py            # GET /api/sessions, POST /api/session/start|end
│   │   ├── trends.py              # GET /api/trends
│   │   ├── reports.py             # GET /api/reports, POST /api/report/generate
│   │   ├── cameras.py             # GET /api/cameras
│   │   ├── workstations.py        # GET /api/workstations
│   │   ├── deployment.py          # GET /api/deployment
│   │   ├── manager.py             # GET /api/manager
│   │   ├── alerts.py              # GET /api/alerts
│   │   └── websocket.py           # WS /ws/dashboard, /ws/alerts, /ws/camera
│   ├── schemas/
│   │   └── api.py                 # Pydantic models (exact React contracts)
│   ├── repositories/
│   │   ├── base.py                # Abstract DashboardRepository interface
│   │   └── mock.py                # MockRepository — serves hardcoded JSON
│   ├── core/
│   │   ├── config.py              # Environment-based configuration
│   │   ├── deps.py                # FastAPI dependency injection
│   │   ├── health.py              # Health check endpoint logic
│   │   └── logging.py             # Logging configuration
│   ├── websocket/
│   │   └── manager.py             # WebSocket connection manager
│   └── utils/
│       └── mock_data.py           # All mock JSON data matching React interfaces
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── requirements.txt
```

---

## API Endpoints

### REST

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/api/dashboard` | Current session dashboard |
| GET | `/api/session/latest` | Latest session data |
| GET | `/api/sessions` | Historical session list |
| GET | `/api/trends` | Weekly trends and feature trends |
| GET | `/api/reports` | Generated reports list |
| POST | `/api/report/generate` | Generate a new report |
| POST | `/api/session/start` | Start a monitoring session |
| POST | `/api/session/end` | End the current session |
| GET | `/api/cameras` | Camera status and metadata |
| GET | `/api/workstations` | Workstation posture data |
| GET | `/api/deployment` | Infrastructure metrics |
| GET | `/api/manager` | Factory manager summary |
| GET | `/api/alerts` | Active and historical alerts |

### WebSocket

| Path | Description |
|------|-------------|
| `/ws/dashboard` | Live risk and feature updates |
| `/ws/alerts` | Live alert notifications |
| `/ws/camera` | Live camera frame / status updates |

---

## OpenAPI Documentation

When the server is running, visit:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

---

## Data Flow

```
React Frontend (localhost:3000)
    │
    │ HTTP / WebSocket
    ▼
FastAPI (localhost:8000)
    │
    ├── MockRepository (USE_MOCK_REPOSITORY=true)
    │     └── Returns hardcoded JSON from app/utils/mock_data.py
    │
    └── ApiRepository (USE_MOCK_REPOSITORY=false — TODO)
          └── Connected to OpenCV / MediaPipe pipeline
```

Switch between mock and live mode by setting the `USE_MOCK_REPOSITORY` environment variable:

```bash
# Mock mode (default — no external dependencies)
USE_MOCK_REPOSITORY=true

# Live mode (requires OpenCV/MediaPipe pipeline)
USE_MOCK_REPOSITORY=false
```

---

## Future Integration

### Python CV + MediaPipe

The `ApiDashboardRepository` (not yet implemented) will consume data from the existing
`backend/services/` pipeline:

1. **Pose Detection** — `backend/services/pose.py` (MediaPipe) extracts 33 keypoints per frame
2. **Feature Extraction** — `backend/services/features.py` computes angles (neck, trunk, shoulder, knee)
3. **Issue Detection** — `backend/services/issue_detection.py` checks threshold violations
4. **Risk Classification** — MLP model predicts `riskLevel` from feature vectors
5. **Session Analytics** — `backend/services/session_analytics.py` aggregates per-session metrics
6. **Trend Analysis** — `backend/services/trend_analysis.py` computes weekly/daily trends
7. **Recommendations** — `backend/services/recommendation_engine.py` generates worker/supervisor tips
8. **Safety Reports** — `backend/services/safety_reporting.py` compiles PDF/CSV reports

### Implementation Plan

```python
# app/repositories/api.py (future)
class ApiRepository(DashboardRepository):
    def __init__(self):
        self.pose_service = PoseService()               # backend/services/pose.py
        self.feature_service = FeatureService()          # backend/services/features.py
        self.issue_service = IssueDetectionService()     # backend/services/issue_detection.py
        self.session_service = SessionAnalyticsService() # backend/services/session_analytics.py
        self.trend_service = TrendAnalysisService()      # backend/services/trend_analysis.py
        self.recommend_service = RecommendationService() # backend/services/recommendation_engine.py

    async def get_dashboard(self) -> DashboardResponse:
        # 1. Capture frame from camera
        # 2. Run MediaPipe pose detection
        # 3. Extract ergonomic features
        # 4. Detect issues from thresholds
        # 5. Generate recommendations
        # 6. Compile DashboardResponse
        ...
```

### WebSocket Streaming

When the real pipeline is connected, the WebSocket endpoints will broadcast:

- `/ws/dashboard` — risk level changes, feature value updates, new issues every ~2 seconds
- `/ws/alerts` — instant push when a critical threshold is exceeded
- `/ws/camera` — compressed frame data or skeleton overlay for the CameraPanel

---

## Testing

```bash
# Install test dependencies
pip install pytest httpx

# Run tests
pytest app/tests/ -v
```

---

## Docker

```bash
# Build and run
docker compose up --build

# The API will be available at http://localhost:8000
```

---

## Configuration

All configuration is via environment variables (see `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8000` | Server port |
| `DEBUG` | `true` | Enable debug mode |
| `CORS_ORIGINS` | `http://localhost:3000,...` | Allowed CORS origins |
| `USE_MOCK_REPOSITORY` | `true` | Use mock data vs live pipeline |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
