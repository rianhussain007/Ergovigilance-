# Pilot Intake Tracker — How to Use

A lightweight spreadsheet for tracking inbound pilot requests. Import
`PILOT_INTAKE_TRACKER.csv` into Google Sheets / Excel — no CRM needed.

## Columns

| Column | Meaning |
|---|---|
| `name` | Contact name (the person you talked to, not the site) |
| `company` | Company / site name |
| `site_type` | Assembly line, warehouse, packing, workshop, office… |
| `camera_network_readiness` | What they have: USB webcam, existing IP cameras, LAN availability, firewall constraints. Free text is fine. |
| `decision_maker` | `yes` / `no` — can this person say yes, or do we need to reach their manager/IT too? |
| `call_date` | Date of the qualifying call (YYYY-MM-DD) |
| `triage_score` | 0–10, see rubric below |
| `status` | `waitlisted` / `scheduled` / `active` / `declined` |
| `notes` | Anything from the call: stations, shifts, pain points, objections |
| `next_action` | The concrete next step |
| `next_followup` | Date to follow up |

## Triage score rubric (0–10)

Score the *readiness to run a pilot*, not enthusiasm:

| Points | Factor |
|---|---|
| +0–2 | Pain point is real (recent WMSD, comp claim, rising assessment cost) |
| +0–2 | A camera and a Windows PC are available on-site |
| +0–2 | Decision-maker is on the call (or reachable within a week) |
| +0–2 | Site type matches our single-station framing (they accept one camera/one worker to start) |
| +0–2 | Network/LAN is workable (IT is at least aware, no hard block on local devices) |

**Gate:** a score of 7+ and `decision_maker=yes` qualifies for a pilot.
Anything less goes to `waitlisted` and gets a follow-up date.

## Status flow

```
waitlisted ──(qualifying call, score ≥7)──▶ scheduled ──(deployed)──▶ active
     │                                                              │
     └────(declined / no reply after 3 touches)────────────────────▶ declined
```

- **scheduled** — call booked and pre-deployment checklist sent.
- **active** — system deployed and running real shifts.
- **declined** — record *why*; declined reasons are your roadmap signal.

## Cap: max 2 active pilots (policy)

**Never more than 2 sites in `active` at once.** This is a hard rule, not a
target — the installer and the support loop must prove out before scaling.
When both slots are full:

1. New qualifying sites go to `waitlisted` with a clear "next available" date.
2. Tell them the truth: *"We're limiting concurrent pilots to make sure every
   site gets full attention; we can start yours on <date>."* — scarcity reads
   as demand, not weakness.
3. The moment one site ends, the highest-scoring waitlisted site moves up.

## Weekly metric (the only one that matters)

Count of **real conversations with safety managers / EHS consultants** this
week (calls, not emails). The tracker's job is to make sure every conversation
has a next action and a follow-up date — not to be a dashboard you optimize.
