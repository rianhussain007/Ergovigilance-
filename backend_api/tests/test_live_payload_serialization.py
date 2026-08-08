"""Regression tests for live-monitoring payload fixes.

Covers two production bugs found while running Live Monitoring:

1. ``app.repositories.live.LiveRepository.get_context_snapshot`` crashed with
   ``PydanticSerializationError: Unable to serialize unknown type: numpy.float32``
   because ``ContextSnapshot.feature_scores`` can hold numpy scalars (from EMA
   smoothing / numpy-sourced feature values) and the old NaN guard
   (``isinstance(v, float)``) missed them — the endpoint 500'd on every poll.

2. ``app.services.live_monitor._process_loop`` treated the recommendation
   export (a ``to_dict()``-serialized bundle of dicts) as dataclasses and did
   ``r.id`` — an ``AttributeError`` logged every frame, silently dropping the
   timeline's recommendations.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.context.engine import ContextSnapshot  # noqa: E402
from app.repositories.live import LiveRepository  # noqa: E402
from app.schemas.api import ContextSnapshotResponse  # noqa: E402
from app.services.live_monitor import (  # noqa: E402
    build_ws_payload,
    clean_feature_values,
    export_recommendations_from_bundle,
)
from backend.core.types import LiveState  # noqa: E402
from backend.services.features import compute_rula_informed_score  # noqa: E402
from backend.services.guidance import build_guidance  # noqa: E402

_FEATURES = {
    "neck_flexion": 5.0, "trunk_flexion": 5.0,
    "left_shoulder_elev": 10.0, "right_shoulder_elev": 10.0,
    "shoulder_symmetry": 2.0, "alignment_deviation": 3.0,
    "knee_angle": 170.0, "elbow_flexion_angle": 170.0,
    "upper_arm_angle_from_vertical": 5.0,
    "forward_head_posture": 4.0, "head_tilt_angle": 3.0,
    "wrist_deviation_angle": 0.0, "stance_stability": 0.8,
    "weight_shift_offset": 4.0, "hand_reach_ratio": 1.0,
    "finger_spread_ratio": 0.4, "stance_width_ratio": 0.9,
}


def _make_snapshot(feature_scores: dict) -> ContextSnapshot:
    return ContextSnapshot(
        session_id="SESH-1", frame_number=1,
        captured_at="2026-08-07T23:34:28Z", worker_id="W1",
        base_risk=10.0, context_modifier=0.0, fatigue_score=5.0, exposure_score=3.0,
        confidence_modifier=0.0, final_risk=12.0, risk_level="MEDIUM", safety_state="SAFE",
        reason="test", active_rules=("R1",),
        feature_scores=feature_scores,
        unavailable_features=("finger_spread_ratio",),
        approximate_features=("neck_flexion",),
        lower_body_confidence=0.9,
    )


class _FakeService:
    def get_state_snapshot(self):
        return SimpleNamespace(
            context_snapshot=_make_snapshot({
                "neck_flexion": np.float64(5.0),
                "knee_angle": np.float32(170.0),
                "nan_feat": float("nan"),
            }),
            features=_FEATURES,
        )


class LivePayloadSerializationTest(unittest.TestCase):
    def test_context_snapshot_serializes_numpy_and_nan_scores(self):
        """feature_scores with numpy scalars/NaN must serialize (regression for the 500)."""
        import asyncio

        repo = LiveRepository()
        fake = _FakeService()

        with patch("app.repositories.live.get_live_service", return_value=fake):
            result = asyncio.run(repo.get_context_snapshot())

        assert result is not None
        assert isinstance(result, ContextSnapshotResponse)
        assert result.feature_scores["neck_flexion"] == 5.0
        assert result.feature_scores["knee_angle"] == 170.0
        assert result.feature_scores["nan_feat"] is None
        # pydantic JSON serialization must succeed (this raised before the fix)
        result.model_dump_json()
        assert result.guidance is not None
        assert result.rula_informed_score is not None

    def test_context_snapshot_guidance_renders(self):
        """Guidance + RULA blocks build from realistic features."""
        raw = build_guidance(_FEATURES)
        assert raw["feedback"]
        rula = compute_rula_informed_score(_FEATURES)
        assert rula["rula_informed_score"] >= 1

    def test_recommendation_export_dict_access(self):
        """_process_loop's recommendation export must use dict access (regression).

        RecommendationEngine.export() returns bundle.to_dict() — a dict of dicts —
        so attribute access (r.id) raised AttributeError every frame.
        """
        rec_bundle = {
            "bundle": {
                "recommendations": [
                    {"id": "REC-1", "title": "Adjust seat", "category": "posture", "priority": "high"},
                ],
                "summary": "1 rec",
            },
            "total_generated": 1,
        }
        exported = export_recommendations_from_bundle(rec_bundle)
        assert exported == [{"id": "REC-1", "title": "Adjust seat", "category": "posture", "priority": "high"}]

    def test_recommendation_export_handles_empty_and_non_dict(self):
        assert export_recommendations_from_bundle(None) == []
        assert export_recommendations_from_bundle({}) == []
        assert export_recommendations_from_bundle({"bundle": {"recommendations": ["not-a-dict"]}}) == []

    def test_clean_feature_values_json_safe(self):
        """WebSocket payload features must be JSON-safe (numpy → float, NaN → None)."""
        cleaned = clean_feature_values({
            "neck_flexion": np.float64(5.0),
            "knee_angle": np.float32(170.0),
            "nan_feat": float("nan"),
            "plain": 3.0,
            "bad": object(),
        })
        assert cleaned["neck_flexion"] == 5.0
        assert cleaned["knee_angle"] == 170.0
        assert cleaned["nan_feat"] is None
        assert cleaned["plain"] == 3.0
        assert cleaned["bad"] is None
        # The cleaned dict must round-trip through JSON without errors
        import json

        json.dumps(cleaned)
        # None features input must not raise
        assert clean_feature_values(None) == {}

    def test_build_ws_payload_json_safe_and_numpy_clean(self):
        """get_ws_payload must serialize without deep-copying the frame and with
        numpy scalars coerced to floats (regression guard for WS JSON breaks)."""
        import json

        state = LiveState(
            session_active=True,
            session_id="SESH-1",
            current_frame=np.zeros((4, 4, 3), dtype=np.uint8),  # must NOT be serialized
            risk_level="MEDIUM",
            risk_score=np.float32(12.5),
            confidence=np.float64(0.87),
            task_confidence=0.6,
            fps=np.float32(29.97),
            inference_latency_ms=18.2,
            features={
                "neck_flexion": np.float64(5.0),
                "knee_angle": np.float32(170.0),
                "occluded": float("nan"),
            },
            issues=["neck_flexion"],
        )
        payload = build_ws_payload(state)
        # Frame must not leak into the wire payload
        assert "current_frame" not in payload
        assert payload["risk_score"] == 12.5
        assert payload["confidence"] == 0.87
        assert abs(payload["fps"] - 29.97) < 0.01  # float32 precision
        assert payload["features"]["occluded"] is None
        assert payload["features"]["knee_angle"] == 170.0
        assert payload["issues"] == ["neck_flexion"]
        # Must round-trip through JSON without errors (this broke before)
        json.dumps(payload)


if __name__ == "__main__":
    unittest.main()
