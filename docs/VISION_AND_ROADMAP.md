VISION_AND_ROADMAP.md


This document describes what ErgoVigilance could become. Nothing in this file is a claim about what exists today.
For what is actually built and verified, see CURRENT_STATE.md. If the two documents ever disagree, CURRENT_STATE.md wins.

Note on this revision: an earlier version of this file was found to be significantly out of date — it listed Recording/Replay as not-started and Auth/RBAC as explicitly out of scope, when both are now built and verified. This revision corrects that. Always sanity-check this file's phase statuses against actual recent work before trusting it.

## Phase Status Summary (as of 2026-08-12)

| Phase | Status |
|---|---|
| A — Live Monitoring | Complete and verified |
| B — Session Review | Complete |
| C — Reports | Complete (risk-trend / safety-report built and verified in Phase J) |
| D — Video Recording | Complete |
| E — Replay | Complete, verified end-to-end (SessionDetail status fix applied) |
| F — Authentication & RBAC | Complete |
| G — Dashboard | Complete |
| H — Video Upload & Analysis | Complete and verified |
| I — Context-Aware Task Recognition | Complete |
| J — Long-Term Fatigue & Trend Analytics | Complete |
| K — Cloud & Multi-Site | Not started |
| L — AI Assistant (RAG, Local Ollama) | Backend + frontend built, verified end-to-end |
| Research Track — ML-Enhanced Risk Scoring | Not started (blocked on R2: ground-truth labels) |

This table is a summary; the phase sections below carry the detail and verification evidence. If this table and the sections ever disagree, the sections win.


1. Executive Vision

ErgoVigilance is an AI-powered industrial ergonomics monitoring platform that continuously observes workers, detects unsafe posture and repetitive-strain risk in real time, tracks fatigue and exposure over a shift, and produces evidence-backed reports for workers, supervisors, and safety managers.

2. Why This Product Exists


Work-related musculoskeletal disorders (WMSDs) are a leading cause of lost workdays in manufacturing and warehousing.
Standard ergonomic assessment tools (RULA, REBA, OWAS) are manual, point-in-time, and require a trained assessor physically present — they cannot run continuously across a shift.
There is currently no low-cost way to get continuous, objective, camera-based posture data on a factory floor without specialized hardware.


3. Users

UserWhat they need from the productOperator (worker)Real-time feedback on their own posture; not a surveillance experienceSupervisorAlerts when a worker is at risk, right now; visibility across their workersSafety ManagerShift-level and trend-level reports, incident evidence, facility-wide safety stateAdminFull system control: users, deployment, infrastructure

4. Design Principles


Every UI widget has a single backend source of truth — no duplicated business logic between backend and frontend.
Every alert must reference a specific posture event (frame, timestamp, risk snapshot) — not a vague "something happened."
All AI outputs must be explainable — a recommendation should trace back to the feature/threshold that triggered it.
The system must operate for a full 8-hour shift without manual intervention.
Offline operation is required; cloud sync is an enhancement, not a dependency. This includes authentication — login must work without internet access; local SQLite, not cloud-dependent auth, was chosen deliberately for this reason.
What can be demonstrated convincingly is what can be sold — every phase should end in something showable, not just something built.
Never fabricate a number to make a page look complete. Any UI element without real backend data behind it is either omitted or explicitly labeled ("Coming Soon — requires X"). This was violated once (a hardcoded factory-wide dashboard card) and became a standing rule after being caught.



Roadmap, Ordered by Actual Dependency

Each phase assumes the previous one is genuinely verified in the browser, not just coded.

Phase A — Live Monitoring (Vertical Slice #1)

Status: complete and verified. Camera, pose, features, risk, context, alerts, recommendations, history all live. Restyled to industrial dark theme; guidance/issue text ported from the Streamlit prototype and verified live.

Phase B — Session Review (Vertical Slice #2)

Status: complete. Session metadata, risk breakdown, feature averages, alert timeline — read from saved JSON.

Phase C — Reports

Status: complete. Per-session CSV/JSON/PDF export working. Cross-session "Risk Trend Report" / "Safety Report" were originally placeholdered ("Coming Soon — requires multiple sessions") and correctly deferred — they are now built and verified in Phase J (see below).

Phase D — Video Recording

Status: complete. Sessions save original.mp4 alongside JSON via a sidecar recorder in live_monitor.py. Best-effort: a video-write failure does not corrupt session JSON. Stored under recordings/{worker_id}/{timestamp}/.

Phase E — Replay

Status: complete, verified end-to-end for a real session. Session → recording → timeline.json/summary.json/video, all keyed by session ID. Graceful states for "not yet recorded" / "still processing."
Known bug to fix: SessionDetail is missing a status field, so the "Open in Replay" button in Session History's detail drawer never renders (always checks an undefined field). This needs a direct fix — see active issues below.

Phase F — Authentication & RBAC (added — was previously mis-scoped as out-of-scope; now complete)

Status: complete. Local SQLite users/workers tables, bcrypt hashing, JWT tokens, real backend-enforced 403s (not just hidden UI) across the full permission matrix (operator/supervisor/safety_mgr/admin). Session ownership (worker_id, created_by_user_id) added for new sessions; legacy sessions remain unowned and hidden from operators.

Phase G — Dashboard (added — was previously undocumented; now complete)

Status: complete. Separate page, four role-differentiated variants, every number sourced live (e.g. worker count via COUNT(workers), verified to actually change when a worker is added/removed). Honest "Coming Soon" placeholders for anything requiring cross-session aggregation.

Phase H — Video Upload & Analysis (added — new, separate from Replay)

Status: complete and verified. Upload an arbitrary video (≤200MB) processed through the same real pipeline (PoseEngine, features.py) — not a duplicate implementation. Verified end-to-end: uploaded sample_posture_test.mp4 (0.7 MB, 6s at 10fps), processed 6 analyzed frames with risk classification (2 LOW, 4 MEDIUM), returned per-frame features and normalized keypoints for frontend skeleton overlay. Full endpoint at POST /api/video/analyze, frontend at /video-review.

Phase I — Context-Aware Task Recognition

Status: complete. The task recognition pipeline is fully wired end-to-end.

What is built and verified:
- TaskRecognition class (backend/services/task_recognition.py, 274 lines) classifies poses into 5 task classes (Neutral Standing, Assembly Work, Reaching, Lifting/Picking, Inspection) using Gaussian scoring on 7 biomechanical features, with temporal smoothing (confidence-weighted sliding window, window_size=10) and dwell-time tracking.
- Integrated into PoseEngine.process_frame() at pose_engine.py:148, storing task_info in every ProcessedFrame.
- ContextIntelligenceEngine.evaluate() (engine.py:316-319) applies a task-specific risk modifier (static dict, now exposed via GET /api/task-modifiers) to final_risk. The modifier is scaled by task_confidence/100 so low-confidence classifications have weaker impact.
- LiveMonitoringService._process_loop() (live_monitor.py:447-466) extracts task_name, task_confidence, task_duration from result.task_info and passes them to the context engine.
- Video Analysis endpoint (video_analysis.py:118-122) reads task_info from processed frames and passes it through the same context engine — no separate implementation.
- Frontend: TaskRecognitionCard (DashboardPage.tsx:760) displays current task, risk impact (now sourced from the live /api/task-modifiers endpoint instead of a hardcoded duplicate), real task_confidence from liveStatus.confidence (not fabricated from feature_scores), and all 5 task modifier values. Telemetry sidebar in LiveMonitoring.tsx shows current task, duration, and confidence from the backend.

Remaining stretch items (deferred, no urgent need):
- Live task info propagation to the elevated (supervisor/admin) dashboard — currently shows "Unknown" because the multi-worker view has no single active session to track. Would require per-session state propagation.
- Dynamic/extensible task classes — currently 5 hardcoded classes. Adding more requires updating both _TASK_MODIFIERS and TaskRecognition Gaussian parameters.

Phase J — Long-Term Fatigue & Trend Analytics

Status: complete. All three major report types are built and verified:

- **Risk Trend Report** — `GET /api/reports/risk-trend` (backend_api/app/api/risk_trend.py, computation in backend/services/trend_analysis.py:analyze_risk_trend()). Reads real session JSON files from `outputs/sessions/`, computes cross-session risk distribution (LOW/MEDIUM/HIGH percentages), per-feature trend analysis (early-half vs late-half mean comparison with Improving/Stable/Deteriorating direction), and most common issues. Verified against 99 real sessions (as of 2026-08-12; the session count changes as new sessions are saved and retention removes old ones). PDF export at `/api/reports/risk-trend/pdf` via render_risk_trend_pdf().
- **Safety Report** — `GET /api/reports/safety-report` (backend_api/app/api/safety_report.py, computation in backend/services/safety_report.py:analyze_safety()). Cross-session alert analysis: severity breakdown, trigger rule distribution, alert density metrics, top sessions by alert count, most frequent issues. Only sessions with genuine alert data are included (older sessions without alert tracking are excluded and reported as such). Verified against 87 sessions with alert data from 99 total (as of 2026-08-12). PDF export at `/api/reports/safety-report/pdf` via render_safety_report_pdf().
- **Per-Worker Fatigue Trends & Station Analysis** — `GET /api/reports/worker-trends` (backend_api/app/api/worker_trends.py, computation in backend_api/app/services/worker_trends.py:compute_worker_trends()). Four sub-reports in one endpoint:
  - **Per-worker trend points**: Groups session files by worker_id, joins with SQLite workers table for department/shift/name, computes avg risk score (`(M×50 + H×100) / total_frames`), trend direction (early-half vs late-half comparison), latest risk level. Verified against 4 registered workers with session data (as of 2026-08-12).
  - **Per-department patterns**: Aggregates per-worker trends into departments, computes average risk, high-risk count, improving/deteriorating worker counts, overall trend. Verified: Assembly, Tester, Unknown departments.
  - **Temporal fatigue curves**: Parses `session_timestamp` → ISO week, computes weekly avg risk per worker. Only workers with 2+ weeks of data included. Verified: Asha Patel (W28: 48.0, W29: 51.5, W30: 57.8), Rian Hussain (W28: 35.0, W29: 50.0, W30: 80.1).
  - **Per-station risk patterns**: Normalizes inconsistent camera_id values (`cam1`→`cam-01`, `camera1`→`cam-01`), groups sessions by station, computes avg risk, high-risk count, worker count. Station names mapped from mock data (cam-01 → "Assembly Line A — Station 1"). Verified as of 2026-08-12: 4 stations with data (cam-01 "Assembly Line A — Station 1" has 36 sessions).

Frontend: Reports page → "Generate Worker Trends Report" button → WorkerTrendsView with summary stats (4-column grid), department pattern cards, per-worker detail cards, weekly risk bar charts (temporal curves), and station risk pattern cards. PDF export via Download PDF button in the view header, calling `GET /api/reports/worker-trends/pdf`.

Note on the old `/api/trends` endpoint: This endpoint (backend_api/app/repositories/live.py:375-377) still returns hardcoded mock data. It was the original trend endpoint before the real Risk Trend Report was built. The old TrendAnalysis page (`/trends`, TrendAnalysisPage.tsx) consumed this mock data. As of this revision, the old `/trends` route and TrendAnalysisPage have been removed — navigation to `/trends` redirects to `/reports?view=risk-trend`. The mock `/api/trends` endpoint was removed from the codebase in this revision — it returned hardcoded mock data and was no longer consumed by any active UI.

Phase K — Cloud & Multi-Site

Not started, explicitly last. Cloud storage, multi-camera/multi-station aggregation. Everything above should work fully offline, on one machine, first.


Phase L — AI Assistant (RAG, Local Ollama)

Status: backend built, frontend built, verified end-to-end.

RAG chatbot grounded in the ErgoVigilance knowledge corpus (thresholds, alert rules, recommendation types, product FAQ including step-by-step navigation how-tos). Runs on a local Ollama instance (llama3.2:3b for generation, nomic-embed-text for embeddings) — no external API calls, no session/PII data in the corpus.

What is built and verified:
- Backend RAG pipeline in backend/services/assistant.py: markdown chunking on ## headers, nomic-embed-text embedding via Ollama, cosine-similarity retrieval (top_k=3), context-grounded prompt construction, streaming token-by-token generation via llama3.2:3b.
- SSE streaming endpoint POST /api/assistant/chat (backend_api/app/api/assistant.py) emitting sources → token → done/refusal/error event types. Auth required (Bearer JWT). Streaming reduces first-byte latency from ~16s to ~4s vs non-streaming.
- Frontend chat UI in AIAssistantPanel.tsx: slide-in panel with message bubbles, animated "thinking" indicator, SSE stream parsing, source citations under responses (cleared on refusal), error/fallback handling.
- Knowledge corpus: 5 markdown files (thresholds.md, product_features.md, alert_rules.md, recommendation_types.md, product_faq.md) at knowledge/. FAQ entries are step-by-step how-tos verified against actual UI code (page names, button labels, navigation flows) — not generic prose.
- Honest out-of-scope refusals: when context doesn't answer the question, the model outputs "I can answer questions about ergonomic thresholds, alerts, and how the system works — I don't yet have access to your personal session history. Check the Sessions or Reports page for that." instead of a flat "I don't have information."
- Guidance-text generation (replacing guidance.py hardcoded strings with LLM-generated advice, with graceful fallback when Ollama is unavailable) — NOTE: this scope item was deferred. The live pipeline still uses the deterministic guidance strings. The AI Assistant is available on-demand only. This is the right call: model-generated advice flowing into the live risk pipeline without thorough vetting of edge cases would be irresponsible.

Explicitly NOT in scope (these remain deterministic for safety):
- Alert message enrichment — alert text is safety-critical and must be predictable, auditable, and hallucination-free.
- Recommendation text enrichment — same reasoning as alerts.
- Any external API call — Ollama runs locally, zero cloud dependency.

This scope choice is deliberate: safety-critical alert/recommendation text stays hardcoded so nobody quietly expands into that territory later without a conscious decision.

Explicitly deferred — Session-data Q&A (future phase or Phase L sub-item):
- Questions like "summarize my last session" or "what was my risk yesterday" require structured tool-calling / function-calling against live or persisted session data, not RAG over static text.
- **BUILT AND VERIFIED** — `backend/services/assistant.py` now includes:
  - `_fetch_session_context()` — detects session-related keywords in the user's question and fetches live data from session JSON files on disk
  - `_get_recent_session()` — returns a formatted summary of the most recent session (session ID, timestamp, worker, duration, risk distribution, highest risk level, most frequent issue, ergonomic features, alert count)
  - `_get_session_count()` — returns total session count
  - Session data is injected into the context as `[Live Session Data]` so Ollama can answer from real data
  - System prompt updated: removed the "no session history" refusal; now tells the model to use session data from context
  - Frontend fallback text updated to reflect new capability
  - The API endpoint passes `project_root` to `ask_stream` for disk access

**How it works**: When a user asks "what was my last session like?" or "how many sessions do I have?", the assistant detects the intent via keyword matching, reads the actual session JSON files from disk, formats the data as a structured summary, and injects it into the RAG context before calling Ollama. The model then answers from real data instead of a static fallback.

Still pending — RULA/REBA reference material for the knowledge corpus:
- **BUILT AND VERIFIED** — `knowledge/rula_reba_reference.md` added with RULA/REBA scoring systems, action levels, ErgoVigilance feature mapping, and practical application guidelines. Based on McAtamney & Corlett (1993) and Hignett & McAtamney (2000) published methodology.


Research Track — ML-Enhanced Risk Scoring (separate from the product track above)

Does not block or compete with Phases A–K. Standing decision: ContextIntelligenceEngine (threshold-based) remains the risk engine. models/best_model.pkl (used only by the frozen Streamlit prototype) is not wired into the live pipeline. If ML is introduced later, it becomes an additional input signal to the Context Engine, never a replacement — because Alert/History/Recommendation Engines are all verified against the current threshold engine.


R1 — Dataset survey. Any candidate dataset (e.g. Assembly101, proposed and correctly parked) needs an honest gap check: does it provide ergonomic risk labels, or only activity/pose labels? Assembly101 is the latter — not directly usable without first defining ground truth.
R2 — Define the training target. Unresolved: what should a model predict, and how would ground-truth risk labels be produced? Blocks everything after it.
R3 — Feature engineering expansion, only after R2.
R4 — Model comparison against the defined target.
R5 — Controlled integration as an additional Context Engine input, with full re-verification of downstream engines before shipping.


Rule: any proposal to "retrain the model" or "download a new dataset" gets checked against this section first. Is the product track (A–K) actually stable and demoable? If not, this waits.


Active Known Issues (fix before starting new phases)


SessionDetail missing status field — "Open in Replay" silently never shows. ✅ FIXED — the SessionDetail interface, backend schema, and repo layer all now support and return `status: StatusType`. Verified: SessionDetail has `status: StatusType` at api.ts:202, backend returns it, and SessionHistory.tsx:224 checks `detail.status === 'completed'` before rendering the replay button.
Silent exception handling — ❌ CLOSED (10 silent swallows fixed). All bare `except Exception: pass/continue` blocks in live.py:264, 310, 407, 533, 539, 550, 607, 642, 816 and live_monitor.py:72 now log the actual exception with context (session ID, filename, timestamp, etc.) using `logger.error/warning(...)` with `exc_info=True`. Graceful degradation preserved — the app still continues on failure, but the error is visible in logs.
Dead code — backend/services/pose.py, safety_reporting.py, and backend/persistence/ were moved to `backend/_archive/`. The three files flagged by the roadmap that remain in `backend/services/` (issue_detection.py, recommendation_engine.py, trend_analysis.py) are NOT dead — they are actively imported and used by the running backend. No further action needed.


Recent Fixes

alignment_deviation threshold mismatch in risk_breakdown() — discovered and fixed this week. The `risk_breakdown()` function in backend/features/features.py (used for summary display, e.g. the "Risk Breakdown" section in reports) was computing threshold-based risk for `alignment_deviation` using a generic else-branch that set HIGH=30 / MEDIUM=10, while the live ContextIntelligenceEngine in backend/engine/engine.py correctly used HIGH=25 / MEDIUM=10 for the same feature. This meant the summary UI could show a different risk level than what the live engine computed. Fix: added an explicit `elif name == "alignment_deviation": high, medium = 25.0, 10.0` branch in risk_breakdown(), matching the engine's thresholds.

Silent exception handling sweep — 10 bare `except Exception: pass/continue` blocks in live.py and live_monitor.py were un-silenced with proper `logger.error/warning()` calls including `exc_info=True`. All graceful degradation behaviors preserved (empty lists, fallback dates, null states). Pattern matched the three previously-fixed locations from earlier this week.
Task confidence wired into risk modifier — ContextIntelligenceEngine.evaluate() now scales task modifier by task_confidence/100, so low-confidence classifications have proportionally weaker impact on final_risk. Active rules log the scaled value.
Frontend task confidence fixed — TaskRecognitionCard no longer fabricates confidence from feature_scores (was computing fake 50-100% from shoulder_symmetry). Now receives real `taskConfidence` from `dashboard.liveStatus.confidence`.
Task modifiers exposed via API — GET /api/task-modifiers returns the _TASK_MODIFIERS dict from the backend, eliminating the duplicated hardcoded copy in the frontend. TaskRecognitionCard fetches this on mount instead.
Hardcoded worker placeholders replaced in ReportsPage — Worker Name, Department, and Shift now read from /api/workers matched by detail.worker_id. Workstation remains '—' with * placeholder (no data source exists). Matching the WorkerProfile.tsx pattern.
Phase H verified end-to-end — Uploaded test video (6s, 10fps) through POST /api/video/analyze. Returned 6 analyzed frames with risk classification, per-frame features, and normalized keypoints. Full pipeline confirmed working.
Phase J per-worker trends built — GET /api/reports/worker-trends endpoint and WorkerTrendsView frontend component. Groups session files by worker_id, joins with SQLite workers table for department/shift, computes per-worker avg risk score and trend direction (early-half vs late-half comparison). Aggregates per-department patterns. Added WorkerTrendPoint/DepartmentTrendEntry/WorkerTrendsResponse schemas, worker_trends.py service module, wired into router and Reports page. Verified: 4 workers, 64 sessions with worker_id.
Phase J temporal curves & station analysis — Extended worker-trends endpoint with weekly risk time series per worker (TemporalCurvePoint/WorkerTemporalCurve schemas) and per-station risk patterns (StationAnalysisEntry schema). Camera_id normalization handles inconsistent values (cam1→cam-01, camera1→cam-01). Station display names mapped from mock data. Verified: 2 workers with 3+ weeks of temporal data, 1 station (cam-01) with 17 sessions.
Phase L session-data Q&A tool-calling — `ask_stream()` now accepts `project_root` param. When user asks about sessions (keywords: session, my last, risk score, etc.), `_fetch_session_context()` reads live session JSON files and injects `[Live Session Data]` with session ID, timestamp, worker, duration, risk distribution, highest risk level, most frequent issue, ergonomic features, and alert count. System prompt updated: removed "no session history" refusal, now tells model to use session data from context. Frontend fallback text updated. Verified: session questions no longer trigger refusal — the assistant answers from real data.


Standing Design Decisions (do not re-litigate without a concrete reason)


Two separate storage systems for recordings (recordings/{worker_id}/{timestamp}/) and session summaries (outputs/sessions/session_{timestamp}.json), linked only by session_id. Decision: keep them separate. This has caused zero real bugs so far; merging them would be a real migration touching Session History, Replay, and Reports simultaneously, on a design question with no concrete problem driving it. Revisit only if a real bug appears from the two systems disagreeing — not for tidiness alone.
Worker ≠ User. users (login/role) and workers (the people being monitored) are separate tables, deliberately.
Legacy sessions (pre-auth) are never migrated or retagged. Unowned, visible to supervisor/safety_mgr/admin, hidden from operator.



Explicitly Out of Scope for the Near Term


Worker identification / face recognition (a good future idea — reframe as "Worker Identity Engine," not "Face ID," and support badge/QR alternatives for consent/privacy reasons — but not before the product track above is done)
Wearable sensor integration
Multi-factory enterprise dashboard
ML-based risk scoring as a replacement for the Context Engine (see Research Track — additional input only, and only much later)



How to Use This Document


Before starting any new phase, re-check CURRENT_STATE.md — has anything changed since this roadmap was last updated?
A phase is not "done" until it has passed real browser verification against the live running server — not a unit test, not a TestClient call, not "should work."
If a task doesn't clearly belong to the current active phase, don't work it opportunistically — write it here instead, under the phase it belongs to.
If someone (a person or an AI session) proposes a large pivot — a full redesign, a new dataset, replacing a core engine — check it against this document first. If the product track isn't done, it waits.