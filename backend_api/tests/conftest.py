"""Pytest bootstrap — make ``app.*`` and ``backend.*`` importable.

Adds ``backend_api/`` and the repo root to ``sys.path`` so tests can be run
from anywhere (``pytest backend_api/tests``, a single file, or CI) without
relying on accidental path pollution from sibling test modules.
"""

import sys
from pathlib import Path

BACKEND_API_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[2]

for _path in (BACKEND_API_DIR, REPO_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
