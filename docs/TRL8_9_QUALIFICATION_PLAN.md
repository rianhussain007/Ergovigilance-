# TRL-8 / TRL-9 Qualification Plan — pilot exit to proven product

Companion to `docs/TRL7_QUALIFICATION_PLAN.md` (C1–C4) and
`docs/SELL_READINESS_AUDIT.md` (commercial gaps). Written 2026-09-26.

## 1. Where TRL-7 ends

TRL-7 closes at the Day-15 exit review (`TRL7_QUALIFICATION_PLAN.md`
§4.6): one site, 2 cameras, 2 weeks, §4.4 ledger complete, ergonomist
agreement filed, verdict "demonstrated" or an honest shortfall list.
Everything below starts from that verdict.

## 2. TRL-8 workstream — complete and qualified

NASA TRL-8: *system complete and qualified through test and
demonstration.* For ErgoVigilance = the register's P1 column
(`DEEP_AUDIT_REPORT.md`, "P1 — TRL-8 qualification"), each its own SHA:

| # | P1 item | Owner / status 2026-09-26 |
|---|---|---|
| 1 | Pen-test + remediation | User (book vendor); fixes in-repo after |
| 2 | DPIA + signed DPA/SCCs, SOC2 evidence | User + lawyer; `DPA_TEMPLATE.md` exists |
| 3 | Offsite backup + timed RTO drill | Hermetic drill exists (`deploy/backup_restore_drill.sh`); RTO run pending |
| 4 | PG retention + crypto-erasure | Telemetry prune landed (`efa8b15`); erasure procedure open |
| 5 | HPA / load qualification | `deploy/load_test.py` exists; 50-cam run unmeasured |
| 6 | SBOM + Trivy + secret-scan, pinned images, `readOnlyRootFilesystem` | Agent 2 (TRL-8 supply-chain lane) |
| 7 | Frontend unit tests | Agent 2 |
| 8 | Stale-doc quarantine + count reconciliation | Agent 2 (verify pass) |
| 9 | Pilot accuracy re-measure → Safe Claims edit | Ergonomist + deliberate reviewed edit only (§4.5 rules) |

Out of scope for TRL-8 (TRL-9): second site, production upgrades,
support track record.

## 3. TRL-9 lean bar (agreed 2026-09-26)

TRL-9 = *proven in operational environment.* Closed when ALL hold:

- [ ] **1 paid site**: pilot converted (assessment credit or direct),
  contract filed
- [ ] **3 months** continuous operation with the §4.4 ledger unbroken
- [ ] **Zero data loss**: `clips_truncated_total == 0` across the window
- [ ] **1 clean in-place upgrade**: version bump with zero data loss,
  rollback path tested first
- [ ] **Published case study**: `docs/pilot/CASE_STUDY_TEMPLATE.md`
  filled, guardrails signed off, customer permission filed

## 4. Timeline (vs `PMF_90DAY_PLAN.md`)

| Window | Milestone |
|---|---|
| Weeks 1–2 | Pilot runs (§4.3–4.4); metrics ledger accumulates |
| Week 3 | §4.5 label handoff; ergonomist agreement |
| Day 15 | Exit review → TRL-7 verdict |
| Weeks 4–6 | TRL-8 P1 batch (pen-test, DPIA, load, supply-chain) |
| Month 2–4 | Paid operation → TRL-9 evidence accumulates |
| Month 4 | TRL-9 review against §3 |

The 90-day sales clock and the TRL clock are the same clock: every
pilot week either produces ledger rows or a shortfall note.

## 5. Standing rules (inherited)

- Safe Claims discipline from `TRL7_QUALIFICATION_PLAN.md` §6 applies
  unchanged through TRL-9; pilot numbers enter only via deliberate edit.
- One SHA per item; `file:line` cites; no other agent's lanes
  (Agent 2: CI/supply-chain/frontend; deploy session: TLS/drills).
