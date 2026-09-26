# P0 Re-verification — register vs. code (2026-09-26)

Re-checks every "P0 — must fix for TRL-6/7" item in
`docs/DEEP_AUDIT_REPORT.md:242-253` against the current tree. First pass
was written at `40ae6e0` (4 CLOSED / 3 PARTIAL / 3 OPEN); the second
revision added the Phase-1 fixes (`8067aad` P0-6, `61423d5` P0-8,
`ab9c3e4` P0-10, `d4aecdd` C4 disk guard, `bcf904e` P0-9, `aaf102d` P0-7,
`c7d6cd1` P0-3 — merged via `139f2da`). Synced at `5d71cc0`: follow-ups
`efa8b15` (Postgres telemetry prune), `83aa528` (restore flags + `--yes`
+ hermetic drill), `5d71cc0` (nginx request-time upstream) folded in;
all line cites re-verified against HEAD. Each row: verdict + the
`file:line` evidence that supports it. Verdicts: **CLOSED** (fix verified
in code), **PARTIAL** (something shipped, the named gap remains),
**OPEN** (gap still present as written).

| # | P0 (register wording) | Verdict | Evidence (current tree) |
|---|---|---|---|
| 1 | `DEBUG=true` defeats secret gate | **CLOSED** | `82a3231` flipped the default and added boot-refusal (6/6 self-checks); compose no longer defaults DEBUG on |
| 2 | CI 5.5% + broken Docker builds | **CLOSED** | `4a9647a` runs `backend_api/tests` with no `\|\| true`, installs requirements-dev, fixes docker file paths; actionlint clean |
| 3 | TLS not deployed | **PARTIAL** | Overlay mounts the pair and swaps nginx config: `docker-compose.tls.yml:20` (+ `docker-compose.yml:81-82` pointer). Issuance automated: `certs/issue_letsencrypt.sh:1` (`issue`/`renew`/`install`, cron in `certs/README.md`). Self-signed handshake drilled live: HTTPS 200 + HTTP→301 + `CN=localhost`, request-time upstream `nginx.tls.conf.example:63` (`5d71cc0`); hermetic script `deploy/tls_handshake_drill.sh`. **Still open:** live LE issuance against a real domain — no domain on record |
| 4 | Login brute-force unthrottled | **CLOSED** | Per-IP/per-role limiter `backend_api/app/core/rate_limit.py:1`, wired as middleware `backend_api/app/main.py:351`; auth routes delegate to it (`auth.py:43-45`), forensics in `database.py:259-261` |
| 5 | MFA non-functional | **CLOSED** | `bc093f6`: `pyotp` required, fail-closed challenge, single-use pending token, `POST /auth/login/mfa` |
| 6 | Privacy: single retention policy | **PARTIAL** | `8067aad`: one owner `app/services/retention.py:120` (`retention_config()` — sessions/recordings GB cap/audit/alerts at `:128-129`), admin overrides `:82-86`, `run_retention()` applies it `:315-340`; boot logs the EFFECTIVE policy `app/main.py:142-146`; audit files age-filtered (`audit_log.py:312`), alerts SQL-expired (`database.py:563`, default 30 d); `efa8b15` added Postgres telemetry prune (`postgres.py:392`, 5 tests in `test_postgres_prune.py`). **Still open by design:** consent records (`CONSENT_POLICY`) and login throttling are separate policies (mapped in the `retention.py` docstring) |
| 7 | Backup/restore path bugs + plaintext secrets | **PARTIAL** | `aaf102d`: sessions picked from `deploy/backup.sh:104-109` (root `sessions/` never existed), compose auth DB captured `:89`, `--encrypt` flag `:59` (aes-256-cbc+pbkdf2), restore decrypts `deploy/restore.sh:76` with `--yes` `:60` and extracts to `outputs/sessions` `:155-160`; `83aa528` fixed pg_restore flags (`:134`) and added the hermetic drill `deploy/backup_restore_drill.sh`. Proven: host roundtrip (plain + `.enc` + wrong-passphrase + full restore), `docker compose cp` from a live stack (81 920 B), dry-run clean. **Still open:** timed RTO run; encryption opt-in by design |
| 8 | Default creds / ephemeral JWT / empty `audit_logs/` | **CLOSED** | `61423d5`: chain key resolution `audit_log.py:55` (env > file > auto-provision), fail-fast at boot `main.py:126` + `audit_log.py:111`; compose mounts the persistent volume and audit dir `docker-compose.yml:52-54,60` (key survives recreation at `/data/audit_hmac.key`); both services hard-require the JWT `docker-compose.yml:41,115` (`:?`); `.env.production.example:16` documents both. 6 tests green incl. `test_audit_hmac_key.py` (full-suite isolation fix `bf89009`) |
| 9 | Backend image omits Chromium → PDF fails | **CLOSED** | `bcf904e` + `3d9f316`: browser layer installed `backend_api/Dockerfile:20-21` (`playwright install --with-deps --only-shell chromium` into `/ms-playwright` so the non-root runtime user can exec it), every launch failure maps to HTTP 503 with cause + fix `report_pdf.py:78`, tests `backend_api/tests/test_report_pdf.py` (3/3). Image rebuilt green; in-container render proven as uid 999 (7712 B PDF) |
| 10 | `/metrics` public + `task_path` NameError | **CLOSED** | `ab9c3e4`: all 7 stats routes gated — `/metrics` carries `dependencies=OPS_TOKEN_DEP` `ops.py:125` (gate `:53-78`: `METRICS_TOKEN` bearer else DEBUG-only → prod fail-closed), health probes stay open by design (`ops.py:7`); token wired `docker-compose.yml:57` + `deploy/k8s/*`. Live smoke: 403 without token / 200 with bearer. `task_path` NameError already fixed at `yolo_cloud/pose_engine.py:340-345`. 7 tests green incl. `test_ops_token.py` |

## Summary

- **CLOSED: 7 / 10** (1, 2, 4, 5, 8, 9, 10)
- **PARTIAL: 3 / 10** (3, 6, 7)
- **OPEN: 0 / 10**

Everything the register called "must fix for TRL-6/7" now has a verified
code fix; the three PARTIAL rows are all **operational-evidence gaps**
(live TLS issuance, retention consent scoping, restore-drill RTO),
which is exactly the TRL-7 column of `docs/TRL7_QUALIFICATION_PLAN.md`.

## Rules this document obeys

- Verdicts cite `file:line` from HEAD (`5d71cc0`, post-merge `139f2da`),
  never file length.
- Full gate green at HEAD: backend 453 (448 at merge + 5 prune tests),
  cloud 142, tsc exit 0; docker build + in-container PDF proven. Agent 2
  owns the final re-run after its TRL-8 lane.
- Safe Claims language untouched; no accuracy claims of any kind.
