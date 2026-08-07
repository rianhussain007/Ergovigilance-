from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List

# Canonical definition lives in backend.core.constants.
# Re-exported here for backward compatibility.
from backend.core.constants import RISK_ORDER  # noqa: F401


class SessionAnalytics:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._start_time: float = time.monotonic()
        self._frame_count: int = 0
        self._risk_counts: Dict[str, int] = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
        self._issue_counts: Dict[str, int] = {}
        self._highest_risk_level: str = "LOW"
        self._highest_risk_timestamp: str | None = None
        self._neck_sum: float = 0.0
        self._trunk_sum: float = 0.0
        self._shoulder_sum: float = 0.0
        self._knee_sum: float = 0.0

    @property
    def elapsed_seconds(self) -> float:
        return time.monotonic() - self._start_time

    def update(
        self,
        features: Dict[str, float],
        risk_level: str,
        issues: List[Dict],
        person_detected: bool,
        frame_timestamp: str | None = None,
    ) -> None:
        if not person_detected:
            return

        self._frame_count += 1

        normalized_risk = risk_level.upper()
        if normalized_risk in self._risk_counts:
            self._risk_counts[normalized_risk] += 1
        else:
            self._risk_counts[normalized_risk] = 1

        current_rank = RISK_ORDER.get(normalized_risk, -1)
        highest_rank = RISK_ORDER.get(self._highest_risk_level, -1)
        if current_rank > highest_rank:
            self._highest_risk_level = normalized_risk
            self._highest_risk_timestamp = frame_timestamp or datetime.now().strftime("%H:%M:%S")

        for issue in issues:
            name = issue["issue"]
            self._issue_counts[name] = self._issue_counts.get(name, 0) + 1

        self._neck_sum += features.get("neck_flexion", 0.0)
        self._trunk_sum += features.get("trunk_flexion", 0.0)
        self._shoulder_sum += features.get("shoulder_symmetry", 0.0)
        self._knee_sum += features.get("knee_angle", 0.0)

    def get_summary(self) -> Dict:
        if self._frame_count == 0:
            return {
                "session_duration_seconds": round(self.elapsed_seconds, 1),
                "total_frames": 0,
                "risk_percentages": {"LOW": 0.0, "MEDIUM": 0.0, "HIGH": 0.0},
                "most_frequent_issue": None,
                "most_frequent_issue_count": 0,
                "highest_risk_level": "LOW",
                "highest_risk_timestamp": None,
                "avg_neck_flexion": 0.0,
                "avg_trunk_flexion": 0.0,
                "avg_shoulder_symmetry": 0.0,
                "avg_knee_angle": 0.0,
            }

        total = self._frame_count
        risk_pct: Dict[str, float] = {
            k: round(v / total * 100, 1) for k, v in self._risk_counts.items()
        }

        most_frequent: str | None = None
        most_frequent_count: int = 0
        if self._issue_counts:
            most_frequent = max(self._issue_counts, key=self._issue_counts.get)
            most_frequent_count = self._issue_counts[most_frequent]

        avg_neck = round(self._neck_sum / total, 2)
        avg_trunk = round(self._trunk_sum / total, 2)
        avg_shoulder = round(self._shoulder_sum / total, 2)
        avg_knee = round(self._knee_sum / total, 2)

        return {
            "session_duration_seconds": round(self.elapsed_seconds, 1),
            "total_frames": total,
            "risk_percentages": risk_pct,
            "most_frequent_issue": most_frequent,
            "most_frequent_issue_count": most_frequent_count,
            "highest_risk_level": self._highest_risk_level,
            "highest_risk_timestamp": self._highest_risk_timestamp,
            "avg_neck_flexion": avg_neck,
            "avg_trunk_flexion": avg_trunk,
            "avg_shoulder_symmetry": avg_shoulder,
            "avg_knee_angle": avg_knee,
        }


SESSION_INDEX_COLS = [
    "timestamp", "duration", "high_pct", "medium_pct", "low_pct",
    "most_frequent_issue", "highest_risk",
]


def save_session_summary(
    summary: Dict,
    sessions_dir: str | Path,
    session_timestamp: str | None = None,
    alerts_data: Dict | None = None,
    session_id: str | None = None,
) -> str | None:
    if summary["total_frames"] == 0:
        return None

    sessions_dir = Path(sessions_dir)
    sessions_dir.mkdir(parents=True, exist_ok=True)

    ts = session_timestamp or datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]

    if session_id:
        filename = f"session_{ts}_{session_id}.json"
    else:
        filename = f"session_{ts}.json"
    filepath = sessions_dir / filename

    payload = {
        "session_timestamp": ts,
        "session_duration_seconds": summary["session_duration_seconds"],
        "total_frames": summary["total_frames"],
        "risk_percentages": summary["risk_percentages"],
        "most_frequent_issue": summary["most_frequent_issue"],
        "most_frequent_issue_count": summary["most_frequent_issue_count"],
        "highest_risk_level": summary["highest_risk_level"],
        "highest_risk_timestamp": summary["highest_risk_timestamp"],
        "avg_neck_flexion": summary["avg_neck_flexion"],
        "avg_trunk_flexion": summary["avg_trunk_flexion"],
        "avg_shoulder_symmetry": summary["avg_shoulder_symmetry"],
        "avg_knee_angle": summary["avg_knee_angle"],
    }

    if alerts_data:
        payload["alerts"] = alerts_data.get("history", [])

    with open(filepath, "w") as f:
        json.dump(payload, f, indent=2)

    _append_session_index(sessions_dir, summary, ts)

    return str(filepath)


def _append_session_index(
    sessions_dir: Path,
    summary: Dict,
    timestamp_key: str,
) -> None:
    index_path = sessions_dir / "session_index.csv"
    rp = summary["risk_percentages"]
    row = [
        timestamp_key,
        summary["session_duration_seconds"],
        rp.get("HIGH", 0.0),
        rp.get("MEDIUM", 0.0),
        rp.get("LOW", 0.0),
        summary["most_frequent_issue"] or "",
        summary["highest_risk_level"],
    ]

    is_new = not index_path.exists()
    with open(index_path, "a", newline="") as f:
        if is_new:
            f.write(",".join(SESSION_INDEX_COLS) + "\n")
        f.write(",".join(str(v) for v in row) + "\n")
