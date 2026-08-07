# Product FAQ

## General

**Q: What is ErgoVigilance?**
A: An AI-powered industrial ergonomics monitoring platform that uses a webcam to detect unsafe posture, track fatigue/exposure, generate alerts, and produce session reports.

**Q: How does posture detection work?**
A: MediaPipe PoseLandmarker extracts 33 body landmarks from each video frame. The system computes 7 biomechanical features (neck/trunk/shoulder angles, symmetry, alignment, knee angle) and classifies risk using threshold-based rules.

**Q: Does it use machine learning for risk scoring?**
A: No. Risk scoring is 100% deterministic threshold-based logic in the ContextIntelligenceEngine. An SVM/Random Forest model exists from the prototype but is NOT used in the live pipeline. ML-based scoring is deferred to a separate Research Track.

**Q: What hardware is required?**
A: A standard webcam. The system runs on a single Windows machine. No specialized hardware, wearables, or cloud infrastructure needed.

## Data & Privacy

**Q: Where is data stored?**
A: All data is local. Session summaries (JSON) go to `outputs/sessions/`. Video recordings go to `recordings/{worker_id}/{timestamp}/`. User/worker data is in local SQLite. No cloud dependency.

**Q: Are video recordings mandatory?**
A: No. Video recording is best-effort via a sidecar recorder. A video-write failure does not corrupt session data. Recording can be disabled.

**Q: Does the system identify workers by face?**
A: No. Worker identification uses explicit worker profiles, not face recognition. Face recognition is explicitly out of scope.

## Alerts

**Q: When are alerts triggered?**
A: Four rule types: HIGH risk posture, CRITICAL (escalated after 10 consecutive HIGH frames), RECOVERY (when posture returns to safe), and RAPID MOVEMENT (repetitive motion).

**Q: Are alerts persistent?**
A: No. Alerts are in-memory only and lost on backend restart. They are saved with session data when a session stops.

**Q: Can alerts be acknowledged?**
A: Yes. Supervisor, safety_mgr, and admin roles can acknowledge via PATCH `/api/alerts/{alert_id}/acknowledge`. Safety_mgr and admin can also resolve alerts.

**Q: How do I see my alerts?**
A: Click the **Alerts** button (Bell icon) in the top toolbar — it's visible on every page.

1. A slide-in panel opens from the right (the NotificationCenter).
2. The panel is divided into two sections:
   - **Active Alerts** — current, unresolved alerts that are firing right now.
   - **Past Alerts** — alerts that have been resolved or acknowledged.
3. Filter alerts by category using the pill buttons: **All**, **Critical**, **Warning**, **Info**, or **Resolved**.
4. Use the **Search** box to search by alert title or description.
5. Each alert shows: severity colour badge (Critical=red, Warning=orange, Info=blue, Resolved=green), title, description, and timestamp.
6. If you have the **Supervisor**, **Safety Mgr**, or **Admin** role, each active alert has action buttons:
   - **Acknowledge** (Eye icon) — marks the alert as seen.
   - **Resolve** (Shield icon) — resolves the alert (Safety Mgr and Admin only).
7. Click **"Mark all read"** at the top to dismiss the unread dot on all notifications.
8. The panel footer shows a summary: total alerts and critical count.
9. The backend polls for new alerts every 1 second, so the panel stays current without manual refresh.

## Roles & Permissions

**Q: What roles exist?**
A: Four roles: operator (self-view only), supervisor (can acknowledge alerts, view team), safety_mgr (can acknowledge and resolve alerts, full access), admin (full system control).

**Q: How is authentication handled?**
A: Local SQLite with bcrypt-hashed passwords and JWT tokens. No internet required. No SSO, no OAuth, no cloud auth.

## Sessions & History

**Q: How long can a session run?**
A: Designed for full 8-hour shifts. Tested up to 30 minutes continuously (~17,000 frames).

**Q: How is history stored?**
A: Tiered storage: full resolution for the most recent 300 seconds (5 minutes), then 10x downsampling. Maximum 50,000 snapshots (FIFO).

**Q: What happens if the backend crashes mid-session?**
A: All in-memory data is lost. Session data only saves on explicit `stop_session()` call. No periodic checkpoints.

**Q: How do I start a monitoring session?**
A: Use the controls in the top bar (always visible on every page):

1. Select a worker from the dropdown (shows worker name and employee ID).
2. Click **"Start Monitoring"** (green button with a Play icon). The button shows "Starting..." with a spinner while the session initialises.
3. Once active, the button becomes **"Stop Monitoring"** (red button with a Square icon) and a pulsing **"Live"** indicator appears.
4. To end the session, click **"Stop Monitoring"** (or **"Stop"** if the session stops automatically). The button reverts to "Start Monitoring".
5. Optionally toggle **"Demo"** to use a simulated camera feed (visible when not monitoring).

The session lifecycle (`GET /api/session/status`) is polled every 2 seconds to keep the UI in sync.

**Q: How do I view a past session?**
A: Go to the **Sessions** page (sidebar → _Sessions_ icon).

1. The page shows a table of past sessions with columns: Session ID, Date, Duration, Highest Risk, Task, and Status.
2. Use the **Search** bar to filter by session ID or task name.
3. Filter by status using the pill buttons: **All**, **Active**, **Completed**, or **Interrupted**.
4. Click **Asc / Desc** to toggle sort order.
5. Click any row — a **Drawer** slides in from the right showing full session details:
   - **Session Metadata**: timestamp, duration, total frames, highest risk level.
   - **Risk Breakdown**: horizontal bars for LOW, MEDIUM, and HIGH percentages.
   - **Average Feature Values**: neck flexion (°), trunk flexion (°), shoulder symmetry (%), knee angle (°).
   - **Most Frequent Issue** (if any).
   - **Alert Timeline**: each alert with severity badge, timestamp, frame number, trigger rule, confidence, and state.

**Q: How do I replay a recorded session?**
A: A session must have a recording and be in **completed** or **interrupted** status.

1. Go to the **Sessions** page (sidebar → _Sessions_).
2. Find a completed/interrupted session in the table.
3. Either:
   - Click **"Replay"** in the rightmost column of the table row, or
   - Click the row to open the detail Drawer, then click **"Open in Replay"**.
4. The browser navigates to `/replay/{sessionId}`.
5. The replay page shows:
   - **Video player** with standard controls (play/pause, seek, volume).
   - **Risk Timeline bar** — a colour-coded bar (green/orange/red) that you can click to seek to any point.
   - **Feature graph** — select any tracked feature (neck flexion, trunk flexion, shoulder elevation, etc.) to see its value over time. Click the graph to seek.
   - **Live Telemetry panel** — shows current risk level, risk score, confidence, context score, fatigue, exposure, task, and duration for the selected time position.
   - **Alert Timeline** — clickable alert entries that seek the video and data to the moment the alert fired.
6. If no recording exists, the page shows "No recording available for this session."

**Q: How do I generate / export a report?**
A: Reports are generated per session. Go to the **Reports** page (sidebar → _Reports_ icon).

1. The page shows two larger report cards at the top (Generate Risk Trend Report and Generate Safety Report — both are **coming soon**).
2. Below is the **Session Reports** section with a search bar.
3. Browse or search the list of session reports. Each shows a title, type (Safety/Session/Summary), date, and size.
4. Click a report row to open its detailed view. The detail page displays:
   - **Session Metadata**: session ID, date, duration, total frames, worker info.
   - **Risk Breakdown**: LOW/MEDIUM/HIGH percentages and the highest risk level.
   - **Average Ergonomic Features**: neck flexion, trunk flexion, shoulder symmetry, knee angle.
   - **Alert Timeline**: full list of alerts triggered during that session.
5. In the detail view, three export buttons are available at the top:
   - **Export CSV** — downloads a `session-report-{id}.csv` file with session fields and all alerts in tabular format.
   - **Export JSON** — downloads a `session-report-{id}.json` file containing the full session detail as structured JSON.
   - **Export PDF** — opens the browser Print dialog; choose "Save as PDF" to export a print-optimised version.

## AI Assistant (Phase L)

**Q: Is there an AI chatbot?**
A: Yes. Click the **AI Assistant** button (Brain icon) in the top toolbar to open the chat panel. It answers questions about ergonomic thresholds, alert rules, product features, and recommendations using a local LLM (llama3.2:3b) grounded in the knowledge corpus. It does not have access to personal session history or live data.

**Q: Will the AI modify alert or recommendation text?**
A: No. Alert and recommendation text remain deterministic (hardcoded) for safety. The AI Assistant is strictly a Q&A tool and on-demand guidance generator.

## Technical

**Q: Why two backend directories?**
A: `backend/` is the AI core (engines, features, pose). `backend_api/` is the FastAPI wrapper that exposes it over HTTP. This separation allows the AI core to be reused without a web server.

**Q: What ports are used?**
A: Backend API on port 8000. React frontend on port 3000 (proxies /api and /video to backend).

**Q: What is the expected FPS?**
A: ~13-15 FPS on typical hardware with a standard webcam.

**Q: How to start the system?**
A: Run `.\run_backend.bat` for the API server, `.\run_frontend.bat` for the Streamlit prototype, or `npm run dev` in `ui_posture/` for the React dashboard.
