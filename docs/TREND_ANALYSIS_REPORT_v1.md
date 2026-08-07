# Trend Analysis Module — v1

## Overview

`TrendAnalysis` loads all saved session JSON files from `outputs/sessions/`, computes aggregate metrics, and identifies long-term ergonomic trends across multiple sessions. It transforms the system from reactive single-session monitoring into proactive, longitudinal ergonomic intelligence.

## Module

**File:** `backend/services/trend_analysis.py`

### Class: `TrendAnalysis`

#### Constructor

```python
from backend.services.trend_analysis import TrendAnalysis

ta = TrendAnalysis("outputs/sessions")
```

Scans the given directory for `session_*.json` files, loads them, and sorts chronologically by `session_timestamp`.

#### Methods

| Method | Description |
|---|---|
| `analyze()` | Returns a dict with all computed metrics, trends, and aggregates. |
| `generate_report()` | Returns the full trend report as a markdown string. |
| `save_report(output_path)` | Writes the report to a file. Returns the path. |

#### `analyze()` Return Value

```python
{
    "total_sessions": int,
    "earliest_session": str,
    "latest_session": str,
    "average_low_pct": float,
    "average_medium_pct": float,
    "average_high_pct": float,
    "most_common_issue": str | None,
    "most_common_issue_count": int,
    "most_common_highest_risk": str,
    "average_neck_flexion": float,
    "average_trunk_flexion": float,
    "average_shoulder_symmetry": float,
    "average_knee_angle": float,
    "trend_neck_flexion": str,        # Improving / Stable / Deteriorating
    "trend_trunk_flexion": str,
    "trend_shoulder_symmetry": str,
    "trend_knee_angle": str,
    "overall_ergonomic_trend": str,   # Improving / Stable / Deteriorating
}
```

## Trend Classification

### Per-Metric Trend

Sessions are split into first-half and second-half groups (chronologically). If fewer than 4 sessions exist, the trend is `Stable`.

| Metric | Direction | Better |
|---|---|---|
| Neck Flexion | Lower | Yes (inverted) |
| Trunk Flexion | Lower | Yes (inverted) |
| Shoulder Symmetry | Lower | Yes (inverted) |
| Knee Angle | Higher | Yes (non-inverted) |

The raw direction (late half vs early half) is computed, then flipped for inverted metrics.

### Overall Ergonomic Trend

Each metric trend is scored: Improving=+1, Stable=0, Deteriorating=-1. The average across all 4 metrics determines the overall trend:

| Average Score | Overall Trend |
|---|---|
| >= 0.25 | Improving |
| <= -0.25 | Deteriorating |
| otherwise | Stable |

## Report Sections

| Section | Content |
|---|---|
| **Executive Summary** | Sessions analysed, risk distribution, most common issue |
| **Sessions Analysed** | Total count, date range |
| **Trend Analysis** | Per-metric trend with direction arrows |
| **Common Issues** | Most frequent issue and highest-risk event |
| **Risk Distribution** | Average LOW / MEDIUM / HIGH percentages |
| **Long-Term Recommendations** | Trend-specific guidance |
| **Conclusion** | Final assessment and recommended actions |

## CLI Tool

**File:** `scripts/generate_trend_report.py`

```bash
# Default (reads outputs/sessions, writes reports/trend_report.md)
python scripts/generate_trend_report.py

# Custom paths
python scripts/generate_trend_report.py --sessions-dir data/sessions -o my_trend.md
```

## Dependencies

| Module | Relationship |
|---|---|
| `safety_reporting` | Imports `_sanitize_text` for Unicode-safe output |
| `session_analytics` | Consumes saved JSON files (no direct import) |
| `recommendation_engine` | Not modified |

## Test File

**File:** `scripts/test_trend_analysis.py`

```bash
python scripts/test_trend_analysis.py
```

Verifies:
- Empty sessions directory handled correctly
- Single session with Stable trends
- Multi-session averages and percentages
- Most common issue tracking across sessions
- Most common highest risk level
- Improving / Deteriorating / Stable trend classification
- Correct inversion logic for all 4 metrics
- Earliest/latest timestamp sorting
- Report generation with all 7 sections
- File save round-trip
