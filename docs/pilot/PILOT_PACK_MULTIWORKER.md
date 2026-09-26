# Multi-Worker Pilot Pack (Cloud, 4+ Cameras)

Per-station addendum to `PILOT_DEPLOYMENT_CHECKLIST.md`. Use it when one
camera covers **several workers** (5–10 tiles per frame) and identity binding
is required. Nothing here changes risk logic, pricing, or accuracy claims.

## 1. Identity at the site (badge-first)

- [ ] **Badge flow chosen and tested:** scan →
      `POST /cameras/{id}/tracks/{track_id}/identity` binds the tile.
      Rebinding an existing tile to a different worker is allowed and audited
      as an ID switch.
- [ ] **Re-entry verified:** worker leaves frame and returns → same track_id
      rebinds automatically (`reentry_rebinds` in the soak summary; ambiguous
      re-entries are logged as `reentry_ambiguous` and left unbound).
- [ ] **Supervisor override path known:** dashboard or
      `POST /cameras/{id}/tracks/{track_id}/identity/override` with actor +
      reason — used when badge/face is wrong. Every override is in the
      audit log and counts toward the success metric below.
- [ ] **Face identity is OFF by default.** It is consent-gated
      (`identity_mode='face'`, consent not denied) and only binds from
      verified-band face records. If used: enrollment → consent record →
      test match → all three documented.
- [ ] **Withdrawal rehearsed once:** `consent/withdraw` → tile unbinds, face
      data wiped, re-bind blocked. This is the demonstration the works
      council will ask for.
- [ ] **Audit trail location known:** `GET /identity/audit` (also mirrored to
      PostgreSQL when configured). Every bind/rebind/override/withdraw is in
      there — pull it at the end of day one and show it to the contact.

## 2. Signage (site-visible, before day one)

- [ ] Sign at every monitored zone entrance: *"This area is monitored by an
      ergonomics screening system for safety. Video is processed on-site and
      not published. Contact: ____________."*
- [ ] Sign text matches what the consent one-pager says (no new promises).
- [ ] Photo of each installed sign attached to the intake tracker row.

## 3. Screening-aid agreement (with the site contact)

Risk scores are an **early-warning screening aid** — they prioritize where a
supervisor looks; they are not discipline evidence. Get explicit agreement:

- [ ] Alerts are reviewed by a supervisor before any action.
- [ ] No automated decisions about workers from alerts.
- [ ] Override records are treated as the site's own corrections.

## 4. Day-one per-tile test (multi-worker, ~15 minutes)

For **each camera**, with all real workers in frame:

1. Start a session; open `/api/cloud/cameras/{id}/persons` and confirm one
   tile per worker (`person_count` matches head-count, labels stable).
2. Each worker slouches deliberately for ~5 s (this is the tile-level
   equivalent of the single-worker checklist step) → an alert naming that
   worker's tile appears.
3. Badge-scan two workers; verify their tiles show `worker_id` and the audit
   log gains two `bind` events.
4. Pull `GET /persons/{track_id}/timeline?limit=50` for one bound worker —
   the risk series should show the deliberate slouch window.
5. Record: camera id, head-count, tiles matched, overrides used:
   `________________________________`

## 5. Success metric (agreed BEFORE go-live, measured from the data)

- [ ] **Primary:** alerts per worker per shift, split by risk level —
      target band agreed with the contact (looping-clip soak numbers are NOT
      field rates; do not quote them).
- [ ] **Quality guard:** supervisor override rate = overrides ÷ (binds +
      rebinds) from `identity_audit_counts` in the soak/summary or the audit
      endpoint — agree the acceptable band (pilot target: low; a high rate
      means identity, not workers, needs fixing).
- [ ] **Stability guard:** `id_switches` per shift from the same summary —
      expected near zero after day one.
- [ ] Review cadence: weekly call with the contact; export the audit log +
      summary JSON each week.

## Sign-off

| Role | Name | Date |
|---|---|---|
| On-site contact | | |
| Worker rep (if applicable) | | |
| Founder / deployer | | |
