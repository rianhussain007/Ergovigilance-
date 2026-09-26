# P0 Re-verification — register vs. code (2026-09-26)

Re-checks every "P0 — must fix for TRL-6/7" item in
`docs/DEEP_AUDIT_REPORT.md:242-253` against the current tree (16 commits
since that register was written). Each row: verdict + the `file:line`
evidence that supports it. Verdicts: **CLOSED** (fix verified in code),
**PARTIAL** (something shipped, the named gap remains), **OPEN** (gap
still present as written).

| # | P0 (register wording) | Verdict | Evidence (current tree) |
|---|---|---|---|
| 1 | `DEBUG=true` defeats secret gate | **CLOSED** | `82a3231` flipped the default and added boot-refusal (6/6 self-checks); compose no longer defaults DEBUG on |
| 2 | CI 5.5% + broken Docker builds | **CLOSED** | `4a9647a` runs `backend_api/tests` with no `\|\| true`, installs requirements-dev, fixes docker file paths; actionlint clean |
| 3 | TLS not deployed | **PARTIAL** | Overlay exists: `docker-compose.tls.yml:1` + `docker-compose.yml:76-77` (mount `certs/`, `ENABLE_HSTS` path) + `certs/README.md`. **Still open:** live certificate issuance (Let's Encrypt) and a real handshake against a deployed instance — no evidence of either in-repo |
| 4 | Login brute-force unthrottled | **CLOSED** | Per-IP/per-role limiter `backend_api/app/core/rate_limit.py:1`, wired as middleware `backend_api/app/main.py:338`; auth routes delegate to it (`auth.py:43-45`), forensics in `database.py:259-261` |
| 5 | MFA non-functional | **CLOSED** | `bc093f6`: `pyotp` required, fail-closed challenge, single-use pending token, `POST /auth/login/mfa` |
| 6 | Privacy: single retention policy | **OPEN** | Policy still scattered: audit logs 365 d (`app/core/audit_log.py:35`), DB default 90 d (`db_backend.py:282`), recordings 30 d (`storage_manager.py:31`), sessions/alerts read separately (`app/api.py:1052-1053`); no single settings key; consent-record model unverified |
| 7 | Backup/restore path bugs + plaintext secrets | **PARTIAL** | `backup.sh:3` / `restore.sh:6` exist; JWT now compose-required (`docker-compose.yml:41` `:?` gate). **Still open:** `./outputs/sessions` remains a host bind-mount (`docker-compose.yml` service volume), restore has not been drilled end-to-end, backups unencrypted |
| 8 | Default creds / ephemeral JWT / empty `audit_logs/` | **OPEN** | `AUDIT_HMAC_KEY` falls back to a per-boot random key (`app/core/audit_log.py:38` — HMACs unverifiable across restarts) and is **not set anywhere in `docker-compose.yml`**; no `audit_logs` volume mount; `AUTH_JWT_SECRET` required at `docker-compose.yml:41` but empty-default at `:104` (second service) |
| 9 | Backend image omits Chromium → PDF fails | **OPEN** | `backend_api/Dockerfile:4` explicitly skips Playwright/Chromium; PDF generation in-container therefore unproven (matches the register's "include or document optional" — neither done) |
| 10 | `/metrics` public + `task_path` NameError | **PARTIAL** | `/metrics` still unauthenticated: `app/api/ops.py:93` (`@router.get("/metrics")`, no auth dependency; docstring `ops.py:9` states health probes are intentionally open — `/healthz`, `/readyz` are fine, `/metrics` is a disclosure decision not yet taken). The `pose_engine.py:346` `task_path` NameError **appears fixed** — guarded `joblib.load` inside try/except (`yolo_cloud/pose_engine.py:338-355`), warning path logs instead of crashing |

## Summary

- **CLOSED: 4 / 10** (1, 2, 4, 5)
- **PARTIAL: 3 / 10** (3, 7, 10)
- **OPEN: 3 / 10** (6, 8, 9)

The register's own headline — "P0 must fix for TRL-6/7" — is therefore
**two-thirds done**: everything blocking the TRL-6 evidence pack (DEBUG,
CI, MFA, brute-force) is closed; what remains (6, 8, 9 + the two halves
of 3, 7, 10) is operational-environment hardening, which is exactly the
TRL-7 column of `docs/TRL7_QUALIFICATION_PLAN.md`.

## Rules this document obeys

- Read-only verification: no product code was changed to produce it.
- Safe Claims language untouched; no accuracy claims of any kind.
- Each verdict cites `file:line`, never file length.
