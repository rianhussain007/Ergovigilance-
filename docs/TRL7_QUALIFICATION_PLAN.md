# TRL-7 Qualification Plan — definition, in-repo workstream, executable pilot

Companion to `docs/TRL6_EVIDENCE.md` (TRL-6 evidence) and
`docs/P0_REVERIFICATION.md` (hardening status). Written 2026-09-26.

## 1. What TRL-7 means for this product

NASA TRL-7: *system prototype completed and demonstrated in an operational
environment.* For ErgoVigilance that translates to exactly four claims,
each with a named proof:

| # | TRL-7 claim | Proof required | Type |
|---|---|---|---|
| C1 | Runs sustained in a real workplace, not a dev box | ≥ 2 weeks of continuous operation at the pilot site, uptime + no data loss (0 truncated clips, sessions persisted) | Site + in-repo |
| C2 | Works for people who didn't build it | Operators (not developers) run the daily workflow: acknowledge alerts, review clips, export report | Site |
| C3 | Output is trusted enough to act on | Ergonomist-reviewed labels on a sample of alerts; inter-rater agreement recorded; **no HIGH claim unless a human certifies HIGH** | Site + ergonomist |
| C4 | The product-side is hardened for operations | All TRL-6/7 P0s closed or waived with evidence (`docs/P0_REVERIFICATION.md`) | In-repo |

**TRL-6 status: CLOSED 2026-09-26.** Evidence pack complete
(`docs/TRL6_EVIDENCE.md`, relevant-environment 4-camera RTSP demo with
Runs A/B/C, identity attribution, UDP probe) and the spot-check sheet was
human-reviewed on 2026-09-26: 2 HIGH confirmed, 3 rejected (model HIGH
over-warn — human said LOW ×2 / MEDIUM ×1), 7 unrateable (blurred/small
subjects). n=5 rateable is process evidence only, never an accuracy
figure. That review's camera-labelability lesson is now a site-gate
requirement (§4.1).

**The fast path:** C4 is pure in-repo work (§3, starts immediately) and C1
can only be earned by wall-clock time at the site — so the pilot protocol
(§4) is written to be executable *now*, letting the 2-week clock overlap
the C4 work instead of queueing behind it.

## 2. Definition of Done (evidence mapping)

| Claim | Already in hand | Missing | Owner |
|---|---|---|---|
| C1 sustained operation | 4-hour soak capability (`--seconds 14400`), moov/idx1 guard (0/628 + 0/270 truncated), graceful soak teardown, `restart: unless-stopped` compose (`docker-compose.yml:24,59,82,110`) | 2 consecutive weeks at the site with the uptime/clip-integrity metrics of §4.4 collected daily | Site |
| C2 non-builder users | RBAC 4-role, alert acknowledge/review/PDF flows, MFA (`bc093f6`) | ≥ 2 operators completing the daily workflow unassisted for ≥ 5 days; 1 usability incident log | Site |
| C3 trusted output | 87.6% LOW/MEDIUM Safe Claims number; spot-check sheet drafted (`outputs/tri6_demo/spotcheck/`); 21 identity tests | Human approval of spot-check; ergonomist review of pilot alert sample; agreement stats | User + ergonomist |
| C4 product hardening | 4/10 P0 CLOSED, 3 PARTIAL | 3 OPEN + 3 PARTIAL closed (§3) | In-repo (this agent) |

## 3. In-repo workstream (C4) — ordered, each its own SHA

Run these **after** the TRL-6 consolidation soak frees the CPU; gates
(`backend 425 / cloud 134 / tsc`) run once at the end over everything.

1. **P0-6 privacy retention unification** — one settings source of truth
   (e.g. `RETENTION_DAYS` + per-store overrides) replacing audit 365
   (`audit_log.py:35`), DB 90 (`db_backend.py:282`), recordings 30
   (`storage_manager.py:31`), sessions/alerts (`api.py:1052-1053`).
   Tests: config resolution + each store's cleanup honoring it.
2. **P0-8 audit integrity** — set `AUDIT_HMAC_KEY` via compose (fail-closed
   `:?` like `docker-compose.yml:41`), drop the ephemeral
   `token_hex(32)` default (`audit_log.py:38`), mount an `audit_logs`
   volume, align the empty-default `AUTH_JWT_SECRET` at
   `docker-compose.yml:104` with the `:?` gate.
3. **P0-9 PDF path** — either add a Chromium stage to
   `backend_api/Dockerfile` or implement + test the documented
   "optional" fallback; verify `/api/cloud/reports/pdf` in a container.
4. **P0-10 metrics disclosure** — decision + code: keep `/healthz`,
   `/readyz` open (healthchecks require it, `ops.py:9`) but gate
   `/metrics` (`ops.py:93`) behind auth or an allowlist.
5. **P0-3 TLS issuance** — script/verify the Let's Encrypt path against a
   staged host (or document self-hosted cert rotation); handshake proof
   attached to the doc.
6. **P0-7 backup drill** — run `restore.sh` into a throwaway container,
   record RTO + integrity result; encrypt the archive.
7. **Recordings disk guard** — clip floods are currently bounded only by
   alert cooldown (`ingestion.py:816`); add a low-watermark prune
   (delete oldest clips below N GB free) + metric, test with a fake
   filesystem. *This is the one operational failure mode the 4-hour run
   cannot prove absent (disk headroom on this host).*

Out of scope here (defer, listed honestly): pen-test, DPIA/SOC2, HA,
fleet/SSO — the register's P1 column (`DEEP_AUDIT_REPORT.md:255-259`),
i.e. TRL-8.

## 4. Pilot protocol (C1–C3) — executable

### 4.1 Site gate (before signing — score ≥ 7 required)

A qualifying site: ≥ 1 assembly/handling line, stable lighting, camera
mounting points ≥ 2.2 m, wired power, management willing to record
workers **with posted consent**, and a named internal champion. Reject
sites that cannot commit the 2-week window.

**Labelability gate (added 2026-09-26, from the TRL-6 spot-check
outcome):** before a site qualifies, grab trial frames from the actual
cameras at the actual mounting points and confirm a human can assess
posture from them (subject large enough, no motion blur at capture). The
TRL-6 spot-check had **7/12 frames unrateable** because the source
footage's subjects were too small/blurry — a camera that cannot be
labelled produces alerts no ergonomist can verify, so it fails the site
gate even if the pipeline runs perfectly. Use
`scripts/verify_one_camera.py` / `scripts/verify_station_rois.py` to
capture and check trial frames.

### 4.2 Setup day (Day 0)

- [ ] Deploy: `docker compose -f docker-compose.yml -f docker-compose.tls.yml up -d` (TLS overlay per `docker-compose.yml:76-77`, certs via `certs/README.md`); verify `/readyz`.
- [ ] Cameras: 2 for pilot (per Safe Claims: 1–2 cameras, controlled pilot). RTSP feeds into the cloud core; verify per-cam FPS ≥ target with `scripts/soak_cloud.py --urls ... --seconds 120` (this doubles as the site's baseline latency row).
- [ ] Consent: posted notice + per-worker consent record (worker_consent flow) before any recording; face recognition **off** unless separately consented — badge/QR is the default identity path (21 tests, `yolo_cloud/tests/test_identity.py`).
- [ ] Accounts: 1 supervisor + 2 operators, MFA enrolled (`POST /auth/login/mfa` path), no shared logins.
- [ ] Baseline: ergonomist walks the line, records existing RULA/REBA observations (this is the pre-pilot reference, not a product output).
- [ ] Export: retention + clock/NTP check; disk watermark confirmed (§3.7 guard if landed, else manual free-space check daily).

### 4.3 Daily operation (Days 1–14) — the C2 loop

Per shift, each operator, unassisted after onboarding:

1. Confirm cameras healthy (dashboard green / `/readyz`).
2. Acknowledge or dismiss HIGH/MEDIUM alerts; for each dismissed, pick
   the reason from the list (false pose / wrong task / occluded /
   not-a-worker).
3. End of shift: export the daily PDF report; file it.
4. Onboarding = one 30-minute session using the existing UI; note every
   point where the operator needed a developer (that is usability data).

### 4.4 Metrics to collect daily (C1 evidence — mostly automated)

| Metric | Source | Target |
|---|---|---|
| Uptime / restarts | compose `restart` count, `/healthz` logs | ≥ 99% shift-time availability |
| Clips saved / truncated | soak + `clips.truncated_total` | **truncated = 0** always |
| Frames dropped, p95 | processing metrics per camera | recorded, not gamed; investigate regressions |
| Identity bind success | `outputs/audit/identity_audit.jsonl` bind/reentry counts | every regular worker bound ≥ once/shift |
| Alert volume / camera / shift | alerts store | trend; spike = investigate, not silence |
| Operator dismiss reasons | §4.3 step 2 | false-alert rate trending down week 1→2 |
| Disk free | host | never < 20% |

### 4.5 Label handoff (C3 evidence) — weeks 2–3

1. Random sample: ≥ 50 alerts stratified by camera/severity (the 5
   rateable spot-check rows from 2026-09-26 are included as seed rows).
2. Ergonomist reviews **frames + context** (clip is pre-alert context,
   `recordings/clips/`), labels task + risk level independently of the
   model; disagreements adjudicated in a 1-hour session.
3. Record agreement stats per band (same format as Safe Claims: precision
   / recall / support). **Rules:** no product-accuracy figure outside the
   existing 87.6% LOW/MEDIUM Safe Claims number may be quoted until this
   completes; HIGH stays unvalidated unless the ergonomist certifies HIGH
   examples; any new number enters Safe Claims only through a deliberate,
   reviewed edit (never silently).
4. Output: `pilot_labels_ergonomist.csv` + agreement JSON → this, plus
   §4.4 uptime, closes C3 and finishes the TRL-7 evidence pack.

### 4.6 Exit review (Day 15)

Assemble: §4.4 table + operator incident log + ergonomist agreement +
`docs/TRL6_EVIDENCE.md` → a single TRL-7 status block appended to the
evidence pack (same style as TRL-6). Verdict wording candidates:
"TRL-7 demonstrated at one site, 2 cameras, 2 weeks, screening aid only"
— or the honest shortfall list if any C1–C3 target was missed.

## 5. Immediate sequence (who does what)

| When | What | Owner |
|---|---|---|
| Now | TRL-6 consolidation (4 h soak, UDP probe, doc reconcile) | Agent 2 |
| Now | C4 workstream §3 prep + this plan | Agent 1 (this session) |
| Done 2026-09-26 | Spot-check sheet human-reviewed → TRL-6 closed (2 HIGH / 3 over-warn / 7 unrateable) | **User** ✓ |
| This week | Site selected against §4.1; Day 0 executed | **User + site** |
| Weeks 1–2 | §4.3–4.4 daily loop | Site operators |
| Week 3 | §4.5 label handoff | Ergonomist |
| Day 15 | §4.6 exit review → TRL-7 verdict | User + Agent 1 |

## 6. Non-claims (standing rules)

- "Screening aid, not medical device." Never: prevents injuries /
  clinically certified / works in every factory / 8 workers per feed /
  10 FPS per feed / GPU numbers (none measured).
- Only customer-safe accuracy: **87.6% on 500 human frames, LOW/MEDIUM**;
  cloud engine = **no accuracy claim** (1/119 both profiles);
  never quote 94.1/97.6/88.6/86.4/76.9%.
- This plan changes no Safe Claims language; pilot-derived numbers enter
  it only via an explicit, reviewed edit.
