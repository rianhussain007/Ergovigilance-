"""Migrate existing persisted sessions into the PostgreSQL telemetry store.

Reads every session summary JSON in ``outputs/sessions/`` plus its recording
timeline (``recordings/{worker}/{session}/timeline.json``) and upserts them
into Postgres (``ergo_sessions`` + ``ergo_session_frames``). Idempotent —
rerunning updates rows in place, so it is safe to run again after new
sessions are recorded.

Usage:
    DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/ergovigilance \
        python scripts/migrate_sessions_to_postgres.py [--dry-run]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
BACKEND_API_DIR = ROOT / "backend_api"
if str(BACKEND_API_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_API_DIR))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--dry-run", action="store_true",
        help="Scan + report what would be migrated without writing anything.",
    )
    args = ap.parse_args()

    from app.core.postgres import (
        init_postgres_schema,
        iter_timeline_files,
        pg_enabled,
        reset_connection,
        upsert_session,
        bulk_insert_frames,
    )

    if not pg_enabled():
        print("ERROR: DATABASE_URL is not set — nothing to migrate.")
        print("Example: DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/ergovigilance")
        return 1

    if not init_postgres_schema():
        print("ERROR: could not create the Postgres schema (is the DB up?).")
        return 1

    print(f"Scanning sessions under {ROOT / 'outputs' / 'sessions'} ...")
    pairs = list(iter_timeline_files(str(ROOT)))
    total_sessions = len(pairs)
    total_frames = sum(len(frames) for _, frames in pairs)
    print(f"Found {total_sessions} session summaries, {total_frames} timeline rows.")

    if args.dry_run:
        print("Dry run — no writes performed.")
        return 0

    migrated = 0
    migrated_frames = 0
    for payload, frames in pairs:
        # upsert_session synthesizes a session_id for legacy files that
        # predate the field — nothing is skipped.
        ok = upsert_session(payload)
        ok_f = bulk_insert_frames(payload, frames)
        if ok:
            migrated += 1
            migrated_frames += len(frames) if ok_f else 0

    reset_connection()
    print(
        f"Migrated {migrated}/{total_sessions} sessions "
        f"({migrated_frames} timeline rows) into Postgres."
    )
    return 0 if migrated > 0 else 2


if __name__ == "__main__":
    sys.exit(main())
