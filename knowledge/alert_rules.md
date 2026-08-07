# Alert Rules

## Overview

The Alert Engine subscribes to `ContextSnapshotCreatedEvent` via EventBus and evaluates 4 rules per frame. Alerts are stored in memory only (lost on restart). Lifecycle: ACTIVE -> ACKNOWLEDGED -> RESOLVED.

## Rules

### RULE_HIGH_RISK
| Field | Value |
|-------|-------|
| Name | `high_risk` |
| Severity | HIGH |
| Title Template | "High Risk Posture Detected" |
| Message Template | "Worker posture risk is HIGH (final_risk={final_risk:.0f}). Immediate attention recommended." |
| Requires ACK | Yes |
| Cooldown | 30 frames |
| Trigger | risk_level == HIGH and not on cooldown |

### RULE_CRITICAL_RISK
| Field | Value |
|-------|-------|
| Name | `critical_risk` |
| Severity | CRITICAL |
| Title Template | "Critical Risk Posture — Escalated" |
| Message Template | "Worker posture risk has been HIGH for {consecutive_high} consecutive frames. Escalated to CRITICAL." |
| Requires ACK | Yes |
| Cooldown | 30 frames |
| Escalation Threshold | 10 consecutive HIGH frames |
| Trigger | consecutive HIGH frames >= 10 and not on cooldown |

### RULE_RECOVERY
| Field | Value |
|-------|-------|
| Name | `recovery` |
| Severity | LOW |
| Title Template | "Posture Recovered" |
| Message Template | "Worker posture has returned to safe levels (final_risk={final_risk:.0f}). Alert resolved." |
| Requires ACK | No |
| Cooldown | 0 frames (fires immediately) |
| Trigger | risk_level returns to LOW while active HIGH/CRITICAL alerts exist |

### RULE_RAPID_MOVEMENT
| Field | Value |
|-------|-------|
| Name | `rapid_movement` |
| Severity | WARNING |
| Title Template | "Rapid Repetitive Movement Detected" |
| Message Template | "Rapid movement: {velocity:.1f} deg/s during {risk_level} posture." |
| Requires ACK | No |
| Cooldown | 90 frames |
| Trigger | movement velocity exceeds threshold during a posture state |

## Alert States

- `ACTIVE` — alert has fired and is awaiting acknowledgment or resolution
- `ACKNOWLEDGED` — supervisor/safety_mgr/admin has acknowledged via PATCH
- `RESOLVED` — automatically set by recovery rule, or manually via PATCH by safety_mgr/admin
- `EXPIRED` — defined in model enum but never set by engine logic

## API Endpoints

| Method | Path | Auth Required |
|--------|------|---------------|
| GET | `/api/alerts` | No (returns active + history + summary) |
| PATCH | `/api/alerts/{alert_id}/acknowledge` | supervisor, safety_mgr, admin |
| PATCH | `/api/alerts/{alert_id}/resolve` | safety_mgr, admin |

## Cooldown Notes

Cooldown is frame-based (not wall-clock), so effective cooldown duration varies with FPS. At ~14 FPS, 30 frames = ~2.1 seconds.

## Recovery Behavior

When risk_level returns to LOW, the recovery rule immediately resolves ALL active HIGH and CRITICAL alerts with severity=LOW, title="Posture Recovered", and trigger_rule="recovery".
