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

1. The rule system over-alarms on normal-activity poses relative to the REBA-informed band — expected for a safety-first design (unknown → elevated), but worth a threshold-tuning pass using this dataset before production claims.
2. The trained model is a **cross-check only**: runtime risk remains rule-based; the model confidence can be surfaced as a UI hint.
3. Feature columns with no signal on COCO-derived keypoints (wrist deviation, hand reach, finger spread, stance width) are absent here; a MediaPipe-33 capture session of real workplace tasks would fill that gap (Phase-D Tier 2).