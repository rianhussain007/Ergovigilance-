"""Task configuration — exposes task modifers and class info from the backend."""

from fastapi import APIRouter

from backend.context.engine import _TASK_MODIFIERS

router = APIRouter()


@router.get("/task-modifiers")
async def get_task_modifiers():
    """Return the task modifier table used by ContextIntelligenceEngine.

    Frontend consumes this to display risk impact per task, eliminating the
    duplicated hardcoded copy that was drifting out of sync.
    """
    return _TASK_MODIFIERS