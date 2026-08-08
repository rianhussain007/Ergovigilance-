"""Unit tests for the task classifier v2 (model-primary, Gaussian fallback).

The trained model lives in models/task_model_v2.pkl (git-tracked, verified
by scripts/verify_models.py). Tests skip gracefully when it is absent so
the suite also runs in minimal environments.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.services.features import MEDIAPIPE_33, extract_features_from_keypoints  # noqa: E402
from backend.services.task_recognition import TaskRecognition  # noqa: E402

MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "task_model_v2.pkl"

CLASSES = ["Neutral Standing", "Assembly Work", "Reaching", "Lifting / Picking", "Inspection"]

_NEUTRAL = {
    "nose": (320, 120),
    "left_ear": (295, 130),
    "right_ear": (345, 130),
    "left_shoulder": (295, 220),
    "right_shoulder": (345, 220),
    "left_elbow": (295, 330),
    "right_elbow": (345, 330),
    "left_wrist": (295, 430),
    "right_wrist": (345, 430),
    "left_index": (295, 445),
    "right_index": (345, 445),
    "left_thumb": (299, 440),
    "right_thumb": (341, 440),
    "left_pinky": (296, 447),
    "right_pinky": (344, 447),
    "left_hip": (300, 420),
    "right_hip": (340, 420),
    "left_knee": (305, 560),
    "right_knee": (335, 560),
    "left_ankle": (305, 700),
    "right_ankle": (335, 700),
    "left_heel": (307, 720),
    "right_heel": (333, 720),
    "left_foot_index": (309, 730),
    "right_foot_index": (331, 730),
}


def _build_33(overrides: dict | None = None) -> np.ndarray:
    kp = np.zeros((33, 4))
    kp[:, 3] = 0.95
    pts = dict(_NEUTRAL)
    if overrides:
        pts.update(overrides)
    for name, (x, y) in pts.items():
        kp[MEDIAPIPE_33[name], 0] = x
        kp[MEDIAPIPE_33[name], 1] = y
    return kp


def _features(kp: np.ndarray) -> dict:
    feats, _, _ = extract_features_from_keypoints(kp)
    feats["movement_velocity"] = 0.0
    feats["wrist_movement_velocity"] = 0.0
    return feats


@pytest.fixture(scope="module")
def model_available():
    return MODEL_PATH.exists()


class TestBundle:
    def test_bundle_shape(self, model_available):
        if not model_available:
            pytest.skip("task_model_v2.pkl not present")
        import joblib

        bundle = joblib.load(MODEL_PATH)
        assert set(bundle.keys()) >= {"model", "feature_columns", "labels", "config"}
        assert len(bundle["feature_columns"]) == 19
        assert bundle["labels"] == CLASSES
        assert bundle["config"]["confidence_threshold"] == 0.6

    def test_proba_is_distribution(self, model_available):
        if not model_available:
            pytest.skip("task_model_v2.pkl not present")
        import joblib

        bundle = joblib.load(MODEL_PATH)
        feats = _features(_build_33())
        row = [feats.get(c, 0.0) for c in bundle["feature_columns"]]
        proba = bundle["model"].predict_proba([row])[0]
        assert proba.shape == (5,)
        assert proba.sum() == pytest.approx(1.0)


class TestRuntimeIntegration:
    def test_neutral_pose_returns_known_task(self):
        recognizer = TaskRecognition()
        kp = _build_33()
        info = recognizer.detect_task(kp, _features(kp))
        assert info["task"] in CLASSES
        assert 0.0 <= info["confidence"] <= 100.0
        assert "task_duration_seconds" in info

    def test_missing_model_falls_back_to_gaussian(self):
        recognizer = TaskRecognition(model_path="C:/nonexistent/task_model_v2.pkl")
        assert recognizer.using_model is False
        kp = _build_33()
        info = recognizer.detect_task(kp, _features(kp))
        assert info["task"] in CLASSES or info["task"] == "Unknown"
        assert recognizer.using_model is False

    def test_degenerate_keypoints_are_unknown(self):
        recognizer = TaskRecognition(model_path="C:/nonexistent/task_model_v2.pkl")
        kp = np.zeros((33, 4))
        info = recognizer.detect_task(kp, _features(kp))
        assert info["task"] == "Unknown"

    def test_neutral_pose_decides_via_model(self, model_available):
        """Model-primary on a REAL neutral standing pose (arms at sides,
        raise ~1.05). Regression for the 2026-08-08 retrain: the synthetic
        generator now spans hands-at-sides, so a real neutral pose must sit
        INSIDE the trained Neutral Standing cluster, clear the 0.6 gate and
        report using_model=True with the correct label — not fall back to the
        Gaussian and not read back a rotated class name (predict_proba
        columns follow model.classes_, not bundle labels)."""
        if not model_available:
            pytest.skip("task_model_v2.pkl not present")
        recognizer = TaskRecognition()
        kp = _build_33()
        info = recognizer.detect_task(kp, _features(kp))
        assert recognizer.using_model is True
        assert info["task"] == "Neutral Standing"
        assert info["confidence"] >= 60.0  # cleared the 0.6 gate
        assert "Trained task classifier" in info["reason"]

    def test_real_model_out_of_distribution_gates_to_gaussian(self, model_available):
        """Graceful degradation stays intact: a genuinely out-of-distribution
        pose (arms crossed at the waist — the generator never produces crossed
        wrists) must route to the Gaussian fallback instead of an unguarded
        model guess."""
        if not model_available:
            pytest.skip("task_model_v2.pkl not present")
        recognizer = TaskRecognition()
        overrides = {
            "left_wrist": (345, 400), "right_wrist": (295, 400),
            "left_index": (352, 415), "right_index": (288, 415),
        }
        kp = _build_33(overrides)
        info = recognizer.detect_task(kp, _features(kp))
        assert info["task"] in CLASSES or info["task"] == "Unknown"
        assert recognizer.using_model is False


class DummyModel:
    """Picklable stand-in exposing sklearn's predict_proba shape."""

    def __init__(self, row: list[float]):
        self._row = row

    def predict_proba(self, X):
        return np.tile([self._row], (len(X), 1))


class TestConfidenceGate:
    """The gate must route to the model only when the top prediction clears
    the 0.6 threshold — otherwise the Gaussian fallback decides and the drift
    canary sees a 'gaussian' source. These use a fabricated bundle so the
    gate logic is exercised without depending on the trained artifact."""

    @pytest.fixture()
    def low_conf_bundle(self, tmp_path):
        import joblib

        bundle = {
            "model": DummyModel([0.30, 0.25, 0.20, 0.15, 0.10]),  # best 0.30 < 0.6
            "feature_columns": [
                "neck_flexion", "trunk_flexion", "left_shoulder_elev",
                "right_shoulder_elev", "shoulder_symmetry", "alignment_deviation",
            ],
            "labels": CLASSES,
            "config": {"confidence_threshold": 0.6},
        }
        path = tmp_path / "low_conf.pkl"
        joblib.dump(bundle, path)
        return str(path)

    @pytest.fixture()
    def high_conf_bundle(self, tmp_path):
        import joblib

        bundle = {
            "model": DummyModel([0.85, 0.05, 0.05, 0.03, 0.02]),  # best 0.85 >= 0.6
            "feature_columns": [
                "neck_flexion", "trunk_flexion", "left_shoulder_elev",
                "right_shoulder_elev", "shoulder_symmetry", "alignment_deviation",
            ],
            "labels": CLASSES,
            "config": {"confidence_threshold": 0.6},
        }
        path = tmp_path / "high_conf.pkl"
        joblib.dump(bundle, path)
        return str(path)

    def test_below_threshold_gates_to_gaussian(self, low_conf_bundle):
        recognizer = TaskRecognition(model_path=low_conf_bundle)
        assert recognizer._get_model_bundle() is not None  # model IS loadable
        kp = _build_33()
        info = recognizer.detect_task(kp, _features(kp))
        assert recognizer.using_model is False
        # Gaussian must still return a decision on a valid pose
        assert info["task"] in CLASSES or info["task"] == "Unknown"
        assert "Trained task classifier" not in info["reason"]

    def test_at_threshold_uses_model(self, high_conf_bundle):
        recognizer = TaskRecognition(model_path=high_conf_bundle)
        assert recognizer._get_model_bundle() is not None
        kp = _build_33()
        info = recognizer.detect_task(kp, _features(kp))
        assert recognizer.using_model is True
        assert info["task"] == CLASSES[0]  # argmax label of the fabricated row
        assert info["confidence"] == pytest.approx(85.0, abs=0.1)
        assert "Trained task classifier" in info["reason"]

    def test_threshold_read_from_bundle_config(self, low_conf_bundle):
        recognizer = TaskRecognition(model_path=low_conf_bundle)
        recognizer._get_model_bundle()
        assert recognizer._confidence_threshold == 0.6
