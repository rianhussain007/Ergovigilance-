# Industrial Ergonomic Recommendation Engine — v1

---

## Overview

The recommendation engine translates detected posture issues into two-tiered, assembly-line-specific guidance: **Worker Actions** (immediate, self-directed corrections) and **Supervisor / Workplace Interventions** (engineering and administrative controls). The guidance targets repetitive tasks, workstation design, lifting mechanics, fatigue reduction, and injury prevention in industrial environments.

---

## Architecture

```
features → detect_posture_issues() → list[dict] of issues
                                          │
                                          ▼
                                 get_recommendations(issues)
                                          │
                                          ▼
                              list[dict] enriched with:
                                worker_actions[]
                                supervisor_actions[]
                                          │
                                          ▼
                              format_recommendations_text()
                              live_demo.py GUIDANCE panel
```

The engine is a pure lookup layer — it maps each issue name to a pre-authored set of actions. No feature values or thresholds are used in recommendation logic, keeping the system simple and auditable.

---

## Output Format

```python
{
    "issue": "Excessive Trunk Flexion",
    "severity": "HIGH",
    "worker_actions": [
        "Sit upright with your lower back pressed fully against the chair backrest...",
        "When leaning forward to reach parts, hinge from the hips (not the waist)...",
        ...
    ],
    "supervisor_actions": [
        "Bring work surface closer to the worker by repositioning parts bins...",
        "Provide height-adjustable workstations so the worker can alternate...",
        ...
    ],
}
```

---

## Per-Issue Guidance

### 1. Excessive Neck Flexion

| Role | Actions |
|---|---|
| **Worker** | 1. Adjust monitor/task target to eye level<br>2. Chin-tuck exercise every 15 min<br>3. Bring reading material up, not head down<br>4. Alternate gaze between hands and neutral |
| **Supervisor** | 1. Raise shelves/bins 15-20 cm<br>2. Install tilt stands or document holders<br>3. Micro-break prompts every 20 min<br>4. Redesign cell layout for elbow-height parts |

### 2. Excessive Trunk Flexion

| Role | Actions |
|---|---|
| **Worker** | 1. Sit upright with back fully supported<br>2. Hinge from hips, keep back straight<br>3. Stand and walk 30 s every 20 min<br>4. Shift weight foot-to-foot, use anti-fatigue mat |
| **Supervisor** | 1. Reposition bins within 40 cm reach<br>2. Height-adjustable sit-stand workstations<br>3. Footrest or lean-support stool<br>4. Evaluate conveyor speed vs. posture |

### 3. Shoulder Imbalance

| Role | Actions |
|---|---|
| **Worker** | 1. Check for leaning on one elbow<br>2. Shrug and release both shoulders<br>3. Level pelvis in chair<br>4. Apply equal force with both arms |
| **Supervisor** | 1. Verify level workstation surface<br>2. Bilateral tool use or jigs<br>3. Mirror for self-check<br>4. Station assessment for reach asymmetry |

### 4. Elevated Left Shoulder

| Role | Actions |
|---|---|
| **Worker** | 1. Drop left shoulder down and back<br>2. Lower left armrest if too high<br>3. Reduce left-hand grip force<br>4. Upper trap stretch 20 s x 3/shift |
| **Supervisor** | 1. Lower left work surface 2-5 cm<br>2. Tool balancer for left-hand tools<br>3. Rotate to right-hand station every 2 hr<br>4. Reposition left parts bins |

### 5. Elevated Right Shoulder

| Role | Actions |
|---|---|
| **Worker** | 1. Drop right shoulder down and back<br>2. Lower right armrest if too high<br>3. Reduce right-hand grip force<br>4. Upper trap stretch 20 s x 3/shift |
| **Supervisor** | 1. Lower right work surface 2-5 cm<br>2. Tool balancer for right-hand tools<br>3. Rotate to left-hand station every 2 hr<br>4. Check right-side bin height |

### 6. Knee Instability

| Role | Actions |
|---|---|
| **Worker** | 1. Knees at 90 deg with feet flat<br>2. Soft knees when standing, shift weight<br>3. No squatting — use step stool<br>4. Gel knee pad, alternate legs |
| **Supervisor** | 1. Adjustable chairs for optimal knee angle<br>2. Anti-fatigue matting<br>3. Eliminate floor-level storage (< 30 cm)<br>4. Padded mats + rotation every 30 min |

### 7. Body Misalignment

| Role | Actions |
|---|---|
| **Worker** | 1. Stack ears-shoulders-hips vertically<br>2. Turn whole body, not twist torso<br>3. Reset alignment every 15 min<br>4. Face task directly |
| **Supervisor** | 1. Orient work zone directly in front<br>2. Footrest for weight shift without twist<br>3. Full-length mirror for self-check<br>4. Floor tape for optimal standing position |

---

## Live Demo Integration

The `live_demo.py` panel now includes a **GUIDANCE** section below the detected issues:

```
┌─────────────────────────────────────────────┐
│  ISSUES DETECTED                            │
│  ! Excessive Neck Flexion (HIGH)            │
│  ~ Elevated Left Shoulder (MEDIUM)          │
├─────────────────────────────────────────────┤
│  GUIDANCE                                   │
│  Worker: Adjust your monitor or task target │
│         to eye level...                     │
│  Supervisor: Raise workstation shelves...   │
├─────────────────────────────────────────────┤
│  SESSION STATS                              │
│  ...                                        │
└─────────────────────────────────────────────┘
```

- Shows top issue's first worker action + first supervisor action
- Color-coded by severity
- Worker actions in severity color, supervisor actions in muted white

---

## Files

| File | Action | Description |
|---|---|---|
| `backend/services/recommendation_engine.py` | **Created** | Core engine with 7 issue definitions, each with 4 worker + 4 supervisor actions |
| `scripts/live_demo.py` | **Modified** | Added GUIDANCE section in dashboard panel, integrates `get_recommendations()` |
| `scripts/test_recommendation_engine.py` | **Created** | 3 test cases, verifies structure and content of every recommendation |
| `docs/INDUSTRIAL_RECOMMENDATION_ENGINE_REPORT_v1.md` | **Created** | This report |

---

## Industrial Focus Areas Covered

| Focus Area | Applicable Issues |
|---|---|
| Repetitive tasks | Neck, trunk, shoulders, wrists |
| Workstation design | All 7 issues — height, reach, orientation |
| Lifting mechanics | Trunk flexion, knee instability |
| Fatigue reduction | Micro-breaks, task rotation, anti-fatigue mats |
| Injury prevention | Shoulder imbalance, elevated shoulders, alignment |
| Tool & equipment | Tool balancers, adjustable furniture, jigs |
| Self-monitoring | Mirrors, timers, wearable alerts |

---

## Future Enhancements

1. **Severity-weighted actions**: Show different actions based on MEDIUM vs HIGH severity
2. **Task-specific guidance**: Actions tuned to specific job roles (welder, packer, sorter, inspector)
3. **Cumulative fatigue recommendations**: Combine issues detected over a session to suggest rest timing
4. **Multi-language support**: Translate worker actions to local languages
5. **Measurable outcomes**: Each action tagged with expected biomechanical improvement (e.g., "reduces neck flexion by 5 degrees")
