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
