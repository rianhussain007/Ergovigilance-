"""TRL-8 / TRL-9 requirements → implementation → check → status.

One row per criterion in ``docs/TRL8_9_QUALIFICATION_PLAN.md`` (§2 TRL-8
P1 register, §3 TRL-9 lean bar). The qualification harness imports this
module, refuses to run if any row cites a check id that does not exist,
and renders ``docs/TRL8_TRACEABILITY.md`` from it — so the matrix cannot
silently drift from the checks that actually execute.

Status vocabulary (deliberately blunt — nothing here may round up):

- ``CLOSED-INREPO``   verifiable here, and the cited checks pass.
- ``PARTIAL-INREPO``  an in-repo part landed, a named part has not.
- ``EXTERNAL-PENDING``needs a third party / vendor / lawyer.
- ``SITE-DEPENDENT``  needs a real site, real cameras, or wall-clock time
                      in operation; no amount of repo work produces it.
- ``BUSINESS-DEPENDENT`` needs a signed customer or published artifact.

``not_covered`` is mandatory on every row: it is the sentence that stops a
row being read as more than it is. Screen aid, not a medical device.
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# TRL-8 — docs/TRL8_9_QUALIFICATION_PLAN.md §2 (register: DEEP_AUDIT_REPORT
# §12 "P1 — TRL-8 qualification")
# --------------------------------------------------------------------------
CRITERIA: list[dict] = [
    {
        "id": "TRL8-1",
        "criterion": "Pen-test + remediation",
        "status": "EXTERNAL-PENDING",
        "implementation": [
            "docs/PENTEST_SCOPE.md",
            "docs/SECURITY_QUESTIONNAIRE.md",
        ],
        "checks": ["pentest-scope"],
        "evidence": "Scope, target inventory and rules of engagement are in-repo; the test itself is booked with a vendor.",
        "not_covered": "No third-party penetration test has been executed, so no 'pen-tested' claim may be made. Remediation of findings cannot be scheduled before findings exist.",
    },
    {
        "id": "TRL8-2",
        "criterion": "DPIA + signed DPA/SCCs, SOC2 evidence",
        "status": "EXTERNAL-PENDING",
        "implementation": [
            "docs/DPA_TEMPLATE.md",
            "docs/PRIVACY.md",
            "docs/SECURITY_QUESTIONNAIRE.md",
            "backend_api/app/api/privacy.py",
        ],
        "checks": ["privacy-pack"],
        "evidence": "DPA template, privacy policy and the admin-only erasure/export endpoints; consent + audit trail are implemented and tested.",
        "not_covered": "No DPIA has been signed off and no DPA/SCC is executed; SOC2 has no audit. Templates are not agreements.",
    },
    {
        "id": "TRL8-3",
        "criterion": "Offsite backup + timed RTO drill",
        "status": "PARTIAL-INREPO",
        "implementation": [
            "deploy/backup.sh",
            "deploy/restore.sh",
            "deploy/backup_restore_drill.sh",
            "docs/BACKUP_RESTORE_OPS.md",
        ],
        "checks": ["backup-restore-drill"],
        "evidence": "Hermetic backup→encrypt→decrypt→restore→verify drill with a measured RTO (seconds) written to outputs/backup_drill/result.json.",
        "not_covered": "The drill is a sandbox restore on this host: it proves the scripts and a local RTO, not an offsite target. Offsite replication is an operator configuration and no remote destination has been exercised.",
    },
    {
        "id": "TRL8-4",
        "criterion": "PG retention + crypto-erasure",
        "status": "CLOSED-INREPO",
        "implementation": [
            "backend_api/app/services/retention.py",
            "backend_api/app/api/privacy.py",
            "backend_api/app/core/audit_log.py",
            "backend_api/app/core/database.py",
            "yolo_cloud/disk_guard.py",
        ],
        "checks": ["erasure-ops"],
        "evidence": "Single retention policy resolved from configuration, worker-scoped delete + portability export, key-file destruction and page reclamation as the documented erasure steps.",
        "not_covered": "Erasing a row does not erase it from a backup archive taken earlier; backup retention is governed by the archive's own lifecycle, which is an operator policy.",
    },
    {
        "id": "TRL8-5",
        "criterion": "HPA / load qualification (50-camera run)",
        "status": "PARTIAL-INREPO",
        "implementation": [
            "deploy/load_test.py",
            "scripts/soak_cloud.py",
            "scripts/ffmpeg_reconnect_drill.py",
            "yolo_cloud/rtsp_manager.py",
        ],
        "checks": ["load", "soak", "reconnect-drill"],
        "evidence": "Concurrent-user load, multi-stream soak and a kill/reconnect drill, each measured on this host and recorded with its limits.",
        "not_covered": "The 50-camera / horizontal-scale qualification requires a cluster and more camera feeds than exist; on this box the numbers are single-host CPU-only and must never be quoted as fleet capacity.",
    },
    {
        "id": "TRL8-6",
        "criterion": "SBOM + Trivy + secret-scan, pinned images, readOnlyRootFilesystem",
        "status": "CLOSED-INREPO",
        "implementation": [
            ".github/workflows/ci.yml",
            ".gitleaks.toml",
            "docker-compose.yml",
        ],
        "checks": ["supply-chain-gates", "scans"],
        "evidence": "Pinned scanner images running as hard gates in CI, CycloneDX SBOM artifact, plus the same scanners run locally by the harness.",
        "not_covered": "A scan is a snapshot: it covers the dependency and configuration state at run time, and the vulnerability feed is advisory (drifts daily). Nothing here is an attestation of the build artifacts.",
    },
    {
        "id": "TRL8-7",
        "criterion": "Frontend unit tests",
        "status": "CLOSED-INREPO",
        "implementation": ["ui_posture/src", "ui_posture/package.json"],
        "checks": ["frontend-unit", "frontend-typecheck", "frontend-build"],
        "evidence": "Vitest suite plus typecheck and production build, all run by the harness and by CI.",
        "not_covered": "Component/unit coverage is not end-to-end browser coverage; the operator clickthrough is a manual procedure (docs/pilot/PILOT_DEPLOYMENT_CHECKLIST.md).",
    },
    {
        "id": "TRL8-8",
        "criterion": "Stale-doc quarantine + count reconciliation",
        "status": "PARTIAL-INREPO",
        "implementation": [
            "scripts/qualification/run_qualification.py",
            "README.md",
            "docs/CURRENT_STATE.md",
        ],
        "checks": ["doc-counts"],
        "evidence": "The harness re-derives every quoted test count from the suites it just ran and fails if a live doc still quotes a stale number.",
        "not_covered": "Only the phrasings listed in the harness are reconciled, and the frozen TRL-6 / TRL-7 / P0 records are intentionally excluded because they are dated evidence, not current claims.",
    },
    {
        "id": "TRL8-9",
        "criterion": "Pilot accuracy re-measure → Safe Claims edit",
        "status": "SITE-DEPENDENT",
        "implementation": [
            "scripts/label_tool.py",
            "scripts/evaluate_ground_truth.py",
            "docs/ERGOVIGILANCE_HANDBOOK.md",
        ],
        "checks": [],
        "evidence": "Labeling tooling and the 87.6% LOW/MEDIUM Safe Claims baseline exist; the pilot sample has not been labelled.",
        "not_covered": "No new accuracy number exists, so the Safe Claims figure stays 87.6% LOW/MEDIUM on 500 frames. HIGH stays unvalidated until an ergonomist certifies HIGH examples.",
    },
    # ----------------------------------------------------------------------
    # TRL-9 — docs/TRL8_9_QUALIFICATION_PLAN.md §3 (lean bar)
    # ----------------------------------------------------------------------
    {
        "id": "TRL9-1",
        "criterion": "1 paid site: pilot converted, contract filed",
        "status": "BUSINESS-DEPENDENT",
        "implementation": [
            "docs/pilot/PILOT_INTAKE_TRACKER.md",
            "docs/pilot/PILOT_INTAKE_TRACKER.csv",
            "docs/ErgoVigilance_Assessment_Pricing.md",
        ],
        "checks": ["pilot-pack"],
        "evidence": "Intake tracker, consent one-pager and pricing exist so a conversion can be filed the day it happens.",
        "not_covered": "No customer has signed and paid. This is the gate no repository change can close.",
    },
    {
        "id": "TRL9-2",
        "criterion": "3 months continuous operation with §4.4 ledger unbroken",
        "status": "SITE-DEPENDENT",
        "implementation": [
            "scripts/pilot_metrics.py",
            "scripts/test_pilot_metrics.py",
        ],
        "checks": ["pilot-pack"],
        "evidence": "The §4.4 ledger collector runs and is tested, so the clock can start on Day 0.",
        "not_covered": "Zero days of real operation have elapsed. The ledger is empty; a 3-month window cannot be simulated.",
    },
    {
        "id": "TRL9-3",
        "criterion": "Zero data loss: clips_truncated_total == 0 across the window",
        "status": "PARTIAL-INREPO",
        "implementation": [
            "yolo_cloud/ingestion.py",
            "yolo_cloud/disk_guard.py",
            "docs/SIZING_SOAK_CLOUD.md",
        ],
        "checks": ["cloud-suite", "soak"],
        "evidence": "moov/idx1 guard plus the local soak's truncated-clip counter; the 4-hour Run C in docs/TRL6_EVIDENCE.md recorded 0 truncated clips.",
        "not_covered": "The counter is zero for the runs performed here; a 3-month site window is unmeasured, and disk-headroom behaviour on the site's storage is unknown.",
    },
    {
        "id": "TRL9-4",
        "criterion": "1 clean in-place upgrade with zero data loss and a tested rollback",
        "status": "SITE-DEPENDENT",
        "implementation": [
            "docs/UPGRADE_RUNBOOK.md",
            "docs/DEPLOYMENT.md",
            "docker-compose.yml",
        ],
        "checks": [],
        "evidence": "Upgrade and rollback procedures are written with the compose version bump and volume layout.",
        "not_covered": "No production instance exists to upgrade, so the procedure is documented and drilled nowhere. A rehearsal against a live stack with real data is still required.",
    },
    {
        "id": "TRL9-5",
        "criterion": "Published case study with signed guardrails and customer permission",
        "status": "BUSINESS-DEPENDENT",
        "implementation": ["docs/pilot/CASE_STUDY_TEMPLATE.md"],
        "checks": ["pilot-pack"],
        "evidence": "Case-study template with the guardrail and permission fields already enumerated.",
        "not_covered": "Nothing is published and no permission has been granted; an unpublished template is not a case study.",
    },
]
