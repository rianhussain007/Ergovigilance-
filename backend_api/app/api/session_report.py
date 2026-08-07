"""Session Report PDF endpoint — single-session detail as PDF."""

import json
import logging
import os
import sys
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

ROOT = Path(__file__).resolve().parents[3]
if not (ROOT / "backend_api").is_dir() and (Path(__file__).resolve().parents[2] / "app").is_dir():
    ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.auth import get_current_user
from app.core.security import AuthenticatedUser
from backend.services.report_pdf import render_session_pdf

logger = logging.getLogger(__name__)
router = APIRouter()

SESSIONS_DIR = os.path.join(str(ROOT), "outputs", "sessions")


@router.get("/reports/session/{session_id}/pdf")
async def get_session_pdf(
    session_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Single Session Report as PDF download."""
    # Map session_id like "SESH-20260706_143117" to filename "session_20260706_143117.json"
    ts_part = session_id.replace("SESH-", "", 1)
    filename = f"session_{ts_part}.json"
    filepath = os.path.join(SESSIONS_DIR, filename)

    if not os.path.exists(filepath) and os.path.exists(SESSIONS_DIR):
        # Fallback: iterate all JSON files and match by session_id field
        # This handles format mismatches between session ID generation and file naming.
        for fname in os.listdir(SESSIONS_DIR):
            if not fname.endswith(".json"):
                continue
            candidate = os.path.join(SESSIONS_DIR, fname)
            try:
                with open(candidate, "r") as f:
                    probe = json.load(f)
                if probe.get("session_id") == session_id:
                    filepath = candidate
                    break
            except Exception:
                continue

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    try:
        with open(filepath, "r") as f:
            data = json.load(f)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read session file: {exc}")

    data["id"] = session_id
    pdf_bytes = await render_session_pdf(data)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=session-report-{ts_part}.pdf",
        },
    )
