from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict

from backend.services.recommendation_engine import _RECOMMENDATIONS

# Canonical definitions live in backend.core.utils.
# Re-exported here for backward compatibility.
from backend.core.utils import sanitize_text as _sanitize_text  # noqa: F401
from backend.core.utils import _UNICODE_REPLACEMENTS  # noqa: F401


_RECOMMENDATION_KEYS = {k.lower(): k for k in _RECOMMENDATIONS}


def _recommendation_for(issue_name: str | None) -> tuple[str, str] | None:
    if not issue_name:
        return None
    key = _RECOMMENDATION_KEYS.get(issue_name.lower())
    if not key:
        return None
    rec = _RECOMMENDATIONS[key]
    worker = rec["worker_actions"][0] if rec.get("worker_actions") else "Maintain neutral posture."
    supervisor = rec["supervisor_actions"][0] if rec.get("supervisor_actions") else "Monitor and adjust workstation."
    return (worker, supervisor)


def _assess_safety(summary: Dict) -> str:
    rp = summary["risk_percentages"]
    high = rp.get("HIGH", 0.0)
    medium = rp.get("MEDIUM", 0.0)

    if high >= 20.0 or medium >= 50.0:
        return "High Risk"
    if high >= 10.0 or medium >= 30.0:
        return "Moderate Risk"
    if high == 0.0 and medium < 10.0:
        return "Excellent"
    return "Good"


def _format_duration(seconds: float) -> str:
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    if minutes >= 60:
        hours = minutes // 60
        minutes = minutes % 60
        return f"{hours}h {minutes}m {secs}s"
    return f"{minutes}m {secs}s"


class SafetyReport:
    def __init__(self, session_data: Dict) -> None:
        self._data = session_data

    @classmethod
    def from_json(cls, json_path: str | Path) -> SafetyReport:
        with open(json_path) as f:
            data = json.load(f)
        return cls(data)

    def _generate_executive_summary(self) -> list[str]:
        d = self._data
        rp = d["risk_percentages"]
        assessment = _assess_safety(d)
        mf = d.get("most_frequent_issue")

        low = rp.get("LOW", 0.0)
        med = rp.get("MEDIUM", 0.0)
        high = rp.get("HIGH", 0.0)

        lines: list[str] = []
        lines.append(f"This session was classified as {assessment}.")

        risk_detail = (
            f"The worker spent {low}% of the session in LOW-risk postures, "
            f"{med}% in MEDIUM-risk postures, and {high}% in HIGH-risk postures."
        )
        lines.append(risk_detail)

        if mf:
            lines.append(f"The most frequently observed ergonomic issue was {mf}.")

        if assessment == "Excellent":
            lines.append("Posture quality was excellent throughout the session. "
                         "Continued adherence to current ergonomic practices is recommended.")
        elif assessment == "Good":
            lines.append("Posture quality was good overall. "
                         "Minor adjustments may further reduce ergonomic risk.")
        elif assessment == "Moderate Risk":
            lines.append("Overall posture quality was acceptable but requires "
                         "improvement to reduce strain during prolonged tasks.")
        elif assessment == "High Risk":
            lines.append("Immediate ergonomic intervention is recommended to address "
                         "high-risk posture patterns observed during the session.")

        return lines

    def generate(self) -> str:
        d = self._data
        rp = d["risk_percentages"]
        assessment = _assess_safety(d)
        rec = _recommendation_for(d.get("most_frequent_issue"))

        ts = d.get("session_timestamp", "unknown")
        try:
            date_str = datetime.strptime(ts, "%Y%m%d_%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            date_str = str(ts)

        duration = _format_duration(d.get("session_duration_seconds", 0.0))

        lines: list[str] = []
        lines.append("# Session Safety Report")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        lines.append("## Executive Summary")
        lines.append("")
        lines.extend(self._generate_executive_summary())
        lines.append("")
        lines.append("## A. Session Information")
        lines.append("")
        lines.append(f"- **Date:** {date_str}")
        lines.append(f"- **Duration:** {duration}")
        lines.append(f"- **Total Frames:** {d.get('total_frames', 0)}")
        lines.append("")
        lines.append("## B. Risk Summary")
        lines.append("")
        lines.append(f"- **LOW Risk:** {rp.get('LOW', 0.0):.1f}%")
        lines.append(f"- **MEDIUM Risk:** {rp.get('MEDIUM', 0.0):.1f}%")
        lines.append(f"- **HIGH Risk:** {rp.get('HIGH', 0.0):.1f}%")
        lines.append("")
        lines.append("## C. Issue Analysis")
        lines.append("")
        mf = d.get("most_frequent_issue")
        lines.append(f"- **Most Frequent Issue:** {mf or 'None detected'}")
        lines.append(f"- **Highest Risk Event:** {d.get('highest_risk_level', 'LOW')}")
        ht = d.get("highest_risk_timestamp")
        lines.append(f"- **Timestamp:** {ht or 'N/A'}")
        lines.append("")
        lines.append("## D. Ergonomic Metrics")
        lines.append("")
        lines.append(f"- **Average Neck Flexion:** {d.get('avg_neck_flexion', 0.0):.1f} deg")
        lines.append(f"- **Average Trunk Flexion:** {d.get('avg_trunk_flexion', 0.0):.1f} deg")
        lines.append(f"- **Average Shoulder Symmetry:** {d.get('avg_shoulder_symmetry', 0.0):.1f} %")
        lines.append(f"- **Average Knee Angle:** {d.get('avg_knee_angle', 0.0):.1f} deg")
        lines.append("")
        lines.append("## E. Safety Assessment")
        lines.append("")
        lines.append(f"**{assessment}**")
        lines.append("")
        lines.append("## F. Recommendations")
        lines.append("")
        if rec:
            worker_action, supervisor_action = rec
            lines.append(f"- **Worker:** {worker_action}")
            lines.append(f"- **Supervisor:** {supervisor_action}")
        else:
            lines.append("- No specific recommendations available.")
        lines.append("")

        return "\n".join(_sanitize_text(l) for l in lines)

    def save(self, output_path: str | Path) -> str:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        content = self.generate()
        path.write_text(content)
        return str(path)
