# Task-Conditional Risk Thresholds

## Overview

ErgoVigilance uses **task-conditional risk thresholds** — the joint-angle cutoffs that determine when a posture is scored LOW / MEDIUM / HIGH change based on the detected task class. This ensures that a 30° trunk flexion during a lifting task (expected and biomechanically normal) is scored differently from the same angle during seated assembly work (abnormal and risky).

The task classifier is a **deterministic HistGradientBoosting model** (the existing `task_model_v2.pkl`). It is never an LLM — it runs per-frame in <1ms as part of the pose processing pipeline. When its confidence is below 50%, the system falls back to the baseline (neutral) thresholds and displays "Task: Uncertain" in the UI.

**Ollama's role is limited to generating a plain-language explanation** of an already-computed result (task label + risk score + threshold table). It is never in the critical path for classification or risk scoring.

---

## Task Classes (7-class model)

| # | Task Label | Ergonomic Method | Rationale |
|---|-----------|-----------------|-----------|
| 1 | **Neutral Standing** | Baseline (default thresholds) | Low-risk reference posture; all joints within normal range. |
| 2 | **Assembly Work** | RULA-informed (upper-body focus) | Repetitive fine-motor work: neck, shoulder, wrist strain dominate. |
| 3 | **Reaching** | Blended (shoulder + weight-shift) | Dynamic arm extension: shoulder elevation and trunk flexion are primary risks. |
| 4 | **Lifting / Picking** | REBA-informed (whole-body) | Load-bearing task: trunk flexion, knee angle, weight shift, stance stability are critical. |
| 5 | **Inspection** | RULA-informed (upper-body focus) | Sustained visual task: head-forward posture and neck flexion dominate. |
| 6 | **Seated Work** | RULA-informed (upper-body focus) | Desk/workbench posture: neck, trunk, wrist strain with seated knee angle. |
| 7 | **Walking / Moving** | Baseline (relaxed thresholds) | Dynamic activity: transient postures, balance-focused scoring. |

---

## Threshold Tables

All thresholds are (MEDIUM, HIGH) cutoffs.  Features not listed for a task inherit from the baseline `RISK_THRESHOLDS`.

### Lifting / Picking — REBA-Informed (Whole-Body, Load-Bearing)

| Feature | MEDIUM | HIGH | Notes |
|---------|--------|------|-------|
| `neck_flexion` | 10.0° | 25.0° | Moderate — REBA Table A neck bands |
| `trunk_flexion` | 20.0° | 45.0° | **Tighter** — REBA trunk assessment: <20° low, 20-45° moderate, >45° high |
| `shoulder_elev` | 30.0° | 55.0° | Slightly relaxed (arms carry load, some elevation expected) |
| `knee_angle` | 155.0° | 120.0° | **Tighter** — REBA leg assessment: deep knee bend under load = high risk |
| `stance_stability` | 0.65 | 0.40 | **Tighter** — balance matters under load |
| `weight_shift_offset` | 10.0 | 20.0 | **Tighter** — asymmetric loading is dangerous |

### Assembly Work — Relaxed Baseline (Assembly + Heavy-Lifting Profile)

**Mend rule (2026-08):** the operator profile is an **assembly worker who also
performs heavy lifting**. Normal assembly work therefore scores on the SAME
relaxed bands the standard RULA/REBA gate uses (calibration `RELAXED`
`feature_cutoffs`) — a routine assembly posture (moderate neck flexion, arms at
bench height) no longer over-alarms. The previous table (neck 8/22, shoulder
25/50, wrist 4/12) was **stricter than the standard gate itself**, which is what
manufactured yellow/red on slight movement. Heavy lifting is scored by the
REBA-grounded Lifting / Picking table below.

| Feature | MEDIUM | HIGH | Notes |
|---------|--------|------|-------|
| `neck_flexion` | 15.0° | 35.0° | Relaxed baseline (matches standard gate) |
| `trunk_flexion` | 30.0° | 70.0° | Relaxed baseline |
| `shoulder_elev` | 35.0° | 60.0° | Relaxed baseline |
| `shoulder_symmetry` | 9.0 | 18.0 | Same as tuned baseline |
| `knee_angle` | 140.0° | 95.0° | Relaxed baseline |
| `forward_head_posture` | 15.0 | 28.0 | Relaxed baseline |
| `head_tilt_angle` | 15.0° | 28.0° | Relaxed baseline |
| `wrist_deviation_angle` | 10.0° | 25.0° | Relaxed baseline |
| `stance_stability` | 0.6 | 0.45 | Same as baseline |
| `weight_shift_offset` | 15.0 | 30.0 | Same as baseline |

### Reaching — Blended (Shoulder + Weight-Shift)

| Feature | MEDIUM | HIGH | Notes |
|---------|--------|------|-------|
| `trunk_flexion` | 18.0° | 50.0° | **Tighter** — forward reach involves trunk |
| `shoulder_elev` | 22.0° | 45.0° | **Tighter** — reaching elevates shoulders |
| `shoulder_symmetry` | 7.0 | 15.0 | **Tighter** — one-arm reach = asymmetry |
| `stance_stability` | 0.65 | 0.45 | **Tighter** — balance during reach |
| `weight_shift_offset` | 10.0 | 20.0 | **Tighter** — reaching shifts weight |

### Inspection — RULA-Informed (Visual Task)

| Feature | MEDIUM | HIGH | Notes |
|---------|--------|------|-------|
| `neck_flexion` | 8.0° | 25.0° | **Tighter** — sustained neck flexion looking down |
| `shoulder_elev` | 28.0° | 55.0° | Slightly tighter |
| `forward_head_posture` | 8.0 | 18.0 | **Tighter** — inspecting = head forward |
| `head_tilt_angle` | 8.0° | 18.0° | **Tighter** — looking at angles |

### Walking / Moving — Baseline (Dynamic Activity)

| Feature | MEDIUM | HIGH | Notes |
|---------|--------|------|-------|
| `neck_flexion` | 12.0° | 30.0° | Relaxed (movement = transient postures) |
| `trunk_flexion` | 22.0° | 60.0° | Relaxed |
| `shoulder_elev` | 32.0° | 60.0° | Relaxed |
| `knee_angle` | 148.0° | 110.0° | Slightly tighter (gait analysis) |
| `stance_stability` | 0.6 | 0.35 | **Tighter** — walking = dynamic balance |

### Seated Work — RULA-Informed (Desk/Workbench)

| Feature | MEDIUM | HIGH | Notes |
|---------|--------|------|-------|
| `neck_flexion` | 8.0° | 22.0° | **Tighter** — desk/workbench neck strain |
| `trunk_flexion` | 18.0° | 50.0° | **Tighter** — seated trunk posture matters |
| `shoulder_elev` | 25.0° | 50.0° | **Tighter** — repetitive arm work |
| `knee_angle` | 100.0° | 80.0° | **Tighter** — seated knee angle critical |
| `forward_head_posture` | 8.0 | 18.0 | **Tighter** — sustained desk posture |
| `wrist_deviation_angle` | 4.0° | 12.0° | **Tighter** — keyboard/tool use |
| `weight_shift_offset` | 10.0 | 20.0 | **Tighter** — seated weight distribution |

---

## How Task Selection Works

1. **Per-frame classification**: The HistGradientBoosting model classifies the current frame's keypoints + features into one of 7 task classes with a confidence score (0–100%).

2. **Confidence gate**: If confidence ≥ 50%, the task-specific threshold table is applied. If confidence < 50%, the baseline `RISK_THRESHOLDS` are used and the UI displays "Task: Uncertain".

3. **Threshold merging**: Task-specific thresholds are merged onto the baseline defaults — any feature not overridden by the task table inherits the calibrated baseline value.

4. **Task modifier**: The existing additive task modifier (Neutral +0, Walking +2, Inspection +3, Seated +4, Assembly +5, Reaching +8, Lifting +12) is applied ON TOP of the task-specific thresholds. The modifier penalizes tasks that inherently carry more biomechanical load.

---

## Graded Duration-Exposure Curve (doc §8)

RULA/REBA only add a coarse binary "held > 1 minute" muscle-use point. The
duration penalty instead uses a **graded exposure curve** from
posture-endurance research so a sustained posture scores materially higher than
a momentary one:

| Sustained high-risk time | Penalty | Meaning |
|--------------------------|---------|---------|
| < 1 min | 0 | Grace — a momentary posture costs nothing |
| 1–5 min | 0 → 8 | "Moderate" posture — recommend holding < 1 min |
| 5–15 min | 8 → 20 | "Uncomfortable" — not recommended to sustain |
| 15–30 min | 20 → 30 | Low-back complaints onset ~15 min, rising sharply past ~30 min |
| > 30 min | 30 (cap) | Maximum penalty |

This is the mathematical version of the product's pitch: continuous monitoring
beats a point-in-time audit — the same MEDIUM-risk trunk-flexion angle held for
8 minutes scores materially higher than one held for 20 seconds, even though
RULA's own scoring table treats both identically below the 1-minute mark.

The exposure tracker accumulates high-risk seconds using the **same relaxed
calibration bands as the live risk gate** (not the published strict cutoffs), so
a mild posture can no longer be double-penalized as the session wears on.

## Insufficient-Data Rule: Assess What's Available, No Soft Floor

When the standard RULA/REBA assessment cannot run (worker partially out of
frame, landmarks too sparse), the engine no longer manufactures a MEDIUM
soft floor (legacy 20–40) from unavailable features. Instead:

- **Partial body visible (top half)** → the standard gate runs **RULA** on the
  visible upper body and scores what it can see.
- **Very few features at all** → base risk comes only from the features that
  were actually computed; unavailable features are excluded, never assumed
  risky. A worker half out of frame reads as *assessed on visible data* rather
  than *elevated because we couldn't see everything*.

This keeps the "can't confirm safe ⇒ risk" legacy behavior from manufacturing
alerts on data quality problems.

---

## Architecture Notes

- **Ollama is never in the critical path**: The LLM generates a plain-language explanation AFTER scoring is complete. A slow or failed Ollama response returns an empty string; the pipeline continues uninterrupted.

- **Deterministic classification**: The task classifier is a trained scikit-learn model with a confidence-gated Gaussian fallback. No LLM, no API call, no network dependency.

- **Threshold traceability**: Every frame's `active_rules` log includes which threshold table was used (`task_thresholds: using Lifting / Picking table (conf=87%)` or `task_thresholds: using baseline (task=Unknown, conf=12%)`), making risk decisions auditable.

- **Standard assessment preserved**: The RULA/REBA standard assessment (gated by body visibility) remains the authoritative posture-risk gate. Task-specific thresholds provide supplementary per-feature context scoring that feeds into the context intelligence engine.
