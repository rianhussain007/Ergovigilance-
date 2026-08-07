from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple

from backend.services.safety_reporting import _sanitize_text


METRIC_NAMES = [
    "avg_neck_flexion",
    "avg_trunk_flexion",
    "avg_shoulder_symmetry",
    "avg_knee_angle",
]

METRIC_LABELS = {
    "avg_neck_flexion": "Neck Flexion",
    "avg_trunk_flexion": "Trunk Flexion",
    "avg_shoulder_symmetry": "Shoulder Symmetry",
    "avg_knee_angle": "Knee Angle",
}

METRIC_UNITS = {
    "avg_neck_flexion": "deg",
    "avg_trunk_flexion": "deg",
    "avg_shoulder_symmetry": "%",
    "avg_knee_angle": "deg",
}

_INVERTED_METRICS = {"avg_neck_flexion", "avg_trunk_flexion", "avg_shoulder_symmetry"}

TREND_ORDER = {"Improving": 1, "Stable": 0, "Deteriorating": -1}
_TREND_REVERSE = {v: k for k, v in TREND_ORDER.items()}


def _compute_trend(values: List[float]) -> str:
    if len(values) < 4:
        return "Stable"

    mid = len(values) // 2
    early = values[:mid]
    late = values[mid:]

    early_avg = sum(early) / len(early)
    late_avg = sum(late) / len(late)

    diff = late_avg - early_avg
    threshold = 0.05 * abs(early_avg) if early_avg != 0 else 0.01

    if abs(diff) <= threshold:
        return "Stable"
    if diff > 0:
        return "Improving"
    return "Deteriorating"


class TrendAnalysis:
    def __init__(self, sessions_dir: str | Path) -> None:
        self._sessions_dir = Path(sessions_dir)
        self._sessions: List[Dict] = []
        self._load_sessions()

    def _load_sessions(self) -> None:
        pattern = "session_*.json"
        paths = sorted(self._sessions_dir.glob(pattern))
        for p in paths:
            with open(p) as f:
                data = json.load(f)
            self._sessions.append(data)

    @property
    def session_count(self) -> int:
        return len(self._sessions)

    def analyze(self) -> Dict:
        if not self._sessions:
            return {"status": "No sessions found"}

        sessions = self._sessions
        n = len(sessions)

        rp_low = [s["risk_percentages"]["LOW"] for s in sessions]
        rp_med = [s["risk_percentages"]["MEDIUM"] for s in sessions]
        rp_high = [s["risk_percentages"]["HIGH"] for s in sessions]

        avg_low = round(sum(rp_low) / n, 1)
        avg_med = round(sum(rp_med) / n, 1)
        avg_high = round(sum(rp_high) / n, 1)

        all_issues: List[str] = []
        all_highest: List[str] = []
        for s in sessions:
            issue = s.get("most_frequent_issue")
            if issue:
                all_issues.append(issue)
            hr = s.get("highest_risk_level", "LOW")
            all_highest.append(hr)

        most_common_issue = Counter(all_issues).most_common(1)
        most_common_issue_name = most_common_issue[0][0] if most_common_issue else None
        most_common_issue_count = most_common_issue[0][1] if most_common_issue else 0

        most_common_highest = Counter(all_highest).most_common(1)
        most_common_highest_name = most_common_highest[0][0] if most_common_highest else "LOW"

        metric_totals: Dict[str, float] = {m: 0.0 for m in METRIC_NAMES}
        metric_values: Dict[str, List[float]] = {m: [] for m in METRIC_NAMES}
        for s in sessions:
            for m in METRIC_NAMES:
                val = s.get(m, 0.0)
                metric_totals[m] += val
                metric_values[m].append(val)

        metric_averages = {
            m: round(metric_totals[m] / n, 2) for m in METRIC_NAMES
        }

        metric_trends: Dict[str, str] = {}
        for m in METRIC_NAMES:
            raw_trend = _compute_trend(metric_values[m])
            if m in _INVERTED_METRICS:
                metric_trends[m] = _TREND_REVERSE.get(-TREND_ORDER[raw_trend], "Stable")
            else:
                metric_trends[m] = raw_trend

        trend_scores = [TREND_ORDER[metric_trends[m]] for m in METRIC_NAMES]
        overall_score = sum(trend_scores) / len(trend_scores) if trend_scores else 0.0

        if overall_score >= 0.25:
            overall_trend = "Improving"
        elif overall_score <= -0.25:
            overall_trend = "Deteriorating"
        else:
            overall_trend = "Stable"

        earliest = sessions[0].get("session_timestamp", "unknown")
        latest = sessions[-1].get("session_timestamp", "unknown")

        return {
            "total_sessions": n,
            "earliest_session": earliest,
            "latest_session": latest,
            "average_low_pct": avg_low,
            "average_medium_pct": avg_med,
            "average_high_pct": avg_high,
            "most_common_issue": most_common_issue_name,
            "most_common_issue_count": most_common_issue_count,
            "most_common_highest_risk": most_common_highest_name,
            "average_neck_flexion": metric_averages["avg_neck_flexion"],
            "average_trunk_flexion": metric_averages["avg_trunk_flexion"],
            "average_shoulder_symmetry": metric_averages["avg_shoulder_symmetry"],
            "average_knee_angle": metric_averages["avg_knee_angle"],
            "trend_neck_flexion": metric_trends["avg_neck_flexion"],
            "trend_trunk_flexion": metric_trends["avg_trunk_flexion"],
            "trend_shoulder_symmetry": metric_trends["avg_shoulder_symmetry"],
            "trend_knee_angle": metric_trends["avg_knee_angle"],
            "overall_ergonomic_trend": overall_trend,
        }

    def generate_report(self) -> str:
        result = self.analyze()
        if "status" in result:
            return f"# Trend Report\n\n{result['status']}"

        d = result
        lines: List[str] = []
        lines.append("# Ergonomic Trend Report")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## Executive Summary")
        lines.append("")
        trend = d["overall_ergonomic_trend"]
        lines.append(
            f"Analysis of {d['total_sessions']} session(s) from "
            f"{d['earliest_session']} to {d['latest_session']} "
            f"indicates an overall {trend.lower()} trend."
        )
        lines.append(
            f"Average session risk distribution: "
            f"{d['average_low_pct']}% LOW, {d['average_medium_pct']}% MEDIUM, "
            f"{d['average_high_pct']}% HIGH."
        )
        if d["most_common_issue"]:
            lines.append(
                f"The most frequently observed ergonomic issue across sessions "
                f"was {d['most_common_issue']}."
            )
        lines.append("")
        lines.append("## Sessions Analysed")
        lines.append("")
        lines.append(f"- **Total Sessions:** {d['total_sessions']}")
        lines.append(f"- **Date Range:** {d['earliest_session']} to {d['latest_session']}")
        lines.append("")
        lines.append("## Trend Analysis")
        lines.append("")
        for m in METRIC_NAMES:
            label = METRIC_LABELS[m]
            unit = METRIC_UNITS[m]
            avg = d[f"average_{m.split('_', 1)[1]}"] if m.startswith("avg_") else d.get(m, 0)
            trend_key = f"trend_{m.split('_', 1)[1]}" if m.startswith("avg_") else m
            t = d.get(trend_key, "Stable")
            icon = {"Improving": "UP", "Stable": "--", "Deteriorating": "DN"}.get(t, "--")
            lines.append(f"- **{label}:** {avg} {unit} ({icon} {t})")
        lines.append("")
        lines.append(f"- **Overall Ergonomic Trend:** {trend}")
        lines.append("")
        lines.append("## Common Issues")
        lines.append("")
        if d["most_common_issue"]:
            lines.append(f"- **Most Common Issue:** {d['most_common_issue']} "
                         f"(appeared in {d['most_common_issue_count']} session(s))")
        else:
            lines.append("- No issues recorded across sessions.")
        lines.append(f"- **Most Common Highest-Risk Event:** {d['most_common_highest_risk']}")
        lines.append("")
        lines.append("## Risk Distribution")
        lines.append("")
        lines.append(f"- **Average LOW Risk:** {d['average_low_pct']:.1f}%")
        lines.append(f"- **Average MEDIUM Risk:** {d['average_medium_pct']:.1f}%")
        lines.append(f"- **Average HIGH Risk:** {d['average_high_pct']:.1f}%")
        lines.append("")
        lines.append("## Long-Term Recommendations")
        lines.append("")
        if trend == "Deteriorating":
            if d.get("most_common_issue"):
                lines.append(
                    f"Immediate ergonomic intervention is recommended. "
                    f"The persistent issue of {d['most_common_issue']} requires "
                    f"workstation assessment and targeted corrective actions."
                )
            else:
                lines.append(
                    "Immediate ergonomic intervention is recommended. "
                    "Workstation adjustments and posture training should be prioritised."
                )
        elif trend == "Improving":
            lines.append(
                "Current ergonomic practices are yielding positive results. "
                "Continue monitoring and maintain existing interventions."
            )
        else:
            lines.append(
                "Ergonomic conditions are stable. "
                "Regular monitoring should continue to detect any emerging patterns."
            )
        lines.append(
            "Schedule follow-up ergonomic assessments at regular intervals "
            "(e.g. weekly) to track the effectiveness of interventions."
        )
        lines.append("")
        lines.append("## Conclusion")
        lines.append("")
        lines.append(
            f"Based on {d['total_sessions']} sessions spanning "
            f"{d['earliest_session']} to {d['latest_session']}, "
            f"the overall ergonomic trend is classified as **{trend}**. "
        )
        if d.get("most_common_issue"):
            lines.append(
                f"{d['most_common_issue']} remains the primary area of concern "
                f"and should be the focus of corrective measures."
            )
        lines.append("")

        raw = "\n".join(lines)
        return _sanitize_text(raw)

    def save_report(self, output_path: str | Path) -> str:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        content = self.generate_report()
        path.write_text(content)
        return str(path)
