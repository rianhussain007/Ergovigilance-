# Session Analytics Module — v1

## Overview

`SessionAnalytics` is a lightweight, real-time analytics tracker that records session-level posture metrics. It runs alongside the main live demo loop and accumulates frame-by-frame data without modifying any existing inference, detection, or recommendation pipelines.

## Module

**File:** `backend/services/session_analytics.py`

### Class: `SessionAnalytics`

#### Constructor

```python
analytics = SessionAnalytics()
```

Initialises all counters and records the session start time via `time.monotonic()`.

#### Methods

| Method | Description |
|---|---|
| `update(features, risk_level, issues, person_detected, frame_timestamp=None)` | Called every frame. Accumulates data only when `person_detected` is `True`. |
| `get_summary()` | Returns a dictionary with all computed session metrics. |
| `reset()` | Resets all counters and start time as if a new session began. |

#### `update()` Parameters

| Parameter | Type | Source |
|---|---|---|
| `features` | `Dict[str, float]` | Raw feature values from `extract_features_from_keypoints()` |
| `risk_level` | `str` | One of `"LOW"`, `"MEDIUM"`, `"HIGH"` from `risk_from_features()` |
| `issues` | `List[Dict]` | Output of `detect_posture_issues(features)` |
| `person_detected` | `bool` | Whether MediaPipe found a pose in the frame |
| `frame_timestamp` | `str \| None` | Human-readable timestamp (e.g. `"2026-06-22 14:32:05"`) |

#### `get_summary()` Return Value

```python
{
    "session_duration_seconds": float,   # elapsed wall-clock seconds
    "total_frames": int,                 # frames with person detected
    "risk_percentages": {                # % of total frames in each band
        "LOW": float,
        "MEDIUM": float,
        "HIGH": float,
    },
    "most_frequent_issue": str | None,   # issue name that appeared most
    "most_frequent_issue_count": int,
    "highest_risk_level": str,           # highest risk level observed
    "highest_risk_timestamp": str | None, # when highest risk was first seen
    "avg_neck_flexion": float,
    "avg_trunk_flexion": float,
    "avg_shoulder_symmetry": float,
    "avg_knee_angle": float,
}
```

If no frames have been recorded, all numeric values are `0.0` and `most_frequent_issue` / `highest_risk_timestamp` are `None`.

## Integration

Integration in `scripts/live_demo.py` requires three changes:

1. **Import** — add `from backend.services.session_analytics import SessionAnalytics`.
2. **Instantiate** — create `analytics = SessionAnalytics()` after the camera setup block.
3. **Update** — call `analytics.update(features, risk_level, issues, person_detected, timestamp_str)` each frame.

The session summary is printed to the terminal when the user presses `Q` to quit.

## Design Decisions

- **Running sums** are used for feature averages instead of storing all values, giving O(1) memory regardless of session length.
- **`person_detected` guard** ensures only valid frames contribute to metrics — frames with no person present are skipped.
- **Risk level string normalization** uses `.upper()` for robustness.
- **Highest risk** is tracked by ordinal comparison (`LOW=0, MEDIUM=1, HIGH=2`), recording the first time a new highest level is reached.
- **No modifications** are made to `features.py`, `issue_detection.py`, or `recommendation_engine.py`.

## Test File

**File:** `scripts/test_session_analytics.py`

Run with:

```
python scripts/test_session_analytics.py
```
