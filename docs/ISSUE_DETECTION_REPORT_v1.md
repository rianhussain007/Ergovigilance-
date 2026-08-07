# Issue Detection Report — v1

---

## Overview

This report documents the posture issue detection system built on top of the existing feature extraction pipeline. The system translates raw biomechanical features into human-readable, actionable posture issues — bridging the gap between numerical risk scores and explainable ergonomic feedback.

---

## Architecture

```
features dict (7 values)
        │
        ▼
detect_issues(features)
        │
        ▼
List[PostureIssue]         ← each issue has:
  ├── issue_id               name, severity, description,
  ├── name                   feature_value, thresholds,
  ├── severity                recommendation, details
  ├── description
  ├── recommendation
  └── details
```

### Integration Point

The issue detection layer sits directly above the existing `extract_features_from_keypoints()` pipeline and below the `risk_from_features()` / `risk_breakdown()` functions:

```
keypoints → extract_features → detect_issues() → formatted output
                                    │
                                    ▼
                            risk_from_features()
```

No existing feature extraction logic was modified. The issue detection module only reads the output of `extract_features_from_keypoints()`.

---

## Defined Posture Issues

| # | Issue ID | Feature Source | MEDIUM Threshold | HIGH Threshold | Inverted |
|---|---|---|---|---|---|
| 1 | `excessive_neck_flexion` | `neck_flexion` | > 10° | > 30° | No |
| 2 | `excessive_trunk_flexion` | `trunk_flexion` | > 20° | > 60° | No |
| 3 | `elevated_left_shoulder` | `left_shoulder_elev` | > 30° | > 60° | No |
| 4 | `elevated_right_shoulder` | `right_shoulder_elev` | > 30° | > 60° | No |
| 5 | `shoulder_imbalance` | `shoulder_symmetry` | > 5% | > 15% | No |
| 6 | `alignment_deviation` | `alignment_deviation` | > 5% | > 15% | No |
| 7 | `knee_instability` | `knee_angle` | < 150° | < 100° | Yes |

### Inverted Thresholds

`knee_instability` uses inverted logic: a lower feature value means higher risk (overly bent knees), whereas all other issues follow the pattern where a higher feature value means higher risk.

---

## `PostureIssue` Dataclass

```python
@dataclass(frozen=True)
class PostureIssue:
    issue_id: str         # unique key, e.g. "excessive_neck_flexion"
    name: str             # human-readable, e.g. "Excessive Neck Flexion"
    severity: str         # "LOW" | "MEDIUM" | "HIGH"
    feature_name: str     # maps to FEATURE_COLUMNS key
    feature_value: float  # current measured value
    thresholds: tuple     # (medium_threshold, high_threshold)
    description: str      # explainable problem statement
    recommendation: str   # actionable next step
    details: str          # measured value + target explanation
```

### Example

```python
PostureIssue(
    issue_id="excessive_neck_flexion",
    name="Excessive Neck Flexion",
    severity="HIGH",
    feature_name="neck_flexion",
    feature_value=35.0,
    thresholds=(10.0, 30.0),
    description="Your head is positioned too far forward, causing strain on the cervical spine.",
    recommendation="Tuck your chin slightly back and align your ears above your shoulders.",
    details="Measured value: 35.0. Threshold for MEDIUM: > 10, HIGH: > 30.",
)
```

---

## API

### `detect_issues(features) -> List[PostureIssue]`

- **Input**: A dict of 7 feature values (same keys as `FEATURE_COLUMNS`)
- **Output**: A list of `PostureIssue` instances, sorted by severity (HIGH first) then alphabetically
- **Filter**: Only returns issues with severity MEDIUM or HIGH. If no issues are detected, returns an empty list.

### `format_issues_text(issues, include_recommendations=True) -> str`

- **Input**: List of `PostureIssue`
- **Output**: Formatted text with icons, descriptions, and recommendations

---

## Test Results

| Test Case | Expected Issues | Detected Issues | Result |
|---|---|---|---|
| Normal Posture | (none) | (none) | ✅ PASS |
| Excessive Neck Flexion | neck_flexion | neck_flexion | ✅ PASS |
| Excessive Trunk Flexion | trunk_flexion, alignment_deviation | trunk_flexion, alignment_deviation | ✅ PASS |
| Shoulder Imbalance | left_shoulder, shoulder_symmetry | left_shoulder, shoulder_symmetry | ✅ PASS |
| Multiple Risks (5 issues) | 6 issues | 6 issues | ✅ PASS |
| All Issues (7 issues) | 7 issues | 7 issues | ✅ PASS |

**Overall: 6/6 tests passed**

### Synthetic Test Data

Each test case uses a synthetic feature vector designed to simulate a specific posture condition:

| Condition | `neck_flexion` | `trunk_flexion` | `L shoulder` | `R shoulder` | `symmetry` | `alignment` | `knee` |
|---|---|---|---|---|---|---|---|
| Normal | 5.0 | 8.0 | 12.0 | 14.0 | 2.0 | 3.0 | 165.0 |
| Neck Flexion | **35.0** | 10.0 | 15.0 | 16.0 | 2.5 | 4.0 | 160.0 |
| Trunk Flexion | 8.0 | **45.0** | 14.0 | 13.0 | 1.8 | **6.0** | 155.0 |
| Shoulder Imbalance | 6.0 | 12.0 | **35.0** | 12.0 | **18.0** | 3.5 | 162.0 |
| Multiple Risks | **32.0** | 15.0 | **55.0** | **50.0** | **12.0** | **8.0** | **140.0** |
| All Issues | **35.0** | **65.0** | **62.0** | **58.0** | **16.0** | **18.0** | **85.0** |

Bold values indicate feature values that exceed MEDIUM or HIGH thresholds.

---

## Screenshots

Generated annotated screenshots for each test case are saved at:

```
outputs/issue_detection_tests/
├── normal_posture.png
├── excessive_neck_flexion.png
├── excessive_trunk_flexion.png
├── shoulder_imbalance.png
├── multiple_risks_neck_and_shoulder_and_imbalance.png
├── knee_instability_and_all_issues.png
└── test_report.txt
```

Each screenshot shows:
- Posture name and overall risk level
- All 7 feature values
- Detected issues with severity, description, and recommendation

---

## Integration: `live_demo.py`

The `live_demo.py` script now includes a dedicated **ISSUES DETECTED** section in the real-time dashboard panel:

```
┌─────────────────────────────────────────┐
│  POSTURE ANALYSIS                       │
│  2026-06-21 14:30:00                    │
│─────────────────────────────────────────│
│  ┌─────────────────────────────────┐    │
│  │      HIGH RISK                  │    │
│  └─────────────────────────────────┘    │
│─────────────────────────────────────────│
│  FEATURES                               │
│  Neck Flexion    ████████░░ 35.0°       │
│  Trunk Flexion   ██░░░░░░░░ 10.0°       │
│  ...                                    │
│─────────────────────────────────────────│
│  ISSUES DETECTED                        │
│  ! Excessive Neck Flexion (HIGH)        │
│  ~ Elevated Left Shoulder (MEDIUM)      │
│─────────────────────────────────────────│
│  SESSION STATS                          │
│  Avg Neck Flexion: 12.3 deg             │
│─────────────────────────────────────────│
│  RISK HISTORY (30s)                     │
│  ┌─────────────────────────────────┐    │
│  │     ~graph~                     │    │
│  └─────────────────────────────────┘    │
│  FPS: 30  Screenshots: 0               │
│  Q: Quit | S: Screenshot               │
└─────────────────────────────────────────┘
```

### Changes to `live_demo.py`

1. Added import of `detect_issues` and `PostureIssue` from `backend.services.issue_detection`
2. Replaced the "PRIMARY CONTRIBUTORS" section with a dedicated "ISSUES DETECTED" section
3. Each issue is shown with:
   - `!` icon for HIGH severity, `~` for MEDIUM
   - Issue name (truncated to 24 chars if needed)
   - Color-coded by severity (red = HIGH, orange = MEDIUM)
4. Displays up to 4 issues at a time (avoids panel overflow)

---

## Files Created / Modified

| File | Action | Description |
|---|---|---|
| `backend/services/issue_detection.py` | **Created** | Core issue detection module with `PostureIssue` dataclass and `detect_issues()` |
| `scripts/live_demo.py` | **Modified** | Added ISSUES DETECTED dashboard section |
| `scripts/test_issue_detection.py` | **Created** | Test script with 6 test cases and annotated screenshot generation |
| `outputs/issue_detection_tests/` | **Created** | Test outputs (report text + 6 screenshots) |
| `docs/ISSUE_DETECTION_REPORT_v1.md` | **Created** | This report |

---

## Future Improvements

1. **Real-time issue accumulation**: Track issue frequency over a session and report persistent issues
2. **Composite issues**: Detect combined patterns (e.g., "Forward Head + Rounded Shoulders" as a "Computer User Syndrome" composite)
3. **Severity scoring**: Add a numeric severity score (0-100) per issue for finer granularity
4. **Cross-session trending**: Track which issues recur across multiple sessions per worker
5. **Issue-specific PDF reports**: Generate targeted exercise sheets per detected issue
