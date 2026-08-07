"""JSON file-based session repository."""

from __future__ import annotations

import json
import os
from pathlib import Path

from backend.persistence.models import SessionRecord
from backend.persistence.repository import SessionRepository


class JsonSessionRepository(SessionRepository):
    """Persists session records as JSON files.

    File structure:
        {base_dir}/
            {session_id}.json

    Each file contains one SessionRecord serialized as JSON.
    Thread-safe for single-process use.
    """

    def __init__(self, base_dir: str | Path) -> None:
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)

    @property
    def base_dir(self) -> Path:
        return self._base_dir

    def _session_path(self, session_id: str) -> Path:
        safe_id = session_id.replace("/", "_").replace("\\", "_")
        return self._base_dir / f"{safe_id}.json"

    def save(self, record: SessionRecord) -> None:
        """Save session record as JSON file."""
        path = self._session_path(record.session_id)
        data = record.to_dict()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load(self, session_id: str) -> SessionRecord | None:
        """Load session record from JSON file."""
        path = self._session_path(session_id)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return SessionRecord.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError):
            return None

    def list_sessions(self) -> list[str]:
        """List all session IDs from JSON files."""
        ids = []
        for p in self._base_dir.glob("*.json"):
            ids.append(p.stem)
        return sorted(ids)

    def delete(self, session_id: str) -> bool:
        """Delete a session JSON file."""
        path = self._session_path(session_id)
        if not path.exists():
            return False
        path.unlink()
        return True

    def exists(self, session_id: str) -> bool:
        """Check if a session file exists."""
        return self._session_path(session_id).exists()
