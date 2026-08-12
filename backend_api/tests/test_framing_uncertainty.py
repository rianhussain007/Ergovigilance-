"""Tests for Tier 3 framing intelligence and uncertainty-aware scoring.

Covers:
- ``framing_quality.assess_framing``: full-body / cropped / profile detection,
  guidance text, quality score.
- Per-joint uncertainty: profile view inflates depth-sensitive joint sigma.
- ``ContextIntelligenceEngine._score_feature``: soft P(rule violated) scoring
  near boundaries (no snap), with legacy hard behavior preserved at sigma=0.
- ``RiskForecaster.predict_per_joint``: per-joint trend forecast + honesty
  guard for thin data.
"""

from __future__ import annotations

from backend.context.engine import ContextIntelligenceEngine
from backend.services.framing_quality import assess_framing
from backend.services.predictive import RiskForecaster

SF = ContextIntelligenceEngine._score_feature


def _full_body_keypoints() -> list:
    kps = []
    for i in range(33):
        kps.append([320.0, 240.0, 0.0, 1.0])
    kps[0] = [320, 60, 0.0, 0.95]     # nose
    kps[7] = [300, 70, 0.0, 0.9]      # left ear
    kps[8] = [340, 70, 0.0, 0.9]      # right ear
    kps[11] = [270, 140, 0.0, 0.95]   # left shoulder
    kps[12] = [370, 140, 0.0, 0.95]   # right shoulder
    kps[13] = [250, 220, 0.0, 0.9]    # left elbow
    kps[14] = [390, 220, 0.0, 0.9]    # right elbow
    kps[15] = [240, 300, 0.0, 0.85]   # left wrist
    kps[16] = [400, 300, 0.0, 0.85]   # right wrist
    kps[23] = [280, 330, 0.0, 0.9]    # left hip
    kps[24] = [360, 330, 0.0, 0.9]    # right hip
    kps[25] = [280, 480, 0.0, 0.85]   # left knee
    kps[26] = [360, 480, 0.0, 0.85]   # right knee
    kps[27] = [280, 660, 0.0, 0.8]    # left ankle
    kps[28] = [360, 660, 0.0, 0.8]    # right ankle
    kps[29] = [280, 680, 0.0, 0.75]
    kps[30] = [360, 680, 0.0, 0.75]
    return kps


def test_full_body_framing_is_good():
    f = assess_framing(_full_body_keypoints(), 640, 720)
    assert f["framing_state"] == "full_body"
    assert f["quality_score"] >= 90
    assert "Good framing" in f["guidance"][0]


def test_cropped_bottom_flags_lower_body_guidance():
    kps = _full_body_keypoints()
    for i in (27, 28, 29, 30):
        kps[i][1] = 715  # ankles at frame bottom edge
    f = assess_framing(kps, 640, 720)
    assert f["framing_state"] in ("upper_body", "poor")
    assert any("Lower body out of frame" in g for g in f["guidance"])


def test_profile_view_inflates_depth_sensitive_sigma():
    base = assess_framing(_full_body_keypoints(), 640, 720)
    kps = _full_body_keypoints()
    kps[11][2] = 0.5    # left shoulder much closer
    kps[12][2] = -0.5   # right shoulder far
    prof = assess_framing(kps, 640, 720)
    assert prof["profile_view"] is True
    assert prof["joint_uncertainty"]["trunk_flexion"] > base["joint_uncertainty"]["trunk_flexion"]
    assert prof["quality_score"] < base["quality_score"]


def test_uncertainty_scoring_softens_boundaries():
    # At the exact HIGH cutoff, hard scoring snaps to 100; soft stays ~75.
    hard = SF(35.0, 15.0, 35.0, False, 0.0)
    soft = SF(35.0, 15.0, 35.0, False, 5.0)
    assert hard == 100.0
    assert soft < hard - 10
    # At the exact MEDIUM cutoff, hard is 0; soft rises toward 25.
    assert SF(15.0, 15.0, 35.0, False, 0.0) == 0.0
    assert SF(15.0, 15.0, 35.0, False, 5.0) > 0.0
    # Far from boundaries both agree.
    assert SF(5.0, 15.0, 35.0, False, 5.0) < 5.0
    assert SF(60.0, 15.0, 35.0, False, 5.0) > 95.0
    # Inverted feature (knee, lower = riskier).
    assert SF(100.0, 150.0, 100.0, True, 0.0) == 100.0
    assert SF(100.0, 150.0, 100.0, True, 6.0) < 100.0


def test_engine_accepts_joint_uncertainty():
    engine = ContextIntelligenceEngine(session_id="S-U")
    snap = engine.evaluate(
        features={"neck_flexion": 35.0, "trunk_flexion": 10.0, "left_shoulder_elev": 15.0,
                  "right_shoulder_elev": 16.0, "shoulder_symmetry": 2.5, "alignment_deviation": 4.0,
                  "knee_angle": 160.0, "forward_head_posture": 4.0, "head_tilt_angle": 3.0,
                  "wrist_deviation_angle": 0.0, "stance_stability": 0.8, "weight_shift_offset": 4.0},
        issues=[], task_name="Assembly Work", task_confidence=85.0,
        session_duration_seconds=60.0, camera_confidence=95.0, delta_seconds=0.033,
        joint_uncertainty={"neck_flexion": 6.0, "trunk_flexion": 5.0},
    )
    assert snap.risk_level in ("LOW", "MEDIUM", "HIGH")
    assert snap.final_risk >= 0.0


def test_per_joint_forecast_honesty_guard():
    frames = [{"risk_score": 30.0, "risk_level": "LOW", "timestamp": i * 5.0,
               "features": {"neck_flexion": 10 + i * 0.2, "trunk_flexion": 12.0}}
              for i in range(40)]
    fc = RiskForecaster()
    out = fc.predict_per_joint(frames)
    assert out["insufficient_data"] is False
    assert len(out["joints"]) == 5
    assert out["joints"][0]["joint"] == "neck_flexion"
    assert out["joints"][0]["available"] is True
    # Thin data -> honest "not enough data", never fabricated.
    assert fc.predict_per_joint(frames[:3])["insufficient_data"] is True
