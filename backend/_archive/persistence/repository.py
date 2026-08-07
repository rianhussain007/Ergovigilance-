"""Abstract repository interface for session persistence."""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.persistence.models import SessionRecord


class SessionRepository(ABC):
    """Abstract interface for session data persistence.

    All storage backends implement this interface.
    Current: JsonSessionRepository (JSON files).
    Future: SqlSessionRepository (SQL database).
    """

    @abstractmethod
    def save(self, record: SessionRecord) -> None:
        """Save or update a session record."""

    @abstractmethod
    def load(self, session_id: str) -> SessionRecord | None:
        """Load a session record by ID. Returns None if not found."""

    @abstractmethod
    def list_sessions(self) -> list[str]:
        """List all stored session IDs."""

    @abstractmethod
    def delete(self, session_id: str) -> bool:
        """Delete a session record. Returns True if deleted, False if not found."""
