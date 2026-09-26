# Local Dev Start — 3 processes (verified 2026-09-26)

Cloud pages (`/cloud-cameras`, `/cloud-settings`, `/model-dashboard`, …)
need the cloud core on :8100. There is no one-command starter; run three
terminals. Verified end-to-end this session (health 200, settings
GET/POST, probe, restart-applies).

## 0. Prereqs

Python 3.12+, Node 20+, `ffmpeg` + `ffprobe` on PATH (the RTSP probe
shells to ffprobe), network access (first cloud inference downloads the
YOLO weights, ~20 MB).

## 1. Backend API (:8000)

```powershell
cd C:\GGS_intership\posture_analysis
$env:AUTH_JWT_SECRET = python -c "import secrets; print(secrets.token_urlsafe(48))"
$env:DEBUG = "true"
cd backend_api
uvicorn app.main:app
```

`DEBUG=true` = dev mode (ephemeral JWT, open `/metrics`). Production
needs `DEBUG=false` + strong secret + `METRICS_TOKEN`
(`backend_api/.env.production.example`). No `.env` auto-loading exists —
export vars in each shell.

## 2. Cloud core (:8100)

```powershell
cd C:\GGS_intership\posture_analysis
$env:DEBUG = "true"
$env:AUTH_JWT_SECRET = "<same-or-any-48-char-secret>"
python -m uvicorn yolo_cloud.api:create_app --factory --host 127.0.0.1 --port 8100
```

Check: `curl.exe http://127.0.0.1:8100/api/cloud/health` → `healthy`.
Settings persist to `config/cloud_settings.json` (gitignored) and apply
on restart; env vars always win. First inference downloads
`yolov8s-pose.pt` — expect a one-time delay, not a failure.

## 3. Frontend (:3000)

```powershell
cd C:\GGS_intership\posture_analysis\ui_posture
npm run dev
```

Vite proxies `/api`, `/health*`, `/readyz`, `/video/`, `/ws` → :8000 and
`/cloud-api` → :8100 (rewritten to `/api/*`). Open
http://localhost:3000; System Health should show all four green.

## Notes

- Ports: backend 8000, cloud 8100, frontend 3000 must be free. A compose
  stack uses 8080/8001/5433 and global container names — stop it before
  local dev to avoid confusion (`docker compose ps`).
- Auth DB is per-shell CWD: run backend from `backend_api/` so it uses
  `backend_api/local_auth.db` (gitignored), same as tests expect.
- Boot artifacts (`backend_api/data/audit_hmac.key`) are gitignored.
