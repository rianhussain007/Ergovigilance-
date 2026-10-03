import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.repositories.live import LiveRepository
from backend.core.types import LiveState


class _FakeAnalytics:
    def get_summary(self):
        return {"total_frames": 0}


class _FakeService:
    def __init__(self, state) -> None:
        self._state = state
        self.analytics = _FakeAnalytics()

    def get_state_snapshot(self):
        return self._state


class LiveDashboardPhantomSessionTest(unittest.TestCase):
    """Regression: the dashboard must never render a phantom LIVE session.

    A start/stop race (a slow background init that finishes after the session
    was stopped) used to leave ``camera_status == "active"`` while
    ``session_active`` was already False. ``_build_dashboard`` read
    ``camera_status`` directly, so the header and Live Monitoring page showed a
    LIVE session with an ever-growing duration and a dead feed — while
    ``/api/session/status`` correctly reported "not active".
    """

    def _dashboard_for(self, state: LiveState):
        with patch(
            "app.repositories.live.get_live_service",
            return_value=_FakeService(state),
        ):
            return LiveRepository()._build_dashboard()

    def test_stopped_session_with_stale_active_camera_is_not_reported_live(self) -> None:
        state = LiveState(
            session_active=False,  # /api/session/status would say inactive
            session_id="SESH-2026-10-03_07-45-36",
            session_start=time.time() - (91 * 60 + 44),
            camera_status="active",  # stale — left behind by the race
        )
        dash = self._dashboard_for(state)
        self.assertEqual(dash.session.cameraStatus, "disconnected")
        self.assertEqual(dash.session.id, "")
        self.assertEqual(dash.session.duration, 0)
        self.assertEqual(dash.session.startTime, "")
        self.assertFalse(dash.session.cameraReconnecting)

    def test_active_session_still_reports_camera_and_duration(self) -> None:
        state = LiveState(
            session_active=True,
            session_id="SESH-LIVE-TEST",
            session_start=time.time() - 10,
            camera_status="active",
            camera_reconnecting=True,
            fps=27.0,
        )
        dash = self._dashboard_for(state)
        self.assertEqual(dash.session.cameraStatus, "active")
        self.assertEqual(dash.session.id, "SESH-LIVE-TEST")
        self.assertGreaterEqual(dash.session.duration, 9)
        self.assertTrue(dash.session.cameraReconnecting)
        # Real pipeline FPS must survive the schema round-trip.
        self.assertEqual(dash.liveStatus.fps, 27.0)


if __name__ == "__main__":
    unittest.main()
