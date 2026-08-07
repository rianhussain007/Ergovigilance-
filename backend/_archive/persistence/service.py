"""Persistence Service — collects data from engines and saves to repository."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from backend.alerts.engine import AlertEngine
from backend.history.engine import HistoryEngine
from backend.persistence.models import SessionRecord
from backend.persistence.repository import SessionRepository
from backend.recommendations.engine import RecommendationEngine


class PersistenceService:
    """Collects data from engines and persists via a SessionRepository.

    Usage::

        service = PersistenceService(repository)
        service.start_session(session_id, worker_id)
        # ... monitoring runs ...
        service.end_session()
    """

    def __init__(self, repository: SessionRepository) -> None:
        self._repository = repository
        self._session_id: Optional[str] = None
        self._worker_id: Optional[str] = None
        self._started_at: Optional[str] = None

        # Engine references (set via attach_*)
        self._history_engine: Optional[HistoryEngine] = None
        self._alert_engine: Optional[AlertEngine] = None
        self._recommendation_engine: Optional[RecommendationEngine] = None

    @property
    def session_id(self) -> Optional[str]:
        return self._session_id

    @property
    def is_active(self) -> bool:
        return self._session_id is not None

    def attach_history(self, engine: HistoryEngine) -> None:
        self._history_engine = engine

    def attach_alerts(self, engine: AlertEngine) -> None:
        self._alert_engine = engine

    def attach_recommendations(self, engine: RecommendationEngine) -> None:
        self._recommendation_engine = engine

    def start_session(self, session_id: str, worker_id: str = "unknown") -> None:
        """Start a new session. Saves any existing session first."""
        if self._session_id is not None:
            self.end_session()
        self._session_id = session_id
        self._worker_id = worker_id
        self._started_at = datetime.now(timezone.utc).isoformat()

    def end_session(self) -> SessionRecord | None:
        """End the current session and persist it. Returns the saved record."""
        if self._session_id is None:
            return None

        record = self._build_record()
        self._repository.save(record)

        session_id = self._session_id
        self._session_id = None
        self._worker_id = None
        self._started_at = None

        return record

    def save_snapshot(self) -> SessionRecord | None:
        """Save the current session state without ending it."""
        if self._session_id is None:
            return None
        record = self._build_record()
        self._repository.save(record)
        return record

    def load(self, session_id: str) -> Optional[SessionRecord]:
        return self._repository.load(session_id)

    def list_sessions(self) -> list[str]:
        return self._repository.list_sessions()

    def delete(self, session_id: str) -> bool:
        return self._repository.delete(session_id)

    def _build_record(self) -> SessionRecord:
        """Build a SessionRecord from current engine states."""
        stats = {}
        snapshots = []
        alerts = []
        recommendations = []

        if self._history_engine is not None:
            history_data = self._history_engine.export()
            stats["history"] = history_data.get("statistics", {})
            snapshots = history_data.get("snapshots", [])

        if self._alert_engine is not None:
            alert_data = self._alert_engine.export()
            stats["alerts"] = {
                "total_fired": alert_data.get("total_fired", 0),
                "active_count": len(alert_data.get("active_alerts", [])),
            }
            alerts = alert_data.get("active_alerts", []) + alert_data.get("history", [])

        if self._recommendation_engine is not None:
            rec_data = self._recommendation_engine.export()
            stats["recommendations"] = {
                "total_generated": rec_data.get("total_generated", 0),
            }
            bundle = rec_data.get("bundle")
            if bundle is not None:
                recommendations = bundle.get("recommendations", [])

        return SessionRecord(
            session_id=self._session_id or "",
            started_at=self._started_at or "",
            ended_at=datetime.now(timezone.utc).isoformat(),
            worker_id=self._worker_id or "unknown",
            statistics=stats,
            snapshots=snapshots,
            alerts=alerts,
            recommendations=recommendations,
        )
