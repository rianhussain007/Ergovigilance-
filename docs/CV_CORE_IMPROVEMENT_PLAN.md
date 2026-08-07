# CV Core & ML Improvement Plan — ErgoVigilance

**Status:** Phases A–C shipped (2026-08-07). Phase D (ML models) still awaits your
dataset-tier decision.
**Goal:** a stronger real-time ergonomics worker-risk-management core — better landmark
utilization, richer biomechanical features, a properly wired RULA score, and (phase D)
trained models for task & risk classification.

---

## Execution status (2026-08-07)

### ✅ Phase A — activated landmarks + 8 new features (shipped)
- `FEATURE_COLUMNS` now **17** (canonical in `backend/core/constants.py`, `features.py`
  re-exports — drift fixed). Landmarks activated: **nose, index (19,20), thumb (21,22),
  pinky (17,18), heels (29,30), foot_index (31,32)**.
- New features: `forward_head_posture`, `head_tilt_angle`, `wrist_deviation_angle`,
  `stance_stability`, `weight_shift_offset`, `hand_reach_ratio`, `finger_spread_ratio`,
  `stance_width_ratio` — with `FEATURE_DEPENDENCIES`, `FEATURE_THRESHOLDS`, NaN/`unavailable`
  semantics, and COCO-17 graceful degradation (fingers/feet absent → NaN, never a crash).
- **Two pre-existing angle-inversion bugs fixed while validating:** `head_tilt_angle` and
  `upper_arm_angle_from_vertical` both returned ~180° for a neutral pose (every frame
  scored HIGH). Now `abs(180 − angle)` → 0° neutral.
- `_point()` hardened against short/corrupt keypoint rows (NaN point instead of IndexError).

### ✅ Phase B — signal quality (shipped)
- EMA temporal smoothing in `PoseEngine` (α configurable via
  `ERGOVIGILANCE_FEATURE_SMOOTHING`, default 0.7); motion features and NaN propagate
  through untouched; smoothing resets when the person leaves frame.
- Reviewer-caught fix: NaN (unavailable) features now propagate NaN through the smoothed
  vector instead of keeping a stale value, so issues/task-recognition can't fire on ghosts.
- Heavy pose model: **deferred** (decision point still open; default remains `lite`).

### ✅ Phase C — risk & RULA wiring (shipped)
- `risk_from_features` scores the new features (FHP, head tilt, wrist deviation, stance,
  weight shift) with literature-aligned thresholds; `risk_breakdown` renders them;
  **RULA Table B now uses real wrist deviation**, neck row uses head tilt, legs row uses stance.
- Context engine: `engine.py` feature sets + `exposure.py` duration penalties extended.
- `guidance.py`: 5 new posture areas (NaN-safe); `issue_detection.py`: 5 new named issues;
  `session_analytics.py`: 5 new averages in the summary payload.
- Frontend: live dashboard list (`live.py` `feature_configs`), FeatureGraph, ReplayPage,
  VideoReviewPage maps + LiveMonitoring N/A hints extended; unavailable features now
  report status `"unavailable"` instead of `"good"`.

### ⏳ Phase D — ML models (blocked on your decision)

---

## 0. Current state (what the investigation found)

- **Landmarks used: 14 of the 33 MediaPipe outputs** — ears (7,8), shoulders (11,12),
  elbows (13,14), wrists (15,16), hips (23,24), knees (25,26), ankles (27,28).
- **Unused:** nose (0), eyes (1–6), mouth (9,10), fingers — index (19,20), thumb (21,22),
  pinky (17,18), heels (29,30), foot_index (31,32).
- **9 features** → rule-based `risk_from_features` + `compute_rula_informed_score`.
  Documented RULA limitation: *wrist deviation/twist and force/load are defaulted* —
  Table B is not fully informed.
- **Task recognition:** Gaussian scorer, 5 classes, uses elbows/wrists/hips/knees only.
- **ML artifacts:** `pose_landmarker_lite.task` (production pose model),
  `svm_model.pkl` (task classifier, training-only), `best_model.pkl` (risk, archived —
  production is rule-based). `FEATURE_COLUMNS` has **drift**: `backend/core/constants.py`
  (7 features) vs `backend/services/features.py` (9).
- **Ripple surface for new features:** `feature_scores` flows to the frontend as a generic
  `Record<string, number>` (auto), but the live feature panels, VideoReview/Replay maps,
  DigitalTwin, context-engine scoring and recommendations hardcode feature names and must
  be extended. New features also need `FEATURE_THRESHOLDS` + `FEATURE_DEPENDENCIES` entries.
- The pipeline already has the right scaffolding to absorb this: per-feature
  `unavailable`/`approximate` flags, hip-free fallbacks, and a px/s motion signal.

---

## Phase A — Activate landmarks + new features (no data needed)

Activate the unused landmarks and add deterministic biomechanical features. MediaPipe emits
all 33 landmarks at no extra inference cost; only the feature math changes.

| New feature | Landmarks used (new) | Ergonomics value |
|---|---|---|
| `forward_head_posture` | nose (0), ears, shoulders | Classic **FHP** metric (ear/nose offset vs shoulder) — screen-work neck strain |
| `head_tilt_angle` | nose, eyes, ears, shoulders | Monitor-height proxy (looking down vs up) — complements neck flexion |
| `wrist_deviation_angle` | **index fingers (19,20)**, thumb (21,22), wrist, elbow | **RULA Table B wrist deviation** — the biggest current RULA gap |
| `hand_reach_ratio` | **index fingertips (19,20)**, shoulder, hip | Better Reaching + grasping detection (fingertip vs wrist-based) |
| `finger_spread` / `hand_use_intensity` | index + thumb spread | Tool use / typing / gripping proxy for task recognition |
| `squat_depth` / `stance_width_ratio` | **heels (29,30), foot_index (31,32)**, ankles | Lifting stability, deep-squat detection, weight distribution |
| `weight_shift_offset` | mid-ankle vs mid-hip horizontal offset | Postural sway / load-balance proxy for long sessions |

Per feature: `FEATURE_DEPENDENCIES` (with the new landmarks), `FEATURE_THRESHOLDS`,
unavailable/approximate handling (fingers can be low-visibility when hands are at sides —
fall back to wrist-based metrics and mark `approximate`, reusing the existing machinery).

**Also:** fix the `FEATURE_COLUMNS` drift — `backend/core/constants.py` is the single
source of truth; `features.py` re-exports it (matches the existing constants pattern).

## Phase B — Signal quality (no data needed)

1. **Temporal smoothing** in `PoseEngine.process_frame` — exponential moving average
   (configurable α) on the feature vector before risk scoring. Kills landmark jitter →
   fewer false alert flaps (the #1 real-world complaint). Skip smoothing for the velocity
   features.
2. **Optional heavier pose model** — `pose_landmarker_heavy.task` behind the existing
   `POSE_MODEL_PATH` config (default stays `lite` for FPS). More accurate landmark
   placement in industrial scenes. Ships with `MANIFEST.json` update + `verify_models`.
   ~2–3× inference cost; decision point below.
3. **Confidence gating for new landmarks** — extend the per-feature visibility checks to
   the newly activated landmarks (fingers/heels get lower minimum-visibility thresholds +
   approximate fallbacks).

## Phase C — Risk engine & RULA wiring (no data needed)

1. Wire new features into `risk_from_features` (FHP, wrist deviation, stance) with
   defensible thresholds from the ergonomics literature (RULA/REBA tables).
2. **Complete the RULA score** — Table B wrist row now uses real `wrist_deviation_angle`
   instead of the default; neck row can use `head_tilt_angle`; legs row can use
   `squat_depth`. `is_partial_score` stays for genuinely missing landmarks.
3. **Context engine + recommendations + guidance** — add the new features to per-feature
   scoring and recommendation templates (e.g., "reduce wrist deviation — keep wrist
   straight while gripping").
4. **Frontend** — extend the live feature panels (LiveMonitoring), VideoReview/Replay
   feature maps, and DigitalTwin to render the new features with colors/thresholds.
5. **Reports** — session analytics averages and CSV/PDF exports gain the new features.

## Phase D — ML models (needs data — see §1)

Two tracks, both **layered on top of** the deterministic core (which stays authoritative —
safety-critical interpretability):

1. **Task classifier v2** — replace/augment the Gaussian scorer with a trained model
   (HistGradientBoosting or small MLP) over the *augmented* feature set:
   - **Bootstrap without external data:** synthetic labeled poses generated from the
     rule engine (diagnose-style sweeps of the Gaussian + new features).
   - **Real data (recommended):** CP3D (0.5M 3D samples, 14 construction activities,
     REBA/RULA-mapped, public GitHub) or DyWHSE (warehouse/heavy industry) or the user's
     own recordings (`recordings/` + `outputs/sessions` — the system already captures
     them; label via rule engine + human review).
   - Gaussian remains the interpretable fallback; model output gated by confidence.
2. **Risk classifier / threshold calibration** — train on expert-labeled RULA/REBA data
   to *validate and calibrate* the rule thresholds (not to replace them):
   - **REBA_Dataset for Human3.6m** (shakhaout/REBA_Dataset — public GitHub; H3.6M itself
     needs academic registration).
   - **Industrial Multimodal RULA dataset** (Cruciata et al., Sensors 2025, CC BY 4.0).
   - Output: a calibration report comparing rule-based risk vs expert labels, plus
     optional model-based cross-check surfaced as "model confidence" in the UI.

---

## 1. Dataset answer (direct)

**Phases A–C need NO datasets** — they are deterministic geometry from landmarks the
model already outputs.

**Phase D needs data**, and there are three tiers:
- **Tier 0 (start today, no downloads):** synthetic pose generation from the rule engine
  for the task classifier; the system's own `recordings/` + session files as a
  self-supervised source.
- **Tier 1 (recommended, public):** CP3D (tasks, public GitHub), REBA_Dataset (risk
  labels, public GitHub), Industrial Multimodal RULA (CC BY 4.0). I can fetch and prepare
  these once you approve downloads.
- **Tier 2 (best fidelity, needs you):** a short captured session of your actual
  workplace tasks (5–10 min per task type) — the highest-value training data because it
  matches your camera angle, lighting, and work content. I'd need you to run a capture
  (the system already has the tooling).

## 2. Decisions needed before execution

1. **Go/no-go per phase.** Recommended order: **A + B → C → D** (A–C are self-contained,
   no data, biggest measurable win; D is gated on the dataset choice).
2. **Heavy vs lite pose model** (Phase B): lite default (≈15–20 FPS) vs heavy optional
   (slower, more accurate in cluttered industrial scenes).
3. **Phase D data tier** (Tier 0/1/2) and whether to keep the Gaussian as the visible
   task output or let the trained model take over (I recommend model-primary with
   Gaussian fallback).
4. **Risk model role**: calibration-only (recommended, safety) vs replacing rule tables.

## 3. Validation

- Unit tests for every new feature (synthetic keypoint fixtures, like `test_wrist_velocity.py`).
- Extended `test_task_recognition.py` (finger-based reaching/typing cases).
- Extended `scripts/generate_pose_validation_report.py` to capture the new features.
- Keep the 36-test pytest suite + 22 legacy scripts green (fresh `python:3.12` container
  replica, as used for the CI fixes).
- Manual webcam before/after comparison on your machine (Phase A/B/C), and a small
  labeled holdout set for Phase D models.

## 4. Effort estimate (relative)

- Phase A: ~1 day (features + tests + thresholds) + frontend/report wiring (~½ day).
- Phase B: ~½ day (smoothing + config) + model-file download/MANIFEST (~½ day).
- Phase C: ~½–1 day (risk/RULA wiring + context/recommendations + frontend).
- Phase D: 1–2 days per model (data prep → train → eval → integrate), plus your
  captured data if Tier 2.
