# Improvement Plan Status

> **This file is archived.** All items below have been completed or superseded.
>
> For the current delivery status, see:
> - **`docs/DELIVERY_CHECKLIST.md`** — the single source of truth for what remains before the factory pilot
> - **`docs/CURRENT_STATE.md`** — authoritative snapshot of what is built and verified
> - **`ROADMAP.md`** — prioritized remaining work

---

## Completed Items (archived from 2026-08-15)

### Tier 1 — "Coming Soon" Gaps: ALL DONE ✅
- PDF export (Playwright-based, 4 report types)
- Recorded session video playback + skeleton overlay
- Workers page (full CRUD)
- Live monitoring sidebar (override, capture, log)
- Manager dashboard (aggregate stats, department trends)
- Settings deployment configuration

### Tier 2 — Intelligent Analytics: ALL DONE ✅
- Calibrated risk model (HGB classifier, 91.8% on REBA bands)
- Drift monitoring canary
- Rule threshold tuning (30,698-pose REBA dataset)

### Tier 3 — Scale & UX: ALL DONE ✅
- Async video analysis (background job queue)
- Memory + polling bounds (timeline capped at 20K, configurable intervals)
- WebSocket stub cleanup (removed dead `WebSocketClient.ts`)

### Tier 4 — ML Accuracy: IN PROGRESS
- Real-task capture script exists; needs real workplace recordings (P1 in delivery checklist)
