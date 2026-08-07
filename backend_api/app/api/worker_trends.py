from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Response

from app.core.auth import get_current_user
from app.core.security import AuthenticatedUser
from app.schemas.api import WorkerTrendsResponse
from app.services.worker_trends import compute_worker_trends

logger = logging.getLogger(__name__)

router = APIRouter(tags=["worker-trends"])


@router.get("/reports/worker-trends", response_model=WorkerTrendsResponse)
async def get_worker_trends():
    """Return per-worker fatigue trends and per-department pattern analysis."""
    project_root = Path(__file__).resolve().parents[3]
    return compute_worker_trends(project_root)


@router.get("/reports/worker-trends/pdf")
async def get_worker_trends_pdf(
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Worker Trends Report as PDF download."""
    from backend.services.report_pdf import render_worker_trends_pdf

    project_root = Path(__file__).resolve().parents[3]
    data = compute_worker_trends(project_root)
    pdf_bytes = await render_worker_trends_pdf(data.model_dump())
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=worker-trends-report.pdf",
        },
    )