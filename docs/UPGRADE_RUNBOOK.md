# Upgrade Runbook — clean in-place upgrades (TRL-9 gate support)

Upgrades are migration-driven: `run_migrations()` (`app/core/migrations.py`)
applies every `migrations/NNN_*.sql` past `PRAGMA user_version`, one
transaction each, at startup (`init_local_database`). Rules: never edit an
applied migration; add schema changes as a new numbered file.

## Pre-upgrade (every time)

1. **Back up the auth DB**: `bash deploy/backup.sh --db-only`
   (SQLite file copy; compose: captured from the volume).
2. Record `PRAGMA user_version` + image tag being replaced.

## Deploy

3. Roll the new image (one pod/replica at a time where applicable).
   Migrations run automatically at boot; concurrent first-boots are
   serialized (`BEGIN IMMEDIATE` + version re-check — the old
   crash-loop on fresh DBs is fixed and covered by
   `test_concurrent_fresh_boot_applies_once`).
4. Watch boot logs for `Applied database migration N` lines; any
   `ROLLBACK` + raise = failed upgrade, DB untouched on its version.

## Verify

5. `/healthz` 200, login works, `/api/orgs/current` returns the org
   (exercises the auth→DB path end to end).
6. `PRAGMA user_version` advanced; spot-check a write + read.

## Roll back (no down-migrations by design)

7. Stop the new version, restore the pre-upgrade DB file from step 1,
   redeploy the previous image tag. Old code never reads newer schema
   because the DB file itself was restored.

## Evidence for the TRL-9 gate

File the version pair, migration lines from boot logs, verification
outputs, and rollback-test date with the release. One clean upgrade
with zero data loss closes that gate.
