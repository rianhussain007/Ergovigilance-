# ErgoVigilance — YOLO Cloud Core

Cloud-based ergonomic monitoring service that processes RTSP CCTV camera
streams using YOLOv8-pose + ByteTrack worker tracking.

## Architecture

```
Factory IP Cameras (RTSP) → FFmpeg Ingestion → YOLOv8-pose → ByteTrack → Risk Engine → Dashboard
```

### How It Differs from MediaPipe Core

| Feature | MediaPipe Core (On-Premise) | YOLO Cloud Core |
|---------|----------------------------|-----------------|
| Runs on | Factory gateway PC | Cloud servers |
| Input | USB webcam / local video | RTSP CCTV streams |
| Pose keypoints | 33 (MediaPipe) | 17 (YOLOv8-pose) |
| Installation | Install app + gateway | **Just share RTSP URLs** |
| Scalability | 1-4 cameras per PC | **100+ cameras per cluster** |
| Price model | One-time + maintenance | **Monthly SaaS** |

### Revenue Model

| Tier | Cameras | Price |
|------|---------|-------|
| Starter | 1-3 | $99/camera/month |
| Professional | 4-10 | $79/camera/month |
| Enterprise | 10+ | $59/camera/month |

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Start with demo RTSP feeds
python -m yolo_cloud.main --demo

# Start with real cameras
export RTSP_CAMERAS='[{"id":"cam-1","name":"Assembly Line","url":"rtsp://192.168.1.100:554/stream"}]'
python -m yolo_cloud.main
```

## Endpoints

- `GET /cloud/health` — Service health
- `GET /cloud/cameras` — List configured cameras
- `POST /cloud/cameras` — Add camera (RTSP URL)
- `DELETE /cloud/cameras/{id}` — Remove camera
- `POST /cloud/cameras/{id}/start` — Start monitoring a camera
- `POST /cloud/cameras/{id}/stop` — Stop monitoring
- `GET /cloud/sessions` — Cloud session history
- `GET /cloud/sessions/{id}` — Session detail with timeline
- `GET /cloud/alerts` — Recent alerts across all cameras
- `GET /cloud/reports/daily` — Daily PDF report
- `GET /cloud/reports/export` — CSV export
- `GET /cloud/dashboard` — Aggregated dashboard data
