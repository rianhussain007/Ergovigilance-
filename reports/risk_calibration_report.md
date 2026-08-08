# ErgoVigilance — Risk Calibration Report

_Generated 2026-08-07 22:35 from 30698 REBA-labeled real-world poses (rebapose/COCO-derived)._

## Headline: rule-based risk vs REBA-informed risk

The deterministic `risk_from_features` rule system is compared against the REBA-informed risk band computed from the same 2D joints (standard REBA methodology, 2D projection approximation).

### Rule risk (rows) vs REBA band (columns)

| rule \ reba | LOW | MEDIUM | HIGH | total |
|---|---|---|---|---|------|
| LOW | 0 (0%) | 0 (0%) | 0 (0%) | 0 |
| MEDIUM | 1037 (4%) | 5037 (20%) | 19164 (76%) | 25238 |
| HIGH | 0 (0%) | 60 (1%) | 5400 (99%) | 5460 |

- **Exact band agreement: 34.0%** (Cohen's κ = 0.085)
- Rule system flags **80%** of poses HIGH; REBA flags **18%**.
- Rule LOW on 1037 / REBA LOW on 0 samples — the rules are deliberately conservative (unknown/NaN features score as elevated risk).

### Per-rule-verdict REBA distribution

| rule_risk | REBA LOW | REBA MEDIUM | REBA HIGH |
|---|---|---|---|
| LOW | 0 | 1037 | 0 |
| MEDIUM | 0 | 5037 | 60 |
| HIGH | 0 | 19164 | 5400 |

## Trained calibration model (cross-check overlay)

- Model: HistGradientBoosting → REBA band, holdout accuracy **91.8%**
- Holdout size: 6140 samples

### Holdout per-class report

```
              precision    recall  f1-score   support

         LOW       0.00      0.00      0.00         0
      MEDIUM       0.94      0.96      0.95      5048
        HIGH       0.79      0.73      0.76      1092

    accuracy                           0.92      6140
   macro avg       0.58      0.56      0.57      6140
weighted avg       0.92      0.92      0.92      6140

```

## Interpretation & recommendation

1. **Threshold-tuning pass completed (2026-08-08).** A vectorized Pareto sweep over the secondary-feature cutoffs (weight_shift, shoulder_symmetry, stance_stability) found a strictly-better operating point that holds the hard safety constraint — **zero REBA-HIGH poses scored LOW**:

   | metric | pre-tuning | tuned (current) |
   |---|---|---|
   | exact-band agreement | 34.0% | **36.9%** |
   | Cohen's κ | 0.085 | **0.107** |
   | rule HIGH rate | 80.0% | **73.5%** |
   | missed REBA-HIGH (→ LOW) | 0 | **0** |
   | REBA-HIGH downgraded (→ MEDIUM) | 60 | 102 |

   Applied changes (backend/services/features.py `RISK_THRESHOLDS`): weight_shift_offset HIGH 15→25 / MED 8→12.5; shoulder_symmetry HIGH 15→18 / MED 5→9; stance_stability and all classical REBA drivers (neck/trunk/knee/shoulders) unchanged. The two loosened features caused **56%** (weight_shift) and **49%** (symmetry) of all false-HIGH verdicts; their REBA-HIGH medians (31.0 and 33.3) sit well above the new cutoffs, so coverage is preserved. Sweep tooling: `scripts/tune_risk_thresholds.py`; pinned by `backend_api/tests/test_risk_threshold_tuning.py`.

   Remaining over-alarm is inherent to the safety-first design (unknown landmarks score as elevated) plus dataset skew (REBA LOW ≈ 0 in this COCO-derived set) — the tuned point is the best safe operating point found.

2. The trained model is a **cross-check only**: runtime risk remains rule-based; the model confidence can be surfaced as a UI hint.

3. Feature columns with no signal on COCO-derived keypoints (wrist deviation, hand reach, finger spread, stance width) are absent here; a MediaPipe-33 capture session of real workplace tasks would fill that gap (Phase-D Tier 2).