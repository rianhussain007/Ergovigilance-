# RULA & REBA Ergonomic Assessment Reference

## Overview

RULA (Rapid Upper Limb Assessment) and REBA (Rapid Entire Body Assessment) are standardized ergonomic screening tools developed by McAtamney and Corlett (RULA, 1993) and Hignett and McAtamney (REBA, 2000). They provide systematic methods for evaluating exposure to ergonomic risk factors in the workplace.

## RULA — Rapid Upper Limb Assessment

### Purpose
Evaluates upper limb biomechanical loads with emphasis on neck, trunk, and upper extremities. Designed for tasks requiring repeated static postures or awkward upper limb positions.

### Scoring System

#### Arm and Wrist Analysis (Group A)

| Posture | Score 1 | Score 2 | Score 3 |
|---------|---------|---------|---------|
| Upper Arm | 0-20° flexion | 20-45° or >90° | 45-90° |
| Lower Arm | 0-100° flexion | >100° | — |
| Wrist | 0-15° flexion/extension | >15° flexion/extension | — |

**Wrist Twist:** Mid-range = 1, End range = 2

**Muscle Use:** Static/posture held >1 min = +1, Repeated/small movements = +1

**Force/Load:** <2 kg = 0, 2-10 kg = +1, >10 kg = +2

#### Neck, Trunk, and Leg Analysis (Group B)

| Posture | Score 1 | Score 2 | Score 3 | Score 4 |
|---------|---------|---------|---------|---------|
| Neck | 0-20° flexion | >20° flexion | Twisted/侧弯 | — |
| Trunk | 0-20° flexion | 20-60° | >60° | Twisted/侧弯 |
| Legs | Weight evenly distributed | Weight unevenly | One leg supported | — |

**Activity Score:** Posture held >1 min = +1, Repeated movements = +1

### RULA Action Levels

| Score | Action Level | Risk Category | Recommended Action |
|-------|-------------|---------------|-------------------|
| 1-2 | 1 | Low | Acceptable — investigate if maintained for long periods |
| 3-4 | 2 | Medium | Investigate further — may need changes |
| 5-6 | 3 | High | Investigate and implement changes soon |
| 7 | 4 | Very High | Immediate investigation and changes required |

### ErgoVigilance Feature Mapping to RULA

| ErgoVigilance Feature | RULA Component | Correlation |
|----------------------|----------------|-------------|
| `neck_flexion` | Neck score | Direct — both measure forward head posture |
| `trunk_flexion` | Trunk score | Direct — both measure trunk forward lean |
| `shoulder_symmetry` | Shoulder elevation balance | Related — asymmetry indicates uneven loading |
| `left_shoulder_elev` / `right_shoulder_elev` | Upper arm elevation | Direct — elevated shoulders increase RULA score |
| `knee_angle` | Leg/foot support score | Indirect — affects trunk stability |

## REBA — Rapid Entire Body Assessment

### Purpose
Evaluates whole-body posture risk including trunk, neck, legs, and upper/lower extremities. More comprehensive than RULA — suitable for varied tasks and mobile workers.

### Scoring System

#### Trunk, Neck, and Legs (Group A)

| Posture | Score 1 | Score 2 | Score 3 | Score 4 | Score 5 |
|---------|---------|---------|---------|---------|---------|
| Trunk | Upright | 0-20° flexion | 20-60° | >60° | Twisted/侧弯 |
| Neck | Slight flexion | 0-20° flexion | >20° flexion | Twisted/侧弯 | — |
| Legs | Weight evenly | Weight uneven | One leg supported | Sitting | — |

**Activity Score:** Posture held >1 min = +1, Repeated small movements = +1, Rapid changes/instability = +2

#### Arms and Wrists (Group B)

| Posture | Score 1 | Score 2 | Score 3 | Score 4 |
|---------|---------|---------|---------|---------|
| Upper Arm | 0-20° | 20-45° or >90° | 45-90° | — |
| Lower Arm | 0-100° | >100° | — | — |
| Wrist | 0-15° flexion/extension | >15° flexion/extension | — | — |

**Wrist Twist:** Mid-range = 1, End range = 2

**Muscle Use:** Static/posture held >1 min = +1, Repeated movements = +1

**Force/Load:** <2 kg = 0, 2-10 kg = +1, >10 kg = +2, Shock/strong force = +3

### REBA Score Calculation

1. **Score A** = Trunk + Neck + Legs + Activity (Group A)
2. **Score B** = Upper Arm + Lower Arm + Wrist + Wrist Twist + Muscle + Force (Group B)
3. **Table C** lookup using Score A and Score B
4. **Final REBA Score** = Table C value + Activity Score

### REBA Action Levels

| Score | Risk Level | Recommended Action |
|-------|-----------|-------------------|
| 1 | Negligible risk | No action required |
| 2-3 | Low risk | Investigate — monitor for changes |
| 4-7 | Medium risk | Assessment required — implement changes soon |
| 8-10 | High risk | Investigation and changes required immediately |
| 11-15 | Very high risk | Immediate intervention — stop task if necessary |

## Key Differences: RULA vs REBA

| Aspect | RULA | REBA |
|--------|------|------|
| Body regions | Upper limb focus | Whole body |
| Lower body | Limited (legs/feet) | Full leg/foot assessment |
| Tasks suited | Repetitive upper limb | Varied, mobile tasks |
| Scoring complexity | 2 group scores | 2 group scores + Table C |
| Sensitivity | Higher for upper limb | Higher for whole body |

## Practical Application in ErgoVigilance

### How ErgoVigilance Risk Levels Map to RULA/REBA

| ErgoVigilance Level | Approximate RULA | Approximate REBA |
|--------------------|------------------|-------------------|
| LOW (score < 30) | Action Level 1 (1-2) | Negligible-Low (1-3) |
| MEDIUM (score 30-69) | Action Level 2-3 (3-6) | Medium (4-7) |
| HIGH (score ≥ 70) | Action Level 4 (7) | High-Very High (8-15) |

### Key Risk Factors Monitored

1. **Neck Flexion**: Forward head posture increases cervical spine loading
2. **Trunk Flexion**: Forward lean increases lumbar disc pressure
3. **Shoulder Elevation**: Static elevation causes muscle fatigue and impingement risk
4. **Wrist Posture**: Deviation from neutral increases carpal tunnel pressure
5. **Duration**: Prolonged exposure amplifies all posture risks

### Corrective Hierarchy (REBA-based)

1. **Eliminate** the risk (redesign task/workspace)
2. **Reduce** exposure (rotation, breaks, automation)
3. **Redesign** workstation (adjust heights, angles)
4. **Use PPE** (last resort — wrist supports, etc.)

## References

- McAtamney, L., & Corlett, E. N. (1993). RULA: A survey method for the investigation of work-related upper limb disorders. Applied Ergonomics, 24(2), 91-99.
- Hignett, S., & McAtamney, L. (2000). Rapid Entire Body Assessment (REBA). Applied Ergonomics, 31(2), 201-205.
- Occupational Safety and Health Administration (OSHA). Ergonomic Guidelines for Manual Material Handling.
- Canadian Centre for Occupational Health and Safety (CCOHS). RULA/REBA Assessment Tools.
