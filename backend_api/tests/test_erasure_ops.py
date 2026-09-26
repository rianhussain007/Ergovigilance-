"""Erasure-operation helpers (TRL-8 leftovers: BACKUP_RESTORE_OPS steps 3-4).

Covers: HMAC key destruction (+rotation proof) and SQLite VACUUM.
"""

from __future__ import annotations


def test_destroy_missing_key_file_is_false(monkeypatch, tmp_path):
    from app.core import audit_log

    monkeypatch.delenv("AUDIT_HMAC_KEY", raising=False)
    monkeypatch.setenv("AUDIT_HMAC_KEY_FILE", str(tmp_path / "audit_hmac.key"))
    monkeypatch.setattr(audit_log, "_HMAC_KEY_CACHE", None)

    assert audit_log.destroy_hmac_key() is False


def test_destroy_provisioned_key_rotates(monkeypatch, tmp_path):
    from app.core import audit_log

    monkeypatch.delenv("AUDIT_HMAC_KEY", raising=False)
    monkeypatch.setenv("AUDIT_HMAC_KEY_FILE", str(tmp_path / "audit_hmac.key"))
    monkeypatch.setattr(audit_log, "_HMAC_KEY_CACHE", None)

    first = audit_log._resolve_hmac_key()
    assert (tmp_path / "audit_hmac.key").exists()

    assert audit_log.destroy_hmac_key() is True
    assert not (tmp_path / "audit_hmac.key").exists()

    second = audit_log._resolve_hmac_key()
    assert second
    assert second != first  # rotation: fresh provision, old chain unverifiable
    assert (tmp_path / "audit_hmac.key").exists()


def test_destroy_keeps_env_key_process_alive(monkeypatch, tmp_path):
    from app.core import audit_log

    monkeypatch.setenv("AUDIT_HMAC_KEY", "env-supplied-key-0123456789abcdef")
    monkeypatch.setenv("AUDIT_HMAC_KEY_FILE", str(tmp_path / "audit_hmac.key"))
    monkeypatch.setattr(audit_log, "_HMAC_KEY_CACHE", "env-supplied-key-0123456789abcdef")

    assert audit_log.destroy_hmac_key() is False
    assert audit_log._hmac_key() == "env-supplied-key-0123456789abcdef"


def test_vacuum_database_reports_counters():
    import sqlite3

    from app.core.database import get_connection, vacuum_database

    with get_connection() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS _erasure_probe (id INTEGER PRIMARY KEY, v TEXT)")
        conn.executemany(
            "INSERT INTO _erasure_probe (v) VALUES (?)", [(f"value-{i}",) for i in range(200)]
        )
        conn.commit()
        conn.execute("DELETE FROM _erasure_probe")
        conn.commit()

    result = vacuum_database()
    assert isinstance(result["page_count"], int) and result["page_count"] >= 0
    assert isinstance(result["freelist_count"], int) and result["freelist_count"] >= 0

    with get_connection() as conn:
        conn.execute("DROP TABLE IF EXISTS _erasure_probe")
        conn.commit()
