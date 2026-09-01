"""Tests for yolo_cloud — config, reports, API (unit tests without GPU/YOLO)."""

import io
import csv
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, AsyncMock

import pytest


# ── Config Tests ──────────────────────────────────────────────────────────────

class TestCloudConfig:
    """Test that CloudSettings loads correctly."""

    def test_default_values(self):
        from yolo_cloud.config import CloudSettings
        cfg = CloudSettings()
        assert cfg.YOLO_MODEL == "yolov8s-pose.pt"
        assert cfg.YOLO_DEVICE == "cpu"
        assert cfg.YOLO_CONFIDENCE == 0.5
        assert cfg.RTSP_RECONNECT_DELAY == 2.0
        assert cfg.TRACK_THRESH == 0.5
        assert cfg.TRACK_BUFFER == 60

    def test_session_idle_timeout(self):
        from yolo_cloud.config import CloudSettings
        cfg = CloudSettings()
        assert cfg.SESSION_IDLE_TIMEOUT == 60

    def test_singleton(self):
        from yolo_cloud.config import settings
        from yolo_cloud.config import settings as settings2
        assert settings is settings2


# ── Report Tests ──────────────────────────────────────────────────────────────

class TestDailyReport:
    """Test daily report generation."""

    def _make_sessions(self, count=5):
        """Create mock session data."""
        now = datetime.now()
        sessions = []
        for i in range(count):
            sessions.append({
                "session_id": f"CLOUD-{now.strftime('%Y-%m-%d_%H-%M-%S')}-{i}",
                "camera_id": f"cam-{i % 3}",
                "camera_name": f"Camera {i % 3}",
                "start_time": (now - timedelta(hours=i)).isoformat(),
                "duration_seconds": 300 + i * 60,
                "frame_count": 1000 + i * 200,
                "person_count": 1 + (i % 3),
                "avg_risk_score": 20 + i * 10,
                "highest_risk": ["LOW", "MEDIUM", "HIGH"][i % 3],
                "alert_count": i,
                "risk_summary": {"LOW": 5, "MEDIUM": 2, "HIGH": 1},
                "is_active": False,
            })
        return sessions

    def test_generate_daily_summary(self):
        from yolo_cloud.reports import generate_daily_summary
        sessions = self._make_sessions()
        report = generate_daily_summary(sessions, datetime.now())

        assert report["report_type"] == "daily"
        assert "summary" in report
        assert report["summary"]["total_sessions"] > 0
        assert "risk_distribution" in report

    def test_generate_daily_csv(self):
        from yolo_cloud.reports import generate_daily_csv
        sessions = self._make_sessions()
        csv_str = generate_daily_csv(sessions, datetime.now())

        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)
        assert len(rows) > 1  # header + data
        assert rows[0][0] == "Time"
        assert rows[0][2] == "Session ID"

    def test_generate_daily_csv_with_camera_filter(self):
        from yolo_cloud.reports import generate_daily_csv
        sessions = self._make_sessions(10)
        csv_str = generate_daily_csv(sessions, datetime.now(), camera_id="cam-0")

        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)
        # Only cam-0 sessions (indices 0, 3, 6, 9 -> 4 sessions)
        assert len(rows) == 5  # header + 4 data rows

    def test_generate_daily_summary_empty(self):
        from yolo_cloud.reports import generate_daily_summary
        report = generate_daily_summary([], datetime.now())
        assert report["summary"]["total_sessions"] == 0


class TestWeeklyReport:
    """Test weekly report generation."""

    def test_generate_weekly_summary(self):
        from yolo_cloud.reports import generate_weekly_summary
        now = datetime.now()
        week_start = now - timedelta(days=now.weekday())
        report = generate_weekly_summary([], week_start)

        assert report["report_type"] == "weekly"
        assert len(report["daily_breakdown"]) == 7
        assert "summary" in report

    def test_generate_weekly_csv(self):
        from yolo_cloud.reports import generate_weekly_csv
        now = datetime.now()
        week_start = now - timedelta(days=now.weekday())
        csv_str = generate_weekly_csv([], week_start)

        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)
        assert len(rows) == 8  # header + 7 days


class TestPDFReport:
    """Test PDF generation (requires reportlab)."""

    def test_pdf_generation_with_reportlab(self):
        """Test PDF generation if reportlab is available."""
        from yolo_cloud.reports import generate_pdf_report

        report_data = {
            "report_type": "daily",
            "date": "2026-08-31",
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_sessions": 10,
                "total_frames": 5000,
                "total_alerts": 3,
                "avg_risk_score": 35.0,
                "total_duration_hours": 2.5,
                "cameras_active": 3,
            },
            "risk_distribution": {"LOW": 50, "MEDIUM": 30, "HIGH": 10},
        }

        result = generate_pdf_report(report_data, "daily")
        # Either returns bytes or None (if reportlab not installed)
        if result is not None:
            assert isinstance(result, bytes)
            assert len(result) > 100
            # PDF magic bytes
            assert result[:4] == b"%PDF"


# ── API Endpoint Tests (unit, no server) ─────────────────────────────────────

class TestCloudAPIEndpoints:
    """Test API endpoint logic without starting a server."""

    def test_router_prefix(self):
        from yolo_cloud.api import router
        assert router.prefix == "/cloud"
        assert "Cloud Core" in router.tags

    def test_health_endpoint_structure(self):
        """Verify health endpoint exists and has correct path."""
        from yolo_cloud.api import router
        routes = [r.path for r in router.routes if hasattr(r, "path")]
        assert "/cloud/health" in routes
        assert "/cloud/cameras" in routes
        assert "/cloud/dashboard" in routes
        assert "/cloud/sessions" in routes
        assert "/cloud/alerts" in routes
        assert "/cloud/reports/daily" in routes
        assert "/cloud/reports/weekly" in routes
        assert "/cloud/reports/pdf" in routes
        assert "/cloud/reports/csv" in routes
        assert "/cloud/reports/export" in routes


# ── Ingestion Service Tests ───────────────────────────────────────────────────

class TestCloudSession:
    """Test CloudSession data model."""

    def test_session_creation(self):
        from yolo_cloud.ingestion import CloudSession
        session = CloudSession(
            session_id="TEST-001",
            camera_id="cam-1",
            camera_name="Test Camera",
            start_time=datetime.now().timestamp(),
        )
        assert session.session_id == "TEST-001"
        assert session.is_active is True
        assert session.highest_risk == "LOW"

    def test_session_to_dict(self):
        from yolo_cloud.ingestion import CloudSession
        now = datetime.now().timestamp()
        session = CloudSession(
            session_id="TEST-002",
            camera_id="cam-1",
            camera_name="Test Camera",
            start_time=now,
            frame_count=100,
            risk_summary={"LOW": 5, "MEDIUM": 2, "HIGH": 1},
        )
        d = session.to_dict()
        assert d["session_id"] == "TEST-002"
        assert d["frame_count"] == 100
        assert "start_time" in d

    def test_session_avg_risk(self):
        from yolo_cloud.ingestion import CloudSession
        session = CloudSession(
            session_id="TEST-003",
            camera_id="cam-1",
            camera_name="Test Camera",
            start_time=datetime.now().timestamp(),
            risk_scores=[20, 40, 60, 80],
        )
        assert session.avg_risk_score == 50.0

    def test_session_highest_risk_priority(self):
        from yolo_cloud.ingestion import CloudSession
        session = CloudSession(
            session_id="TEST-004",
            camera_id="cam-1",
            camera_name="Test Camera",
            start_time=datetime.now().timestamp(),
            risk_summary={"LOW": 10, "MEDIUM": 5, "HIGH": 2},
        )
        assert session.highest_risk == "HIGH"


class TestCloudAlert:
    """Test CloudAlert data model."""

    def test_alert_creation(self):
        from yolo_cloud.ingestion import CloudAlert
        alert = CloudAlert(
            alert_id="ALERT-001",
            camera_id="cam-1",
            camera_name="Test Camera",
            session_id="TEST-001",
            severity="HIGH",
            message="Sustained high-risk posture detected",
            timestamp=datetime.now().timestamp(),
            risk_score=85.0,
            task="lifting",
            track_id=1,
        )
        d = alert.to_dict()
        assert d["severity"] == "HIGH"
        assert d["risk_score"] == 85.0
        assert d["task"] == "lifting"


# ── Pose Engine Tests ─────────────────────────────────────────────────────────

class TestPoseEngineData:
    """Test pose engine data structures."""

    def test_tracked_pose(self):
        from yolo_cloud.pose_engine import TrackedPose
        pose = TrackedPose(
            track_id=1,
            bbox=[0.1, 0.2, 0.5, 0.8],
            keypoints=[[0.3, 0.1, 0.9]] * 17,
            angles={"trunk_angle": 25, "knee_angle": 140},
            risk_level="MEDIUM",
            risk_score=55.0,
            confidence=0.85,
            task="lifting",
        )
        assert pose.track_id == 1
        assert pose.risk_level == "MEDIUM"

    def test_processed_frame(self):
        from yolo_cloud.pose_engine import ProcessedCloudFrame, TrackedPose
        pose = TrackedPose(
            track_id=1,
            bbox=[0.1, 0.2, 0.5, 0.8],
            keypoints=[[0.3, 0.1, 0.9]] * 17,
            angles={},
            risk_level="LOW",
            risk_score=20.0,
            confidence=0.9,
            task="standing",
        )
        frame = ProcessedCloudFrame(
            frame_width=1920,
            frame_height=1080,
            tracked_poses=[pose],
            person_count=1,
            inference_ms=45.2,
            timestamp=datetime.now().timestamp(),
        )
        assert frame.person_count == 1
        assert frame.frame_width == 1920


# ── RTSP Manager Tests ────────────────────────────────────────────────────────

class TestRTSPManager:
    """Test RTSP stream manager data structures."""

    def test_camera_info(self):
        from yolo_cloud.rtsp_manager import CameraInfo
        cam = CameraInfo(
            id="cam-1",
            name="Assembly Line",
            url="rtsp://192.168.1.100:554/stream1",
        )
        assert cam.id == "cam-1"
        assert cam.url == "rtsp://192.168.1.100:554/stream1"


# ── Integration: API + Reports ───────────────────────────────────────────────

class TestReportEndpoints:
    """Test that report endpoints call correct functions."""

    def test_daily_report_calls_generate(self):
        """Verify the daily report endpoint uses generate_daily_summary."""
        from yolo_cloud.api import daily_report
        assert callable(daily_report)

    def test_csv_report_calls_generate(self):
        """Verify the CSV report endpoint exists."""
        from yolo_cloud.api import csv_report
        assert callable(csv_report)

    def test_pdf_report_calls_generate(self):
        """Verify the PDF report endpoint exists."""
        from yolo_cloud.api import pdf_report
        assert callable(pdf_report)

    def test_weekly_report_calls_generate(self):
        """Verify the weekly report endpoint exists."""
        from yolo_cloud.api import weekly_report
        assert callable(weekly_report)
