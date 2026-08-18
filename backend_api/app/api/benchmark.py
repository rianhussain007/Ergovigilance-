"""Benchmark baseline API — de-identified posture percentiles.

- ``GET  /api/benchmark``            — baseline summary (any authenticated user)
- ``POST /api/benchmark/rebuild``    — rescan sessions and rebuild (manager roles)
- ``POST /api/benchmark/percentile`` — rank a live session's metric against it
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import get_current_user, require_roles
from app.core.security import AuthenticatedUser
from app.services import benchmark

router = APIRouter()


class PercentileRequest(BaseModel):
    metric: str = Field(..., description="One of the benchmark avg_* metrics")
    value: float = Field(..., description="The session's average for that metric")


@router.get("/benchmark")
async def get_benchmark(_: AuthenticatedUser = Depends(get_current_user)):
    """Baseline summary: per-metric count/min/median/max + session count."""
    baseline = benchmark.load_baseline()
    if baseline is None:
        # First use — build it so the UI always has an answer.
        benchmark.ensure_baseline_exists()
        baseline = benchmark.load_baseline()
    if baseline is None:
        return {"generated_at": None, "session_count": 0, "metrics": {}}
    return benchmark.summary_from_baseline(baseline)


@router.post("/benchmark/rebuild", status_code=201)
async def rebuild_benchmark(
    user: AuthenticatedUser = Depends(require_roles("supervisor", "safety_mgr", "admin")),
):
    """Rescan all recorded sessions and rebuild the percentile pool."""
    return benchmark.rebuild_baseline()


@router.post("/benchmark/percentile")
async def get_percentile(
    body: PercentileRequest,
    _: AuthenticatedUser = Depends(get_current_user),
):
    """Percentile rank of a metric value against the baseline."""
    if body.metric not in benchmark.BENCHMARK_METRICS:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown metric '{body.metric}'. Valid: {', '.join(benchmark.BENCHMARK_METRICS)}",
        )
    return benchmark.percentile_for(body.metric, body.value)
