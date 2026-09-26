"""Camera entitlement enforcement (sell-readiness audit F-01).

Single rule: an org may have at most ``max_cameras`` registered cameras
(``None`` = unlimited, e.g. enterprise). Callers without an org identity —
dev mode, self-hosted boxes, legacy tenant keys — are never gated: the
operator owns their own hardware, so that path stays honor-system by
design (see ``docs/SELL_READINESS_AUDIT.md`` F-01).

Enforcement lives here (pure, DB-free) so both the cloud ``add_camera``
endpoint and tests share one gate; the org lookup itself stays in
``yolo_cloud/org_auth.py`` next to the key validation.
"""

from __future__ import annotations

from typing import Optional

from fastapi import HTTPException


def check_camera_allowance(org: Optional[dict], current_count: int) -> None:
    """Raise 403 if registering one more camera would exceed the org cap.

    ``org`` is the ``lookup_org_by_api_key`` dict (``plan``,
    ``max_cameras``) or ``None`` when the caller has no org identity.
    """
    if org is None:
        return
    limit = org.get("max_cameras")
    if limit is None:
        return
    if int(current_count) >= int(limit):
        plan = org.get("plan", "current")
        raise HTTPException(
            status_code=403,
            detail=(
                f"Camera limit reached for plan '{plan}' "
                f"({limit} cameras). Remove a camera or upgrade "
                "your plan to add more."
            ),
        )
