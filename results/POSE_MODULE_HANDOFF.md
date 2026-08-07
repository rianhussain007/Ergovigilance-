# Pose Estimation Module — Handoff Document

**Project:** AI-Based Real-Time Posture & Movement Monitoring
**Module:** Pose Estimation (`backend/services/features.py`) + Context Intelligence (`backend/context/engine.py`)
**Status:** Ready for system integration
**Date:** 2026-07-20

---

## 1. Module Overview

The Pose Estimation module converts raw MediaPipe Pose Landmarker 33-keypoint output into 9 ergonomic features, classifies overall posture risk (LOW / MEDIUM / HIGH), and provides per-feature risk breakdowns. It operates on a single video frame at a time with no temporal state.

The **ContextIntelligenceEngine** adds temporal awareness (duration, fatigue, task modifiers) on top of per-frame features, producing a continuous 0-100 risk score and the authoritative risk level.

### Architecture

```
MediaPipe Pose Landmarker
        |
        v 33 landmarks x (x, y, z, visibility)
mediapipe_landmarks_to_keypoints()
        |
        v list[list[float]] shape (33, 4)
extract_features_from_keypoints()
        |
        v dict[str, float]  (9 features) + unavailable + approximate lists
            |
            +-- risk_from_features()  -->  "LOW" | "MEDIUM" | "HIGH"  (legacy, per-frame only)
            +-- risk_breakdown()      -->  dict[str, RiskBreakdown]
            |
            v
ContextIntelligenceEngine.evaluate()
        |
        v ContextSnapshot (continuous 0-100 final_risk, risk_level, fatigue, exposure)
            |
            +-- live_monitor.py  -->  state.risk_level (single source of truth)
            +-- AlertEngine      -->  alerts, escalation, recovery
            +-- HistoryEngine    -->  session statistics, trends
            +-- Timeline         -->  per-frame history entries
            +-- Video Analysis   -->  per-frame risk in video review
```

---

## 2. Current Features

| # | Feature | Formula | Thresholds | Dependencies |
|---|---------|---------|------------|-------------|
| 1 | `neck_flexion` | `\|180 deg - (ear, neck, hip)\|` | LOW <= 10 deg, MED 10-30 deg, HIGH > 30 deg | ears, shoulders, hips |
| 2 | `trunk_flexion` | `(neck, hip, vertical_up)` | LOW <= 20 deg, MED 20-60 deg, HIGH > 60 deg | shoulders, hips |
| 3 | `left_shoulder_elev` | `(elbow, shoulder, vertical_down)` | LOW <= 30 deg, MED 30-60 deg, HIGH > 60 deg | L shoulder, L elbow |
| 4 | `right_shoulder_elev` | `(elbow, shoulder, vertical_down)` | LOW <= 30 deg, MED 30-60 deg, HIGH > 60 deg | R shoulder, R elbow |
| 5 | `shoulder_symmetry` | `\|L_y - R_y\| / shoulder_width * 100` | LOW <= 5%, MED 5-15%, HIGH > 15% | L shoulder, R shoulder |
| 6 | `alignment_deviation` | `\|ear_x - hip_x\| / torso_len * 100` | LOW <= 20%, MED 20-50%, HIGH > 50% | ears, hips (or ears + shoulders for fallback) |
| 7 | `knee_angle` | `avg(L_hip->L_knee->L_ankle, R_hip->R_knee->R_ankle)` | HIGH < 100 deg, MED 100-150 deg, LOW >= 150 deg | hips, knees, ankles |
| 8 | `elbow_flexion_angle` | `avg(L_shoulder->L_elbow->L_wrist, R_shoulder->R_elbow->R_wrist)` | LOW >= 90 deg, MED 45-90 deg, HIGH < 45 deg | shoulders, elbows, wrists |
| 9 | `upper_arm_angle_from_vertical` | `avg(L_vert_up->L_shoulder->L_wrist, R_vert_up->R_shoulder->R_wrist)` | LOW <= 20 deg, MED 20-45 deg, HIGH > 45 deg | shoulders, wrists |

### Source Code

All feature logic is in `backend/services/features.py`:
- `extract_features_from_keypoints()` — computes all 9 features, returns 3-tuple `(features, unavailable, approximate)`
- `risk_from_features()` — per-frame risk classification (legacy, used internally by PoseEngine)
- `risk_breakdown()` — per-feature risk levels for UI display
- `mediapipe_landmarks_to_keypoints()` — MediaPipe landmark to keypoint conversion

Context intelligence is in `backend/context/engine.py`:
- `ContextIntelligenceEngine.evaluate()` — produces the authoritative `ContextSnapshot` with continuous risk score

---

## 3. Inputs

### Primary Input: `mediapipe_landmarks_to_keypoints(landmarks, width, height)`

- **`landmarks`**: Iterable of 33 MediaPipe `NormalizedLandmark` objects from `PoseLandmarkerResult.pose_landmarks[0]`
- **`width, height`**: Frame dimensions in pixels
- **Output**: `list[list[float]]` with shape `(33, 4)` — each entry is `[x_px, y_px, z, visibility]`

### Required MediaPipe Landmark Indices (MEDIAPIPE_33)

| Index | Landmark | Used By |
|-------|----------|---------|
| 0 | nose | — |
| 7 | left_ear | neck_flexion, alignment_deviation |
| 8 | right_ear | neck_flexion, alignment_deviation |
| 11 | left_shoulder | neck_flexion, trunk_flexion, shoulder_symmetry, L shoulder_elev, elbow_flexion, upper_arm_angle |
| 12 | right_shoulder | neck_flexion, trunk_flexion, shoulder_symmetry, R shoulder_elev, elbow_flexion, upper_arm_angle |
| 13 | left_elbow | L shoulder_elev, elbow_flexion_angle |
| 14 | right_elbow | R shoulder_elev, elbow_flexion_angle |
| 15 | left_wrist | elbow_flexion_angle, upper_arm_angle_from_vertical |
| 16 | right_wrist | elbow_flexion_angle, upper_arm_angle_from_vertical |
| 23 | left_hip | neck_flexion, trunk_flexion, alignment_deviation, knee_angle |
| 24 | right_hip | neck_flexion, trunk_flexion, alignment_deviation, knee_angle |
| 25 | left_knee | knee_angle |
| 26 | right_knee | knee_angle |
| 27 | left_ankle | knee_angle |
| 28 | right_ankle | knee_angle |

### Fallback Input: COCO 17-keypoint format

When fewer than 25 keypoints are provided, the module automatically uses `COCO_17` index mapping. This supports alternative pose detectors that output the COCO 17-keypoint skeleton.

---

## 4. Outputs

### `extract_features_from_keypoints()` -> `(dict, list, list)`

Returns a 3-tuple: `(features, unavailable_features, approximate_features)`

```python
features = {
    "neck_flexion": 12.3456,
    "trunk_flexion": 5.1234,
    "left_shoulder_elev": 15.6789,
    "right_shoulder_elev": 12.3456,
    "shoulder_symmetry": 3.4567,
    "alignment_deviation": 8.9012,
    "knee_angle": 165.4321,
    "elbow_flexion_angle": 120.5,
    "upper_arm_angle_from_vertical": 15.3,
}
unavailable = ["knee_angle", "trunk_flexion"]  # features that could not be computed
approximate = ["neck_flexion", "alignment_deviation"]  # computed via hip-free fallback
```

### `risk_from_features()` -> `str` (legacy)

One of: `"LOW"`, `"MEDIUM"`, `"HIGH"`. Used internally by `PoseEngine.process_frame()` for `ProcessedFrame.risk_level`. The live monitoring gauge now reads from `ContextSnapshot.risk_level` instead (see Section 7).

### `ContextIntelligenceEngine.evaluate()` -> `ContextSnapshot`

The authoritative risk output. Contains:
- `final_risk: float` — continuous 0-100 score
- `risk_level: str` — `"LOW"`, `"MEDIUM"`, or `"HIGH"` (derived from final_risk thresholds: >=70=HIGH, >=40=MEDIUM)
- `feature_scores: dict` — per-feature 0-100 risk contribution
- `fatigue_score: float` — accumulated fatigue
- `exposure_score: float` — cumulative high-risk exposure
- `reason: str` — human-readable explanation of the risk assessment

---

## 5. Feature Extraction Details

### 5.1 Hip-Free Fallbacks

When hip landmarks are unavailable (seated posture, lower body out of frame), `neck_flexion` and `alignment_deviation` are computed via approximate fallbacks:

- **neck_flexion fallback**: Uses image-vertical reference through neck point instead of hip. Head angle relative to vertical: `angle_between_three_points(ear, neck, [neck.x, neck.y + torso_len])`.
- **alignment_deviation fallback**: Uses ear x-offset from neck (shoulder midpoint) instead of hip: `abs(ear[0] - neck[0]) / torso_len * 100`.

These fallback features are flagged in the `approximate_features` list. The ContextIntelligenceEngine weights them at 0.5 (instead of 1.0) in the base risk calculation.

### 5.2 Visibility Overrides

Angle-sensitive features require higher landmark visibility than the default 0.35 threshold:

- **Shoulder elevation features**: 0.40 visibility threshold (elbows can be partially occluded when arms are at sides)
- **Elbow flexion and upper arm angle**: 0.40 visibility threshold (wrists can be partially occluded)

Features falling below their visibility threshold are added to the `unavailable_features` list.

### 5.3 Unavailable Feature Handling

- Features explicitly marked unavailable or containing NaN are set to `float("nan")` in the features dict
- `risk_from_features()` treats unavailable features as conservative defaults (e.g., knee_angle=140 when unavailable triggers MEDIUM)
- The ContextIntelligenceEngine assigns NaN scores to unavailable features, excluding them from the weighted risk calculation
- A soft floor is applied: 0 unavailable = no floor; 1 lower-body = 25; 1 upper-body = 20; >=2 = 40

---

## 6. Validated Features

All 9 features have been validated using visual diagnostic tools with screenshots at multiple postures.

| Feature | Validation Status | Evidence |
|---------|------------------|----------|
| neck_flexion | PASS | `outputs/debug_neck/` |
| trunk_flexion | PASS | `outputs/debug_trunk/` |
| left_shoulder_elev | PASS | Validated via diagnostic tool |
| right_shoulder_elev | PASS | Validated via diagnostic tool |
| shoulder_symmetry | PASS | `outputs/debug_shoulder/` |
| alignment_deviation | PASS (with fallback) | Hip-free fallback validated |
| knee_angle | PASS | `outputs/debug_knee/` |
| elbow_flexion_angle | PASS | Computed when wrists visible |
| upper_arm_angle_from_vertical | PASS | Computed when wrists visible |

### Validation Tools

| Script | Feature | Key Command |
|--------|---------|-------------|
| `scripts/debug_trunk.py` | trunk_flexion | S = screenshot, Q = quit |
| `scripts/debug_neck.py` | neck_flexion | S = screenshot, Q = quit |
| `scripts/debug_shoulder_symmetry.py` | shoulder_symmetry | S = screenshot, Q = quit |
| `scripts/debug_knee.py` | knee_angle | S = screenshot, Q = quit |
| `scripts/analyze_compression.py` | compression ratio (research) | Q = quit + prints stats |
| `scripts/generate_pose_validation_report.py` | ALL features (auto-capture) | Follow on-screen prompts |

---

## 7. Risk Scoring Pipeline

### 7.1 Per-Frame Risk (Legacy): `risk_from_features()`

Simple threshold check on raw feature values. Produces discrete LOW/MEDIUM/HIGH. Used internally by `PoseEngine.process_frame()` but **not** the authoritative risk source for the live display.

### 7.2 Context Intelligence Engine (Authoritative)

`ContextIntelligenceEngine.evaluate()` produces the authoritative risk assessment:

1. **Base risk**: Weighted combination of feature scores (0-100 per feature). Only features exceeding their medium threshold contribute. Geometrically decaying weights. Approximate features count at 0.5.
2. **Soft floor**: Conservative minimum when features are unavailable (0=none, 1-lower=25, 1-upper=20, >=2=40).
3. **Context modifiers**: Duration penalty (ExposureTracker), task modifier (lifting=+12, reaching=+8, etc.), fatigue modifier (FatigueModel).
4. **Confidence modifier**: Reduces score when camera confidence is low (-1.5 at 70-90%, -4.0 at 50-70%, -6.0 below 50%).
5. **Final risk**: `clamp(base_risk + context_modifier + confidence_modifier, 0, 100)`
6. **Risk level**: `>=70` = HIGH, `>=40` = MEDIUM, else LOW

### 7.3 Single Source of Truth

`live_monitor.py:531` sets `state.risk_level = context_snapshot.risk_level` (not `result.risk_level`). This ensures the live gauge label, score, skeleton overlay color, and all downstream consumers (alerts, history, timeline) read from the same ContextIntelligenceEngine output.

The `ProcessedFrame.risk_level` (from `risk_from_features()`) is still computed internally but is not used for the live display.

---

## 8. Known Limitations

### 8.1 2D Projection Ambiguity

All features operate in 2D image space. Forward bending (toward/away from camera) has limited 2D projection and is detected primarily through vertical landmark displacement, not true 3D angle.

### 8.2 Trunk Rotation Not Tracked

Lateral trunk rotation (twisting) produces minimal signal. `shoulder_symmetry` catches some rotation effects, but a dedicated rotation feature would require 3D landmark data or temporal tracking.

### 8.3 Upper-Body-Only Framing

When the lower body is out of frame (seated posture), `knee_angle` and `trunk_flexion` are unavailable. The soft floor (40.0) ensures the system remains conservative when it cannot verify lower-body posture. The engine will show MEDIUM for partial-body views even if all visible features are within safe ranges — this is by design ("can't verify = don't claim safe").

### 8.4 Confidence Score Scope

The confidence score averages visibility values for landmarks 0-16 (face, shoulders, elbows, wrists). It does not reflect detection quality for lower-body landmarks. `lower_body_confidence` is computed separately for lower-body landmarks (23-28).

---

## 9. Integration Points

### 9.1 Direct Python Import

```python
from backend.services.features import (
    FEATURE_COLUMNS,
    extract_features_from_keypoints,
    mediapipe_landmarks_to_keypoints,
    risk_from_features,
    risk_breakdown,
)
from backend.context.engine import ContextIntelligenceEngine

# In video loop:
kps = mediapipe_landmarks_to_keypoints(landmarks, w, h)
features, unavailable, approximate = extract_features_from_keypoints(kps)
risk = risk_from_features(features, unavailable)  # legacy per-frame

# Context-aware risk (authoritative):
snapshot = context_engine.evaluate(
    features=features,
    issues=issues,
    task_name="Neutral Standing",
    task_confidence=0.0,
    session_duration_seconds=elapsed,
    camera_confidence=confidence,
    delta_seconds=dt,
    unavailable_features=unavailable,
    approximate_features=approximate,
    lower_body_confidence=lb_conf,
)
# snapshot.risk_level  -> authoritative risk label
# snapshot.final_risk  -> continuous 0-100 score
```

### 9.2 Live Monitoring Pipeline

`backend_api/app/services/live_monitor.py`:
- `PoseEngine.process_frame(frame)` -> `ProcessedFrame` (features, keypoints, issues)
- `ContextIntelligenceEngine.evaluate(...)` -> `ContextSnapshot`
- `state.risk_level = context_snapshot.risk_level` (single source of truth)
- `state.risk_score = context_snapshot.final_risk`
- Timeline entries use `context_snapshot.risk_level`

### 9.3 Video Analysis Pipeline

`backend_api/app/api/video_analysis.py`:
- Creates fresh `PoseEngine` + `ContextIntelligenceEngine` per video upload
- Each frame: `engine.process_frame(frame)` then `context_engine.evaluate(...)`
- `VideoAnalysisFrame.risk_level = snapshot.risk_level` (already uses ContextSnapshot)
- No dual-source issue — was always correct

### 9.4 Frontend

`ui_posture/src/`:
- `LiveMonitoring.tsx`: RiskGauge reads `liveStatus.riskLevel` (from `state.risk_level`)
- `ContextAwareRiskCard.tsx`: reads `snapshot.risk_level` (from `/api/context/snapshot`)
- Both now show the same ContextIntelligenceEngine value

### 9.5 Live Demo

`scripts/live_demo.py` demonstrates the full pipeline: webcam -> MediaPipe -> feature extraction -> risk classification -> dashboard overlay.

---

## 10. Future Improvements

### P1 — Before Production

- [ ] **Unit tests**: Add `pytest` tests for `extract_features_from_keypoints()` with synthetic landmark data
- [ ] **Frame-drop resilience**: Add a counter for consecutive no-person frames to avoid stale session statistics
- [ ] **SessionAnalytics alignment**: `highest_risk_level` in session JSON still uses `risk_from_features()` — consider switching to ContextSnapshot

### P2 — Enhancements

- [ ] **Temporal smoothing**: Apply exponential moving average to feature values to reduce frame-to-frame jitter
- [ ] **3D feature extraction**: Use `pose_world_landmarks` for camera-distance-invariant angles
- [ ] **Compression ratio feature**: `torso_len / shoulder_width` could add signal for forward-bend detection
- [ ] **Historical baseline**: Store per-user baseline feature values and flag deviations
- [ ] **Camera calibration**: Detect camera tilt angle to correct the vertical reference vector

### P3 — Research

- [ ] **Trunk rotation metric**: Investigate shoulder-width asymmetry + elbow position delta
- [ ] **Multi-person support**: Currently processes only `result.pose_landmarks[0]`

---

## Files Reference

| File | Role |
|------|------|
| `backend/services/features.py` | Core extraction, risk, and breakdown logic (9 features) |
| `backend/context/engine.py` | ContextIntelligenceEngine — authoritative risk scoring |
| `backend/services/pose_engine.py` | PoseEngine — wraps MediaPipe + feature extraction |
| `backend/core/types.py` | ProcessedFrame, LiveState dataclasses |
| `backend_api/app/services/live_monitor.py` | Live camera loop, state management, single source of truth |
| `backend_api/app/api/video_analysis.py` | Video upload analysis endpoint |
| `backend_api/app/api/video_feed.py` | MJPEG skeleton overlay |
| `backend_api/app/repositories/live.py` | API response builders (LiveStatus, ContextSnapshotResponse) |
| `backend/alerts/engine.py` | AlertEngine — reads ContextSnapshot.risk_level |
| `backend/history/engine.py` | HistoryEngine — session statistics |
| `scripts/live_demo.py` | Live webcam demo dashboard |
| `scripts/debug_trunk.py` | Trunk flexion geometric validation |
| `scripts/debug_neck.py` | Neck flexion geometric validation |
| `scripts/debug_shoulder_symmetry.py` | Shoulder symmetry visual validation |
| `scripts/debug_knee.py` | Knee angle geometric validation |
| `scripts/analyze_compression.py` | Research tool: compression ratio analysis |
| `scripts/generate_pose_validation_report.py` | Automated validation report generator |
| `models/pose_landmarker_lite.task` | MediaPipe model (download separately) |
| `ui_posture/src/pages/LiveMonitoring.tsx` | Frontend live monitoring page |
| `ui_posture/src/components/common/ContextAwareRiskCard.tsx` | Frontend context-aware risk display |
