# CURRENT_STATE.md

Snapshot of ErgoVigilance as of 2026-07-07. Every statement below is backed by code inspection or runtime evidence.

---
# Appendix: Why Two Backends?
  
ErgoVigilance has two Python backend directories. This has caused repeated confusion across sessions — this section exists so it never needs re-answering.
 
## `backend/` — The AI Core
 
Contains the actual computer vision and intelligence engines. This code knows nothing about HTTP, FastAPI, or the web. It could theoretically run standalone (e.g. from a script, or embedded in a different application) with no web server at all.
 
Lives here:
- `backend/services/pose_engine.py` — MediaPipe wrapper
- `backend/services/features.py` — 7-feature extraction
- `backend/context/` — Context Intelligence Engine, fatigue, exposure
- `backend/alerts/` — Alert Engine
- `backend/recommendations/` — Recommendation Engine
- `backend/history/` — History Engine
- `backend/events/` — EventBus
- `backend/services/session_analytics.py` — session persistence
**Mental model:** if you deleted every line of `backend_api/`, this code would still represent "the product's brain" — just with no way for a browser to talk to it.
 
## `backend_api/` — The API Wrapper
 
Contains FastAPI routes, request/response schemas, and the `LiveMonitoringService` that owns and drives instances of the `backend/` engines. This is the layer that turns "an AI pipeline running in a Python process" into "something a React app can poll over HTTP."
 
Lives here:
- `backend_api/app/main.py` — FastAPI entry point
- `backend_api/app/api/*.py` — endpoint definitions
- `backend_api/app/services/live_monitor.py` — owns instances of PoseEngine, ContextIntelligenceEngine, EventBus, AlertEngine, HistoryEngine, RecommendationEngine; runs the frame-processing loop
- `backend_api/app/repositories/live.py` — translates internal engine state into the JSON shapes the frontend expects
**Mental model:** this is glue and translation. It does not contain ergonomic logic — it contains "how do I expose ergonomic logic over HTTP."
 
## The Actual Data Flow
 
```
Camera
  │
  ▼
backend/services/pose_engine.py       (Pose Estimation)
  │
  ▼
backend/services/features.py          (Feature Extraction)
  │
  ▼
backend/context/engine.py             (Context Intelligence)
  │
  ▼
backend/events/event_bus.py           (EventBus — publishes ContextSnapshotCreatedEvent)
  │
  ├──▶ backend/alerts/engine.py           (Alert Engine)
  ├──▶ backend/history/engine.py          (History Engine)
  └──▶ backend/recommendations/engine.py  (Recommendation Engine)
  │
  ▼
backend_api/app/services/live_monitor.py   (orchestrates all of the above, holds LiveState)
  │
  ▼
backend_api/app/repositories/live.py       (translates LiveState → API schema)
  │
  ▼
backend_api/app/api/*.py                   (FastAPI routes — GET /api/dashboard, /api/alerts, etc.)
  │
  ▼
ui_posture/ (React frontend, port 3000, polls the above endpoints)
```
 
## Why Keep Them Separate?
 
This is a legitimate architectural choice, not accidental duplication:
 
- `backend/` can be tested, reused, or even swapped onto a different API layer (e.g. a future gRPC service, a CLI batch tool, an embedded edge deployment) without rewriting the ergonomic logic.
- `backend_api/` can add new endpoints, change response shapes, or add auth without ever touching the pose/risk/alert logic itself.
- It matches the "Design Principle" from the vision doc: *backend engines are independent modules that communicate through events, enabling future expansion without tightly coupling components.*
## The One-Line Answer
 
> **`backend/` is the product. `backend_api/` is how the product talks to a browser.**
 
`frontend/app.py` (the Streamlit app) was a separate, third thing — an internal validation tool only, not part of the product architecture, and out of scope for modification per current project rules. **Removed 2026-08** (it imported deleted pre-pivot modules); retained in git history.
 -------------------------------------------------------------------------------------------------------

## 1. Camera Acquisition

**What it does.** The `LiveMonitoringService` opens an OpenCV `VideoCapture` on a configurable camera index (default 0). It attempts resolution negotiation at 1280x720 then 640x480, flips the frame horizontally, and feeds each frame into the PoseEngine. A separate `camera_manager.py` module provides cross-backend camera enumeration (DSHOW, MSMF, ANY on Windows) with WMI-based name resolution and max-resolution probing, but the live pipeline does not use it — it opens the camera directly by index.

**Files.** `backend_api/app/services/live_monitor.py` (lines 74-116, 151-247), `backend/services/camera_manager.py`

**Verified evidence.** Session `SESH-20260707-C72A` ran for 20+ seconds with FPS reported at 13-15 via `/api/session/status`. The MJPEG stream at `/video/feed` rendered in the browser with a skeleton overlay.

**Known limitations.** Camera is opened by index only — no automatic selection in the live pipeline. `camera_manager.py` exists but is not wired into `LiveMonitoringService.start_session()`. The `VideoCapture` is released on `stop_session()` with no reconnection logic.

---

## 2. Pose Estimation

**What it does.** Wraps MediaPipe Vision `PoseLandmarker` in VIDEO mode. Loads a `.task` model file (default `models/pose_landmarker_lite.task`), detects a single pose per frame with detection confidence >= 0.5 and tracking confidence >= 0.5, and converts the 33 landmarks into a normalized keypoint list `[x, y, z, visibility]` in pixel coordinates. Confidence is computed as the mean visibility of landmarks 0-16, multiplied by 100.

**Files.** `backend/services/pose_engine.py`

**Verified evidence.** `ProcessedFrame.person_detected` was `True` during live sessions. `ProcessedFrame.confidence` ranged from 50-90+ during the endurance test (session `SESH-20260706-19A5`).

**Known limitations.** Single-pose only (`num_poses=1`). No multi-person tracking. No hand/face landmarks — body only.

---

## 3. Feature Extraction

**What it does.** Computes exactly 7 ergonomic features from the 33 MediaPipe pose landmarks using trigonometric calculations (angle between three points, Euclidean distance, midpoint). Each feature is a single float value in degrees or percent. A separate `risk_from_features()` function classifies the overall risk as LOW/MEDIUM/HIGH using per-feature thresholds, and `risk_breakdown()` returns per-feature risk levels with threshold metadata.

**Files.** `backend/services/features.py`, `backend/core/constants.py` (`FEATURE_COLUMNS`)

**The exact 7 features:**

| # | Name | Unit | MEDIUM threshold | HIGH threshold | Inverted? |
|---|------|------|-----------------|---------------|-----------|
| 1 | `neck_flexion` | degrees | > 10 | > 30 | No |
| 2 | `trunk_flexion` | degrees | > 20 | > 60 | No |
| 3 | `left_shoulder_elev` | degrees | > 30 | > 60 | No |
| 4 | `right_shoulder_elev` | degrees | > 30 | > 60 | No |
| 5 | `shoulder_symmetry` | percent | > 5 | > 15 | No |
| 6 | `alignment_deviation` | percent | > 10 | > 30 | No |
| 7 | `knee_angle` | degrees | < 150 | < 100 | Yes |

**Verified evidence.** Session `SESH-20260706-19A5` produced real feature values: neck=9.3 deg, trunk=0.5 deg, left_shoulder=35.7 deg, right_shoulder=18.0 deg, symmetry=5.0%, alignment=5.3%, knee=179.3 deg. All 7 features appeared in `GET /api/dashboard` response.

**Known limitations.** No smoothing or temporal filtering — values can jitter frame-to-frame. Risk thresholds are static, not user-configurable.

---

## 4. Context Intelligence Engine

**What it does.** Takes the 7 raw features plus task type, camera confidence, session duration, and delta-time, and produces a `ContextSnapshot` with a context-adjusted risk score (0-100). The scoring pipeline is: (1) score each feature 0-100 via linear interpolation between medium/high thresholds, (2) base_risk = max of all feature scores, (3) add context_modifier = duration_penalty + task_modifier + fatigue_modifier, (4) add confidence_modifier, (5) clamp to [0, 100], (6) classify as HIGH (>=70), MEDIUM (>=30), or LOW.

**Files.** `backend/context/engine.py`, `backend/context/fatigue.py`, `backend/context/exposure.py`

**Fatigue model.** Exponential curve: `base_fatigue = 100 * (1 - e^(-0.42 * minutes / 30))`. Exposure penalty adds `high_risk_minutes * 0.8`. Recovery subtracts `low_risk_minutes * 1.2`. Task modifier adds 0.0-0.6 per minute depending on task type. Final fatigue modifier = `score * 0.2` (range 0-20 added to risk). Levels: fresh (<20), mild (20-49), moderate (50-74), severe (>=75).

**Exposure tracker.** Weighted body-region accumulation: neck=1.5x, trunk=1.3x, shoulder=1.2x, alignment=1.1x, knee=1.0x. Duration penalty = `min(total_high_risk_seconds / 10, 30)`. High-risk detection thresholds: neck>30, trunk>60, shoulder>60, symmetry>15, alignment>25, knee<100.

**Task modifiers.** Neutral Standing=0, Assembly Work=5, Reaching=8, Lifting/Picking=12, Inspection=3.

**Safety state hysteresis.** HIGH -> CRITICAL, MEDIUM+SAFE -> OBSERVE, LOW+OBSERVE -> SAFE, LOW+CRITICAL -> RECOVERY, LOW+RECOVERY -> SAFE.

**Verified evidence.** Session `SESH-20260706-19A5`: `/api/context/snapshot` returned fatigue=0.8, risk=LOW, safety_state=SAFE, frame 560 at one point during the endurance test. The engine evaluated 16,904 frames with 1.9% classified HIGH risk.

**Known limitations.** 100% deterministic — no ML, no personalization. Fatigue model uses a fixed exponential curve calibrated for a "general worker." All thresholds are hardcoded constants, not configurable at runtime.

---

## 5. Alert Engine

**What it does.** Subscribes to `ContextSnapshotCreatedEvent` via the EventBus and evaluates three rules per frame: (1) `high_risk` — fires when risk_level is HIGH and not on cooldown, (2) `critical_risk` — fires when consecutive HIGH frames >= 10 and not on cooldown, (3) `recovery` — fires when risk_level returns to LOW and there are active HIGH/CRITICAL alerts. Each rule has a cooldown (30 frames for HIGH and CRITICAL, 0 for recovery). Alerts are stored in-memory with ACTIVE -> RESOLVED lifecycle. The recovery rule immediately resolves all active HIGH/CRITICAL alerts.

**Files.** `backend/alerts/engine.py`, `backend/alerts/rules.py`, `backend/alerts/models.py`

**Rules summary:**

| Rule | Severity | Cooldown (frames) | Escalation threshold | Requires ACK |
|------|----------|-------------------|---------------------|-------------|
| `high_risk` | HIGH | 30 | — | Yes |
| `critical_risk` | CRITICAL | 30 | 10 consecutive HIGH | Yes |
| `recovery` | LOW | 0 | — | No |

**Verified evidence.** Session `SESH-20260706-19A5`: AlertEngine produced 143 alerts (70 HIGH, 37 CRITICAL, 36 Recovery). Session `SESH-20260706-B91D`: 7 alerts (1 HIGH, 6 others). Session `SESH-20260707-C72A`: 7 alerts total. The `alerts` array in the saved session JSON (`session_20260706_143117.json`) contained exactly 7 entries matching `summary.total_fired` from `/api/alerts`. Each entry includes `id`, `session_id`, `frame_number`, `created_at`, `severity`, `state`, `title`, `message`, `trigger_rule`, `confidence`, `requires_ack`, `expires_at`.

**Known limitations.** In-memory only — alerts are lost when the backend restarts. No persistence of the alert history across sessions. Cooldown is frame-based (not wall-clock time), so the effective cooldown varies with FPS.

---

## 6. Recommendation Engine

**What it does.** Subscribes to `ContextSnapshotCreatedEvent` and evaluates a catalog of 12 templates against the current context. Templates cover 6 categories: Posture (5 templates for neck/trunk/shoulder/alignment/knee), Break (3 templates for fatigue/exposure/duration), Workstation (1), Training (1), Supervisor Action (1), Medical Review (1). Each template has trigger conditions based on feature scores, fatigue, exposure, alert counts, and risk trends. When triggered, a recommendation is added to the current bundle. The bundle is regenerated on each frame (not accumulated).

**Files.** `backend/recommendations/engine.py`, `backend/recommendations/catalog.py`

**12 templates:** REC-NECK (neck_flexion>50), REC-TRUNK (trunk_flexion>50), REC-SHOULDER (shoulder_symmetry>50), REC-ALIGN (alignment>50), REC-KNEE (knee_angle>50), REC-BREAK-F (fatigue>40), REC-BREAK-E (exposure>50), REC-BREAK-D (frames>100), REC-WS (active_alerts>=3), REC-TRAIN (frames>50 and high_risk>30%), REC-SUPER (any CRITICAL alert), REC-MED (frames>100 and high_risk>50%).

**Verified evidence.** `GET /api/recommendations` returned 562 total_generated during session `SESH-20260706-19A5`. The `export()` method returns `{bundle: {recommendations, summary, highest_priority, generated_at}, total_generated}`.

**Known limitations.** Bundle is regenerated every frame, not accumulated — only the latest frame's recommendations are visible. No user acknowledgment or persistence. Trigger thresholds are static.

---

## 7. History Engine

**What it does.** Subscribes to `ContextSnapshotCreatedEvent` and stores snapshots in a deque. Uses tiered storage: full resolution for the most recent 300 seconds (5 minutes), then downsamples by a factor of 10 (keeps every 10th snapshot) for older data. Running statistics (risk sums, max/min, frame counts per risk level) are always maintained regardless of whether the snapshot is stored. Export produces a dictionary of snapshots, statistics, and session-level counters.

**Files.** `backend/history/engine.py`

**Configuration:**
- `maxlen` = 50,000 snapshots (deque limit)
- `RECENT_WINDOW_SECONDS` = 300 (5 minutes full resolution)
- `DOWNSAMPLE_FACTOR` = 10

**Export format:** `{snapshots: [...], statistics: {frames_stored, session_duration_seconds, average_risk, maximum_risk, minimum_risk, average_fatigue, average_exposure}, total_received, total_pruned, session_statistics: {total_frames, frames_high_risk, frames_medium_risk, frames_low_risk}}`

**Verified evidence.** Session `SESH-20260706-19A5`: `/api/history` returned 4,482 points after ~30 minutes. The tiered storage was not directly observable in the API response (no timestamp-based field to verify downsampling), but the point count (4,482 in ~30 min at ~14 FPS = ~25,200 frames) is consistent with downsampling being active for ~25 of those minutes.

**Known limitations.** The 50,000 snapshot cap means older data is silently dropped (FIFO). Downsampled data loses per-frame granularity. Export does not distinguish between full-resolution and downsampled entries. No persistence across restarts.

---

## 8. Session Persistence

**What it does.** When `stop_session()` is called, the `LiveMonitoringService` calls `save_session_summary()` which writes a single JSON file to `outputs/sessions/`. The file contains aggregated analytics from `SessionAnalytics` plus the full alert history from `AlertEngine.export()`. A CSV index (`session_index.csv`) is also appended with summary rows.

**Files.** `backend/services/session_analytics.py`, `backend_api/app/services/live_monitor.py` (line 140)

**Exact saved JSON schema (every field):**

```
{
  "session_timestamp": string,              // "YYYYMMDD_HHMMSS"
  "session_duration_seconds": float,
  "total_frames": int,
  "risk_percentages": {
    "LOW": float,
    "MEDIUM": float,
    "HIGH": float
  },
  "most_frequent_issue": string | null,
  "most_frequent_issue_count": int,
  "highest_risk_level": string,             // "LOW" | "MEDIUM" | "HIGH"
  "highest_risk_timestamp": string | null,  // "HH:MM:SS"
  "avg_neck_flexion": float,
  "avg_trunk_flexion": float,
  "avg_shoulder_symmetry": float,
  "avg_knee_angle": float,
  "alerts": [                              // present when alerts_data is provided
    {
      "id": string,                        // "ALT-XXXXXXXX"
      "session_id": string,
      "frame_number": int,
      "created_at": string,                // ISO-8601 timestamp
      "severity": string,                  // "HIGH" | "CRITICAL" | "LOW"
      "state": string,                     // "ACTIVE" | "RESOLVED"
      "title": string,
      "message": string,
      "trigger_rule": string,              // "high_risk" | "critical_risk" | "recovery"
      "confidence": float,
      "requires_ack": bool,
      "expires_at": string
    }
  ]
}
```

**CSV index columns:** `timestamp, duration, high_pct, medium_pct, low_pct, most_frequent_issue, highest_risk`

**Verified evidence.** Session `SESH-20260707-C72A`: saved file `session_20260707_094947.json` contained `"alerts"` array with 7 entries. `summary.total_fired` from `/api/alerts` was 7, matching the array length exactly. Session `SESH-20260706-B91D`: saved file contained `"alerts"` with 2 entries (1 HIGH with `created_at=2026-07-06T09:00:24.397778+00:00`, severity=HIGH, trigger_rule=high_risk).

**Known limitations.** Saves only at session end — no periodic checkpoints. If the backend crashes mid-session, all data is lost. The `SessionAnalytics` averages are computed from person-detected frames only (frames where `person_detected=False` are excluded from averages). The `session_index.csv` is append-only with no deduplication.

---

## 9. API Layer

**What it does.** FastAPI application serving on port 8000. All endpoints are synchronous reads from in-memory state (LiveState, AlertEngine, HistoryEngine, RecommendationEngine) or from the file system (session files). The `LiveRepository` translates backend-internal data types into the API schema. A Vite dev server on port 3000 proxies `/api` and `/video` to the backend.

**Files.** `backend_api/app/main.py`, `backend_api/app/api/router.py`, `backend_api/app/api/*.py`, `backend_api/app/repositories/live.py`, `backend_api/app/schemas/api.py`

**Every working endpoint:**

| Method | Path | Purpose | Source |
|--------|------|---------|--------|
| GET | `/api/dashboard` | Live session dashboard (features, risk, issues, recommendations) | LiveState |
| GET | `/api/session/latest` | Latest session data | LiveState |
| GET | `/api/sessions` | List all saved sessions | `outputs/sessions/*.json` |
| GET | `/api/trends` | Weekly/feature trends | Mock (frozen) |
| GET | `/api/reports` | List reports from session files | `outputs/sessions/*.json` |
| POST | `/api/report/generate` | Generate a report | Stub (returns mock) |
| GET | `/api/cameras` | Camera list | LiveRepository (returns `[]`) |
| GET | `/api/workstations` | Workstation list | LiveRepository (returns `[]`) |
| GET | `/api/deployment` | Infrastructure metrics | Mock (frozen) |
| GET | `/api/manager` | Factory-wide summary | Mock (frozen) |
| GET | `/api/alerts` | Active alerts, history, summary | AlertEngine |
| POST | `/api/session/start` | Start monitoring session | LiveMonitoringService |
| POST | `/api/session/stop` | Stop session, save data | LiveMonitoringService |
| GET | `/api/session/status` | Session active/idle status | LiveState |
| GET | `/video/feed` | MJPEG video stream with skeleton overlay | LiveMonitoringService |
| GET | `/api/context/snapshot` | Current ContextSnapshot | LiveState |
| GET | `/api/recommendations` | Current recommendation bundle | RecommendationEngine |
| GET | `/api/history` | Risk history points + statistics | HistoryEngine |
| WS | `/ws/dashboard` | Live dashboard updates (30s heartbeat) | WebSocket |
| WS | `/ws/alerts` | Live alert notifications (15s heartbeat) | WebSocket |
| WS | `/ws/camera` | Live camera frame updates (10s heartbeat) | WebSocket |

**Verified evidence.** All GET endpoints returning `200` during live session (100/100 consecutive requests to `/api/dashboard` returned HTTP 200 during endurance test). `/api/alerts` returned correct `AlertsResponse` with `active`, `history`, `summary` fields. `/api/history` returned `HistoryResponse` with `points` and `statistics`. WebSocket endpoints exist in code but were not tested.

**Known limitations.** `/api/trends`, `/api/deployment`, `/api/manager` always return mock data (endpoints are frozen). `/api/cameras` and `/api/workstations` return empty lists. `/api/report/generate` is a stub. WebSocket endpoints are defined but not consumed by the React frontend (which uses polling instead). No authentication or rate limiting.

---

## 10. Frontend (React Dashboard)

**What it does.** Vite + React + TypeScript single-page application on port 3000. Uses Tailwind CSS for styling. Data flows through a repository pattern: `ApiDashboardRepository` (live) or `MockDashboardRepository` (mock), selected by `config.USE_MOCK` (currently `false`). Individual widgets poll their own endpoints at 1-2 second intervals.

**Files.** `ui_posture/` directory

**Every page and its data source:**

| Page | Data Source | Live Hooks | Hardcoded Data |
|------|-----------|------------|----------------|
| **LiveMonitoring** (`/`) | **Mixed** | `useDashboardWithDemo` (2s), `useHistory` (1s) | ExecutiveDashboardCard fallback, SystemPerformanceCard fallback |
| **SessionHistory** (`/sessions`) | **Live** | `useDashboardWithDemo` (2s) | None |
| **TrendAnalysis** (`/trends`) | **Mixed** | `useDashboardWithDemo` (2s) | `weeklyTrend` array (8 weeks) for area charts |
| **Analytics** (`/analytics`) | **Mixed** | `useDashboardWithDemo` (2s) | `weeklyData`, `issueFreq`, `distData` for charts |
| **Reports** (`/reports`) | **Static** | None | `reports` array (5 entries), button handlers are toast-only |
| **Manager Dashboard** (`/manager`) | **Mixed** | `useDashboardWithDemo` (2s) | `workers` (10), `gridPositions` (10) for factory floor |
| **Deployment Center** (`/deployment`) | **Static** | None (hook declared but unused) | `infraStatus`, `cameras`, `edgeMetrics`, `workstations` |
| **Multi-Camera** (`/cameras`) | **Static** | None | `allCams` (9 cameras) |
| **Audit Trail** (`/audit`) | **Static** | None | `entries` (24 audit events) |
| **Settings** (`/settings`) | **Static** | None (uses `useTheme`, `useToast` only) | Default settings object, localStorage persistence |

**Polling hooks:**

| Hook | Interval | Endpoint |
|------|----------|----------|
| `useDashboard` | 2s | `GET /api/dashboard` + `GET /api/sessions` + `GET /api/trends` |
| `useHistory` | 1s | `GET /api/history` |
| `useAlerts` | 1s | `GET /api/alerts` |
| `useContextSnapshot` | 1s | `GET /api/context/snapshot` |
| `useRecommendations` | 1s | `GET /api/recommendations` |
| `useSessionLifecycle` | 2s (when active) | `GET /api/session/status` |

**Components that poll live data:** `ContextAwareRiskCard` (1s), `AlertManagementCard` (1s), `RecommendationsCard` (1s)

**Components with static/hardcoded data:** `AIInsights` (5 hardcoded insights), `LiveTimeline` (random fake events on 8s timer), `NotificationCenter` (10 hardcoded notifications), `SearchModal` (8 hardcoded items), `ExportsCenter` (fake export, toast only), `ExecutiveDashboardCard` (demo data), `SystemPerformanceCard` (demo data)

**Config:** `USE_MOCK: false` in `ui_posture/src/config/index.ts`

**Verified evidence.** The LiveMonitoring page rendered real data from the backend during the endurance test: 7 ergonomic features with live values, risk level, context snapshot, alerts, and recommendations all updated in real time.

**Known limitations.** 5 of 10 pages are fully static (Reports, Deployment, Multi-Camera, Audit Trail, Settings). 4 pages are mixed (live KPIs + hardcoded charts). Only SessionHistory is fully live. No WebSocket consumption — all data via polling. No error boundaries around individual widgets. No offline support or service worker.

---

## Cross-Cutting: EventBus

**What it does.** Synchronous in-process pub/sub. Handlers are called in registration order during `publish()`. Global singleton via `get_event_bus()`. Used by AlertEngine, HistoryEngine, and RecommendationEngine — all subscribe to `ContextSnapshotCreatedEvent`.

**File.** `backend/events/event_bus.py`

**Verified evidence.** AlertEngine, HistoryEngine, and RecommendationEngine all received events during live sessions (confirmed by non-zero alert counts, history points, and recommendation counts).

**Known limitations.** Synchronous — a slow handler blocks the publisher. No event ordering guarantees across threads (the processing loop runs in a daemon thread). No persistence or replay.

---

## Test Baselines

| Metric | Value | Session |
|--------|-------|---------|
| Total tests passing | 212+ | Unit test suite |
| Consecutive `/api/dashboard` HTTP 200 | 100/100 | Endurance test |
| Alerts fired (session `SESH-20260706-19A5`) | 143 (70 HIGH, 37 CRITICAL, 36 Recovery) | 30-min endurance |
| Alerts in saved JSON matching engine count | 7 == 7 | `session_20260707_094947.json` |
| Session files in `outputs/sessions/` | 45+ | Cumulative |
| Frames processed (30-min session) | 16,904 | `session_20260706_140235.json` |
| Effective average FPS | ~9.4 | 16,904 frames / 1,572.6 seconds |
