# Posture Thresholds &amp; Guidance

## Feature Thresholds

| Feature | Unit | MEDIUM threshold | HIGH threshold | Direction |
|---------|------|-----------------|---------------|-----------|
| `neck_flexion` | degrees | > 10 | > 30 | forward |
| `trunk_flexion` | degrees | > 20 | > 60 | forward |
| `left_shoulder_elev` | degrees | > 30 | > 60 | elevated |
| `right_shoulder_elev` | degrees | > 30 | > 60 | elevated |
| `shoulder_symmetry` | percent | > 5 | > 15 | imbalance |
| `alignment_deviation` | percent | > 10 | > 25 | misalignment |
| `knee_angle` | degrees | < 150 | < 100 | bent (inverted) |

## Risk Score Computation

ContextIntelligenceEngine computes a risk score 0-100:
1. Each feature scored 0-100 via linear interpolation between MEDIUM/HIGH thresholds
2. `base_risk = max` of all feature scores
3. Add context modifiers: `duration_penalty + task_modifier + fatigue_modifier`
4. Add `confidence_modifier`
5. Clamp to [0, 100]
6. Classify: HIGH (>= 70), MEDIUM (>= 30), LOW

## Safety States

- HIGH -> CRITICAL (with hysteresis)
- MEDIUM+SAFE -> OBSERVE
- LOW+OBSERVE -> SAFE
- LOW+CRITICAL -> RECOVERY
- LOW+RECOVERY -> SAFE

## Fatigue Model

Exponential curve: `base_fatigue = 100 * (1 - e^(-0.42 * minutes / 30))`
- Exposure penalty: `high_risk_minutes * 0.8`
- Recovery: `low_risk_minutes * 1.2`
- Task modifier: 0.0-0.6 per minute
- Final modifier: `score * 0.2` (range 0-20)
- Levels: fresh (< 20), mild (20-49), moderate (50-74), severe (>= 75)

## Exposure Tracker

Weighted body-region accumulation: neck=1.5x, trunk=1.3x, shoulder=1.2x, alignment=1.1x, knee=1.0x.
Duration penalty = `min(total_high_risk_seconds / 10, 30)`.

## Corrective Guidance by Area

### Head and Neck
- HIGH: "Your head is too far forward — tuck your chin slightly back"
- MEDIUM: "Your neck is slightly forward — try to bring your ears above your shoulders"
- LOW: "Good — your neck position looks natural"

### Back (Trunk)
- HIGH: "You are hunching forward significantly — sit up straight and push your lower back into the chair"
- MEDIUM: "You are leaning forward slightly — try to straighten your back"
- LOW: "Good — your back posture looks upright"

### Shoulders
- HIGH: "Your shoulders are raised — relax them down away from your ears"
- MEDIUM: "Your shoulders are slightly tense — try to drop them and relax"
- LOW: "Good — your shoulders look relaxed"

### Shoulder Balance
- HIGH: "Your shoulders are uneven — check if you are leaning to one side"
- MEDIUM: "Slight shoulder tilt detected — try to sit evenly on both sides"
- LOW: "Good — your shoulders are level"

### Overall Alignment
- HIGH: "Your head is not aligned with your hips — sit back in your chair and sit tall"
- MEDIUM: "Slight forward lean detected — imagine a string pulling the top of your head upward"
- LOW: "Good — your overall alignment looks balanced"

## Generic Recommendations (always included)
1. Take a short movement break every 30 minutes.
2. Set your screen so the top edge is around eye level.
3. Use a small hourly reminder to reset your posture.
