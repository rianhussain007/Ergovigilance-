"""Abstract repository interface — follows the React frontend's repository pattern."""

from abc import ABC, abstractmethod
from typing import List, Optional

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
    RecommendationsBundleResponse,
    HistoryResponse,
    SessionDetailResponse,
)


class RepositoryUnavailableError(RuntimeError):
    """A repository cannot serve REAL data (e.g. the database is unreachable).

    API layers translate this into HTTP 503 — never into canned or demo data.
    """


class DashboardRepository(ABC):
    @abstractmethod
    async def get_dashboard(self) -> DashboardResponse:
        ...

    @abstractmethod
    async def get_latest_session(self) -> DashboardResponse:
        ...

    @abstractmethod
    async def get_sessions(self, current_user=None) -> List[SessionRecord]:
        ...

    @abstractmethod
    async def get_cameras(self) -> List[CameraInfo]:
        ...

    @abstractmethod
    async def get_workstations(self) -> List[WorkstationInfo]:
        ...

    @abstractmethod
    async def get_deployment(self) -> DeploymentMetrics:
        ...

    @abstractmethod
    async def get_manager(self) -> ManagerSummary:
        ...

    @abstractmethod
    async def get_alerts(self) -> List[Alert]:
        ...

    @abstractmethod
    async def get_alerts_full(self) -> AlertsResponse:
        ...

    async def get_alerts_summary(self, recent_n: int = 6) -> AlertsResponse:
        """Lightweight alert fetch — override for efficiency. Default falls back to full scan."""
        return await self.get_alerts_full()

    @abstractmethod
    async def get_context_snapshot(self) -> Optional[ContextSnapshotResponse]:
        ...

    @abstractmethod
    async def get_recommendations(self) -> RecommendationsBundleResponse:
        ...

    @abstractmethod
    async def get_history(self) -> HistoryResponse:
        ...

    @abstractmethod
    async def get_session_detail(self, session_id: str, current_user=None) -> Optional[SessionDetailResponse]:
        ...
