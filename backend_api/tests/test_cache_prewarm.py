"""Regression tests for the startup cache-prewarm performance fixes.

Measured problem (before the fix): the first /api/sessions call took ~3.25s
(scanning + parsing every session JSON on disk) and the first /api/deployment
and /api/cameras calls took ~9s (probing physical camera devices), because
both caches were cold and rebuilt lazily with a short TTL.

Fixes under test:
1. app.services.session_cache — SESSION_CACHE_TTL raised to 300s + a
   prewarm_session_cache() that builds the cache eagerly at startup.
2. app.repositories.live._ensure_camera_cache / warm_camera_cache — camera
   probing consolidated, cached for 5 min, and prewarmable at startup.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services import session_cache as sc  # noqa: E402
from app.repositories import live as live_repo  # noqa: E402


class SessionCacheTest(unittest.TestCase):
    def setUp(self):
        sc._session_cache = None
        sc._session_cache_time = 0

    def test_ttl_is_long(self):
        """TTL must be minutes, not seconds — the old 30s TTL re-scanned disk every poll."""
        assert sc.SESSION_CACHE_TTL >= 300

    def test_prewarm_then_get_all_sessions_uses_cache(self):
        with patch.object(sc, "_scan_session_files", return_value=[{"session_id": "S1"}]) as mock_scan:
            sc.prewarm_session_cache()
            assert mock_scan.call_count == 1
            # Second read within TTL must NOT rescan disk
            sc.get_all_sessions()
            sc.get_all_sessions()
            assert mock_scan.call_count == 1
            assert sc.get_all_sessions() == [{"session_id": "S1"}]

    def test_invalidate_forces_rescan(self):
        with patch.object(sc, "_scan_session_files", return_value=[{"session_id": "S1"}]) as mock_scan:
            sc.prewarm_session_cache()
            assert mock_scan.call_count == 1
            sc.invalidate_session_cache()
            sc.get_all_sessions()
            assert mock_scan.call_count == 2

    def test_prewarm_tolerates_missing_dir(self):
        with patch.object(sc, "_scan_session_files", return_value=[]):
            sc.prewarm_session_cache()
            assert sc.get_all_sessions() == []


class CameraCacheTest(unittest.TestCase):
    def setUp(self):
        live_repo._camera_cache = []
        live_repo._camera_cache_time = 0

    def _fake_detected(self):
        return [SimpleNamespace(index=0, name="Cam 0"), SimpleNamespace(index=1, name="Cam 1")]

    def test_ensure_probes_then_caches(self):
        with patch(
            "backend.services.camera_manager.detect_cameras",
            return_value=self._fake_detected(),
        ) as mock_detect:
            live_repo._ensure_camera_cache()
            assert mock_detect.call_count == 1
            # Within TTL — cache hit, no second probe
            live_repo._ensure_camera_cache()
            assert mock_detect.call_count == 1
            # force=True probes again (used by startup prewarm)
            live_repo._ensure_camera_cache(force=True)
            assert mock_detect.call_count == 2

        assert len(live_repo._camera_cache) == 2
        assert live_repo._camera_cache[0].id == "cam-0"
        assert live_repo._camera_cache[0].status == "available"

    def test_probe_failure_does_not_raise_and_backs_off(self):
        with patch(
            "backend.services.camera_manager.detect_cameras",
            side_effect=OSError("no devices"),
        ) as mock_detect:
            # Must not raise — the repo surface then reports zero cameras.
            live_repo._ensure_camera_cache(force=True)
            assert mock_detect.call_count == 1
            assert live_repo._camera_cache == []

    def test_warm_camera_cache_smoke(self):
        with patch(
            "backend.services.camera_manager.detect_cameras",
            return_value=self._fake_detected(),
        ) as mock_detect:
            live_repo.warm_camera_cache()
            assert mock_detect.call_count == 1
            assert len(live_repo._camera_cache) == 2


if __name__ == "__main__":
    unittest.main()
