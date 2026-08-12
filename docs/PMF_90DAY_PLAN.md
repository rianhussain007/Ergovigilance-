# ErgoVigilance — PMF Ladder & 90-Day Plan (v2, 2026-08-08)

Synthesis of independent reviews by Claude and Grok, plus a third review that
corrected three things (v1 → v2 changes marked **CHANGED**). This is the
operating plan for taking product-market fit from ~2–4/10 to 9/10. Shareable
with other AIs for critique (see the shared-review block at the end).

---

## 0. Where the reviews agreed (treat as settled)

1. **PMF is a market-observed fact, not an engineering property.** The single
   highest-leverage action is one real pilot with a real safety manager.
2. **Service-first to first dollar.** Nobody signs a software license with an
   unproven vendor; a one-time assessment engagement clears a discretionary budget
   with zero procurement friction.
3. **Don't build multi-person tracking before a real customer names it as the
   blocker.** Sell "monitor your highest-risk station" (single worker per camera)
   for pilot #1.
4. **Offline-first is a moat** ("your video never leaves the building"). Optional
   sync of *derived* data later; never raw video by default.
5. **Liability language is more urgent than clinical validation.** "Heuristic
   thresholds, not clinically validated, not a medical device" on every report +
   a lawyer conversation before pilot #1.
6. **IP/RTSP camera support + a non-developer installer are table stakes.**
7. **Cap concurrent pilots at 2–3** until the installer + support loop is proven.
8. **Don't raise.** $0 and 90 days produces the signal that makes money raiseable
   later.

## 0.1 Where they diverged (my verdict)

- PMF 2 vs 4: irrelevant — meaningless until market observation exists.
- $50k funding (no vs conditional yes): don't raise (see #8 above).
- Pricing (Claude $300–600/camera/mo ≈ Grok $4–12k/site/yr): compatible; firm up
  only after pilot #1.

---

## 1. The PMF ladder (how the number actually moves)

| Rung | Target | What happens | Exit criterion |
|---|---|---|---|
| R1 | → 5 | One real site runs the system 2+ weeks, unpaid | Signed written feedback from a real safety manager + 3 concrete requests |
| R2 | → 6 | First **paid** engagement (assessment service) | Invoice paid, report delivered, "worth it" |
| R3 | → 7 | 3 engagements (2 paid), repeat/referral, ergonomist reviews report wording | External ergonomist sign-off + 1 repeat engagement |
| R4 | → 8 | Repeatable: 5+ assessments, service menu, case study w/ numbers, multi-camera supervisor view live | 2 engagements closed from cold pipeline |
| R5 | → 9 | First annual on-prem license; multi-person shipped or scoped w/ committed buyer; quantified ROI story | 2+ sites on paid license, 1 named reference |
| 10 | — | Buyers call you | Asymptotic; 9 = buyers proactively ask to buy |

> **CHANGED — the ladder is a tracking tool, not the target.** Don't manage to
> the rungs. The actual target is one sentence from one real person — *"I'd pay
> for this"* — followed by an invoice. If you catch yourself optimizing the score
> instead of the conversation, that's the tell. The weekly metric is **number of
> real conversations with safety managers/EHS consultants**, not ladder position.

---

## 2. The 90-day plan

### Weeks 1–3 — outreach is the protected resource (CHANGED)

- **Priority: outreach first, every day.** Cold LinkedIn/email to 30+ EHS
  consultants & safety managers, offering a free 2-week single-station assessment
  in exchange for feedback + case study. Protect a dedicated block daily.
- **Code runs in the spare time — realistically 2.5–3 weeks, not 2** (CHANGED):
  RTSP/IP camera support + Windows service packaging + liability disclaimers on
  every report. RTSP will eat days on random-camera negotiation issues; budget for
  it.
- **If forced to pick between the two, the choice is made: protect outreach.**
  Code with no pilot to run on it is dead weight; a pilot with a slightly rougher
  installer is still a pilot. The installer can be "good enough for one site"
  long before it's "good enough for ten."
- **Decision:** lock the framing — "monitor your highest-risk workstation," one
  worker per camera.

### Weeks 3–6 — land pilot #1 (the whole game)

- Deploy on one real site (unpaid/heavily discounted). Run real shifts. Deliver a
  real assessment report.
- Watch what the safety manager looks at, ignores, asks for. Write everything down.
- Start one university-lab / ergonomist validation conversation in parallel
  (3–6-month close — start now).

**WEEK-6 CHECKPOINT — the failure branch (NEW).** If nothing is signed by week 6,
cold outreach alone did not work. The fallback is **NOT "send more LinkedIn
messages" — it's switch channel:**

1. **GGS Information Services network** — you already have a foot inside an
   industrial-adjacent company. Anyone there who knows a client, a partner, or a
   plant manager is a warm bridge.
2. **University contacts** — career office, industry-liaison office, faculty in
   industrial engineering / occupational health / kinesiology. A professor who
   consults for a manufacturer is a trust multiplier.
3. **Your personal network** — anyone who runs a warehouse, a workshop, a
   distribution center, or knows someone who does. A friend's uncle's plant beats
   a cold inbox every time for something this trust-dependent.

**Warm-through-a-person beats cold-through-a-platform.** This is a camera
watching a factory floor — people say yes to people they trust, not to strangers
with a free offer.

### Weeks 7–10 — build only what the pilot asked for

- Top 1–2 requests from that specific pilot. Resist un-surfaced roadmap items.
- Second engagement — **now paid.**

### Weeks 11–13 — package the proof

- Case study with numbers, one-page price sheet, service menu.
- Sales conversation #2 with proof, not demo.
- **Cap concurrent deployments at 2–3.**

### Money verdict

Raise nothing. $0 + 90 days → the signal that makes a $50–150k pre-seed a
reasonable ask. The moment a safety manager says "I'd pay for this" and does,
money becomes raiseable.

---

## 3. Shared-review block (paste into Claude AND Grok — updated for v2)

> **ROLE:** Product strategist. You previously reviewed ErgoVigilance (AI
> ergonomics monitoring: camera→MediaPipe→biomechanical features→risk engine→
> alerts→reports; offline-first, single-person tracking, no clinical validation,
> no customers; your verdict was service-first, PMF 2–4/10).
>
> **THE PLAN I'M RUNNING (90 days, $0, v2 after incorporating your critique):**
> - Weeks 1–3: Cold outreach to 30+ EHS consultants/safety managers is the
>   protected daily resource, offering a free 2-week single-station assessment in
>   exchange for feedback + case study. RTSP/IP camera support + Windows service
>   packaging + liability disclaimers run in spare time, budgeted at 2.5–3 weeks.
>   If forced to pick, outreach wins — a pilot with a rougher installer is still a
>   pilot.
> - Weeks 3–6: Land ONE unpaid/cheap pilot on a real factory floor. Deliver a
>   real assessment report. Capture what the safety manager looks at/ignores/asks
>   for. Start one university-lab validation conversation in parallel.
> - **Week-6 checkpoint (failure branch):** if nothing is signed, switch channel
>   from cold outreach to warm network — employer's industrial network, university
>   career/industry-liaison contacts, personal warehouse/manufacturing
>   connections. Warm-through-a-person beats cold-through-a-platform.
> - Weeks 7–10: Build ONLY the top 1–2 requests from that pilot. Second
>   engagement, now paid.
> - Weeks 11–13: Case study with numbers, one-page price sheet, sales
>   conversation #2 with proof. Cap concurrent deployments at 2–3.
> - Decision: no funding raised. Single-worker-per-camera framing for pilot #1.
>   Multi-person deferred until a real customer names it as the blocker. The PMF
>   ladder is a tracking tool only — the real metric is conversations, and the
>   real target is one safety manager saying "I'd pay for this."
>
> **Answer these, in order:**
> 1. What would make this plan fail, specifically — where is it weakest?
> 2. Which one decision would you change, and what would you do instead?
> 3. What is the single best question to ask the pilot safety manager on day 1
>    that we might not think to ask?
> 4. Is the 2.5–3-week code block (RTSP/installer/liability) correctly scoped
>    behind the outreach priority, or should it be cut further?
> 5. Is the week-6 warm-network failure branch the right fallback — and what
>    would you add to it?
> 6. What does success look like on day 91, and what's the #1 weekly metric?
>
> Be direct. If the plan is wrong, say so and propose the replacement.

**Convergence rule:** where reviewers agree on a change, adopt it. Where they
disagree, that decision lands on the founder — bring the disagreement back and
decide with full information.

---

## 3.5 Pilot-intake appendix (v3, 2026-08-09) — what happens when requests come in

Added once the pilot-request landing page is live and outreach is running. These
files live in `docs/pilot/`; the tracker is the operating surface.

### Intake pipeline

1. **Landing page → inbox.** Requests land in the admin **Pilot Requests** page
   (SQLite-backed) — they also arrive by email if the landing page form is
   deployed against the live API. Check both daily.
2. **Qualifying call** (15–20 min, the goal is a call, not email). Use the
   intake tracker to record: name, company, site type, camera/network readiness,
   decision-maker (y/n), call date, triage score (0–10), status.
3. **Gate:** score ≥ 7 AND decision-maker = yes → `scheduled`. Send the
   pre-deployment checklist + worker consent one-pager. Everything else goes to
   `waitlisted` with a follow-up date.
4. **Deploy** using the Windows service installer (`deploy/install_windows_service.ps1`)
   + `deploy/README.md`. Status → `active`.
5. **Cap: max 2 `active` pilots.** Hard rule — see tracker README. New
   qualifying sites waitlist; scarcity reads as demand.

### The code block is DONE (2026-08-09) — deployment-ready

The Weeks 1–3 code block is no longer "in progress":

- **RTSP/IP camera support** — `CAMERA_SOURCES` env (JSON list of `{id, name,
  url}`) exposes factory IP cameras in Settings + Multi-Camera; sessions can
  start on a USB index or an RTSP URL through one code path; raw feeds work for
  both. Also fixed a latent `NameError` (`active_index`) that crashed
  `/api/cameras` during live sessions.
- **Windows service packaging** — `deploy/install_windows_service.ps1`
  (NSSM, auto-downloads if missing, env from `.env`, log rotation, auto-restart)
  + uninstaller + `deploy/README.md` with the full pilot-site install guide.
- **Liability language on every report** — standard "heuristic thresholds, not
  clinically validated, not a medical device" disclosure on all four PDF report
  types (single choke point in `report_pdf.py`), plus the session summary JSON
  and every CSV/JSON/email/share export in the UI.

**Remaining before a real pilot (hardware, not code):** a qualifying call →
pre-deployment checklist → a site with a camera. The remaining *code* lever is
only what that specific pilot asks for.

### Pilot ops files (all in `docs/pilot/`)

| File | Purpose |
|---|---|
| `PILOT_INTAKE_TRACKER.csv` + `.md` | Spreadsheet template, triage rubric, status flow, cap-at-2 policy |
| `PILOT_DEPLOYMENT_CHECKLIST.md` | Camera/network/contact/consent/rollback — run before every deploy |
| `WORKER_CONSENT_ONEPAGER.md` | Printable "what this is" for the person on camera (union/privacy risk) |

---

## 4. The path, concluded

**Chosen: Service-first → pilot-driven product.** Rejected product-first (build
bias trap) and partnership-first (too slow for 90 days).

The 90 days are ~80% sales/fieldwork, ~15% a 2.5–3-week code block (outreach
protected over code), ~5% packaging. Success criterion: a real safety manager
says *"I'd pay for this"* — followed by an invoice. If the first channel fails,
the plan has a branch, not a cliff.
