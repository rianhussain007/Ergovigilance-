"""User settings endpoints."""

import logging
from fastapi import APIRouter, Depends

from app.core.auth import get_current_user
from app.core.database import get_user_settings, save_user_settings
from app.core.security import AuthenticatedUser
from app.schemas.user_settings import UserSettings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/settings/notifications")
async def get_notification_settings(user: AuthenticatedUser = Depends(get_current_user)):
    """Get notification configuration (email, Slack)."""
    try:
        from app.services.notifications import get_notification_config
    except ImportError:
        from backend_api.app.services.notifications import get_notification_config
    return get_notification_config()


@router.post("/settings/notifications/test")
async def send_test_notification(user: AuthenticatedUser = Depends(get_current_user)):
    """Send a test alert via configured channels (email, Slack)."""
    import os
    results: dict[str, str] = {}

    # Try email
    smtp_host = os.getenv("SMTP_HOST")
    if smtp_host:
        try:
            import smtplib
            from email.mime.text import MIMEText
            from datetime import datetime, timezone

            smtp_port = int(os.getenv("SMTP_PORT", "587"))
            smtp_user = os.getenv("SMTP_USER", "")
            smtp_pass = os.getenv("SMTP_PASS", "")
            smtp_from = os.getenv("SMTP_FROM", smtp_user)
            recipients = [r.strip() for r in os.getenv("ALERT_RECIPIENTS", "").split(",") if r.strip()]

            if not recipients:
                results["email"] = "No ALERT_RECIPIENTS configured"
            else:
                msg = MIMEText(
                    f"This is a test alert from ErgoVigilance.\n\n"
                    f"Sent at: {datetime.now(timezone.utc).isoformat()}\n"
                    f"Sent by: {user.email}\n"
                    f"\nIf you received this, your SMTP configuration is working correctly."
                )
                msg["Subject"] = "[ErgoVigilance] Test Alert"
                msg["From"] = smtp_from
                msg["To"] = ", ".join(recipients)

                with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                    server.starttls()
                    if smtp_user and smtp_pass:
                        server.login(smtp_user, smtp_pass)
                    server.sendmail(smtp_from, recipients, msg.as_string())
                results["email"] = f"Sent to {', '.join(recipients)}"
        except Exception as e:
            results["email"] = f"Failed: {e}"
    else:
        results["email"] = "SMTP not configured (no SMTP_HOST)"

    # Try Slack
    slack_url = os.getenv("SLACK_WEBHOOK_URL")
    if slack_url:
        try:
            import urllib.request
            import json as _json
            from datetime import datetime, timezone

            payload = _json.dumps({
                "text": f":white_check_mark: *ErgoVigilance Test Alert*\nSent by {user.email} at {datetime.now(timezone.utc).strftime('%H:%M UTC')}\n_This is a test — your Slack integration is working!_"
            }).encode()
            req = urllib.request.Request(
                slack_url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=10)
            results["slack"] = "Sent successfully"
        except Exception as e:
            results["slack"] = f"Failed: {e}"
    else:
        results["slack"] = "Slack not configured (no SLACK_WEBHOOK_URL)"

    any_success = any("Sent" in v and "Failed" not in v for v in results.values())
    if any_success:
        return {"status": "ok", "detail": "Test alert sent", "results": results}
    else:
        from fastapi import HTTPException, status as http_status
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"No channels could deliver the test alert: {results}",
        )


@router.get("/settings")
async def get_settings(user: AuthenticatedUser = Depends(get_current_user)):
    """Get current user's settings."""
    return get_user_settings(user.id)


@router.put("/settings")
async def update_settings(
    body: UserSettings,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Save current user's settings."""
    # Only save non-None fields (partial update)
    settings_dict = body.model_dump(exclude_none=True)
    if not settings_dict:
        return {"status": "ok", "message": "No settings to update"}
    save_user_settings(user.id, settings_dict)
    return {"status": "ok", "updated_fields": list(settings_dict.keys())}
