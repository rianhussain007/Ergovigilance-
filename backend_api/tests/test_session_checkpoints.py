"""Crash-safe session checkpoints: save_session_checkpoint writes the in-flight
session to .checkpoints/ (a subdir the session scanner ignores) and
recover_interrupted_sessions finalizes orphaned checkpoints into real session
files flagged ``interrupted: true`` after a hard crash.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.services.session_analytics import (  # noqa: E402
    _append_session_index,
    recover_interrupted_sessions,
    save_session_checkpoint,
    save_session_summary,
)

# Re-export for coverage of the summary path
from backend.services.session_analytics import _build_session_payload  # noqa: E402,F401


def _summary() -> dict:
    return {
        "session_duration_seconds": 305.5,
        "total_frames": 812,
        "risk_percentages": {"LOW": 60.0, "MEDIUM": 30.0, "HIGH": 10.0},
        "most_frequent_issue": "neck_flexion",
        "most_frequent_issue_count": 42,
        "highest_risk_level": "HIGH",
        "highest_risk_timestamp": "14:22:01",
        "avg_neck_flexion": 9.4,
        "avg_trunk_flexion": 18.2,
        "avg_shoulder_symmetry": 4.1,
        "avg_knee_angle": 161.3,
        "avg_forward_head_posture": 5.0,
        "avg_head_tilt_angle": 6.1,
        "avg_wrist_deviation_angle": 2.2,
        "avg_stance_stability": 88.0,
        "avg_weight_shift_offset": 3.3,
    }


def _alerts() -> dict:
    return {
        "history": [
            {"id": "ALT-1", "severity": "HIGH", "state": "ACTIVE",
             "trigger_rule": "high_risk", "message": "high risk"}
        ]
    }


def test_checkpoint_writes_to_checkpoints_subdir(tmp_path):
    path = save_session_checkpoint(
        _summary(), tmp_path, "20260818_120000", "SESH-ABC",
        alerts_data=_alerts(), meta={"worker_id": "w1", "camera_id": "cam-01"},
    )
    assert path is not None
    ckpt = Path(path)
    assert ckpt.parent.name == ".checkpoints"
    data = json.loads(ckpt.read_text(encoding="utf-8"))
    assert data["total_frames"] == 812
    assert data["checkpoint"] is True
    assert data["session_id"] == "SESH-ABC"
    assert data["worker_id"] == "w1"
    assert data["camera_id"] == "cam-01"
    assert len(data["alerts"]) == 1
    # The scanner must never see it: top-level dir has no .json entries.
    top_level = [f for f in tmp_path.iterdir() if f.suffix == ".json"]
    assert top_level == []


def test_checkpoint_requires_frames_and_session_id(tmp_path):
    no_frames = _summary()
    no_frames["total_frames"] = 0
    assert save_session_checkpoint(no_frames, tmp_path, "t", "SESH-X") is None
    assert save_session_checkpoint(_summary(), tmp_path, "t", None) is None


def test_recovery_finalizes_orphan_checkpoint(tmp_path):
    save_session_checkpoint(
        _summary(), tmp_path, "20260818_120000", "SESH-ABC",
        alerts_data=_alerts(), meta={"worker_id": "w1"},
    )
    recovered = recover_interrupted_sessions(tmp_path)
    assert len(recovered) == 1
    final = Path(recovered[0])
    assert final.parent == tmp_path
    data = json.loads(final.read_text(encoding="utf-8"))
    assert data["interrupted"] is True
    assert "interrupted_at" in data
    assert "checkpoint" not in data
    assert data["worker_id"] == "w1"
    assert len(data["alerts"]) == 1
    # Checkpoint dir cleaned up, index row appended.
    assert not (tmp_path / ".checkpoints").exists()
    index = (tmp_path / "session_index.csv").read_text(encoding="utf-8")
    assert "60.0" in index


def test_recovery_skips_already_finalized(tmp_path):
    save_session_checkpoint(
        _summary(), tmp_path, "20260818_120000", "SESH-ABC"
    )
    # Simulate a clean stop that also finalized the real file.
    save_session_summary(_summary(), tmp_path, "20260818_120000", session_id="SESH-ABC")
    recovered = recover_interrupted_sessions(tmp_path)
    assert recovered == []
    finals = [f for f in tmp_path.glob("session_*.json")]
    assert len(finals) == 1
    assert json.loads(finals[0].read_text(encoding="utf-8")).get("interrupted") is None


def test_recovery_skips_empty_checkpoint(tmp_path):
    ckpt_dir = tmp_path / ".checkpoints"
    ckpt_dir.mkdir()
    (ckpt_dir / "session_20260818_120000_SESH-EMPTY.json").write_text(
        json.dumps({"total_frames": 0, "checkpoint": True}), encoding="utf-8"
    )
    recovered = recover_interrupted_sessions(tmp_path)
    assert recovered == []
    assert not (ckpt_dir / "session_20260818_120000_SESH-EMPTY.json").exists()
