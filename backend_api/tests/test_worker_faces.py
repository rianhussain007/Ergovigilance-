"""Tests for worker face enrollment (SFace embeddings) and person detection.

Covers the pure matching logic with synthetic embeddings (fast, no model
dependency) plus one end-to-end round-trip through the real YuNet + SFace
models when they're present on disk.
"""

import os
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import init_local_database  # noqa: E402
from app.services import worker_faces  # noqa: E402

init_local_database()


def _vec(seed: int) -> np.ndarray:
    """Deterministic unit vector for synthetic embedding tests."""
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(128).astype(np.float32)
    return v / np.linalg.norm(v)


def _ensure_worker(wid: str) -> None:
    """Create a real workers row for an enrollment fixture.

    Face matching joins against the workers table (identity mode + consent
    gate), so a test enrollment must belong to an actual worker row.
    """
    from app.core.database import get_connection

    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO workers (worker_id, employee_id, name, department, shift, identity_mode, consent_status) "
            "VALUES (?, ?, 'Test Worker', 'Assembly', 'Day', 'face', 'pending')",
            (wid, wid.upper()),
        )
        conn.commit()


def _drop_worker(wid: str) -> None:
    from app.core.database import delete_worker

    worker_faces.delete_worker_face(wid)
    delete_worker(wid)


class TestEmbeddingMatching:
    def test_self_match_is_high(self):
        v = _vec(1)
        assert float(np.dot(v, v)) > 0.999

    def test_different_vectors_are_far_apart(self):
        a, b = _vec(1), _vec(2)
        assert float(np.dot(a, b)) < 0.35


class TestEnrollAndIdentify:
    def test_enroll_then_identify_round_trip(self, monkeypatch):
        worker_id = "worker-999-test"
        _ensure_worker(worker_id)
        emb = _vec(42)
        # Stub the real model call so the test runs without the ONNX models.
        monkeypatch.setattr(worker_faces, "embedding_from_image", lambda _b: emb)

        status = worker_faces.enroll_worker(worker_id, b"fake-image-bytes")
        assert status["enrolled"] is True
        assert status["sample_count"] == 1
        face_status = worker_faces.get_face_status(worker_id)
        assert face_status["enrolled"] is True
        assert face_status["sample_count"] == 1

        result = worker_faces.identify_face(emb)
        assert result["matched"] is True
        assert result["verified"] is True
        assert result["band"] == "verified"
        assert result["worker_id"] == worker_id

        _drop_worker(worker_id)
        assert worker_faces.get_face_status(worker_id)["enrolled"] is False

    def test_unmatched_face_reports_unknown(self, monkeypatch):
        worker_id = "worker-888-test"
        _ensure_worker(worker_id)
        # Enroll e1 = [1, 0, ...]; query with an ORTHOGONAL vector so the
        # similarity is exactly 0.0 — far below the unknown floor.
        enrolled = np.zeros(128, dtype=np.float32)
        enrolled[0] = 1.0
        orthogonal = np.zeros(128, dtype=np.float32)
        orthogonal[1] = 1.0
        monkeypatch.setattr(worker_faces, "embedding_from_image", lambda _b: enrolled)
        worker_faces.enroll_worker(worker_id, b"fake")

        result = worker_faces.identify_face(orthogonal)
        assert result["matched"] is False
        assert result["band"] == "unknown"
        assert result["worker_id"] is None

        _drop_worker(worker_id)

    def test_no_face_raises_value_error(self, monkeypatch):
        worker_id = "worker-777-test"
        monkeypatch.setattr(worker_faces, "embedding_from_image", lambda _b: None)
        with pytest.raises(ValueError):
            worker_faces.enroll_worker(worker_id, b"no-face")

    def test_multi_sample_matching_rescues_angles(self, monkeypatch):
        """Best-over-samples scoring: either enrolled angle identifies the worker."""
        worker_id = "worker-666-test"
        _ensure_worker(worker_id)
        a, b = _vec(11), _vec(12)  # two distinct 'angles' of the same person
        monkeypatch.setattr(worker_faces, "embedding_from_image", lambda _b: a)
        worker_faces.enroll_worker(worker_id, b"front")
        monkeypatch.setattr(worker_faces, "embedding_from_image", lambda _b: b)
        worker_faces.enroll_worker(worker_id, b"side")

        assert worker_faces.get_face_status(worker_id)["sample_count"] == 2
        for probe in (a, b):
            result = worker_faces.identify_face(probe)
            assert result["worker_id"] == worker_id
            assert result["verified"] is True

        _drop_worker(worker_id)

    def test_sample_cap_prunes_oldest(self, monkeypatch):
        worker_id = "worker-556-test"
        _ensure_worker(worker_id)
        for seed in range(worker_faces.FACE_MAX_SAMPLES + 2):
            monkeypatch.setattr(
                worker_faces, "embedding_from_image", lambda _b, s=seed: _vec(s)
            )
            worker_faces.enroll_worker(worker_id, f"shot-{seed}".encode())

        status = worker_faces.get_face_status(worker_id)
        assert status["sample_count"] == worker_faces.FACE_MAX_SAMPLES
        # The two OLDEST samples were pruned; their probes must not match.
        pruned_probe = worker_faces.identify_face(_vec(0))
        assert pruned_probe["worker_id"] is None
        # The newest sample still matches.
        kept = worker_faces.identify_face(_vec(worker_faces.FACE_MAX_SAMPLES + 1))
        assert kept["worker_id"] == worker_id

        _drop_worker(worker_id)


class TestConfidenceBands:
    def test_mid_similarity_is_unverified_never_attributed(self):
        """Similarity between the unverified floor and match threshold yields a
        candidate identity that is NEVER treated as matched — the product must
        not guess names it is not sure of."""
        worker_id = "worker-445-test"
        _ensure_worker(worker_id)
        enrolled = np.zeros(128, dtype=np.float32)
        enrolled[0] = 1.0
        other = np.zeros(128, dtype=np.float32)
        other[1] = 1.0

        # Insert a synthetic sample directly at a controlled embedding.
        import json as _json
        from app.core.database import get_connection
        from datetime import datetime, timezone as _tz

        now = datetime.now(_tz.utc).isoformat()
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO worker_face_samples (worker_id, embedding, enrolled_at, sample_index) VALUES (?, ?, ?, 0)",
                (worker_id, _json.dumps(enrolled.tolist()), now),
            )
            conn.commit()

        # Query vector at cosine ~0.37 to the enrolled sample: inside the
        # unverified band [FACE_UNVERIFIED_THRESHOLD, FACE_MATCH_THRESHOLD).
        t = 0.37
        query = np.sqrt(max(0.0, 1.0 - t * t)) * other + t * enrolled
        query = query.astype(np.float32)
        result = worker_faces.identify_face(query)

        assert result["band"] == "unverified"
        assert result["matched"] is False
        assert result["verified"] is False
        # Candidate identity IS surfaced (for the "Name (?)" overlay tag).
        assert result["worker_id"] == worker_id

        _drop_worker(worker_id)


def _models_present() -> bool:
    from app.core.config import settings
    return os.path.exists(
        os.path.join(settings.MODEL_DIR, "face_detection_yunet_2023mar.onnx")
    )


@pytest.mark.skipif(
    not _models_present(),
    reason="YuNet/SFace models not present on disk",
)
class TestRealModelRoundTrip:
    def test_real_face_embedding_round_trip(self):
        """Enroll a real photo through YuNet+SFace, then match its own embedding."""
        # matplotlib ships a real face photo in its sample data.
        hop = Path(sys.prefix) / "Lib/site-packages/matplotlib/mpl-data/sample_data/grace_hopper.jpg"
        if not hop.exists():
            pytest.skip("grace_hopper.jpg sample image not available")
        image_bytes = hop.read_bytes()
        worker_id = "worker-555-test"
        _ensure_worker(worker_id)

        emb = worker_faces.embedding_from_image(image_bytes)
        assert emb is not None, "expected a face to be detected in the sample photo"
        assert emb.shape == (128,)

        worker_faces.enroll_worker(worker_id, image_bytes)
        result = worker_faces.identify_face(emb)
        assert result["matched"] is True
        assert result["worker_id"] == worker_id

        _drop_worker(worker_id)


class TestIdentifyPersonsInFrame:
    def test_no_boxes_returns_empty(self):
        frame = np.zeros((240, 320, 3), np.uint8)
        assert worker_faces.identify_persons_in_frame(frame, []) == []

    def test_each_person_gets_nested_box_entry(self, monkeypatch):
        """Every person box yields {box, worker_id, name, confidence, matched}."""
        # No enrolled faces -> identify_face returns no match for any box;
        # the entry shape must still be complete (box nested, seen=False).
        frame = np.zeros((240, 320, 3), np.uint8)
        boxes = [
            {"x1": 0.1, "y1": 0.1, "x2": 0.4, "y2": 0.9, "confidence": 0.9},
            {"x1": 0.6, "y1": 0.2, "x2": 0.9, "y2": 0.8, "confidence": 0.8},
        ]
        # Without the real models, identify_persons_in_frame returns [] early;
        # monkeypatch the model loader + detector to exercise the box loop.
        class _FakeDetector:
            def detect(self, img):
                return None, None  # no faces in the blank frame

        monkeypatch.setattr(worker_faces, "_load_models", lambda: (object(), object()))
        monkeypatch.setattr(
            worker_faces.cv2, "FaceDetectorYN",
            type("FDYN", (), {"create": staticmethod(lambda *a, **k: _FakeDetector())}),
        )
        out = worker_faces.identify_persons_in_frame(frame, boxes)
        # No faces detected in a blank frame -> seen=False, no identity.
        assert len(out) == 2
        for entry in out:
            assert "box" in entry and entry["box"]["x1"] >= 0
            assert entry["worker_id"] is None
            assert entry["matched"] is False
            assert entry["seen"] is False


class TestPersonDetectorDegradation:
    def test_detect_persons_returns_list_when_unavailable(self):
        from app.services import person_detector
        person_detector.reset_person_detector()
        frame = np.zeros((240, 320, 3), np.uint8)
        # With no model path configured this must degrade to [] — never raise.
        boxes = person_detector.detect_persons(frame)
        assert isinstance(boxes, list)
