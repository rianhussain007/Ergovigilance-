"""Mock repository — returns hardcoded data matching the React frontend contracts.

Replace with ApiRepository when the real OpenCV/MediaPipe pipeline is connected.
"""

from typing import List, Optional

from app.repositories.base import DashboardRepository
from app.schemas.api import (
    DashboardResponse,
    SessionRecord,
    CameraInfo,
    WorkstationInfo,
    DeploymentMetrics,
    ManagerSummary,
    Alert,
    ContextSnapshotResponse,
    AlertsResponse,
    AlertResponse,
    AlertSummary,
    RecommendationsBundleResponse,
    HistoryResponse,
    HistoryPoint,
    HistoryStatistics,
    SessionDetailResponse,
)
from app.utils import mock_data


class MockRepository(DashboardRepository):
    async def get_dashboard(self) -> DashboardResponse:
        return DashboardResponse(**mock_data.DASHBOARD)

    async def get_latest_session(self) -> DashboardResponse:
        return DashboardResponse(**mock_data.DASHBOARD)

    async def get_sessions(self, current_user=None) -> List[SessionRecord]:
        return [SessionRecord(**s) for s in mock_data.SESSIONS]

    async def get_cameras(self) -> List[CameraInfo]:
        return [CameraInfo(**c) for c in mock_data.CAMERAS]

    async def get_workstations(self) -> List[WorkstationInfo]:
        return [WorkstationInfo(**w) for w in mock_data.WORKSTATIONS]

    async def get_deployment(self) -> DeploymentMetrics:
        return DeploymentMetrics(**mock_data.DEPLOYMENT)

    async def get_manager(self) -> ManagerSummary:
        return ManagerSummary(**mock_data.MANAGER)

    async def get_alerts(self) -> List[Alert]:
        return [Alert(**a) for a in mock_data.ALERTS]

    async def get_alerts_full(self) -> AlertsResponse:
        return AlertsResponse(
            active=[],
            history=[],
            summary=AlertSummary(
                total_fired=0,
                active_count=0,
                critical_count=0,
                acknowledged_count=0,
                consecutive_high=0,
            ),
        )

    async def get_context_snapshot(self) -> Optional[ContextSnapshotResponse]:
        return None

    async def get_recommendations(self) -> RecommendationsBundleResponse:
        return RecommendationsBundleResponse(bundle=None, total_generated=0)

    async def get_history(self) -> HistoryResponse:
        return HistoryResponse(
            points=[],
            statistics=HistoryStatistics(
                frames_stored=0,
                session_duration_seconds=0.0,
                average_risk=0.0,
                maximum_risk=0.0,
                minimum_risk=0.0,
                average_fatigue=0.0,
                average_exposure=0.0,
            ),
        )

    async def get_session_detail(self, session_id: str, current_user=None) -> Optional[SessionDetailResponse]:
        return None
