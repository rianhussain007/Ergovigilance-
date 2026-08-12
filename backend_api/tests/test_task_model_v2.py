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

CLASSES = [
    "Neutral Standing", "Assembly Work", "Reaching", "Lifting / Picking",
    "Inspection", "Seated Work", "Walking / Moving",
]

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
        assert proba.shape == (len(CLASSES),)
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

    def test_seated_pose_is_seated_work_not_neutral_standing(self):
        """The user-facing regression: a sitting worker (knee ~93°, thighs
        horizontal, hips dropped) must read 'Seated Work' — never 'Neutral
        Standing'. The geometric gate decides BEFORE the model, so this holds
        even with the trained classifier present (which was trained on
        standing poses and confidently mislabeled real seating at 98.9%)."""
        recognizer = TaskRecognition()
        overrides = {
            # Drop the whole torso ~84px so the hips land at knee height
            # (thighs horizontal), keep ankles forward under the knees.
            "left_shoulder": (295, 304), "right_shoulder": (345, 304),
            "nose": (320, 204), "left_ear": (295, 214), "right_ear": (345, 214),
            "left_elbow": (290, 400), "right_elbow": (350, 400),
            "left_wrist": (300, 470), "right_wrist": (340, 470),
            "left_hip": (300, 504), "right_hip": (340, 504),
            "left_knee": (305, 560), "right_knee": (335, 560),
            "left_ankle": (385, 610), "right_ankle": (415, 610),
            "left_heel": (387, 624), "right_heel": (417, 624),
            "left_foot_index": (395, 626), "right_foot_index": (425, 626),
        }
        kp = _build_33(overrides)
        info = recognizer.detect_task(kp, _features(kp))
        assert info["task"] == "Seated Work"
        assert info["confidence"] >= 60.0

    def test_seated_gate_uses_geometry_not_model(self, model_available):
        """The seated gate must fire even when the model is present and
        would confidently vote otherwise — geometry is authoritative."""
        if not model_available:
            pytest.skip("task_model_v2.pkl not present")
        recognizer = TaskRecognition()
        overrides = {
            "left_shoulder": (295, 304), "right_shoulder": (345, 304),
            "left_hip": (300, 504), "right_hip": (340, 504),
            "left_knee": (305, 560), "right_knee": (335, 560),
            "left_ankle": (385, 610), "right_ankle": (415, 610),
            "left_elbow": (290, 400), "right_elbow": (350, 400),
            "left_wrist": (300, 470), "right_wrist": (340, 470),
        }
        kp = _build_33(overrides)
        info = recognizer.detect_task(kp, _features(kp))
        assert info["task"] == "Seated Work"
        assert recognizer.using_model is False
        assert "seated" in info["reason"].lower()

    def test_standing_neutral_not_seated(self):
        """Straight legs (knee ~180°) must NOT trip the seated gate."""
        recognizer = TaskRecognition(model_path="C:/nonexistent/task_model_v2.pkl")
        kp = _build_33()  # neutral standing, knees straight
        info = recognizer.detect_task(kp, _features(kp))
        assert info["task"] != "Seated Work"
        assert info["task"] in CLASSES

    def test_walking_velocity_detected(self):
        """High frame-to-frame movement with an upright posture and straight
        legs reads as 'Walking / Moving', not 'Neutral Standing' (which now
        subtracts a velocity term)."""
        recognizer = TaskRecognition(model_path="C:/nonexistent/task_model_v2.pkl")
        kp = _build_33()
        feats = _features(kp)
        feats["movement_velocity"] = 120.0
        feats["wrist_movement_velocity"] = 90.0
        info = recognizer.detect_task(kp, feats)
        assert info["task"] == "Walking / Moving"

    def test_real_model_out_of_distribution_gates_to_gaussian(self, model_available):
        """Graceful degradation stays intact: a genuinely out-of-distribution
        pose (T-pose — arms fully abducted to horizontal; the generator never
        produces it) must route to the Gaussian fallback instead of an
        unguarded model guess. Arms crossed at the waist no longer qualifies
        as OOD — the 7-class model confidently handles it."""
        if not model_available:
            pytest.skip("task_model_v2.pkl not present")
        recognizer = TaskRecognition()
        overrides = {
            "left_elbow": (195, 220), "right_elbow": (445, 220),
            "left_wrist": (130, 220), "right_wrist": (510, 220),
            "left_index": (110, 215), "right_index": (530, 215),
            "left_thumb": (120, 210), "right_thumb": (520, 210),
            "left_pinky": (105, 225), "right_pinky": (535, 225),
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
