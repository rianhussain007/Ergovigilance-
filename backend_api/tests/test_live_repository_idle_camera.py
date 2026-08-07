import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app.repositories.live as live_repo_module

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.repositories.live import LiveRepository


class _FakeService:
    def is_running(self) -> bool:
        return False

    def get_state_snapshot(self):
        return SimpleNamespace(fps=0, risk_level="LOW", timestamp="", session_id=None)


class LiveRepositoryIdleCameraTest(unittest.TestCase):
    def setUp(self) -> None:
        live_repo_module._camera_cache = []
        live_repo_module._camera_cache_time = 0

    def test_idle_requests_reuse_cached_cameras_without_reprobing(self) -> None:
        repo = LiveRepository()
        fake_service = _FakeService()
        fake_service.is_running = lambda: False

        with patch("app.repositories.live.get_live_service", return_value=fake_service), patch(
            "backend.services.camera_manager.detect_cameras",
            side_effect=[
                [SimpleNamespace(index=0, name="USB Camera")],
                AssertionError("detect_cameras should not be called again while the idle cache is still fresh"),
            ],
        ) as detect_mock:
            first_result = asyncio.run(repo.get_cameras())
            second_result = asyncio.run(repo.get_cameras())

        self.assertEqual(len(first_result), 1)
        self.assertEqual(first_result[0].status, "available")
        self.assertEqual(first_result[0].name, "USB Camera")
        self.assertEqual(second_result, first_result)
        self.assertEqual(detect_mock.call_count, 1)

    def test_idle_requests_return_detected_cameras_when_available(self) -> None:
        repo = LiveRepository()

        fake_service = _FakeService()
        fake_service.is_running = lambda: False

        with patch("app.repositories.live.get_live_service", return_value=fake_service), patch(
            "backend.services.camera_manager.detect_cameras",
            return_value=[SimpleNamespace(index=0, name="USB Camera")],
        ) as detect_mock:
            result = asyncio.run(repo.get_cameras())

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].status, "available")
        self.assertEqual(result[0].name, "USB Camera")
        detect_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
