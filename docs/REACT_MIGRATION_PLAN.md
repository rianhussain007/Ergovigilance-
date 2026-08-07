# React Migration Plan — Industrial Ergonomics Monitoring System

> **Historical note (2026-08):** this plan predates the pivot and references
> pre-pivot files that have since been removed (`frontend/app.py`,
> `streamlit_app.py`, `backend/main.py`). The React migration it describes is
> complete — the product is now `ui_posture/` + `backend_api/` + `backend/`
> (see `README.md` and `ROADMAP.md`).

---

## Section 1: Current Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Single Process                      │
│                                                      │
│  streamlit_app.py                                    │
│       │                                              │
│  frontend/app.py  (Streamlit UI)                     │
│       │                                              │
│  ┌────┴────────────────────┐                         │
│  │  backend/services/      │  ← direct Python calls  │
│  │  ├── pose.py            │    (no HTTP)            │
│  │  ├── features.py        │                         │
│  │  └── best_model.pkl     │                         │
│  └─────────────────────────┘                         │
│                                                      │
│  results/  ← flat JSON files (no database)           │
│                                                      │
│  backend/main.py  ← FastAPI (unused by frontend)     │
└─────────────────────────────────────────────────────┘
```

### What exists today

| Layer | Technology | State |
|---|---|---|
| UI | Streamlit (Python) | 4 tabs, 807 lines, procedural |
| API | FastAPI | 2 endpoints (`/health`, `/predict`), NOT called by UI |
| Pose Engine | MediaPipe | Python `pose.py` — landmark detection |
| Feature Extraction | Python `features.py` | 7 biomechanical features + rule-based risk |
| ML Model | Random Forest (`best_model.pkl`) | 97.97% accuracy, 3 classes |
| Storage | Flat JSON files in `results/` | No database, no query layer |
| Session State | Local Python variables | No persistence across runs |

### Key limitation
The Streamlit frontend imports and calls `backend/services/*` **in-process**. The FastAPI server (`backend/main.py`) is a separate entry point that the frontend never uses over HTTP. This means:

- Cannot separate frontend from backend
- No REST API contract for external consumers
- No database — history is file-system scan only
- No real-time streaming protocol (WebSocket) for live monitoring
- No multi-user or multi-worker support

---

## Section 2: Target Architecture

```
┌──────────────────────────────────────────────┐
│              React SPA                        │
│  ┌──────────┬──────────┬──────────────────┐  │
│  │Dashboard │Monitoring│ Image Analysis   │  │
│  ├──────────┼──────────┼──────────────────┤  │
│  │Video Rev │Analytics │ Workers / Tasks  │  │
│  └──────────┴──────────┴──────────────────┘  │
│         │                                     │
│      HTTP/REST + WebSocket                    │
└─────────┼─────────────────────────────────────┘
          │
┌─────────▼─────────────────────────────────────┐
│           FastAPI Backend                      │
│                                                 │
│  /predict/*    ← image/video analysis          │
│  /sessions/*   ← live monitoring CRUD          │
│  /history/*    ← saved results with filters    │
│  /analytics/*  ← aggregated statistics         │
│  /ws/*         ← WebSocket for live frames     │
│  /reports/*    ← PDF generation                │
│                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │pose.py   │  │features  │  │best_model.pkl│  │
│  │(MediaPipe)│  │.py       │  │(RandomForest)│  │
│  └──────────┘  └──────────┘  └──────────────┘  │
└─────────────────────┬───────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────┐
│              Database (SQLite → PostgreSQL)      │
│                                                 │
│  results         sessions        session_frames │
│  users           daily_aggregates               │
└─────────────────────────────────────────────────┘
```

### Principle
- Frontend is a pure SPA — never imports Python code
- Backend is the single source of truth — REST + WebSocket
- Database replaces flat-file storage
- React communicates only via HTTP/WS — no Python in the browser

---

## Section 3: Page Breakdown

### 3.1 Dashboard (`/dashboard`)

Live overview of the system state.

| Element | Description |
|---|---|
| Live risk gauge | Current overall risk level (LOW/MEDIUM/HIGH) with posture score |
| Active workers | List of workers currently being monitored |
| Recent alerts | Last 5 HIGH-risk events with timestamps |
| Today's stats | Scans today, avg score, risk distribution |
| Quick actions | "New Scan", "View History", "View Analytics" |

### 3.2 Monitoring (`/monitor`)

Real-time webcam monitoring with live feedback.

| Element | Description |
|---|---|
| Camera feed | Live webcam stream with pose skeleton overlay |
| Risk indicator | Real-time badge + posture score updating every frame |
| Session timer | Elapsed time, frames analyzed |
| Live stats | LOW/MEDIUM/HIGH percentages updating in real time |
| Detected issues | Current posture issues (head forward, shoulder raised, etc.) |
| Controls | Start/stop, camera select, duration slider |
| Session summary | Appears after stop — risk distribution chart, avg score, duration |
| Save button | Persists session to history |

### 3.3 Image Analysis (`/analyze/image`)

Single-image posture analysis.

| Element | Description |
|---|---|
| Image upload | Drag-and-drop or file picker (jpg/png/bmp) |
| Preview | Before/after with skeleton overlay toggle |
| Result card | Risk badge + posture score side by side |
| Feature breakdown | Per-feature gauge bars with color coding |
| Detected issues | List of flagged areas with icons |
| Feedback panel | Expandable detailed feedback per body area |
| Recommendations | Actionable + long-term recommendation cards |
| Actions | Download PDF, save to history, share |

### 3.4 Video Review (`/analyze/video`)

Full video upload and frame-by-frame analysis.

| Element | Description |
|---|---|
| Video upload | Drag-and-drop (mp4/avi/mov) |
| Video player | Native player with scrub bar |
| Analyze button | Triggers backend frame extraction |
| Progress bar | Real-time analysis progress |
| Risk timeline | Line chart of risk score over time |
| Risk distribution | Bar/pie chart of LOW/MEDIUM/HIGH percentages |
| Worst frame | Card with annotated image + features at worst moment |
| Best frame | Card with annotated image + features at best moment |
| Average posture | Overall average score across all frames |
| Detected issues | Issues from average features |
| Actions | Download video assessment PDF, save |

### 3.5 Analytics (`/analytics`)

Historical data aggregation and trend visualization.

| Element | Description |
|---|---|
| Date range picker | Filter by custom date range |
| Daily trend line | Average posture score over days |
| Risk distribution | Stacked bar chart per day (LOW/MEDIUM/HIGH) |
| Scan volume | Bar chart: scans per day |
| Aggregated metrics | Total scans, active days, avg score, current streak |
| Per-feature trends | Line charts for each of 7 features over time |
| Export | Download analytics as CSV/PDF |

### 3.6 Workers (`/workers`)

Multi-worker tracking (for factory/office deployments).

| Element | Description |
|---|---|
| Worker list | Table of workers with name, ID, last scan, avg score |
| Worker detail | Individual worker's history, trend, recommendations |
| Add worker | Form (name, ID, workstation) |
| Worker groups | Filter/group by team, shift, workstation |
| Comparison | Side-by-side worker risk comparison |

### 3.7 Task Recognition (`/tasks`)

Recognize specific work tasks and correlate with posture risk.

| Element | Description |
|---|---|
| Task list | Predefined tasks (sitting, standing, lifting, typing) |
| Active task | Current detected task from pose data |
| Task-risk correlation | Chart showing which tasks produce highest risk |
| Task timeline | Timeline colored by task type |
| Task configuration | Define new tasks by pose thresholds |

*Note: Task recognition requires new backend logic — pose data exists but no task classifier.*

---

## Section 4: Per-Page Requirements

### 4.1 Dashboard

**Components required:**
- `RiskGauge` — circular gauge component (LOW/MEDIUM/HIGH colored)
- `WorkerChip` — compact worker avatar + name + status
- `AlertCard` — timestamp + risk level + thumbnail
- `StatCard` — metric value + label + trend arrow
- `MiniChart` — small sparkline (last 7 days)

**Data sources:**
- `GET /analytics/today` — today's aggregate stats
- `GET /analytics/recent-alerts?limit=5` — recent HIGH events
- `GET /workers/active` — currently monitored workers
- `GET /analytics/daily?days=7` — 7-day sparkline data

**Existing backend APIs:**
- `GET /health` — only relevant endpoint

**Missing APIs:**
- `GET /analytics/today` → `{scans, avg_score, risk_distribution, active_workers}`
- `GET /analytics/recent-alerts?limit=N` → `[{timestamp, risk_level, thumbnail_url, worker_id}]`
- `GET /workers/active` → `[{id, name, current_risk, since}]`
- `GET /analytics/daily?days=7` → `[{date, avg_score, scan_count}]`

---

### 4.2 Monitoring

**Components required:**
- `WebcamFeed` — live video stream with overlay canvas
- `SkeletonOverlay` — CSS/Canvas drawn pose skeleton
- `RiskBadge` — colored badge with animated transitions
- `PostureScoreRing` — SVG circular progress (0-100)
- `LiveStatsBar` — horizontal bar showing LOW/MED/HIGH %
- `IssueList` — icon + text list of current detected issues
- `SessionTimer` — MM:SS elapsed counter
- `SessionSummary` — modal with results, chart, metrics
- `CameraSelector` — dropdown for camera index

**Data sources:**
- WebSocket stream for real-time frames
- `POST /sessions` — create session
- `POST /sessions/{id}/frame` — submit frame, get risk
- `GET /sessions/{id}/summary` — aggregated session stats
- `GET /sessions/{id}/frames?page=N` — paginated frame history

**Existing backend APIs:**
- None — live camera is entirely client-side in Streamlit

**Missing APIs:**
- `POST /sessions` → `{session_id, started_at}`
- `POST /sessions/{id}/frame` → `{risk_level, confidence, features, keypoints, annotated_image_b64}`
- `WebSocket /ws/monitor/{session_id}` → continuous frame submission + result streaming
- `GET /sessions/{id}` → session metadata
- `GET /sessions/{id}/summary` → `{total_frames, low_pct, med_pct, high_pct, avg_score, duration}`
- `GET /sessions/{id}/frames?page=N&per_page=M` → paginated frame records
- `DELETE /sessions/{id}` — discard session

**Camera frame capture:**
- Must be done in browser via `getUserMedia()` API
- Frames sent to backend as base64 JPEG or binary blob
- Backend runs pose detection + classification, returns result
- WebSocket eliminates HTTP overhead per frame

---

### 4.3 Image Analysis

**Components required:**
- `ImageDropzone` — drag-and-drop upload with preview
- `ImagePreview` — before/after toggle with skeleton overlay
- `ResultCard` — badge + score + confidence
- `FeatureGauge` — horizontal bar for each feature with LOW/MED/HIGH coloring
- `IssueCard` — issue area + icon + description text
- `FeedbackPanel` — expandable per-area text feedback
- `RecommendationCard` — actionable + long-term recs
- `ActionBar` — download PDF, save, new scan buttons

**Data sources:**
- `POST /predict` — submit image, get results

**Existing backend APIs:**
- `POST /predict` — returns `{risk_level, confidence, features, unavailable_features}`

**Missing APIs:**
- `POST /predict` needs enhancement to also return:
  - `annotated_image_url` or base64 annotated image
  - `breakdown` per-feature risk levels
  - `feedback` array of per-area text
  - `recommendations` actionable + long-term arrays
  - `posture_score` (0-100)
- `GET /results/{id}` — retrieve saved result by ID
- `POST /results` — save a completed analysis to history

---

### 4.4 Video Review

**Components required:**
- `VideoDropzone` — drag-and-drop video upload
- `VideoPlayer` — native player with custom controls
- `ProgressBar` — animated analysis progress
- `RiskTimeline` — interactive line chart (risk score vs time)
- `RiskDistributionChart` — bar or pie chart
- `FrameCard` — annotated frame thumbnail + risk badge
- `TimelineScrubber` — clickable timeline to jump to frame
- `SummaryPanel` — aggregated metrics, avg score, issues

**Data sources:**
- `POST /predict/video` — upload video, trigger analysis
- `GET /predict/video/{id}` — poll for analysis status
- `WebSocket /ws/video/{id}` — real-time frame results

**Existing backend APIs:**
- None — video is processed entirely in-process by Streamlit

**Missing APIs:**
- `POST /predict/video` → `{video_id, status, total_frames, estimated_time}`
- Accepts video file upload (mp4/avi/mov), returns immediately with video_id
- Backend processes asynchronously (background task)
- `GET /predict/video/{id}` → `{status, progress, frames_analyzed, total_frames}`
- `GET /predict/video/{id}/results` → full results with all frame records
- `GET /predict/video/{id}/frames?page=N` → paginated frame details
- `WebSocket /ws/video/{id}/progress` → push progress updates + individual frame results
- `POST /results` — save video analysis to history

---

### 4.5 Analytics

**Components required:**
- `DateRangePicker` — calendar-based date selection
- `TrendChart` — multi-series line chart (daily avg score)
- `StackedBarChart` — daily LOW/MED/HIGH distribution
- `ScanVolumeChart` — daily scan count
- `SummaryCards` — total scans, active days, avg score, streak
- `FeatureTrendChart` — 7 line charts (one per feature)
- `ExportButton` — CSV/PDF export trigger

**Data sources:**
- `GET /analytics/overview?from=...&to=...` — all aggregated stats
- `GET /analytics/daily?from=...&to=...` — per-day breakdowns
- `GET /analytics/features?from=...&to=...` — per-feature trends

**Existing backend APIs:**
- None — history is computed client-side from flat JSON files

**Missing APIs:**
- `GET /analytics/overview?from=DATE&to=DATE` → `{total_scans, active_days, avg_score, current_streak, risk_distribution}`
- `GET /analytics/daily?from=DATE&to=DATE` → `[{date, avg_score, scan_count, low_pct, med_pct, high_pct}]`
- `GET /analytics/features?from=DATE&to=DATE` → `[{date, neck_flexion_avg, trunk_flexion_avg, ...}]`
- `GET /analytics/export?from=DATE&to=DATE&format=csv` → CSV download

---

### 4.6 Workers

**Components required:**
- `WorkerTable` — sortable, filterable data table
- `WorkerCard` — compact detail view
- `WorkerForm` — create/edit worker form
- `GroupSelector` — filter by team/shift/workstation
- `ComparisonChart` — side-by-side risk comparison
- `WorkerTrend` — individual worker's score over time

**Data sources:**
- `GET /workers` — list all workers
- `GET /workers/{id}` — single worker detail
- `GET /workers/{id}/history` — worker's scan history
- `GET /workers/{id}/trend` — worker's score trend
- `POST /workers` — create worker
- `PUT /workers/{id}` — update worker
- `DELETE /workers/{id}` — remove worker

**Existing backend APIs:**
- None — workers concept does not exist yet

**Missing APIs:**
- All of the above — this is new functionality requiring:
  - New `workers` database table
  - CRUD endpoints
  - Linking `results` table to `workers` via foreign key
  - Adding `worker_id` to scan metadata

---

### 4.7 Task Recognition

**Components required:**
- `TaskList` — table of defined tasks with thresholds
- `TaskBadge` — current detected task indicator
- `TaskRiskChart` — bar chart: risk level per task type
- `TaskTimeline` — timeline colored by active task
- `TaskForm` — create/edit task definition

**Data sources:**
- `GET /tasks` — list defined tasks
- `POST /tasks` — create task definition
- `GET /tasks/{id}/correlation` — risk correlation for a task
- `POST /predict/task` — detect task from pose data

**Existing backend APIs:**
- None — task recognition does not exist at any layer

**Missing APIs:**
- All of the above — this requires:
  - New `tasks` database table (name, pose thresholds, description)
  - New `task_classifier` module (rule-based or ML)
  - New `task_results` table for per-frame task labels
  - `POST /predict/task` → `{task_id, task_name, confidence}`
  - `GET /tasks/{id}/correlation` → `{low_pct, med_pct, high_pct}`

---

## Section 5: Migration Strategy

### Phase 1: Replace Streamlit UI Only

**Goal:** Functional parity — React frontend does everything Streamlit does.

**Duration:** 4-6 weeks

**Tasks:**

| # | Task | Effort |
|---|---|---|
| 1.1 | Set up React project with Vite, TypeScript, Tailwind CSS | Small |
| 1.2 | Set up React Router (pages: Dashboard, Monitor, Image, Video, History/Analytics) | Small |
| 1.3 | Build shared component library (Button, Card, Badge, Modal, Chart wrappers, Spinner) | Medium |
| 1.4 | Enhance FastAPI backend — add missing CRUD endpoints for results | Medium |
| 1.5 | Enhance `/predict` to return annotated image + feedback + recommendations + score | Small |
| 1.6 | Build Dashboard page — gauge, recent scans, quick actions | Medium |
| 1.7 | Build Image Analysis page — upload, preview, results, PDF download | Medium |
| 1.8 | Build Video Analysis page — upload, progress, timeline, results | Large |
| 1.9 | Build History/Analytics page — daily trends, distribution charts | Medium |
| 1.10 | Add SQLite database, migrate flat-file storage to DB | Medium |
| 1.11 | Add CORS middleware to FastAPI | Small |
| 1.12 | Replace PDF generation to run server-side (reportlab or similar) | Medium |
| 1.13 | Integrate FastAPI background tasks for video processing | Medium |
| 1.14 | E2E testing — verify parity with Streamlit output for same inputs | Medium |

**Deliverable:** React SPA that matches all Streamlit functionality. Streamlit can be retired.

---

### Phase 2: Live Monitoring + Real-Time

**Goal:** Real-time WebSocket-based live monitoring with session tracking.

**Duration:** 3-4 weeks

**Tasks:**

| # | Task | Effort |
|---|---|---|
| 2.1 | Add WebSocket support to FastAPI (via `fastapi.WebSocket`) | Medium |
| 2.2 | Build `/ws/monitor/{session_id}` — continuous frame submission stream | Large |
| 2.3 | Add sessions CRUD + database tables | Medium |
| 2.4 | Build browser camera capture (`getUserMedia()` with frame extraction) | Medium |
| 2.5 | Build SkeletonOverlay — Canvas-based pose skeleton rendered from keypoints | Large |
| 2.6 | Build Monitoring page — live feed, real-time stats, controls | Large |
| 2.7 | Build SessionSummary component — post-session modal with charts | Medium |
| 2.8 | Implement session save to history | Small |

**Deliverable:** Real-time monitoring page with live skeleton overlay, frame-by-frame risk updates, and session summaries saved to database.

---

### Phase 3: Workers + Tasks + Enterprise

**Goal:** Multi-worker support, task recognition, advanced analytics.

**Duration:** 4-5 weeks

**Tasks:**

| # | Task | Effort |
|---|---|---|
| 3.1 | Add `workers` database table + CRUD endpoints | Medium |
| 3.2 | Link `results` and `sessions` to `workers` | Medium |
| 3.3 | Build Workers page — list, detail, trends | Medium |
| 3.4 | Build task classifier module (rule-based from pose features) | Large |
| 3.5 | Add `tasks` database table + CRUD endpoints | Medium |
| 3.6 | Build Task Recognition page — task list, correlation charts | Large |
| 3.7 | Add user authentication (JWT-based, simple roles) | Large |
| 3.8 | Add role-based access control (admin, viewer, operator) | Medium |
| 3.9 | Build Analytics page with full date range, feature trends, CSV export | Large |
| 3.10 | Add filtered search API for history (by date, risk level, worker, task) | Medium |
| 3.11 | Migrate from SQLite to PostgreSQL (optional, if scale requires) | Medium |
| 3.12 | Performance optimization: image caching, query optimization, CDN for results | Medium |

**Deliverable:** Full enterprise-grade application with multi-worker management, task correlation, authentication, and comprehensive analytics.

---

## Section 6: Effort Estimate

### Size Definitions

| Size | Person-Days | Description |
|---|---|---|
| **Small** | 1-2 days | Single component, simple API endpoint, straightforward change |
| **Medium** | 3-5 days | Multiple related components, new page section, API + DB work |
| **Large** | 5-10 days | Complex new feature, real-time streaming, significant new functionality |

### Phase Totals

| Phase | Small | Medium | Large | Est. Person-Days |
|---|---|---|---|---|
| Phase 1: UI Replacement | 3 | 9 | 2 | ~50 |
| Phase 2: Live Monitoring | 1 | 4 | 3 | ~40 |
| Phase 3: Enterprise Features | 0 | 8 | 3 | ~55 |
| **Total** | **4** | **21** | **8** | **~145** |

### Calendar Estimate

| Staffing | Phase 1 | Phase 2 | Phase 3 | Total |
|---|---|---|---|---|
| 1 developer | 10 weeks | 8 weeks | 11 weeks | 29 weeks |
| 2 developers | 5 weeks | 4 weeks | 6 weeks | 15 weeks |

---

## Section 7: Can a Single Frontend Developer Complete This?

**Yes, but with caveats.**

### What a single frontend developer would need to know:

1. **React + TypeScript** (core)
2. **Tailwind CSS** (styling)
3. **Chart.js or Recharts** (charts)
4. **Canvas API** (skeleton overlay on video)
5. **WebSocket API** (live monitoring)
6. **React Router** (routing)
7. **Python** (modifying FastAPI backend)
8. **SQL** (SQLite schema, queries for analytics)
9. **MediaPipe basics** (understanding pose output format)
10. **Git** (version control)

### Key risks for a solo developer:

| Risk | Mitigation |
|---|---|
| No Python experience → backend changes slow | Backend already exists; Phase 1 requires only endpoint additions, not ML changes |
| Canvas skeleton overlay is complex | MediaPipe keypoints are well-documented; reference Streamlit's `annotate_pose` logic |
| Real-time WebSocket performance | Start with HTTP polling for Phase 1; WebSocket in Phase 2 |
| Video processing is heavy | FastAPI background tasks already pattern; use Celery later if needed |
| Scope creep | Stick to Phase 1 first; don't start Phase 2-3 until Phase 1 is deployed |

### Recommended approach for a solo developer:

1. **Week 1-2:** React project scaffold, shared components, enhance FastAPI backend
2. **Week 3-4:** Image Analysis page (simplest tab, high confidence)
3. **Week 5-6:** History/Analytics page (read-only, good patterns for charts)
4. **Week 7-8:** Video Analysis page (harder — progress bar, async)
5. **Week 9-10:** Dashboard (glue page), polish, deploy
6. Then decide: real-time monitoring (Phase 2) or workers/analytics (Phase 3)

### Recommendation

**Hire or contract a second developer** with Python/backend experience for Phase 1. The frontend developer focuses on React; the backend developer adds API endpoints and database logic. This cuts Phase 1 from 10 weeks to 5 weeks and reduces integration risk.

If only one developer is available, **budget 12 weeks** for Phase 1 (including learning curve for Python backend work) and **do not start Phase 2 until Phase 1 is deployed and stable**.

---

## Appendix: Backend Enhancement Summary

### New Endpoints Required (Total: ~20)

```
POST   /predict                    (enhance existing)
POST   /predict/video              (new)
GET    /predict/video/{id}         (new)
GET    /predict/video/{id}/results (new)

POST   /sessions                   (new)
GET    /sessions/{id}              (new)
POST   /sessions/{id}/frame        (new)
GET    /sessions/{id}/summary      (new)
GET    /sessions/{id}/frames       (new)
DELETE /sessions/{id}              (new)
WS     /ws/monitor/{session_id}    (new)

POST   /results                    (new)
GET    /results                    (new)
GET    /results/{id}               (new)

GET    /analytics/overview         (new)
GET    /analytics/daily            (new)
GET    /analytics/features         (new)
GET    /analytics/export           (new)

GET    /workers                    (new)
POST   /workers                    (new)
GET    /workers/{id}               (new)
PUT    /workers/{id}               (new)
DELETE /workers/{id}               (new)
GET    /workers/{id}/history       (new)

GET    /tasks                      (new)
POST   /tasks                      (new)
GET    /tasks/{id}/correlation     (new)
POST   /predict/task               (new)
```

### Database Tables Required

```
results
├── id (UUID, PK)
├── worker_id (FK → workers, nullable)
├── source_filename
├── timestamp
├── risk_level
├── confidence
├── features (JSON)
├── annotated_image_path
├── created_at

sessions
├── id (UUID, PK)
├── worker_id (FK → workers, nullable)
├── camera_index
├── total_frames
├── started_at
├── ended_at
├── summary (JSON)

session_frames
├── id (UUID, PK)
├── session_id (FK → sessions)
├── frame_index
├── timestamp
├── risk_level
├── confidence
├── features (JSON)
├── keypoints (JSON, optional)

workers
├── id (UUID, PK)
├── name
├── employee_id
├── workstation
├── team
├── created_at

tasks
├── id (UUID, PK)
├── name
├── thresholds (JSON)
├── description

task_results
├── id (UUID, PK)
├── session_id or result_id
├── frame_index
├── task_id (FK → tasks)
├── confidence

daily_aggregates
├── id (UUID, PK)
├── date (DATE, unique)
├── total_scans
├── avg_score
├── risk_distribution (JSON)
```
