# Changelog

All notable changes to ErgoVigilance will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-09-03

### 🎉 Initial Release

ErgoVigilance v1.0.0 is a production-ready AI-powered ergonomic risk monitoring platform with dual-core architecture (MediaPipe on-premise + YOLO cloud).

---

### ✨ Added

#### Frontend (39 pages)
- **Dashboard** — Executive dashboard with real-time risk scores, worker status, department heatmaps
- **Live Monitoring** — Real-time 33-point pose tracking with skeleton overlay and risk coloring
- **Webcam Demo** — Live webcam demo with pose detection and risk scores
- **YOLO Demo** — YOLO-based pose detection demo
- **Analytics** — Cross-session analytics with trend charts and department comparisons
- **ROI Analytics** — Cost savings calculator and business case builder
- **Reports** — Auto-generated PDF/CSV compliance reports
- **Sessions** — Session history with replay and annotation
- **Workers** — Employee management with profiles, consent tracking, risk history
- **Users** — User management with roles (Admin, Safety Manager, Supervisor, Operator)
- **Settings** — System configuration with notification preferences
- **Cloud Cameras** — RTSP camera management for cloud tier
- **Cloud Settings** — YOLO model configuration, confidence thresholds, RTSP defaults
- **System Health** — Real-time service status monitoring
- **API Documentation** — Interactive API docs with code examples
- **Model Dashboard** — ML model performance metrics
- **Architecture** — System architecture diagram
- **Deployment** — Deployment status and configuration
- **Audit Trail** — SOC2-compliant audit log
- **Consent Management** — Worker consent tracking
- **Onboarding** — 5-step guided setup wizard
- **Pilot Checklist** — Factory pilot deployment guide
- **Pilot Requests** — Demo request management
- **Pricing** — Tier comparison with Stripe checkout
- **Request Pilot** — Demo request form
- **Landing Page** — Marketing page with product tour

#### Backend API (45+ endpoints)
- **Authentication** — JWT auth with MFA/TOTP support
- **Authorization** — RBAC with 4 roles (Admin, Safety Manager, Supervisor, Operator)
- **Workers** — CRUD with org-scoped isolation
- **Sessions** — Start/stop/replay with risk timeline
- **Alerts** — Real-time alerts with acknowledge/resolve workflow
- **Reports** — PDF/CSV generation with daily/weekly summaries
- **Dashboard** — Aggregated metrics and trends
- **Search** — Full-text search across workers, sessions, alerts
- **Audit** — SOC2-compliant audit trail
- **Billing** — Stripe checkout, subscriptions, webhooks
- **Organizations** — Multi-tenant isolation with API keys
- **Signup** — Self-service organization creation
- **Health** — `/health` and `/healthz` endpoints
- **WebSocket** — Real-time data streaming

#### YOLO Cloud Core (4,700+ lines)
- **RTSP Ingestion** — Connect IP cameras via RTSP streams
- **Pose Engine** — YOLOv8-pose inference with GPU acceleration
- **Risk Scoring** — RULA/REBA-informed risk classification
- **Task Recognition** — 5-class task identification (Assembly, Inspection, Lifting, Seated, Neutral)
- **Alerts** — Email (SMTP) and Slack webhook notifications
- **Reports** — Daily/weekly PDF reports
- **Webhooks** — Custom webhook integrations
- **Model Registry** — Versioned model management
- **Organization Auth** — API key authentication for multi-tenant

#### MediaPipe On-Premise Engine
- **Pose Detection** — 33-point MediaPipe pose landmarks
- **Risk Scoring** — HistGradientBoosting classifier (88.6% F1)
- **Task Recognition** — 5-class task classifier (86.4% F1)
- **Temporal Smoothing** — Confidence-weighted sliding window
- **Geometric Gate** — Seated work detection via knee angle
- **Dwell Time** — Task duration tracking

#### Machine Learning
- **Risk Model** — HistGradientBoosting, 88.6% CV F1
  - HIGH: 100% F1
  - LOW: 88.5% F1
  - MEDIUM: 58.3% F1
- **Task Model** — HistGradientBoosting, 86.4% CV F1
  - Assembly Work: 99.6% F1
  - Inspection: 99.6% F1
  - Lifting/Carrying: 100% F1
  - Seated Work: 96.4% F1
  - Neutral Standing: 94.8% F1
- **Training Data** — 1,937 samples from 41 videos
- **Retraining Pipeline** — Automated model improvement

#### Multi-Tenancy
- **Organizations** — Per-factory data isolation
- **API Keys** — Org-scoped cloud core authentication
- **Org Switcher** — Admin UI for switching between factories
- **Tenant Filtering** — All endpoints filter by org_id

#### Security
- **JWT + MFA** — Token-based auth with TOTP support
- **RBAC** — 4 roles with granular permissions
- **CSP Headers** — Content Security Policy
- **Rate Limiting** — API and login rate limits
- **Audit Trail** — SOC2-compliant logging
- **GDPR** — Consent management, data export, retention

#### Deployment
- **Docker Compose** — 4 services (frontend, backend, cloud-core, nginx)
- **Nginx** — Production config with security headers
- **CI/CD** — GitHub Actions pipeline
- **Kubernetes** — K8s manifests
- **Trivy** — Container security scanning

#### Documentation
- **DEPLOYMENT.md** — Enterprise deployment guide
- **MARKETING_ONE_PAGER.md** — Sales one-pager
- **PRODUCT_DEMO_SCRIPT.md** — 2-minute demo script
- **CHANGELOG.md** — This file
- **LICENSE** — MIT License

---

### 🔧 Fixed

- **SQLite transactions** — Added commit/rollback on context manager exit
- **Vite proxy** — Changed from port 8001 to 8000 to match uvicorn
- **Onboarding checklist** — Replaced static with 5-step guided wizard
- **TypeScript errors** — Fixed apiFetch Response handling
- **MediaPipe 1.0** — Updated to Tasks API for video extraction

---

### 📊 Performance

- **Risk Model**: 76.9% → 88.6% F1 (+11.7%)
- **Task Model**: 70.8% → 86.4% F1 (+15.6%)
- **Training Data**: 705 → 1,937 samples (+175%)
- **Frontend**: 39 pages, <2s initial load
- **Backend**: 45+ endpoints, <100ms response time

---

## [0.9.0] - 2026-08-28

### Added
- Initial beta release
- Basic pose detection
- Simple risk scoring
- Worker management

---

## [0.1.0] - 2026-06-01

### Added
- Project inception
- MediaPipe integration
- Basic dashboard

---

*For more details, see the [README](README.md) and [DEPLOYMENT](DEPLOYMENT.md).*
