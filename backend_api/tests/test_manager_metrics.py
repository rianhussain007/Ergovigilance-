"""Regression tests for cross-session manager metrics."""

import unittest
from datetime import datetime, timedelta, timezone

from app.services.manager_metrics import compute_manager_metrics, session_avg_risk


def _ts(days_ago: int) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return dt.strftime("%Y%m%d_%H%M%S")


def _session(days_ago: int, pct: dict, highest: str = "LOW") -> dict:
    return {
        "session_timestamp": _ts(days_ago),
        "risk_percentages": pct,
        "highest_risk_level": highest,
    }


class SessionAvgRiskTest(unittest.TestCase):
    def test_weighted_average(self):
        self.assertAlmostEqual(session_avg_risk({"risk_percentages": {"LOW": 100, "MEDIUM": 0, "HIGH": 0}}), 0.0)
        self.assertAlmostEqual(session_avg_risk({"risk_percentages": {"LOW": 0, "MEDIUM": 100, "HIGH": 0}}), 50.0)
        self.assertAlmostEqual(session_avg_risk({"risk_percentages": {"LOW": 0, "MEDIUM": 0, "HIGH": 100}}), 100.0)
        # 50/50 medium+high
        self.assertAlmostEqual(session_avg_risk({"risk_percentages": {"LOW": 0, "MEDIUM": 50, "HIGH": 50}}), 75.0)

    def test_fallback_to_highest_level(self):
        self.assertAlmostEqual(session_avg_risk({"highest_risk_level": "HIGH"}), 90.0)
        self.assertAlmostEqual(session_avg_risk({}), 10.0)

    def test_missing_percentages_key(self):
        self.assertAlmostEqual(session_avg_risk({"highest_risk_level": "MEDIUM"}), 50.0)


class ComputeManagerMetricsTest(unittest.TestCase):
    def test_empty_sessions(self):
        m = compute_manager_metrics([])
        self.assertIsNone(m["weeklyImprovement"])
        self.assertIsNone(m["averageCompliance"])
        self.assertIsNone(m["healthScore"])

    def test_single_session(self):
        m = compute_manager_metrics([_session(1, {"LOW": 100, "MEDIUM": 0, "HIGH": 0})])
        self.assertAlmostEqual(m["averageCompliance"], 100.0)
        self.assertAlmostEqual(m["healthScore"], 100.0)
        self.assertEqual(m["weeklyImprovement"], 0.0)  # no baseline → stable

    def test_improvement_positive_when_risk_drops(self):
        sessions = [
            _session(10, {"LOW": 0, "MEDIUM": 0, "HIGH": 100}),  # last week: risky
            _session(1, {"LOW": 100, "MEDIUM": 0, "HIGH": 0}),    # this week: safe
        ]
        m = compute_manager_metrics(sessions)
        self.assertGreater(m["weeklyImprovement"], 0.0)

    def test_deterioration_negative(self):
        sessions = [
            _session(10, {"LOW": 0, "MEDIUM": 50, "HIGH": 50}),   # last week: 75
            _session(1, {"LOW": 0, "MEDIUM": 0, "HIGH": 100}),    # this week: 100
        ]
        m = compute_manager_metrics(sessions)
        self.assertIsNotNone(m["weeklyImprovement"])
        self.assertLess(m["weeklyImprovement"], 0.0)

    def test_improvement_zero_baseline_is_none(self):
        # Prev week perfectly safe (avg risk 0) — percent change undefined.
        sessions = [
            _session(10, {"LOW": 100, "MEDIUM": 0, "HIGH": 0}),
            _session(1, {"LOW": 0, "MEDIUM": 0, "HIGH": 100}),
        ]
        m = compute_manager_metrics(sessions)
        self.assertIsNone(m["weeklyImprovement"])

    def test_compliance_bounds(self):
        sessions = [_session(2, {"LOW": 0, "MEDIUM": 0, "HIGH": 100})]
        m = compute_manager_metrics(sessions)
        self.assertAlmostEqual(m["averageCompliance"], 0.0)

    def test_health_score_recency_weighting(self):
        # Same average risk, but recent session is safe — health should be above 0.
        sessions = [
            _session(30, {"LOW": 0, "MEDIUM": 0, "HIGH": 100}),
            _session(1, {"LOW": 100, "MEDIUM": 0, "HIGH": 0}),
        ]
        m = compute_manager_metrics(sessions)
        self.assertGreater(m["healthScore"], 50.0)


if __name__ == "__main__":
    unittest.main()
