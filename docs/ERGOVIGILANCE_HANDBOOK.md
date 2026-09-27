# ErgoVigilance Handbook — A Small Book for Factory People

> **How to use this book:** Give it to an owner, EHS manager, supervisor, or operator. Each chapter is one idea. Read in order or jump to what you need.
> **Status:** DRAFT 2026-09-24. Fill every `[FILL]` before printing/sharing. Every number traces to `docs/DEEP_AUDIT_REPORT.md` Safe Claims Sheet.
> Contact: Rian Hussain · [FILL: contact email] · [FILL: phone] · ErgoVigilance

---

## Contents

**Part A — Why this exists (p1–6)**
1. Cover story: Raju's back (p1) · 2. What this book will give you (p2) · 3. The injury you don't see coming (p3) · 4. Why manual checking misses it (p4) · 5. Continuous vs spot-check (p5) · 6. What one bad posture costs (p6)

**Part B — How it works (p7–14)**
7. One-sentence answer (p7) · 8. Cameras: what you need (p8) · 9. The skeleton: how the camera sees (p9) · 10. The 17 body angles in plain words (p10) · 11. LOW / MEDIUM / HIGH colours (p11) · 12. Why it doesn't beep on one frame (p12) · 13. It knows the task (p13) · 14. What each person sees daily (p14)

**Part C — Proof you can hold (p15–17)**
15. Alerts + guidance (p15) · 16. Video replay (p16) · 17. Reports: the PDF sample (p17)

**Part D — Trust: privacy + honest numbers (p18–22)**
18. Video never leaves your building (p18) · 19. Consent: three modes (p19) · 20. Who sees what (p20) · 21. Honest accuracy box (p21) · 22. What it cannot do (p22)

**Part E — Get it on your floor (p23–28)**
23. Free 2-week pilot (p23) · 24. Install checklist (p24) · 25. Paid assessment tiers (p25) · 26. Full pricing (p26) · 27. ROI worksheet (p27) · 28. Objection handling (p28)

**Part F — Close (p29–30+)**
29. FAQ (p29) · 30. Glossary + contact + next step (p30) · Appendix: Kannada/Hindi insert

---

# PART A — WHY THIS EXISTS

## p1. Cover story: Raju's back

Raju is 34. Second shift, packing station, Bommasandra. Six hours a day he leans 20 cm over a low table, neck bent, right shoulder raised. No single moment looks dangerous. After 8 months his neck burns every night. He takes leave. The line slows. The company pays.

Nobody did anything wrong. The manual audit visited in March, watched for 20 minutes, ticked "OK". The bad posture happened in April–November, when nobody watched.

This book is about catching Raju's posture in April — with an ordinary camera, before it becomes a claim.

`[PHOTO: packing station, side view, arrow on neck bend]`

## p2. What this book will give you

* Owner: will this save money and trouble? (p6, p26–27)
* EHS / Safety manager: will this give me proof I can file? (p17, p21)
* Supervisor: will this tell me which station needs me now? (p14–15)
* Operator: will this spy on me? (p18–19 — short answer: no)

Read all 30 pages in 25 minutes, or read only your chapter. If you want the machine on your floor, jump to p23.

## p3. The injury you don't see coming

Musculoskeletal injuries — back, neck, shoulder, wrist, knee — are the most common factory injuries. They rarely come from one lift. They come from small wrong postures repeated thousands of times: neck 30° forward, trunk bent, shoulder up, wrist twisted, weight on one leg.

Pain builds silently. By the time a worker complains, the pattern is months old. Compensation, leave, retraining, slower line — all arrive together.

`[PHOTO: 4 common risky postures, simple line drawings]`

## p4. Why manual checking misses it

Manual RULA/REBA audits are good science but bad coverage:

| Manual audit | Reality on floor |
|---|---|
| 20–30 min visit, once a quarter | Risk happens 8 hrs/day, 26 days/month |
| One observer, one moment | Posture changes by task, fatigue, shift hour |
| Paper score | No trend, no station comparison, no replay |
| Finds today's worst moment | Misses the repeated medium-risk that actually injures |

ErgoVigilance does not replace your ergonomist. It gives them continuous data between visits.

## p5. Continuous vs spot-check

| | Spot audit | ErgoVigilance |
|---|---|---|
| When | Visit day | Every shift |
| What | Score at one moment | LOW/MEDIUM/HIGH every second + trend |
| Evidence | Paper form | Video replay + PDF/CSV timeline |
| Comparison | Memory | Station vs station, shift vs shift, week vs week |
| Action | "Improve posture" | "Station 3, trunk bend 40–60°, 2–4 pm — raise table 10 cm" |

One-liner for your meeting: **continuous screening between audits, not instead of audits.**

## p6. What one bad posture costs

Industry benchmarks (not our promise — your pilot will measure yours):

* One MSD injury in India: hospital + leave + overtime + retraining + slower line. US OSHA benchmark often cited: ~$15,000 per prevented injury; Indian factory cost is lower per case but frequency is higher.
* Industry claim often cited: ~40% incident reduction after sustained ergonomic action. Treat as direction, not guarantee.
* Your worksheet is on p27. Fill: workers × shifts × past strains × leave days. Two weeks of our trend usually pays for the assessment alone in avoided guesswork.

`[FILL: your plant's last-year strain leaves — even a rough number makes p27 work]`

---

# PART B — HOW IT WORKS

## p7. One-sentence answer

**A camera watches the workstation, draws a skeleton, measures body angles, scores risk, beeps only when risk stays, and gives you a report.**

No wearables. No bands. No phone on the worker. On-prem runs on a laptop, offline.

```text
Camera → Skeleton → 17 angles → LOW/MED/HIGH + reason
  → Alert (only if sustained) → Advice → Report
```

## p8. Cameras: what you need

* On-prem (free tier): any USB webcam or laptop camera. 1 camera per station is best. Keep full torso + arms in frame, even light, no strong backlight.
* Cloud tier: existing CCTV via RTSP stream — no new hardware, central dashboard.
* Placement per station (see sketches):

| Station | Camera side | Distance | Watch for |
|---|---|---|---|
| Assembly (seated/standing) | Front-side 45° | 2–3 m | Neck + shoulder + wrist |
| Packing (standing, reaching) | Side | 2.5–3.5 m | Trunk bend + reach distance |
| Warehouse (lifting) | Side-front | 3–4 m | Knee + trunk + load moment |

`[PHOTO: 3 placement sketches with tripod height marked]`
Day-one check (p24) confirms framing before any scoring counts.

## p9. The skeleton: how the camera sees

On-prem draws **33 body points** (MediaPipe: nose, ears, shoulders, elbows, wrists, hips, knees, ankles…). Cloud draws **17 points** (YOLOv8-pose, COCO style: leaner, better for CCTV distance).

4 points are finger/foot detail that CCTV can't see reliably — the system marks them unknown instead of guessing. That honesty is by design.

Frame rate: ~15–20 FPS on a normal laptop CPU (on-prem), up to 30 on GPU/cloud. Enough to catch a sustained bend; not a slow-motion lab.

`[PHOTO: skeleton overlay, green/yellow/red joints]`

## p10. The 17 body angles in plain words

| # | Name | Plain meaning | Risky when |
|---|---|---|---|
| 1 | Neck flexion | Head bent forward | >30° |
| 2 | Trunk flexion | Back bent over table | >60° |
| 3–4 | Shoulder elevation L/R | Shoulder raised toward ear | >60° |
| 5 | Shoulder symmetry | One shoulder higher | >15% diff |
| 6 | Alignment deviation | Ear far ahead of hip | Large offset |
| 7 | Knee angle | Squat vs stand | <100° under load |
| 8 | Elbow flexion | Arm folded tight | <45° |
| 9 | Upper-arm from vertical | Arm reaching out/up | >45° |
| 10 | Forward head posture | Head poking forward | >20° |
| 11 | Head tilt | Head tipped sideways | >20° |
| 12 | Wrist deviation | Wrist bent (RULA Table B) | >15° |
| 13 | Stance stability | Feet narrow/uneven | <0.5 score |
| 14 | Weight shift | Leaning to one leg | >15% torso |
| 15–17 | Hand reach / finger spread / stance width | Task signals (how far, grip, feet) | Reference, not alarms |

Plus 2 motion signals: body speed (deg/s) and wrist speed (px/s) — fast repeated reaching counts more.

## p11. LOW / MEDIUM / HIGH colours

* **LOW (green, score ~20):** RULA 1–2 / REBA 1–3. Keep working. Example: upright, neck <10°, trunk <20°.
* **MEDIUM (yellow, ~50):** RULA 3–4 / REBA 4–7. Watch. Example: neck 10–30°, trunk 20–60°, shoulder 30–60°. Most factory work lives here — this is where prevention happens.
* **HIGH (red, ~80):** RULA 5+ / REBA 8+. Stop and fix. Example: trunk >60°, neck >30° sustained, deep knee bend under load.

On-prem scoring is **rule-based RULA/REBA** (inspectable, same every time). ML models assist (task, calibration, forecast) but never overrule a HIGH on-prem. Cloud uses trained classifiers first, rules as backup.

`[PHOTO: 3 workers — green/yellow/red with reason labels]`

## p12. Why it doesn't beep on one frame

Four smoothing layers stop false alarms:

1. **Kalman filter** steadies shaky points (ignores 1-frame jumps).
2. **Feature averaging** (α 0.6) — angles glide, unknown stays unknown (never invents HIGH).
3. **Task window** (10 frames) — task label changes only on clear majority; seated-posture geometric check bypasses smoothing (never smoothed away).
4. **Dwell (10 frames) + cooldowns** — risk level must persist; alerts cool down (HIGH 30s, sustained 60s, worsening 120s) so you get one useful alert, not fifty.

Result: brief glance down = no alert. Two minutes bent over = alert.

## p13. It knows the task

7 tasks: Neutral, Assembly, Reaching, Lifting/Picking, Inspection, Seated, Walking/Moving. Why it matters: reaching thresholds differ from seated thresholds. A 25° trunk bend while lifting is worse than while seated.

Task comes from 19 signals (17 angles + 2 speeds) with confidence gating + temporal smoothing. If unsure, it says unsure — and scores conservatively (toward MEDIUM, see p21).

## p14. What each person sees daily

* **Operator (`/my-posture`):** big gauge + one-line advice ("Bring the box closer", "Straighten your neck"). Own data only. Hindi available.
* **Supervisor (dashboard + multi-camera):** all stations now, heatmap, who needs a visit, acknowledge alert button.
* **EHS manager (reports + analytics):** trends by worker/station/shift, benchmark percentiles ("Station 3 neck-flexion worse than 80% of recorded sessions"), evidence package.
* **Admin/IT (health + users + retention):** service status, users, cameras, retention settings.

`[PHOTOS: 4 screenshots — gauge, heatmap, trend, health]`

---

# PART C — PROOF YOU CAN HOLD

## p15. Alerts + guidance

When risk stays MEDIUM/HIGH, you get: on-screen toast + alert entry + supervisor email/Slack (cloud tier) + recommended action.

Lifecycle: **created → shown → acknowledged (supervisor+) → resolved (safety mgr+) → filed in history/audit.** Nothing vanishes. Every ack/resolve is logged with who and when.

Guidance examples: "Raise table 10 cm", "Bring object 15 cm closer", "Micro-break 30 s each 20 min", "Rotate lifting task", "Check camera framing" (when joints uncertain).

## p16. Video replay

Every session can replay with skeleton burned over video + risk timeline underneath. Drag the timeline to the red spike, see exactly what the worker did. Frame-by-frame angles available.

Recordings auto-delete after 30 days (configurable, capped at 20 GB — oldest first). No replay leaves the plant in on-prem mode.

`[PHOTO: replay screen with timeline, red spike at 14:32]`

## p17. Reports: the PDF sample (2 pages, read carefully)

Each session ends with: duration, average risk, % LOW/MED/HIGH, top-3 risky angles, task split, alert list, trend sparkline, recommendations. Export PDF/CSV/JSON. EHS gets daily/weekly rollups + one-click evidence zip (for OSHA/insurance/internal review).

`[PHOTO: 2 redacted sample PDF pages — blur faces, keep scores]`
Ask us for a live sample on your station — p23.

---

# PART D — TRUST: PRIVACY + HONEST NUMBERS

## p18. Video never leaves your building

On-prem: frames processed in laptop memory, never uploaded. No cloud account, works on local Wi-Fi/hotspot or no internet at all. Reports generate locally. AI assistant (Ollama) runs locally if enabled.

Cloud tier (only if you choose RTSP/CCTV): streams go to your cloud-core server (`:8100`), multi-tenant isolated by API key, same retention rules. You pick the lane — most first pilots stay on-prem.

## p19. Consent: three modes

1. **Anonymous** — no name, no face record. Risk by station, not person. Default for pilots.
2. **Badge/QR** — worker scans badge; system links sessions to ID without face match.
3. **Face (with signed consent only)** — face samples stored locally, matched only after consent granted; withdraw flips status and triggers deletion flow (p20). Paper consent form + one-page explainer provided (`docs/pilot/WORKER_CONSENT_ONEPAGER.md`).

Floor signage mandatory: "Camera-based posture screening in progress — ask your supervisor for the notice." No hidden cameras, ever.

## p20. Who sees what

| Role | Sees | Cannot |
|---|---|---|
| Operator | Own gauge, own history, own tips | Others' data, settings |
| Supervisor | All stations/workers now, trends, ack alerts | System settings, user admin |
| Safety Mgr | All + resolve, PDFs, evidence, benchmarks, ROI | Delete workers, auth settings |
| Admin | Users, workers, cameras, retention, billing, erasure | Nothing (full access, fully logged) |

Deletion: `Delete worker data` wipes recordings + alerts + profile on request (admin, logged). Session JSONs without worker ID age out by retention only — we tell you this upfront (`docs/PRIVACY.md`). Backups and Postgres telemetry rows follow the same retention on request — ask and we show the log.

## p21. Honest accuracy box (read before quoting us)

* **87.6% agreement with human assessors on 500 labeled frames.** LOW: precision 100%, recall 57% (we over-warn — 62 LOW frames flagged MEDIUM). MEDIUM: precision 85%, recall 100% (we catch all MEDIUM). **No HIGH validated. One worker, one room, one camera.** File: `results/ground_truth_evaluation.json`.
* What this means: good screening sensitivity (misses little), some false yellows. Alert fatigue is the trade-off — dwell + cooldowns (p12) exist to contain it.
* Not quoted as product accuracy: 94.1%/97.6% (YOLO holdout on rule-derived labels, leaky), 88.6%/86.4% F1 (research track, not runtime), 76.9% (old REBA holdout, retired). If anyone shows you those as promises, correct them with this page.
* Threshold review: **[FILL: Pending / Reviewed by ___ , ___credential___, date ___]**. In safety, provenance matters as much as performance.

## p22. What it cannot do

* Cannot prevent all injuries, cannot diagnose, cannot replace your safety officer or ergonomist.
* Cannot see through occlusion (machine blocks body), heavy PPE glare, darkness, violent vibration — it flags "low framing quality, reposition camera" instead of guessing.
* On-prem tracks one primary person per camera reliably (up to 4 detected, primary scored). Crowded multi-person per-camera analytics is cloud-tier + follow-up work — we won't promise it on-prem.
* Cannot run 24/7 unproven — first pilots are supervised shifts, not unmanned nights.
* Not certified (no SOC2/ISO yet — planned), no fleet/HA/load proof at 50+ cameras yet. We list this so your IT team doesn't have to find it.

---

# PART E — GET IT ON YOUR FLOOR

## p23. Free 2-week pilot (the actual offer)

**$0. One station. 1–2 cameras. ~30-min laptop install. 2 weeks. We uninstall if you see no value.**

* You pick the station (assembly, packing, inspection — fixed work, not outdoor mobile).
* We do the 4-step setup (position, lighting, framing, face/consent check) + day-one smoke test: live feed → deliberate slouch → alert fires → report + clip proves the loop.
* You watch 2 weeks: alerts, trend, one supervisor debrief per week.
* Success agreed upfront: **risk-score trend + supervisor feedback** (2 weeks can't move injury rates — anyone promising that is lying).
* Paperwork: consent + signage + one-page agreement stating **screening aid, not medical device**.

`[FILL: pilot slots — max 2 active, next slot date ___]`

## p24. Install checklist (tear out and keep)

* [ ] Table/chair heights noted; camera 2–3.5 m, 45° front-side (p8)
* [ ] Full torso + arms visible; face unobstructed; even light
* [ ] `http://<PC-IP>:8080` reachable; login roles tested
* [ ] Consent signed / anonymous mode selected; signage up
* [ ] `AUTH_JWT_SECRET` set (strong random), `DEBUG=false`, `CAMERA_SOURCES` filled if RTSP
* [ ] Slouch test passes; alert + report + clip confirmed
* [ ] Supervisor knows ack/resolve buttons; EHS knows Reports page
* [ ] Retention confirmed (30 d sessions/recordings, 20 GB cap)

Leave-behind: `docs/PILOT_GUIDE.md` (plain language) + `docs/OPS_RUNBOOK.md` (IT).

## p25. Paid assessment tiers (if you want proof before pilot)

Same camera pipeline, time-boxed, no SaaS commitment. Ex-GST, Bengaluru/Hosur belt; travel beyond at cost. Priced **under** office-ergonomics consulting on purpose (Elion public range ₹50,000–₹3,00,000, typical ₹1–2.5L for **office** work — factory-floor camera screening is different, and we're unproven, so the price says so).

| Tier | Scope | On site | You get | Price |
|---|---|---|---|---|
| Rapid Station Screen | 1 station, 1 camera, 1 shift | 2 days | Session PDFs + top-3 risks + 30-min debrief | ₹19,999 |
| Line Assessment ★ | 1 line, up to 2 stations | 3–5 days | Trend + station comparison + RULA/REBA PDFs + 60-min EHS review | ₹39,999 |
| Multi-Line Baseline | Up to 3 lines, rotating | Up to 2 weeks | Baseline + benchmarks + 50% credit to Cloud* | ₹79,999 |

\* 50% credited to first 3 months Cloud if converted in 60 days. 50% advance, 50% on delivery. Reschedule free to 72h; line-down day ₹5,000.

## p26. Full pricing (canonical — matches app Pricing page)

| Tier | Price | Cameras | For |
|---|---|---|---|
| On-Premise Starter | Free (self-hosted) | 4 USB/webcam | Small facilities, offline |
| Cloud Professional | $299/mo per 10 cams (up to 20); $239/mo annual | 20 RTSP | Medium factories, zero hardware |
| Enterprise | Custom | 50+, multi-site | GPU cluster, ERP/CMMS, SLA |

First-10 Indian buyers: ask for INR quote — we quote one currency per deal, never mixed. Stripe checkout live (needs keys); otherwise `/request-pilot` + invoice.

## p27. ROI worksheet (fill with your numbers)

```text
Workers on line:            ___
Strains / leaves last year: ___
Avg leave days per strain:  ___
Overtime + temp cost / day: ₹___
Assessment cost (p25):      ₹___
Pilot cost:                 ₹0
If trend halves repeat-strain time on 1 station: saves ≈ ___ days × ₹___ = ₹___
```

Even without injury math: one station comparison ("Station 3 trunk 2× Station 1") usually justifies table-height fixes costing less than the assessment.

## p28. Objection handling (say it plainly)

* "Union/workers will refuse." → Start anonymous mode, signage + consent demo, operator-only view. No names needed for station trends.
* "Night shift?" → Needs decent light; IR/low-light unproven — test one night before promising.
* "Internet?" → On-prem needs none after install. Cloud needs stable uplink.
* "Old cameras?" → USB webcam ₹2–3k works for pilot; keep CCTV for cloud phase.
* "OSH Code compliance?" → Code in force Nov 2025, central rules May — raises accountability, does **not** mandate cameras. Honest hook, not compliance claim.
* "Why not Intenseye/Voxel?" → They sell broad PPE/hazards to Fortune-500 at enterprise cycles ($90M+/$54M funded). Nobody owns ergonomics-specific + self-serve + Indian mid-market. That's our wedge.

---

# PART F — CLOSE

## p29. FAQ (12)

1. Wearables? No — camera only. 2. Which camera? Any USB for pilot; RTSP later. 3. How long to value? Day-one smoke test; trend in 3–5 days. 4. False alerts? Some yellows by design (p21); dwell contains them — tell us and we tune. 5. PPE/occlusion? Flagged, not guessed. 6. Multiple workers? One primary per camera on-prem; cloud tracks more. 7. Data ownership? Yours; deletion on request + logged. 8. Medical? No — screening only. 9. Languages? English + Hindi operator strings; Kannada insert next. 10. IT needs? Laptop + browser; no AD/cloud. TLS on request (p24). 11. After pilot? Keep free tier, buy assessment, or upgrade to Cloud. 12. Cost of doing nothing? p6 + p27.

## p30. Glossary + contact + next step

* RULA/REBA: standard posture-score methods (upper-body / whole-body). We implement them as inspectable rules + task context.
* Dwell: risk must persist N frames before alert — kills flicker.
* False-positive: yellow when green was true — we prefer this over missing risk, within limits.
* Benchmark percentile: your station vs past sessions on record (de-identified).

**Next step (15 min):** pick one station + date. Call/WhatsApp `[FILL: phone]`, email `[FILL: contact email]`, or scan:

`[QR: /request-pilot link — FILL]`

ErgoVigilance · Industrial ergonomics, automated · A product by Rian Hussain · Version 2026-09-24-DRAFT.

## Appendix. Kannada / Hindi insert (1 page each, print double-sided)

`[FILL: Kannada summary — 8 lines: what camera does, no video leaves, consent, anonymous OK, who to ask]`
`[FILL: Hindi summary — same 8 lines]`
`[PHOTO: signage sample on factory wall]`

---

*End of handbook. If anything here disagrees with `docs/ONE_PAGER_RECONCILED.md` or `docs/DEEP_AUDIT_REPORT.md` §13, the audit + one-pager win — file an issue and fix this book.*
