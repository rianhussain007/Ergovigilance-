"""Tests for the load / QA instrumentation.

Covers the percentile helper, frame-drop accounting, and the tracking audit, so
the numbers a soak reports are produced by tested code rather than by the
harness script alone.
"""

from __future__ import annotations

import numpy as np
import pytest

from yolo_cloud.ingestion import (
    LATENCY_BUDGET_MS,
    CloudCameraProcessor,
    normalize_per_hour,
    percentiles,
)
from yolo_cloud.pose_engine import YOLOPoseEngine, _SimpleTracker
from yolo_cloud.rtsp_manager import CameraInfo


class TestPercentiles:
    def test_empty_buffer_has_no_percentiles(self):
        assert percentiles([]) == {}

    def test_nearest_rank_is_an_observed_value(self):
        # 1..100: a nearest-rank p95 is the 95th sample itself, not an
        # interpolation between samples — the point is whether a real frame
        # breached the budget.
        out = percentiles(range(1, 101))
        assert out["p50"] == 50.0
        assert out["p95"] == 95.0
        assert out["p99"] == 99.0
        assert out["max"] == 100.0
        assert out["n"] == 100

    def test_single_sample(self):
        out = percentiles([420.0])
        assert out["p50"] == 420.0 and out["p95"] == 420.0 and out["max"] == 420.0

    def test_small_buffer_still_returns_the_maximum(self):
        out = percentiles([10.0, 20.0])
        assert out["p95"] == 20.0

    def test_normalize_per_hour(self):
        assert normalize_per_hour(10, 60) == 600.0
        assert normalize_per_hour(5, 3600) == 5.0
        assert normalize_per_hour(10, 0) == 0.0  # never divides by zero


def _processor() -> CloudCameraProcessor:
    return CloudCameraProcessor(
        CameraInfo(id="cam-1", name="Cell A", url="rtsp://x/1"),
        YOLOPoseEngine(),
    )


class TestFrameDropAccounting:
    def test_drops_are_decoded_minus_processed(self):
        processor = _processor()
        processor.camera.frame_count = 100  # decoder produced 100 frames
        processor._frame_counter = 60       # we scored 60 of them
        snapshot = processor.metrics_snapshot()
        assert snapshot["decoded_frames"] == 100
        assert snapshot["processed_frames"] == 60
        assert snapshot["dropped_frames"] == 40
        assert snapshot["repeat_frames"] == 0
        assert snapshot["drop_rate"] == 0.4

    def test_consumer_outpacing_the_decoder_reports_repeats_not_negative_drops(self):
        # get_frame returns the LATEST frame, so a fast consumer re-scores one
        # image; that must surface as repeats, never as a negative drop count.
        processor = _processor()
        processor.camera.frame_count = 10
        processor._frame_counter = 14
        snapshot = processor.metrics_snapshot()
        assert snapshot["dropped_frames"] == 0
        assert snapshot["repeat_frames"] == 4

    def test_zero_decoded_frames_is_not_a_zero_drop_rate(self):
        processor = _processor()
        snapshot = processor.metrics_snapshot()
        assert snapshot["decoded_frames"] == 0
        assert snapshot["drop_rate"] == 0.0
        assert snapshot["dropped_frames"] == 0


class TestLatencyBudget:
    def test_counts_frames_over_budget(self):
        processor = _processor()
        processor.latency_ms.extend([100.0, 200.0, 900.0, 1200.0])
        snapshot = processor.metrics_snapshot()
        assert snapshot["latency_budget_ms"] == LATENCY_BUDGET_MS
        assert snapshot["latency_over_budget_frames"] == 2
        assert snapshot["latency_ms"]["max"] == 1200.0
        assert snapshot["latency_ms"]["n"] == 4

    def test_buffers_are_bounded(self):
        # A four-hour soak must not grow memory without limit.
        processor = _processor()
        assert processor.latency_ms.maxlen is not None
        processor.latency_ms.extend(range(processor.latency_ms.maxlen + 500))
        assert len(processor.latency_ms) == processor.latency_ms.maxlen


class TestTrackerAudit:
    def _feed(self, tracker, boxes, confs=None, kps=None):
        boxes = np.asarray(boxes, dtype=float).reshape(-1, 4)
        confs = np.ones(len(boxes))
        kps = np.zeros((len(boxes), 17, 3))
        return tracker.update(boxes, confs, kps)

    def test_new_and_expired_tracks_are_counted(self):
        tracker = _SimpleTracker(iou_thresh=0.3, max_lost=2)
        self._feed(tracker, [[0, 0, 100, 100]])
        for _ in range(3):  # let the lost-track buffer elapse
            self._feed(tracker, [])
        snapshot = tracker.audit_snapshot()
        assert snapshot["new_tracks"] == 1
        assert snapshot["expired_tracks"] == 1
        assert snapshot["live_tracks"] == 0

    def test_reacquisition_is_counted(self):
        # The worker is still there but comes back with a fresh id: the tracker
        # lost and re-acquired them, which is the flip this metric exists for.
        tracker = _SimpleTracker(iou_thresh=0.3, max_lost=2)
        self._feed(tracker, [[0, 0, 100, 100]])
        for _ in range(3):
            self._feed(tracker, [])
        self._feed(tracker, [[0, 0, 100, 100]])
        snapshot = tracker.audit_snapshot()
        assert snapshot["new_tracks"] == 2
        assert snapshot["reacquisitions"] == 1

    def test_a_far_away_new_track_is_not_a_reacquisition(self):
        tracker = _SimpleTracker(iou_thresh=0.3, max_lost=2)
        self._feed(tracker, [[0, 0, 100, 100]])
        for _ in range(3):
            self._feed(tracker, [])
        self._feed(tracker, [[900, 900, 1000, 1000]])  # different place entirely
        assert tracker.audit_snapshot()["reacquisitions"] == 0

    def test_ids_are_never_reused(self):
        tracker = _SimpleTracker(iou_thresh=0.3, max_lost=1)
        first = self._feed(tracker, [[0, 0, 100, 100]])[0]["track_id"]
        for _ in range(2):
            self._feed(tracker, [])
        second = self._feed(tracker, [[0, 0, 100, 100]])[0]["track_id"]
        assert second != first


class TestEngineTrackingAudit:
    def test_aggregates_per_camera_and_normalises_per_hour(self):
        engine = YOLOPoseEngine()
        tracker = _SimpleTracker(iou_thresh=0.3, max_lost=2)
        tracker.new_tracks = 3
        tracker.expired_tracks = 1
        tracker.reacquisitions = 2
        engine._simple_trackers["cam-1"] = tracker

        audit = engine.tracking_audit(elapsed_seconds=60.0)
        assert audit["totals"]["new_tracks"] == 3
        assert audit["totals"]["reacquisitions"] == 2
        assert audit["per_hour"]["new_tracks"] == 180.0  # 3 in one minute
        assert "cam-1" in audit["per_camera"]

    def test_declares_the_tracker_actually_in_use(self):
        # The audit must not imply ByteTrack counters when ByteTrack is unusable.
        engine = YOLOPoseEngine()
        audit = engine.tracking_audit(elapsed_seconds=0.0)
        assert audit["active_tracker"].startswith("_SimpleTracker")
        assert audit["per_hour"]["new_tracks"] == 0.0  # no divide-by-zero


class TestFrameSkipKnob:
    """YOLO_SCORE_EVERY: score every Nth pulled frame, default every frame."""

    def test_default_scores_every_pulled_frame(self):
        processor = _processor()
        assert [processor._should_score() for _ in range(4)] == [True] * 4
        assert processor.metrics_snapshot()["score_every"] == 1
        assert processor.metrics_snapshot()["frames_skipped"] == 0

    def test_score_every_two_scores_half_the_frames(self, monkeypatch):
        from yolo_cloud.config import settings

        monkeypatch.setattr(settings, "YOLO_SCORE_EVERY", 2)
        processor = _processor()
        # The FIRST pull is scored — a session never starts with a skip — then
        # every 2nd frame after it.
        assert [processor._should_score() for _ in range(4)] == [True, False, True, False]
        assert processor.metrics_snapshot()["score_every"] == 2

    def test_values_below_one_clamp_to_scoring_everything(self, monkeypatch):
        from yolo_cloud.config import settings

        monkeypatch.setattr(settings, "YOLO_SCORE_EVERY", 0)
        processor = _processor()
        assert [processor._should_score() for _ in range(3)] == [True, True, True]
        assert processor.metrics_snapshot()["score_every"] == 1

    def test_skipped_frames_never_read_as_decoder_drops(self):
        # 100 decoded, 60 scored, 30 intentionally skipped -> only 10 were
        # actually lost to the single-slot buffer.
        processor = _processor()
        processor.camera.frame_count = 100
        processor._frame_counter = 60
        processor._frames_skipped = 30
        snapshot = processor.metrics_snapshot()
        assert snapshot["dropped_frames"] == 10
        assert snapshot["frames_skipped"] == 30


class TestProcessingMetricsService:
    def test_service_reports_one_entry_per_camera(self):
        from yolo_cloud.ingestion import CloudIngestionService

        service = CloudIngestionService()
        service._processors.clear()
        service._processors["cam-1"] = _processor()
        metrics = service.get_processing_metrics()
        assert [m["camera_id"] for m in metrics] == ["cam-1"]
        assert "drop_rate" in metrics[0] and "latency_ms" in metrics[0]
