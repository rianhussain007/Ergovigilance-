# Pilot Pre-Deployment Checklist

Run this before deploying at any pilot site. Every item is a yes/no with a
"where to record it" note — fill it in, then keep it in the intake tracker row.

## 1. Contact & consent (do FIRST — this gates everything)

- [ ] **Single point of contact on-site** identified — name + phone/WhatsApp:
      `________________________________`
- [ ] **Who else must be in the loop?** Plant manager / shift supervisor / union
      rep / works council — list them and their stance:
      `________________________________`
- [ ] **Worker notification done.** The person(s) who will be on camera have
      been told *what this is, why, and what happens to the video*. Use
      `WORKER_CONSENT_ONEPAGER.md` — hand it to them BEFORE the camera is set up.
- [ ] **No-surprise policy agreed:** monitoring runs only during agreed shifts;
      the camera is covered or the session is stopped outside those hours.
- [ ] **Question they must answer:** *"Are you OK with your workstation being
      monitored for 2 weeks for an ergonomics assessment?"* — record the answer.

## 2. Camera

- [ ] **Camera make/model/type:** `________________________________`
      (USB webcam, built-in laptop cam, or IP camera)
- [ ] If **USB**: it works on the deployment PC (`device manager` shows it).
- [ ] If **IP/RTSP**: the URL is reachable *from the deployment PC* (test with
      `VLC → open network stream`, or `ffprobe <url>`); credentials documented.
- [ ] **Mounting decided:** tripod / shelf / existing bracket; the worker's full
      torso + arms are in frame; backlighting is not blowing out the subject.
- [ ] **Camera is NOT pointed at other workers** (single-station framing) —
      or if unavoidable, those workers are covered by the same consent.

## 3. Network / firewall

- [ ] **Deployment PC is on the plant LAN** (not guest Wi-Fi).
- [ ] **Firewall:** inbound TCP **8000** allowed on the deployment PC for the
      LAN subnet only (ask IT if unsure; give them this doc).
- [ ] **No internet required** — confirm the site accepts that (it's a feature:
      video never leaves the building).
- [ ] **Static IP or reserved DHCP** for the deployment PC so the URL doesn't
      change mid-pilot. Record the IP: `________________`

## 4. Hardware / deployment PC

- [ ] Windows 10/11, x64, **8 GB RAM minimum** (16 GB preferred), a CPU from the
      last ~6 years (the pose model needs ~1 core).
- [ ] **No other heavy apps** running on it during shifts (the CV loop uses a
      full core).
- [ ] Space for recordings: ~**1–2 GB per monitored hour** (MP4); 30-day
      retention default.
- [ ] Optional: a small UPS so a power blip doesn't kill a shift's data.

## 5. Software (deployment-ready)

- [ ] `venv` + `backend_api/requirements.txt` installed.
- [ ] `playwright install chromium` done (PDF reports).
- [ ] `backend_api/.env` created from the production template with:
      `AUTH_JWT_SECRET` set (strong, ≥32 chars), `DEBUG=false`,
      `CORS_ORIGINS` correct, `CAMERA_SOURCES` if IP cameras.
- [ ] **Windows service installed** (`deploy/install_windows_service.ps1`) —
      or the manual start command documented as the fallback.
- [ ] `http://<pc-ip>:8000/health` returns ok **before** the pilot starts.
- [ ] Admin + supervisor logins created; worker record added for the monitored
      worker.

## 6. Day-one runbook (first shift)

- [ ] Camera framed + focused, worker consented (re-confirm day 1).
- [ ] Start a session; confirm: live feed renders, risk level moves, alerts
      fire on a deliberate bad posture (ask the worker to slouch for 5 s).
- [ ] Stop the session; confirm the report + MP4 appear.
- [ ] Agree with the on-site contact: **when** sessions run, **who** watches
      the dashboard, **how** you get feedback (WhatsApp / email / weekly call).
- [ ] Write down the worker's *questions* — they're your product feedback.

## 7. Rollback plan (if anything breaks mid-shift)

- [ ] **Immediate:** stop the session via the UI or `Restart-Service
      ErgoVigilance`. Data before the crash is already persisted (sessions are
      saved on stop; recordings stream to disk).
- [ ] **If the PC is unusable:** pull the camera off the mount and revert to
      normal work — nothing about the worker's job changes while the system is
      off. Have the contact's phone number to coordinate.
- [ ] **If the camera/feed fails:** the system logs the failure and keeps the
      UI alive; switch to a spare webcam if available, else pause the pilot day.
- [ ] **Rollback decision rule:** if the system is down > 30 min during a
      monitored shift, the on-site contact calls you; you decide together
      whether to continue that day.
- [ ] **Data stays on-site.** If the pilot ends early, recordings/sessions are
      deleted on request (right-to-erasure is built in — see retention policy).

## Sign-off

| Role | Name | Date |
|---|---|---|
| On-site contact | | |
| Founder / deployer | | |
| Worker(s) informed | | |
