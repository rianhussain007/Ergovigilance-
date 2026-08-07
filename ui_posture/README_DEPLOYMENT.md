# ErgoVigilance — Deployment Guide

## Overview

ErgoVigilance is designed as a real-time AI ergonomic monitoring platform for industrial manufacturing environments. This document describes the deployment architecture, factory topology, and integration points for connecting to a live production environment.

---

## Factory Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Factory Floor (Zones A-D)                     │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │  Zone A  │  │  Zone B  │  │  Zone C  │  │  Zone D  │        │
│  │ Assembly │  │Precision │  │  Heavy   │  │ Assembly │        │
│  │  3 WS   │  │  3 WS   │  │  3 WS   │  │  3 WS   │        │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘        │
│       │              │              │              │             │
│       └──────────────┴──────┬──────┴──────────────┘             │
│                              │                                   │
│                    ┌─────────▼─────────┐                        │
│                    │   Edge Devices    │                        │
│                    │  (NVIDIA Jetson   │                        │
│                    │   Orin NX × 4)    │                        │
│                    └─────────┬─────────┘                        │
│                              │                                   │
│                    ┌─────────▼─────────┐                        │
│                    │   On-Prem Server  │                        │
│                    │  (Inference + DB) │                        │
│                    └─────────┬─────────┘                        │
└──────────────────────────────┼──────────────────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │   Dashboard UI      │
                    │  (This application) │
                    └─────────────────────┘
```

### Zones

| Zone | Type | Workstations | Primary Risks |
|------|------|-------------|---------------|
| A | Assembly Line | A1, A2, A3 | Neck flexion, shoulder strain |
| B | Precision Work | B1, B2, B3 | Trunk flexion, sustained neck |
| C | Heavy Duty | C1, C2, C3 | Deep trunk flexion, knee stress |
| D | General Assembly | D1, D2, D3 | Shoulder asymmetry, neck strain |

---

## Camera Topology

Each workstation is monitored by one or more RGB cameras:

- **Resolution**: 1280×720 @ 30 FPS
- **Interface**: USB 3.0 / GigE Vision
- **Placement**: 2–3m from worker, 45° angle
- **Coverage**: Single camera per workstation (up to 4m² area)

Camera IDs follow the convention: `CAM-{XXX}` mapped to `Workstation {Zone}{Number}`.

### Recommended Camera Layout

```
CAM-001 → Workstation A1 (Marcus Thorne)
CAM-001 → Workstation A2 (Elena Rodriguez)
CAM-002 → Workstation B1 (Chen Wei)
CAM-004 → Workstation B2 (Priya Sharma)
CAM-003 → Workstation C1 (James Kowalski)
CAM-005 → Workstation C2 (Sarah Jenkins)
CAM-006 → Workstation C3 (Maria Santos)
CAM-002 → Workstation D1 (David Park)
CAM-005 → Workstation D2 (Lisa Chen)
CAM-004 → Workstation D3 (Ahmed Hassan)
```

Note: Cameras can be shared across adjacent workstations when using wide-angle lenses.

---

## Edge AI Deployment

Each zone is served by an **NVIDIA Jetson Orin NX** edge device:

| Metric | Expected Value |
|--------|---------------|
| CPU Usage | 40–70% |
| GPU Usage | 50–85% |
| RAM Usage | 45–65% |
| Inference Time | 18–30ms |
| Throughput | 25–30 FPS |
| Temperature | 55–75°C |
| Uptime | Months |

The edge device runs:
1. **MediaPipe Pose** — skeletal keypoint detection
2. **Ergonomic Feature Extractor** — angle/ distance computation
3. **Rule-based Issue Detection** — threshold violation checking
4. **MLP Classifier (v3.2)** — risk level prediction

### Model Versioning

Models are versioned as `ergo-mlp-v{major}.{minor}`:
- v3.0 — Initial production model
- v3.1 — Improved shoulder elevation accuracy (+8%)
- v3.2 — Reduced inference time (-12%), added knee angle detection

---

## Future FastAPI Integration

When the real FastAPI backend is ready, the following endpoints will power the dashboard:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/dashboard` | GET | Current session dashboard (liveStatus, features, issues) |
| `/api/v1/sessions` | GET | Historical session list |
| `/api/v1/trends` | GET | Weekly / feature trend data |
| `/api/v1/cameras` | GET | Camera status and metadata |
| `/api/v1/infrastructure` | GET | Edge device metrics and system health |
| `/api/v1/audit` | GET | Audit trail events |
| `/api/v1/notifications` | GET | Notification history |
| `/api/v1/settings` | GET/PUT | User and deployment settings |

Switch from mock to live API by setting:
```typescript
// src/config/index.ts
export const config = {
  USE_MOCK: false,  // ← Set to false for live API
  API_BASE_URL: '/api/v1',
  // ...
};
```

---

## Future WebSocket Integration

For real-time updates, WebSocket connections will stream:

```typescript
// src/services/WebSocketClient.ts
ws.connect();
ws.subscribe('risk_update', (data) => {
  // data = { workerId, riskLevel, riskScore, features, issues }
  // Update dashboard state without polling
});
ws.subscribe('camera_frame', (data) => {
  // data = { cameraId, fps, recording, snapshot? }
  // Update camera panel UI
});
ws.subscribe('alert', (data) => {
  // data = { severity, title, description, timestamp }
  // Show toast notification
});
```

The WebSocket client is already stubbed in `src/services/WebSocketClient.ts` and ready for implementation.

---

## Role-Based Access Control

| Role | Access | Visible Pages |
|------|--------|---------------|
| **Operator** | View own workstation | Live Monitoring, Analytics, Sessions, Settings |
| **Supervisor** | View zone/ team data | + Trends, Reports, Multi-Camera, Manager |
| **Safety Manager** | Full factory view | + Deployment Center, Audit Trail |
| **Administrator** | Full access + configuration | All pages + deployment settings |

Role selection is done via the toolbar at the top of every page. This is a UI-only mock; real RBAC would be enforced server-side.

---

## Data Retention

| Data Type | Default Retention | Storage Estimate |
|-----------|------------------|-----------------|
| Session records | 90 days | ~2 KB / session |
| Risk history | 90 days | ~10 KB / session |
| Audit events | 180 days | ~0.5 KB / event |
| Raw frames | Not stored | N/A |
| Reports | Indefinite | ~3 MB / report |

Configurable via **Settings → Data Retention**.

---

## Deployment Checklist

- [ ] Edge devices installed at each zone (NVIDIA Jetson Orin NX)
- [ ] Cameras positioned and calibrated
- [ ] Network connectivity verified (latency <50ms)
- [ ] FastAPI backend deployed (or USE_MOCK=true for demo)
- [ ] Worker profiles created in database
- [ ] Workstation-to-camera mapping configured
- [ ] Alert thresholds set per zone (Settings)
- [ ] Data retention policy configured
- [ ] Role-based access assigned

---

## Monitoring & Alerts

The Deployment Center page provides real-time infrastructure monitoring:

- **Backend API** — health check endpoint status
- **AI Model** — version deployed and inference performance
- **Edge Device** — CPU/GPU/RAM/temperature gauges
- **Cameras** — FPS, recording status, uptime
- **Storage** — usage against capacity

Alert notifications appear in the **Notification Center** (bell icon in toolbar) and are categorized as:

- **Critical** — Immediate action required (risk threshold exceeded, device offline)
- **Warning** — Attention needed (risk approaching threshold, camera degraded)
- **Info** — Informational (report generated, model updated)
- **Resolved** — Previously flagged issues now resolved

---

## See Also

- `README_DEMO.md` — Demo Mode walkthrough
- `src/config/index.ts` — Configuration (USE_MOCK toggle)
- `src/services/WebSocketClient.ts` — WebSocket stub
- `src/repositories/ApiDashboardRepository.ts` — Future API integration point
