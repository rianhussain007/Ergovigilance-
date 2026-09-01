# Changelog

All notable changes to ErgoVigilance are documented here.

## [1.0.0] - 2026-09-01

### Added — YOLO Cloud Core
- **RTSP Stream Ingestion** — FFmpeg-based RTSP ingestion with auto-reconnect
- **YOLOv8-pose Inference** — 17-keypoint COCO pose detection
- **ByteTrack Worker Tracking** — Track individual workers across frames
- **ML Risk Classifier** — HistGradientBoosting, 94.1% accuracy (73K samples)
- **ML Task Classifier** — HistGradientBoosting, 97.6% accuracy (7 task classes)
- **Docker GPU Support** — NVIDIA CUDA base image for GPU inference
- **Rate Limiting** — 120 req/min general, 10 camera writes/min
- **WebSocket Streaming** — Live camera data push (2s interval)

### Added — Training Pipeline
- **Feature Extraction** — COCO_17 keypoint mapping (shared with MediaPipe core)
- **Risk Model Training** — 5-fold cross-validation, balanced classes
- **Task Model Training** — 7 classes: Reaching, Lifting, Assembly, Standing, Seated, Walking, Inspection
- **Synthetic Data Generation** — Seated Work, Inspection, Walking keypoints from REBA data
- **Keypoint Extraction** — From 47 factory videos (YouTube + HuggingFace + Voxel51)
- **Data Augmentation** — Gaussian noise injection (2x sample multiplier)
- **YOLO Fine-tuning Script** — Factory-specific posture detection
- **Dataset Preparation** — YOLOv8-pose format converter

### Added — Frontend Pages (12 new)
- **YOLO Demo** — Upload image → see pose + risk overlay
- **Model Dashboard** — YOLO vs MediaPipe comparison, confusion matrix, versioning
- **ROI Analytics** — Cost savings, compliance scores, business case
- **System Health** — Service status, storage, live metrics
- **Onboarding Checklist** — 10-step factory setup guide
- **Cloud Cameras** — Camera management with health monitoring
- **Cloud Settings** — YOLO model config + RTSP connection tester
- **Pricing** — 3-tier pricing (Starter/Cloud/Enterprise)

### Added — Backend Endpoints (25 new)
- Camera CRUD, start, stop, health
- Session management, alerts, reports
- Model metrics, comparison, versions
- Inference detection (image → pose + risk)
- WebSocket for live camera data
- Model export/import/rollback

### Added — Documentation
- **DEPLOYMENT.md** — Factory IT setup guide (Docker, cameras, troubleshooting)
- **Worker Consent Form** — HTML template for PDF generation
- **API Documentation** — Interactive Swagger UI

### Added — Infrastructure
- **Docker Compose** — 4 services (db, backend, frontend, cloud-core)
- **Nginx Config** — Security headers, CSP, WebSocket proxy
- **Rate Limiting** — Cloud core API protection
- **Model Registry** — Versioning, export/import, rollback

### Improved
- **Search Modal** — Real API data (sessions + workers) instead of mock
- **Product Tour** — Auto-starts in demo mode, spotlight + tooltips
- **Keyboard Shortcuts** — `?` help, `Ctrl+K` search, single-key nav
- **API Documentation** — Interactive docs for IT teams

### Fixed
- **Unicode Encoding** — CSV writer uses UTF-8 for international characters
- **Feature Importance** — HistGradientBoosting compatibility (no `feature_importances_`)

## [0.9.0] - 2026-08-30

### Added
- **Demo Mode** — Synthetic data seeding, amber banner
- **User Invitations** — Admin invite flow with temp passwords
- **Email/Slack Notifications** — Alert engine integration
- **CSP Security Headers** — Nginx Content-Security-Policy
- **Rate Limiting** — Backend API protection
- **OG Meta Tags** — SEO optimization

### Improved
- **Docker Hardening** — Non-root user, healthcheck, .dockerignore
- **Production Config** — `.env.production.example` (60+ variables)
- **CI Pipeline** — Docker build step

## [0.8.0] - 2026-08-25

### Added
- **Integration Tests** — 34 backend tests
- **Settings Notifications** — UI for email/Slack configuration
- **Smoke Tests** — 7 frontend vitest tests
- **Code Splitting** — React.lazy for all routes

### Improved
- **Ground Truth Accuracy** — 87.6% on 500 labeled frames
- **Validation Page** — Honest accuracy disclosure

## [0.7.0] - 2026-08-20

### Added
- **Multi-Camera View** — Simultaneous camera monitoring
- **Video Review** — Upload and analyze recorded videos
- **Session Replay** — Frame-by-frame pose analysis
- **AI Assistant** — Ollama-powered ergonomic advice

## [0.6.0] - 2026-08-15

### Added
- **Worker Management** — CRUD, face samples, identity
- **Alert Management** — Acknowledge/resolve lifecycle
- **Audit Trail** — Complete activity logging
- **Deployment Center** — Infrastructure health monitoring

## [0.5.0] - 2026-08-10

### Added
- **Live Monitoring** — Real-time pose estimation at 30 FPS
- **Risk Scoring** — RULA/REBA standard-method assessment
- **Task Classification** — 7 task classes
- **Dashboard** — Role-gated views (operator, supervisor, admin)

## [0.4.0] - 2026-08-05

### Added
- **Authentication** — JWT-based login/register
- **Session Management** — Start/stop/delete sessions
- **Basic Reporting** — Session history, risk trends

## [0.3.0] - 2026-08-01

### Added
- **Pose Estimation** — MediaPipe Pose (33 keypoints)
- **Feature Extraction** — 17 biomechanical features
- **Risk Calculation** — Task-conditional thresholds

## [0.2.0] - 2026-07-25

### Added
- **Backend API** — FastAPI application structure
- **Database** — SQLite/PostgreSQL support
- **Frontend** — React 19 SPA with Tailwind CSS

## [0.1.0] - 2026-07-20

### Added
- **Project Setup** — Initial repository structure
- **README** — Project documentation
- **Docker** — Basic Dockerfile
