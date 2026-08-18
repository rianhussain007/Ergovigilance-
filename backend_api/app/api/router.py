"""Main API router — aggregates all endpoint modules."""

from fastapi import APIRouter

from app.api.dashboard import router as dashboard_router
from app.api.sessions import router as sessions_router
from app.api.reports import router as reports_router
from app.api.cameras import router as cameras_router
from app.api.workstations import router as workstations_router
from app.api.deployment import router as deployment_router
from app.api.manager import router as manager_router
from app.api.alerts import router as alerts_router
from app.api.session_lifecycle import router as session_lifecycle_router
from app.api.video_feed import router as video_feed_router
from app.api.context import router as context_router
from app.api.recommendations import router as recommendations_router
from app.api.history import router as history_router
from app.api.auth import router as auth_router
from app.api.workers import router as workers_router
from app.api.users import router as users_router
from app.api.video_analysis import router as video_analysis_router
from app.api.recordings import router as recordings_router
from app.api.assistant import router as assistant_router
from app.api.risk_trend import router as risk_trend_router
from app.api.safety_report import router as safety_report_router
from app.api.session_report import router as session_report_router
from app.api.analytics import router as analytics_router
from app.api.live_timeline import router as live_timeline_router
from app.api.audit import router as audit_router
from app.api.pilot_requests import router as pilot_requests_router
from app.api.task_config import router as task_config_router
from app.api.worker_trends import router as worker_trends_router
from app.api.settings import router as settings_router
from app.api.predictions import router as predictions_router
from app.api.retention import router as retention_router
from app.api.privacy import router as privacy_router
from app.api.observations import router as observations_router
from app.api.report_digest import router as report_digest_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/api", tags=["Auth"])
api_router.include_router(dashboard_router, prefix="/api", tags=["Dashboard"])
api_router.include_router(sessions_router, prefix="/api", tags=["Sessions"])
api_router.include_router(reports_router, prefix="/api", tags=["Reports"])
api_router.include_router(cameras_router, prefix="/api", tags=["Cameras"])
api_router.include_router(workstations_router, prefix="/api", tags=["Workstations"])
api_router.include_router(deployment_router, prefix="/api", tags=["Deployment"])
api_router.include_router(manager_router, prefix="/api", tags=["Manager"])
api_router.include_router(alerts_router, prefix="/api", tags=["Alerts"])
api_router.include_router(session_lifecycle_router, prefix="/api", tags=["Session Lifecycle"])
api_router.include_router(video_feed_router, prefix="", tags=["Video"])
api_router.include_router(context_router, prefix="/api", tags=["Context Intelligence"])
api_router.include_router(recommendations_router, prefix="/api", tags=["Recommendations"])
api_router.include_router(history_router, prefix="/api", tags=["History"])
api_router.include_router(workers_router, prefix="/api", tags=["Workers"])
api_router.include_router(users_router, prefix="/api", tags=["Users"])
api_router.include_router(video_analysis_router, prefix="/api", tags=["Video Analysis"])
api_router.include_router(recordings_router, prefix="/api", tags=["Recordings"])
api_router.include_router(assistant_router, prefix="/api", tags=["Assistant"])
api_router.include_router(risk_trend_router, prefix="/api", tags=["Reports"])
api_router.include_router(safety_report_router, prefix="/api", tags=["Reports"])
api_router.include_router(session_report_router, prefix="/api", tags=["Reports"])
api_router.include_router(analytics_router, prefix="/api", tags=["Analytics"])
api_router.include_router(live_timeline_router, prefix="/api", tags=["Session Lifecycle"])
api_router.include_router(audit_router, prefix="/api", tags=["Audit Trail"])
api_router.include_router(pilot_requests_router, prefix="/api", tags=["Pilot Requests"])
api_router.include_router(task_config_router, prefix="/api", tags=["Task Config"])
api_router.include_router(worker_trends_router, prefix="/api", tags=["Worker Trends"])
api_router.include_router(settings_router, prefix="/api", tags=["Settings"])
api_router.include_router(predictions_router, prefix="/api", tags=["Predictions"])
api_router.include_router(retention_router, prefix="/api", tags=["Retention"])
api_router.include_router(privacy_router, prefix="/api", tags=["Privacy"])
api_router.include_router(observations_router, prefix="/api", tags=["Session Lifecycle"])
api_router.include_router(report_digest_router, prefix="/api", tags=["Reports"])
