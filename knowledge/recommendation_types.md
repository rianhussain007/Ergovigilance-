# Recommendation Types

## Overview

The Recommendation Engine subscribes to `ContextSnapshotCreatedEvent` and evaluates 12 templates from a catalog against the current context. The bundle is regenerated on every frame (not accumulated). Templates are organized into 6 categories.

## Categories

### Posture (5 templates)

| ID | Name | Trigger | Priority | Target |
|----|------|---------|----------|--------|
| REC-NECK | Adjust Neck Posture | `neck_flexion` > 50 | HIGH | Worker |
| REC-TRUNK | Correct Trunk Flexion | `trunk_flexion` > 50 | HIGH | Worker |
| REC-SHOULDER | Balance Shoulder Elevation | `shoulder_symmetry` > 50 | MEDIUM | Worker |
| REC-ALIGN | Improve Body Alignment | `alignment_deviation` > 50 | MEDIUM | Worker |
| REC-KNEE | Adjust Knee Position | feature score `knee_angle` > 50 | MEDIUM | Worker |

All posture triggers use the feature's risk score on a 0-100 scale (computed by `ContextIntelligenceEngine._score_feature()`), not the raw biomechanical value. `knee_angle` is an *inverted* metric: a lower raw angle (more bent knee) produces a higher risk score. For example, a raw knee angle of 80° scores near 100 (HIGH), while 160° scores near 0 (LOW). This differs from features like `neck_flexion` where higher raw values mean higher risk.

### Break (3 templates)

| ID | Name | Trigger | Priority | Target |
|----|------|---------|----------|--------|
| REC-BREAK-F | Take a Micro-Break | `fatigue` > 40 | HIGH | Worker |
| REC-BREAK-E | Reduce Exposure Duration | `exposure` > 50 | HIGH | Worker |
| REC-BREAK-D | Extended Work Period Detected | `duration_frames` > 100 | MEDIUM | Worker |

### Workstation (1 template)

| ID | Name | Trigger | Priority | Target |
|----|------|---------|----------|--------|
| REC-WS | Review Workstation Setup | `active_alerts` >= 3 | MEDIUM | Both |

### Training (1 template)

| ID | Name | Trigger | Priority | Target |
|----|------|---------|----------|--------|
| REC-TRAIN | Ergonomic Training Recommended | frames > 50 AND high_risk_ratio > 30% | MEDIUM | Supervisor |

### Supervisor Action (1 template)

| ID | Name | Trigger | Priority | Target |
|----|------|---------|----------|--------|
| REC-SUPER | Supervisor Intervention Required | Any CRITICAL alert active | CRITICAL | Supervisor |

### Medical Review (1 template)

| ID | Name | Trigger | Priority | Target |
|----|------|---------|----------|--------|
| REC-MED | Medical Review Recommended | frames > 100 AND high_risk_ratio > 50% | HIGH | Supervisor |

## Priority Levels

- CRITICAL: Immediate action required (Supervisor Intervention)
- HIGH: Urgent, address soon (Posture corrections, Fatigue breaks)
- MEDIUM: Monitor and address (Workstation review, Training)
- LOW: Informational

## Target Audiences

- WORKER: Real-time self-correction guidance
- SUPERVISOR: Escalation and intervention triggers
- BOTH: Recommendations relevant to both (e.g., workstation setup)

## API Endpoint

`GET /api/recommendations` returns:
```json
{
  "bundle": {
    "recommendations": [...],
    "summary": { "total": int, "by_category": {...}, "by_priority": {...} },
    "highest_priority": "CRITICAL|HIGH|MEDIUM|LOW",
    "generated_at": "ISO-8601"
  },
  "total_generated": int
}
```

## Known Limitations
- Bundle regenerated every frame (not accumulated)
- No user acknowledgment or persistence
- Trigger thresholds are static (not configurable at runtime)
