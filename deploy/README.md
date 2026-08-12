# ErgoVigilance — Pilot Deployment (Windows Service)

This is the packaging that makes a pilot site deployable by a non-developer:
one PowerShell command installs the backend as a Windows service that starts at
boot, restarts if it crashes, and logs to disk. No terminal stays open, no
`uvicorn` prompt, nothing to babysit.

## What a pilot site needs (minimum)

- A Windows 10/11 PC (or a small office PC / refurbished mini-PC) on the plant
  LAN. It does **not** need internet access — the whole stack runs on-prem.
- One camera per monitored station. Either:
  - a **USB webcam** (auto-detected), or
  - an **IP/RTSP camera** — list it in `CAMERA_SOURCES` in
    `backend_api/.env` (see below).
- `Python 3.10+` installed **once** during setup (or ship the venv pre-built).

## Install (one time, ~10 minutes)

```powershell
# 0. (First machine only) Python 3.10+ from python.org — tick "Add to PATH".

# 1. From the repo root:
python -m venv venv
venv\Scripts\pip install -r backend_api\requirements.txt
venv\Scripts\python -m playwright install chromium

# 2. Create backend_api\.env from the production template
copy backend_api\.env.production.example backend_api\.env
#    then edit: AUTH_JWT_SECRET (REQUIRED — see the template), CORS_ORIGINS,
#    CAMERA_SOURCES for IP cameras.

# 3. Install + start the Windows service (elevated PowerShell):
powershell -ExecutionPolicy Bypass -File deploy\install_windows_service.ps1
```

Done. The API is now at:

- `http://localhost:8000` on the machine itself
- `http://<this-machine-ip>:8000` from any PC on the same LAN
  (find the IP with `ipconfig` — the plant's IT can reserve a static IP)

## RTSP / IP cameras

Add factory cameras to `backend_api/.env`:

```
CAMERA_SOURCES=[{"id":"dock-cam-1","name":"Loading Dock","url":"rtsp://user:pass@192.168.1.50:554/stream1"},{"id":"line-2","name":"Assembly Line 2","url":"rtsp://admin:admin@192.168.1.51:554/ch1"}]
```

- The `id` is what the UI sends back as the camera; the `url` is opened by
  OpenCV (any RTSP/RTMP/HTTP stream).
- Configured cameras appear in **Settings → Camera** and **Multi-Camera**.
- After changing `.env`, restart the service:
  `powershell -Command "Restart-Service ErgoVigilance"`

## Frontend (the UI)

The SPA is built separately. For a pilot you can either:

- **(Recommended)** serve the production build from the same box — run
  `npm run build` in `ui_posture/`, then serve `ui_posture/dist/` over the LAN
  with any static server (or wire the existing nginx config), or
- point each viewer's browser at the dev server during setup only.

The frontend talks to the API at the same origin via the Vite/nginx proxy, so
no CORS work is needed when both are on one machine.

## Service management

| Action | Command |
|---|---|
| Status | `Get-Service ErgoVigilance` |
| Restart | `Restart-Service ErgoVigilance` |
| Logs | `deploy\logs\service-stdout.log` / `service-stderr.log` |
| Uninstall | `powershell -ExecutionPolicy Bypass -File deploy\uninstall_windows_service.ps1` |

## Post-install smoke test

1. Open `http://localhost:8000/health` — expect `{"status":"ok",...}`.
2. Log in at the UI, **Settings → Camera** — pick the USB/IP camera.
3. Start a session — the live feed + overlay should render.
4. Stop it — the session report + MP4 appear in **Reports** and **Replay**.
5. Check `deploy\logs\` for errors if anything is missing.

## Security notes for the pilot

- The API binds `0.0.0.0:8000` so LAN PCs can reach it. Do **not** port-forward
  it to the internet — the offline-first design is the privacy story.
- `AUTH_JWT_SECRET` must be set to a strong random value (the template shows
  how to generate one); the API refuses to start without it in non-debug mode.
- Put the machine on the plant LAN, not the guest Wi-Fi.
