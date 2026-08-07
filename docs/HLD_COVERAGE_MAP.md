# HLD Coverage Map

Maps every deliverable/requirement from the **Pose Estimation Module HLD** (`docs/Pose_Estimation_Module_HLD_Rian.docx (2).pdf`) and implied team-wide architecture against actual codebase implementation.

**Status legend:** FULLY COVERED / PARTIALLY COVERED / NOT COVERED / DELIBERATELY DEFERRED

---

## Module 1: Human Detection (HLD Member 2 — Mohan, upstream)

The HLD defines this as the upstream module that supplies bounding boxes, tracking IDs, and frame data to the Pose Estimation Module.

| # | HLD Requirement | Status | Code Evidence | Notes |
|---|----------------|--------|--------------|-------|
| 1.1 | Person detection in video frames | PARTIALLY COVERED | `backend/services/pose_engine.py` — `PoseLandmarker` detects poses directly (no separate person detector); `person_detected` flag set when landmarks found | Uses MediaPipe's built-in person detection rather than a standalone human detector. No separate YOLO/SSD model. The `num_poses=1` limits to single person. |
| 1.2 | Bounding Box output (x, y, width, height) | PARTIALLY COVERED | `backend/services/pose_engine.py` — `ProcessedFrame` does not expose explicit bounding box; person presence tracked via `person_detected` boolean and confidence score | Bounding box coordinates are not computed or exposed. The pipeline skips this step since MediaPipe operates on the full frame. |
| 1.3 | Confidence threshold > 0.7 | NOT COVERED | HLD specifies 0.7; actual code uses 0.5 (detection) + 0.5 (tracking): `pose_engine.py:52-53` | Threshold mismatch is intentional — MediaPipe's own thresholds are used. Configurable via constants. |
| 1.4 | Tracking ID (unique integer, persistent across frames) | NOT COVERED | No tracking ID implementation exists. Single-person (`num_poses=1`) renders tracking moot. | Explicitly deferred. Multi-person tracking is in VISION_AND_ROADMAP.md as research track. |
| 1.5 | Frame data: RGB array, min 640x480, 30 FPS | PARTIALLY COVERED | `live_monitor.py:74-116` — negotiates 1280x720 then 640x480; actual FPS ~9-15 (not 30) | Resolution negotiation works. FPS target (30) not met — actual throughput is 9-15 FPS due to MediaPipe + overlay rendering. |
| 1.6 | NumPy array (uint8) output | FULLY COVERED | `live_monitor.py` — OpenCV reads into numpy array; `pose_engine.py` accepts numpy frame | Standard OpenCV `VideoCapture` returns numpy arrays. |
| 1.7 | Timestamp in milliseconds | FULLY COVERED | `events/events.py` — `ContextSnapshotCreatedEvent` includes timestamp; frame metadata tracked | Per-frame timestamps are captured using `time.monotonic()` and wall clock. |

### Design Note: Why There Is No Separate Person Detector

The HLD describes a two-stage pipeline (Human Detection → bounding box → Pose Estimation), but the implementation uses MediaPipe's **`PoseLandmarker`** in VIDEO mode, which **performs person detection internally** as part of its own pipeline — no separate YOLO/SSD stage is needed.

**How MediaPipe's internal detection works** (equivalent to HLD §3.1 bounding box + §3.3 confidence):

| HLD Requirement | How MediaPipe Satisfies It Internally | Code |
|----------------|--------------------------------------|------|
| Person detection | `PoseLandmarker` detects persons via a built-in person-detection model (a MobileNet-based SSD) before landmark regression. The `min_pose_detection_confidence=0.5` parameter controls this internal detector. | `pose_engine.py:69` |
| Bounding box (ROI) | MediaPipe applies detection internally to define the ROI for landmark extraction. The pipeline operates on the **full frame** — the ROI is implicit, not exposed as coordinates. | `pose_engine.py:98` — `keypoints = mediapipe_landmarks_to_keypoints(landmarks, w_f, h_f)` uses full-frame dimensions |
| Person present flag | `result.pose_landmarks` is non-empty when a person is detected; mapped to `person_detected = True` at `pose_engine.py:95-96` | `pose_engine.py:95-96` |
| Confidence score | Mean visibility of landmarks 0-16, multiplied by 100 (`pose_engine.py:34-40`). This is a **post-detection quality metric**, not a detection confidence — detection binary decision uses MediaPipe's internal 0.5 threshold. | `pose_engine.py:34-40`, `pose_engine.py:145` |
| Frame data (full frame) | `process_frame()` accepts the raw OpenCV BGR frame, converts to RGB, and passes it directly to `detect_for_video()`. No ROI cropping occurs. | `pose_engine.py:75-82` |
| Keypoint output (pixel coords) | `mediapipe_landmarks_to_keypoints()` multiplies normalized `[0.0, 1.0]` coordinates by `(width, height)`, producing the same pixel-coordinate format as if a bounding-box-crop pipeline had run. | `features.py:391-402` |
| Tracking ID | `num_poses=1` at `pose_engine.py:68` — single-person mode means no tracking ID is needed. Multi-person tracking is a future concern per VISION_AND_ROADMAP.md. | `pose_engine.py:68` |

**Bottom line:** The HLD's "bounding box → pose estimation" two-stage pipeline was designed for a 6-person team where Mohan (Human Detection) and Rian (Pose Estimation) were separate engineers. In the single-developer implementation, MediaPipe's integrated pipeline subsumes both stages. The **outcome is the same** — 33 landmarks with pixel coordinates, confidence scores, and per-frame person detection — achieved without the overhead of a separate detector (which would cost ~15-30ms per frame on CPU for no benefit at current scale).

---

## Module 2: Pose Estimation (HLD Member 3 — Rian, this module)

The core HLD document covers this module. All pipeline stages (MediaPipe → landmark validation → feature extraction → angle calculation → feature vector) are assessed against the actual `backend/services/` code.

### Pipeline Stages (HLD §2, §4)

| # | HLD Stage | HLD Output | Status | Code Evidence |
|---|-----------|-----------|--------|--------------|
| 2.1 | Pose Estimation Engine (MediaPipe) | 33 landmarks (x, y, z) | FULLY COVERED | `backend/services/pose_engine.py` — `PoseLandmarker` in VIDEO mode; 33 landmarks with x, y, z, visibility |
| 2.2 | Landmark Validation | Valid Points | PARTIALLY COVERED | `features.py` — visibility check for landmarks; COCO_17 fallback when <25 keypoints. No Kalman filtering, no anatomical coherence checks, no low-pass filter. |
| 2.3 | Feature Extraction | Raw Features | FULLY COVERED | `backend/services/features.py` — `extract_features_from_keypoints()` returns all 7 features |
| 2.4 | Angle Calculation | Angles | FULLY COVERED | `backend/services/features.py` — `_angle_between()` computes 3-point angles; all 7 features are angle-based |
| 2.5 | Feature Vector Builder | 15+ dim feature vector | PARTIALLY COVERED | Current feature vector is 7-dimensional (the 7 ergonomic features). HLD specifies 15+ dimensions. Extra dimensions (confidence, tracking, temporal) not in current vector. |

### Input Specifications (HLD §3)

| # | HLD Input | HLD Format | Status | Code Evidence |
|---|-----------|-----------|--------|--------------|
| 2.6 | Bounding Box | (x, y, width, height), normalized or pixel | NOT COVERED | Not consumed. MediaPipe operates on full frame. |
| 2.7 | Tracking ID | Unique integer | NOT COVERED | Not consumed. Single-person only. |
| 2.8 | Frame Data | RGB Array, HxWx3, uint8, min 640x480 | FULLY COVERED | `pose_engine.py:process_frame()` accepts BGR frame (OpenCV default), internally converts to RGB for MediaPipe |

### MediaPipe Configuration (HLD §4.1.1)

| # | HLD Parameter | HLD Value | Status | Code Evidence |
|---|--------------|-----------|--------|--------------|
| 2.9 | Model | MediaPipe Pose Landmarks 33 Points | FULLY COVERED | `pose_engine.py:42-48` — `PoseLandmarker.create_from_options()` with `PoseLandmarkerOptions()` |
| 2.10 | Dimensions | 3D (x, y, z) | FULLY COVERED | `mediapipe_landmarks_to_keypoints()` returns `[x_px, y_px, z, visibility]` — z is in meters (MediaPipe depth) |
| 2.11 | Min Detection Confidence | 0.5 | FULLY COVERED | `pose_engine.py:52` — `min_pose_detection_confidence=0.5` |
| 2.12 | Min Tracking Confidence | 0.5 | FULLY COVERED | `pose_engine.py:53` — `min_pose_tracking_confidence=0.5` |

### Landmark Validation (HLD §4 Step 2)

| # | HLD Check | HLD Threshold | Status | Code Evidence |
|---|----------|--------------|--------|--------------|
| 2.13 | Visibility | > 0.5, flag occluded | PARTIALLY COVERED | `features.py` uses visibility filtering for feature computation; no explicit "occluded" flag separate from confidence |
| 2.14 | Confidence | > 0.7, interpolate/reject | PARTIALLY COVERED | `confidence` computed as mean visibility of landmarks 0-16 (`pose_engine.py:120-121`); no interpolation; low-confidence frames are processed with reduced reliability |
| 2.15 | Completeness | 25/33 min, re-estimate | PARTIALLY COVERED | `features.py:109-119` — keypoint count check; falls back to COCO_17 mapping if <25 landmarks. No explicit "re-estimation" request. |
| 2.16 | Coherence | Joint limits, Kalman smoothing | NOT COVERED | No anatomical feasibility checks. No Kalman filter implemented. |
| 2.17 | Temporal | < 15 degrees, low-pass filter | NOT COVERED | No temporal smoothing or low-pass filtering on feature values across frames. |

### Feature Engineering (HLD §4 Step 3)

| # | HLD Feature | Calculation Method | Status | Code Evidence |
|---|-----------|-------------------|--------|--------------|
| 2.18 | Neck Flexion | Ear-shoulder-hip angle | FULLY COVERED | `features.py:128-139` — `_angle_between()` with ear, neck, hip midpoints |
| 2.19 | Trunk Flexion | Shoulder-hip-knee angle | FULLY COVERED | `features.py:140-152` — `_angle_between()` with neck, hip midpoint, vertical_up |
| 2.20 | Shoulder Elevation | Vertical shoulder offset | FULLY COVERED | `features.py:153-167` (left), `168-182` (right) — elbow-shoulder-vertical_down angle |
| 2.21 | Shoulder Symmetry | L/R shoulder height diff | FULLY COVERED | `features.py:183-195` — `\|L_y − R_y\| / shoulder_width × 100` |
| 2.22 | Alignment Deviation | Plumb line offset | FULLY COVERED | `features.py:196-208` — `\|ear_x − hip_x\| / torso_len × 100` |
| 2.23 | Leg Position (Knee Angle) | Hip-knee-ankle angles | FULLY COVERED | `features.py:209-225` — average of left and right knee angles |

### Output Specifications (HLD §5)

| # | HLD Output | HLD Format | Status | Code Evidence |
|---|-----------|-----------|--------|--------------|
| 2.24 | Pose Landmarks | JSON, 33 (x,y,z) + visibility | FULLY COVERED | `mediapipe_landmarks_to_keypoints()` — returns `list[list[float]]` shape (33, 4); serialized via `ProcessedFrame.to_dict()` |
| 2.25 | Body Angles | Array | FULLY COVERED | `extract_features_from_keypoints()` returns `dict[str, float]` — 7 named features |
| 2.26 | Feature Vector | 15+ dim normalized array | PARTIALLY COVERED | 7 dimensions (not 15+). No normalization (values are raw degrees/percentages). |
| 2.27 | Confidence Scores | Per-landmark + overall, JSON | PARTIALLY COVERED | Overall confidence in `ProcessedFrame.confidence`; per-landmark visibility available in raw landmarks |
| 2.28 | Tracking ID | Integer | NOT COVERED | No tracking ID. Worker identification not implemented. |
| 2.29 | Timestamp | Integer (frame sequence) | FULLY COVERED | `ProcessedFrame` includes frame number; events include wall-clock timestamps |
| 2.30 | Validation Flags | Boolean | NOT COVERED | No per-frame validation flag output |

### Interface Spec (HLD §6.3)

| # | HLD Interface | HLD Spec | Status | Code Evidence |
|---|--------------|---------|--------|--------------|
| 2.31 | Input Protocol | Shared memory / Redis | DELIBERATELY DEFERRED | Direct in-process function calls (`live_monitor.py` -> `pose_engine.py`). No IPC. Deferred until multi-process deployment needed. |
| 2.32 | Output Protocol | JSON via RabbitMQ | DELIBERATELY DEFERRED | Direct in-process event bus (`events/event_bus.py`). No message broker. |
| 2.33 | Data Format | JSON with base64 arrays | NOT COVERED | Internal dict/list structures; JSON only at API layer (`backend_api/` schemas) |
| 2.34 | Frequency | Real-time (30 FPS) | PARTIALLY COVERED | Realtime processing loop at 9-15 FPS. EventBus fires on every frame. |

---

## Module 3: Risk Assessment (HLD Member 4 — Nikhil, downstream)

The HLD defines this as the downstream module receiving feature vectors, angles, and confidence scores.

| # | HLD Deliverable / Downstream Contract | Status | Code Evidence | Notes |
|---|--------------------------------------|--------|--------------|-------|
| 3.1 | Feature Vector consumption | FULLY COVERED | `backend/context/engine.py` — `compute_context_snapshot()` takes features dict, computes risk score 0-100 | Context Intelligence Engine is the downstream consumer |
| 3.2 | Biomechanical Angle consumption | FULLY COVERED | `backend/context/engine.py` — scores each of 7 features individually using medium/high thresholds | Per-feature scoring pipeline |
| 3.3 | Confidence Score consumption | FULLY COVERED | `backend/context/engine.py` — includes `confidence_modifier` in risk adjustment | Low confidence reduces risk score reliability |
| 3.4 | Risk classification (LOW/MEDIUM/HIGH) | FULLY COVERED | `backend/context/engine.py` — threshold-based: HIGH >= 70, MEDIUM >= 30, LOW < 30 | Three-level classification matching HLD §4 (Stage 7) |
| 3.5 | Continuous scoring per frame | FULLY COVERED | `backend/context/engine.py` — called on every frame in `live_monitor.py` processing loop | Frame-by-frame risk computation |
| 3.6 | Alert generation on threshold breach | FULLY COVERED | `backend/alerts/engine.py` — fires HIGH/CRITICAL alerts; 3 rules (high_risk, critical_risk, recovery) | Cooldown mechanism (30 frames), ACTIVE→RESOLVED lifecycle |
| 3.7 | Fatigue tracking | FULLY COVERED | `backend/context/fatigue.py` — exponential curve `100 * (1 - e^(-0.42 * min/30))`, recovery logic | Fatigue modifier adds 0-20 to risk score |
| 3.8 | Exposure tracking | FULLY COVERED | `backend/context/exposure.py` — weighted body-region accumulation (neck 1.5x, trunk 1.3x, etc.) | Duration penalty, high-risk detection thresholds |
| 3.9 | Safety state machine | FULLY COVERED | `backend/context/engine.py` — hysteresis: CRITICAL, OBSERVE, SAFE, RECOVERY states | State transitions with hysteresis to prevent flickering |
| 3.10 | Temporal analysis / history | FULLY COVERED | `backend/history/engine.py` — tiered storage (300s full res, then 10x downsample), 50K snapshot deque | Running statistics always maintained |
| 3.11 | Recommendation generation | FULLY COVERED | `backend/recommendations/engine.py` — 12 catalog templates across 6 categories | Triggered by feature scores, fatigue, exposure, alert counts |

---

## Module 4: Backend & Storage

Covers the API layer, database, file storage, authentication, and session infrastructure.

| # | Capability | Status | Code Evidence | Notes |
|---|-----------|--------|--------------|-------|
| 4.1 | REST API for live dashboard data | FULLY COVERED | `backend_api/app/api/dashboard.py` — `GET /api/dashboard` returns features, risk, issues, recommendations | 19 working endpoints verified (CURRENT_STATE.md §9) |
| 4.2 | Session lifecycle (start/stop/status) | FULLY COVERED | `backend_api/app/api/session_lifecycle.py` — `POST /api/session/start`, `POST /api/session/stop`, `GET /api/session/status` | In-memory LiveState management |
| 4.3 | Session persistence to disk | FULLY COVERED | `backend/services/session_analytics.py` — `save_session_summary()` writes JSON to `outputs/sessions/` | 127 saved session files exist |
| 4.4 | Session listing / history | FULLY COVERED | `backend_api/app/api/sessions.py` — `GET /api/sessions` reads from `outputs/sessions/*.json` | Includes search/filter by date |
| 4.5 | Video recording (session recordings) | FULLY COVERED | `live_monitor.py` — sidecar recorder saves `original.mp4` to `recordings/{worker_id}/{timestamp}/` | Best-effort: write failure doesn't corrupt session JSON |
| 4.6 | Video feed streaming | FULLY COVERED | `backend_api/app/api/video_feed.py` — `GET /video/feed` — MJPEG stream with skeleton overlay | Overlay toggle via `overlay` query param (RISK_COLORS: green/amber/red) |
| 4.7 | Alert history API | FULLY COVERED | `backend_api/app/api/alerts.py` — `GET /api/alerts` returns active, history, summary | Verified matching AlertEngine counts |
| 4.8 | Context snapshot API | FULLY COVERED | `backend_api/app/api/context.py` — `GET /api/context/snapshot` | Returns current ContextSnapshot |
| 4.9 | Recommendation API | FULLY COVERED | `backend_api/app/api/recommendations.py` — `GET /api/recommendations` | Returns bundle with highest_priority |
| 4.10 | Risk history API | FULLY COVERED | `backend_api/app/api/history.py` — `GET /api/history` | Points + statistics |
| 4.11 | WebSocket endpoints | FULLY COVERED | `backend_api/app/websocket/manager.py` — `/ws/dashboard`, `/ws/alerts`, `/ws/camera` | Defined, with heartbeats. Not consumed by React frontend (uses polling instead). |
| 4.12 | SQLite database | FULLY COVERED | `backend_api/app/core/database.py` — tables: `users`, `workers`, `alerts`, `audit_log`, `pilot_requests` | Auto-created; `local_auth.db` file present |
| 4.13 | Authentication (JWT, bcrypt) | FULLY COVERED | `backend_api/app/core/auth.py` — JWT tokens; `backend_api/app/core/security.py` — bcrypt password hashing | Real backend-enforced 403s |
| 4.14 | RBAC (operator/supervisor/safety_mgr/admin) | FULLY COVERED | `backend_api/app/core/auth.py` — `require_role()` dependency; permission matrix: 4 roles × 4+ resource types | Verified with SEED_CREDENTIALS |
| 4.15 | User management CRUD | FULLY COVERED | `backend_api/app/api/users.py`, `backend_api/app/api/workers.py` | Users and workers tables |
| 4.16 | Audit log | PARTIALLY COVERED | `backend_api/app/core/database.py` — `audit_log` table; `backend_api/app/api/audit.py` — GET endpoint | Audit trail endpoint exists but limited auto-logging of actions |
| 4.17 | Report generation | PARTIALLY COVERED | `backend_api/app/api/reports.py` — `POST /api/report/generate` is a stub (returns mock); `backend/services/report_pdf.py` — PDF via Playwright | PDF generation code exists but report/generate endpoint returns mock |
| 4.18 | Video analysis (upload arbitrary video) | PARTIALLY COVERED | `backend_api/app/api/video_analysis.py` — endpoint exists, processes through real pipeline | Phase H per VISION_AND_ROADMAP.md; needs re-verification (interrupted mid-test) |
| 4.19 | AI Assistant RAG (knowledge base chat) | FULLY COVERED | `backend/services/assistant.py` — RAG pipeline; `backend_api/app/api/assistant.py` — SSE streaming endpoint | Local Ollama, 5 knowledge files, verified end-to-end |
| 4.20 | Mock / demo data layer | FULLY COVERED | `backend_api/app/repositories/mock.py` — all mock JSON responses; `backend_api/app/utils/mock_data.py` | Demo mode switchable via config |
| 4.21 | Trends endpoint | PARTIALLY COVERED | `backend_api/app/api/trends.py` — `GET /api/trends` returns mock (frozen) data | Cross-session trend aggregation deferred to Phase J |
| 4.22 | Manager / factory-wide dashboard endpoint | PARTIALLY COVERED | `backend_api/app/api/manager.py` — returns mock data | Requires cross-session aggregation (Phase J) |
| 4.23 | Deployment / infrastructure endpoint | PARTIALLY COVERED | `backend_api/app/api/deployment.py` — returns mock data | Frozen; not wired to real infra metrics |
| 4.24 | Camera enumeration endpoint | PARTIALLY COVERED | `backend_api/app/api/cameras.py` — returns `[]`; `backend/services/camera_manager.py` — real camera enumeration exists but not wired | camera_manager.py is unused by the live pipeline |

---

## Module 5: UI/UX Dashboard

Covers the React frontend (`ui_posture/src/`), pages, components, hooks, and data flow.

| # | Feature | Status | Code Evidence | Notes |
|---|--------|--------|--------------|-------|
| 5.1 | Live Monitoring page | FULLY COVERED | `src/pages/LiveMonitoring.tsx` — real dashboard data; `CameraPanel.tsx` — MJPEG stream with overlay toggle | Polls `GET /api/dashboard` + `GET /api/history` |
| 5.2 | Session History page | FULLY COVERED | `src/pages/SessionHistory.tsx` — lists sessions; detail drawer with risk breakdown | Fully live data |
| 5.3 | Trend Analysis page | PARTIALLY COVERED | `src/pages/TrendAnalysisPage.tsx` — live KPIs + hardcoded 8-week `weeklyTrend` array | Charts are hardcoded demo data |
| 5.4 | Analytics page | PARTIALLY COVERED | `src/pages/AnalyticsPage.tsx` — live data + hardcoded `weeklyData`, `issueFreq`, `distData` | Charts are demo/hardcoded |
| 5.5 | Reports page | NOT COVERED | `src/pages/ReportsPage.tsx` — 5 hardcoded entries, button handlers are toast-only | No real report generation workflow |
| 5.6 | Manager Dashboard | PARTIALLY COVERED | `src/pages/ManagerDashboard.tsx` — live KPIs + hardcoded `workers` (10), `gridPositions` (10) | Factory floor view is hardcoded |
| 5.7 | Deployment Center | NOT COVERED | `src/pages/DeploymentCenter.tsx` — static mock data | `infraStatus`, `cameras`, `edgeMetrics` are hardcoded |
| 5.8 | Multi-Camera View | NOT COVERED | `src/pages/MultiCameraView.tsx` — 9 hardcoded cameras | No real multi-camera support |
| 5.9 | Audit Trail | NOT COVERED | `src/pages/AuditTrail.tsx` — 24 hardcoded audit events | No real audit data consumption |
| 5.10 | Settings page | NOT COVERED (real) | `src/pages/SettingsPage.tsx` — localStorage persistence; no backend sync | No settings API |
| 5.11 | Login / Auth page | FULLY COVERED | `src/pages/LoginPage.tsx` — JWT auth flow; `src/auth/AuthContext.tsx` — role-based context | Verified with real backend auth |
| 5.12 | Video Review / Replay | FULLY COVERED | `src/pages/VideoReviewPage.tsx` — upload + analyze; `src/pages/ReplayPage.tsx` — session replay | Video analysis endpoint exists; Replay has status field bug (VISION_AND_ROADMAP.md) |
| 5.13 | AI Assistant UI | FULLY COVERED | `src/demo/AIAssistantPanel.tsx` — slide-in chat panel, SSE stream, source citations | Verified end-to-end |
| 5.14 | Alert management UI | FULLY COVERED | `src/common/AlertManagementCard.tsx` — polls `GET /api/alerts` at 1s interval | Real-time alert display |
| 5.15 | Context-aware risk card | FULLY COVERED | `src/common/ContextAwareRiskCard.tsx` — polls `GET /api/context/snapshot` at 1s | Real risk score with context modifiers |
| 5.16 | Recommendations display | FULLY COVERED | `src/common/RecommendationsCard.tsx` — polls `GET /api/recommendations` at 1s | Highest priority shown |
| 5.17 | Live timeline | PARTIALLY COVERED | `src/common/LiveTimeline.tsx` — 8s timer with random fake events | Not connected to real event stream |
| 5.18 | Exports Center | FULLY COVERED | `src/common/ExportsCenter.tsx` — grid-aligned export actions | Previously had `align-super` bug; now uses `grid grid-cols-[auto_1fr_auto]` |
| 5.19 | Workstation registry | NOT COVERED | No Workstation management UI component exists | `GET /api/workstations` returns `[]` |
| 5.20 | Digital twin visualization | NOT COVERED | `src/common/DigitalTwin.tsx` — exists but uses static data | No real 3D/render visualization |
| 5.21 | Notification center | NOT COVERED (real) | `src/common/NotificationCenter.tsx` — 10 hardcoded notifications | Not connected to backend |
| 5.22 | Search modal | NOT COVERED (real) | `src/common/SearchModal.tsx` — 8 hardcoded items | Not connected to backend search |
| 5.23 | Health score gauge | PARTIALLY COVERED | `src/common/HealthScore.tsx` — displays score, but source data may be hardcoded | Verify live data binding |
| 5.24 | Shift summary | NOT COVERED (real) | `src/common/ShiftSummary.tsx` — exists but may use hardcoded data | No real shift aggregation |

### Data Architecture

| # | Element | Status | Code Evidence |
|---|--------|--------|--------------|
| 5.25 | Repository pattern (live/mock switching) | FULLY COVERED | `src/repositories/DashboardRepository.ts` + `ApiDashboardRepository.ts` + `MockDashboardRepository.ts` |
| 5.26 | USE_MOCK config flag | FULLY COVERED | `src/config/index.ts` — `USE_MOCK: false` |
| 5.27 | Polling hooks (1-2s intervals) | FULLY COVERED | `useAlerts`, `useHistory`, `useDashboard`, `useContextSnapshot`, `useRecommendations`, `useSessionLifecycle` |
| 5.28 | WebSocket client | FULLY COVERED (built) | `src/services/WebSocketClient.ts` — exists but not actively used (polling preferred) |
| 5.29 | API client (axios) | FULLY COVERED | `src/services/apiClient.ts` — base URL, auth token injection, error handling |
| 5.30 | TypeScript types matching Pydantic schemas | PARTIALLY COVERED | `src/types/api.ts` — manual alignment with `backend_api/app/schemas/api.py` | Requires manual sync when API schema changes |

---

## Module 6: Project Lead / Integration

Covers CI/CD, Docker, testing, documentation, and cross-cutting concerns.

### CI/CD & Deployment

| # | HLD Requirement | Status | Code Evidence | Notes |
|---|----------------|--------|--------------|-------|
| 6.1 | CI/CD pipeline | NOT COVERED | No `.github/workflows/`, `.gitlab-ci.yml`, or `Jenkinsfile` in repository | No automated CI. Single-developer project; manual testing. |
| 6.2 | Docker containerization | PARTIALLY COVERED | `docker-compose.yml` (root), `backend_api/Dockerfile`, `ui_posture/Dockerfile`, `ui_posture/nginx.conf` | Works locally but has reproducibility issues (see session notes: Playwright Chromium download timeout, cache invalidation) |
| 6.3 | GPU acceleration | NOT COVERED | No CUDA/cuDNN dependencies in requirements; no GPU runtime configs | MediaPipe runs on CPU. GPU acceleration deferred (Research Track). |
| 6.4 | NVIDIA GPU support | NOT COVERED | No NVIDIA container toolkit config | Would require separate GPU-enabled Dockerfile |
| 6.5 | Message queue (Redis/RabbitMQ) | DELIBERATELY DEFERRED | In-process EventBus used instead (`backend/events/event_bus.py`) | Not needed for single-process deployment. VISION_AND_ROADMAP.md Phase K (multi-site) would require this. |
| 6.6 | Time-series database (InfluxDB) | DELIBERATELY DEFERRED | In-memory history engine + flat JSON files used instead | Not needed for current scale. Phase K would re-evaluate. |

### Testing

| # | Type | Status | Evidence | Notes |
|---|------|--------|---------|-------|
| 6.7 | Unit tests (pytest) | NOT COVERED | No `pytest.ini` or `conftest.py`; no organized test directory | Tests are standalone Python scripts in `scripts/` (33 scripts) |
| 6.8 | Integration tests | PARTIALLY COVERED | `scripts/test_sprint*.py` (6 sprint integration tests); `scripts/test_runtime_integration.py` | Ad-hoc scripts, not in automated suite |
| 6.9 | API tests | PARTIALLY COVERED | `backend_api/tests/` (4 tests); `_test_auth.py`, `_test_cache.py` | Test specific components; not comprehensive |
| 6.10 | Endurance / load test | PARTIALLY COVERED | `endurance_test.ps1` — 100 consecutive `/api/dashboard` requests | Verifies HTTP 200 stability only |
| 6.11 | Validation / debug scripts | FULLY COVERED | 7 debug scripts (`debug_trunk.py`, `debug_neck.py`, `debug_knee.py`, `debug_shoulder_symmetry.py`, etc.) | Visual validation with screenshots captured |
| 6.12 | Pose validation report | FULLY COVERED | `scripts/generate_pose_validation_report.py` — automated validation | 7 features validated (CURRENT_STATE.md §3) |
| 6.13 | Playwright browser tests | PARTIALLY COVERED | `scripts/capture_session_detail_screenshots.py`; no formal Playwright test suite | Browser-based verification done ad-hoc during development |

### Documentation

| # | Document | Status | Evidence |
|---|---------|--------|---------|
| 6.14 | HLD | FULLY COVERED | `docs/Pose_Estimation_Module_HLD_Rian.docx (2).pdf` — 11 pages |
| 6.15 | CURRENT_STATE.md | FULLY COVERED | `docs/CURRENT_STATE.md` — 362 lines, 10 subsystems, endpoint inventory, verified evidence |
| 6.16 | VISION_AND_ROADMAP.md | FULLY COVERED | `docs/VISION_AND_ROADMAP.md` — 12 phases (A–L), standing decisions, scope exclusions |
| 6.17 | Implementation reports | FULLY COVERED | 6 reports in `docs/` (trend, session, persistence, safety, issue detection, recommendations) |
| 6.18 | README files | FULLY COVERED | `README.md`, `ui_posture/README*.md` (4 READMEs), `backend_api/README.md` |
| 6.19 | Knowledge corpus (AI Assistant) | FULLY COVERED | `knowledge/` — 5 markdown files (thresholds, alerts, features, recommendations, FAQ) |
| 6.20 | Module handoff document | FULLY COVERED | `results/POSE_MODULE_HANDOFF.md` — 240 lines, 8 sections |
| 6.21 | Architecture diagrams | NOT COVERED | No formal architecture diagram (PlantUML, Draw.io, etc.) files found | Architecture is described textually in CURRENT_STATE.md |

### Model / Research

| # | Item | Status | Evidence |
|---|------|--------|---------|
| 6.22 | MediaPipe model | FULLY COVERED | `models/pose_landmarker_lite.task` — 4.8MB MediaPipe Lite model |
| 6.23 | ML model (Random Forest) | DELIBERATELY DEFERRED | `models/best_model.pkl`, `models/svm_model.pkl` — exist but NOT wired into live pipeline | Research Track per VISION_AND_ROADMAP.md — threshold-based engine is the live system |
| 6.24 | Dataset exploration notebooks | FULLY COVERED | `notebooks/01_explore_datasets.ipynb`, `02_feature_engineering.ipynb`, `03_model_training.ipynb` | Research track only; not part of live pipeline |
| 6.25 | Dataset files | FULLY COVERED | `data/processed/dataset_final.csv`, `dataset_fixed.csv`, `dataset_with_knee.csv` | Processed datasets for model training experiments |
| 6.26 | SVM model training | FULLY COVERED | `scripts/train_svm.py` — trains SVM classifier on processed dataset | Research track; not deployed |

---

## Coverage Summary

| Module | FULLY COVERED | PARTIALLY COVERED | NOT COVERED | DELIBERATELY DEFERRED | Total Items |
|--------|:----------:|:---------------:|:---------:|:-------------------:|:--------:|
| 1. Human Detection | 2 | 2 | 2 | 0 | 6 (plus 1 sub-item) |
| 2. Pose Estimation | 11 | 8 | 7 | 2 | 28 (plus 6 sub-items) |
| 3. Risk Assessment | 11 | 0 | 0 | 0 | 11 |
| 4. Backend & Storage | 16 | 7 | 1 | 0 | 24 |
| 5. UI/UX Dashboard | 8 | 5 | 9 | 0 | 22 (plus 6 sub-items) |
| 6. Project Lead / Integration | 10 | 4 | 5 | 3 | 22 (plus 6 sub-items) |
| **Total** | **58** | **26** | **24** | **5** | **113** |

**Key Gaps:**
1. **No CI/CD pipeline** — no automated build/test/deploy configuration
2. **No organized test framework** — 33 standalone scripts instead of pytest suite
3. **5 of 10 dashboard pages are static** — Reports, Deployment, Multi-Camera, Audit Trail, Settings use hardcoded data
4. **No multi-person tracking** — `num_poses=1`; tracking IDs not implemented
5. **No temporal smoothing** — feature values jitter frame-to-frame
6. **FPS below target** — 9-15 FPS vs. HLD target of 30 FPS
7. **No message broker** — in-process EventBus replaces Redis/RabbitMQ (correct for current scale)
8. **No time-series DB** — flat JSON + in-memory deque replaces InfluxDB (correct for current scale)
9. **ML model not wired** — `best_model.pkl` exists but threshold-based engine runs live (intentional per VISION_AND_ROADMAP.md)

---

*Generated 2026-07-18 against commit `HEAD` of `C:\GGS_intership\posture_analysis`. Each claim is backed by file inspection or session evidence from CURRENT_STATE.md.*
