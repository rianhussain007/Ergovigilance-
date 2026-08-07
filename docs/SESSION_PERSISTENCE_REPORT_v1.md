# Session Persistence Module — v1

## Overview

Lightweight persistence layer for `SessionAnalytics` summaries. Each session is saved as a JSON file and appended to a CSV index when the user presses `Q` to quit. No changes were made to the `SessionAnalytics` class itself.

## File Locations

| Artifact | Path |
|---|---|
| Session JSON files | `outputs/sessions/session_YYYYMMDD_HHMMSS.json` |
| CSV index | `outputs/sessions/session_index.csv` |
| Helper function | `backend/services/session_analytics.py` → `save_session_summary()` |

## JSON Schema

Each JSON file contains:

```json
{
  "session_timestamp": "20260622_143005",
  "session_duration_seconds": 120.5,
  "total_frames": 4500,
  "risk_percentages": { "LOW": 60.0, "MEDIUM": 30.0, "HIGH": 10.0 },
  "most_frequent_issue": "Shoulder Imbalance",
  "most_frequent_issue_count": 180,
  "highest_risk_level": "HIGH",
  "highest_risk_timestamp": "14:45:12",
  "avg_neck_flexion": 12.3,
  "avg_trunk_flexion": 18.7,
  "avg_shoulder_symmetry": 4.2,
  "avg_knee_angle": 155.0
}
```

## CSV Schema

| Column | Description |
|---|---|
| `timestamp` | Session identifier (same as JSON filename stem) |
| `duration` | Wall-clock duration in seconds |
| `high_pct` | Percentage of frames at HIGH risk |
| `medium_pct` | Percentage of frames at MEDIUM risk |
| `low_pct` | Percentage of frames at LOW risk |
| `most_frequent_issue` | Most common posture issue (empty string if none) |
| `highest_risk` | Highest risk level observed during session |

A header row is written only when the file is first created. Each subsequent session appends one row without repeating the header.

## API

```python
from backend.services.session_analytics import save_session_summary

saved_path = save_session_summary(summary, "outputs/sessions", "20260622_143005")
```

| Parameter | Type | Description |
|---|---|---|
| `summary` | `Dict` | Output of `SessionAnalytics.get_summary()` |
| `sessions_dir` | `str \| Path` | Directory for JSON + CSV output |
| `session_timestamp` | `str \| None` | Optional key; defaults to `now().strftime(...)` |

Returns `str` path to saved JSON file, or `None` if `total_frames == 0`.

## Integration

Single call added after `analytics.get_summary()` in `live_demo.py` line 691:

```python
saved_path = save_session_summary(summary, ROOT / "outputs" / "sessions")
```

No other code changed. Existing terminal output is preserved with an extra line showing the save path.

## Test File

**File:** `scripts/test_session_persistence.py`

```
python scripts/test_session_persistence.py
```

Verifies:
- JSON is written with correct fields
- Zero-frame sessions are skipped (returns `None`)
- CSV index is created with header on first write
- CSV rows are appended without re-header
- Null values are written as empty strings in CSV

## Future Use

The stored session files provide the data foundation for:
- **Safety Reporting** — aggregate risk percentages across shifts
- **Trend Analysis** — compare avg neck/trunk flexion week-over-week
- **Dashboard** — load historical sessions for review
