"""Tests for audit-chain HMAC key resolution (P0-8).

Covers: env precedence, file persistence (restart-stable chains),
fail-closed when DEBUG=false, and the dev-only ephemeral fallback.
"""

import json

import pytest

from app.core import audit_log


def test_env_key_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("AUDIT_HMAC_KEY", "env-supplied-key-0123456789abcdef")
    monkeypatch.setenv("AUDIT_HMAC_KEY_FILE", str(tmp_path / "unused.key"))

    assert audit_log._resolve_hmac_key() == "env-supplied-key-0123456789abcdef"
    assert not (tmp_path / "unused.key").exists()


def test_key_file_created_then_reused(monkeypatch, tmp_path):
    key_file = tmp_path / "audit_hmac.key"
    monkeypatch.delenv("AUDIT_HMAC_KEY", raising=False)
    monkeypatch.setenv("AUDIT_HMAC_KEY_FILE", str(key_file))

    first = audit_log._resolve_hmac_key()
    assert key_file.exists()
    assert len(first) == 64  # secrets.token_hex(32)

    second = audit_log._resolve_hmac_key()
    assert second == first  # restart-equivalent: same file, same key


def test_chain_verifies_across_restart(monkeypatch, tmp_path):
    """Entries signed before a restart still verify after re-resolution."""
    key_file = tmp_path / "audit_hmac.key"
    monkeypatch.delenv("AUDIT_HMAC_KEY", raising=False)
    monkeypatch.setenv("AUDIT_HMAC_KEY_FILE", str(key_file))
    # Start from a cold cache: an earlier test in the suite may have warmed
    # _HMAC_KEY_CACHE with a different key (monkeypatch only restores env).
    monkeypatch.setattr(audit_log, "_HMAC_KEY_CACHE", None)

    entry_data = json.dumps({"event": "user_login"}, sort_keys=True)
    signed = audit_log._hmac_chain("0" * 64, entry_data)

    # Simulate restart: drop the in-process cache, resolve from file again.
    monkeypatch.setattr(audit_log, "_HMAC_KEY_CACHE", None)
    assert audit_log._hmac_chain("0" * 64, entry_data) == signed


def test_fail_closed_when_debug_false_and_unusable(monkeypatch, tmp_path):
    blocker = tmp_path / "unusable.key"
    blocker.mkdir()  # a directory can never be written as a key file
    monkeypatch.delenv("AUDIT_HMAC_KEY", raising=False)
    monkeypatch.setenv("AUDIT_HMAC_KEY_FILE", str(blocker))
    monkeypatch.setenv("DEBUG", "false")

    with pytest.raises(RuntimeError, match="AUDIT_HMAC_KEY"):
        audit_log._resolve_hmac_key()


def test_dev_falls_back_to_ephemeral(monkeypatch, tmp_path):
    blocker = tmp_path / "unusable.key"
    blocker.mkdir()
    monkeypatch.delenv("AUDIT_HMAC_KEY", raising=False)
    monkeypatch.setenv("AUDIT_HMAC_KEY_FILE", str(blocker))
    monkeypatch.setenv("DEBUG", "true")

    assert audit_log._resolve_hmac_key()  # non-empty key, no raise


def test_ensure_hmac_key_caches(monkeypatch, tmp_path):
    key_file = tmp_path / "audit_hmac.key"
    monkeypatch.delenv("AUDIT_HMAC_KEY", raising=False)
    monkeypatch.setenv("AUDIT_HMAC_KEY_FILE", str(key_file))
    monkeypatch.setattr(audit_log, "_HMAC_KEY_CACHE", None)

    key = audit_log.ensure_hmac_key()
    assert audit_log._HMAC_KEY_CACHE == key
    # Second call is served from cache even if the file disappears.
    key_file.unlink()
    assert audit_log.ensure_hmac_key() == key
