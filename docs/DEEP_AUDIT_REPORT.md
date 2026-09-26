# ErgoVigilance — Deep Audit Report + TLR (NASA TRL 1–9) Readiness

**Date:** 2026-09-24
**Scope:** Full product audit — every layer, every claim, verified against code.
**Brand decision:** `ErgoVigilance` is canonical (used in `README.md:1`, UI, docs, Docker). `Ergovigilance` (lowercase-v) appears only in `ROADMAP.md:1` + git remote URL. **`Ergovilance-Think` / `ErgoVigilance-Think` appears nowhere in the repo** (verified by grep) — treat as external alias only. Do not rebrand without normalizing remote, docs, Stripe descriptor, SEO.
**Honest positioning (must use externally):** *AI-assisted ergonomic risk screening and decision-support tool. Not a medical device. Not clinically validated. Not yet enterprise-qualified.*

---

## 0. Executive Summary

ErgoVigilance is a **real, end-to-end industrial ergonomics platform**, not a demo script:

> Ordinary camera → pose estimation → biomechanical features → RULA/REBA-informed risk (LOW/MEDIUM/HIGH) → sustained-risk alerts → plain-language guidance → sessions + video replay + PDF/CSV/JSON evidence — no wearables, offline-first by default.

| Dimension | Verdict |
|---|---|
| Product completeness | Strong. Live monitoring, video review/replay, 39 pages, ~100+ backend routes + 36 cloud routes, alerts lifecycle, reports, workers/users, cameras, billing/Stripe, audit, consent, onboarding, ROI, validation page |
| AI core | Dual-core, honest rule-based runtime on-prem + ML-primary cloud. 4-layer temporal smoothing is well-engineered. Multi-person is primary-only on-prem, true ByteTrack on cloud |
| Validation honesty | Mixed. One credible number exists (**87.6% on 500 human frames, LOW/MEDIUM only**), surrounded by 4 other vintages that must never be quoted as product accuracy without qualification |
| Security/privacy | Architecture is serious (JWT+RBAC, middlewares, retention, dual audit) but **5 P0 gaps** block pilot claims: compose `DEBUG=true`, CI 5.5% coverage + broken Docker paths, HTTP-only default, unenforced login throttling, broken MFA |
| Deployment/Ops | Docker Compose 4 services works for demo; TLS/backup/restore/HA are documented but not proven |
| Business/pilot | Best-in-repo sales/pilot kit (`SALES_ONE_PAGER`, `SALES_DECK_3SLIDES`, `PILOT_GUIDE`, `docs/pilot/` intake + consent). Zero active pilots. Pricing + accuracy numbers conflict across docs — fix before quoting |
| Readiness | **Demo 85–88% / Controlled pilot 70–75% / Enterprise 45–55%** |
| **TLR (NASA TRL)** | **TRL 4 met, TRL 5 partial → Overall TRL 4–5.** TRL 6+ not met (no off-dev field test, no pilot shifts, no qualification) |

Top 3 actions before any enterprise claim: (1) reconcile pricing + accuracy numbers, (2) fix P0 security/deploy gates, (3) land one `docs/pilot/`-gated single-station pilot and publish the delta.

---

## 1. Product — What It Is, Who Uses It

### 1.1 One-liner (consistent across `docs/SALES_ONE_PAGER.md:18-20`, `MARKETING_ONE_PAGER.md:12`, `hackathon_idea_submission.md:40-44`)

Continuous posture-risk screening from an ordinary camera, with instant alerts, coaching, and audit-grade reports.

### 1.2 Problem solved (`explanation_ergovigilance.md:50-58`)

Manual RULA/REBA spot audits are point-in-time, observer-dependent, paper-based, non-comparable across stations/shifts. ErgoVigilance makes it continuous, camera-based, evidence-backed.

### 1.3 Users — 4-role RBAC (consistent in code + docs)

| Role | Needs | Can do | Source |
|---|---|---|---|
| Operator / Worker | Is my posture OK? Simple language | Own sessions, own gauge, `/my-posture`, own tips. Cannot see others | `PILOT_GUIDE.md:38-86`, Hindi i18n |
| Supervisor | Which station/worker now? Are alerts rising? | All-worker risk, heatmaps, trends, ack/override, multi-camera grid | `README.md:26` |
| Safety Mgr / EHS | Trends, audit trail, evidence | Resolve alerts, safety/risk/worker PDFs, evidence zip, benchmarks, ROI | `README.md:27` |
| Admin / IT | Users, cameras, health, retention | CRUD users/workers, cameras, retention, deployment, billing, erasure | `README.md:28` |

Implementation: `backend_api/app/core/auth.py:105` JWT + `require_roles`, `ELEVATED_ROLES`, server-enforced 403s. `users` ≠ `workers` by design.

### 1.4 Dual-core business logic (pricing/packaging spine)

| | On-Premise (`backend/` + `backend_api/`) | Cloud (`yolo_cloud/` :8100) |
|---|---|---|
| Pose | MediaPipe 33-kpt, CPU ~15–20 FPS, `ERGOVIGILANCE_NUM_POSES` default 1 max 4, primary-only scored | YOLOv8-pose 17 COCO + ByteTrack, GPU/CUDA, RTSP/FFmpeg |
| Input | USB webcam, upload ≤200 MB | RTSP CCTV (`CAMERA_SOURCES`), no on-site app |
| Data | SQLite + JSON sessions + MP4, local Ollama RAG | Postgres + API-key multi-tenancy, Stripe, webhooks, email/Slack |
| Promise | Privacy-first, free, offline, video never leaves plant | Frictionless scale, 20–100+ cams, central dashboard |
| Limit | 1 `LiveMonitoringService` singleton per backend → multi-cam = multi-process (`OPS_RUNBOOK.md:103`) | `100+ cameras` unverified; `50+ load test` still TODO (`RELEASE_v1.0.0:122`) |

Funnel: **land free on-prem pilot (30-min laptop), expand to paid cloud for CCTV scale.** Correct hybrid per `PRODUCT_ANALYSIS.md:192-216`. Fleet/multi-site explicitly deferred (`ROADMAP.md:96-97`).

---

## 2. Architecture + Data Flow

```text
Camera / Video / RTSP
  → Pose (MediaPipe 33 | YOLOv8-pose 17 + ByteTrack)
  → Features (17 biomechanical + 2 motion)
  → Risk (RULA/REBA rules authoritative on-prem; HGB ML-primary on cloud)
  → Context (task/fatigue/exposure/uncertainty/dwell) → Alerts (cooldowns, lifecycle)
  → FastAPI (auth/sessions/reports/video/workers) → React 19 SPA (39 pages) → PDF/CSV/JSON evidence
```

Live flow: frame → landmarks → angles → task → LOW/MED/HIGH + reasons → dwell check → recommendation → HTTP/WS (`/ws/dashboard`, `/ws/alerts`, `/ws/camera`, MJPEG `/video/`) → skeleton + gauge + timeline. Video flow: upload → `VIDJOB-*` daemon (`video_analysis.py:749`) → same pipeline → replay + risk timeline + burned MP4 (`outputs/video_review/*.mp4`). Reporting: session end → summary → trend/safety/worker PDFs (Playwright, lazy).

---

## 3. AI Core — Verified Deep Dive

### 3.1 Pose: 33 vs 17 confirmed

* On-prem: `backend/services/pose_engine.py:156-162`, `models/MANIFEST.json:5-18`, `MEDIAPIPE_33` in `backend/core/constants.py:62-88` — `pose_landmarker_lite.task`, `RunningMode.VIDEO`.
* Cloud: `yolo_cloud/pose_engine.py:11-22,58-75`, `config.py:18` (`yolov8s-pose.pt`; repo root also has `yolov8s-pose.pt` + `yolo11n.pt`), `COCO_17` in `constants.py:90-106`.
* Shared extractor auto-selects (`features.py:228-229`): `len>=25 → MEDIAPIPE_33 else COCO_17`. YOLO maps `coco→mp` for shared task engine (`yolo_cloud/pose_engine.py:353-359`).
* COCO gap by design: 4 features always `NaN` on YOLO (`wrist_deviation_angle, hand_reach_ratio, finger_spread_ratio, stance_width_ratio` — `train_yolo_*_model.py:38-46`); HGB chosen because it handles `NaN` natively. Must disclose.

### 3.2 Features: “12” is stale — code is 17

`backend/core/constants.py:15-37` `FEATURE_COLUMNS` (verified):

1. `neck_flexion` 2. `trunk_flexion` 3. `left_shoulder_elev` 4. `right_shoulder_elev` 5. `shoulder_symmetry` 6. `alignment_deviation` 7. `knee_angle` 8. `elbow_flexion_angle` 9. `upper_arm_angle_from_vertical` 10. `forward_head_posture` 11. `head_tilt_angle` 12. `wrist_deviation_angle` 13. `stance_stability` 14. `weight_shift_offset` 15. `hand_reach_ratio` 16. `finger_spread_ratio` 17. `stance_width_ratio` + 2 motion (`movement_velocity` deg/s, `wrist_movement_velocity` px/s — `pose_engine.py:280-324`).

Docs say 12 (`README.md:85,286`, `SYSTEM_ARCHITECTURE:75,93`) or 7 (`CURRENT_STATE.md:28`) — **update all to 17** (10 scored + 5 reference + 2 motion) or explicitly “12-scored subset”. Related drift: 13-feature legacy bundles (`MANIFEST.json:33,48`), 19-col task model (17+2 vel), 34-col v3 (19+15 temporal) — never reconciled.

### 3.3 Risk: rule-based authoritative (on-prem), ML-primary (cloud)

* On-prem runtime = deterministic rules, NOT ML. `standard_assessment.py:387-495` `assess_standard_risk()` gated in `pose_engine.py:345-351`: full-body (hips/knees/ankles vis ≥50) → **REBA** (`TABLE_A/B/C`, 2D approx, twist/side-bend omitted); else → **RULA** (legs neutral=1 when invisible). Bands: REBA 1–3 LOW / 4–7 MED / 8+ HIGH; RULA 1–2 LOW / 3–4 MED / 5+ HIGH. `NONE` → legacy `risk_from_features()` fallback. Context engine band-anchors (`LOW=20/MED=50/HIGH=80`) with `standard_cap` (never manufactures HIGH). Calibration/forecaster are explicitly **advisory, never raise** (`risk_calibration.py` docstring, `MANIFEST.json:76,90`). `svm_model.pkl`/`best_model.pkl` are training-only/archived, NOT loaded by API.
* Cloud = opposite: `yolo_cloud/pose_engine.py:328-402` — if `yolo_risk/task_model.pkl` exist, `predict()` wins; else heuristic + `_calculate_risk()` 0–100 + task multiplier.
* Calibration profiles: `RELAXED` default (widened neutrals anti-jitter), `STANDARD` = published breakpoints.

### 3.4 Smoothing: 4 layers (strength)

1. Tier-0 Kalman per-landmark (`kalman.py`, `Q0.05 R4.0`, freeze if vis<0.35).
2. Feature EMA α0.6 (`ERGOVIGILANCE_FEATURE_SMOOTHING`), NaN propagates (no stale HIGH).
3. Task confidence-weighted window size 10, margin>5.0, geometric seated gate never smoothed away + dwell time.
4. Context dwell (`LEVEL_DWELL=10`, strict majority) + `temporal_risk.py` 300-frame window + `alerts/engine.py` cooldowns (high30/critical30/sustained60/rapid90/worsening120, `consecutive_high≥10` → CRITICAL).

### 3.5 Tracking

* MediaPipe: **primary-only.** `NUM_POSES` default 1 max 4, largest-bbox = primary; `compute_person_risks` scores all for display but secondaries NOT fed to context/fatigue/task/alerts (`CURRENT_STATE:202`). No persistent ID.
* YOLO: **true tracking.** ByteTrack (`track_thresh0.5 buffer60 match0.8 min_hits3`) + per-camera thread, `track_id`, per-track cooldown + task engines, `person_count` = max unique. `rtsp_manager.py` FFmpeg bgr24 + ffprobe + backoff (2s×2≤30s, max 10).

### 3.6 Bug found (read-only)

`yolo_cloud/pose_engine.py:346` references undefined `task_path` (`str(task_path) if task_path.exists()`) — `NameError` when shared engine present. Should be `settings.YOLO_TASK_MODEL`.

---

## 4. Validation + Accuracy — The Honesty Matrix (use exactly this)

| Number | Verified source | What it really is | Safe to quote? |
|---|---|---|---|
| **87.6%** | `results/ground_truth_evaluation.json:4022-4068` — acc 0.876, n=500 matched, LOW P1.0 R57.2% F1 72.8% (83/145, 62→MED), MEDIUM P85.1% R100% F1 92.0% (355/355), classes [LOW,MEDIUM], matrix [[83,62],[0,355]] | Human-labeled, single session `recordings\worker-001\20260812…`, labeler `unknown`, nearest-timestamp 1s tol, 213/713 unmatched (30%). **No HIGH validated. Biases MEDIUM (over-warns).** | ✅ Only customer-safe number, always with caveats |
| **94.1% risk / 97.6% task** | `models/yolo_risk_metrics.json` (acc 0.9413 F1 0.9437 n=80454), `yolo_task_metrics.json` (0.9761/0.9766 n=68464), cited `README:38,126-127,237-238`, `RELEASE_v1.0.0:15-16,80-81` | YOLO COCO_17 HGB 5-fold CV on **rule-derived labels** (`rule_risk` + proxy), Gaussian augmentation, final-fit-on-full-X leakage (`train_yolo_risk_model.py:132-148`) | ❌ Never as product accuracy. Label “YOLO holdout, REBA-derived, not human; independent eval pending” |
| **88.6% risk F1 / 86.4% task F1** | `CHANGELOG:75-93`, `RELEASE_NOTES:27-28,55-56`, `DEMO_SCRIPT:145-146`; retrained 1937 rows / 41 videos (800 NaN risk, 119 NaN task), MEDIUM F1 58.3% | MediaPipe **research track, NOT runtime** (runtime is rules per MANIFEST). `RELEASE_NOTES` says “accuracy”, table says F1 — use F1 | ⚠️ Research-only, note MEDIUM weakness |
| **76.9% / 91.8%** | `MANIFEST:33,48,90`, `best_model/svm_metrics` (24558/6140 split, 30698 REBA poses), `risk_calibration_report.md:31` | Honest REBA-labeled holdout (HGB 76.9% vs RF 76.4%); calibration 91.8% advisory | ⚠️ Provenance only, retired from headlines (`DELIVERY_CHECKLIST:24`) |
| Retired | 97.97% circular, 76.9%→dashboard, 63.5% n=96, v2 100% n=780 imbalanced, v3 99.9% synthetic n=14000, upper-body 5.8% collapsed | Documented in `honest_*`, `v2_training`, `upper_body_v2`, `POSE_VALIDATION_REPORT` | ❌ Do not quote |

Also: 5-class (Assembly/Inspect/Lift/Seated/Neutral in CHANGELOG/RELEASE_NOTES) vs 7-class (Neutral/Assembly/Reaching/Lifting-Picking/Inspection/Seated/Walking-Moving in README/YOLO/v3) — pin canonical 7, note retrained 5-label subset. `78K` (`RELEASE_v1.0.0:15`) vs exact 80,454/68,464 — cite exact per-model N.

---

## 5. Backend API (`backend_api/`) — Verified

* **Size:** 50 files in `app/api/` (verified glob: 48 feature + `__init__` + `router.py`); `router.py:99` wires 46 routers under `/api` (+`video_feed`, `audit_log`, `webcam` at root). **100+ `@router.*` decorators verified by grep (truncated at 100)**; ~110+ with remainder + `main.py` `/health / /api/demo-mode`. YOLO adds 36 (`api.py`: cameras×8, dashboard/sessions/alerts, reports×5, models×8, inference, webhooks×4, storage/retention, api-keys×4, WS). So “45+ / 87 / 92 / 112+” across docs are all stale slices — use **~100+ on-prem + 36 cloud**.
* **Auth:** hand-rolled HS256 JWT (`security.py:171`, 8h TTL, stream-token 600s `purpose=stream`), bcrypt + dummy-hash anti-enumeration, `DEBUG=true`→ephemeral secret + warning, `DEBUG=false`→require ≥32ch, reject dev default, fail-fast. `auth.py:105` bearer + DB re-read + stale-role reject + org resolve. Roles seeded operator/supervisor/safety_mgr/admin. MFA TOTP exists (`mfa.py`, `core/mfa.py:185`) but **broken** — see §8.
* **DB:** `db_backend.py:300` SQLite default (`local_auth.db` via `AUTH_DB_PATH` or `backend_api/local_auth.db`) + Postgres pool (min2/max10, `?→%s`, `PgRow`) when `DATABASE_URL~postgres`. `database.py:628` + 5 migrations (`001_initial` … `005_multi_tenant`) + seeds. `postgres.py:434` additive telemetry (`ergo_sessions JSONB`, Timescale opt-in, 30s backoff, NaN→null). Separate `video_analysis_jobs.db` (TTL 30m, crash-mark on restart).
* **Services:** `live_monitor.py:1436` (heart: pose/alert engine, checkpoint recovery), `session_cache.py:133`, `pose_overlay.py:427`, `liveness.py:390`, `worker_faces.py:316`, `retention.py:330`, `evidence_package.py:134`, `report_digest.py:157`, `websocket/manager.py:102` (3 managers, 15s heartbeat/45s stale).
* **Health:** `ops.py:176` `/healthz /readyz ({database,live_service,model_available} 200/503) /metrics (prometheus) /sla /storage /cache /queries /logs /recovery` (no auth, `include_in_schema=False`) + `main.py` `/health` + `core/health.py:141`. Docker HEALTHCHECK→`/healthz`, `WEB_CONCURRENCY=2` (vs single-process session assumption in OPS_RUNBOOK — needs affinity).
* **Security middlewares (`main.py:439`):** CORS→RateLimit (500/60s ×role, `AUTH_MAX=50` defined)→Headers (nosniff/DENY/XSS/Referrer/Permissions, CSP with `unsafe-inline/eval`, HSTS only if enabled)→Logging→Versioning→Validation (422 details, no leak)→RequestID→Sanitization (XSS/SQLi/traversal regex, log-only ≤10 depth)→Compression + SafeJSON. Fail-closed 503 when model/service missing.
* **Retention/audit:** `retention.py` env (30d/30d/20GB/6h) + `config/retention.json` override (currently **365/365/20GB** — overrides env); admin-only `retention.py:40` endpoints; tested (7 tests, tmp-only). Dual audit: DB table (`audit.py:34` safety_mgr+) + HMAC-chained file (`audit_log.py:282`, 50MB rotate, 365d) + `audit_log.py:93` verify/stats/export — but `audit_logs/` **empty**, no compose volume, `AUDIT_HMAC_KEY` **ephemeral per process** (unverifiable after restart), `cleanup_old_logs` never scheduled.
* **Tests:** **54 files in `backend_api/tests/`** (verified glob) covering smoke/critical/fail-closed/demo/analytics/audit/users/settings, sessions/video/overlay/recorder/checkpoints/live-payload/cameras, risk/ML (reba/calibration/forecaster/thresholds, HGB, task v2, manifest, drift, perf, benchmark), privacy/retention/evidence/stream-tokens/liveness/faces/migrations/postgres. Plus root `tests/` 2 files/23 funcs. **CI only runs root tests** — see §9.

---

## 6. Frontend (`ui_posture/`) — Verified

* **Stack:** React 19.0.1 + TS ~5.8 + Vite 6.2.3 + Tailwind v4, `App.tsx` + `main.tsx`, `vitest` jsdom, `Dockerfile` node:20-alpine→nginx:alpine, `nginx.conf:80` SPA + `/api→backend:8000 /cloud-api→8100 /ws` + `client_max_body_size 200m`. Root `package.json` is only pptxgenjs+playwright (report tooling). `frontend/` = empty `__pycache__` — ignore.
* **Pages — truth 39/40:** **39 files in `src/pages/`** (verified glob) = 39 lazy pages = 40 `<Route>` (1 redirect `/trends→/reports?view=risk-trend`). Public 6 (`/ /request-pilot /validation /login /forgot-password /signup`) + authed Layout 32 + outside-Layout 2 (`/pricing /status`). All 11 requested pages exist (Dashboard 859L, LiveMonitoring 1113L, VideoReview 1370L largest, Reports 1091L, Workers 671L, ModelDashboard 417L admin, ROI 285L, SystemHealth 438L admin, Onboarding 418L+wizards, Validation 212L presents 87.6%, Pricing 344L). Doc counts 31/34/19/6 are stale vintages — **use 39/40**.
* **Components 63, hooks 14:** `common/` 38 (AlertCenter/Toast, AIInsights, DigitalTwin, ExportsCenter, ProductTour, …), `cards/` 6, `charts/` 6 (RiskGauge, RiskHistory, NeckTrunkTrend), `timeline/` 4, `layout/` 5, `Layout.tsx:281` (auth+role+onboarding guard, tour), `Sidebar.tsx:187` (3 sections, role-filtered). Hooks: `useDashboard` (poll `refreshInterval` 30s + WS merge, sessions once), `useSettings` (localStorage + `GET/PUT /api/settings`), `useTheme`, `useWebSocket` (backoff 3s×2ⁿ≤48s), `useAlerts*`, `useRecommendations`, `useHistory`, `useLiveTimeline`, etc. State = Context only (no Redux/Query). i18n en/hi/zh. `config/index.ts` empty stub (old `USE_MOCK` docs obsolete).
* **API client:** `apiClient.ts:28` (Bearer, 401→clear+`AUTH_INVALID_EVENT`, friendly 503/500/404) + `dashboardService.ts:229` facade + `ApiDashboardRepository.ts:99` (`API_BASE=/api`, 15 methods), native fetch. Vite proxy `/api /health /healthz /readyz→8000`, `/video/` MJPEG fix, `/ws→ws`, `/cloud-api→8100/api`.
* **Auth flow:** `AuthContext.tsx:152` localStorage `ergovigilance_auth` → exp decode → `POST /api/auth/login|/demo` → rolePaths single source for Layout/Sidebar/tour. Demo amber banner.
* **Tests/build/perf:** `vitest.config` jsdom, `smoke.test.tsx:190` 7 tests + `interactions:73` 2 tests + fixtures 19 endpoints + setup. Scripts: `dev :3000`, `build vite build` (**no tsc** — `lint: tsc --noEmit` separate), `tsconfig` ES2022, `skipLibCheck`, no explicit `strict`. 39 lazy chunks in `dist/`; single Suspense spinner; 30s poll + WS; `dist/index.html` 4668B. Gaps: no bundle analyzer/manualChunks, no React-Query cache, no SW/offline, external Fonts+Plausible, `dist/` ships stray `Hackathon_MVP.pptx videos/ images/ results/` — strip.
* **Stale docs to quarantine:** `ui_posture/README_ARCHITECTURE.md` (mock era), `FRONTEND_ASSET_AUDIT.md` (6 static pages, “no router/WS/tests” — all since built).

---

## 7. YOLO Cloud Core (`yolo_cloud/`, :8100) — Verified

`api.py` 36 routes + WS `/ws`, `pose_engine.py` YOLOv8-pose + ByteTrack + ML inference, `ingestion.py:126-276` per-camera thread (timeline every 5th frame), `rtsp_manager.py:54-309` FFmpeg bgr24 + ffprobe + backoff, `model_registry.py` version/save/rollback/export/import, `reports.py` PDF/CSV daily/weekly, `training/` 10 scripts (`build_yolo_features` merges 30K REBA + dataset_final + keypoints JSON + real_data + Gaussian noise_std2.0 doubling N; labels = `rule_risk` + proxy → fidelity-to-rules, not human), `Dockerfile` GPU+CPU, `tests/` 24 claimed. Org API-key auth + tenant isolation + webhooks HMAC + email/Slack. Fix `task_path` NameError (§3.6).

---

## 8. Security, Privacy, Compliance — Claim vs Reality

| Claim (`SECURITY_QUESTIONNAIRE`, `DPA_TEMPLATE`, `CHANGELOG`) | Reality (verified) |
|---|---|
| AES-256 at rest + TLS 1.3 | SQLite/PG/recordings/backups plaintext; TLS opt-in only, no `certs/` (verified missing), `ENABLE_HSTS=false` (`security_headers.py:25`); prod `nginx.conf:206` (HSTS/CSP/rate 30r/s + 5r/m login, OCSP) **not used by compose**; image uses `nginx.conf:80` HTTP-only + permissive `connect-src` |
| MFA/TOTP + backup codes | `pyotp` **not in `requirements.txt`** (verified) → `verify_totp` **fail-open True** (`core/mfa.py:96`), generate errors; `login()` never challenges; backup `sha256(concat)` unverifiable |
| Rate limiting per-IP/role | `rate_limit.py` 500/min ×role exists but `/auth/* /search /settings /health /docs` **exempt**; `auth.py:94` “Rate limiting removed”; `LOGIN_MAX 5/10 per 15m` defined, never checked → brute-force + bcrypt ~400ms DoS |
| SOC2 II, immutable HMAC log | Ephemeral HMAC key, empty `audit_logs/`, no volume, SQLite deletable, no auditor — feature-complete only |
| GDPR consent/portability/erasure | Consent (`consent.py:221`, policy v1.0 2025-01-15, 90d) any-user can grant/deny any worker (no `require_roles`), `consent_proof None`, no audit, withdraw flips only (no wipe trigger), expiry never checked by `live_monitor`, export queries wrong table (`worker_consent` vs `consent_records` → always 0). Paper form + PDF gen not linked to DB. Deletion (`privacy.py:189` admin, traversal-guarded) wipes `recordings/<id>` + alerts only — **misses session JSONs (admitted in `PRIVACY.md:95`), worker row, consents, PG rows, jobs DB, face embeddings, backups**. Retention conflict: `PRIVACY 30d` vs `consent 90d` vs `form 30d keypoints/1yr scores` vs `questionnaire 90d` vs `retention.json 365d` |
| Trivy/pip-audit/npm audit | No job in `ci.yml` (verified) despite claim |
| RPO 24h/RTO 30m, daily backups | `deploy/backup.sh` wrong paths (`sessions` vs `outputs/sessions`), `DB_PORT 5432` vs compose 5433, plaintext `.env` in tar, no checksum/offsite/cron; `restore.sh` `pg_restore -c -if` typo, `rm -rf sessions/ recordings/` wrong, can clobber live `.env`, no stop/integrity check |
| DPA/ISO | Template `[Insert]` placeholders, no SCCs executed; ISO correctly `planned` — do not oversell. DPO phone `+1-XXX`, `security@ergovigilance.com` placeholders |

Strengths (real): bcrypt, parameterized queries, 4-role RBAC + 403s, Security/Sanitization/Validation/RequestID middlewares, Prometheus `/metrics`, Grafana `deploy/grafana/`, K8s `NetworkPolicy` default-deny, K8s `secretsKeyRef` (never commit filled), `.gitignore` covers `.env/db`, `security.py:29-62` correctly rejects <32ch/known-default when `DEBUG=false`. **Undone by compose `DEBUG=true` (`docker-compose.yml:36,94`) + weak `POSTGRES_PASSWORD` default + `verify.yml` dev JWT + `TRUST_PROXY_HEADERS=true` + Windows service `0.0.0.0:8000` + docs-published `admin@example.local/AdminPass123!` (`DEPLOYMENT.md:93-99`) — rotate.**

Also: backend `Dockerfile` skips Playwright/Chromium → PDF fails in compose; `WEB_CONCURRENCY=2` vs single-process sessions; K8s `ingress.yaml:15-32` duplicate annotation (WS overwrites HSTS/CSP); K8s `:latest` unpinned, `readOnlyRootFilesystem:false`; `/metrics /docs /openapi.json` public via ingress — gate/allowlist.

---

## 9. Deployment, Testing, Docs

### 9.1 Compose + env (verified `docker-compose.yml:129`, `.env.production.example:138`)

4 services: `db` (pg16-alpine, loopback `5433`, weak defaults), `backend` (loopback `8001→8000`, `DEBUG=true` bug, empty JWT default, `SESSIONS_DIR=/data/sessions`, `DATABASE_URL` constructed, healthcheck `/healthz`), `frontend` (`8080:80` **not loopback-bound**, TLS commented), `cloud-core` (loopback `8100`, `DEBUG=true`, YOLO/RTSP env, GPU commented). `verify.yml:73` self-contained but drifted (no cloud-core, no sessions mount, dev JWT, never in CI). Root `.env`/`demo` = `DEMO_MODE=true` only → insecure defaults. Prod example complete (`DEBUG=false`, strong-secret gen, ports, 30/30/20GB/6h, SMTP/Slack/Stripe blank-disabled, Ollama, `CAMERA_SOURCES`).

### 9.2 CI (verified `.github/workflows/ci.yml:115`)

4 jobs: `backend` py3.13 → `pytest ../tests/` (root only); `cloud-core` → `pytest ../tests/ -k cloud || true` (always green); `frontend` node20 → `tsc` + `build`; `docker` (master only) builds 3 images — **broken**: frontend `file: Dockerfile` (no root Dockerfile; should be `ui_posture/Dockerfile`), cloud `context+file` double-prefix, py 3.13 vs image 3.12-slim. No audit/Trivy/gitleaks/CodeQL/coverage/compose-verify. **CI gates ~23/418 tests (~5.5%); 395 backend tests never gate.** Fix: run `backend_api/tests/`, fix paths, drop `|| true`, add pip-audit/npm audit, pin images.

### 9.3 Docs inventory (35 files in `docs/` verified)

Current/useful: `SYSTEM_ARCHITECTURE_PRESENTATION.md:28KB` (canonical arch), `DELIVERY_CHECKLIST.md:7.6KB` (QA 2026-08-13 truth), `PRIVACY.md:95L` (honest offline-first + per-worker-wipe admission), `PILOT_GUIDE.md:170L` (plain-language), `OPS_RUNBOOK.md` (prereqs/backup/TLS/scale), `CURRENT_STATE.md:12.5KB` (2026-09-01 snapshot; page count 34 now stale), `DEPLOYMENT.md` root + docs (pilot 4c/8GB → prod 8c/16GB → ent 16c/32GB+RTX), `SALES_ONE_PAGER` + `SALES_DECK_3SLIDES` (best, DRAFT + claim-checklist + $0/2wk offer — use for pilots), `PRODUCT_DEMO_SCRIPT` 2-min + `DEMO_SCRIPT` 5-7-min (shoot-ready; 7-min mixes 88.6/86.4/87.6 — reconcile), `pilot/` intake + deployment + `WORKER_CONSENT_ONEPAGER` (triage 0-10 gate ≥7, cap 2 active, slouch-test, rollback), `MARKETING_ONE_PAGER` (priced + vs Intenseye; update 88.6/86.4 → ground-truth framing), `SECURITY_QUESTIONNAIRE/DPA/PRIVACY/DEPLOYMENT/OPS_RUNBOOK` (enough for pre-screen; fill placeholders). Archived: `pose_estimation_status*.md`, `IMPROVEMENT_PLAN_STATUS.md` — do not quote.

### 9.4 Business: pricing + ROI conflicts (fix before quoting)

Canonical UI: Starter Free (MIT, 4 USB) / Cloud $299/mo per 10 cams up to 20 ($239 annual) / Enterprise custom 50+ (`PricingPage.tsx:10-83,185-190`, `MARKETING_ONE_PAGER:39-40`, `RELEASE_NOTES:100-102`). Conflicts: `yolo_cloud/README:27-29` per-cam $99/79/59 (3–6× different math); `RELEASE_NOTES:83` diagram $299/10 vs table $299/20; `SELLABLE_ASSESSMENT:241-244` stale $299/3 + $799/10; `PMF_90DAY:34-35` $300–600/cam/mo unfirmed; sales pilot `$0/2wk` disconnected from Pricing page (correct for pilot). ROI `$42k/injury` (`ROIAnalytics:53`), `$20B MSD`, `40% reduction`, `2-hour ROI` are benchmarks, `injuriesPrevented=highRisk*0.15` heuristic — label estimates (Pricing FAQ does). Stripe checkout exists (`billing.py:59-218`, `PricingPage:112-132`) but needs live keys; fallback `/request-pilot`.

---

## 10. Readiness Percentages (honest)

| Stage | % | Rationale |
|---|---|---|
| **Demo** | **85–88%** | Live skeleton + gauge + alerts + video review + replay + PDF + `DEMO_MODE` + validation page. Deduct for count drift + accuracy-vintage drift |
| **Pilot (controlled, 1 site / 1–2 cams / consented)** | **70–75%** | Matches `explanation:542-545` (70–80%) and `PRODUCT_ANALYSIS:11` (60–70% sellable). Code done; **site smoke is the gate**. Frame as screening aid only |
| **Enterprise (multi-site, 50+ cams, SLA)** | **45–55%** | No fleet, no SSO/LDAP, singleton scaling, no HA/backup proof, no real-TLS test, no 50-cam load, no clinical validation, no reference customer (lower than `explanation:544` 55–65% because `CURRENT_STATE:200-211` + `ROADMAP:96-102` explicitly defer fleet/isolation/24-7) |

Pilot can start in 1–2 days once a qualifying site (score ≥7) signs. Do not promise multi-worker-per-camera isolation, 24/7, real-cert TLS, or fleet.

---

## 11. TLR Assessment — NASA TRL 1–9

> TRL = Technology Readiness Level. Rate the **operational on-prem screening system** (not research tracks).

| TRL | Definition | Verdict | Evidence |
|---|---|---|---|
| 1 Basic principles | RULA/REBA + pose observed | ✅ Met | `knowledge/rula_reba_reference.md` (McAtamney & Corlett 1993, Hignett & McAtamney 2000), `hackathon_idea_submission:89-96` |
| 2 Concept formulated | Camera→pose→features→risk→alert→report | ✅ Met | `explanation:364-402`, `PRODUCT_ANALYSIS:21` pipeline |
| 3 Proof of concept | Lab demo, webcam + skeleton + risk | ✅ Met | Live Monitoring + YOLO Demo + video review (`README:83-120`) |
| 4 Lab validation | Component + integration test | ✅ Met | 54 backend test files + 22 legacy scripts, CI green slice, Docker PDF/persistence verified, **87.6% on 500 human frames** (`DELIVERY_CHECKLIST:15-26`, `CURRENT_STATE:185-196`) |
| 5 Relevant-environment validation | Realistic data, single setup | ⚠️ **Partial** | 99–133 real sessions, 30,698-pose REBA tuning, framing/uncertainty/forecast shipped (`ROADMAP:77-93`). But one room/person, no factory dust/glare/PPE/occlusion/shift test; single-person default; YOLO minority zero-recall (`CURRENT_STATE:200-211`) |
| 6 Prototype in relevant environment | Factory-floor demo | ❌ Not met | P0-6/P0-7 never off dev machine; no ≥2-cam RTSP field test; no real-cert TLS; no 24/7 run (`ROADMAP:63-71`, `DELIVERY_CHECKLIST:42-49`) |
| 7 Operational prototype | Pilot shifts, EHS sign-off | ❌ Not met | Zero pilots active, zero paid assessment, zero ergonomist sign-off; PMF R1–R5 unstarted (`PMF_90DAY:41-48`) |
| 8 Qualified system | Hardened, certified, repeatable | ❌ Not met | No SOC2/ISO cert (planned), no HA/backup proof, no SSO/fleet/billing-live, no multi-site qualification |
| 9 Proven operational | Sustained deployment | ❌ Not met | No reference customer, no sustained injury-reduction evidence |

**Overall: TRL 4+ (TRL-4 met, TRL-5 partial) → report as TRL 4–5.** “Production-ready” (`RELEASE_NOTES:5`, `CHANGELOG:12`) overclaims — use “pilot-ready candidate”.

**Path:** TRL-6 = one consented single-station pilot + day-one smoke (live feed → deliberate slouch → alert → report+MP4) + 2-week shift data. TRL-7 = paid assessment + ergonomist review + repeat site. TRL-8 = pen-test + DPIA/DPA + SOC2 evidence + HA/backup drills + PG retention + SBOM/Trivy + pinned images + load gates (p95<500ms, <5% errors).

---

## 12. Gaps Register (prioritized)

### P0 — must fix for TRL-6/7

1. Compose `DEBUG=true` defeats secret gate — `${DEBUG:-false}` + require `.env` (`docker-compose.yml:36,94` vs `.env.production.example:12`).
2. CI 5.5% + broken Docker builds — run `backend_api/tests/`, fix `Dockerfile` paths (`ci.yml:91,111`), drop `|| true`, add pip-audit/npm audit.
3. TLS not deployed — mount `certs/` + fix `nginx.tls.conf.example` (missing `cloud-api/`, headers), `ENABLE_HSTS=true`, Let's Encrypt; fix K8s duplicate annotation.
4. Login brute-force unthrottled — enforce lockout + nginx `login 5r/m` in compose path; fix `TRUST_PROXY` spoof on `0.0.0.0`.
5. MFA non-functional — add `pyotp` to requirements, enforce challenge in `login()`, fix backup codes (`core/mfa.py:96` fail-open).
6. Privacy incomplete — single retention policy (30 vs 90 vs 365 vs 1yr), clean PG rows + backups, fix `worker_consent` vs `consent_records`, `withdraw`→wipe or document, gate `live_monitor` on `granted`.
7. Backup/restore path bugs + plaintext secrets — fix `outputs/sessions`, `5433`, `pg_restore` flags; encrypt + quarterly restore drill.
8. Default creds in docs + ephemeral JWT + empty `audit_logs/` — rotate seeds, persist `AUDIT_HMAC_KEY` + mount volume, schedule cleanup.
9. Backend image omits Chromium — PDF fails; include or document optional.
10. `/metrics /docs` public — gate/allowlist. Fix `task_path` NameError (`yolo_cloud/pose_engine.py:346`).

### P1 — TRL-8 qualification

Pen-test, DPIA + signed DPA/SCCs, SOC2 evidence, backup encryption/offsite + RTO drill, PG retention + crypto-erasure, consent proof + audit trail, HPA/load (`deploy/load_test.py`, `tests/load_test.py`, `endurance_test.ps1`), SBOM + Trivy + secret-scan, pinned images + `readOnlyRootFilesystem:true`, frontend unit tests, strip `dist/` strays, quarantine stale docs, reconcile all counts (17 features; 39/40 pages; ~100+36 endpoints; 7 task classes; F1 vs accuracy).

---

## 13. Safe Claims Sheet (copy-paste)

* ✅ “AI-assisted ergonomic risk screening system, RULA/REBA-informed, 17 biomechanical features + task/fatigue/exposure/uncertainty/smoothing.”
* ✅ “87.6% agreement with human assessors on 500 labeled frames (LOW P100%/R57%, MEDIUM P85%/R100%; no HIGH validated; single worker/room; tends to over-warn MEDIUM).”
* ✅ “Ready for controlled pilot evaluation (1 site, 1–2 cameras, consented, supervised, non-critical decision support).”
* ❌ Never: “prevents injuries / clinically certified / fully enterprise-ready / works in every factory / 94–97% product accuracy / replaces safety officers.”

---

## 14. 30-Day Next Steps

**Week 1:** Professor/EHS review of scoring + thresholds; clean stale claims (features/pages/endpoints/classes/F1); decide pilot station.
**Week 2:** Collect diverse videos; label frames + task clips (frame-accurate join, real labeler ID, include HIGH); re-run eval with unmatched reporting.
**Week 3:** Tune thresholds for LOW-recall vs alert-fatigue; camera-angle/lighting matrix; retrain task on real clips.
**Week 4:** Controlled pilot (consent + signage + LAN/`AUTH_JWT_SECRET`/`CAMERA_SOURCES`); day-one smoke; 2-week report; limitations + TRL-6 evidence pack.

---

## Appendix A. Verified Counts (2026-09-24)

* Pages: **39 files** (`ui_posture/src/pages/*.tsx` glob) → 40 routes.
* Backend API files: **50** (`backend_api/app/api/*.py` glob); decorators **100+ verified (truncated)** + YOLO **36** (`yolo_cloud/api.py` grep).
* Backend tests: **54 files** (`backend_api/tests/test*.py` glob); CI runs root `tests/` (2 files/23 funcs) only.
* Docs: **35 files** (`docs/*.md` glob) + `pilot/ screenshots/`.
* Models: `yolo_risk` acc 0.9413 F1 0.9437 n=80454; `yolo_task` 0.9761/0.9766 n=68464; ground-truth 0.876 n=500 matrix [[83,62],[0,355]] classes [LOW,MEDIUM].
* Config: compose `DEBUG=true` ×2, `requirements.txt` no `pyotp`, `ci.yml` broken paths ×2 + `|| true`, `certs/` + `backups/` absent, `Thinks` branding zero hits.

## Appendix B. Key File Pointers

* Runtime heart: `backend_api/app/services/live_monitor.py:1436`, `backend/services/pose_engine.py`, `backend/services/standard_assessment.py`, `backend/services/features.py`, `backend/core/constants.py:15-37`
* Auth/DB/health: `backend_api/app/core/security.py:171`, `auth.py:105`, `database.py:628`, `db_backend.py:300`, `postgres.py:434`, `api/ops.py:176`, `app/main.py:439`
* Privacy/retention/audit: `api/consent.py:221`, `api/privacy.py:189`, `services/retention.py:330`, `core/audit_log.py:282`, `docs/PRIVACY.md:95`
* Cloud: `yolo_cloud/api.py`, `pose_engine.py:328-402,542-686`, `ingestion.py:126-276`, `rtsp_manager.py:54-309`, `training/build_yolo_features.py:272-290`
* Frontend: `ui_posture/src/App.tsx`, `pages/LiveMonitoring.tsx:1113`, `VideoReviewPage.tsx:1370`, `ValidationPage.tsx:212`, `PricingPage.tsx:100`, `services/apiClient.ts:28`
* Deploy/CI: `docker-compose.yml:36,94`, `nginx.conf:206`, `ui_posture/nginx.conf:80`, `deploy/backup.sh:60-74`, `restore.sh:107-113`, `.github/workflows/ci.yml:91,111`, `.env.production.example:138`
* Evidence: `results/ground_truth_evaluation.json:4022-4068`, `models/MANIFEST.json`, `models/yolo_*_metrics.json`, `docs/DELIVERY_CHECKLIST.md`, `docs/CURRENT_STATE.md:200-211`, `ROADMAP.md:63-71`

*End of report — single source for pilot and TRL decisions. Fix P0, land one site, republish validation delta; that moves TRL more than any code.*
