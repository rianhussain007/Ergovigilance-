"""Cross-session risk trend analysis.

Reuses the early-half vs late-half mean comparison algorithm from the
archived _archive/services/trend_analysis.py — the core logic is sound.
Differences from the archived version:
  - Accepts a pre-filtered list of session dicts (role filtering done by caller).
  - Uses .get() with sensible defaults throughout for schema-variant safety.
  - Outputs structured JSON (not markdown). No generate_report() / save_report().
  - No external imports from archived modules.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List

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

TREND_ORDER: Dict[str, int] = {"Improving": 1, "Stable": 0, "Deteriorating": -1}
_TREND_REVERSE: Dict[int, str] = {v: k for k, v in TREND_ORDER.items()}


def _compute_trend(values: List[float]) -> str:
    """Early-half vs late-half mean comparison with 5% threshold.

    Same algorithm as the archived version — reused, not reinvented.
    """
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


def _compute_trend_for_metric(values: List[float], metric: str) -> str:
    """Compute trend, inverting for metrics where increasing = worse."""
    raw = _compute_trend(values)
    if metric in _INVERTED_METRICS:
        return _TREND_REVERSE.get(-TREND_ORDER[raw], "Stable")
    return raw


def analyze_risk_trend(sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze risk trends across a list of session dicts.

    Args:
        sessions: Pre-filtered list of session JSON dicts (role-filtered by caller).

    Returns:
        Structured JSON dict suitable for the /api/reports/risk-trend endpoint.
    """
    if not sessions:
        return {"total_sessions": 0, "status": "No sessions found"}

    n = len(sessions)

    # --- risk_percentages ---
    rp_low = [s.get("risk_percentages", {}).get("LOW", 0.0) for s in sessions]
    rp_med = [s.get("risk_percentages", {}).get("MEDIUM", 0.0) for s in sessions]
    rp_high = [s.get("risk_percentages", {}).get("HIGH", 0.0) for s in sessions]

    avg_low = round(sum(rp_low) / n, 1)
    avg_med = round(sum(rp_med) / n, 1)
    avg_high = round(sum(rp_high) / n, 1)

    # --- most frequent issue ---
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

    # --- per-metric averages and trends ---
    metric_totals: Dict[str, float] = {m: 0.0 for m in METRIC_NAMES}
    metric_values: Dict[str, List[float]] = {m: [] for m in METRIC_NAMES}
    for s in sessions:
        for m in METRIC_NAMES:
            val = s.get(m, 0.0)
            metric_totals[m] += val
            metric_values[m].append(val)

    metric_averages = {m: round(metric_totals[m] / n, 2) for m in METRIC_NAMES}

    metric_trends: Dict[str, str] = {}
    for m in METRIC_NAMES:
        metric_trends[m] = _compute_trend_for_metric(metric_values[m], m)

    # --- overall composite trend ---
    trend_scores = [TREND_ORDER[metric_trends[m]] for m in METRIC_NAMES]
    overall_score = sum(trend_scores) / len(trend_scores) if trend_scores else 0.0

    if overall_score >= 0.25:
        overall_trend = "Improving"
    elif overall_score <= -0.25:
        overall_trend = "Deteriorating"
    else:
        overall_trend = "Stable"

    # --- date range ---
    timestamps = [s.get("session_timestamp", "") for s in sessions if s.get("session_timestamp")]
    earliest = min(timestamps) if timestamps else "unknown"
    latest = max(timestamps) if timestamps else "unknown"

    # --- build structured output ---
    metrics = []
    for m in METRIC_NAMES:
        metrics.append({
            "name": m,
            "label": METRIC_LABELS[m],
            "unit": METRIC_UNITS[m],
            "average": metric_averages[m],
            "trend": metric_trends[m],
        })

    return {
        "total_sessions": n,
        "earliest_session": earliest,
        "latest_session": latest,
        "risk_distribution": {
            "low_pct": avg_low,
            "medium_pct": avg_med,
            "high_pct": avg_high,
        },
        "most_common_issue": most_common_issue_name,
        "most_common_issue_count": most_common_issue_count,
        "most_common_highest_risk": most_common_highest_name,
        "metrics": metrics,
        "overall_trend": overall_trend,
    }
