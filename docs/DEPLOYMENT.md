# ErgoVigilance — Factory Deployment Guide

**Version:** 1.0 · **Last updated:** September 2026

This guide walks factory IT teams through deploying ErgoVigilance — the dual-core ergonomic monitoring system with both on-premise (MediaPipe) and cloud (YOLO) capabilities.

---

## Table of Contents

1. [System Requirements](#1-system-requirements)
2. [Quick Start (Docker)](#2-quick-start-docker)
3. [Manual Installation](#3-manual-installation)
4. [Camera Configuration](#4-camera-configuration)
5. [Environment Variables](#5-environment-variables)
6. [Starting Services](#6-starting-services)
7. [SSL / HTTPS Setup](#7-ssl--https-setup)
8. [Firewall Rules](#8-firewall-rules)
9. [Monitoring & Health Checks](#9-monitoring--health-checks)
10. [Troubleshooting](#10-troubleshooting)
11. [Backup & Recovery](#11-backup--recovery)
12. [Always-On Factory Deployment](#12-always-on-factory-deployment-99-uptime)
13. [Uninstall](#13-uninstall)

---

## 1. System Requirements

### On-Premise Core (MediaPipe)
| Component | Minimum | Recommended |
|-----------|---------|-------------|
| OS | Windows 10/11 or Linux (Ubuntu 20.04+) | Windows 11 or Ubuntu 22.04 |
| CPU | 4 cores | 8 cores |
| RAM | 8 GB | 16 GB |
| GPU | Not required (CPU inference) | NVIDIA GTX 1060+ (faster) |
| Storage | 10 GB | 50 GB (for recordings) |
| Camera | USB webcam (720p+) | USB webcam (1080p) |

### Cloud Core (YOLO)
| Component | Minimum | Recommended |
|-----------|---------|-------------|
| OS | Any (Docker host) | Linux (Ubuntu 22.04) |
| CPU | 4 cores | 8 cores |
| RAM | 8 GB | 16 GB |
| GPU | Not required (CPU inference) | NVIDIA T4/A10 (20+ cameras) |
| Storage | 5 GB | 100 GB (for session data) |
| Network | 10 Mbps per camera | 50 Mbps per camera |

### Docker Requirements
- Docker Engine 20.10+ or Docker Desktop 4.0+
- Docker Compose v2.0+
- 4 GB free RAM for all services

---

## 2. Quick Start (Docker)

### Step 1: Clone the Repository
```bash
git clone <repository-url> ergovigilance
cd ergovigilance
```

### Step 2: Configure Environment
```bash
# Copy the production environment template
cp .env.production.example .env

# Edit with your settings
nano .env
```

**Minimum required changes in `.env`:**
```env
AUTH_JWT_SECRET=<generate-a-strong-secret>
POSTGRES_PASSWORD=<choose-a-strong-password>
```

Generate a strong JWT secret:
```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

### Step 3: Start All Services
```bash
docker compose up -d --build
```

This starts:
- **PostgreSQL** database (port 5432)
- **Backend API** (port 8000)
- **Frontend** (port 8080)
- **YOLO Cloud Core** (port 8100)

### Step 4: Verify
```bash
# Check all services are running
docker compose ps

# Test the health endpoint
curl http://localhost:8000/health

# Open the dashboard
# Browser: http://localhost:8080
```

### Step 5: Create Admin Account
```bash
# The first user to register becomes admin
# Or use the demo mode:
docker compose exec backend python -m app.utils.demo_seeding
```

---

## 3. Manual Installation

If Docker is not available, install each component manually.

### Backend API
```bash
cd backend_api
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

pip install -r requirements.txt

# Set environment variables
export AUTH_JWT_SECRET="your-secret-here"
export DATABASE_URL="sqlite:///./ergovigilance.db"

# Start the server
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Frontend
```bash
cd ui_posture
npm install

# Configure API endpoint
echo "VITE_API_URL=http://localhost:8000" > .env.local

# Build for production
npm run build

# Serve with nginx or any static server
# The built files are in dist/
```

### YOLO Cloud Core
```bash
cd yolo_cloud
pip install -r requirements.txt

# Start the cloud core
uvicorn api:create_app --factory --host 0.0.0.0 --port 8100
```

---

## 4. Camera Configuration

### On-Premise Core (USB Webcam)

1. Connect a USB webcam to the gateway PC
2. The camera is auto-detected (index 0 by default)
3. To use a specific camera, set in `.env`:
   ```env
   CAMERA_SOURCES=[{"id": "cam-01", "name": "Assembly Station", "source": 0}]
   ```

**Camera placement tips:**
- Mount 2-3 meters from the worker
- Angle: 15-30° above eye level
- Ensure full body is visible (head to knees minimum)
- Avoid backlighting (windows behind the worker)

### Cloud Core (RTSP CCTV)

1. Get the RTSP URL from your IP camera:
   ```
   rtsp://<username>:<password>@<camera-ip>:<port>/<stream>
   ```
   
   Common formats:
   - Hikvision: `rtsp://admin:password@192.168.1.100:554/Streaming/Channels/101`
   - Dahua: `rtsp://admin:password@192.168.1.100:554/cam/realmonitor?channel=1&subtype=0`
   - Axis: `rtsp://root:password@192.168.1.100/axis-media/media.amp`
   - Generic: `rtsp://admin:password@192.168.1.100:554/live`

2. Test the RTSP stream:
   ```bash
   ffplay rtsp://admin:password@192.168.1.100:554/live
   ```

3. Add cameras via the dashboard:
   - Go to **Cloud Cameras** → **Add Camera**
   - Enter Camera ID, Name, and RTSP URL
   - Click **Start** to begin monitoring

4. Or configure in `.env`:
   ```env
   RTSP_CAMERAS=[{"id": "cam-01", "name": "Line 1", "url": "rtsp://admin:pass@192.168.1.100:554/live"}]
   ```

### Camera Network Requirements
- Cameras must be on the same network as the cloud core server
- RTSP uses TCP port 554 (default) — ensure firewall allows this
- Bandwidth: ~5 Mbps per 1080p camera stream
- Latency: 200-500ms for cloud processing (acceptable for monitoring)

---

## 5. Environment Variables

### Required (must set before first run)

| Variable | Description | Example |
|----------|-------------|---------|
| `AUTH_JWT_SECRET` | Secret key for JWT tokens (64+ chars) | `openssl rand -base64 64` |
| `POSTGRES_PASSWORD` | Database password | `your-strong-password` |

### Optional (sensible defaults)

| Variable | Default | Description |
|----------|---------|-------------|
| `BACKEND_PORT` | 8000 | Backend API port |
| `FRONTEND_PORT` | 8080 | Frontend port |
| `POSTGRES_PORT` | 5432 | Database port |
| `CLOUD_PORT` | 8100 | YOLO Cloud Core port |
| `DEMO_MODE` | false | Enable demo mode with synthetic data |
| `YOLO_MODEL` | yolov8s-pose.pt | YOLO model to use |
| `YOLO_DEVICE` | cpu | Inference device (cpu/cuda) |
| `INFERENCE_FPS` | 10 | Frames per second to process |
| `RTSP_TRANSPORT` | tcp | RTSP transport protocol |
| `SESSION_IDLE_TIMEOUT` | 60 | Seconds before ending a session |
| `SMTP_HOST` | - | Email server for alerts |
| `SMTP_PORT` | 587 | Email server port |
| `SMTP_USER` | - | Email username |
| `SMTP_PASS` | - | Email password |
| `SLACK_WEBHOOK_URL` | - | Slack webhook for alerts |

---

## 6. Starting Services

### Docker (Recommended)
```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f

# Stop all services
docker compose down

# Restart a specific service
docker compose restart backend
```

### Windows Service (Manual Install)
```bash
# Install as Windows service
deploy\install-service.bat

# Start the service
net start ErgoVigilance

# Stop the service
net stop ErgoVigilance
```

### Systemd (Linux Manual Install)
```bash
# Create service file
sudo tee /etc/systemd/system/ergovigilance.service <<EOF
[Unit]
Description=ErgoVigilance Backend
After=network.target

[Service]
Type=simple
User=ergovigilance
WorkingDirectory=/opt/ergovigilance/backend_api
ExecStart=/opt/ergovigilance/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable ergovigilance
sudo systemctl start ergovigilance
```

---

## 7. SSL / HTTPS Setup

For production, always use HTTPS.

### Option 1: Nginx Reverse Proxy (Recommended)
```nginx
server {
    listen 443 ssl http2;
    server_name ergovigilance.yourfactory.com;

    ssl_certificate /etc/ssl/certs/ergovigilance.pem;
    ssl_certificate_key /etc/ssl/private/ergovigilance.key;

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /cloud-api/ {
        proxy_pass http://localhost:8100/api/;
        proxy_set_header Host $host;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### Option 2: Let's Encrypt
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d ergovigilance.yourfactory.com
```

---

## 8. Firewall Rules

### Required Ports

| Port | Protocol | Service | Direction |
|------|----------|---------|-----------|
| 8080 | TCP | Frontend | Inbound |
| 8000 | TCP | Backend API | Inbound |
| 8100 | TCP | YOLO Cloud Core | Inbound |
| 5432 | TCP | PostgreSQL | Internal only |
| 554 | TCP | RTSP cameras | From cameras |

### UFW (Linux)
```bash
sudo ufw allow 8080/tcp  # Frontend
sudo ufw allow 8000/tcp  # Backend
sudo ufw allow 8100/tcp  # Cloud Core
sudo ufw deny 5432/tcp   # Block external DB access
sudo ufw enable
```

### Windows Firewall
```powershell
New-NetFirewallRule -DisplayName "ErgoVigilance Frontend" -Direction Inbound -Port 8080 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "ErgoVigilance Backend" -Direction Inbound -Port 8000 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "ErgoVigilance Cloud" -Direction Inbound -Port 8100 -Protocol TCP -Action Allow
```

---

## 9. Monitoring & Health Checks

### Health Endpoints
```bash
# Backend health
curl http://localhost:8000/health
# → {"status": "healthy", "version": "0.1.0", "model_available": true}

# Cloud Core health
curl http://localhost:8100/api/cloud/health
# → {"status": "healthy", "model": "yolov8s-pose.pt", "cameras": 0}
```

### Docker Monitoring
```bash
# View resource usage
docker stats

# Check logs for errors
docker compose logs --tail=100 backend | grep -i error
docker compose logs --tail=100 cloud-core | grep -i error
```

### Log Files
- Backend logs: `docker compose logs backend`
- Cloud core logs: `docker compose logs cloud-core`
- Application logs: `outputs/logs/`
- Session data: `outputs/sessions/`

---

## 10. Troubleshooting

### Common Issues

#### "Port already in use"
```bash
# Find what's using the port
netstat -ano | findstr :8000
# Kill the process or change the port in .env
```

#### "Database connection refused"
```bash
# Check if PostgreSQL is running
docker compose ps db
# Restart the database
docker compose restart db
```

#### "Camera not detected"
```bash
# Check camera connection
ls /dev/video*  # Linux
# Or check Device Manager on Windows

# Test with ffplay
ffplay /dev/video0  # Linux
ffplay -f dshow -i video="Camera Name"  # Windows
```

#### "RTSP stream not connecting"
```bash
# Test the RTSP URL
ffplay rtsp://admin:password@192.168.1.100:554/live

# Common issues:
# 1. Wrong credentials
# 2. Camera on different subnet
# 3. Firewall blocking port 554
# 4. Camera doesn't support RTSP
```

#### "Model not loaded"
```bash
# Check if model files exist
ls models/yolo_*.pkl

# If missing, retrain:
python -m yolo_cloud.training.build_yolo_features
python -m yolo_cloud.training.train_yolo_risk_model
python -m yolo_cloud.training.train_yolo_task_model
```

#### "High CPU usage"
```bash
# Reduce inference FPS in .env
INFERENCE_FPS=5

# Or use a smaller YOLO model
YOLO_MODEL=yolov8n-pose.pt
```

#### "WebSocket disconnects"
```bash
# Check nginx proxy timeout
proxy_read_timeout 3600s;
proxy_send_timeout 3600s;
```

---

## 11. Backup & Recovery

### Database Backup
```bash
# Backup
docker compose exec db pg_dump -U postgres ergovigilance > backup.sql

# Restore
docker compose exec -T db psql -U postgres ergovigilance < backup.sql
```

### Session Data Backup
```bash
# Backup sessions
tar -czf sessions_backup_$(date +%Y%m%d).tar.gz outputs/sessions/

# Backup models
tar -czf models_backup_$(date +%Y%m%d).tar.gz models/
```

### Full Backup Script
```bash
#!/bin/bash
BACKUP_DIR="/backups/ergovigilance/$(date +%Y%m%d_%H%M%S)"
mkdir -p $BACKUP_DIR

# Database
docker compose exec -T db pg_dump -U postgres ergovigilance > $BACKUP_DIR/database.sql

# Sessions
cp -r outputs/sessions/ $BACKUP_DIR/sessions/

# Models
cp -r models/ $BACKUP_DIR/models/

# Configuration
cp .env $BACKUP_DIR/env

echo "Backup complete: $BACKUP_DIR"
```

---

## 12. Always-On Factory Deployment (99% Uptime)

For factories that need 24/7 monitoring with 99% uptime, follow this guide.

### Hardware Requirements for Always-On Operation

| Component | Small Factory (1-5 cameras) | Medium Factory (5-20 cameras) | Large Factory (20+ cameras) |
|-----------|----------------------------|-------------------------------|-----------------------------|
| **Server** | Desktop PC or mini PC | 1U Rack Server | 2U Rack Server or Cloud |
| **CPU** | Intel i5 / AMD Ryzen 5 (4C/8T) | Intel Xeon / AMD EPYC (8C/16T) | 2x Intel Xeon (16C/32T) |
| **RAM** | 16 GB DDR4 | 32 GB DDR4 ECC | 64 GB DDR4 ECC |
| **GPU** | Not required | NVIDIA T4 (16GB) for YOLO | NVIDIA A10 (24GB) for batch |
| **Storage** | 256 GB SSD | 1 TB NVMe SSD | 2 TB NVMe SSD + HDD backup |
| **Network** | 1 Gbps Ethernet | 1 Gbps redundant | 10 Gbps bonded |
| **UPS** | 30-minute battery backup | 1-hour UPS | 2-hour UPS + generator |
| **OS** | Windows 11 Pro or Ubuntu 22.04 | Ubuntu 22.04 LTS Server | Ubuntu 22.04 LTS Server |
| **Estimated Cost** | $800-1,200 | $3,000-5,000 | $8,000-15,000 |

### Why 99% Uptime Matters

- **1% downtime = 3.65 days/year** of no monitoring
- **Each unprotected hour** = risk of undetected injury + potential OSHA violation
- **ROI impact**: A single prevented injury ($42K avg) covers the UPS cost

### Keeping Services Alive

ErgoVigilance includes a built-in **Keep-Alive Monitor** (`ops/keep_alive.py`) that:

1. **Checks health** every 10 seconds via HTTP
2. **Auto-restarts** crashed services within 15 seconds
3. **Logs all events** to `logs/keep_alive/`
4. **Persists status** to `logs/keep_alive/status.json` for external monitoring

#### Start the Monitor

```bash
# Windows (background)
python ops/keep_alive.py

# Linux (daemon)
nohup python ops/keep_alive.py &

# Or use the all-in-one startup script (Windows)
ops/start_services.bat
```

#### Run as a Windows Service

```bash
# Install NSSM (Non-Sucking Service Manager)
nssm install ErgoVigilanceMonitor "C:\Python312\python.exe" "C:\ergovigilance\ops\keep_alive.py"
nssm set ErgoVigilanceMonitor AppDirectory "C:\ergovigilance"
nssm set ErgoVigilanceMonitor Start SERVICE_AUTO_START
nssm start ErgoVigilanceMonitor
```

#### Run as a Linux Systemd Service

Create `/etc/systemd/system/ergovigilance-monitor.service`:
```ini
[Unit]
Description=ErgoVigilance Keep-Alive Monitor
After=network.target

[Service]
Type=simple
User=ergovigilance
WorkingDirectory=/opt/ergovigilance
ExecStart=/usr/bin/python3 ops/keep_alive.py --interval 10
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable ergovigilance-monitor
sudo systemctl start ergovigilance-monitor
```

### UPS (Uninterruptible Power Supply) Requirements

| Scenario | UPS Size | Runtime | Notes |
|----------|----------|---------|-------|
| Desktop + 3 cameras | 500VA / 300W | 30 min | Enough for graceful shutdown |
| Server + 10 cameras | 1500VA / 1000W | 1 hour | Auto-shutdown script included |
| Rack server + 20+ | 3000VA / 2000W | 2 hours | Generator recommended |

**Auto-shutdown on low battery:**
```bash
# Linux — add to /etc/udev/rules.d/99-ups-monitor.rules
SUBSYSTEM=="power_supply", ATTR{status}=="Discharging", ATTR{capacity}=="15", RUN+="/opt/ergovigilance/ops/shutdown.sh"
```

### Network Requirements for CCTV Integration

| Camera Type | Bandwidth per Camera | Protocol | Ports to Open |
|-------------|---------------------|----------|---------------|
| USB Webcam | N/A (local) | Direct | None |
| IP Camera (H.264) | 2-4 Mbps | RTSP | 554, 8554 |
| IP Camera (H.265) | 1-2 Mbps | RTSP | 554, 8554 |
| NVR (multi-camera) | 4-8 Mbps total | RTSP | 554, 8554 |
| Cloud (YOLO core) | 5-10 Mbps per stream | RTSP over VPN | 8100, 8554 |

**Recommended network setup:**
- Dedicated VLAN for cameras (isolated from office network)
- QoS rules prioritizing camera streams
- Firewall: only allow RTSP (554) from camera VLAN to server

### Monitoring & Alerting

The keep-alive status file (`logs/keep_alive/status.json`) can be integrated with:

- **Prometheus + Grafana** — scrape the JSON or add `/metrics` endpoint
- **Nagios / Zabbix** — check `/health` endpoint
- **Email alerts** — configure `SMTP_*` env vars for automatic notifications
- **Slack alerts** — configure `SLACK_WEBHOOK_URL` env var

---

## 13. Uninstall

### Docker
```bash
# Stop and remove all containers
docker compose down -v

# Remove images
docker compose down --rmi all

# Remove data (optional)
rm -rf outputs/ data/ models/
```

### Windows Service
```bash
deploy\uninstall-service.bat
```

### Linux Systemd
```bash
sudo systemctl stop ergovigilance
sudo systemctl disable ergovigilance
sudo rm /etc/systemd/system/ergovigilance.service
sudo rm -rf /opt/ergovigilance
```

---

## Support

- **Documentation:** `/docs/` directory
- **API Reference:** `/api-docs` (when running)
- **Issues:** Contact your ErgoVigilance representative

---

*Generated with Codebuff 🤖*
