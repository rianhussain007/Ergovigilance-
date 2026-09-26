# ErgoVigilance Deployment Guide

**Version**: 1.0.0  
**Last Updated**: September 2026  
**Audience**: Factory IT teams, system administrators, DevOps engineers

---

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Quick Start (Docker)](#quick-start-docker)
3. [Manual Installation](#manual-installation)
4. [Environment Configuration](#environment-configuration)
5. [Camera Setup](#camera-setup)
6. [Network Configuration](#network-configuration)
7. [Security Hardening](#security-hardening)
8. [Backup & Restore](#backup--restore)
9. [Monitoring & Health Checks](#monitoring--health-checks)
10. [Troubleshooting](#troubleshooting)
11. [Hardware Recommendations](#hardware-recommendations)

---

## System Requirements

### Minimum (Pilot / 1-3 cameras)

| Component | Requirement |
|-----------|-------------|
| **CPU** | 4 cores, 2.5 GHz |
| **RAM** | 8 GB |
| **Storage** | 50 GB SSD |
| **OS** | Ubuntu 22.04 LTS, Windows 10/11, macOS 12+ |
| **Network** | 100 Mbps LAN |
| **GPU** | Optional (CPU inference works, GPU is 3x faster) |

### Recommended (Production / 5-20 cameras)

| Component | Requirement |
|-----------|-------------|
| **CPU** | 8 cores, 3.0 GHz |
| **RAM** | 16 GB |
| **Storage** | 200 GB SSD |
| **OS** | Ubuntu 22.04 LTS |
| **Network** | 1 Gbps LAN |
| **GPU** | NVIDIA RTX 3060 or better (for YOLO cloud core) |

### Enterprise (20+ cameras)

| Component | Requirement |
|-----------|-------------|
| **CPU** | 16+ cores, 3.5 GHz |
| **RAM** | 32 GB |
| **Storage** | 1 TB NVMe SSD |
| **OS** | Ubuntu 22.04 LTS |
| **Network** | 1 Gbps dedicated |
| **GPU** | NVIDIA RTX 4090 or A100 |

---

## Quick Start (Docker)

### Prerequisites

- Docker Engine 24.0+ and Docker Compose v2
- Git

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/ergovigilance/posture_analysis.git
cd posture_analysis

# 2. Copy and configure environment
cp .env.production.example .env
# Edit .env with your settings (see Environment Configuration)

# 3. Start all services
docker compose up -d

# 4. Verify services are running
docker compose ps

# 5. Access the application
# Frontend: http://localhost:8080
# Backend API: http://localhost:8001
# Cloud Core: http://localhost:8100
```

### Default Login Credentials

| Role | Email | Password |
|------|-------|----------|
| Admin | admin@example.local | AdminPass123! |
| Supervisor | supervisor@example.local | SupervisorPass123! |
| Safety Manager | safety@example.local | SafetyPass123! |
| Operator | operator@example.local | OperatorPass123! |

⚠️ **Change these passwords immediately in production!**

---

## Manual Installation

### Backend API

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

# 2. Install dependencies
cd backend_api
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your settings

# 4. Start the server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Frontend

```bash
# 1. Install Node.js 18+ and npm

# 2. Install dependencies
cd ui_posture
npm install

# 3. Build for production
npm run build

# 4. Serve with nginx or any static server
# The build output is in dist/
```

### YOLO Cloud Core (Optional)

```bash
# 1. Install dependencies
cd yolo_cloud
pip install -r requirements.txt

# 2. Download YOLO model
python -c "from ultralytics import YOLO; YOLO('yolov8s-pose.pt')"

# 3. Configure environment
cp .env.example .env
# Edit .env with RTSP camera URLs

# 4. Start the cloud core
uvicorn api:app --host 0.0.0.0 --port 8100
```

---

## Environment Configuration

### Essential Variables

```bash
# Security (CRITICAL)
DEBUG=false                          # Set to false in production
AUTH_JWT_SECRET=<random-64-chars>    # Generate: python -c "import secrets; print(secrets.token_urlsafe(64))"

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/ergovigilance
# Or use SQLite (default): leave DATABASE_URL empty

# Ports
BACKEND_PORT=8000
FRONTEND_PORT=8080
CLOUD_PORT=8100
POSTGRES_PORT=5432

# CORS (comma-separated origins)
CORS_ORIGINS=http://localhost:8080,http://your-domain.com
```

### Camera Configuration

```bash
# YOLO Cloud Core
YOLO_MODEL=yolov8s-pose.pt          # yolov8s-pose.pt (fast) or yolov8x-pose.pt (accurate)
YOLO_DEVICE=cpu                      # cpu or cuda (GPU)
YOLO_CONFIDENCE=0.5
INFERENCE_FPS=10                     # Frames per second to process

# RTSP Streams
RTSP_TRANSPORT=tcp                   # tcp or udp
RTSP_TIMEOUT=5                       # Seconds before reconnection
RTSP_RECONNECT_DELAY=2.0            # Seconds between reconnection attempts
```

### Notification Configuration

```bash
# Email (SMTP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password
SMTP_FROM=alerts@ergovigilance.com
ALERT_RECIPIENTS=safety@factory.com,mgr@factory.com

# Slack
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T.../B.../...
```

---

## Camera Setup

### Supported Camera Types

1. **USB Webcams** — Plug-and-play, works with on-premise MediaPipe engine
2. **IP Cameras (RTSP)** — Works with YOLO cloud core
3. **CCTV Systems** — RTSP-enabled DVR/NVR output

### RTSP Stream URLs

Common formats:

```
# Hikvision
rtsp://username:password@192.168.1.100:554/Streaming/Channels/101

# Dahua
rtsp://username:password@192.168.1.100:554/cam/realmonitor?channel=1&subtype=0

# Axis
rtsp://username:password@192.168.1.100/axis-media/media.amp

# Generic
rtsp://username:password@IP:PORT/path
```

### Camera Placement Guidelines

1. **Height**: Mount cameras 2.5-3.5 meters high, angled 15-30° downward
2. **Coverage**: Each camera covers one workstation (3m × 3m area)
3. **Lighting**: Ensure adequate lighting (500+ lux) — avoid backlighting
4. **Visibility**: Worker's full body must be visible (head to knees minimum)
5. **Stability**: Use vibration-resistant mounts near machinery

### Testing RTSP Streams

```bash
# Test with ffplay
ffplay rtsp://username:password@192.168.1.100:554/stream

# Test with the cloud core
curl -X POST http://localhost:8100/api/cameras \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"name": "Test Camera", "rtsp_url": "rtsp://..."}'
```

---

## Network Configuration

### Firewall Rules

```bash
# Frontend (public)
ufw allow 80/tcp
ufw allow 443/tcp

# Backend API (internal only)
ufw allow from 192.168.1.0/24 to any port 8000

# Cloud Core (internal only)
ufw allow from 192.168.1.0/24 to any port 8100

# RTSP cameras (internal only)
ufw allow from 192.168.1.0/24 to any port 554
```

### Bandwidth Requirements

| Stream Type | Resolution | FPS | Bandwidth |
|-------------|------------|-----|-----------|
| MJPEG | 640×480 | 10 | 2-4 Mbps |
| H.264 | 1920×1080 | 15 | 4-8 Mbps |
| H.265 | 1920×1080 | 15 | 2-4 Mbps |

---

## Security Hardening

### Production Checklist

- [ ] Set `DEBUG=false`
- [ ] Generate strong `AUTH_JWT_SECRET` (64+ chars)
- [ ] Change all default passwords
- [ ] Enable HTTPS with valid TLS certificate
- [ ] Configure firewall rules
- [ ] Set up log rotation
- [ ] Enable database backups
- [ ] Review CORS origins
- [ ] Enable rate limiting
- [ ] Set up monitoring alerts

### HTTPS Configuration

```bash
# Generate self-signed certificate (testing only)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/ssl/private/ergovigilance.key \
  -out /etc/ssl/certs/ergovigilance.crt

# Or use Let's Encrypt (production)
certbot --nginx -d ergovigilance.yourdomain.com
```

---

## Backup & Restore

### Database Backup

```bash
# PostgreSQL
pg_dump -U ergovigilance ergovigilance > backup_$(date +%Y%m%d).sql

# SQLite
cp backend_api/local_auth.db backups/local_auth_$(date +%Y%m%d).db
```

### Session Data Backup

```bash
# Backup session files
tar -czf sessions_$(date +%Y%m%d).tar.gz outputs/sessions/

# Backup recordings
tar -czf recordings_$(date +%Y%m%d).tar.gz recordings/
```

### Automated Backup (cron)

```bash
# Add to crontab
0 2 * * * /path/to/backup_script.sh >> /var/log/ergovigilance_backup.log 2>&1
```

### Restore

```bash
# Restore PostgreSQL
psql -U ergovigilance ergovigilance < backup_20260901.sql

# Restore sessions
tar -xzf sessions_20260901.tar.gz -C /
```

---

## Monitoring & Health Checks

### Service Health Endpoints

```bash
# Backend API
curl http://localhost:8000/healthz

# Cloud Core
curl http://localhost:8100/healthz

# System Health Dashboard
# Navigate to http://localhost:8080/system-health
```

### Docker Health Checks

```bash
# Check container status
docker compose ps

# View logs
docker compose logs -f backend
docker compose logs -f cloud-core

# Restart a service
docker compose restart backend
```

### Prometheus Metrics

```bash
# Metrics endpoint — token-gated when METRICS_TOKEN is set (and always
# refused when DEBUG=false with no token; health probes stay open)
curl -H "Authorization: Bearer $METRICS_TOKEN" http://localhost:8000/metrics

# Metrics include:
# - Request count and latency
# - Active sessions
# - Alert counts
# - Model inference time
```

---

## Troubleshooting

### Common Issues

#### 1. "Camera disconnected" error

**Cause**: RTSP stream timeout or network issue

**Fix**:
```bash
# Test camera connectivity
ping 192.168.1.100
ffplay rtsp://user:pass@192.168.1.100:554/stream

# Check RTSP credentials in .env
# Increase RTSP_TIMEOUT if network is slow
```

#### 2. "Pose detection failed" error

**Cause**: Worker not visible in frame, lighting too dark

**Fix**:
```bash
# Check camera placement (2.5-3.5m height, 15-30° angle)
# Ensure adequate lighting (500+ lux)
# Test with: python scripts/live_demo.py
```

#### 3. "Database connection refused"

**Cause**: PostgreSQL not running or wrong credentials

**Fix**:
```bash
# Check PostgreSQL status
docker compose ps db

# Verify credentials in .env
# Test connection: psql -U ergovigilance -h localhost ergovigilance
```

#### 4. "Out of memory" during inference

**Cause**: Too many cameras or high resolution

**Fix**:
```bash
# Reduce INFERENCE_FPS in .env
# Use yolov8s-pose.pt instead of yolov8x-pose.pt
# Increase RAM or reduce camera count
```

#### 5. "CORS error" in browser

**Cause**: Frontend origin not in CORS_ORIGINS

**Fix**:
```bash
# Add frontend URL to CORS_ORIGINS in .env
CORS_ORIGINS=http://localhost:8080,http://192.168.1.50:8080
# Restart backend
```

---

## Hardware Recommendations

### Single Camera Setup (~$500)

- **Mini PC**: Intel NUC or similar
- **CPU**: Intel i5-12400 (6 cores)
- **RAM**: 16 GB
- **Storage**: 256 GB SSD
- **Camera**: Hikvision DS-2CD2043G2-I (4MP, PoE)

### Multi-Camera Setup (~$2,000)

- **Server**: Dell PowerEdge T350 or HP ProLiant ML30
- **CPU**: Intel Xeon E-2300 series (8 cores)
- **RAM**: 32 GB
- **Storage**: 1 TB NVMe SSD
- **GPU**: NVIDIA RTX 3060 (for YOLO cloud core)
- **Cameras**: 4-8x PoE IP cameras

### Enterprise Setup (~$10,000+)

- **Server**: Dell PowerEdge R750 or similar rack server
- **CPU**: 2x Intel Xeon Silver (32+ cores)
- **RAM**: 64-128 GB
- **Storage**: 4 TB NVMe RAID
- **GPU**: NVIDIA A100 or RTX 4090
- **Cameras**: 20+ PoE IP cameras with NVR

---

## Support

- **Documentation**: https://docs.ergovigilance.com
- **Email**: support@ergovigilance.com
- **Slack**: https://ergovigilance.slack.com

---

**Generated with Codebuff**  
**ErgoVigilance v1.0.0**
