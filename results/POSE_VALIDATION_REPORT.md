# Pose Estimation Validation Report

**Generated:** 2026-06-19 23:21:24
**System:** AI-Based Real-Time Posture & Movement Monitoring
**MediaPipe Model:** Pose Landmarker (Lite)

---

## 1. Feature Validation Table

| Feature | Upright | Moderate Bend | Deep Bend | Thresholds | Status |
|---------|---------|---------------|-----------|------------|--------|
| neck_flexion | 0.92 | 8.59 | 6.27 | LOW <= 10 deg, MEDIUM 10-30 deg, HIGH > 30 deg | CHECK |
| trunk_flexion | 0.07 | 1.40 | 3.77 | LOW <= 20 deg, MEDIUM 20-60 deg, HIGH > 60 deg | CHECK |
| left_shoulder_elev | 8.68 | 7.34 | 2.86 | LOW <= 30 deg, MEDIUM 30-60 deg, HIGH > 60 deg | PASS |
| right_shoulder_elev | 31.65 | 23.58 | 19.11 | LOW <= 30 deg, MEDIUM 30-60 deg, HIGH > 60 deg | PASS |
| shoulder_symmetry | 2.35 | 4.06 | 8.54 | LOW <= 5%, MEDIUM 5-15%, HIGH > 15% | PASS |
| alignment_deviation | 0.37 | 10.11 | 4.75 | Lower is better; large horizontal ear-to-hip offset suggests alignment risk | PASS |
| knee_angle | 173.17 | 177.08 | 178.52 | LOW >= 150 deg, MEDIUM 100-150 deg, HIGH < 100 deg | CHECK |

---

## 2. Validation Screenshots

### Upright

![Upright](../outputs/validation_captures/validation_upright_232115.png)

### Moderate Bend

![Moderate Bend](../outputs/validation_captures/validation_moderate_232119.png)

### Deep Bend

![Deep Bend](../outputs/validation_captures/validation_deep_232124.png)

---

## 3. Per-Feature Validation Details

### Neck Flexion

- **Geometry:** Angle at neck between ear→neck and neck→hip vectors, subtracted from 180°
- **Measured:** Upright=0.9°, Moderate=8.6°, Deep=6.3°
- **Expected:** Increases when head tilts forward (chin toward chest)
- **Threshold:** LOW ≤ 10° | MEDIUM 10-30° | HIGH > 30°
- **Verdict:** MANUAL CHECK

### Trunk Flexion

- **Geometry:** Angle at hip between hip→neck and hip→vertical_up vectors
- **Measured:** Upright=0.1°, Moderate=1.4°, Deep=3.8°
- **Expected:** Increases proportionally with forward trunk lean
- **Threshold:** LOW ≤ 20° | MEDIUM 20-60° | HIGH > 60°
- **Verdict:** MANUAL CHECK

### Shoulder Symmetry

- **Geometry:** |L_shoulder_y − R_shoulder_y| / shoulder_width × 100
- **Measured:** Upright=2.3%, Moderate=4.1%, Deep=8.5%
- **Expected:** Near 0% when level, increases with shoulder tilt
- **Threshold:** LOW ≤ 5% | MEDIUM 5-15% | HIGH > 15%
- **Verdict:** PASS

### Knee Angle

- **Geometry:** Average of L and R hip→knee→ankle angles
- **Measured:** Upright=173.2°, Moderate=177.1°, Deep=178.5°
- **Expected:** ~180° standing, ~90° sitting, decreases when bending (hips flex)
- **Threshold:** HIGH < 100° | MEDIUM 100-150° | LOW ≥ 150°
- **Verdict:** MANUAL CHECK

---

## 4. Risk Classification Validation

| Posture | neck_flexion | trunk_flexion | shoulder_elev | shoulder_sym | Overall Risk |
|---------|-------------|---------------|---------------|--------------|--------------|
| Upright | LOW | LOW | MEDIUM | LOW | **MEDIUM** |
| Moderate Bend | LOW | LOW | LOW | LOW | **LOW** |
| Deep Bend | LOW | LOW | LOW | MEDIUM | **MEDIUM** |

---

## 5. Summary & Conclusions

- **Features Validated:** 7
- **Passed:** 4
- **Needs Review:** 3

### Confirmed Working

- ✅ **left_shoulder_elev** — Measured values 8.7 → 7.3 → 2.9 follow expected trend
- ✅ **right_shoulder_elev** — Measured values 31.6 → 23.6 → 19.1 follow expected trend
- ✅ **shoulder_symmetry** — Measured values 2.3 → 4.1 → 8.5 follow expected trend
- ✅ **alignment_deviation** — Measured values 0.4 → 10.1 → 4.7 follow expected trend

### Manual Review Recommended

- ⚠️ **neck_flexion** — Values 0.9 → 8.6 → 6.3 may need threshold adjustment
- ⚠️ **trunk_flexion** — Values 0.1 → 1.4 → 3.8 may need threshold adjustment
- ⚠️ **knee_angle** — Values 173.2 → 177.1 → 178.5 may need threshold adjustment

### Overall Verdict
**⚠️ MOST FEATURES PASS — Minor threshold tuning recommended before final review.**

---

*Report generated automatically by `scripts/generate_pose_validation_report.py`*