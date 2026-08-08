"""Regression tests for the task-classifier drift canary."""

import unittest

from app.schemas.api import DeploymentMetrics, ModelDriftMetrics
from backend.services.drift_monitor import DriftMonitor, reset_drift_monitor, get_drift_monitor


class DriftMonitorTest(unittest.TestCase):
    def setUp(self):
        reset_drift_monitor()

    def tearDown(self):
        reset_drift_monitor()

    def test_schema_round_trip(self):
        m = DriftMonitor()
        m.record("model", 0.9)
        m.record("gaussian", 0.4)
        drift = ModelDriftMetrics(**m.summary())
        self.assertEqual(drift.samples, 2)
        self.assertEqual(drift.fallback_rate, 50.0)
        # DeploymentMetrics accepts the drift payload (Optional field).
        dm = DeploymentMetrics(
            backendStatus="ok",
            backendVersion="0.1.0",
            backendUptimeSeconds=1.0,
            databaseEngine="SQLite",
            databaseSizeBytes=0,
            databaseStatus="ok",
            cameraCount=0,
            registeredWorkerCount=0,
            activeSessionCount=0,
            sessionActive=False,
            drift=drift,
        )
        self.assertEqual(dm.drift.samples, 2)
        # And a mock-style deployment without drift still constructs.
        dm2 = DeploymentMetrics(
            backendStatus="ok",
            backendVersion="0.1.0",
            backendUptimeSeconds=1.0,
            databaseEngine="SQLite",
            databaseSizeBytes=0,
            databaseStatus="ok",
            cameraCount=0,
            registeredWorkerCount=0,
            activeSessionCount=0,
            sessionActive=False,
        )
        self.assertIsNone(dm2.drift)

    def test_empty_summary(self):
        m = DriftMonitor()
        s = m.summary()
        self.assertEqual(s["samples"], 0)
        self.assertTrue(s["healthy"])
        self.assertEqual(s["trend"], "stable")
        self.assertIsNone(s["avg_confidence"])

    def test_all_model_is_healthy(self):
        m = DriftMonitor()
        for _ in range(20):
            m.record("model", 0.9)
        s = m.summary()
        self.assertEqual(s["model_samples"], 20)
        self.assertEqual(s["gaussian_samples"], 0)
        self.assertEqual(s["fallback_rate"], 0.0)
        self.assertTrue(s["healthy"])
        self.assertAlmostEqual(s["avg_confidence"], 0.9, places=2)

    def test_high_fallback_is_unhealthy(self):
        m = DriftMonitor()
        for _ in range(10):
            m.record("model", 0.9)
        for _ in range(30):
            m.record("gaussian", 0.4)
        s = m.summary()
        self.assertEqual(s["fallback_rate"], 75.0)
        self.assertFalse(s["healthy"])
        self.assertGreater(s["gaussian_samples"], s["model_samples"])

    def test_rising_trend_detected(self):
        m = DriftMonitor()
        # Early half: mostly model
        for _ in range(12):
            m.record("model", 0.9)
        # Later half: mostly gaussian (drift)
        for _ in range(12):
            m.record("gaussian", 0.3)
        s = m.summary()
        self.assertEqual(s["trend"], "rising")
        self.assertGreater(s["trend_delta_pp"], 0.0)

    def test_falling_trend_detected(self):
        m = DriftMonitor()
        for _ in range(12):
            m.record("gaussian", 0.3)
        for _ in range(12):
            m.record("model", 0.9)
        s = m.summary()
        self.assertEqual(s["trend"], "falling")
        self.assertLess(s["trend_delta_pp"], 0.0)

    def test_small_sample_count_never_reports_trend(self):
        """Short sessions shouldn't false-alert on jitter."""
        m = DriftMonitor()
        for _ in range(5):
            m.record("model", 0.9)
        for _ in range(5):
            m.record("gaussian", 0.3)
        s = m.summary()
        self.assertEqual(s["trend"], "stable")

    def test_window_cutoff_drops_old_samples(self):
        m = DriftMonitor(window_seconds=1)
        # Inject a fixed clock so the cutoff is deterministic (no real sleeps).
        m._now = lambda: 1010.0
        m.record("model", 0.9, now=1000.0)   # 10s old — outside 1s window
        m.record("gaussian", 0.3, now=1009.5)
        m.record("model", 0.8, now=1010.0)
        s = m.summary()
        # Only samples with now >= (1010 - 1) survive.
        self.assertEqual(s["samples"], 2)
        self.assertEqual(s["gaussian_samples"], 1)
        self.assertEqual(s["model_samples"], 1)

    def test_singleton(self):
        self.assertIs(get_drift_monitor(), get_drift_monitor())

    def test_reset_clears_singleton(self):
        m = get_drift_monitor()
        m.record("model", 0.9)
        reset_drift_monitor()
        self.assertEqual(get_drift_monitor().summary()["samples"], 0)


if __name__ == "__main__":
    unittest.main()
