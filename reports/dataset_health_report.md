# ErgoVigilance — Training Dataset Health Report

_Generated 2026-08-07 23:06 from `data\processed\reba_features.csv`._

## Overview

- **Samples:** 30,698
- **Columns:** 23 (21 features + labels)
- **Sources:** 21,960 distinct H3.6M subjects/sequences, 7 max samples per source

## Per-feature quality

| feature | NaN rate | min | p25 | median | p75 | max |
|---|---|---|---|---|---|---|
| neck_flexion | 0.0% | 0.0 | 0.0 | 0.0 | 0.4 | 173.9 |
| trunk_flexion | 0.0% | 0.0 | 2.2 | 5.2 | 12.6 | 178.9 |
| left_shoulder_elev | 0.0% | 0.0 | 5.7 | 17.2 | 34.4 | 180.0 |
| right_shoulder_elev | 0.0% | 0.0 | 5.8 | 17.6 | 35.5 | 180.0 |
| shoulder_symmetry | 0.0% | 0.0 | 4.0 | 10.5 | 25.4 | 100.0 |
| alignment_deviation | 0.0% | 0.0 | 0.0 | 0.0 | 0.4 | 203.6 |
| knee_angle | 0.0% | 0.0 | 138.9 | 165.5 | 174.6 | 180.0 |
| elbow_flexion_angle | 0.0% | 0.0 | 0.0 | 99.0 | 146.1 | 179.6 |
| upper_arm_angle_from_vertical | 0.0% | 0.0 | 0.0 | 13.2 | 38.5 | 180.0 |
| forward_head_posture | 0.0% | 0.0 | 0.0 | 0.0 | 0.0 | 936.9 |
| head_tilt_angle | 0.0% | 0.0 | 0.0 | 0.0 | 0.0 | 180.0 |
| stance_stability | 0.0% | 0.0 | 0.4 | 0.6 | 0.8 | 1.0 |
| weight_shift_offset | 0.0% | 0.0 | 5.6 | 13.0 | 27.5 | 672.2 |

## Labels

| band | count | share |
|---|---|---|
| HIGH | 5,460 | 17.8% |
| MEDIUM | 25,238 | 82.2% |

## Rule-based risk (for comparison)

| rule_risk | count | share |
|---|---|---|
| HIGH | 24,564 | 80.0% |
| LOW | 1,037 | 3.4% |
| MEDIUM | 5,097 | 16.6% |

## Landmark visibility

- **Full trainable-feature visibility** (no NaN across all 13 trainable features): **30,698** (100.0%)
- **Partial visibility** (≥1 trainable feature NaN): 0 (0.0%)
- **Always NaN on COCO-derived keypoints:** finger_spread_ratio, wrist_deviation_angle, hand_reach_ratio (no finger/foot landmarks in source data)

## Trainability

- **Dropna-safe training rows** (trainable features complete): 30,698
- **Target classes:** 2 in the raw REBA band (LOW absent because the dataset's minimum REBA score is 2); the 3-class LOW/MEDIUM/HIGH target used for training is derived in `scripts/train_svm.py::reba_score_to_band` (2-3 LOW, 4-7 MEDIUM, 8+ HIGH) → LOW 9,802, MEDIUM 15,436, HIGH 5,460
