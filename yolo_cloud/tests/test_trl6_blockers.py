"""Tests for the three TRL-6 blockers: aspect-correct angles, the pixel-space
guard on feature extraction, and pre-alert alert clips."""

from __future__ import annotations

import math
import os

import numpy as np
import pytest

from yolo_cloud.config import settings
from yolo_cloud.ingestion import (
    CLIP_BUFFER_SECONDS,
    CloudCameraProcessor,
    CloudIngestionService,
    CloudSession,
)
from yolo_cloud.pose_engine import YOLOPoseEngine
from yolo_cloud.rtsp_manager import CameraInfo


def _lean_keypoints(true_deg: float, width: int, height: int) -> np.ndarray:
    """A physically true trunk lean of ``true_deg``, in PIXEL coordinates.

    Torso length and segment widths scale with the frame, so the same posture is
    described at any resolution.
    """
    torso = 0.35 * height
    hip_x, hip_y = width * 0.5, height * 0.70
    shoulder_x = hip_x + torso * math.sin(math.radians(true_deg))
    shoulder_y = hip_y - torso * math.cos(math.radians(true_deg))

    kps = np.zeros((17, 3), dtype=float)
    for index in range(17):
        kps[index] = [hip_x, hip_y, 0.9]
    kps[11] = [hip_x - 0.06 * width, hip_y, 0.9]
    kps[12] = [hip_x + 0.06 * width, hip_y, 0.9]
    kps[5] = [shoulder_x - 0.06 * width, shoulder_y, 0.9]
    kps[6] = [shoulder_x + 0.06 * width, shoulder_y, 0.9]
    kps[0] = [shoulder_x, shoulder_y - 0.05 * height, 0.9]
    kps[13] = [hip_x - 0.06 * width, hip_y + 0.17 * height, 0.9]
    kps[14] = [hip_x + 0.06 * width, hip_y + 0.17 * height, 0.9]
    kps[15] = [hip_x - 0.06 * width, hip_y + 0.28 * height, 0.9]
    kps[16] = [hip_x + 0.06 * width, hip_y + 0.28 * height, 0.9]
    return kps


class TestAspectCorrectAngles:
    """A true 60 deg trunk bend must read 60 deg on every aspect ratio."""

    @pytest.mark.parametrize(
        "width,height,label",
        [(1280, 720, "16:9"), (640, 480, "4:3"), (720, 720, "1:1"), (1080, 1920, "portrait")],
    )
    def test_true_60_degree_lean_reads_60(self, width, height, label):
        engine = YOLOPoseEngine()
        keypoints = _lean_keypoints(60.0, width, height)
        frame = np.full((height, width, 3), 128, dtype=np.uint8)
        pose = engine._process_tracked_pose(
            1, [0, 0, width, height], keypoints, width, height, frame, "cam"
        )
        trunk = pose.joint_angles["trunk"]
        assert trunk == pytest.approx(60.0, abs=2.0), f"{label} computed {trunk}"

    def test_legacy_normalized_maths_was_aspect_dependent(self):
        # Regression guard: without frame dimensions the same posture gave
        # different angles per aspect ratio, which is the bug being fixed.
        engine = YOLOPoseEngine()
        width, height = 1280, 720
        keypoints = _lean_keypoints(60.0, width, height)
        normalized = [[kp[0] / width, kp[1] / height, kp[2]] for kp in keypoints]

        legacy = engine._calculate_angles(normalized)["trunk"]
        fixed = engine._calculate_angles(normalized, width, height)["trunk"]

        assert legacy == pytest.approx(44.3, abs=1.0)
        assert fixed == pytest.approx(60.0, abs=2.0)

    def test_square_frame_is_unaffected(self):
        # On a square frame normalized and pixel space agree, so the fix only
        # removes aspect distortion. They are not bit-identical: the legacy path
        # uses a 0.1-unit (72 px here) vertical reference while the pixel path
        # uses 1 px, so a non-zero lean differs by ~0.001 deg. That is still four
        # orders of magnitude below the 15.7 deg aspect error, so assert a
        # tolerance that distinguishes "unaffected" from "distorted".
        engine = YOLOPoseEngine()
        width = height = 720
        keypoints = _lean_keypoints(60.0, width, height)
        normalized = [[kp[0] / width, kp[1] / height, kp[2]] for kp in keypoints]
        assert engine._calculate_angles(normalized)["trunk"] == pytest.approx(
            engine._calculate_angles(normalized, width, height)["trunk"], abs=0.01
        )

    def test_a_true_60_lean_is_still_high_risk(self):
        engine = YOLOPoseEngine()
        width, height = 1280, 720
        keypoints = _lean_keypoints(60.0, width, height)
        frame = np.full((height, width, 3), 128, dtype=np.uint8)
        levels = [
            engine._process_tracked_pose(
                1, [0, 0, width, height], keypoints, width, height, frame, "cam"
            ).risk_level
            for _ in range(15)
        ]
        assert levels.count("HIGH") == 15
        assert len(levels) == 15


class TestPixelSpaceGuard:
    def test_normalized_input_raises_a_clear_error(self):
        from backend.services.features import extract_features_from_keypoints

        with pytest.raises(ValueError, match="PIXEL"):
            extract_features_from_keypoints(np.full((17, 4), 0.5))

    def test_pixel_input_is_accepted(self):
        from backend.services.features import extract_features_from_keypoints

        keypoints = np.zeros((17, 4), dtype=float)
        keypoints[:, 3] = 0.9
        keypoints[:, 0] = 100.0
        keypoints[:, 1] = 200.0
        features, _unavailable, _approx = extract_features_from_keypoints(keypoints)
        assert features

    def test_too_few_points_is_not_treated_as_normalized(self):
        from backend.services.features import assert_pixel_space

        # A single landmark at the frame corner must not trip the guard.
        assert_pixel_space(np.array([[0.5, 0.5, 0.9]]))

    def test_zero_filled_keypoints_degrade_instead_of_raising(self):
        from backend.services.features import (
            assert_pixel_space,
            extract_features_from_keypoints,
        )

        # An all-zero array means "no landmarks detected", not a normalized
        # pose. The extractor must degrade it to unavailable features rather
        # than crash — regression guard for the pixel-space check.
        keypoints = np.zeros((10, 3))
        assert_pixel_space(keypoints)
        features, unavailable, _approx = extract_features_from_keypoints(keypoints)
        assert set(unavailable)


def _processor(tmp_path, monkeypatch) -> CloudCameraProcessor:
    monkeypatch.setattr(settings, "RECORDINGS_DIR", str(tmp_path))
    return CloudCameraProcessor(
        CameraInfo(id="cam-1", name="Cell A", url="rtsp://x/1"), YOLOPoseEngine()
    )


class TestAlertClips:
    def test_buffer_is_bounded_by_the_configured_rate(self, tmp_path, monkeypatch):
        processor = _processor(tmp_path, monkeypatch)
        expected = max(1, int(CLIP_BUFFER_SECONDS * int(settings.INFERENCE_FPS)))
        assert processor._clip_buffer.maxlen == expected

    def test_frames_are_buffered_as_jpeg(self, tmp_path, monkeypatch):
        processor = _processor(tmp_path, monkeypatch)
        for shade in range(5):
            processor._capture_clip_frame(np.full((240, 320, 3), shade, np.uint8))
        assert len(processor._clip_buffer) == 5
        # JPEG magic, so the buffer stores encoded frames rather than raw RGB.
        assert processor._clip_buffer[0][:2] == b"\xff\xd8"

    def test_oversized_frames_are_downscaled(self, tmp_path, monkeypatch):
        import cv2

        processor = _processor(tmp_path, monkeypatch)
        processor._capture_clip_frame(np.full((1080, 1920, 3), 100, np.uint8))
        stored = cv2.imdecode(
            np.frombuffer(processor._clip_buffer[0], np.uint8), cv2.IMREAD_COLOR
        )
        assert stored.shape[1] <= 640

    def test_saving_with_an_empty_buffer_returns_none(self, tmp_path, monkeypatch):
        processor = _processor(tmp_path, monkeypatch)
        assert processor._save_clip("ALT-1", 1.0) is None

    def test_save_clip_writes_a_real_video_file(self, tmp_path, monkeypatch):
        processor = _processor(tmp_path, monkeypatch)
        for shade in range(8):
            processor._capture_clip_frame(np.full((240, 320, 3), shade * 20, np.uint8))
        entry = processor._save_clip("ALT-1", 123.0)

        assert entry is not None
        assert entry["frames"] == 8
        assert entry["bytes"] > 0
        assert entry["post_roll"] is False
        assert os.path.exists(entry["path"])
        with open(entry["path"], "rb") as handle:
            header = handle.read(12)
        # mp4 container, or the AVI fallback — either way a real container.
        assert header[4:8] == b"ftyp" or header[:4] == b"RIFF"

    def test_high_alert_saves_a_clip_and_medium_does_not(self, tmp_path, monkeypatch):
        processor = _processor(tmp_path, monkeypatch)
        processor._session = CloudSession(
            session_id="CLOUD-TEST",
            camera_id="cam-1",
            camera_name="Cell A",
            start_time=0.0,
        )
        for shade in range(6):
            processor._capture_clip_frame(np.full((240, 320, 3), shade * 25, np.uint8))

        processor._check_alert("MEDIUM", 55.0, "Seated Work", 1, 1000.0)
        assert not processor.clips
        assert "clip" not in processor._session.alerts[-1]

        processor._check_alert("HIGH", 85.0, "Deep Bend", 1, 2000.0)
        assert "ALT-000002" in processor.clips
        assert processor._session.alerts[-1]["clip"]["frames"] == 6
        assert "clip" in processor._session.alerts[-1]

    def test_service_returns_the_clip_and_survives_camera_removal(self, tmp_path, monkeypatch):
        processor = _processor(tmp_path, monkeypatch)
        for shade in range(4):
            processor._capture_clip_frame(np.full((240, 320, 3), shade * 30, np.uint8))
        entry = processor._save_clip("ALT-9", 5.0)

        service = CloudIngestionService()
        service._processors.clear()
        service._processors["cam-1"] = processor
        assert service.get_clip("cam-1", "ALT-9")["path"] == entry["path"]

        # The clip stays downloadable from disk after the camera is gone.
        service._processors.clear()
        recovered = service.get_clip("cam-1", "ALT-9")
        assert recovered is not None and recovered["recovered_from_disk"] is True

    def test_unknown_clip_returns_none(self, tmp_path, monkeypatch):
        processor = _processor(tmp_path, monkeypatch)
        service = CloudIngestionService()
        service._processors.clear()
        service._processors["cam-1"] = processor
        assert service.get_clip("cam-1", "ALT-nope") is None
