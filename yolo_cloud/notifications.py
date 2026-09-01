"""YOLO Cloud Core — Alert Notification Service.

Sends email and Slack notifications for cloud alerts.
Self-contained: does not depend on the backend API module.
Falls back gracefully when SMTP/Slack is not configured.
"""

from __future__ import annotations

import logging
import os
import threading
import urllib.request
import json
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

# Configuration from environment
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)
ALERT_RECIPIENTS = [
    r.strip()
    for r in os.getenv("ALERT_RECIPIENTS", "").split(",")
    if r.strip()
]
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
MIN_EMAIL_SEVERITY = os.getenv("MIN_EMAIL_SEVERITY", "HIGH")
MIN_SLACK_SEVERITY = os.getenv("MIN_SLACK_SEVERITY", "MEDIUM")

SEVERITY_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}


def _should_send_email(severity: str) -> bool:
    if not SMTP_HOST or not ALERT_RECIPIENTS:
        return False
    return SEVERITY_ORDER.get(severity, 0) >= SEVERITY_ORDER.get(MIN_EMAIL_SEVERITY, 2)


def _should_send_slack(severity: str) -> bool:
    if not SLACK_WEBHOOK_URL:
        return False
    return SEVERITY_ORDER.get(severity, 0) >= SEVERITY_ORDER.get(MIN_SLACK_SEVERITY, 1)


def _send_email_sync(subject: str, body: str, recipients: list[str], severity: str) -> None:
    try:
        import smtplib

        msg = MIMEText(body)
        msg["Subject"] = f"[ErgoVigilance {severity}] {subject}"
        msg["From"] = SMTP_FROM
        msg["To"] = ", ".join(recipients)

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls()
            if SMTP_USER and SMTP_PASS:
                server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_FROM, recipients, msg.as_string())

        logger.info("Alert email sent to %s: %s", recipients, subject)
    except Exception as exc:
        logger.warning("Failed to send alert email: %s", exc)


def _send_slack_sync(text: str) -> None:
    try:
        payload = json.dumps({"text": text}).encode()
        req = urllib.request.Request(
            SLACK_WEBHOOK_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10)
        logger.info("Alert sent to Slack")
    except Exception as exc:
        logger.warning("Failed to send Slack alert: %s", exc)


def send_alert_notification(
    title: str,
    message: str,
    severity: str,
    session_id: str = "",
    camera_id: str = "",
    risk_score: float = 0.0,
) -> None:
    """Send alert notifications (email + Slack) in background threads.

    Non-blocking: failures are logged but never crash the pipeline.
    """
    if _should_send_email(severity):
        subject = f"{title} (session: {session_id})"
        body = (
            f"Alert: {title}\n"
            f"Severity: {severity}\n"
            f"Camera: {camera_id}\n"
            f"Session: {session_id}\n"
            f"Risk Score: {risk_score:.1f}\n\n"
            f"{message}\n\n"
            f"— ErgoVigilance Cloud Alert System"
        )
        threading.Thread(
            target=_send_email_sync,
            args=(subject, body, ALERT_RECIPIENTS, severity),
            daemon=True,
            name="cloud-alert-email",
        ).start()

    if _should_send_slack(severity):
        slack_text = (
            f":warning: *{title}*\n"
            f"{message}\n"
            f"Camera: `{camera_id}` | Session: `{session_id}` | Score: {risk_score:.1f}"
        )
        threading.Thread(
            target=_send_slack_sync,
            args=(slack_text,),
            daemon=True,
            name="cloud-alert-slack",
        ).start()


def get_notification_config() -> dict:
    """Return current notification configuration status."""
    return {
        "smtp_configured": bool(SMTP_HOST),
        "smtp_host": SMTP_HOST,
        "smtp_port": SMTP_PORT,
        "smtp_from": SMTP_FROM,
        "slack_configured": bool(SLACK_WEBHOOK_URL),
        "recipients": ALERT_RECIPIENTS,
        "min_email_severity": MIN_EMAIL_SEVERITY,
        "min_slack_severity": MIN_SLACK_SEVERITY,
    }
