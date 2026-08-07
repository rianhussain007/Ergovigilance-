# Pose Estimation Module — Status Report

**Date:** 2026-07-13  
**Scope:** `backend/services/pose_engine.py`, `features.py`, `task_recognition.py`, `issue_detection.py`  
`backend/context/engine.py`, `fatigue.py`, `exposure.py`  
`backend/core/constants.py`  
**Role:** Pose Estimation Engineer  
**Audience:** Engineering team

---

## 1. What This Module Does

A single camera frame enters the pipeline; MediaPipe Pose detects a person's 33 body landmarks (shoulders, elbows, wrists, hips, knees, ankles, ears, nose) in 2D pixel coordinates. Those landmarks are converted into 9 continuous biomechanical angles and displacements — neck flexion, trunk flexion, shoulder elevation, shoulder symmetry, alignment deviation, knee angle, elbow flexion angle, and upper arm angle. These features feed two parallel systems: a threshold-based rule engine that scores each frame for ergonomic risk (low/medium/high), and a 5-class task recogniser that guesses what the person is doing (standing, assembling, reaching, lifting, inspecting). The risk score is then modified by temporal context — how long the person has been in a risky posture (exposure), estimated fatigue from session duration and high-risk time, the task type, and camera confidence — to produce a final context-adjusted risk assessment and safety state (safe/observe/critical/recovery). Separately (not yet wired into the risk engine), a RULA-informed score is computed from the same features using published 1993 lookup tables, providing a supplementary ergonomic assessment.

---

## 2. Pipeline Diagram

```
Camera Frame (640×480 RGB)
    │
    ▼
MediaPipe Pose Landmarker (backend/services/pose_engine.py:71)
    │  detect_for_video() → 33 landmarks (x, y, z, visibility)
    │
    ▼
mediapipe_landmarks_to_keypoints() (features.py:319)
    │  Normalised pixel coords + confidence
    │
    ▼
extract_features_from_keypoints() (features.py:203)
    │  9 continuous values: neck_flexion, trunk_flexion,
    │  left/right_shoulder_elev, shoulder_symmetry,
    │  alignment_deviation, knee_angle,
    │  elbow_flexion_angle, upper_arm_angle_from_vertical
    │
    ├──────────────────────────────────────────────────────────┐
    ▼                                                          ▼
risk_from_features() (features.py:273)            detect_task() (task_recognition.py:62)
    │  Hard threshold: 7 features                          │  Gaussian heuristic: 5 classes
    │  → "LOW" / "MEDIUM" / "HIGH"                        │  + 10-frame smoothing window
    │                                                      │  + dwell-time tracking
    ▼                                                      ▼
detect_posture_issues() (issue_detection.py:66)  task_name + confidence + duration
    │  Named issues + severity per                         │
    │  feature exceeding threshold                         │
    ▼                                                      │
ContextIntelligenceEngine.evaluate() (engine.py:193)  ─────┘
    │  base_risk = max(feature_scores)
    │  + task modifer (0-12 from _TASK_MODIFIERS)
    │  + duration penalty (0-30 from ExposureTracker)
    │  + fatigue modifier (0-20 from FatigueModel)
    │  + confidence modifier (-6 to 0)
    │  = final_risk (0-100) → risk_level → safety_state
    │
    ▼
ContextSnapshot (engine.py:53) — returned via API
```

**Parallel path (not yet consumed by the risk engine):**

```
extract_features()
    │
    ▼
compute_rula_informed_score() (features.py:129)
    │  Continuous → discrete band conversion
    │  → RULA Table A lookup (upper body)
    │  → RULA Table B lookup (neck/trunk/legs)
    │  → RULA Table C lookup → grand score 1-7
    │
    ▼
rula_informed_score in API response (live.py:482)
```

---

## 3. What's Actually Built and Verified

### 3.1 Pose Detection (`pose_engine.py:41-125`)

**What it does:** Wraps MediaPipe's `PoseLandmarker.create_from_options()` in a reusable class. Configures VIDEO mode at ~30 FPS, single-person tracking, 0.5 detection/tracking confidence thresholds. `process_frame()` converts BGR→RGB, runs detection, converts landmarks to pixel coordinates, calls feature extraction, calls risk classification, calls task recognition, and returns a `ProcessedFrame` struct.

**Data used:** Raw 640×480 BGR frame from OpenCV.

**Verification:** Has been running live in multiple sessions via the desktop demo (`scripts/live_demo.py`) and the FastAPI backend (`live_monitor.py`). Produces consistent landmark output. Frame time is acceptable (<40 ms on laptop CPU).

### 3.2 Seven Core Ergonomic Features (`features.py:203-270`, lines 259-266)

**What it does:** Computes 7 biomechanical values from landmarks:
- **neck_flexion** (line 233): angle at the shoulder-midpoint between ear and hip, subtracted from 180°. 0 = upright.
- **trunk_flexion** (line 234): angle at the hip between neck-midpoint and a synthetic vertical-up reference.
- **left/right_shoulder_elev** (lines 235-236): angle at each shoulder between elbow and a synthetic vertical-down reference.
- **shoulder_symmetry** (line 237): absolute vertical difference between shoulders ÷ shoulder width × 100.
- **alignment_deviation** (line 238): absolute horizontal ear-to-hip offset ÷ torso length × 100.
- **knee_angle** (line 246): mean of left and right hip–knee–ankle angles.

**Data used:** 33 MediaPipe landmarks.

**Verification:** These 7 features have been tested extensively in live sessions spanning weeks. They produce non-zero, posture-responsive values. The threshold values in `_FEATURE_RULES` (engine.py:22-30) are open-source-common defaults, not clinically validated.

### 3.3 Task Recognition (`task_recognition.py:33-273`)

**What it does:** A hand-tuned, per-frame Gaussian heuristic classifier with 5 classes. Each class scores the frame by summing Gaussian RBF contributions from a manually chosen set of features and derived values (elbow angle, wrist height relative to shoulder, arm extension ratio, wrist-to-torso distance, wrist z-depth). The highest-scoring class wins. A score below 0.3 defaults to "Unknown".

**Temporal smoothing (added this week, lines 241-259):** A 10-frame sliding window accumulates confidence-weighted votes. The smoothed winner overrides the raw frame classification only if its margin exceeds 5% — preventing flicker without masking genuine transitions.

**Dwell-time (added this week, lines 261-266):** A `task_start_time` is set whenever the smoothed task changes. `task_duration_seconds` (line 272) is returned with every frame.

**Data used:** MediaPipe landmarks (shoulder/elbow/wrist/hip/knee/ankle indices 11-28) and the 7 core features.

**Verification:** The original 5-class heuristic has been used in live sessions. The temporal smoothing and dwell-time additions from this week have been **code-reviewed and tested with synthetic keypoints only** — they have not been confirmed in a live webcam session with real postural transitions. The `_gauss()` means and sigmas are arbitrary (never fitted to real data).

### 3.4 Context-Aware Risk Scoring (`engine.py:147-310`, `fatigue.py:21-127`, `exposure.py:40-116`)

**What it does:** The `ContextIntelligenceEngine.evaluate()` method computes:
1. **base_risk** (line 235): each of the 7 features is scored 0-100 against medium/high thresholds; the maximum score becomes base risk.
2. **duration_penalty** (exposure.py:109-116): cumulative seconds with any feature above its high-risk threshold, capped at +30.
3. **task_modifier** (engine.py:250): lookup from `_TASK_MODIFIERS` (Neutral=0, Inspection=3, Assembly=5, Reaching=8, Lifting=12).
4. **fatigue_modifier** (fatigue.py:120-126): exponential fatigue curve driven by session duration + high-risk minutes + task type, with recovery during low-risk tasks. Score × 0.2 → 0-20.
5. **confidence_modifier** (engine.py:341-349): -6 to 0 based on mean landmark visibility.
6. **final_risk** (line 276-278): clamped sum of base + context + confidence modifiers.
7. **safety_state** (lines 360-373): state machine with hysteresis (SAFE → OBSERVE → CRITICAL → RECOVERY → SAFE).

**Data used:** 7 core features, task name + confidence, session duration, camera confidence, delta time.

**Verification:** The engine runs live in every active session. Its outputs (final_risk, risk_level, safety_state, reason) are visible in the API and UI. The thresholds and modifier magnitudes are designed values, not clinically calibrated.

### 3.5 RULA-Informed Scoring (`features.py:21-177`)

**What it does:** Converts 5 of the 9 biomechanical features into discrete RULA band scores (lines 81-127), looks up Posture Score A from Table A (lines 46-53), Posture Score B from Table B (lines 57-64), then Grand Score from Table C (lines 68-78). Returns the grand score plus all intermediate values.

**Data used:** `neck_flexion`, `trunk_flexion`, `knee_angle`, `elbow_flexion_angle`, `upper_arm_angle_from_vertical`. Wrist angle and wrist twist are hardcoded to 1. Force/load and muscle-use adjustments are 0.

**Verification:**
- The lookup tables have been **verified by manual cross-check** against the published RULA worksheet (McAtamney & Corlett 1993) — Table A, Table B, and Table C lookups all match.
- The band-conversion functions have been **tested with synthetic feature values** covering all band ranges (0° through 180° for each body part).
- The `compute_rula_informed_score()` function has been **tested against isolated code** with known input/output pairs.
- **Not yet verified in a live session** with real camera data producing non-zero elbow/upper-arm features. A live session was started and the API returned `rula_informed_score: 3`, but the camera was not detecting a visible person (all feature values were 0), so this does not constitute a useful test.

---

## 4. Explicit Limitations

### 4.1 Single-Person Only

`PoseEngine` configures MediaPipe with `num_poses=1` (pose_engine.py:57). If two people are visible, only the first detected person is tracked. Switching to multi-person would require either MediaPipe `num_poses=N` (performance cost linear with N, CPU-bound) or replacing with YOLO-pose (investigated and deemed unjustified for current CPU-only hardware unless multi-person becomes a near-term requirement). All downstream logic (feature extraction, task recognition, risk scoring) assumes a single person.

### 4.2 CPU-Only, No GPU

All inference runs on CPU via MediaPipe's XNNPACK delegate. Measured per-frame time on a modern laptop is 20-40 ms at 640×480 resolution. This is acceptable for 15-20 FPS but leaves no headroom for additional models (hand tracking, object detection) running concurrently.

### 4.3 RULA Scoring — Known Defaults / Missing Components

| Component | Status | Detail |
|---|---|---|
| Neck angle band | Real | `_rula_neck_score()` (features.py:81) |
| Trunk angle band | Real | `_rula_trunk_score()` (features.py:93) |
| Upper arm angle band | Real | `_rula_upper_arm_score()` (features.py:105) |
| Lower arm angle band | Real | `_rula_lower_arm_score()` (features.py:121) |
| Leg support | Approximated | Inferred from `knee_angle` ≥ 150° (features.py:148-149) |
| Table A lookup | Real | Hardcoded from published worksheet (features.py:46-53) |
| Table B lookup | Real | Hardcoded from published worksheet (features.py:57-64) |
| Table C lookup | Real | Hardcoded from published worksheet (features.py:68-78) |
| **Wrist angle** | **Defaulted to 1** | MediaPipe wrist landmarks (indices 15/16) are at the joint, not the hand. Reliable wrist flexion requires hand-tracking. |
| **Wrist twist** | **Defaulted to 1** | Requires forearm pronation/supination detection, not feasible from single 2D camera. |
| **Force/load** | **Defaulted to 0** | Requires manual input or instrumented gloves — not a camera problem. |
| **Muscle-use (static >1m)** | **Defaulted to 0** | No existing logic; `task_duration_seconds` exists but is not wired in. |
| **Muscle-use (repeated >4×/min)** | **Defaulted to 0** | No repetition counter exists in the pipeline. |
| **Upper arm: raised/abducted** | **Not detected** | Would need 3D vector; current pipeline is 2D only. |
| **Lower arm: across-midline** | **Not detected** | Would need hand position relative to torso midline. |
| **Neck/trunk twist or side-bend** | **Not included** | Requires trunk axial rotation — not reliable from front-facing 2D camera. |

**Bottom line:** The current RULA score is a lower-bound estimate. A true RULA worksheet completed by a trained observer will be at least as high (often higher) because of the missing adjustments. The code's own docstring (features.py:30-39) states this explicitly.

### 4.4 Task Recognition — Zero Training Data

`TaskRecognition` is a hand-tuned heuristic. Every `(mean, sigma)` pair in the five Gaussian scoring functions was chosen by the code author observing their own posture. There is:
- No training script.
- No labeled dataset.
- No cross-validation.
- No confusion matrix.
- No accuracy metric.

The temporal smoothing (10-frame confidence-weighted window) and dwell-time tracking are mechanical additions — they reduce output flicker but do not improve classification accuracy. The output is confidence-weighted in name only; the confidence values are raw Gaussian scores, not calibrated probabilities.

### 4.5 Never Validated Beyond One Person and One Environment

The entire pipeline has been tested by one person (the original code author), under one lighting condition (indoor office), with one camera angle (front-facing, ~1.5 m distance, centred), wearing one set of clothing. The following have never been tested:
- A different person (different height, body proportions, limb lengths).
- A different camera angle (side view, elevated view, angled view).
- Different lighting (low light, backlight, sunlight).
- Different clothing (dark colours, reflective materials, loose-fitting).
- Different background complexity (cluttered, moving background).

The feature extraction is partially normalised (shoulder symmetry ÷ shoulder width, alignment ÷ torso length), but the RULA band cutoffs and `_FEATURE_RULES` thresholds are absolute angles, not relative to body proportions. A shorter or taller person will be scored against the same angle thresholds.

### 4.6 Other Code-Level Limitations

- **`FEATURE_THRESHOLDS` in constants.py (lines 27-35) is a documentation-only dict** — it is never read by the risk engine. The actual thresholds are duplicated in `_FEATURE_RULES` (engine.py:22-30), `_ISSUE_RULES` (issue_detection.py:6-63), `_EXPOSURE_THRESHOLDS` (exposure.py:13-21), and `risk_from_features()` (features.py:273-292). These four sets of thresholds are supposed to be identical but are maintained independently — they can drift out of sync.
- **`movement_velocity` is computed only from neck and trunk flexion deltas** (pose_engine.py:93-95) — it does not use elbow, wrist, or knee movement, limiting its sensitivity for arm-intensive tasks.
- **`_TASK_MODIFIERS` in engine.py (lines 35-41) has an unreachable `"Walking"` class** — the task recogniser never produces this label.
- **The leg-support RULA heuristic uses `knee_angle ≥ 150°`** (features.py:149) — this is a proxy, not an actual leg-support assessment.

---

## 5. This Week's Concrete Additions

### 5.1 Task Recognition: Temporal Smoothing

**Before:** Raw per-frame classification with no memory — every frame independently scored, causing task labels to flicker between frames when two classes had similar scores.

**After:** A 10-frame deque (task_recognition.py:40) stores `(task_name, confidence)` pairs. Weighted voting picks the smoothed task. The raw classification is overridden only if the smoothed winner's margin exceeds 5% (line 257). Raw classification always runs first for responsiveness.

**Verification status:** Code-tested (unit-style input/output checks). **Not yet confirmed in live webcam session** with real postural transitions.

### 5.2 Task Recognition: Dwell-Time Tracking

**Before:** No duration tracking — the system knew the current task but not how long it had been held.

**After:** `_last_smoothed_task` and `_task_start_time` (lines 41-42) track when the task last changed. `task_duration_seconds` is returned with every frame (line 272).

**Verification status:** Code-tested. **Not yet confirmed in live session.**

### 5.3 New RULA Features: `elbow_flexion_angle`

**Before:** Elbow angle was only computed locally inside `task_recognition.py` (lines 104-106) — not exposed as a feature.

**After:** `left_elbow_angle` and `right_elbow_angle` are computed in `extract_features_from_keypoints()` (features.py:251-252) using `angle_between_three_points(shoulder, elbow, wrist)`. The mean of left and right becomes `elbow_flexion_angle` (line 253). Registered in `FEATURE_COLUMNS` (constants.py:23).

**Verification status:** Computed correctly in isolated test with synthetic keypoints. **Not yet confirmed in live session** because `left_wrist`/`right_wrist` were missing from the COCO_17 and MEDIAPIPE_33 keypoint maps until partway through this week — those maps were fixed (constants.py was updated to add the entries). A `live_demo.py` crash caused by this exact issue was observed and fixed.

### 5.4 New RULA Features: `upper_arm_angle_from_vertical`

**Before:** Not computed. The existing `shoulder_elev` uses a vertical-down reference, but the RULA version was implemented separately for clarity.

**After:** Computed as `180° - angle_between_three_points(vertical_up, shoulder, elbow)` (features.py:255-257), then averaged left/right. The `180° -` conversion was a **bug fix applied this week** — the initial implementation measured from vertical-up (giving ~165° for neutral posture → RULA upper arm score 4), which was wrong. Fixed to measure from vertical-down (0° for neutral → RULA upper arm score 1).

**Verification status:** Corrected and tested with synthetic keypoints (neutral posture now produces upper arm score 1). **Not yet confirmed in live session.**

### 5.5 RULA-Informed Scoring with Published Tables

**Before:** No RULA scoring existed anywhere in the codebase.

**After:** `compute_rula_informed_score()` (features.py:129-177) with:
- `_TABLE_A`, `_TABLE_B`, `_TABLE_C` hardcoded from the McAtamney & Corlett 1993 published worksheet (features.py:46-78).
- Band-conversion functions for neck, trunk, upper arm, lower arm (features.py:81-126).
- Wrist and wrist twist defaulted to 1; force/load and muscle-use defaulted to 0; leg support inferred from knee angle.
- Returns dict with grand score plus all intermediate scores for transparency.

The RULA score is computed in the API layer (`live.py:480-482`) and returned as `rula_informed_score` in the context snapshot response. The OpenAPI schema confirms the field is exposed.

**Verification status:**
- ✅ Lookup tables verified by manual cross-check against published RULA worksheet (ErgoPlus / NC State ErgoCenter reproductions). All three tables match.
- ✅ Band-conversion functions tested with synthetic values covering every band range.
- ✅ API schema confirmed to include `rula_informed_score` via OpenAPI.
- ⬜ **Not yet verified in a live session with valid, non-zero feature data.**

---

## 6. Concrete Next Steps

### Tier 1: Hours, Not Days

| Step | Effort | What It Involves |
|---|---|---|
| **Wire dwell-time into RULA Muscle Use** | ~1 hour | In `compute_rula_informed_score()` (features.py:129): add a parameter for `task_duration_seconds`. If > 60, add +1 to `score_d`. No new infrastructure needed — `task_duration_seconds` already flows through every frame from `task_recognition.py:272`. |
| **Expose intermediate RULA scores in API** | ~30 minutes | Add `rula_neck`, `rula_trunk`, `rula_upper_arm`, `rula_lower_arm` to the `ContextSnapshotResponse` schema and the repository function — they are already computed in `compute_rula_informed_score()` but not returned. |

### Tier 2: Days, Not Weeks

| Step | Effort | What It Involves |
|---|---|---|
| **Build a repetition/cycle counter for the ">4×/minute" condition** | 2-3 days | Add a sliding-window feature buffer (15-30 second deque) to `PoseEngine` or a new utility. Implement peak/valley detection on `trunk_flexion` — a simple state machine (STATE_UP/STATE_DOWN with hysteresis) can count cycles. No ML needed. Tune thresholds against real box-lifting footage. Once working on trunk_flexion, extend to other features for other tasks. |
| **Threshold-tuning pass for TaskRecognition on real box-lifting footage** | 2-3 days | Collect 5-10 minutes of labelled box-lifting footage with the target camera setup. Run the pipeline, record predictions + features per frame. Compare against hand labels. Adjust means and sigmas in `_gauss()` calls in `task_recognition.py`. This is empirical: one parameter at a time, re-run, check confusion. The existing architecture supports this without any code structure changes. |
| **Live-session verification of RULA features** | 1 day | Stand in front of the running camera with known postures (arms at side = 0° upper arm angle, arms forward = 90°, etc.). Verify the API returns `upper_arm_angle_from_vertical` and `elbow_flexion_angle` values that match the actual posture. Then verify the RULA grand score changes as expected. This is the single most important step before presenting the RULA feature as working. |

### Tier 3: Requires a Decision

| Step | Effort | Decision Needed |
|---|---|---|
| **Validate on a second person and environment** | 1-2 weeks | Recruit 2-3 subjects with different body types. Set up the camera in a different room with different lighting. Run the full pipeline. Compare feature distributions and risk classifications against the original subject. This is the top validation gap — the entire pipeline has only ever been tested on one person. |
| **Full classifier for TaskRecognition** | 1-2 weeks | If hand-tuning proves unable to separate classes (e.g., "Reaching" vs. "Lifting" produce identical 2D projections), build a Random Forest or Logistic Regression on the same 9 features plus velocity deltas. Requires ≥30 minutes labelled footage, a training script (nothing exists today), and cross-validation. **Not yet justified** — start with threshold-tuning first. |
| **Multi-person support** | Not scoped | Requires YOLO-pose evaluation, CPU benchmark, and redesign of all downstream logic. Only relevant if multi-person becomes a near-term product requirement. |

---

## 7. One-Sentence Summary Per Section

**Section 3 (What's Built):** The pipeline runs end-to-end with real camera data for pose detection, feature extraction, and context-aware risk scoring; task recognition's temporal smoothing and dwell-time are code-complete but not yet confirmed in a live session; the RULA scoring tables are verified against the published standard but the score has not been confirmed with real camera data producing non-zero feature values.  

**Section 4 (Limitations):** The system has only ever been tested on one person in one room with one camera angle, every threshold in the system is an unvalidated default not a clinically-derived value, the RULA score is a lower-bound estimate because wrist angle, wrist twist, force/load, and muscle-use/repetition are all defaulted to zero, and task recognition has zero training data backing its Gaussian means and sigmas.  

**Section 5 (This Week's Additions):** This week added temporal smoothing and dwell-time tracking to task recognition, two new upper-body features (elbow flexion angle and upper arm angle from vertical) required for RULA, and a full RULA-informed scoring function with published Table A/B/C lookups — of these, only the elbow/upper-arm feature calculations have been fixed after a bug was found and corrected, and none have been verified in a live camera session with valid posture data.  

**Section 6 (Next Steps):** The highest-return immediate step is wiring the existing `task_duration_seconds` into RULA's muscle-use "static >1 minute" condition (one hour of work), followed by building a simple peak-detection cycle counter for the "repeated >4×/minute" condition and threshold-tuning task recognition against real box-lifting footage (2-3 days each), with validation on a second person in a different environment being the top unscheduled priority.
