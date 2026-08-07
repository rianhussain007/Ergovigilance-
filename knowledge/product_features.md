# ErgoVigilance Product Features

## Overview

ErgoVigilance is an AI-powered industrial ergonomics monitoring platform. It uses a single webcam + MediaPipe pose estimation to track 7 body features, classifies risk as LOW/MEDIUM/HIGH, generates real-time alerts and recommendations, and saves session data for review.

## Architecture (Two-Backend Design)

### `backend/` — AI Core
Pure Python engines that know nothing about HTTP:
- `pose_engine.py` — MediaPipe PoseLandmarker wrapper (single pose, VIDEO mode)
- `features.py` — 7-feature extraction from 33 landmarks
- `context/engine.py` — Context Intelligence Engine (risk scoring, fatigue, exposure)
- `alerts/engine.py` — Alert Engine (rules-based, in-memory)
- `recommendations/engine.py` — Recommendation Engine (12 templates)
- `history/engine.py` — History Engine (tiered storage, downsampling)
- `events/event_bus.py` — Synchronous in-process pub/sub

### `backend_api/` — API Wrapper
FastAPI layer exposing `backend/` over HTTP:
- `live_monitor.py` — owns engine instances, runs frame-processing loop
- `repositories/live.py` — translates internal state to API schema
- `api/*.py` — FastAPI route definitions

### `ui_posture/` — React Frontend
Vite + React + TypeScript + Tailwind CSS on port 3000.
- Data flow: React hooks poll REST endpoints every 1-2 seconds
- Config: `USE_MOCK: false` (live data by default)
- Repository pattern: `ApiDashboardRepository` or `MockDashboardRepository`

## Key Capabilities
- Live webcam posture analysis at ~13-15 FPS
- 7 ergonomic features computed per frame
- Context-adjusted risk scoring (0-100)
- Fatigue and exposure tracking
- Rules-based alert engine with 4 rule types
- 12 recommendation templates across 6 categories
- In-memory alert lifecycle (ACTIVE -> ACKNOWLEDGED -> RESOLVED)
- History with tiered storage (300s full resolution, then 10x downsampling)
- Session persistence (JSON + video) saved on stop
- RBAC with 4 roles: operator, supervisor, safety_mgr, admin
- Video recording (best-effort sidecar)
- Upload & analyze arbitrary videos (<= 200MB)
- Replay for recorded sessions

## Pages in React Frontend
| Page | Data Quality |
|------|-------------|
| LiveMonitoring (/) | Mixed — live KPIs + hardcoded demo cards |
| SessionHistory (/sessions) | Fully live |
| TrendAnalysis (/trends) | Mixed — live KPIs + hardcoded weekly chart |
| Analytics (/analytics) | Mixed — live KPIs + hardcoded charts |
| Reports (/reports) | Fully static (hardcoded mock data) |
| Manager Dashboard (/manager) | Mixed — live KPIs + hardcoded workers |
| Deployment Center (/deployment) | Fully static |
| Multi-Camera (/cameras) | Fully static |
| Audit Trail (/audit) | Fully static |
| Settings (/settings) | Uses localStorage only |

## Tech Stack
- Pose detection: MediaPipe Pose / MediaPipe Tasks
- Classification: Threshold-based (no ML model in live pipeline)
- Backend: FastAPI (port 8000)
- Frontend: Vite + React + TypeScript + Tailwind CSS (port 3000)
- Language: Python + TypeScript
- Runtime: Windows, local only
- Database: Local SQLite (users, workers, auth)
