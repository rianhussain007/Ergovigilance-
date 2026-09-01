# ErgoVigilance Enterprise Deployment Guide

## Overview

This guide covers enterprise deployment of ErgoVigilance with production-grade security, monitoring, and scalability.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Load Balancer (nginx/HAProxy/Cloud LB)                │
│  ┌──────────────────────────────────────────────────┐   │
│  │  TLS Termination + Rate Limiting                 │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │ Frontend    │  │ Frontend    │  │ Frontend    │     │
│  │ (nginx)     │  │ (nginx)     │  │ (nginx)     │     │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘     │
│         │                │                │             │
│  ┌──────▼────────────────▼────────────────▼──────┐     │
│  │         Backend API (FastAPI)                  │     │
│  │  • JWT Auth + MFA/TOTP                        │     │
│  │  • Security Headers                           │     │
│  │  • Circuit Breaker                            │     │
│  │  • Structured Logging                         │     │
│  │  • API Versioning                             │     │
│  └──────────────────┬────────────────────────────┘     │
│                     │                                   │
│  ┌──────────────────▼────────────────────────────┐     │
│  │         PostgreSQL (StatefulSet)              │     │
│  │  • Persistent Storage (10Gi)                  │     │
│  │  • Automated Backups                          │     │
│  └───────────────────────────────────────────────┘     │
│                                                         │
│  ┌───────────────────────────────────────────────┐     │
│  │         YOLO Cloud Core (Optional)            │     │
│  │  • RTSP Camera Ingestion                      │     │
│  │  • GPU Acceleration                           │     │
│  └───────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────┘
```

## Quick Start

### Docker Compose (Recommended)

```bash
# 1. Clone the repository
git clone https://github.com/your-org/ergovigilance.git
cd ergovigilance

# 2. Copy environment template
cp .env.production.example .env

# 3. Edit .env with your values
nano .env

# 4. Start all services
docker compose up -d

# 5. Verify
curl http://localhost:8001/health
```

### Kubernetes

```bash
# 1. Create namespace
kubectl apply -f deploy/k8s/namespace.yaml

# 2. Create secrets (edit first!)
kubectl apply -f deploy/k8s/secrets-template.yaml

# 3. Deploy all services
kubectl apply -f deploy/k8s/

# 4. Check status
kubectl get pods -n ergovigilance
```

## Security Configuration

### Environment Variables

```bash
# Required for production
DEBUG=false
AUTH_JWT_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(64))")
ENABLE_HSTS=true

# Database
DATABASE_URL=postgresql://user:pass@host:5432/ergovigilance

# Notifications
SMTP_HOST=smtp.gmail.com
SMTP_USER=alerts@yourcompany.com
SMTP_PASS=app-password
ALERT_RECIPIENTS=safety@yourcompany.com
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...

# Billing (optional)
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

### MFA/TOTP Setup

1. Admin logs in → Settings → Security → Enable MFA
2. Scan QR code with Google Authenticator / Authy
3. Enter verification code
4. Save backup codes securely

### Security Headers

The following headers are automatically applied:
- `Strict-Transport-Security: max-age=63072000; includeSubDomains; preload`
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Content-Security-Policy: ...`
- `Referrer-Policy: strict-origin-when-cross-origin`

## Monitoring

### Prometheus Metrics

```bash
# Available at /metrics
curl http://localhost:8001/metrics

# Key metrics:
# ergo_uptime_seconds - Server uptime
# ergo_active_sessions - Active monitoring sessions
# ergovigilance_db_latency_ms - Database query latency
# ergovigilance_websockets_active - Active WebSocket connections
# http_requests_total - Total HTTP requests
```

### Grafana Dashboard

Import `deploy/grafana/dashboard.json` into Grafana:
1. Grafana → Dashboards → Import
2. Upload JSON file
3. Select Prometheus data source

### Health Checks

```bash
# Liveness (always 200 when running)
curl http://localhost:8001/healthz

# Readiness (200 when ready to serve)
curl http://localhost:8001/readyz

# Full health status
curl http://localhost:8001/health
```

## Backup & Restore

### Automated Backups

```bash
# Run backup
./deploy/backup.sh

# Backup with 30-day retention
./deploy/backup.sh --retention=30

# Database only
./deploy/backup.sh --db-only
```

### Restore

```bash
# Dry run (see what would be restored)
./deploy/restore.sh backups/ergovigilance_backup_*.tar.gz --dry-run

# Full restore
./deploy/restore.sh backups/ergovigilance_backup_*.tar.gz
```

### Cron Job (Daily Backup)

```bash
# Add to crontab
0 2 * * * /path/to/ergovigilance/deploy/backup.sh --retention=30 >> /var/log/ergovigilance-backup.log 2>&1
```

## Scaling

### Horizontal Pod Autoscaler

The HPA is configured to:
- Scale backend: 2-10 pods (CPU 70%, Memory 80%)
- Scale frontend: 2-5 pods (CPU 70%)
- Scale up: 2 pods per minute
- Scale down: 1 pod per 2 minutes

### Manual Scaling

```bash
# Scale backend
kubectl scale deployment ergovigilance-backend --replicas=5 -n ergovigilance

# Scale frontend
kubectl scale deployment ergovigilance-frontend --replicas=3 -n ergovigilance
```

## Load Testing

```bash
# Install dependencies
pip install aiohttp

# Run load test
python deploy/load_test.py --url http://localhost:8001 --users 50 --duration 60

# Production validation
python deploy/load_test.py --url https://ergovigilance.yourdomain.com --users 100 --duration 300
```

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| Database connection failed | Check `DATABASE_URL` and PostgreSQL is running |
| JWT token invalid | Regenerate `AUTH_JWT_SECRET` and restart |
| Rate limit exceeded | Increase `RATE_LIMIT_MAX_REQUESTS` in .env |
| WebSocket not connecting | Check firewall allows WebSocket upgrade |
| Backup failed | Verify `pg_dump` is installed and DB credentials |

### Logs

```bash
# Docker logs
docker compose logs -f backend
docker compose logs -f frontend

# Kubernetes logs
kubectl logs -f deployment/ergovigilance-backend -n ergovigilance

# Structured JSON logs (for ELK/Datadog)
LOG_FORMAT=json LOG_LEVEL=DEBUG docker compose up backend
```

## API Versioning

The API supports versioning via:
- URL path: `/api/v1/sessions`
- Header: `Accept: application/vnd.ergovigilance.v1+json`
- Query: `/api/sessions?version=1`

All responses include:
- `X-API-Version: v1`
- `X-API-Supported-Versions: v1`
- `X-API-Latest-Version: v1`

## Enterprise Support

For enterprise support, contact:
- Email: enterprise@ergovigilance.com
- SLA: 99.9% uptime guarantee
- Response: 4-hour critical, 24-hour non-critical
