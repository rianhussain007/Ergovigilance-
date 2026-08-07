# Pose Estimation Module — Current Status & Extensions

**Date:** 2026-07-13  
**Scope:** `backend/services/pose_engine.py`, `features.py`, `task_recognition.py`, `backend/context/engine.py`  
**Audience:** Engineering team presentation — assumes technical literacy, not code familiarity.

---

## PART 1 — How It Works

### 1.1 RULA-Informed Scoring

#### Pipeline (raw keypoints → grand score)

```
MediaPipe Pose Landmarker
       ↓  33 landmarks (x, y, z, visibility) per detected person
  extract_features_from_keypoints()
       ↓  9 continuous biomechanical values (see §1.1.1)
  compute_rula_informed_score()
       ↓  5 discrete band scores (neck, trunk, upper arm, lower arm, legs)
  RULA Table A + Table B lookups
       ↓  Posture Score A (upper body) + Posture Score B (neck/trunk/legs)
  RULA Table C lookup
       ↓  Grand Score 1–7
  returned in API as rula_informed_score (int)
```

#### 1.1.1 Nine features (continuous angles/displacements)

| Feature | How it is computed | Unit |
|---|---|---|
| `neck_flexion` | Angle at "neck" midpoint (between shoulders) from ear through neck to hip, measured from 180°. 0 = upright. | degrees |
| `trunk_flexion` | Angle at hip between neck and a vertical-up reference point. 0 = upright. | degrees |
| `left/right_shoulder_elev` | Angle at shoulder between elbow and a vertical-down reference. How far the arm has been raised. | degrees |
| `shoulder_symmetry` | Absolute vertical difference between shoulders, normalised by shoulder width. | % |
| `alignment_deviation` | Horizontal offset of ear from hip, normalised by torso length. | % |
| `knee_angle` | Mean of left/right angle at the knee (hip–knee–ankle). 180 = straight. | degrees |
| **`elbow_flexion_angle`** | Mean of left/right angle at the elbow (shoulder–elbow–wrist). 180 = straight. | degrees |
| **`upper_arm_angle_from_vertical`** | Mean of left/right angle at the shoulder between the elbow and a vertical-down reference. Arms at side = 0°. Arms straight up = 180°. | degrees |

The last two were added specifically to support RULA. The seven others predate them.

#### 1.1.2 Band conversion (continuous → discrete)

Each continuous value is converted to a 1–7 discrete band via threshold functions that mirror the published RULA worksheet (McAtamney & Corlett 1993, Applied Ergonomics 24(2), 91–99):

| Body part | Input range | Band 1 | Band 2 | Band 3 | Band 4 | Band 5–6 |
|---|---|---|---|---|---|---|
| Neck | 0°–60°+ | 0–10° | 10–20° | >20° | — | — |
| Trunk | 0°–60°+ | 0° (neutral) | 0–20° | 20–60° | >60° | — |
| Upper arm | –90° to +180° | –20° to +20° | 20–45° / –45 to –20° | 45–90° | >90° | — |
| Lower arm | 0°–180° | 60–100° | <60° or >100° | — | — | — |
| Legs | knee angle | ≥150° (supported) | <150° (unsupported) | — | — | — |

#### 1.1.3 Published lookup tables (exact copies of the 1993 worksheet)

**Table A** maps (upper arm, lower arm, wrist twist, wrist) → posture score A (1–9).  
**Table B** maps (neck, trunk, legs) → posture score B (1–9).  
**Table C** maps (score A, score B) → grand RULA score (1–7).

The code contains hard-coded dicts and a list that exactly reproduce the published grids. These were verified by manual cross-check against the ErgoPlus and NC State ErgoCenter reproductions.

#### 1.1.4 What is NOT included (and why)

| Missing component | Impact | Why absent |
|---|---|---|
| Wrist angle | Table A always receives wrist = 1 (neutral) | MediaPipe wrist landmarks (15/16) are at the joint, not the hand. Reliable wrist flexion requires hand-tracking (extra model, ~3× keypoints). |
| Wrist twist | Always receives wrist_twist = 1 (mid-range) | Requires forearm pronation/supination detection. Not feasible from single-camera 2D landmarks. |
| Force/load | Muscle-use score = 0, force/load score = 0 | Requires manual input or instrumented gloves. Not a camera problem. |
| Neck/trunk twist or side-bend | Not included in Table B | MediaPipe provides face orientation but not reliable trunk axial rotation from a single front-facing camera. |
| Upper arm: raised/abducted | Not detected | Would need shoulder-to-elbow vector in 3D; current pipeline is 2D (x,y only). |
| Lower arm: across-midline | Not detected | Would need hand position relative to torso midline. |

**Bottom line:** The current RULA score is a useful lower-bound estimate. A true RULA worksheet completed by a trained observer will always be at least as high (often higher) because of the missing adjustments.

---

### 1.2 Task Recognition

#### Architecture: hand-tuned Gaussian heuristic, 5 classes

`TaskRecognition` (`backend/services/task_recognition.py`) scores every frame against five task classes using a Gaussian radial basis function:

```
score = sum of exp(-0.5 * ((value - mean) / sigma)^2) for each input
```

Each class defines its own `(mean, sigma)` pairs on a subset of inputs:

| Task | Primary inputs | Typical indicator |
|---|---|---|
| Neutral Standing | trunk ≈ 0°, neck ≈ 0°, elbow ≈ 170° | Hands at sides, minimal bend |
| Assembly Work | trunk ≈ 0°, wrists at chest height, elbow ≈ 110° | Hands near waist–chest, moderate bend |
| Reaching | arm extension > 0.9, hands far from body, trunk ≈ 10° | Arms extended forward |
| Lifting / Picking | trunk ≈ 30°, wrists below waist, knees bent | Significant forward bend + hand lowering |
| Inspection | neck ≈ 25°, hands raised to face, trunk ≈ 0° | Looking down with hands near face |

The class with the highest score wins. A score < 0.3 defaults to "Unknown".

#### Temporal smoothing

The raw per-frame classification is buffered in a 10-frame sliding window. Weighted voting (by confidence) picks the smoothed task. The raw classification is overridden only if the smoothed winner has a margin > 5% over the runner-up. This prevents flickering between two similar-scoring tasks.

#### Dwell-time tracking

A `task_start_time` timestamp is updated whenever the smoothed task changes. `task_duration_seconds` is returned with every frame.

#### Known limitations

- **Single-frame-derived even with smoothing** — each frame is classified independently; the window only smooths the *output*.
- **No training pipeline** — all means and sigmas are hand-tuned, never fitted to data.
- **No repetition counter** — task duration measures *how long the current task has been held*, not how many cycles have occurred.
- **Human silhouette only** — the classifier assumes a visible standing person; it has no notion of "not working" vs. "not visible."
- **No depth awareness** — all inputs are 2D pixel coordinates; reaching forward (into the camera) vs. reaching sideways look similar.

---

### 1.3 Context-Aware Risk Engine

`ContextIntelligenceEngine` (`backend/context/engine.py`) produces a single frame-level `ContextSnapshot` with:

```
final_risk = clamp(base_risk + context_modifier + confidence_modifier, 0, 100)
```

where:

#### base_risk (0–100)

Each of the 7 original features is independently scored against a medium/high threshold pair:

```
knee_angle:      medium=150°, high=100°, inverted (lower = worse)
neck_flexion:    medium=10°,  high=30°
trunk_flexion:   medium=20°,  high=60°
shoulder_elev:   medium=30°,  high=60°
shoulder_sym:    medium=5%,   high=15%
alignment_dev:   medium=10%,  high=25%
```

`base_risk = max(feature_scores.values())`. Only the worst feature drives the base risk. The 2 new RULA features (`elbow_flexion_angle`, `upper_arm_angle_from_vertical`) are **not** registered in `_FEATURE_RULES` — they pass through the pipeline but are invisible to the threshold-based engine.

#### context_modifier = duration_penalty + task_modifier + fatigue_modifier

| Modifier | Source | Range |
|---|---|---|
| duration_penalty | `ExposureTracker` — accumulates high-risk seconds | 0–30+ |
| task_modifier | `_TASK_MODIFIERS` dict: Neutral=0, Inspection=3, Assembly=5, Reaching=8, Lifting=12 | 0–12 |
| fatigue_modifier | `FatigueModel` — logistic on session time + high-risk exposure | 0–20+ |

#### confidence_modifier

Based on mean MediaPipe landmark visibility: ≥90% = 0, ≥70% = –1.5, ≥50% = –4, else –6.

#### safety_state (state machine)

```
LOW   → SAFE (or RECOVERY → SAFE if coming from CRITICAL)
MEDIUM → OBSERVE
HIGH  → CRITICAL
```

Hysteresis prevents rapid cycling between states.

---

## PART 2 — Can Task Recognition Feed RULA/REBA Adjustments?

### 2.1 Current hardcoded defaults

Both the RULA **Muscle Use** adjustment and the REBA **Activity Score** are absent from the current code:

- `compute_rula_informed_score()` at line 152: `score_d = posture_b` — no muscle/force score added.
- `score_c` (line 159–160) has no muscle-use or force/load addition.
- There is no REBA implementation at all in the codebase.

**Confirmed:** All four RULA adjustment rows (muscle-use score, force/load score for Group A; muscle-use score, force/load score for Group B) plus the REBA Activity Score are effectively zero / unused.

### 2.2 Dwell-time can directly satisfy the ">1 minute static posture" condition

RULA's Muscle Use score:

> +1 if posture is mainly static (held for >1 minute) OR repeated >4×/minute

REBA's Activity Score:

> +1 if one or more body parts held static for >1 minute  
> +1 if repeated small-range actions >4×/minute  
> +1 if action causes rapid large-range changes in posture

`task_recognition.py` line 266 already computes `task_duration_seconds`. Wiring this into the RULA/REBA score is straightforward:

```python
# Pseudocode for the change
muscle_use_score = 0
if task_duration_seconds > 60:
    muscle_use_score = 1   # static posture >1 minute
```

This would be a ~5-line addition to `compute_rula_informed_score()` — trivially small.

### 2.3 No repetition counter exists — what would be needed

Current state: **No frame-to-frame cycle/repetition counter anywhere in the pipeline.**

To detect "repeated action >4×/minute", you need a **cycle detector** on a time-series of one or more features. For box-lifting, `trunk_flexion` naturally oscillates:

```
Standing (flexion ~10°) → Bend (flexion ~60°) → Stand → Bend → ...
```

A minimal approach:

1. **Pick one or two features** that reliably oscillate during the target activity. For lifting: `trunk_flexion` and `knee_angle` are the clear candidates.
2. **Sliding window** (e.g., 15–30 seconds) — store a deque of `(feature_value, timestamp)`.
3. **Detect zero-crossings** on a detrended or smoothed signal — count how many times `trunk_flexion` rises above a threshold (e.g., 30°) and falls back below it. Each full cycle is one repetition.
4. **Rate-limit** — if cycles/minute > 4, set the repetition flag.

This is a classic 1D peak/valley detection problem. It does **not** require ML. A simple implementation using `scipy.signal.find_peaks` or even a manual finite-state-machine (STATE_UP, STATE_DOWN with hysteresis) would work for a well-defined motion like box-lifting.

### 2.4 Effort assessment

| Item | Effort | Reason |
|---|---|---|
| Wire dwell-time into RULA muscle-use | **Small** (~1 hour) | 5 lines in `compute_rula_informed_score()`; task_duration_seconds already available. |
| Wire dwell-time into REBA activity score | **Small** (~1 hour) | Same pattern, new function. |
| Add cycle/repetition counter for lifting | **Moderate** (~2–3 days) | Requires a sliding-window feature buffer, threshold tuning for `trunk_flexion`, testing against real footage to pick the right smoothing and hysteresis. No ML needed, but the thresholds are activity-specific. |
| Generalise cycle counter to any task | **Large** (1–2 weeks) | Different activities produce different oscillation patterns. A single set of thresholds will not work for "Inspection" (brief neck dips) and "Lifting" (full trunk cycles). Would either need per-task thresholds or a learned detector. |

---

## PART 3 — Validating Task Recognition on Box-Lifting Data

### 3.1 Current state: no training data pipeline

Confirmed. `TaskRecognition` is entirely hand-tuned. Every `(mean, sigma)` pair was chosen by code authors observing their own posture. There is no:

- Training script
- Labeled dataset
- Cross-validation split
- Accuracy/confusion matrix

The existing `scripts/train_svm.py` is for the posture risk classifier, **not** for task recognition.

### 3.2 What validating against real box-lifting footage involves

The primary question: is this a **threshold-tuning** exercise or a **classifier-retraining** exercise?

#### Option A: Threshold-tuning (recommended first step, ~2–3 days)

1. **Collect 5–10 minutes** of real box-lifting footage with a single subject, captured at the same camera angle/distance as the current setup.
2. **Run the existing pipeline** over the footage, recording per-frame task predictions and features to a CSV.
3. **Hand-label** the footage frame-by-frame (or at key transition points). This is the most labour-intensive step — even a rough label every 1–2 seconds takes ~1 hour per minute of footage.
4. **Compare predictions to labels.** Likely findings:
   - "Lifting / Picking" may be confused with "Reaching" at the top of the lift.
   - "Neutral Standing" may be interspersed between lifts, causing flicker.
   - The 10-frame smoothing window may be too short for transition handling.
5. **Tweak thresholds** (means and sigmas) to better separate the classes. This is empirical: check the confusion, adjust one parameter at a time, re-run.

This is feasible and can be done entirely within the existing architecture. It does not require a deep learning framework.

#### Option B: Train a new classifier (~1–2 weeks, more data)

If the Gaussian heuristic proves fundamentally unable to separate classes (e.g., "Reaching forward" vs. "Lifting" produce indistinguishable 2D projections), a simple classifier (Random Forest, Logistic Regression) on the same features could provide better separation. This requires:

- **~30+ minutes** of labelled footage (more classes = more data).
- **Feature engineering** — possibly adding velocity/acceleration deltas.
- **A training script** (no existing infrastructure for this).
- **Cross-validation** to avoid overfitting to one subject or camera setup.

### 3.3 Which is more realistic?

**Threshold-tuning (Option A) is the pragmatic next step.** The existing Gaussian heuristic is simple and interpretable. The most likely failure mode for box-lifting is not "the wrong class of classifier" but "untuned thresholds for a motion the author never performed while tuning." A focused tuning pass against real footage of the target motion should yield acceptable results.

A full classifier (Option B) becomes necessary only if:
- The system must distinguish activities that are truly ambiguous in 2D (e.g., "lifting a box" vs. "tying a shoelace").
- The system must support many simultaneous activity classes (>5).
- Per-class confidence calibration matters for downstream risk scoring.

For a 5-class single-activity (box-lifting) validation, Option A is sufficient.

---

## PART 4 — Known Environmental / Training Constraints

All derived from observations during this week's development and testing:

### 4.1 Single-person only

MediaPipe `PoseLandmarker` is configured with `num_poses=1`. The pipeline ignores the second person if two are visible. This is a MediaPipe-level constraint: `PoseLandmarker` can be configured with `num_poses=N`, but:

- Performance decreases linearly with N (CPU-bound inference).
- The downstream logic (feature extraction, risk calculation) assumes a single person.
- Switching to YOLO-pose for multi-person was investigated and deemed **not justified** for the current CPU-only hardware unless multi-person becomes a near-term requirement.

### 4.2 Never tested on a second person, different lighting, etc.

The entire pipeline has been tested by **one person** (the original author), under **one lighting condition** (indoor office), with **one camera angle** (front-facing, ~1.5 m distance, centred). This is the #1 validation gap.

Known failure modes that have not been tested:
- Side-angle camera: shoulder symmetry, trunk flexion, and especially upper arm angle (RULA input) will produce systematically different values.
- Low-light / backlight: MediaPipe detection confidence drops, triggering the confidence modifier penalty.
- Dark or patterned clothing: MediaPipe is trained on varied data but is known to lose tracking on solid black or highly reflective clothing.
- Different body shapes / heights / limb proportions: The feature extraction is normalised by torso length and shoulder width, but the risk thresholds in `_FEATURE_RULES` and the RULA band cutoffs are absolute angles, not relative. A shorter person with the same absolute trunk angle may have a different biomechanical risk profile — but the thresholds will treat them identically.

### 4.3 CPU-only, no GPU

Inference runs entirely on CPU via MediaPipe's XNNPACK delegate. Typical per-frame time is ~20–40 ms at 640×480 on a modern laptop CPU. This is acceptable for ~15–20 FPS throughput but leaves no headroom for additional models (hand tracking, object detection for load estimation) running simultaneously.

Any future model changes must be assessed against this constraint. A GPU (CUDA/OpenCL) is not available in the current deployment environment.

---

## Summary: What's Next

### Confirmed small additions (weeks, not days)

1. **Wire dwell-time into RULA muscle-use score.** `task_duration_seconds` already flows through the pipeline. Adding `+1` to `score_d` when `task_duration_seconds > 60` is a ~5-line change. This directly addresses the "static posture >1 minute" condition.
2. **Expose intermediate RULA scores in the API response.** Currently only the grand score is returned. Exposing `rula_neck`, `rula_trunk`, `rula_upper_arm`, `rula_lower_arm` would improve explainability and debugging.

### Moderate additions (days, not weeks)

3. **Add a cycle/repetition counter for a single target activity (box-lifting).** A sliding-window peak detector on `trunk_flexion` and `knee_angle` is the simplest approach. Estimated 2–3 days including threshold tuning against real footage. This would unlock the "repeated >4×/minute" branch of both the RULA muscle-use and REBA activity-score adjustments.
4. **Threshold-tuning pass for TaskRecognition on box-lifting footage.** Collect 5–10 minutes of labelled footage, compare predictions, adjust means/sigmas. Estimated 2–3 days.

### Bigger questions (requires decision)

5. **Should the cycle/repetition counter be general (any task) or specific (lifting only)?** A general counter requires either per-task thresholds or a learned detector — 1–2 weeks.
6. **Is a full classifier needed for TaskRecognition?** Not yet. Try threshold-tuning first (step 4).
7. **Multi-person support.** Not currently scoped. Needs YOLO-pose evaluation with a CPU benchmark.
