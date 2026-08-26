"""Pytest bootstrap — make ``app.*`` and ``backend.*`` importable and isolate tests.

1. Adds ``backend_api/`` and the repo root to ``sys.path`` so tests can be run
   from anywhere (``pytest backend_api/tests``, a single file, or CI).

2. Points the app at throwaway paths *before any app module is imported*:

   - ``AUTH_DB_PATH`` → a fresh temp SQLite file (never the dev database)
   - ``POSE_MODEL_PATH`` → a nonexistent file (skips live-service init, which
     is what the fail-closed 503 test exercises)
   - Retention dirs → temp dirs with the policy disabled (0), so the startup
     retention loop can never touch the developer's ``outputs/``/``recordings/``
"""

import os
import sys
import tempfile
from pathlib import Path

BACKEND_API_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[2]

for _path in (BACKEND_API_DIR, REPO_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

_TMP = Path(tempfile.mkdtemp(prefix="ergovigilance-tests-"))

# Force test isolation (must happen before `app.core.config` / `app.core.database`
# are imported anywhere, so conftest runs before all test modules).
os.environ["AUTH_DB_PATH"] = str(_TMP / "test_auth.db")
os.environ["POSE_MODEL_PATH"] = str(_TMP / "missing_pose_model.task")
os.environ["SESSIONS_DIR"] = str(_TMP / "sessions")
os.environ["RECORDINGS_DIR"] = str(_TMP / "recordings")
os.environ["SESSION_RETENTION_DAYS"] = "0"
os.environ["RECORDING_RETENTION_DAYS"] = "0"
os.environ["RECORDINGS_MAX_GB"] = "0"
os.environ["RETENTION_INTERVAL_HOURS"] = "1000"
os.environ["AUTH_JWT_TTL_SECONDS"] = "3600"
