# P0 Re-verification — register vs. code (2026-09-26)

Re-checks every "P0 — must fix for TRL-6/7" item in
`docs/DEEP_AUDIT_REPORT.md:242-253` against the current tree. First pass
was written at `40ae6e0` (4 CLOSED / 3 PARTIAL / 3 OPEN); this revision
adds the Phase-1 fixes on branch `phase1-p0` (`dc04259` P0-6, `89918c8`
P0-8, `e96067d` P0-10, `e34e912` C4 disk guard, `8b3f733` P0-9,
`a5f06cb` P0-7, `3db60bd` P0-3). Each row: verdict + the `file:line`
evidence that supports it. Verdicts: **CLOSED** (fix verified in code),
**PARTIAL** (something shipped, the named gap remains), **OPEN** (gap
still present as written).

| # | P0 (register wording) | Verdict | Evidence (current tree) |
|---|---|---|---|
| 1 | `DEBUG=true` defeats secret gate | **CLOSED** | `82a3231` flipped the default and added boot-refusal (6/6 self-checks); compose no longer defaults DEBUG on |
| 2 | CI 5.5% + broken Docker builds | **CLOSED** | `4a9647a` runs `backend_api/tests` with no `\|\| true`, installs requirements-dev, fixes docker file paths; actionlint clean |
| 3 | TLS not deployed | **PARTIAL** | Overlay mounts the pair and swaps nginx config: `docker-compose.tls.yml:20` (+ `docker-compose.yml:81-82` pointer). Issuance is now automated: `certs/issue_letsencrypt.sh:1` (`issue`/`renew`/`install`, cron line in `certs/README.md`). **Still open:** live certificate issuance against a real domain and a real TLS handshake against a deployed instance — no evidence of either in-repo |
| 4 | Login brute-force unthrottled | **CLOSED** | Per-IP/per-role limiter `backend_api/app/core/rate_limit.py:1`, wired as middleware `backend_api/app/main.py:351`; auth routes delegate to it (`auth.py:43-45`), forensics in `database.py:259-261` |
| 5 | MFA non-functional | **CLOSED** | `bc093f6`: `pyotp` required, fail-closed challenge, single-use pending token, `POST /auth/login/mfa` |
| 6 | Privacy: single retention policy | **PARTIAL** | Phase-1 `dc04259`: one owner `app/services/retention.py:117` (`retention_config()` — sessions/recordings GB cap/audit/alerts at `:124-126`), admin overrides `:82-83`, `run_retention()` applies it `:311-329`; boot logs the EFFECTIVE policy `app/main.py:142-152`; audit files now age-filtered (`audit_log.py:312`, was dead code), alerts SQL-expired (`database.py:563`, default 30 d). **Still open by design:** consent records (`CONSENT_POLICY`) and login throttling are separate policies (mapped in the `retention.py` docstring), and Postgres telemetry rows are not yet pruned |
| 7 | Backup/restore path bugs + plaintext secrets | **PARTIAL** | Phase-1 `a5f06cb`: sessions picked from `deploy/backup.sh:107-111` (root `sessions/` never existed), compose auth DB captured `:89`, `--encrypt` flag `:59` (aes-256-cbc+pbkdf2), restore decrypts `deploy/restore.sh:66-73` and extracts to `outputs/sessions`; host roundtrip tested (plain + `.enc` + wrong-passphrase + full restore). **Still open:** end-to-end drill of the pg_dump/compose-volume/cron paths (deferred to post-soak gates — Agent 2's consolidation window) and encryption is opt-in, not default |
| 8 | Default creds / ephemeral JWT / empty `audit_logs/` | **CLOSED** | `89918c8`: chain key resolution `audit_log.py:55` (env > file > auto-provision), fail-fast at boot `main.py:126` + `audit_log.py:111`; compose mounts the persistent volume and audit dir `docker-compose.yml:52-54,60` (key survives recreation at `/data/audit_hmac.key`); both services hard-require the JWT `docker-compose.yml:41,115` (`:?`); `.env.production.example:16` documents both. 61 tests green incl. `test_audit_hmac_key.py` |
| 9 | Backend image omits Chromium → PDF fails | **CLOSED** | `8b3f733`: browser layer installed `backend_api/Dockerfile:18` (`playwright install --with-deps --only-shell chromium`, previously an explicit skip), every launch failure now maps to HTTP 503 with cause + fix `report_pdf.py:78-83`, tests `backend_api/tests/test_report_pdf.py` (3/3). Image rebuild runs in the post-soak gate (text change only until then) |
| 10 | `/metrics` public + `task_path` NameError | **CLOSED** | `e96067d`: all 7 stats routes gated — `/metrics` carries `dependencies=OPS_TOKEN_DEP` `ops.py:125` (gate `:53-78`: `METRICS_TOKEN` bearer else DEBUG-only → prod fail-closed), health probes stay open by design (`ops.py:7`); token wired `docker-compose.yml:57` + `deploy/k8s/*`. `task_path` NameError already fixed at `yolo_cloud/pose_engine.py:340-345`. 48 tests green incl. `test_ops_token.py` |

## Summary

- **CLOSED: 7 / 10** (1, 2, 4, 5, 8, 9, 10)
- **PARTIAL: 3 / 10** (3, 6, 7)
- **OPEN: 0 / 10**

Everything the register called "must fix for TRL-6/7" now has a verified
code fix; the three PARTIAL rows are all **operational-evidence gaps**
(live TLS handshake, retention consent/telemetry coverage, restore drill),
which is exactly the TRL-7 column of `docs/TRL7_QUALIFICATION_PLAN.md`.

## Rules this document obeys

- Verdicts cite `file:line` from the `phase1-p0` tree, never file length.
- Each Phase-1 verdict is backed by a targeted green test run recorded in
  its commit message; the full gate (backend 425 / cloud 134 / tsc /
  docker build) runs once after Agent 2's soak window ends.
- Safe Claims language untouched; no accuracy claims of any kind.
