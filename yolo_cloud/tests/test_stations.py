"""Tests for station ROI polygons and per-track station mapping.

Covers the ray-casting primitive, polygon validation, the JSON store, and the
resolution rules (three side-by-side stations; per-camera isolation; smallest
polygon wins on overlap).
"""

from __future__ import annotations

import json

import pytest

from yolo_cloud.stations import (
    STORE_VERSION,
    StationStore,
    normalize_polygon,
    point_in_polygon,
    polygon_area,
)

# Three workstations across the frame, with gaps between them so "no station"
# is a case that can actually be tested.
STATION_A = [{"x": 0.05, "y": 0.1}, {"x": 0.25, "y": 0.1}, {"x": 0.25, "y": 0.9}, {"x": 0.05, "y": 0.9}]
STATION_B = [{"x": 0.40, "y": 0.1}, {"x": 0.60, "y": 0.1}, {"x": 0.60, "y": 0.9}, {"x": 0.40, "y": 0.9}]
STATION_C = [{"x": 0.75, "y": 0.1}, {"x": 0.95, "y": 0.1}, {"x": 0.95, "y": 0.9}, {"x": 0.75, "y": 0.9}]


@pytest.fixture()
def store(tmp_path):
    return StationStore(path=str(tmp_path / "stations.json"))


def _seed_three(store, camera_id="cam-1"):
    store.set_station(camera_id, "ST-A", "Assembly", STATION_A)
    store.set_station(camera_id, "ST-B", "Packing", STATION_B)
    store.set_station(camera_id, "ST-C", "Inspection", STATION_C)


class TestPointInPolygon:
    SQUARE = [{"x": 0.2, "y": 0.2}, {"x": 0.8, "y": 0.2}, {"x": 0.8, "y": 0.8}, {"x": 0.2, "y": 0.8}]

    def test_inside(self):
        assert point_in_polygon(0.5, 0.5, self.SQUARE)

    def test_outside_on_every_side(self):
        assert not point_in_polygon(0.1, 0.5, self.SQUARE)
        assert not point_in_polygon(0.9, 0.5, self.SQUARE)
        assert not point_in_polygon(0.5, 0.1, self.SQUARE)
        assert not point_in_polygon(0.5, 0.9, self.SQUARE)

    def test_vertex_order_does_not_matter(self):
        # A supervisor may draw clockwise or counter-clockwise.
        reversed_square = list(reversed(self.SQUARE))
        assert point_in_polygon(0.5, 0.5, reversed_square)
        assert not point_in_polygon(0.1, 0.5, reversed_square)

    def test_triangle(self):
        triangle = [{"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 0.0}, {"x": 0.5, "y": 1.0}]
        assert point_in_polygon(0.5, 0.4, triangle)
        assert not point_in_polygon(0.05, 0.9, triangle)

    def test_concave_notch_is_outside_the_polygon(self):
        # An L-shape: (0.7, 0.7) is inside the convex hull but in the notch.
        l_shape = [
            {"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 0.0}, {"x": 1.0, "y": 0.4},
            {"x": 0.4, "y": 0.4}, {"x": 0.4, "y": 1.0}, {"x": 0.0, "y": 1.0},
        ]
        assert point_in_polygon(0.2, 0.2, l_shape)
        assert not point_in_polygon(0.7, 0.7, l_shape)

    def test_degenerate_polygons_are_never_inside(self):
        assert not point_in_polygon(0.5, 0.5, [])
        assert not point_in_polygon(0.5, 0.5, [{"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 1.0}])

    def test_accepts_plain_xy_pairs(self):
        assert point_in_polygon(0.5, 0.5, [(0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8)])


class TestNormalizePolygon:
    def test_rejects_too_few_points(self):
        with pytest.raises(ValueError, match="at least 3"):
            normalize_polygon([{"x": 0.1, "y": 0.1}, {"x": 0.2, "y": 0.2}])

    def test_rejects_pixel_coordinates_with_an_actionable_message(self):
        with pytest.raises(ValueError, match="normalized"):
            normalize_polygon([{"x": 100, "y": 50}, {"x": 300, "y": 50}, {"x": 300, "y": 400}])

    def test_rejects_collinear_points(self):
        with pytest.raises(ValueError, match="no area"):
            normalize_polygon([{"x": 0.1, "y": 0.1}, {"x": 0.2, "y": 0.2}, {"x": 0.3, "y": 0.3}])

    def test_rejects_a_vertex_missing_a_coordinate(self):
        # A missing "y" must fail loudly rather than default to the frame edge.
        with pytest.raises(ValueError, match="must be"):
            normalize_polygon([{"x": 0.1}, {"x": 0.2, "y": 0.2}, {"x": 0.3, "y": 0.3}])

    def test_accepts_and_rounds_valid_points(self):
        out = normalize_polygon(
            [{"x": 0.1234567, "y": 0.2}, {"x": 0.5, "y": 0.2}, {"x": 0.5, "y": 0.9}]
        )
        assert out == [{"x": 0.123457, "y": 0.2}, {"x": 0.5, "y": 0.2}, {"x": 0.5, "y": 0.9}]

    def test_polygon_area_is_order_independent(self):
        assert polygon_area(STATION_A) == pytest.approx(polygon_area(list(reversed(STATION_A))))
        assert polygon_area(STATION_A) == pytest.approx(0.2 * 0.8)


class TestStationStore:
    def test_set_list_and_get(self, store):
        _seed_three(store)
        stations = store.list_stations("cam-1")
        assert [s["station_id"] for s in stations] == ["ST-A", "ST-B", "ST-C"]
        assert stations[0]["station_name"] == "Assembly"
        assert stations[0]["camera_id"] == "cam-1"
        assert stations[0]["created_at"]
        assert store.get_station("cam-1", "ST-B")["station_name"] == "Packing"
        assert store.get_station("cam-1", "nope") is None

    def test_replace_updates_in_place_and_keeps_created_at(self, store):
        created = store.set_station("cam-1", "ST-A", "Assembly", STATION_A)
        moved = store.set_station("cam-1", "ST-A", "Assembly moved", STATION_B)
        assert moved["station_name"] == "Assembly moved"
        assert moved["created_at"] == created["created_at"]
        assert moved["polygon"] == normalize_polygon(STATION_B)
        assert len(store.list_stations("cam-1")) == 1

    def test_persists_across_instances(self, store):
        _seed_three(store)
        # A fresh store reads the same file — setup survives a process restart.
        reopened = StationStore(path=store.path)
        assert [s["station_id"] for s in reopened.list_stations("cam-1")] == ["ST-A", "ST-B", "ST-C"]

    def test_file_records_the_schema_version(self, store):
        _seed_three(store)
        with open(store.path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
        assert payload["version"] == STORE_VERSION
        assert len(payload["stations"]) == 3

    def test_delete(self, store):
        _seed_three(store)
        assert store.delete_station("cam-1", "ST-B") is True
        assert [s["station_id"] for s in store.list_stations("cam-1")] == ["ST-A", "ST-C"]
        assert store.delete_station("cam-1", "ST-B") is False

    def test_cameras_are_isolated(self, store):
        store.set_station("cam-1", "ST-A", "Assembly", STATION_A)
        store.set_station("cam-2", "ST-A", "Assembly on camera 2", STATION_B)
        assert [s["station_name"] for s in store.list_stations("cam-1")] == ["Assembly"]
        assert [s["station_name"] for s in store.list_stations("cam-2")] == ["Assembly on camera 2"]
        # Same station_id on another camera is a different record.
        assert store.delete_station("cam-2", "ST-A") is True
        assert store.get_station("cam-1", "ST-A") is not None

    def test_requires_ids_and_a_usable_polygon(self, store):
        with pytest.raises(ValueError, match="camera_id"):
            store.set_station("", "ST-A", "x", STATION_A)
        with pytest.raises(ValueError, match="station_id"):
            store.set_station("cam-1", "", "x", STATION_A)
        with pytest.raises(ValueError, match="at least 3"):
            store.set_station("cam-1", "ST-A", "x", STATION_A[:2])


class TestStationResolution:
    def test_centroid_resolves_to_each_of_three_stations(self, store):
        _seed_three(store)
        assert store.station_for_point("cam-1", 0.15, 0.5)["station_id"] == "ST-A"
        assert store.station_for_point("cam-1", 0.50, 0.5)["station_id"] == "ST-B"
        assert store.station_for_point("cam-1", 0.85, 0.5)["station_id"] == "ST-C"

    def test_gaps_between_stations_report_no_station(self, store):
        _seed_three(store)
        assert store.station_for_point("cam-1", 0.32, 0.5) is None
        assert store.station_for_point("cam-1", 0.5, 0.05) is None  # above all stations

    def test_worker_moving_across_the_frame_changes_station(self, store):
        """The validation case: one worker walking left -> right -> left."""
        _seed_three(store)
        path = [0.15, 0.20, 0.35, 0.50, 0.70, 0.85, 0.50, 0.15]
        seen = [store.station_for_point("cam-1", x, 0.5) for x in path]
        resolved = [s["station_id"] if s else None for s in seen]
        assert resolved == ["ST-A", "ST-A", None, "ST-B", None, "ST-C", "ST-B", "ST-A"]

    def test_overlap_resolves_to_the_smallest_polygon(self, store):
        big = [{"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 0.0}, {"x": 1.0, "y": 1.0}, {"x": 0.0, "y": 1.0}]
        store.set_station("cam-1", "ST-BAY", "Whole bay", big)
        store.set_station("cam-1", "ST-01", "Station 1", STATION_A)
        assert store.station_for_point("cam-1", 0.15, 0.5)["station_id"] == "ST-01"
        # Outside the specific station but inside the bay.
        assert store.station_for_point("cam-1", 0.5, 0.5)["station_id"] == "ST-BAY"

    def test_equally_sized_overlaps_resolve_deterministically(self, store):
        store.set_station("cam-1", "ST-B", "B", STATION_B)
        store.set_station("cam-1", "ST-A", "A", STATION_B)  # identical polygon
        first = store.station_for_point("cam-1", 0.5, 0.5)["station_id"]
        assert first == "ST-A"  # station_id is the tie-break
        assert store.station_for_point("cam-1", 0.5, 0.5)["station_id"] == first

    def test_a_malformed_polygon_is_skipped_not_fatal(self, store):
        _seed_three(store)
        with open(store.path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
        payload["stations"].append(
            {"station_id": "ST-BAD", "camera_id": "cam-1", "station_name": "bad",
             "polygon": [{"x": 0.1}, {"x": 0.2, "y": 0.2}], "created_at": "x"}
        )
        with open(store.path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        broken = StationStore(path=store.path)
        assert broken.station_for_point("cam-1", 0.15, 0.5)["station_id"] == "ST-A"

    def test_unreadable_file_is_treated_as_empty(self, store):
        _seed_three(store)
        with open(store.path, "w", encoding="utf-8") as fh:
            fh.write("{not json")
        assert StationStore(path=store.path).list_stations("cam-1") == []


class TestEngineStationMapping:
    def test_engine_resolves_station_per_camera(self, store, monkeypatch):
        from yolo_cloud import pose_engine

        _seed_three(store)
        monkeypatch.setattr(pose_engine, "get_station_store", lambda: store)
        engine = pose_engine.YOLOPoseEngine()

        assert engine._station_for("cam-1", 0.15, 0.5)["station_id"] == "ST-A"
        assert engine._station_for("cam-1", 0.85, 0.5)["station_id"] == "ST-C"
        # Another camera has no stations of its own.
        assert engine._station_for("cam-2", 0.15, 0.5) is None
        # No camera key (legacy single-stream) means no station mapping.
        assert engine._station_for("", 0.15, 0.5) is None

    def test_station_lookup_never_raises(self, monkeypatch):
        from yolo_cloud import pose_engine

        def _boom():
            raise RuntimeError("store exploded")

        monkeypatch.setattr(pose_engine, "get_station_store", _boom)
        # A broken store must degrade to "unmapped", never break a frame.
        assert pose_engine.YOLOPoseEngine()._station_for("cam-1", 0.5, 0.5) is None


class TestPersonsPayloadStation:
    @staticmethod
    def _pose(track_id: int, station_id=None, station_name=None):
        from yolo_cloud.pose_engine import TrackedPose
        return TrackedPose(
            track_id=track_id,
            bbox=[0.1, 0.1, 0.3, 0.5],
            keypoints=[[0.2, 0.3, 0.9]] * 17,
            angles={"trunk": 30.0},
            joint_angles={"trunk": 30.0},
            station_id=station_id,
            station_name=station_name,
            risk_level="LOW",
            risk_score=20.0,
            confidence=0.9,
            task="standing",
        )

    def _persons(self, poses):
        from yolo_cloud.ingestion import CloudCameraProcessor
        from yolo_cloud.pose_engine import ProcessedCloudFrame, YOLOPoseEngine
        from yolo_cloud.rtsp_manager import CameraInfo

        processor = CloudCameraProcessor(
            CameraInfo(id="cam-1", name="Cell A", url="rtsp://x/1"),
            YOLOPoseEngine(),
        )
        processor._binding_for = lambda track_id: None
        return processor.build_persons(
            ProcessedCloudFrame(
                frame_width=1920,
                frame_height=1080,
                tracked_poses=poses,
                person_count=len(poses),
                inference_ms=40.0,
                timestamp=123.0,
            )
        )

    def test_persons_payload_carries_the_station(self):
        persons = self._persons([self._pose(1, "ST-A", "Assembly")])
        assert persons[0]["station_id"] == "ST-A"
        assert persons[0]["station_name"] == "Assembly"

    def test_unmapped_track_reports_null_station(self):
        persons = self._persons([self._pose(2)])
        assert persons[0]["station_id"] is None
        assert persons[0]["station_name"] is None
