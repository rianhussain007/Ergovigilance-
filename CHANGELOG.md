
## [1.0.0] - 2026-09-02

### Initial Release

#### Dashboard & UI
- 38-page React dashboard with dark theme and glassmorphism design
- Product Tour with 13-step interactive guide
- Bilingual support (English, Hindi, Chinese)
- WCAG 2.1 AA accessibility (skip links, ARIA, focus management)
- GDPR/CCPA consent management system
- System Health monitoring with live service status
- Architecture diagram page for technical buyers
- Model Card page with honest per-class metrics
- On-Site Pilot Checklist with progress tracking

#### Computer Vision & ML
- MediaPipe Tasks API (v1.0) pose detection with 33 landmarks
- YOLO cloud core with RTSP ingestion (4,719 lines)
- v2 risk model: 98.2% CV F1 across HIGH/MEDIUM/LOW
- v2 task model: 97.1% CV F1 across 4 balanced classes
- RULA/REBA-informed risk scoring
- Temporal smoothing with confidence-weighted sliding window
- Geometric posture gate for seated work detection
- 780 training samples from 56 factory videos

#### Webcam Demo
- Live webcam pose detection with skeleton overlay
- Risk-colored overlay (green/amber/red)
- Real-time FPS and inference metrics
- Side panel with risk score, task detection, key features

#### Backend API
- FastAPI with 50+ REST endpoints
- JWT authentication with MFA/TOTP
- RBAC (admin, supervisor, safety_mgr, operator)
- PostgreSQL + SQLite dual-backend support
- SOC2 audit logging with HMAC chain integrity
- Rate limiting per role
- Session lifecycle management
- PDF/CSV report export
- WebSocket real-time updates

#### YOLO Cloud Core
- FastAPI service on port 8100
- RTSP camera stream management
- Email notifications (SMTP)
- Slack webhook integration
- Webhook system for external integrations
- Model registry for YOLO models
- Tenant-aware middleware
- Rate limiting
- Daily/weekly PDF reports

#### Deployment
- Docker Compose (db, backend, frontend, cloud-core)
- Dockerfile with multi-worker uvicorn
- Nginx reverse proxy with security headers
- K8s manifests
- Trivy container scanning in CI
- GitHub Actions CI (lint, build, audit, Docker)
- .env.production.example with all config options

#### Security
- MFA/TOTP with backup codes
- SOC2 audit trail with HMAC chain
- Security headers (CSP, X-Frame-Options, etc.)
- Per-role rate limiting
- GDPR consent + data export + retention
- DPA template for enterprise procurement

#### Testing
- 17 backend E2E smoke tests
- 24 cloud core unit tests
- 7 frontend smoke tests
- 25-endpoint integration smoke test
- Load testing script

#### Documentation
- LICENSE (MIT)
- CHANGELOG.md
- Security Questionnaire (118-line FAQ)
- DPA template (173-line GDPR-compliant)
- Pilot Deployment Checklist
- Model Card with honest metrics
- 20+ documentation files
# Changelog

All notable changes to ErgoVigilance will be documented in this file.

## [0.9.0-pilot] - 2026-09-02

### Enterprise Features
- PostgreSQL support with SQLite fallback (db_backend adapter)
- MFA/TOTP for admin accounts with backup codes
- SOC2 audit logging with HMAC chain integrity
- Per-role rate limiting (admin 3x, operator 1x)
- Security headers (HSTS, CSP, X-Frame-Options, Referrer-Policy)
- Input sanitization (XSS, SQL injection, path traversal)
- API versioning (URL/Header/Query negotiation)
- Structured JSON logging for ELK/Datadog/Splunk
- Response caching with TTL
- Request ID tracking for distributed tracing
- Graceful shutdown with in-flight request draining
- Auto-recovery with health monitoring
- Circuit breakers (Ollama, SMTP, Webhooks)

### Privacy & Compliance
- GDPR/CCPA consent management system
- Worker data export (Article 20 portability)
- Tenant isolation middleware
- WCAG 2.1 AA accessibility improvements

### Deployment
- Kubernetes manifests (Deployments, HPA, Ingress, NetworkPolicy)
- Backup/restore scripts with retention
- Grafana dashboard JSON
- Load testing script (concurrent user simulation)
- Deployment smoke test (25+ endpoints)

### Frontend
- Enterprise monitoring cards on System Health page
- Camera capture for face enrollment
- Rate limit info headers (X-RateLimit-*)
- Product tour and keyboard shortcuts

### Bug Fixes
- Logo SVG viewBox widened to prevent cut-off 'e'
- Rate limiter exemptions for health endpoints

## [0.8.0-alpha] - 2026-08-28

### Initial SaaS Platform
- YOLO cloud core for CCTV RTSP monitoring
- Multi-tenant camera management
- SaaS pricing and billing (Stripe)
- i18n (English, Hindi, Chinese)
- Architecture page for technical buyers
