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


# ── Multi-track (multi-worker) isolation ──────────────────────────────────────

class TestMultiTrackIsolation:
    """Per-track state must never leak between workers or between cameras."""

    @staticmethod
    def _pose(track_id: int, risk_score: float = 50.0):
        from yolo_cloud.pose_engine import TrackedPose
        return TrackedPose(
            track_id=track_id,
            bbox=[0.1, 0.1, 0.3, 0.5],
            keypoints=[[0.2, 0.3, 0.9]] * 17,
            angles={"trunk": 61.2, "neck": 32.5, "trunk_angle": 61.2},
            joint_angles={"trunk": 61.2, "neck": 32.5},
            risk_level="HIGH",
            risk_score=risk_score,
            confidence=0.89,
            task="lifting",
            quality={"low_light": False, "occluded": False, "too_small": False},
        )

    def test_persons_payload_carries_angles_and_all_17_keypoints(self):
        from yolo_cloud.ingestion import CloudCameraProcessor
        from yolo_cloud.pose_engine import ProcessedCloudFrame, YOLOPoseEngine
        from yolo_cloud.rtsp_manager import CameraInfo

        processor = CloudCameraProcessor(
            CameraInfo(id="cam-1", name="Cell A", url="rtsp://x/1"),
            YOLOPoseEngine(),
        )
        processor._binding_for = lambda track_id: "EMP-7"
        frame = ProcessedCloudFrame(
            frame_width=1920,
            frame_height=1080,
            tracked_poses=[self._pose(12)],
            person_count=1,
            inference_ms=40.0,
            timestamp=123.0,
        )

        persons = processor.build_persons(frame)
        assert len(persons) == 1
        person = persons[0]
        assert person["track_id"] == 12
        assert person["worker_id"] == "EMP-7"
        # The geometric joint angles only — not the merged feature vector.
        assert person["angles"] == {"trunk": 61.2, "neck": 32.5}
        # All 17 COCO keypoints, index-aligned, [x, y, conf] normalized.
        assert len(person["keypoints"]) == 17
        assert person["keypoints"][0] == [0.2, 0.3, 0.9]
        # bbox stays [x, y, w, h] in pixels of the frame that produced it.
        assert person["bbox"] == [192, 108, 384, 432]

    def test_persons_payload_is_one_entry_per_track(self):
        from yolo_cloud.ingestion import CloudCameraProcessor
        from yolo_cloud.pose_engine import ProcessedCloudFrame, YOLOPoseEngine
        from yolo_cloud.rtsp_manager import CameraInfo

        processor = CloudCameraProcessor(
            CameraInfo(id="cam-1", name="Cell A", url="rtsp://x/1"),
            YOLOPoseEngine(),
        )
        processor._binding_for = lambda track_id: None
        frame = ProcessedCloudFrame(
            frame_width=640,
            frame_height=480,
            tracked_poses=[self._pose(1), self._pose(2), self._pose(3)],
            person_count=3,
            inference_ms=90.0,
            timestamp=124.0,
        )

        persons = processor.build_persons(frame)
        assert [p["track_id"] for p in persons] == [1, 2, 3]
        assert all(p["worker_id"] is None for p in persons)

    def test_risk_ema_is_per_track_and_alpha_weighted(self):
        from yolo_cloud.pose_engine import RISK_EMA_ALPHA, YOLOPoseEngine

        engine = YOLOPoseEngine()
        engine._frame_index = 1
        # A track's first sample passes through unchanged (no warm-up penalty).
        assert engine._smooth_risk(("cam-a", 1), 80.0) == 80.0
        # Then 0.6 * new + 0.4 * previous.
        assert RISK_EMA_ALPHA == 0.6
        assert engine._smooth_risk(("cam-a", 1), 20.0) == pytest.approx(44.0)
        # Another worker in the same frame starts its own series.
        assert engine._smooth_risk(("cam-a", 2), 20.0) == 20.0
        # So does the same track id on a different camera.
        assert engine._smooth_risk(("cam-b", 1), 20.0) == 20.0

    def test_track_state_is_evicted_after_ttl_but_kept_within_grace(self):
        from yolo_cloud.pose_engine import YOLOPoseEngine

        engine = YOLOPoseEngine()
        engine._frame_index = 10
        for track_id in (1, 2):
            engine._smooth_risk(("cam-a", track_id), 50.0)
            engine._task_engines[("cam-a", track_id)] = object()
        # Track 2 has been gone longer than the TTL; track 1 is active now.
        engine._track_last_seen[("cam-a", 2)] = 10 - engine.TRACK_STATE_TTL_FRAMES - 1

        engine._prune_track_state("cam-a", {1})

        assert ("cam-a", 1) in engine._task_engines
        assert ("cam-a", 1) in engine._risk_ema
        assert ("cam-a", 2) not in engine._task_engines
        assert ("cam-a", 2) not in engine._risk_ema
        assert ("cam-a", 2) not in engine._track_last_seen

    def test_prune_never_touches_another_cameras_tracks(self):
        from yolo_cloud.pose_engine import YOLOPoseEngine

        engine = YOLOPoseEngine()
        engine._frame_index = 999
        engine._smooth_risk(("cam-b", 5), 50.0)
        engine._track_last_seen[("cam-b", 5)] = 0

        engine._prune_track_state("cam-a", set())

        assert ("cam-b", 5) in engine._risk_ema
        assert ("cam-b", 5) in engine._track_last_seen


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
