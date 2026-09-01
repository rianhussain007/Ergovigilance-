"""YOLO Cloud Core — Webhook Delivery System.

Allows customers to configure webhook URLs that receive POST requests
when alerts are fired. Each webhook receives a JSON payload with the
full alert details.

Webhook payload example:
{
    "event": "alert.fired",
    "alert_id": "ALT-000001",
    "severity": "HIGH",
    "camera_id": "cam-01",
    "camera_name": "Assembly Line",
    "session_id": "CLOUD-2026-09-01_10-30-00",
    "risk_score": 85.0,
    "task": "lifting",
    "message": "HIGH risk — worker lifting with bent back.",
    "timestamp": "2026-09-01T10:30:15Z"
}
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import threading
import time
import urllib.request
from typing import Optional

logger = logging.getLogger(__name__)

# Webhook secret for signing payloads (set in env for production)
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "ergovigilance-webhook-secret")


def _sign_payload(payload: bytes) -> str:
    """Sign payload with HMAC-SHA256 for verification."""
    return hmac.new(WEBHOOK_SECRET.encode(), payload, hashlib.sha256).hexdigest()


def _deliver_webhook(url: str, payload: dict, timeout: int = 10) -> bool:
    """Deliver a webhook to a single URL. Returns True on success."""
    try:
        body = json.dumps(payload, default=str).encode()
        signature = _sign_payload(body)

        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-ErgoVigilance-Signature": signature,
                "X-ErgoVigilance-Event": payload.get("event", "unknown"),
                "User-Agent": "ErgoVigilance-Cloud/1.0",
            },
            method="POST",
        )
        urllib.request.urlopen(req, timeout=timeout)
        logger.info("Webhook delivered to %s", url)
        return True
    except Exception as exc:
        logger.warning("Webhook delivery to %s failed: %s", url, exc)
        return False


def send_webhook(
    tenant_id: str,
    event: str,
    alert_data: Optional[dict] = None,
) -> int:
    """Send a webhook to all configured URLs for a tenant.

    Args:
        tenant_id: The tenant to send webhooks for
        event: Event type (e.g., "alert.fired", "session.completed")
        alert_data: Alert details to include in the payload

    Returns:
        Number of successful deliveries
    """
    from yolo_cloud.storage import get_connection

    conn = get_connection()
    if conn is None:
        return 0

    try:
        rows = conn.execute(
            """SELECT webhook_url, secret FROM cloud_webhooks
               WHERE tenant_id = %s AND is_active = TRUE AND %s = ANY(events)""",
            (tenant_id, event),
        ).fetchall()
    except Exception as exc:
        logger.warning("Failed to fetch webhooks: %s", exc)
        return 0

    if not rows:
        return 0

    payload = {
        "event": event,
        "timestamp": time.time(),
        "tenant_id": tenant_id,
    }
    if alert_data:
        payload.update(alert_data)

    success_count = 0
    for webhook_url, secret in rows:
        # Use per-webhook secret if configured, otherwise use global
        if secret:
            original_secret = globals().get("WEBHOOK_SECRET")
            globals()["WEBHOOK_SECRET"] = secret

        if _deliver_webhook(webhook_url, payload):
            success_count += 1

        if secret:
            globals()["WEBHOOK_SECRET"] = original_secret

    return success_count


def store_webhook(
    tenant_id: str,
    webhook_url: str,
    events: list[str] = None,
    secret: str = "",
    name: str = "",
) -> bool:
    """Store a webhook configuration."""
    from yolo_cloud.storage import get_connection

    conn = get_connection()
    if conn is None:
        return False

    if events is None:
        events = ["alert.fired"]

    try:
        import uuid
        webhook_id = str(uuid.uuid4())[:8]
        conn.execute(
            """INSERT INTO cloud_webhooks (webhook_id, tenant_id, webhook_url, events, secret, name, is_active)
               VALUES (%s, %s, %s, %s, %s, %s, TRUE)""",
            (webhook_id, tenant_id, webhook_url, events, secret, name),
        )
        conn.commit()
        logger.info("Webhook stored for tenant %s: %s", tenant_id, webhook_url)
        return True
    except Exception as exc:
        logger.warning("Failed to store webhook: %s", exc)
        return False


def get_webhooks(tenant_id: str) -> list[dict]:
    """Get all webhooks for a tenant."""
    from yolo_cloud.storage import get_connection

    conn = get_connection()
    if conn is None:
        return []

    try:
        rows = conn.execute(
            """SELECT webhook_id, name, webhook_url, events, is_active, created_at
               FROM cloud_webhooks WHERE tenant_id = %s ORDER BY created_at DESC""",
            (tenant_id,),
        ).fetchall()
        return [
            {
                "webhook_id": r[0],
                "name": r[1],
                "url": r[2],
                "events": r[3],
                "is_active": r[4],
                "created_at": r[5].isoformat() if r[5] else None,
            }
            for r in rows
        ]
    except Exception as exc:
        logger.warning("Failed to get webhooks: %s", exc)
        return []


def delete_webhook(webhook_id: str, tenant_id: str) -> bool:
    """Delete a webhook."""
    from yolo_cloud.storage import get_connection

    conn = get_connection()
    if conn is None:
        return False

    try:
        conn.execute(
            "DELETE FROM cloud_webhooks WHERE webhook_id = %s AND tenant_id = %s",
            (webhook_id, tenant_id),
        )
        conn.commit()
        return True
    except Exception as exc:
        logger.warning("Failed to delete webhook: %s", exc)
        return False


def test_webhook(webhook_url: str) -> dict:
    """Send a test webhook and return the result."""
    test_payload = {
        "event": "test",
        "message": "This is a test webhook from ErgoVigilance Cloud",
        "timestamp": time.time(),
    }
    success = _deliver_webhook(webhook_url, test_payload, timeout=5)
    return {
        "success": success,
        "message": "Webhook delivered successfully" if success else "Delivery failed",
    }


# Add schema for webhooks table
WEBHOOK_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS cloud_webhooks (
    webhook_id  TEXT PRIMARY KEY,
    tenant_id   TEXT NOT NULL DEFAULT 'default',
    webhook_url TEXT NOT NULL,
    name        TEXT NOT NULL DEFAULT '',
    events      TEXT[] NOT NULL DEFAULT ARRAY['alert.fired'],
    secret      TEXT NOT NULL DEFAULT '',
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cloud_webhooks_tenant ON cloud_webhooks(tenant_id);
"""
