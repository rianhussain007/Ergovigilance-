# TRL-8 / TRL-9 Qualification Plan — pilot exit to proven product

Companion to `docs/TRL7_QUALIFICATION_PLAN.md` (C1–C4) and
`docs/SELL_READINESS_AUDIT.md` (commercial gaps). Written 2026-09-26.
Synced 2026-10-02: §2 carries the measured status and the evidence pack is
`docs/TRL8_QUALIFICATION_EVIDENCE.md` (+ the generated
`docs/TRL8_TRACEABILITY.md`). Regenerate both with
`python scripts/qualification/run_qualification.py --write-docs`; the
harness exits non-zero if any executed check fails, or if the matrix cites
a check or file that does not exist. The 2026-10-02 battery
(`outputs/qualification/20261002T051101Z/`) returned 14 pass / 0 fail /
0 blocked / 2 opt-in skips — QUALIFIED.

## 1. Where TRL-7 ends

TRL-7 closes at the Day-15 exit review (`TRL7_QUALIFICATION_PLAN.md`
§4.6): one site, 2 cameras, 2 weeks, §4.4 ledger complete, ergonomist
agreement filed, verdict "demonstrated" or an honest shortfall list.
Everything below starts from that verdict.

## 2. TRL-8 workstream — complete and qualified

NASA TRL-8: *system complete and qualified through test and
demonstration.* For ErgoVigilance = the register's P1 column
(`DEEP_AUDIT_REPORT.md`, "P1 — TRL-8 qualification"), each its own SHA:

| # | P1 item | Status 2026-09-28 | Evidence / what closes the rest |
|---|---|---|---|
| 1 | Pen-test + remediation | EXTERNAL-PENDING | Scope pack `docs/PENTEST_SCOPE.md` (check `pentest-scope`); a vendor must execute it |
| 2 | DPIA + signed DPA/SCCs, SOC2 evidence | EXTERNAL-PENDING | `docs/DPA_TEMPLATE.md`, `docs/PRIVACY.md`, erasure/export endpoints (check `privacy-pack`); lawyer + audit required |
| 3 | Offsite backup + timed RTO drill | PARTIAL-INREPO | Hermetic drill PASS with **RTO 4 s** (2026-10-02; check `backup-restore-drill`, `outputs/backup_drill/result.json`); offsite replication is still an operator target |
| 4 | PG retention + crypto-erasure | CLOSED-INREPO | Single retention policy + key destruction + page reclaim (check `erasure-ops`) |
| 5 | HPA / load qualification | PARTIAL-INREPO | Concurrent-user load — 20/20 workers authenticated, 61.3 rps, p95 379 ms — plus kill/reconnect drill, measured single-host (checks `load`, `reconnect-drill`); the 50-camera run needs a cluster and more feeds than exist |
| 6 | SBOM + Trivy + secret-scan, pinned images, `readOnlyRootFilesystem` | CLOSED-INREPO | Pinned hard gates + CycloneDX SBOM in `.github/workflows/ci.yml` (check `supply-chain-gates` 6/6; `--with-scans` runs the engines locally) |
| 7 | Frontend unit tests | CLOSED-INREPO | vitest + typecheck + build (checks `frontend-unit`, `frontend-typecheck`, `frontend-build`) |
| 8 | Stale-doc quarantine + count reconciliation | PARTIAL-INREPO | `doc-counts` re-derives every quoted count from the suites it ran (5 stale numbers found and fixed 2026-09-28; parser and red-suite handling hardened 2026-10-02); frozen dated records excluded by design |
| 9 | Pilot accuracy re-measure → Safe Claims edit | SITE-DEPENDENT | Ergonomist-labelled pilot sample; deliberate reviewed edit only (§4.5 rules) |

**The harness is the gate, not this table:**
`scripts/qualification/run_qualification.py` returns 0 only when every
executed check passed, and it refuses to run when a matrix row cites a
check that does not exist or an implementation file that is missing.

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
  The supply-chain and frontend lanes have since landed (§2 rows 6–7).
- TRL-8 is not claimed complete while rows 1, 2, 5 and 9 are open, and
  TRL-9 is not claimed at all until a paid site and its operating window
  exist — see `docs/TRL8_QUALIFICATION_EVIDENCE.md` §5–§6.
