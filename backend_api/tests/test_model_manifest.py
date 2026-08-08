"""Model governance guard: every tracked artifact must match MANIFEST.json.

Runs scripts/verify_models.py (the same checksum + size verifier the CI
pipeline invokes) so a corrupt or unapproved model swap is caught by the
local pytest suite too — not just on push.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "models" / "MANIFEST.json"
VERIFY_SCRIPT = REPO_ROOT / "scripts" / "verify_models.py"


def test_manifest_exists() -> None:
    assert MANIFEST_PATH.exists(), "models/MANIFEST.json is missing"


def test_all_manifest_models_are_git_tracked() -> None:
    """The verify script is only meaningful if the artifacts ship with the repo."""
    import json

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    for entry in manifest["models"]:
        rel = REPO_ROOT / "models" / entry["filename"]
        assert rel.exists(), f"{entry['filename']} listed in manifest but not on disk"


@pytest.mark.skipif(
    not MANIFEST_PATH.exists() or not VERIFY_SCRIPT.exists(),
    reason="verify_models.py or MANIFEST.json not present",
)
def test_verify_models_passes() -> None:
    proc = subprocess.run(
        [sys.executable, str(VERIFY_SCRIPT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, (
        f"verify_models.py failed:\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
