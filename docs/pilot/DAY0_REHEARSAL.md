# Day-0 Rehearsal — dev-mode partial (2026-09-26)

Dry run of `TRL7_QUALIFICATION_PLAN.md` §4.2 against the local dev
stack (backend :8000, cloud :8100, vite :3000 — all healthy at run
time). Steps needing compose ports, site hardware, or people are
marked PENDING with the blocker — nothing is faked.

## Results

| # | §4.2 step | Result | Evidence |
|---|---|---|---|
| 1 | Deploy + `/readyz` | PASS | backend `readyz` (database/live_service/model_available true), `/healthz` ok; cloud `healthy` (0 cams, guard 2.0 GB); vite 200 |
| 2 | Cameras (2 for pilot) | N/A — no hardware | Probe endpoint + Add flow exist; per-cam FPS baseline needs site RTSP |
| 3 | Consent | PASS | Browser roundtrip: grant→granted, withdraw→withdrawn, temp worker removed; seeded data untouched |
| 4 | Accounts + MFA | PARTIAL | Signup → pilot/4 org + trial signal verified; seeded admin/operator/safety_mgr/supervisor intact; MFA enrollment path not exercised |
| 5 | Ergonomist baseline | N/A — site-only | Pre-pilot RULA/REBA reference happens on site |
| 6 | Export (retention/clock/disk) | PASS | EFFECTIVE policy logged (365/365 local override); host disk 28.5 GB free; disk watermark 2.0 GB armed |
| 7 | PDF export | NOT RUN | Endpoint exists; exercise with pilot data on site |

## Pending (compose/site-gated)

- TLS overlay up + handshake (needs 443 + certs on a host)
- Compose health + restart counts
- Camera baseline soak (`soak_cloud.py --seconds 120`)
- NTP/clock check on site hardware

## Teardown

All rehearsal users/orgs removed from the dev DB; seeds verified
present (admin/operator/safety/supervisor); no stray sessions, workers,
or cameras left behind.
