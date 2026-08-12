# Ergovigilance — Remaining Tasks (Roadmap)

Status as of **2026-08-07**: CI is green for the first time (run `31190381521`).
Everything below is what still needs doing, roughly in priority order. Each item
has an acceptance criterion so it is unambiguous when done.

## ✅ Already done (context)

- **P0 (#1–#6)** — mandatory `AUTH_JWT_SECRET` outside debug, login rate-limit/lockout,
  fail-closed `deps.py`, retention, session/recording isolation, auth hardening.
- **P1 (#7–#15)** — runnable pytest suite + smoke tests, DB migrations, observability
  (`/healthz`, `/readyz`, `/metrics`), startup hardening, auth hardening, build hygiene,
  TLS/reverse-proxy, model governance (MANIFEST + verify script), privacy (delete-worker-data
  endpoint + `docs/PRIVACY.md`).
- **Legacy test suite** — all 22 `scripts/test_*.py` green; wired into CI.
- **Wrist-movement velocity** — emitted in px/s so the Reaching classifier works in production.
- **CI fixes** — `httpx2` for starlette TestClient; portable `test_alert_persistence.py`.
  Backend (pytest + legacy + pip-audit) and Frontend (lint + build + audit) both green.

---

## 1. Quick wins — CI & polish (small, safe) ✅ done 2026-08-07

- [x] **Bump GitHub Actions versions** to targets running Node.js 24
  (`checkout@v7`, `setup-python@v7`, `setup-node@v7`). Clears the Node-20 deprecation warning.
- [x] **Add a CI status badge** to the top of `README.md`.
- [x] **README status section** — replaced the stale notes (23→36 tests, "10 legacy scripts"→
  "22-script suite") and linked `ROADMAP.md` from the CI section.

## 2. Broken dev scripts (not in CI → rot silently) ✅ done 2026-08-07

These were never in the `test_*.py` loop, so CI stays green while they were broken:

- [x] **`scripts/generate_trend_report.py`** — rewritten against `analyze_risk_trend`;
  verified on the real `outputs/sessions` (74 sessions → `reports/trend_report.md`).
- [x] **`scripts/generate_safety_report.py`** — rewritten against `analyze_safety`;
  verified on a real session JSON → `reports/session_report.md`.
- [x] **`scripts/smoke_test_model.py`** — **deleted** (decision: it exercised the archived
  `best_model.pkl` SVM on the deleted kaggle images and imported the removed
  `backend.services.pose`; the production path is `pose_engine` with full test coverage).
- [x] **`start_backend.py`, `start_frontend.py`, `inspect_exports.py`** — repo-relative
  paths (no drive-letter literals). `run_backend.bat` fixed to serve `backend_api`
  (`app.main:app` instead of the deleted `backend.main`).
- [x] **Legacy Streamlit entry points removed** — `frontend/`, `streamlit_app.py`,
  `packages.txt`, `run_frontend.bat`, `.streamlit/` deleted (decision: they imported deleted
  pre-pivot modules and could not run; README documented them as out-of-product and git
  history retains them). **Kept by decision:** `handoff_pose_estimation/` and `Week4/` —
  self-contained research artifacts, not broken entry points.

## 3. Test isolation & repo hygiene ✅ done 2026-08-07

- [x] **`test_alert_persistence.py` no longer touches the dev DB** — sets `AUTH_DB_PATH` to
  a throwaway temp file before importing `app.core.database`. Verified: dev DB alert count
  unchanged (1414) across runs.
- [x] **Dev `local_auth.db`** — kept as-is (the ~1414 rows are real dev-session data; the
  `ALT-TEST` rows this session added were purged). No wipe.
- [x] **Stray runtime artifacts** — verified already untracked and covered by `.gitignore`
  (`*.log`, `*.err`, `*.pid`, `queryex`, `auth_tokens_verify.json`, the `backend_*/server_*/vite_*`
  txt files). No further action needed.

## 4. Validation that needs hardware/runtime (cannot be done headlessly)

- [ ] **Live-demo validation of the Reaching/wrist-velocity fix** — with a webcam, confirm
  Reaching fires on a real reach (~150 px/s wrist movement) and does **not** false-positive
  during idle fidgeting (reviewer-flagged watch-out; the smoothing window should anchor it).
  *Accept: documented observation, thresholds tuned if needed.*
- [ ] **Full-stack E2E smoke** — `docker compose up`: backend `/readyz` green with the live
  service up, frontend serves, one camera session produces a session JSON + recording +
  alerts, and the delete-worker-data endpoint works. *Accept: end-to-end checklist passes.*
- [ ] **TLS proxy check** — mount `nginx.tls.conf.example` with real certs and confirm
  HTTPS + HTTP→HTTPS redirect + the 200 MB upload path. *Accept: curl -k over 443 works.*

## 5. P2 — product decisions (investigate → decide → implement)

The original pivot investigation deferred these as product decisions, not code bugs:

- [x] **Multi-person foundation (Tier 3, partial)** — `PoseEngine` now reads
  `ERGOVIGILANCE_NUM_POSES` (default 1, up to 4), selects the PRIMARY person (largest
  bbox) for scoring, and reports `person_count` in the live payload/timeline. Per-worker
  session isolation and analytics aggregation remain the follow-up (new per-person state
  model). *Accept: primary-scored pipeline + person count in UI.*
- [x] **Framing / pose-quality intelligence (Tier 3)** — `backend/services/framing_quality.py`
  auto-detects profile view / cropped body / occlusion, emits "reposition camera" guidance
  and a quality score, and produces per-joint angle uncertainty. Wired into the live
  payload, timeline, demo panel, and the Live Monitoring framing card.
- [x] **Uncertainty-aware risk bands (Tier 3)** — `ContextIntelligenceEngine._score_feature`
  scores P(rule violated) via the per-joint sigma from framing quality instead of hard
  cutoffs (soft ~25/75 at boundaries vs. hard 0/100 snap), killing boundary-flip
  sensitivity at the root. Legacy hard scoring preserved at sigma=0.
- [x] **Per-joint risk forecast (Tier 3)** — `RiskForecaster.predict_per_joint` projects
  next-window mean angle per joint from the recent window trend, honest
  `insufficient_data` guard below 15 frames.
- [x] **Temporal task smoothing** — already shipped (confidence-weighted sliding window in
  `TaskRecognition.detect_task`). Retraining on real labeled footage remains a pilot-time
  item (needs `capture_task_clips.py` ground truth).
- [ ] **Remote fleet management** — multi-camera/multi-site monitoring through the API
  (today one `LiveMonitoringService` singleton per backend). Decide: N instances per backend,
  per-site deployments, or central fleet API. *Accept: decision doc + scoped plan.*
- [ ] **Clinically-validated thresholds** — current feature thresholds and the RULA-informed
  score are heuristic; the flagged bias/privacy review needs real-world validation
  (ergonomics study) for production claims. Decide whether to publish as "research-grade" or
  pursue validation. *Accept: documented threshold provenance + validation plan.*

---

## Suggested order

1. Section 1 quick wins (one small commit).
2. Section 2 broken scripts + Section 3 hygiene (one commit, verified against the fresh-env
   container replica used for the CI fixes).
3. Section 4 on the user's machine (hardware required).
4. Section 5 decisions (each needs a short decision doc before any implementation).
