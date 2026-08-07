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

## 1. Quick wins — CI & polish (small, safe)

- [ ] **Bump GitHub Actions versions** to targets running Node.js 24
  (`actions/checkout@v5`? `actions/setup-python@v6`, `actions/setup-node@v5` — verify the
  latest major that clears the deprecation warning). CI still fails nothing today, but the
  warning is a future breakage. *Accept: no Node-20 deprecation annotation on the next run.*
- [ ] **Add a CI status badge** to the top of `README.md`
  (`https://github.com/rianhussain007/Ergovigilance-/actions/workflows/ci.yml/badge.svg`).
  *Accept: badge renders and shows green.*
- [ ] **README status section** — replace the "known-stale scripts" note (obsolete since the
  suite is green) with a current status table + link to this file.
  *Accept: README accurately reflects CI green + done items.*

## 2. Broken dev scripts (not in CI → rot silently)

These were never in the `test_*.py` loop, so CI stays green while they are broken:

- [ ] **`scripts/generate_trend_report.py`** — imports `TrendAnalysis` from
  `backend.services.trend_analysis`; that class no longer exists (module now exposes
  `analyze_risk_trend`). Rewrite against the function API (same pattern as
  `test_trend_analysis.py`). *Accept: script runs on a sample session JSON.*
- [ ] **`scripts/generate_safety_report.py`** — imports `SafetyReport` from
  `backend.services.safety_reporting`; module is now `safety_report.py` exposing
  `analyze_safety`. Rewrite against it. *Accept: script runs on a sample session JSON.*
- [ ] **`scripts/smoke_test_model.py`** — imports `annotate_pose`, `detect_pose_from_bgr`
  from `backend.services.pose`, which was **deleted** in the pivot. Either rewrite against
  `backend.services.pose_engine` (single-frame detect) or delete. *Accept: no import error.*
- [ ] **`start_backend.py`, `start_frontend.py`, `inspect_exports.py`** — hardcoded
  `C:\GGS_intership\posture_analysis` paths; same portability bug we just fixed in
  `test_alert_persistence.py`. Make repo-relative. *Accept: no drive-letter literals.*
- [ ] **`frontend/app.py`** (legacy Streamlit entry point) — imports the deleted
  `backend.services.pose`. README documents it as out-of-product; decide **delete or archive**
  it (and `streamlit_app.py`, `packages.txt`, `handoff_pose_estimation/`, `Week4/`) so the
  repo stops carrying dead entry points. *Accept: decision made + executed.*

## 3. Test isolation & repo hygiene

- [ ] **`test_alert_persistence.py` writes to the real dev DB** — it calls
  `init_local_database()` with no env override, so it pollutes
  `backend_api/local_auth.db` on every run (it inserted ~1400 `ALT-TEST` rows during this
  session's CI replica). Point `AUTH_DB_PATH` at a temp file (as `backend_api/tests/conftest.py`
  does) or reset the DB after the run. *Accept: running it leaves the dev DB untouched.*
- [ ] **Reset/clean the dev `local_auth.db`** — currently holds 1416 alert rows from test
  runs; decide whether to wipe alerts history or reset the file (gitignored, so no CI impact).
  *Accept: decision made.*
- [ ] **Stray runtime artifacts at repo root** — `backend_log.txt`, `frontend_pid.txt`,
  `vite_log.txt`, `vite.pid`, `*.log`, `server_output.txt` etc. were never gitignored
  (`.gitignore` only covered `.log`/`.pid` extensions and the `_archive` dirs). Remove from
  tracking + extend `.gitignore`. *Accept: `git status` clean after a dev run.*

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

- [ ] **Multi-person tracking** — MediaPipe supports `num_poses > 1`, but the pipeline
  (`PoseEngine`, `LiveState`, per-worker sessions, analytics) is single-person. Decide scope:
  track N workers in one frame (new per-person state model) vs. per-camera sessions.
  *Accept: decision doc + scoped plan.*
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
