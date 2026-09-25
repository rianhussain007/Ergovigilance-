"""Multi-Factor Authentication (MFA/TOTP) for Enterprise Accounts.

Provides TOTP-based 2FA using the standard Google Authenticator / Authy format.
- Generate secret keys for users
- Verify TOTP codes
- Backup codes for account recovery

Requires: pyotp (pip install pyotp)
"""

import os
import secrets
import hashlib
import time
from typing import Optional

try:
    import pyotp
except ImportError:
    pyotp = None

import sqlite3
from pathlib import Path

DB_PATH = Path(os.getenv("AUTH_DB_PATH", "local_auth.db"))


class MFAUnavailable(RuntimeError):
    """Raised when MFA cannot be checked but is required for this account.

    Callers translate this into HTTP 503. It is deliberately an exception and
    not a ``False`` return: a missing ``pyotp`` must not look like a wrong code.
    """


# Alias kept short for the common import site.
MFAUnavailableError = MFAUnavailable


def pyotp_available() -> bool:
    """Whether the TOTP dependency is installed."""
    return pyotp is not None


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_mfa_table():
    """Create the MFA settings table if it doesn't exist."""
    conn = _get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mfa_settings (
            user_id INTEGER PRIMARY KEY,
            secret TEXT NOT NULL,
            enabled INTEGER DEFAULT 0,
            backup_codes TEXT,
            created_at TEXT,
            last_used TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    conn.close()


# Initialize on import
init_mfa_table()


def generate_mfa_secret(user_id: int) -> dict:
    """Generate a new TOTP secret for a user. Returns secret + provisioning URI."""
    if pyotp is None:
        return {"error": "pyotp not installed. Run: pip install pyotp"}

    secret = pyotp.random_base32()
    conn = _get_db()

    # Generate 10 backup codes
    backup_codes = [secrets.token_hex(4).upper() for _ in range(10)]
    backup_hashes = hashlib.sha256("".join(backup_codes).encode()).hexdigest()

    conn.execute("""
        INSERT OR REPLACE INTO mfa_settings (user_id, secret, enabled, backup_codes, created_at)
        VALUES (?, ?, 0, ?, datetime('now'))
    """, (user_id, secret, backup_hashes))
    conn.commit()

    # Get user email for provisioning URI
    row = conn.execute("SELECT email FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()

    email = row["email"] if row else f"user{user_id}"
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(
        name=email,
        issuer_name="ErgoVigilance"
    )

    return {
        "secret": secret,
        "provisioning_uri": provisioning_uri,
        "backup_codes": backup_codes,
        "qr_text": f"otpauth://totp/ErgoVigilance:{email}?secret={secret}&issuer=ErgoVigilance",
    }


def verify_totp(user_id: int, code: str) -> bool:
    """Verify a TOTP code for a user.

    Fails CLOSED when ``pyotp`` is missing but the account HAS MFA enabled: a
    second factor that cannot be checked must never be silently skipped, so we
    raise :class:`MFAUnavailableError` and the caller turns that into a 503.

    Users without MFA enrolled still pass through unchanged — MFA is opt-in, so
    an absent dependency can never block an ordinary login.
    """
    conn = _get_db()
    row = conn.execute(
        "SELECT secret, enabled FROM mfa_settings WHERE user_id = ?", (user_id,)
    ).fetchone()
    conn.close()

    if not row or not row["enabled"]:
        return True  # MFA not enabled — pass through (opt-in)

    if pyotp is None:
        raise MFAUnavailableError(
            "pyotp is not installed but this account has MFA enabled"
        )

    totp = pyotp.TOTP(row["secret"])
    # Allow 1 time step tolerance (30 seconds) for clock drift
    return totp.verify(code, valid_window=1)


def enable_mfa(user_id: int, code: str) -> dict:
    """Enable MFA after verifying the user can generate valid codes."""
    if pyotp is None:
        return {"error": "pyotp not installed"}

    conn = _get_db()
    row = conn.execute(
        "SELECT secret FROM mfa_settings WHERE user_id = ?", (user_id,)
    ).fetchone()

    if not row:
        conn.close()
        return {"error": "No MFA secret generated. Call /mfa/setup first."}

    totp = pyotp.TOTP(row["secret"])
    if not totp.verify(code, valid_window=1):
        conn.close()
        return {"error": "Invalid code. Make sure your authenticator app is synced."}

    conn.execute(
        "UPDATE mfa_settings SET enabled = 1 WHERE user_id = ?", (user_id,)
    )
    conn.commit()
    conn.close()

    return {"status": "enabled", "message": "MFA is now active on your account."}


def disable_mfa(user_id: int, code: str) -> dict:
    """Disable MFA after verifying current code."""
    if pyotp is None:
        return {"error": "pyotp not installed"}

    conn = _get_db()
    row = conn.execute(
        "SELECT secret, enabled FROM mfa_settings WHERE user_id = ?", (user_id,)
    ).fetchone()

    if not row or not row["enabled"]:
        conn.close()
        return {"status": "already_disabled"}

    totp = pyotp.TOTP(row["secret"])
    if not totp.verify(code, valid_window=1):
        conn.close()
        return {"error": "Invalid code."}

    conn.execute(
        "UPDATE mfa_settings SET enabled = 0 WHERE user_id = ?", (user_id,)
    )
    conn.commit()
    conn.close()

    return {"status": "disabled"}


def get_mfa_status(user_id: int) -> dict:
    """Check if MFA is enabled for a user."""
    conn = _get_db()
    row = conn.execute(
        "SELECT enabled, created_at, last_used FROM mfa_settings WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    conn.close()

    if not row:
        return {"enabled": False, "configured": False}

    return {
        "enabled": bool(row["enabled"]),
        "configured": True,
        "created_at": row["created_at"],
        "last_used": row["last_used"],
    }
