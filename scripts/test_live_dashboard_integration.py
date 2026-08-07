from __future__ import annotations

import sys

import pytest
from collections import deque
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.features import FEATURE_COLUMNS
from backend.services.issue_detection import detect_posture_issues
from backend.services.recommendation_engine import get_recommendations
from backend.services.session_analytics import SessionAnalytics
from backend.services.task_recognition import TaskRecognition

from scripts.live_demo import draw_panel


_SHORT_TO_FEATURE = {
    "neck": "neck_flexion",
    "trunk": "trunk_flexion",
    "shoulder_sym": "shoulder_symmetry",
    "shoulder_l": "left_shoulder_elev",
    "shoulder_r": "right_shoulder_elev",
    "alignment": "alignment_deviation",
    "knee": "knee_angle",
}


def _make_features(**overrides) -> dict[str, float]:
    base = {
        "neck_flexion": 5.0,
        "trunk_flexion": 8.0,
        "left_shoulder_elev": 10.0,
        "right_shoulder_elev": 12.0,
        "shoulder_symmetry": 2.0,
        "alignment_deviation": 3.0,
        "knee_angle": 170.0,
    }
    mapped = {}
    for k, v in overrides.items():
        mapped[_SHORT_TO_FEATURE.get(k, k)] = v
    base.update(mapped)
    return base


def test_imports_resolve():
    assert TaskRecognition is not None
    assert SessionAnalytics is not None
    assert detect_posture_issues is not None
    assert get_recommendations is not None


def test_session_analytics_integration():
    analytics = SessionAnalytics()
    feats = _make_features()
    issues = detect_posture_issues(feats)
    analytics.update(feats, "LOW", issues, True, "12:00:00")
    analytics.update(_make_features(neck=35.0), "HIGH", issues, True, "12:00:05")
    analytics.update(_make_features(trunk=25.0), "MEDIUM", issues, True, "12:00:10")

    summary = analytics.get_summary()
    assert summary["total_frames"] == 3
    assert summary["risk_percentages"]["LOW"] == pytest.approx(33.3, rel=0.1)
    assert summary["risk_percentages"]["HIGH"] == pytest.approx(33.3, rel=0.1)
    assert summary["highest_risk_level"] == "HIGH"


def test_task_recognition_integration():
    kps = np.zeros((33, 3))
    kps[0] = [0.5, 0.2, 0.0]
    kps[11] = [0.4, 0.35, 0.0]
    kps[12] = [0.6, 0.35, 0.0]
    kps[13] = [0.35, 0.5, 0.0]
    kps[14] = [0.65, 0.5, 0.0]
    kps[15] = [0.3, 0.65, 0.0]
    kps[16] = [0.7, 0.65, 0.0]
    kps[23] = [0.42, 0.65, 0.0]
    kps[24] = [0.58, 0.65, 0.0]
    kps[25] = [0.43, 0.82, 0.0]
    kps[26] = [0.57, 0.82, 0.0]
    kps[27] = [0.44, 0.95, 0.0]
    kps[28] = [0.56, 0.95, 0.0]

    feats = _make_features(neck=3.0, trunk=4.0)
    tr = TaskRecognition()
    result = tr.detect_task(kps, feats)

    assert "task" in result
    assert "confidence" in result
    assert "reason" in result
    assert result["confidence"] > 0
    assert len(result["reason"]) > 0
    assert tr.get_current_task() == result["task"]
    assert tr.get_confidence() == result["confidence"]


def test_issue_recommendation_integration():
    feats = _make_features(neck=35.0, trunk=45.0, shoulder_symmetry=14.0)
    issues = detect_posture_issues(feats)
    recs = get_recommendations(issues)

    assert len(issues) > 0
    assert len(recs) > 0
    for issue in issues:
        assert "issue" in issue
        assert "severity" in issue
    for rec in recs:
        assert "worker_actions" in rec
        assert "supervisor_actions" in rec
        assert len(rec["worker_actions"]) > 0


def test_draw_panel_with_task_info():
    h, w = 1080, 1920
    frame = np.zeros((h, w, 3), dtype=np.uint8)

    feats = _make_features()
    risk_history = deque()
    for i in range(10):
        risk_history.append((float(i), 0.0 if i < 5 else 1.0))

    session_stats = {"avg_neck": 5.0, "avg_trunk": 8.0, "max_risk": "LOW"}
    task_info = {"task": "Neutral Standing", "confidence": 85.3, "reason": "Upright trunk; Minimal trunk flexion"}

    result = draw_panel(
        frame, feats, "LOW", 30.0, 95.0,
        risk_history, session_stats, "12:00:00", 0,
        issues=[],
        recommendations=[],
        task_info=task_info,
        panel_width=360,
    )

    assert result.shape == (h, w, 3)
    assert result.dtype == np.uint8

    center_col = result[30:60, w - 180, :]
    assert np.any(center_col > 0)


def test_draw_panel_without_task_info():
    h, w = 1080, 1920
    frame = np.zeros((h, w, 3), dtype=np.uint8)

    feats = _make_features()
    risk_history = deque()
    session_stats = {"avg_neck": 5.0, "avg_trunk": 8.0, "max_risk": "LOW"}

    result = draw_panel(
        frame, feats, "LOW", 30.0, 95.0,
        risk_history, session_stats, "12:00:00", 0,
        issues=[],
        recommendations=[],
        task_info=None,
        panel_width=360,
    )

    assert result.shape == (h, w, 3)


def test_analytics_skipped_when_no_person():
    analytics = SessionAnalytics()
    feats = _make_features()
    analytics.update(feats, "HIGH", [], False)
    summary = analytics.get_summary()
    assert summary["total_frames"] == 0
    assert summary["highest_risk_level"] == "LOW"


def test_full_pipeline_integration():
    feats = _make_features(neck=35.0, trunk=45.0)
    issues = detect_posture_issues(feats)
    recs = get_recommendations(issues)

    kps = np.zeros((33, 3))
    kps[0] = [0.5, 0.2, 0.0]
    kps[11] = [0.4, 0.35, 0.0]
    kps[12] = [0.6, 0.35, 0.0]
    kps[13] = [0.35, 0.5, 0.0]
    kps[14] = [0.65, 0.5, 0.0]
    kps[15] = [0.3, 0.65, 0.0]
    kps[16] = [0.7, 0.65, 0.0]
    kps[23] = [0.42, 0.65, 0.0]
    kps[24] = [0.58, 0.65, 0.0]
    kps[25] = [0.43, 0.82, 0.0]
    kps[26] = [0.57, 0.82, 0.0]

    tr = TaskRecognition()
    task_result = tr.detect_task(kps, feats)

    analytics = SessionAnalytics()
    analytics.update(feats, "HIGH", issues, True, "12:00:00")
    summary = analytics.get_summary()

    assert len(issues) >= 2
    assert len(recs) > 0
    assert task_result["task"] in ("Neutral Standing", "Assembly Work", "Reaching", "Lifting / Picking", "Inspection", "Unknown")
    assert summary["total_frames"] == 1
    assert summary["highest_risk_level"] == "HIGH"
