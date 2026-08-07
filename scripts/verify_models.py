"""Verify model artifacts against models/MANIFEST.json.

Checks that every listed model exists, has the expected byte size, and matches
the recorded SHA-256. Exits non-zero on any mismatch — used locally and in CI
so a corrupted or unapproved model swap is caught at push time.

Usage:
    python scripts/verify_models.py            # checksum + size
    python scripts/verify_models.py --list     # just print the manifest
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "models" / "MANIFEST.json"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify() -> tuple[list[str], list[str]]:
    """Return (errors, warnings). Exit code is driven by errors."""
    if not MANIFEST_PATH.exists():
        return [f"MANIFEST not found: {MANIFEST_PATH}"], []

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    models = manifest.get("models", [])
    errors: list[str] = []
    warnings: list[str] = []

    for entry in models:
        rel = entry.get("filename")
        if not rel:
            errors.append("manifest entry missing 'filename'")
            continue
        path = REPO_ROOT / "models" / rel
        if not path.exists():
            errors.append(f"{rel}: file missing")
            continue

        actual_size = path.stat().st_size
        expected_size = entry.get("size_bytes")
        if expected_size is not None and actual_size != expected_size:
            errors.append(f"{rel}: size mismatch (expected {expected_size}, got {actual_size})")

        expected_sha = entry.get("sha256")
        if expected_sha:
            actual_sha = sha256_of(path)
            if actual_sha != expected_sha:
                errors.append(f"{rel}: SHA-256 mismatch — file modified since manifest was recorded")
            else:
                print(f"OK  {rel} ({actual_size} bytes, sha256 {actual_sha[:16]}…)")
        else:
            warnings.append(f"{rel}: no sha256 recorded in manifest")

    # Flag any files in models/ that are not in the manifest (untracked additions).
    known = {e.get("filename") for e in models}
    for path in sorted((REPO_ROOT / "models").glob("*")):
        if path.is_file() and path.name not in known and path.name != "MANIFEST.json":
            warnings.append(f"{path.name}: present on disk but not listed in MANIFEST.json")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify model artifacts against MANIFEST.json")
    parser.add_argument("--list", action="store_true", help="print the manifest and exit")
    args = parser.parse_args()

    if args.list:
        print(MANIFEST_PATH.read_text(encoding="utf-8"))
        return 0

    errors, warnings = verify()
    for w in warnings:
        print(f"WARN {w}")
    for e in errors:
        print(f"ERROR {e}")

    print(f"\n{len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
