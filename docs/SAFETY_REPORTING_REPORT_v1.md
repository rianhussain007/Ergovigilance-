# Safety Reporting Module — v1

## Overview

`SafetyReport` generates a human-readable markdown safety report from a saved session JSON file. It reads the session summary produced by `SessionAnalytics` and produces a structured report with risk assessment, ergonomic metrics, and actionable recommendations.

## Module

**File:** `backend/services/safety_reporting.py`

### Class: `SafetyReport`

#### Constructor

```python
from backend.services.safety_reporting import SafetyReport

# From a dict (e.g. loaded in-memory)
report = SafetyReport(session_data)

# From a saved JSON file
report = SafetyReport.from_json("outputs/sessions/session_20260622_143005.json")
```

#### Methods

| Method | Description |
|---|---|
| `generate()` | Returns the report as a markdown string. |
| `save(output_path)` | Writes the report to a file. Returns the path. |
| `from_json(json_path)` | Class method — loads session data from a JSON file and returns a `SafetyReport` instance. |

### Report Sections

| Section | Content |
|---|---|
| **A. Session Information** | Date, duration (human-readable), total frames |
| **B. Risk Summary** | LOW / MEDIUM / HIGH percentage breakdown |
| **C. Issue Analysis** | Most frequent issue, highest risk event, timestamp |
| **D. Ergonomic Metrics** | Average neck/trunk flexion, shoulder symmetry, knee angle |
| **E. Safety Assessment** | One of: Excellent, Good, Moderate Risk, High Risk |
| **F. Recommendations** | First worker action + first supervisor action from the recommendation engine |

### Safety Assessment Logic

| Condition | Rating |
|---|---|
| HIGH >= 20% or MEDIUM >= 50% | **High Risk** |
| HIGH >= 10% or MEDIUM >= 30% | **Moderate Risk** |
| HIGH == 0 and MEDIUM < 10% | **Excellent** |
| Otherwise | **Good** |

### Helper Functions

| Function | Purpose |
|---|---|
| `_assess_safety(summary)` | Returns "Excellent", "Good", "Moderate Risk", or "High Risk" |
| `_format_duration(seconds)` | Converts seconds to `Xh Ym Zs` format |
| `_recommendation_for(issue_name)` | Looks up the first worker + supervisor action from `recommendation_engine._RECOMMENDATIONS` |

## CLI Tool

**File:** `scripts/generate_safety_report.py`

```bash
# From a session JSON file
python scripts/generate_safety_report.py outputs/sessions/session_20260622_143005.json

# Custom output path
python scripts/generate_safety_report.py outputs/sessions/session_20260622_143005.json -o my_report.md
```

Default output: `reports/session_report.md`

## Integration

No changes to `live_demo.py`. The module reads from **pre-saved** session JSON files in `outputs/sessions/`. This preserves the separation of concerns:

- `SessionAnalytics` collects frame-by-frame data
- `save_session_summary()` persists to JSON + CSV
- `SafetyReport` reads saved JSON to produce a report

## Output File

Default output: `reports/session_report.md`

## Test File

**File:** `scripts/test_safety_reporting.py`

```bash
python scripts/test_safety_reporting.py
```

Verifies:
- All 6 report sections present
- Date/duration/metrics rendered correctly
- Safety assessment logic (all thresholds)
- Duration formatting
- Recommendation lookup (known, unknown, None)
- Edge cases (no issues, null values)
- File save and `from_json` round-trip
