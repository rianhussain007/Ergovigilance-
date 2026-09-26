"""Tests for yolo_cloud/cloud_settings.py (sell-readiness QA: real Save).

Covers: per-key validation incl. UI slider boundaries, unknown/traversal
rejection, save/load roundtrip, env-wins precedence, corrupt-file safety.
"""

from __future__ import annotations

import json

import pytest

from yolo_cloud.cloud_settings import (
    SETTABLE,
    apply_overrides,
    current_values,
    load_overrides,
    save_overrides,
    validate_settings,
)


def _good():
    return {
        "YOLO_MODEL": "yolov8s-pose.pt",
        "YOLO_DEVICE": "cpu",
        "YOLO_CONFIDENCE": 0.5,
        "INFERENCE_FPS": 10,
        "RTSP_TRANSPORT": "tcp",
        "RTSP_TIMEOUT": 5,
        "RTSP_RECONNECT_DELAY": 2.0,
        "SESSION_IDLE_TIMEOUT": 60,
    }


def test_validate_good_and_boundaries():
    cleaned = validate_settings(_good())
    assert cleaned["YOLO_CONFIDENCE"] == 0.5
    edge = dict(_good(), YOLO_CONFIDENCE=0.1, INFERENCE_FPS=30, RTSP_TIMEOUT=2,
                RTSP_RECONNECT_DELAY=10.0, SESSION_IDLE_TIMEOUT=300, YOLO_DEVICE="cuda:0")
    assert validate_settings(edge)["YOLO_DEVICE"] == "cuda:0"
    assert validate_settings({"YOLO_DEVICE": "1"})["YOLO_DEVICE"] == "1"


def test_validate_rejects():
    with pytest.raises(ValueError):
        validate_settings({"NOPE": 1})
    with pytest.raises(ValueError):
        validate_settings({"YOLO_CONFIDENCE": 0.99})
    with pytest.raises(ValueError):
        validate_settings({"INFERENCE_FPS": 0})
    with pytest.raises(ValueError):
        validate_settings({"RTSP_TRANSPORT": "quic"})
    with pytest.raises(ValueError):
        validate_settings({"YOLO_DEVICE": "tpu"})
    with pytest.raises(ValueError):
        validate_settings({"YOLO_MODEL": "../evil.pt"})
    with pytest.raises(ValueError):
        validate_settings({"YOLO_MODEL": "model.onnx"})
    with pytest.raises(ValueError):
        validate_settings("not-a-dict")


def test_save_load_roundtrip(tmp_path):
    path = tmp_path / "cloud_settings.json"
    saved = save_overrides(_good(), path)
    assert saved == _good()
    assert load_overrides(path) == _good()
    assert json.loads(path.read_text())["RTSP_TRANSPORT"] == "tcp"


def test_load_missing_and_corrupt(tmp_path):
    assert load_overrides(tmp_path / "nope.json") == {}
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert load_overrides(bad) == {}
    wrong = tmp_path / "wrong.json"
    wrong.write_text(json.dumps({"YOLO_CONFIDENCE": 5.0}), encoding="utf-8")
    assert load_overrides(wrong) == {}


def test_env_wins_over_file(tmp_path):
    path = tmp_path / "cloud_settings.json"
    save_overrides({"YOLO_CONFIDENCE": 0.7, "INFERENCE_FPS": 5}, path)

    class _Cfg:
        YOLO_CONFIDENCE = 0.5
        INFERENCE_FPS = 10

    cfg = _Cfg()
    applied = apply_overrides(cfg, env={"YOLO_CONFIDENCE": "0.9"}, path=path)
    assert cfg.YOLO_CONFIDENCE == 0.5  # env kept
    assert cfg.INFERENCE_FPS == 5  # file applied
    assert applied == ["INFERENCE_FPS"]


def test_current_values():
    class _Cfg:
        YOLO_MODEL = "x.pt"

    assert current_values(_Cfg())["YOLO_MODEL"] == "x.pt"
    assert set(current_values(_Cfg())) == set(SETTABLE)


def test_settable_matches_ui_sliders():
    assert SETTABLE["YOLO_CONFIDENCE"]["min"] == 0.1
    assert SETTABLE["YOLO_CONFIDENCE"]["max"] == 0.95
    assert SETTABLE["INFERENCE_FPS"]["max"] == 30
    assert SETTABLE["RTSP_TIMEOUT"]["min"] == 2
    assert SETTABLE["SESSION_IDLE_TIMEOUT"]["max"] == 300
