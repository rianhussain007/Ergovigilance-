"""Tests for the task configuration endpoint (GET /api/task-modifiers).

The endpoint exposes the ContextIntelligenceEngine's task modifier table so
the frontend no longer hardcodes a drifting copy. Tests verify the shape of
the returned table and that it stays in sync with the engine.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


class TestTaskModifiers:
    def test_task_modifiers_endpoint_public(self, client: TestClient):
        """Task modifiers are read-only config data — no auth required."""
        res = client.get("/api/task-modifiers")
        assert res.status_code == 200

    def test_task_modifiers_is_dict(self, client: TestClient):
        res = client.get("/api/task-modifiers")
        data = res.json()
        assert isinstance(data, dict)

    def test_task_modifiers_match_engine(self, client: TestClient):
        """The API response matches the engine's internal table (no drift)."""
        from backend.context.engine import _TASK_MODIFIERS

        res = client.get("/api/task-modifiers")
        assert res.json() == _TASK_MODIFIERS

    def test_task_modifiers_have_expected_keys(self, client: TestClient):
        """Each task maps to a numeric modifier."""
        res = client.get("/api/task-modifiers")
        data = res.json()
        assert data, "Task modifier table must not be empty"
        for task, modifier in data.items():
            assert isinstance(modifier, (int, float)), f"Task {task} modifier must be numeric"
            assert modifier >= 0, f"Task {task} modifier must be non-negative"
