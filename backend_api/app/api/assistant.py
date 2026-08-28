"""AI Assistant chat endpoint — RAG-powered Q&A over the ergonomic knowledge corpus.

Streams tokens via Server-Sent Events (SSE). Protocol:
  data: {"type":"sources","sources":["thresholds.md"]}
  data: {"type":"token","text":"When"}
  data: {"type":"token","text":" neck"}
  ...
  data: {"type":"done"}

On refusal (no relevant context):
  data: {"type":"refusal"}

Supports session-data tool-calling: when the user asks about session
history, the assistant fetches live data from session files on disk
and injects it into the context before sending to Ollama.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.auth import get_current_user
from app.core.security import AuthenticatedUser
from backend.services.assistant import ask_stream, check_ollama_available

logger = logging.getLogger(__name__)
router = APIRouter()


class ChatRequest(BaseModel):
    message: str


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _event_stream(message: str):
    try:
        for event in ask_stream(message, project_root=PROJECT_ROOT):
            yield f"data: {json.dumps(event)}\n\n"
            if event.get("type") in ("done", "refusal", "error"):
                break
    except Exception as exc:
        logger.error("Streaming error: %s", exc, exc_info=True)
        yield f"data: {json.dumps({'type': 'error', 'text': str(exc)})}\n\n"


@router.get("/assistant/context")
async def get_live_context(
    _: AuthenticatedUser = Depends(get_current_user),
):
    """Return live session context for the AI assistant.

    Provides the current risk level, task, active alerts, and session
    duration so the assistant can give context-aware answers without
    the user having to describe their current situation.
    """
    try:
        # Import here to avoid circular imports at module level
        from app.services.session_cache import SessionCache
        from app.services.live_monitor import LiveMonitoringService

        cache = SessionCache()
        live = LiveMonitoringService()

        context = {
            "has_active_session": live.is_active,
            "session_id": None,
            "risk_level": None,
            "risk_score": None,
            "current_task": None,
            "task_confidence": None,
            "session_duration": None,
            "active_alerts": [],
            "recent_issues": [],
        }

        if live.is_active and live.current_session:
            session = live.current_session
            context["session_id"] = session.get("session_id")
            context["risk_level"] = session.get("risk_level", "LOW")
            context["risk_score"] = session.get("risk_score", 0)
            context["current_task"] = session.get("current_task", "Unknown")
            context["task_confidence"] = session.get("task_confidence", 0)
            context["session_duration"] = session.get("duration_seconds", 0)

            # Get active alerts
            try:
                alerts = cache.get_active_alerts()
                context["active_alerts"] = [
                    {
                        "severity": a.get("severity", "LOW"),
                        "title": a.get("title", ""),
                        "message": a.get("message", ""),
                    }
                    for a in (alerts or [])[:5]
                ]
            except Exception:
                pass

            # Get recent issues
            try:
                issues = cache.get_recent_issues()
                context["recent_issues"] = [
                    {
                        "name": i.get("name", ""),
                        "severity": i.get("severity", "low"),
                        "detail": i.get("detail", ""),
                    }
                    for i in (issues or [])[:5]
                ]
            except Exception:
                pass

        return context

    except Exception as exc:
        logger.warning("Failed to fetch live context: %s", exc)
        return {"has_active_session": False}


@router.post("/assistant/chat")
async def chat(
    body: ChatRequest,
    _: AuthenticatedUser = Depends(get_current_user),
):
    """Ask a question to the AI Assistant. Streams the answer via SSE.

    Before tokens arrive, a `sources` event indicates which knowledge files
    were retrieved. Each token arrives as a separate event. The stream ends
    with `done` (successful answer), `refusal` (no relevant context found),
    or `error`. Session-data questions automatically fetch live data.
    """
    if not check_ollama_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service is temporarily unavailable. Please try again in a moment.",
        )

    return StreamingResponse(
        _event_stream(body.message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
