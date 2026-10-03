# TRL-8 Qualification Evidence

**TRL-8 status: IN-REPO GATES QUALIFIED 2026-10-02 (battery run
`20261002T051101Z`: 14 pass, 0 fail, 0 blocked, 2 opt-in skips); external
gates listed and open.** This pack is the evidence for the in-repository half of
`docs/TRL8_9_QUALIFICATION_PLAN.md` §2 (the register's P1 column,
`DEEP_AUDIT_REPORT.md` §12). It does **not** close TRL-8 — four of the nine
P1 items need a vendor, a lawyer, a site or a cluster — and it does not
touch TRL-9, which is gated on a paid site and three months of operation.

**Screening aid, not a medical device.** Every number below is measured on
this host and sourced to a file on disk; nothing is projected, and each
section states what is **NOT MEASURED** so no row reads as more than it is.

## 0. How to regenerate all of this

```bash
# repo battery (suites, static gates, count reconciliation)
python scripts/qualification/run_qualification.py --write-docs

# + environment-dependent evidence (drills, load; the load row needs a
#   reachable backend at --backend-url, default http://127.0.0.1:8000)
python scripts/qualification/run_qualification.py --with-drills --with-load --write-docs

# full mode also runs the multi-stream soak
python scripts/qualification/run_qualification.py --mode full --with-scans
```

Outputs (gitignored, never committed):

```
outputs/qualification/<UTC stamp>/qualification_report.json   # machine-readable
outputs/qualification/<UTC stamp>/qualification_report.md     # human-readable
outputs/qualification/<UTC stamp>/logs/<check id>.log         # raw log per check
```

Exit code is 0 **only** when every executed check passed; `BLOCKED` (missing
prerequisite, unreachable backend) counts as failure so an unproven
criterion cannot exit green. The harness also refuses to run if the
traceability matrix cites a check that does not exist or a file that is
gone, and re-derives every quoted test count from the suites it just ran.

## 1. Machine and scope

| Fact | Value |
|---|---|
| Host | Windows 10 (Git Bash toolchain), 8 logical cores, no GPU |
| Python | 3.13 |
| Cloud engine | `yolov8s-pose.pt`, CPU inference |
| Load at battery start | recorded per run in `qualification_report.json → host_load` |

**In scope for this pack:** test/demonstration evidence that can be produced
from this repository on one machine.

**NOT in scope:** any claim of capacity, fleet scale, HA, multi-site,
GPU throughput, penetration-test status, DPIA/SOC2 status, or a signed
customer. Those are named in §5 and §6 rather than approximated.

## 2. Battery results

*Three consecutive runs. Both early runs went red, and every failure was
real — they are written up in §4. Run 3 is the clean re-run after the
fixes, and it is the run this table quotes.*

| Run | UTC stamp | Verdict |
|---|---|---|
| 1 | `20260928T071850Z` | 9 pass / 5 fail — load-test crash, stale doc counts, two wrong assertion strings (all fixed) |
| 2 | `20260928T073654Z` | 12 pass / 2 fail — cold lazy-chunk timeout + a harness count-parser artifact (both fixed) |
| 3 | `20261002T051101Z` | **14 pass / 0 fail / 0 blocked / 2 opt-in skips — QUALIFIED** |

| Check | Criterion | Status | Measured (run 3) |
|---|---|---|---|
| `backend-suite` | C4 | PASS | **478 passed, 1 skipped, 1 deselected** (473 s) |
| `cloud-suite` | C4 | PASS | **181 passed** (102 s) |
| `erasure-ops` | TRL8-4 | PASS | erasure + privacy suites pass (28 s) |
| `frontend-typecheck` | TRL8-7 | PASS | `tsc --noEmit` exit 0 (34 s) |
| `frontend-unit` | TRL8-7 | PASS | **106 vitest tests pass, 0 failed** (20 s) |
| `frontend-build` | TRL8-7 | PASS | production build exit 0 (26 s) |
| `reconnect-drill` | TRL8-5 | PASS | kill/reconnect recovery (5.8 s) |
| `backup-restore-drill` | TRL8-3 | PASS | **RTO 4 s**, all five stages pass |
| `load` | TRL8-5 | PASS | **20/20 workers authenticated**, 1 314 req, 0 failed, **61.3 rps**, p95 **379 ms** — see §4.5 |
| `supply-chain-gates` | TRL8-6 | PASS | 6/6 assertions |
| `pentest-scope` | TRL8-1 | PASS | scope pack assertions hold |
| `privacy-pack` | TRL8-2 | PASS | DPA/privacy endpoints present |
| `pilot-pack` | TRL9-1/2/5 | PASS | ledger + tracker + case template present |
| `doc-counts` | TRL8-8 | PASS | 10 quoted counts match — backend 478 / cloud 181 / frontend 106 / total 765 |
| `scans` | TRL8-6 | opt-in | `--with-scans` (gitleaks + Trivy config, pinned images) |
| `soak` | TRL8-5 | opt-in | `--with-soak` / `--mode full` |

Reports: `outputs/qualification/<stamp>/qualification_report.{md,json}`;
raw per-check logs in the run's `logs/` directory.

Run 3 ran on a box that was **not** quiet (83.7 % CPU at battery start —
browser, IDE and a local model server were up; recorded in the report's
`host_load`). It still went green, which is the point: the frontend suite
no longer depends on cold-chunk transform speed (§4.2).

**Opt-in checks** (kept out of run 3 on purpose, so the main report stays
the executed-gate record), supplementary run
`outputs/qualification/optin/20261002T053535Z`:

- `soak` — **PASS**. Compute mode, 2 concurrent streams × 46 s through the
  real engine (`scripts/soak_cloud.py`): **clips truncated 0** (6 saved),
  10 distinct tracks, 0 ID switches, scoring p95 404 ms against the 500 ms
  budget (4 of 260 frames over), CPU mean ~5.5 cores, RSS ~766 MB. This is
  a single-host, short-window sizing number — not a stability claim; the
  4 h soak and the RTSP variant still have to run on site.
- `scans` — **not executed**: the Docker daemon is not running on this host,
  so `--with-scans` would report BLOCKED. The supply-chain gates are
  verified declaratively instead (pinned gitleaks / Trivy / SBOM steps in
  `.github/workflows/ci.yml`, check `supply-chain-gates` 6/6); CI is where
  the real engines run.

## 3. TRL-8 register — honest status per P1 item

The generated matrix with file-level implementation references lives in
**`docs/TRL8_TRACEABILITY.md`** (regenerated by the harness; do not hand-edit).
Summary:

| # | P1 item | Status | What closes the rest |
|---|---|---|---|
| 1 | Pen-test + remediation | EXTERNAL-PENDING | Vendor execution; scope pack ready (`docs/PENTEST_SCOPE.md`) |
| 2 | DPIA + signed DPA/SCCs, SOC2 | EXTERNAL-PENDING | Lawyer + audit; templates/endpoints ready |
| 3 | Offsite backup + timed RTO drill | PARTIAL-INREPO | Offsite replication is an operator target; **drill + RTO measured here** |
| 4 | PG retention + crypto-erasure | CLOSED-INREPO | — (backup-archive lifecycle is an operator policy) |
| 5 | HPA / load qualification | PARTIAL-INREPO | 50-camera / horizontal scale needs a cluster + feeds |
| 6 | SBOM + Trivy + secret-scan, pinned images, read-only root | CLOSED-INREPO | — (scan is a snapshot; vuln feed drifts) |
| 7 | Frontend unit tests | CLOSED-INREPO | — |
| 8 | Stale-doc quarantine + count reconciliation | PARTIAL-INREPO | Automated for the listed phrasings; broader doc sweep is manual |
| 9 | Pilot accuracy re-measure → Safe Claims edit | SITE-DEPENDENT | Ergonomist-labelled pilot sample |

## 4. What the red runs found (and what was done about it)

The harness is only worth its name if it can fail. Runs 1 and 2 failed, and
every failure was real; run 3 is green only after each was fixed.

1. **`deploy/load_test.py` crashed on Windows after the test had already
   run.** The summary uses box-drawing glyphs; the console codec is cp1252,
   so `print(results.summary())` raised `UnicodeEncodeError` and the whole
   run was lost. Fixed by reconfiguring stdout/stderr (`errors="replace"`) —
   the numbers are no longer thrown away at the last line.
2. **The frontend smoke suite timed out on a cold lazy chunk.** In run 1
   `renders the login page and signs in to the dashboard` failed under load;
   run 2 reproduced it and the log root-caused it: the first test waited its
   10 s budget for the code-split dashboard chunk while Vite was still
   transforming it (the file took 40 s; the same navigation passed in
   927 ms once warm, and the DOM at failure held only the toast portal).
   Fixed by pre-warming the five route chunks this file navigates to in
   `beforeAll` with a generous hook timeout, so each test's timeout measures
   app behaviour, not transform speed. The assertions are unchanged — still
   106 tests, still the 10 s `waitFor`. Standalone the first test now runs
   in 748 ms; in the run-3 battery the whole suite takes 20.4 s.
3. **Five stale numbers were live in the docs** (cloud 170 → 181, README
   badge 754 → 765, totals 754 → 765). Found by `doc-counts`, fixed in
   `README.md` and `docs/CURRENT_STATE.md`, and the gate now re-checks them
   from the measured suites on every run.
4. The harness itself had the same class of bug it hunts: an explicit `-q`
   on top of `pytest.ini`'s `-q` became `-qq`, which suppresses the
   `N passed` line, so the count could not be parsed. Its backend command is
   now exactly CI's.
5. **The load gate was a false PASS.** Run 2 reported "20 users, 0 failed",
   but 10 of the 20 workers never logged in: every worker comes from
   127.0.0.1 and the per-IP auth throttle admits 10 auth calls per 60 s, so
   half the workers exited before sending a single request. The rps figure
   described 10 users, not 20. Fixed twice over: `deploy/load_test.py` now
   records and prints `workers_started` / `workers_authenticated`, and the
   harness **fails** any load row where fewer workers authenticated than
   were requested. Run 3 was executed with `RATE_LIMIT_AUTH_MAX` raised on
   the backend it measured — documented here, not silent: 20 simulated
   users share one IP. The shipped default stays 10/60 s, and a load run
   against the default throttle now fails loudly (10/20) instead of
   reporting a quiet half-load. Run 3: **20/20
   authenticated, 1 314 requests, 0 failed, 61.3 rps, avg 196 ms, p95
   379 ms, p99 2 174 ms.**
6. **`doc-counts` reported four "stale" counts that were not stale.** The
   run-2 frontend suite was red; vitest prints `Tests  1 failed | 105
   passed (106)`, and the old parser's fallback matched the *file* line
   instead (`Test Files  1 failed | 7 passed (8)`), comparing 7 against the
   docs' 106. Fixed: the parser reads only the `Tests` line (handling the
   `failed | passed` form), and the gate now refuses to compare a count
   whose source suite did not pass, reporting it as not comparable instead
   of stale. Run 3 re-derived all 10 quoted counts and they match.

**Separately re-verified in this session (cloud path, not part of the
battery):** hard-killing the cloud core now reaps its ffmpeg decoders — the
pre-fix core left an orphan behind, the post-fix core left zero processes
(Windows job object, `yolo_cloud/rtsp_manager.py`). RTSP live ingest,
posture scoring and dead-stream error reporting were re-checked end to end
through the admin UI.

## 5. TRL-9 lean bar — what remains and who can close it

TRL-9 is *proven in operational environment*. None of the five bullets below
can be produced by a repository change; the honest position is that the
product is **TRL-8-ready**, not TRL-9.

| # | TRL-9 bar | Status | In-repo support ready | What only the site/business can supply |
|---|---|---|---|---|
| 1 | 1 paid site converted, contract filed | BUSINESS-DEPENDENT | intake tracker, consent one-pager, pricing | a signature |
| 2 | 3 months continuous operation, §4.4 ledger unbroken | SITE-DEPENDENT | `scripts/pilot_metrics.py` ledger collector (tested) | elapsed time in a real workplace |
| 3 | Zero data loss (`clips_truncated_total == 0`) | PARTIAL-INREPO | moov/idx1 guard, disk guard, soak counters | 3-month window on the site's storage |
| 4 | 1 clean in-place upgrade with tested rollback | SITE-DEPENDENT | `docs/UPGRADE_RUNBOOK.md`, compose versioning | a live instance with real data to upgrade |
| 5 | Published case study, guardrails + permission | BUSINESS-DEPENDENT | `docs/pilot/CASE_STUDY_TEMPLATE.md` | customer permission and publication |

## 6. NOT MEASURED — do not quote as done

- Pen-test: **not executed** (scope pack only).
- DPIA / DPA / SCC / SOC2: **not signed, not audited**.
- Fleet scale: no 50-camera run, no HPA, no multi-host; the load row is
  single-host and CPU-only.
- GPU: absent; no GPU throughput or memory number exists.
- Pilot accuracy: no new figure. The only customer-safe accuracy is
  **87.6% LOW/MEDIUM on 500 human-labelled frames**; the cloud engine has
  **no accuracy claim**; HIGH is **unvalidated**.
- Site operation: no deployment, no operator usability record, no
  ergonomist agreement.
- Offsite backup: the drill is a hermetic local sandbox restore; no remote
  destination has been exercised.
- Vulnerability scanning: a snapshot, advisory feed; not an attestation.

## 7. Standing rules carried forward

- Safe Claims discipline from `docs/TRL7_QUALIFICATION_PLAN.md` §6 applies
  unchanged: screening aid, never a prevention/clinical/enterprise-ready
  claim; no accuracy number outside the 87.6% LOW/MEDIUM figure.
- One SHA per item; `file:line` cites.
- Frozen records are not rewritten: `docs/P0_REVERIFICATION.md` and
  `docs/TRL7_QUALIFICATION_PLAN.md` are dated evidence, so the count gate
  deliberately excludes them.
