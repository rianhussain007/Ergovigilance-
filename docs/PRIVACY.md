# ErgoVigilance — Privacy & Data Handling

This document describes what data ErgoVigilance captures, where it lives, who
can access it, and how it is deleted. It is written for operators who deploy
the platform and for the workers whose posture is monitored.

> **Headline:** the platform is offline-first. By default **no captured data
> leaves the machine** — no cloud uploads, no telemetry, no third-party
> analytics. The AI Assistant runs against a **local** Ollama instance.

---

## 1. What data is collected

| Data | Where it comes from | Where it is stored |
|---|---|---|
| **Live video frames** | Webcam while a monitoring session is active | Processed in memory; **not persisted** during live monitoring |
| **Skeleton keypoints** (33 body landmarks per frame) | MediaPipe pose estimation | Derived features only — raw keypoints are not stored for live sessions |
| **Posture/ergonomic features** (neck/trunk flexion, shoulder elevation, knee angle, …) | Feature extraction | In-memory live state; session summary JSONs under `outputs/sessions/` |
| **Session summaries** (risk percentages, avg angles, duration) | End-of-session analytics | `outputs/sessions/session_*.json` |
| **Recorded sessions** (video + frame timeline + summary) | Explicit **record** action during a session | `recordings/<worker>/<session>/` |
| **Worker profiles** (name, employee ID, department, shift) | Admin-entered seed data / workers admin | Local SQLite (`backend_api/local_auth.db`) |
| **Alerts & audit log** | Alert engine, login/session events | Local SQLite |
| **Login attempts** | Auth endpoint | Local SQLite (pruned after 24 h) |
| **AI Assistant prompts** | User chat in the UI | Sent to the **local** Ollama endpoint only |

## 2. What leaves the machine

**Nothing by default.** There is no cloud dependency:

- No telemetry, analytics, or crash reporting is built in.
- The AI Assistant queries `OLLAMA_HOST` (default `http://localhost:11434`) —
  a **local** LLM server. Pointing `OLLAMA_HOST` at a remote host would send
  assistant prompts (and any worker context included in them) to that host;
  keep it local.
- PDF/CSV/JSON reports are generated locally (Playwright headless Chromium).
- If you deploy the Docker stack on a reachable network, traffic **is**
  transmitted over the network — terminate it with TLS (see the README's TLS
  section) and restrict access with the firewall.

## 3. Retention & deletion

- **Session summaries** are deleted after `SESSION_RETENTION_DAYS` (default 30).
- **Recorded sessions** are deleted after `RECORDING_RETENTION_DAYS` (default 30)
  and the recordings tree is capped at `RECORDINGS_MAX_GB` (default 20 GB,
  oldest evicted first). A background task enforces this every
  `RETENTION_INTERVAL_HOURS` (default 6 h) and on startup.
- **Per-worker deletion (right-to-erasure):** admins can call
  `POST /api/privacy/delete-worker-data/{worker_id}` to remove a worker's
  recordings directory and alert history immediately. This is audit-logged as
  `worker_data_deleted`.
- **Login attempt rows** are pruned after 24 h.
- **Known limitation:** `outputs/sessions/session_*.json` summaries are **not
  attributed to a worker** (they store no worker_id), so a per-worker wipe
  cannot remove them individually — they fall under the age-based policy.

## 4. Access control

- All APIs require a JWT. Roles (`operator`, `supervisor`, `safety_mgr`,
  `admin`) are enforced **server-side**; unauthorized access returns 403.
- Only `admin` can trigger retention runs, view retention stats, and delete
  worker data.
- The audit log records logins, lockouts, session lifecycle events, and data
  deletions — review it periodically (`GET /api/audit`).

## 5. Operational recommendations (the responsible part)

ErgoVigilance monitors people. Before rolling out in a workplace:

1. **Notice & consent** — post clear signage that camera-based posture
   monitoring is active, what is recorded, how long it is kept, and who can
   see it. Where required, obtain consent and a works-council/union agreement.
2. **Minimize recording** — record sessions only when evidence is genuinely
   needed; live monitoring alone stores no video.
3. **Restrict access** — keep admin accounts minimal; monitor the audit log.
4. **Keep it local & isolated** — do not expose the API port publicly
   (loopback-only by default in docker-compose); terminate TLS at the proxy.
5. **Data protection impact assessment** — posture monitoring is sensitive
   (ergonomic/health-adjacent data). Consult your DPO/legal team and the local
   privacy regulator; this document is engineering guidance, not legal advice.
6. **Backups** — back up the SQLite DB (`local_auth.db`) and decide a
   retention-aligned backup window so backups don't outlive the policy.
7. **Erase on request** — honor worker deletion requests via the per-worker
   wipe endpoint within the window your jurisdiction requires.

## 6. Data protection principles mapped

| Principle | How ErgoVigilance addresses it |
|---|---|
| Data minimization | Keypoints are processed to features; raw frames are not persisted in live mode |
| Storage limitation | Retention policy (age + disk cap) enforced by a background task |
| Integrity & confidentiality | Local storage, bcrypt/JWT auth, RBAC, loopback-only API port |
| Accountability | Audit log for auth, lockout, session, and deletion events |
| Right to erasure | `POST /api/privacy/delete-worker-data/{worker_id}` (admin) + retention |
| Transparency | This document + README + in-app notices (recommended signage) |
