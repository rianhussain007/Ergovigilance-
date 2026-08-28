"""Notification service — sends email/Slack alerts when high-risk postures are detected.

Configured via environment variables:
  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM
  SLACK_WEBHOOK_URL

When no notification config is set, alerts are logged but not sent.
Notifications are non-blocking — a failed send never crashes the pipeline.
"""

from __future__ import annotations

import logging
import os
import smtplib
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587") or "587")
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")

# Recipients for HIGH/CRITICAL alerts (comma-separated emails)
ALERT_RECIPIENTS = [
    e.strip() for e in os.getenv("ALERT_RECIPIENTS", "").split(",") if e.strip()
]

# Minimum severity to trigger email (LOW, MEDIUM, HIGH, CRITICAL)
MIN_EMAIL_SEVERITY = os.getenv("MIN_EMAIL_SEVERITY", "HIGH").upper()


def _severity_order(sev: str) -> int:
    return {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}.get(sev.upper(), 0)


def _should_send_email(severity: str) -> bool:
    """Check if this severity level warrants an email."""
    if not SMTP_HOST or not ALERT_RECIPIENTS:
        return False
    return _severity_order(severity) >= _severity_order(MIN_EMAIL_SEVERITY)


def _should_send_slack(severity: str) -> bool:
    """Check if this severity level warrants a Slack message."""
    if not SLACK_WEBHOOK_URL:
        return False
    return _severity_order(severity) >= _severity_order(MIN_EMAIL_SEVERITY)


# ── Email Sending ──────────────────────────────────────────────────

def _send_email_sync(
    subject: str,
    body: str,
    recipients: list[str],
    severity: str = "HIGH",
) -> bool:
    """Send an email alert. Runs in a background thread."""
    if not SMTP_HOST or not recipients:
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[ErgoVigilance {severity}] {subject}"
        msg["From"] = SMTP_FROM
        msg["To"] = ", ".join(recipients)

        # Plain text body
        msg.attach(MIMEText(body, "plain"))

        # HTML body for better readability
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <div style="background: #1e293b; color: white; padding: 16px; border-radius: 8px; margin-bottom: 16px;">
                <h2 style="margin: 0; color: #f87171;">⚠️ ErgoVigilance Alert</h2>
                <p style="margin: 8px 0 0 0; color: #94a3b8;">Severity: {severity}</p>
            </div>
            <div style="padding: 16px; background: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0;">
                <h3 style="margin: 0 0 8px 0; color: #1e293b;">{subject}</h3>
                <p style="color: #475569; line-height: 1.6;">{body}</p>
            </div>
            <p style="color: #94a3b8; font-size: 12px; margin-top: 16px;">
                ErgoVigilance — AI-Powered Ergonomic Monitoring
            </p>
        </body>
        </html>
        """
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.ehlo()
            if SMTP_PORT != 25:
                server.starttls()
                server.ehlo()
            if SMTP_USER:
                server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_FROM, recipients, msg.as_string())

        logger.info("Email alert sent to %s: %s", recipients, subject)
        return True
    except Exception as exc:
        logger.warning("Failed to send email alert: %s", exc)
        return False


# ── Slack Sending ──────────────────────────────────────────────────

def _send_slack_sync(text: str, severity: str = "HIGH") -> bool:
    """Send a Slack webhook message. Runs in a background thread."""
    if not SLACK_WEBHOOK_URL:
        return False
    try:
        import requests
        color = {
            "LOW": "#22c55e",
            "MEDIUM": "#f59e0b",
            "HIGH": "#ef4444",
            "CRITICAL": "#dc2626",
        }.get(severity, "#6b7280")

        payload = {
            "attachments": [{
                "color": color,
                "blocks": [{
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*🚨 ErgoVigilance Alert*\n*Severity:* {severity}\n{text}",
                    },
                }],
            }],
        }
        resp = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
        if resp.ok:
            logger.info("Slack alert sent: %s", text[:80])
            return True
        else:
            logger.warning("Slack send failed: %s", resp.status_code)
            return False
    except Exception as exc:
        logger.warning("Failed to send Slack alert: %s", exc)
        return False


# ── Public API ─────────────────────────────────────────────────────

def send_alert_notification(
    title: str,
    message: str,
    severity: str,
    session_id: str = "",
    worker_id: str = "",
) -> None:
    """Send alert notifications (email + Slack) in background threads.

    Non-blocking: failures are logged but never crash the pipeline.
    """
    if _should_send_email(severity):
        subject = f"{title} ({session_id})"
        body = (
            f"Alert: {title}\n"
            f"Severity: {severity}\n"
            f"Session: {session_id}\n"
            f"Worker: {worker_id or 'Unassigned'}\n\n"
            f"{message}\n\n"
            f"— ErgoVigilance Alert System"
        )
        threading.Thread(
            target=_send_email_sync,
            args=(subject, body, ALERT_RECIPIENTS, severity),
            daemon=True,
            name="alert-email",
        ).start()

    if _should_send_slack(severity):
        slack_text = f"*{title}*\n{message}\nSession: `{session_id}`"
        threading.Thread(
            target=_send_slack_sync,
            args=(slack_text, severity),
            daemon=True,
            name="alert-slack",
        ).start()


def get_notification_config() -> dict:
    """Return current notification configuration (for Settings page)."""
    return {
        "smtp_configured": bool(SMTP_HOST),
        "smtp_host": SMTP_HOST,
        "smtp_port": SMTP_PORT,
        "smtp_from": SMTP_FROM,
        "slack_configured": bool(SLACK_WEBHOOK_URL),
        "recipients": ALERT_RECIPIENTS,
        "min_severity": MIN_EMAIL_SEVERITY,
    }
