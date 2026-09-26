"""Identity binding coverage for the YOLO cloud core.

``yolo_cloud/identity.py`` and ``yolo_cloud/identity_audit.py`` had no tests at
all. These cover the six behaviours a safety deployment actually depends on:

1. badge/QR bind + verify (the primary, explicit path),
2. face bind (consent-gated, verified band only, badge precedence),
3. alert attribution carrying the bound ``worker_id``,
4. unbind / consent withdrawal,
5. an unbound track staying anonymous (never guessed),
6. append-only audit rows for bind / unbind attempts.

Tests bind into a private ``TrackIdentityRegistry`` and a tmp audit file so
nothing leaks into the process-wide singleton or ``outputs/audit/``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from yolo_cloud import identity
from yolo_cloud import identity_audit as audit
from yolo_cloud.identity import TrackIdentityRegistry, get_identity_registry

CAM = "cam-identity-test"


@pytest.fixture()
def registry(tmp_path: Path, monkeypatch) -> TrackIdentityRegistry:
    """A fresh registry whose audit trail lands in a tmp JSONL file."""
    monkeypatch.setenv("IDENTITY_AUDIT_PATH", str(tmp_path / "identity_audit.jsonl"))
    # Never touch a real face/DB backend from a unit test.
    monkeypatch.setattr(identity, "_load_delete_worker_face", lambda: None)
    return TrackIdentityRegistry()


def _events() -> list[dict]:
    return audit.read(limit=500)


def _events_named(name: str) -> list[dict]:
    return [e for e in _events() if e.get("event") == name]


def _fake_recognizer(result: dict):
    return lambda _embedding: result


# ── 1. badge / QR flow ──────────────────────────────────────────────────────
class TestBadgeFlow:
    def test_badge_scan_binds_and_verifies_the_track(self, registry):
        out = registry.bind_badge(CAM, 7, "W-42", actor="sup-1")

        assert out["bound"] is True
        assert out["method"] == "badge"
        assert out["actor"] == "sup-1"
        # The verify side: the bound id is what the pipeline reads back.
        assert registry.binding_for(CAM, 7) == "W-42"
        record = registry.binding_record(CAM, 7)
        assert record["worker_id"] == "W-42"
        assert record["method"] == "badge"
        assert record["confidence"] == 1.0
        assert record["bound_at"]
        assert record["previous_worker_id"] is None

    def test_badge_scan_without_a_worker_id_refuses_and_binds_nothing(self, registry):
        out = registry.bind_badge(CAM, 7, "", actor="sup-1")

        assert out == {"bound": False, "reason": "worker_id_required"}
        assert registry.binding_for(CAM, 7) is None
        # A refused attempt writes no bind row (nothing was bound).
        assert _events_named("bind") == []

    def test_rebinding_another_worker_is_counted_as_an_id_switch(self, registry):
        registry.bind_badge(CAM, 7, "W-42")
        registry.bind_badge(CAM, 7, "W-77")

        assert registry.binding_for(CAM, 7) == "W-77"
        assert registry.switch_count(CAM) == 1
        assert registry.switch_count() == 1
        assert registry.binding_record(CAM, 7)["previous_worker_id"] == "W-42"
        # First bind is audited as `bind`, the hand-over as `rebind`.
        assert len(_events_named("bind")) == 1
        assert len(_events_named("rebind")) == 1
        assert _events_named("rebind")[0]["previous_worker_id"] == "W-42"

    def test_supervisor_override_requires_an_actor_and_is_audited(self, registry):
        no_sup = registry.override(CAM, 7, "W-42", supervisor="")
        assert no_sup == {"bound": False, "reason": "supervisor_required"}
        assert registry.binding_for(CAM, 7) is None

        ok = registry.override(CAM, 7, "W-42", supervisor="sup-1", reason="misread badge")
        assert ok["bound"] is True
        assert ok["method"] == "supervisor_override"
        audited = _events_named("override")
        assert len(audited) == 1
        assert audited[0]["actor"] == "sup-1"
        assert audited[0]["reason"] == "misread badge"


# ── 2. face flow ────────────────────────────────────────────────────────────
class TestFaceFlow:
    def test_verified_face_match_binds(self, registry, monkeypatch):
        monkeypatch.setattr(
            identity, "_load_identify_face",
            lambda: _fake_recognizer(
                {"worker_id": "W-9", "verified": True, "confidence": 0.93,
                 "band": "verified"}
            ),
        )

        out = registry.bind_face(CAM, 3, b"embedding")

        assert out["bound"] is True
        assert out["method"] == "face"
        assert out["confidence"] == 0.93
        assert registry.binding_for(CAM, 3) == "W-9"

    def test_match_below_the_verified_band_never_binds(self, registry, monkeypatch):
        monkeypatch.setattr(
            identity, "_load_identify_face",
            lambda: _fake_recognizer(
                {"worker_id": "W-9", "verified": False, "confidence": 0.51,
                 "band": "unverified"}
            ),
        )

        out = registry.bind_face(CAM, 3, b"embedding")

        # A safety product that guesses names is worse than one that says
        # "unknown" — nothing is bound, and the refusal is audited.
        assert out["bound"] is False
        assert out["reason"] == "below_match_threshold"
        assert registry.binding_for(CAM, 3) is None
        rejected = _events_named("face_rejected")
        assert len(rejected) == 1
        assert rejected[0]["reason"] == "below_match_threshold"

    def test_badge_outranks_a_face_match(self, registry, monkeypatch):
        registry.bind_badge(CAM, 3, "W-42")
        monkeypatch.setattr(
            identity, "_load_identify_face",
            lambda: _fake_recognizer(
                {"worker_id": "W-9", "verified": True, "confidence": 0.99,
                 "band": "verified"}
            ),
        )

        out = registry.bind_face(CAM, 3, b"embedding")

        assert out == {"bound": False, "reason": "badge_binding_precedence",
                       "worker_id": "W-42"}
        assert registry.binding_for(CAM, 3) == "W-42"

    def test_withdrawn_worker_cannot_be_rebound_by_face(self, registry, monkeypatch):
        monkeypatch.setattr(
            identity, "_load_identify_face",
            lambda: _fake_recognizer(
                {"worker_id": "W-9", "verified": True, "confidence": 0.99,
                 "band": "verified"}
            ),
        )
        registry.withdraw("W-9")

        out = registry.bind_face(CAM, 3, b"embedding")

        assert out["bound"] is False
        assert out["reason"] == "consent_withdrawn"
        assert registry.binding_for(CAM, 3) is None
        assert any(e.get("reason") == "consent_withdrawn"
                   for e in _events_named("face_rejected"))

    def test_missing_recognizer_is_reported_not_raised(self, registry, monkeypatch):
        monkeypatch.setattr(identity, "_load_identify_face", lambda: None)

        out = registry.bind_face(CAM, 3, b"embedding")

        assert out == {"bound": False, "reason": "face_recognizer_unavailable"}
        assert registry.binding_for(CAM, 3) is None


# ── 3. unbind + consent ─────────────────────────────────────────────────────
class TestUnbindAndConsent:
    def test_unbind_returns_the_track_to_anonymous_and_audits(self, registry):
        registry.bind_badge(CAM, 7, "W-42", actor="sup-1")

        assert registry.unbind(CAM, 7, actor="sup-1", reason="scan again") is True
        assert registry.binding_for(CAM, 7) is None
        assert registry.binding_record(CAM, 7) is None
        # A second unbind is a no-op and does not duplicate the audit trail.
        assert registry.unbind(CAM, 7) is False

        rows = _events_named("unbind")
        assert len(rows) == 1
        assert rows[0]["worker_id"] == "W-42"
        assert rows[0]["actor"] == "sup-1"
        assert rows[0]["reason"] == "scan again"

    def test_withdraw_unbinds_every_track_and_latches_the_worker(self, registry):
        registry.bind_badge(CAM, 7, "W-42")
        registry.bind_badge("cam-b", 2, "W-42")
        registry.bind_badge(CAM, 8, "W-77")

        out = registry.withdraw("W-42")

        assert out["unbound_count"] == 2
        assert registry.binding_for(CAM, 7) is None
        assert registry.binding_for("cam-b", 2) is None
        # Other workers are untouched.
        assert registry.binding_for(CAM, 8) == "W-77"
        assert registry.is_revoked("W-42") is True
        assert out["face_matching_disabled"] is True
        assert out["biometrics_wiped"] is False  # recognizer unavailable in test

        rows = _events_named("consent_withdraw")
        assert len(rows) == 1
        assert rows[0]["unbound_count"] == 2

        restored = registry.restore("W-42")
        assert restored["face_matching_disabled"] is False
        assert registry.is_revoked("W-42") is False
        assert _events_named("consent_restore")


# ── 4. anonymity: unknown tracks are never guessed ──────────────────────────
class TestUnknownTrackStaysAnonymous:
    def test_unbound_track_reads_back_none(self, registry):
        assert registry.binding_for(CAM, 11) is None
        assert registry.binding_record(CAM, 11) is None
        assert registry.bindings_for_camera(CAM) == {}

    def test_bindings_never_leak_across_cameras_or_tracks(self, registry):
        registry.bind_badge(CAM, 11, "W-42")

        assert registry.binding_for(CAM, 12) is None      # different track
        assert registry.binding_for("cam-other", 11) is None  # different camera
        assert registry.binding_for("cam-other", 12) is None

    def test_snapshot_lists_only_bound_tracks(self, registry):
        registry.bind_badge(CAM, 11, "W-42")

        snap = registry.snapshot()
        assert list(snap["bindings"]) == [CAM]
        assert list(snap["bindings"][CAM]) == [11]
        assert snap["id_switch_count"] == 0
        assert snap["revoked"] == []

    def test_singleton_is_a_process_wide_registry(self):
        # The ingestion service resolves identity through this accessor; it must
        # be the same object every time so a bind from the API is visible to the
        # frame loop.
        assert get_identity_registry() is get_identity_registry()
        assert isinstance(get_identity_registry(), TrackIdentityRegistry)


# ── 5. alert attribution ────────────────────────────────────────────────────
class TestAlertAttribution:
    @pytest.fixture()
    def processor(self, tmp_path, monkeypatch, registry):
        from yolo_cloud.config import settings
        from yolo_cloud.ingestion import CloudCameraProcessor, CloudSession
        from yolo_cloud.pose_engine import YOLOPoseEngine
        from yolo_cloud.rtsp_manager import CameraInfo
        import yolo_cloud.ingestion as ingestion_mod

        monkeypatch.setattr(settings, "RECORDINGS_DIR", str(tmp_path))
        # CloudCameraProcessor resolves the process-wide singleton in its ctor;
        # point it at this test's private registry instead.
        monkeypatch.setattr(ingestion_mod, "get_identity_registry", lambda: registry)
        processor = CloudCameraProcessor(
            CameraInfo(id=CAM, name="Cell A", url="rtsp://x/1"), YOLOPoseEngine()
        )
        processor._session = CloudSession(
            session_id="CLOUD-IDENTITY-TEST",
            camera_id=CAM,
            camera_name="Cell A",
            start_time=0.0,
        )
        return processor

    def test_alert_carries_the_bound_worker_id(self, processor):
        processor._identity.bind_badge(CAM, 7, "W-42", actor="sup-1")

        assert processor._binding_for(7) == "W-42"
        # Same seam the frame loop uses: worker_id is resolved at alert time.
        processor._check_alert(
            "MEDIUM", 55.0, "Seated Work", 7, 1000.0,
            worker_id=processor._binding_for(7),
        )

        alert = processor._session.alerts[-1]
        assert alert["worker_id"] == "W-42"
        assert alert["track_id"] == 7
        assert alert["severity"] == "MEDIUM"

    def test_alert_for_an_unbound_track_stays_anonymous(self, processor):
        processor._identity.bind_badge(CAM, 7, "W-42")

        processor._check_alert(
            "MEDIUM", 55.0, "Seated Work", 8, 2000.0,
            worker_id=processor._binding_for(8),
        )

        alert = processor._session.alerts[-1]
        assert alert["track_id"] == 8
        assert alert["worker_id"] is None

    def test_person_snapshots_carry_the_bound_worker_id(self, processor):
        from yolo_cloud.pose_engine import ProcessedCloudFrame, TrackedPose

        processor._identity.bind_badge(CAM, 7, "W-42")
        pose = TrackedPose(
            track_id=7, bbox=[0.1, 0.1, 0.5, 0.9],
            keypoints=[[10, 10, 0.9]] * 17, angles={},
            risk_level="MEDIUM", risk_score=55.0, confidence=0.9,
            task="Seated Work",
        )
        processor.frame_width, processor.frame_height = 640, 480

        persons = processor.build_persons(ProcessedCloudFrame(
            frame_width=640, frame_height=480, tracked_poses=[pose],
            person_count=1, inference_ms=12.0, timestamp=1000.0,
        ))

        assert persons[0]["worker_id"] == "W-42"


# ── 6. audit log ────────────────────────────────────────────────────────────
class TestAuditLog:
    def test_bind_and_unbind_each_write_a_jsonl_row(self, registry, tmp_path):
        registry.bind_badge(CAM, 7, "W-42", actor="sup-1")
        registry.unbind(CAM, 7, actor="sup-1", reason="done")

        path = Path(tmp_path / "identity_audit.jsonl")
        assert path.exists()
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]

        assert [r["event"] for r in rows] == ["bind", "unbind"]
        for row in rows:
            assert row["ts"]
            assert row["camera_id"] == CAM
            assert row["track_id"] == 7
            assert row["worker_id"] == "W-42"
            assert row["method"] == "badge"

    def test_read_filters_by_event_and_worker(self, registry):
        registry.bind_badge(CAM, 7, "W-42")
        registry.bind_badge(CAM, 8, "W-77")

        assert len(_events_named("bind")) == 2
        only_42 = audit.read(limit=50, event="bind", worker_id="W-42")
        assert [e["worker_id"] for e in only_42] == ["W-42"]
        assert audit.read(limit=50, camera_id="cam-nope") == []

    def test_a_failed_audit_write_never_breaks_the_bind(self, registry, tmp_path, monkeypatch):
        # Point the audit path at a directory: opening it for append fails.
        monkeypatch.setenv("IDENTITY_AUDIT_PATH", str(tmp_path))

        record = registry.bind_badge(CAM, 7, "W-42")

        assert record["bound"] is True
        assert registry.binding_for(CAM, 7) == "W-42"
        # The failure is swallowed (returns None), never raised into the caller.
        assert audit.record("bind") is None
