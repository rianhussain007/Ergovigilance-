# End-to-End QA Report — 2026-10-02 (re-verified 2026-10-03)

**Scope:** full-stack end-to-end QA of the running product — browser journeys (Playwright/Chromium),
API journeys against the live backend, both backend pytest suites, the frontend suite, and every
quality gate — on the development environment (backend `:8000`, frontend `:3000`, on this host).

**Verdict: no blocker failures anywhere, and all four findings are now fixed.** The re-run on
2026-10-03 after the F1–F4 + O1 fix pass is **59/59 automated journey checks** (API 32/32,
browser 27/27, both with 0 findings), blockers all green, both backend suites green, all gates
green. Findings F1–F4 and observation O1 are marked ✅ resolved below with evidence; the two
remaining observations (O2) are documented at the end.

---

## 1. Summary table

| Suite | Result | Evidence |
|---|---|---|
| API journeys (live backend) | **32/32** · all blockers · 0 findings (re-run 2026-10-03) | `results/qa-pass/e2e_api_results.json` |
| Browser journeys (Playwright) | **27/27** · all blockers · 0 findings (2 consecutive clean runs) | `results/qa-pass/e2e_browser_results.json` |
| Backend pytest | **exit 0, 0 failures** (`python -m pytest backend_api/tests`) | run 2026-10-03 |
| Cloud pytest | **181 passed** (124s), exit 0 | `results/qa-pass/e2e_cloud_pytest.log` |
| Frontend vitest | **278/278** in 15 files, exit 0 (incl. new claims + camera-feed guards) | run 2026-10-03 (F5) |
| TypeScript | `tsc --noEmit` clean | run 2026-10-03 |
| UX guards | 141 files checked, **0 violations** | `ui_posture/scripts/ux_guards.mjs` |
| Session persistence script | **30/30 checks** (incl. new O1 stub checks) | `python scripts/test_session_persistence.py` |
| Bundle budget | 62 chunks, 1607 kB raw / **456 kB gzip**, entry 40 kB gzip — within budget | `ui_posture/scripts/check_bundle_budget.mjs` |
| Backend server log (re-run) | **0 errors, 0 tracebacks** | `results/uvicorn_e2e.log` |

**Combined journeys: 59/59 pass · findings 0 (was 52/56 with 4 findings).**

---

## 2. What was run, and how to reproduce

```bash
# Backend + cloud suites (development env)
cd backend_api && python -m pytest tests          # 478 passed
cd <cloud suite dir> && python -m pytest          # 181 passed

# Live API journeys (backend must be running: DEBUG=true python -m uvicorn app.main:app --port 8000)
python scripts/e2e_api_journeys.py                # 32/32, writes results/qa-pass/e2e_api_results.json

# Browser journeys (frontend on :3000)
node scripts/e2e_browser_journeys.mjs             # 27/27, writes results/qa-pass/e2e_browser_results.json

# Frontend gates (from ui_posture/)
npx tsc --noEmit && npx vitest run
node scripts/ux_guards.mjs && node scripts/check_bundle_budget.mjs
```

Both journey scripts self-clean: they create their own QA users/pilot requests and sweep them
afterwards, so repeated runs don't pollute the user table.

---

## 3. API journey matrix (live backend, 32 checks — 32 pass)

Auth & session integrity:

| ID | Check | Result |
|---|---|---|
| J1 | `GET /health` is 200 | ✅ |
| J2 | Demo login returns token with `operator` role | ✅ |
| J3 | Anonymous `GET /api/cameras` → 401 | ✅ |
| J4 | Garbage bearer token → 401 | ✅ |
| J8a/J8b | Fresh-account login 200 · bad password → 4xx (not 200) | ✅ |

RBAC (anonymous / operator / admin matrix across 8 endpoints):

| Endpoint | Expected | Result |
|---|---|---|
| `/api/cameras` (supervisor+) | 401 / 403 / 200 | ✅ |
| `/api/reports/digest` (supervisor+) | 401 / 403 / 200 | ✅ |
| `/api/users` (admin) | 401 / 403 / 200 | ✅ |
| `/api/audit-log` (admin/safety_mgr) | 401 / 403 / 200 | ✅ |
| `/api/manager` (safety_mgr+) | 401 / 403 / 200 | ✅ |
| `/api/deployment` (admin) | 401 / 403 / 200 | ✅ |
| `/api/alerts` (any authenticated) | 401 / 200 / 200 | ✅ |
| `/api/session/status` (any authenticated) | 401 / 200 / 200 | ✅ |

J5/J5b additionally verify that the 403 body **explains the missing permission** rather than
leaking a stack trace — passes.

Commercial & lifecycle:

| ID | Check | Result |
|---|---|---|
| J7 | Signup → `plan=pilot`, `max_cameras=4`, `max_workers=50`, admin user | ✅ |
| J7dup | Duplicate signup email → 409 | ✅ |
| J10 | Admin `GET /api/reports/digest` → 200 JSON | ✅ |
| J11a–e | Session start → status → stop → list, **and the stopped session appears in history** (O1 regression guard) | ✅ all |
| J12a/J12b | Anonymous pilot request → 201; admin can list it | ✅ |
| J13 | Unknown session id → 404 | ✅ |
| J14 | `GET /api/billing/config` → 200 (`stripe_enabled=None`, trial config) | ✅ |
| J15a | Admin `DELETE` **own** account → 409 self-lockout guard | ✅ |
| J15 | Admin DELETE sweeps every OTHER QA E2E user (list re-checked, `list_status=200`) | ✅ |
| J15db | SQLite sweep removes leftover `qa-e2e-%` users + QA/Dup orgs (`remaining=0`) | ✅ |

---

## 4. Browser journey matrix (Playwright/Chromium, 27 checks — 27 pass)

Marketing funnel:

| ID | Check | Result |
|---|---|---|
| B1 | Landing renders with exactly one `h1` | ✅ |
| B2/B4 | Top bar has exactly one Validation link; navigates to `/validation` | ✅ |
| B3:* | All 5 landing anchors (`#solutions`, `#technology`, `#how-it-works`, `#deployment-options`, `#command-center`) exist | ✅ |
| B5 | Validation page states the 87.6% figure | ✅ |
| B6 | Validation carries the LOW/MEDIUM + 500-frame qualifier | ✅ fixed (F1) |
| B7 | Pricing shows all three tiers | ✅ |
| B8 | Annual toggle updates to $239/mo | ✅ |
| B8b | Starter exclusions rendered (RTSP/CCTV listed) | ✅ |
| B8c | Annual toggle button has an accessible name | ✅ fixed (F2) |
| B9 | Pilot-form fields programmatically labeled | ✅ fixed (F3) |
| B10 | Empty required submit is blocked client-side (stays on page) | ✅ |
| B13 | No broken images on landing | ✅ |

Auth & app:

| ID | Check | Result |
|---|---|---|
| B11 | Bad password → HTTP 4xx **and** visible error message | ✅ |
| B12a | "Try Demo" lands in the app with DEMO MODE disclosure | ✅ |
| B12t | Guided product tour appears on demo, closes on Escape | ✅ |
| B12b | Sidebar nav → Settings renders with `h1` | ✅ |
| B12c | Sidebar nav → Live Monitoring works | ✅ |
| B12d | Sign-out control exists, works, returns to `/login`, clears auth keys | ✅ |

Claims & console:

| ID | Check | Result |
|---|---|---|
| B14:/ , /pricing, /validation | No banned accuracy vintage (94.1/97.6/88.6/86.4/76.9) on any marketing page | ✅ all |
| B15 | Zero page errors and unexpected console errors across the walk | ✅ |

---

## 5. Findings — all 4 RESOLVED (2026-10-03)

**F1 — Validation page states bare "87.6% overall accuracy" (B6). ✅ RESOLVED.**
`/validation` presented the accuracy figure without the required LOW/MEDIUM + 500-labeled-frame
qualifier and without the HIGH-class-not-validated note. **Fix:** the hero subtitle now reads
*"agreement with human assessors on 500 labeled frames"* (frame count read from
`ground_truth_evaluation.json`), with a scope line — *LOW/MEDIUM risk only, HIGH not yet
validated, single-site, screening aid not a medical device* — plus the same scope restated in
the explanatory paragraph. **Guard:** `claims.test.ts` gained
`qualifies the dynamically rendered accuracy headline on ValidationPage`, which asserts the
scope copy is present and that "overall accuracy" framing is gone. **Evidence:** B6 ✅,
vitest 276/276. This also closes **T1 (HIGH) in WEBSITE_TRUTHFUL_AUDIT.md**.

**F2 — Annual pricing toggle has no accessible name (B8c). ✅ RESOLVED.**
**Fix:** `type="button" role="switch" aria-checked={annual} aria-label="Bill annually (save 20%)"`
on the `button.w-12.h-6` switch. **Evidence:** B8c ✅, B8 (behaviour) ✅, ux_guards 0 violations.

**F3 — Pilot request form: 6/6 fields unlabeled (B9). ✅ RESOLVED.**
**Fix:** every field now has a matching `id` (`pilot-companyName`, `pilot-contactName`,
`pilot-email`, `pilot-role`, `pilot-numStations`, `pilot-message`) and `<label htmlFor>`,
including the `<select>`. **Evidence:** B9 ✅ ("all labeled"), B10 ✅ (submit behaviour intact).

**F4 — QA cleanup sweep deleted 1 of 2 expected users (J15). ✅ RESOLVED.**
Root cause: `delete_user` answers **409 "Cannot delete your own account"**
(`backend_api/app/api/users.py`), so the acting QA admin can never delete itself, and a stale
`qa-e2e-*` admin from a crashed run can't delete the new one either. **Fix in
`scripts/e2e_api_journeys.py`** (test hygiene, no product change): the sweep now (a) asserts
the self-delete → 409 guard explicitly as **J15a**, (b) sweeps every *other* `qa-e2e-*` user via
the API and fails if the list call itself fails, and (c) finishes with **J15db**, a direct
SQLite sweep of `backend_api/local_auth.db` for leftover `qa-e2e-%` users and `QA E2E %`/`Dup
Org` organisations. **Evidence:** J15a ✅ (`Cannot delete your own account`), J15 ✅
(`list_status=200`), J15db ✅ (`users_removed=1 orgs_removed=1 remaining=0` — it also cleaned
the leftovers the two crashed pre-fix runs had left behind).

**F5 — Live Monitoring showed a phantom LIVE session over a dead feed. ✅ RESOLVED (2026-10-03).**
A screenshot showed the header/page rendering `LIVE SESSION SESH-…` with a growing elapsed time
(`91m 44s`), `TASK: UNKNOWN`, `RISK INDEX 0 / LOW`, `SYSTEM CONFIDENCE 0%`, a broken feed whose
alt text (`live camera feed`) was painted into the frame — while the toolbar button still read
**Start Monitoring** (`/api/session/status` said *not* active). Root cause: a start/stop race — a
slow background camera-init thread finished *after* the session was stopped and left
`camera_status = "active"` while `session_active` was already `False`. `_build_dashboard` read
`camera_status` directly (ignoring `session_active`), so `/api/dashboard` reported LIVE while
`/api/session/status` and `/api/video/feed` correctly reported inactive (the 503 → broken `<img>`).
Secondary defects: the feed badge showed a hardcoded `29.97` FPS; `SessionInfo` silently dropped
`cameraReconnecting` (Pydantic drops extras); and `/api/dashboard`'s 10 s response cache delayed
start/stop transitions. **Fixes:** (1) `_build_dashboard` gates the whole session block on
`state.session_active` — the same flag as `/api/session/status`/`is_running()`
(`backend_api/app/repositories/live.py`); (2) a session-generation guard in `_init_and_start`
aborts a superseded init so it can never resurrect `camera_status="active"`
(`backend_api/app/services/live_monitor.py`); (3) `SessionInfo.cameraReconnecting` +
`LiveStatus.fps` schema fields, with real FPS wired to the feed badge; (4) `CameraPanel` drops the
broken `<img>` and shows an honest "Camera feed unavailable" state after retries exhaust;
(5) `RiskGauge`/`SystemConfidenceTile`/`RiskTrajectoryTile` say "no data yet" while active but
frame-less instead of faking a 0/LOW reading; (6) `invalidate_cache()` on session
start/stop/demo-login. **Evidence:** new backend `tests/test_live_dashboard_phantom_session.py`
(2 tests) and frontend `src/test/cameraPanelFeedFailure.test.tsx` (2 tests); live HTTP repro —
running session → dashboard + status agree (real fps ≈ 12); immediately after stop →
`cameraStatus="disconnected"`, `id=""`, agree; start→stop-during-init race + 8 s settle → **no
phantom LIVE**. Browser spot-check: idle screen renders "No active session" / "NOT MONITORING" /
"Camera not in use" / "— FPS" with no broken alt text; a demo session renders the live feed with
no contradictions.

---

## 6. Probe observations (outside the automated matrix)

**O1 — Sessions in which no person is ever detected leave no history record. ✅ RESOLVED.**
`save_session_summary()` returned `None` when `total_frames == 0`
(`backend/services/session_analytics.py`), and `SessionAnalytics.update()` only counts frames
where `person_detected` is true — so a started→stopped session on a camera with nobody in
frame vanished: no history entry, and a stop response of "Summary: not saved". **Fix:**
`save_session_summary(..., allow_empty=True)` (used **only** by `LiveMonitoringService.stop_session`)
persists a stub payload flagged `"no_person_detected": true` with `total_frames: 0`; every
other caller keeps the old skip semantics (checkpoints still require frames, recovery still
skips them). The stop response now says *"Session ended. Recorded, but no person was
detected — saved with no risk data."* **Consumer guards so stubs never skew analytics:**
`/api/analytics`, `/api/reports/risk-trend` and `report_digest` exclude 0-frame stubs from every
risk average/weight/trend (digest reports them separately as `no_person_session_count`);
`worker_summary` lists them but keeps them out of the risk trend; the session repository maps
them to task **"No person detected"** and risk **"NO DATA"**, and SessionHistory /
WorkerSelfView / the session-detail drawer render that as neutral grey — never green LOW.
**Evidence:** J11e ✅ (stopped session listed), `python scripts/test_session_persistence.py`
30/30 incl. new stub checks, backend pytest exit 0, and a live probe: stop → history shows
`SESH-… | No person detected | NO DATA`.

**O2 — Backend process died mid-run during two pre-fix E2E attempts; not reproducible once warmed. ✅ MITIGATED/UNDER OBSERVATION.**
On 2026-10-03 the uvicorn process exited twice while the API journey hit the session lifecycle
~10–15 s after a cold boot (no Python traceback in `results/uvicorn_e2e.log` — a native/teardown
crash, not an application exception). The identical sequence (demo login → start → stop →
history) ran cleanly on a fully warmed server, and two consecutive full API runs then passed
32/32 with the server still up. Likely a cold-start race between the async startup loaders
(assistant corpus, person/face detectors) and the first live session. **Operator note:** let
the backend warm ~30 s (or hit `/health` until stable) before exercising session lifecycle in
QA. Worth a dedicated look if it recurs — it predates the F1–F4/O1 changes and no product
change has been made for it.

---

## 7. What this run does *not* cover

- **Real cameras / RTSP** — no camera hardware on this host; J11 exercises the lifecycle with
  the synthetic/demo source. The 4 public RTSP URLs are never claimed to work.
- **Browser matrix** — Chromium only (Playwright bundled); no Firefox/WebKit/real devices.
- **Non-functional at scale** — no load test, no multi-tenant soak; bundle/gates are the perf
  proxy (456 kB gzip total).
- **External-only items** (unchanged, tracked in the audit): operator usability testing,
  counsel review of Terms/Privacy, pen-test, RUM from a real deployment.
- Nothing was committed to git; all evidence files live under `results/qa-pass/` (gitignored)
  and the two scripts are untracked (`scripts/e2e_api_journeys.py`,
  `scripts/e2e_browser_journeys.mjs`).

---

## 8. Bottom line

The product passes a genuine end-to-end gauntlet: **59/59 automated journey checks
(API 32/32 + browser 27/27, 0 findings), all blocker checks, green backend + frontend suites**
(478-test backend suite exit 0, 278/278 vitest, 181 cloud), with clean typecheck, zero guard
violations, within budget, and a server log with zero errors. All four findings from the first
run (F1 truthfulness, F2/F3 accessibility, F4 test hygiene) and the zero-person-session gap (O1)
are fixed, guarded by new assertions, and re-verified live. The one open item is O2 (a
cold-start process exit seen twice before the fixes) — documented with an operator workaround,
not yet root-caused.
