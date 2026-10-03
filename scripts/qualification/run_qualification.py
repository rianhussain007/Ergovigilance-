#!/usr/bin/env python3
"""TRL-8 qualification harness — regenerate the evidence with one command.

TRL-8 is "system complete and *qualified through test and demonstration*"
(`docs/TRL8_9_QUALIFICATION_PLAN.md` §2). A qualification nobody can re-run
is an anecdote, so every number quoted in `docs/TRL8_QUALIFICATION_EVIDENCE.md`
is produced here by a real command, with the raw log kept beside the JSON.

    python scripts/qualification/run_qualification.py                  # repo battery
    python scripts/qualification/run_qualification.py --with-drills --with-load
    python scripts/qualification/run_qualification.py --mode full --with-scans
    python scripts/qualification/run_qualification.py --only cloud-suite,doc-counts
    python scripts/qualification/run_qualification.py --write-docs

Outputs (gitignored, never committed):

    outputs/qualification/<UTC stamp>/qualification_report.{json,md}
    outputs/qualification/<UTC stamp>/logs/<check id>.log

Exit code 0 only when every *executed* check passed. ``BLOCKED`` counts as
a failure — an unproven criterion must not exit green — and
``--allow-blocked`` exists only for exploratory runs, never for evidence.

Honesty rules baked in: a check whose prerequisite is missing is BLOCKED
with the reason recorded, never guessed; a check that only inspects files
is reported as a definition/config check, not as a scan that ran; and the
``doc-counts`` check re-derives every quoted number from the runs in this
report instead of trusting a doc.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import traceability  # noqa: E402  (same-directory data module)

REPO = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO / "outputs" / "qualification"

PASS, FAIL, BLOCKED, SKIP = "PASS", "FAIL", "BLOCKED", "SKIP"


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------
@dataclass
class Check:
    id: str
    criterion: str
    title: str
    # "pytest" | "cmd" | "drill" | "load" | "soak" -> command checks,
    # "static" -> declarative file assertions below.
    kind: str
    cwd: Path = REPO
    cmd: list[str] = field(default_factory=list)
    timeout: int = 900
    requires: tuple[str, ...] = ()
    opt_in: str | None = None  # None = always on; else the flag that enables it
    expect: str = ""           # stdout marker required for PASS (drills)
    notes: str = ""
    artifacts: tuple[str, ...] = ()


COMMAND_CHECKS: list[Check] = [
    Check(
        id="backend-suite",
        criterion="TRL7-C4",
        title="Backend test suite",
        kind="pytest",
        cwd=REPO / "backend_api",
        # Exactly CI's command. No explicit -q: backend_api/pytest.ini already
        # passes one, and a second becomes -qq, which suppresses the final
        # "N passed" line this check parses (found 2026-09-28).
        cmd=[sys.executable, "-m", "pytest", "tests", "--tb=short"],
        timeout=2700,
        notes="Same command CI runs; counts feed the doc-counts gate.",
    ),
    Check(
        id="cloud-suite",
        criterion="TRL7-C4",
        title="Cloud-core test suite",
        kind="pytest",
        cmd=[sys.executable, "-m", "pytest", "yolo_cloud/tests", "-q", "--tb=short"],
        timeout=2700,
        notes="RTSP ingest, identity, entitlements, watchdog, orphan reaping.",
    ),
    Check(
        id="erasure-ops",
        criterion="TRL8-4",
        title="Right-to-erasure + retention operations",
        kind="pytest",
        cwd=REPO / "backend_api",
        cmd=[
            sys.executable, "-m", "pytest",
            "tests/test_erasure_ops.py", "tests/test_privacy.py", "-q", "--tb=short",
        ],
        timeout=600,
        notes="Erasure steps (key destroy, page reclaim) and worker-scoped delete/export.",
    ),
    Check(
        id="frontend-typecheck",
        criterion="TRL8-7",
        title="Frontend typecheck (tsc --noEmit)",
        kind="cmd",
        cwd=REPO / "ui_posture",
        cmd=["npx", "tsc", "--noEmit"],
        timeout=900,
        requires=("npx",),
    ),
    Check(
        id="frontend-unit",
        criterion="TRL8-7",
        title="Frontend unit tests (vitest)",
        kind="cmd",
        cwd=REPO / "ui_posture",
        cmd=["npx", "vitest", "run"],
        timeout=1200,
        requires=("npx",),
        notes="Counts feed the doc-counts gate.",
    ),
    Check(
        id="frontend-build",
        criterion="TRL8-7",
        title="Frontend production build",
        kind="cmd",
        cwd=REPO / "ui_posture",
        cmd=["npm", "run", "build"],
        timeout=1800,
        requires=("npm",),
    ),
    Check(
        id="reconnect-drill",
        criterion="TRL8-5",
        title="FFmpeg kill / reconnect drill",
        kind="drill",
        cmd=[sys.executable, "scripts/ffmpeg_reconnect_drill.py"],
        timeout=900,
        expect="RESULT: PASS",
        opt_in="drills",
        notes="Spawns the real reader against a fake camera, kills it mid-stream, proves recovery.",
    ),
    Check(
        id="backup-restore-drill",
        criterion="TRL8-3",
        title="Backup → encrypt → restore drill with measured RTO",
        kind="drill",
        cmd=["bash", "deploy/backup_restore_drill.sh"],
        timeout=900,
        expect="DRILL PASS",
        opt_in="drills",
        artifacts=("outputs/backup_drill/result.json",),
        notes="Hermetic sandbox; RTO comes from the drill's own result.json.",
    ),
    Check(
        id="load",
        criterion="TRL8-5",
        title="Concurrent-user load qualification",
        kind="load",
        timeout=600,
        opt_in="load",
        requires=("python",),
        notes="Needs a reachable backend; BLOCKED (not PASS) when the stack is down.",
    ),
    Check(
        id="soak",
        criterion="TRL8-5",
        title="Multi-stream soak (dropped frames / truncated clips)",
        kind="soak",
        cmd=[sys.executable, "scripts/soak_cloud.py"],
        timeout=3600,
        opt_in="soak",
    ),
]

# Declarative file assertions. These prove a *definition* exists and is not
# weakened — they are not scans that ran.
STATIC_CHECKS: list[dict] = [
    {
        "id": "supply-chain-gates",
        "criterion": "TRL8-6",
        "title": "Supply-chain gates defined and pinned (CI config)",
        "assertions": [
            (".github/workflows/ci.yml", "contains", "zricethezav/gitleaks:v8.30.1"),
            (".github/workflows/ci.yml", "contains", "ghcr.io/aquasecurity/trivy:0.58.1"),
            (".github/workflows/ci.yml", "contains", "--format cyclonedx"),
            (".github/workflows/ci.yml", "contains", "actions/upload-artifact@v4"),
            (".github/workflows/ci.yml", "contains", "--exit-code 1"),
            (".gitleaks.toml", "contains", "[allowlist]"),
        ],
        "notes": "Pinned scanner images as hard gates + CycloneDX SBOM artifact. Proves the gate is defined; --with-scans runs the engines.",
    },
    {
        "id": "pentest-scope",
        "criterion": "TRL8-1",
        "title": "Pen-test scope pack ready for a vendor",
        "assertions": [
            ("docs/PENTEST_SCOPE.md", "contains", "Targets (in scope)"),
            ("docs/PENTEST_SCOPE.md", "contains", "Out of scope"),
            ("docs/SECURITY_QUESTIONNAIRE.md", "contains", "Encrypted at rest"),
        ],
        "notes": "Scope + rules of engagement + questionnaire. Definition only — no test has been executed.",
    },
    {
        "id": "privacy-pack",
        "criterion": "TRL8-2",
        "title": "Privacy / DPA pack present",
        "assertions": [
            ("docs/DPA_TEMPLATE.md", "contains", "Data Processing"),
            ("docs/PRIVACY.md", "contains", "retention"),
            ("backend_api/app/api/privacy.py", "contains", "delete-worker-data"),
            ("backend_api/app/api/privacy.py", "contains", "export-worker-data"),
        ],
        "notes": "Templates and endpoints. An unsigned template is not an agreement.",
    },
    {
        "id": "pilot-pack",
        "criterion": "TRL9-1/2/5",
        "title": "TRL-9 pilot pack (ledger, tracker, case template)",
        "assertions": [
            ("scripts/pilot_metrics.py", "contains", "def main"),
            ("scripts/test_pilot_metrics.py", "contains", "def test"),
            ("docs/pilot/CASE_STUDY_TEMPLATE.md", "contains", "permission"),
            ("docs/pilot/PILOT_INTAKE_TRACKER.md", "contains", "Site"),
            ("docs/pilot/DAY0_REHEARSAL.md", "contains", "Day-0 Rehearsal"),
        ],
        "notes": "Everything a paid pilot needs on day 0; nothing here is a signed site.",
    },
]

# Live docs whose quoted test counts must equal what this run measured.
# Dated records (TRL6_EVIDENCE, TRL7_QUALIFICATION_PLAN, P0_REVERIFICATION)
# are intentionally excluded: they are evidence of a past date, not claims.
COUNT_CLAIMS: list[dict] = [
    # The public badge first: it is the number a visitor sees before anything else.
    {"file": "README.md", "regex": r"badge/tests-(\d+)%20passing", "keys": ["total"]},
    {"file": "README.md", "regex": r"#\s+(\d+) tests \(all passing\)", "keys": ["cloud"]},
    {"file": "README.md", "regex": r"# Cloud core \((\d+) tests\)", "keys": ["cloud"]},
    {"file": "README.md", "regex": r"# Backend \((\d+) tests\)", "keys": ["backend"]},
    {"file": "README.md", "regex": r"# Frontend \((\d+) vitest\)", "keys": ["frontend"]},
    {"file": "docs/CURRENT_STATE.md", "regex": r"`pytest yolo_cloud/tests` \| (\d+) passed", "keys": ["cloud"]},
    {
        "file": "docs/CURRENT_STATE.md",
        "regex": r"\*\*(\d+) automated tests[^*]*\*\* \((\d+) backend \+ (\d+) cloud \+ (\d+) vitest\)",
        "keys": ["total", "backend", "cloud", "frontend"],
    },
]


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _wrap(cmd: list[str]) -> list[str]:
    """Run through cmd.exe for the .cmd shims (npx/npm) on Windows."""
    if os.name == "nt" and cmd and not cmd[0].lower().endswith((".exe",)):
        if shutil.which(cmd[0]) or cmd[0] in {"npx", "npm"}:
            return ["cmd", "/c", *cmd]
    return cmd


def _missing(requires: tuple[str, ...]) -> list[str]:
    return [name for name in requires if shutil.which(name) is None]


def _run(cmd: list[str], cwd: Path, timeout: int) -> dict:
    started = time.time()
    try:
        proc = subprocess.run(
            _wrap(cmd),
            cwd=str(cwd),
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
        )
        return {
            "returncode": proc.returncode,
            "output": (proc.stdout or "") + (proc.stderr or ""),
            "seconds": round(time.time() - started, 1),
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "returncode": None,
            "output": (exc.stdout or "") + (exc.stderr or "")
            if isinstance(exc.stdout, str) or isinstance(exc.stderr, str)
            else "",
            "seconds": round(time.time() - started, 1),
            "timed_out": True,
        }
    except FileNotFoundError as exc:
        return {
            "returncode": None,
            "output": f"executable not found: {exc}",
            "seconds": round(time.time() - started, 1),
            "timed_out": False,
            "missing_exe": True,
        }


def _parse_pytest(output: str) -> dict:
    def grab(pattern: str) -> int | None:
        m = re.search(pattern, output)
        return int(m.group(1)) if m else None

    return {
        "passed": grab(r"(\d+) passed"),
        "failed": grab(r"(\d+) failed"),
        "errors": grab(r"(\d+) error"),
        "skipped": grab(r"(\d+) skipped"),
        "deselected": grab(r"(\d+) deselected"),
    }


_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _parse_counts(output: str) -> dict:
    """Parse vitest's summary line, e.g. 'Tests  106 passed (106)'.

    Two traps, both hit on 2026-09-28:
      * with failures vitest prints 'Tests  1 failed | 105 passed (106)',
        which a pattern requiring 'Tests  N passed' silently misses; and
      * the unanchored fallback then matched the *file* line
        'Test Files  1 failed | 7 passed (8)' and reported 7 frontend tests.
    So: find the 'Tests' line first, then read only from that line.
    """
    line = None
    for match in re.finditer(r"^[ \t]*Tests[ \t]+(.+)$", _ANSI.sub("", output), re.MULTILINE):
        line = match.group(1)
        break
    if line is None:
        return {"passed": None, "failed": None, "total": None}

    def num(pattern: str) -> int | None:
        found = re.search(pattern, line)
        return int(found.group(1)) if found else None

    return {
        "passed": num(r"(\d+) passed"),
        "failed": num(r"(\d+) failed"),
        "total": num(r"\((\d+)\)"),
    }


def _host_load() -> dict:
    """CPU state at battery start.

    Recorded because the frontend smoke suite waits on lazily-loaded route
    chunks and is CPU-sensitive: on 2026-09-28 it failed under a loaded box
    (cloud core scoring video + dev servers) and passed standalone. Without
    this number a red frontend row is uninterpretable.
    """
    info: dict = {"cpu_count": os.cpu_count()}
    try:
        info["loadavg_1m"] = round(os.getloadavg()[0], 2)  # POSIX only
    except (AttributeError, OSError):
        info["loadavg_1m"] = None
    try:
        import psutil  # optional reporting aid, not a runtime dependency

        info["cpu_percent"] = psutil.cpu_percent(interval=1.0)
        info["cpu_percent_source"] = "psutil"
    except Exception as exc:
        info["cpu_percent"] = None
        info["cpu_percent_source"] = f"unavailable ({type(exc).__name__})"
    return info


def _tail(text: str, limit: int = 4000) -> str:
    text = text.strip()
    return text[-limit:] if len(text) > limit else text


# --------------------------------------------------------------------------
# Runners
# --------------------------------------------------------------------------
def run_command_check(check: Check, log_dir: Path, opts) -> dict:
    missing = _missing(check.requires)
    if missing:
        return _result(check, BLOCKED, 0.0, None, f"missing prerequisite(s): {', '.join(missing)}")

    if check.kind == "load":
        return run_load(check, log_dir, opts)
    if check.kind == "soak":
        return run_soak(check, log_dir, opts)

    run = _run(list(check.cmd), check.cwd, check.timeout)
    log_path = log_dir / f"{check.id}.log"
    log_path.write_text(run["output"], encoding="utf-8", errors="replace")

    details: dict = {}
    if check.kind == "pytest":
        details = _parse_pytest(run["output"])
    elif check.id == "frontend-unit":
        details = _parse_counts(run["output"])

    if run.get("missing_exe"):
        status, summary = BLOCKED, run["output"].strip()
    elif run["timed_out"]:
        status, summary = FAIL, f"timed out after {check.timeout}s"
    elif check.expect:
        ok = check.expect in run["output"] and run["returncode"] == 0
        status = PASS if ok else FAIL
        summary = f"expected marker '{check.expect}'"
    else:
        status = PASS if run["returncode"] == 0 else FAIL
        summary = f"exit {run['returncode']}"

    for artifact in check.artifacts:
        path = REPO / artifact
        if path.exists():
            try:
                details[Path(artifact).stem] = json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:  # never fail a check on a parse slip
                details.setdefault("artifact_errors", []).append(f"{artifact}: {exc}")
        elif status == PASS:
            return _result(
                check, FAIL, run["seconds"], run["returncode"],
                f"expects artifact {artifact}, which was not written",
                details, log_path,
            )

    return _result(check, status, run["seconds"], run["returncode"], summary, details, log_path)


def run_load(check: Check, log_dir: Path, opts) -> dict:
    """Concurrent-user load against a running backend."""
    import urllib.error
    import urllib.request

    base = opts.backend_url.rstrip("/")
    try:
        with urllib.request.urlopen(f"{base}/health", timeout=5) as resp:
            if resp.status != 200:
                raise urllib.error.HTTPError(base, resp.status, "health", None, None)
    except Exception as exc:
        return _result(
            check, BLOCKED, 0.0, None,
            f"backend not reachable at {base} ({exc}) — start the stack, then re-run",
        )

    run_dir = log_dir.parent
    run = _run(
        [
            sys.executable, str(REPO / "deploy" / "load_test.py"),
            "--url", base,
            "--users", str(opts.load_users),
            "--duration", str(opts.load_seconds),
        ],
        run_dir, check.timeout,
    )
    log_path = log_dir / f"{check.id}.log"
    log_path.write_text(run["output"], encoding="utf-8", errors="replace")

    details: dict = {"users": opts.load_users, "duration_s": opts.load_seconds, "url": base}
    result_file = run_dir / "load_test_results.json"
    if result_file.exists():
        payload = json.loads(result_file.read_text(encoding="utf-8"))
        details.update(
            {k: payload.get(k) for k in ("total_requests", "successful", "failed", "rps",
                                         "avg_latency_ms", "p95_latency_ms", "p99_latency_ms",
                                         "workers_started", "workers_authenticated")}
        )
        details["errors_sample"] = payload.get("errors", [])[:5]

    if run["timed_out"]:
        status, summary = FAIL, f"timed out after {check.timeout}s"
    elif run["returncode"] != 0:
        status, summary = FAIL, f"exit {run['returncode']}"
    elif not result_file.exists():
        status, summary = FAIL, "load test wrote no load_test_results.json"
    elif details.get("workers_authenticated") != details.get("users"):
        # A worker that fails to log in contributes zero requests, so the rps
        # and latency numbers only describe the workers that got in. This was
        # a real false PASS on 2026-09-28 (per-IP auth throttle admitted 10/20).
        status = FAIL
        summary = (
            f"only {details.get('workers_authenticated')}/{details.get('users')} workers "
            f"authenticated — the run did not simulate the users it claims"
        )
    elif details.get("failed"):
        status = FAIL
        summary = f"{details.get('failed')} failed requests of {details.get('total_requests')}"
    else:
        status = PASS
        summary = (
            f"{details.get('users')} users × {details.get('duration_s')}s → "
            f"{details.get('total_requests')} req, {details.get('rps', 0):.1f} rps, "
            f"p95 {details.get('p95_latency_ms', 0):.0f} ms"
        )
    return _result(check, status, run["seconds"], run["returncode"], summary, details, log_path)


def run_soak(check: Check, log_dir: Path, opts) -> dict:
    out_dir = log_dir.parent / "soak"
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [*check.cmd, "--streams", str(opts.soak_streams), "--seconds", str(opts.soak_seconds),
           "--out", str(out_dir)]
    run = _run(cmd, REPO, check.timeout)
    log_path = log_dir / f"{check.id}.log"
    log_path.write_text(run["output"], encoding="utf-8", errors="replace")

    details: dict = {"streams": opts.soak_streams, "seconds": opts.soak_seconds}
    summaries = sorted(out_dir.glob("soak_*_summary.json"))
    if summaries:
        summary = json.loads(summaries[-1].read_text(encoding="utf-8"))
        details["summary"] = summary if len(json.dumps(summary)) < 4000 else str(summary)[:2000]
        details["summary_file"] = str(summaries[-1].relative_to(REPO))

    if run["timed_out"]:
        return _result(check, FAIL, run["seconds"], None, f"timed out after {check.timeout}s", details, log_path)
    status = PASS if run["returncode"] == 0 else FAIL
    return _result(check, status, run["seconds"], run["returncode"],
                   f"exit {run['returncode']}; {len(summaries)} summary file(s)", details, log_path)


def run_static_check(spec: dict, log_dir: Path) -> dict:
    findings: list[str] = []
    checked: list[str] = []
    for relpath, kind, needle in spec["assertions"]:
        path = REPO / relpath
        if not path.exists():
            findings.append(f"{relpath}: missing")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        checked.append(relpath)
        if kind == "contains":
            line = next((i for i, ln in enumerate(text.splitlines(), 1) if needle in ln), None)
            if line is None:
                findings.append(f"{relpath}: does not contain {needle!r}")
            else:
                findings.append(f"OK {relpath}:{line} contains {needle!r}")
        elif kind == "regex":
            if not re.search(needle, text):
                findings.append(f"{relpath}: no match for /{needle}/")
    failures = [f for f in findings if not f.startswith("OK ")]

    log_path = log_dir / f"{spec['id']}.log"
    log_path.write_text("\n".join(findings) + "\n", encoding="utf-8")
    check = Check(id=spec["id"], criterion=spec["criterion"], title=spec["title"], kind="static",
                  notes=spec.get("notes", ""))
    details = {"assertions": len(spec["assertions"]), "files": sorted(set(checked)),
               "findings": findings}
    status = PASS if not failures else FAIL
    summary = f"{len(spec['assertions']) - len(failures)}/{len(spec['assertions'])} assertions hold"
    return _result(check, status, 0.0, None, summary, details, log_path)


def run_doc_counts(measured: dict, log_dir: Path, not_comparable: dict | None = None) -> dict:
    """Re-derive every quoted test count from the runs in this report."""
    check = Check(
        id="doc-counts",
        criterion="TRL8-8",
        title="Live docs quote the measured test counts",
        kind="static",
        notes="Counts come from this run's suites; frozen dated records are excluded by design.",
    )
    lines: list[str] = []
    unmeasured: list[str] = []
    not_comparable = dict(not_comparable or {})
    findings: list[str] = []
    for claim in COUNT_CLAIMS:
        path = REPO / claim["file"]
        if not path.exists():
            findings.append(f"{claim['file']}: missing")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), 1):
            match = re.search(claim["regex"], line)
            if not match:
                continue
            for key, quoted in zip(claim["keys"], match.groups()):
                if key in not_comparable:
                    unmeasured.append(f"{key} ({not_comparable[key]})")
                    lines.append(f"SKIP {claim['file']}:{lineno} {key}: "
                                 f"{not_comparable[key]} — doc quotes {quoted}")
                    continue
                want = measured.get(key)
                if want is None:
                    unmeasured.append(f"{key} (not measured in this run)")
                    continue
                if int(quoted) != int(want):
                    findings.append(
                        f"{claim['file']}:{lineno} quotes {quoted} for {key}, measured {want}"
                    )
                    lines.append(f"STALE {claim['file']}:{lineno} {key}: doc={quoted} measured={want}")
                else:
                    lines.append(f"OK   {claim['file']}:{lineno} {key}: {quoted}")

    log_path = log_dir / f"{check.id}.log"
    log_path.write_text("\n".join(lines + ["unmeasured: " + ", ".join(unmeasured)]) + "\n",
                        encoding="utf-8")
    details = {"measured": measured, "stale": findings, "unmeasured": unmeasured,
               "not_comparable": not_comparable}
    if findings:
        status = FAIL
        summary = f"{len(findings)} stale count(s)"
    elif unmeasured:
        status = BLOCKED
        summary = "not comparable: " + ", ".join(sorted(set(unmeasured)))
    else:
        status = PASS
        summary = f"{len(lines)} quoted count(s) match"
    return _result(check, status, 0.0, None, summary, details, log_path)


def _result(check: Check, status: str, seconds: float, returncode, summary: str,
            details: dict | None = None, log_path: Path | None = None) -> dict:
    return {
        "id": check.id,
        "criterion": check.criterion,
        "title": check.title,
        "kind": check.kind,
        "status": status,
        "seconds": seconds,
        "returncode": returncode,
        "summary": summary,
        "details": details or {},
        "notes": check.notes,
        "log": str(log_path.relative_to(REPO)) if log_path else "",
        "command": " ".join(check.cmd) if check.cmd else "(file assertions)",
    }


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------
def write_markdown(report: dict, path: Path) -> None:
    lines = [
        "# TRL-8 qualification run",
        "",
        f"- **When:** {report['started_utc']} UTC",
        f"- **Mode:** {report['mode']}",
        f"- **Host:** {report['host']}",
        f"- **Python:** {report['python']}",
        f"- **CPU at start:** {report.get('host_load', {}).get('cpu_percent')}% "
        f"({report.get('host_load', {}).get('cpu_count')} cores)",
        f"- **Verdict:** {report['verdict']} "
        f"({report['counts']['PASS']} pass / {report['counts']['FAIL']} fail / "
        f"{report['counts']['BLOCKED']} blocked / {report['counts']['SKIP']} skipped)",
        "",
        "| Check | Criterion | Status | Seconds | Summary |",
        "|---|---|---|---|---|",
    ]
    for res in report["results"]:
        lines.append(
            f"| `{res['id']}` | {res['criterion']} | {res['status']} | "
            f"{res['seconds']} | {res['summary']} |"
        )
    lines += ["", "## Measurements", "", "```json",
              json.dumps(report["measured"], indent=2), "```", "",
              "Raw logs for each check are in `logs/<check id>.log` next to this report.",
              "", "Screening aid, not a medical device.", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_traceability_doc(path: Path, results: dict[str, str], source_run: str = "") -> None:
    lines = [
        "# TRL-8 / TRL-9 traceability matrix",
        "",
        "*Generated by `scripts/qualification/run_qualification.py` from",
        "`scripts/qualification/traceability.py`. Do not hand-edit: the harness fails",
        "if a row cites a check that does not exist or a file that is missing.*",
        "",
        f"*Last-run column sourced from `outputs/qualification/{source_run or '<none>'}`.*",
        "",
        "Status vocabulary: `CLOSED-INREPO`, `PARTIAL-INREPO`, `EXTERNAL-PENDING`,",
        "`SITE-DEPENDENT`, `BUSINESS-DEPENDENT`. Nothing here rounds up —",
        "screening aid, not a medical device.",
        "",
        "| Criterion | Requirement | Status | Checks | Last run |",
        "|---|---|---|---|---|",
    ]
    for row in traceability.CRITERIA:
        checks = ", ".join(f"`{c}`" for c in row["checks"]) or "—"
        observed = ", ".join(
            f"{results[c]}" for c in row["checks"] if c in results
        ) or "—"
        lines.append(
            f"| {row['id']} | {row['criterion']} | {row['status']} | {checks} | {observed} |"
        )
    lines += ["", "## Detail", ""]
    for row in traceability.CRITERIA:
        lines += [
            f"### {row['id']} — {row['criterion']}",
            "",
            f"- **Status:** {row['status']}",
            f"- **Implementation:** " + ", ".join(f"`{p}`" for p in row["implementation"]),
            f"- **Checks:** " + (", ".join(f"`{c}`" for c in row["checks"]) or "none (site/business gate)"),
            f"- **Evidence:** {row['evidence']}",
            f"- **NOT covered:** {row['not_covered']}",
            "",
        ]
    path.write_text("\n".join(lines), encoding="utf-8")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    # A Windows console defaults to cp1252 and the report uses a few arrows;
    # without this the harness dies logging its own banner.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="TRL-8 qualification harness")
    parser.add_argument("--mode", choices=["short", "full"], default="short")
    parser.add_argument("--only", default="", help="comma-separated check ids")
    parser.add_argument("--with-drills", action="store_true", help="kill/reconnect + backup restore drills")
    parser.add_argument("--with-load", action="store_true", help="concurrent-user load test (needs a stack)")
    parser.add_argument("--with-soak", action="store_true", help="multi-stream soak")
    parser.add_argument("--with-scans", action="store_true", help="run gitleaks/trivy locally (docker)")
    parser.add_argument("--backend-url", default="http://127.0.0.1:8000")
    parser.add_argument("--load-users", type=int, default=20)
    parser.add_argument("--load-seconds", type=float, default=20.0)
    parser.add_argument("--soak-streams", type=int, default=2)
    parser.add_argument("--soak-seconds", type=int, default=45)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--write-docs", action="store_true", help="refresh docs/TRL8_TRACEABILITY.md")
    parser.add_argument(
        "--write-docs-only", action="store_true",
        help="regenerate docs/TRL8_TRACEABILITY.md from the last run (no checks executed)",
    )
    parser.add_argument("--allow-blocked", action="store_true", help="exploratory runs only")
    opts = parser.parse_args(argv)

    if opts.write_docs_only:
        latest = DEFAULT_OUT / "latest.json"
        if not latest.exists():
            print(f"no previous run at {latest}", file=sys.stderr)
            return 2
        previous = json.loads(latest.read_text(encoding="utf-8"))
        statuses = {r["id"]: r["status"] for r in previous["results"]}
        write_traceability_doc(
            REPO / "docs" / "TRL8_TRACEABILITY.md", statuses, previous.get("started_utc", "")
        )
        print(f"wrote docs/TRL8_TRACEABILITY.md from run {previous.get('started_utc')} "
              f"({previous.get('verdict')})")
        return 0

    if opts.mode == "full":
        opts.with_drills = opts.with_load = opts.with_soak = True

    enabled = {
        "drills": opts.with_drills,
        "load": opts.with_load,
        "soak": opts.with_soak,
        "scans": opts.with_scans,
    }
    only = {i.strip() for i in opts.only.split(",") if i.strip()}

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    # Resolve here: report and log paths are stored relative to the repo, and
    # a relative --out made that .relative_to(REPO) call raise mid-run
    # (hit 2026-10-02 when an opt-in soak was run with --out outputs/...).
    run_dir = Path(opts.out).resolve() / stamp
    log_dir = run_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    host_load = _host_load()
    print(f"TRL-8 qualification — mode={opts.mode} → {run_dir}")
    print(f"  host: {host_load['cpu_count']} cores, CPU {host_load['cpu_percent']}% at start")
    results: list[dict] = []

    known_ids = (
        {c.id for c in COMMAND_CHECKS}
        | {s["id"] for s in STATIC_CHECKS}
        | {"doc-counts", "scans"}
    )
    # The matrix must not cite a check that does not exist, or a file that was
    # moved/deleted — a traceability row pointing at nothing is worse than none.
    for row in traceability.CRITERIA:
        for check_id in row["checks"]:
            if check_id not in known_ids:
                print(f"FATAL: {row['id']} cites unknown check '{check_id}'", file=sys.stderr)
                return 2
        for ref in row["implementation"]:
            if not (REPO / ref).exists():
                print(f"FATAL: {row['id']} cites missing implementation '{ref}'", file=sys.stderr)
                return 2
        if not row.get("not_covered"):
            print(f"FATAL: {row['id']} has no not_covered sentence", file=sys.stderr)
            return 2

    def wanted(check_id: str, opt_in: str | None) -> tuple[bool, str]:
        if only and check_id not in only:
            return False, "not requested by --only"
        if opt_in and not enabled[opt_in]:
            return False, f"opt-in: pass --with-{opt_in}"
        return True, ""

    for check in COMMAND_CHECKS:
        run_it, why = wanted(check.id, check.opt_in)
        if not run_it:
            results.append(_result(check, SKIP, 0.0, None, why))
            continue
        print(f"  ▸ {check.id} …", end="", flush=True)
        res = run_command_check(check, log_dir, opts)
        print(f" {res['status']} ({res['seconds']}s)")
        results.append(res)

    for spec in STATIC_CHECKS:
        run_it, why = wanted(spec["id"], None)
        if not run_it:
            results.append(_result(Check(spec["id"], spec["criterion"], spec["title"], "static"),
                                   SKIP, 0.0, None, why))
            continue
        print(f"  ▸ {spec['id']} …", end="", flush=True)
        res = run_static_check(spec, log_dir)
        print(f" {res['status']}")
        results.append(res)

    # Supply-chain scanners (opt-in): the same pinned images CI uses.
    if enabled["scans"] and (not only or "scans" in only):
        print("  ▸ scans …", end="", flush=True)
        scan_check = Check(
            id="scans", criterion="TRL8-6", title="gitleaks + trivy config scan (local)",
            kind="drill", timeout=1800, expect="SCANS OK",
            notes="Pinned images, same commands as CI.",
        )
        if shutil.which("docker") is None:
            results.append(_result(scan_check, BLOCKED, 0.0, None, "docker not on PATH"))
            print(" BLOCKED")
        else:
            steps = [
                ["docker", "run", "--rm", "-v", f"{REPO}:/repo", "zricethezav/gitleaks:v8.30.1",
                 "detect", "--source=/repo", "--config=/repo/.gitleaks.toml", "--redact", "--no-banner"],
                ["docker", "run", "--rm", "-v", f"{REPO}:/repo", "ghcr.io/aquasecurity/trivy:0.58.1",
                 "config", "--severity", "HIGH,CRITICAL", "--exit-code", "1", "--skip-dirs", ".git", "/repo"],
            ]
            output, ok = [], True
            for step in steps:
                run = _run(step, REPO, scan_check.timeout)
                output.append(f"$ {' '.join(step[:4])} … exit={run['returncode']}\n{_tail(run['output'], 3000)}")
                ok = ok and run["returncode"] == 0
            log_path = log_dir / "scans.log"
            log_path.write_text("\n\n".join(output), encoding="utf-8")
            results.append(_result(
                scan_check, PASS if ok else FAIL, 0.0, None,
                "gitleaks + trivy config clean" if ok else "scanner reported findings (see log)",
                {"engine": "gitleaks v8.30.1 + trivy 0.58.1"}, log_path,
            ))
            print(f" {'PASS' if ok else 'FAIL'}")
    else:
        results.append(_result(
            Check("scans", "TRL8-6", "gitleaks + trivy config scan (local)", "drill"),
            SKIP, 0.0, None,
            "opt-in: pass --with-scans (docker)" if not enabled["scans"] else "not requested by --only",
        ))

    # A count is only comparable when its source suite actually went green:
    # a red suite makes the number meaningless, not merely different, and the
    # red row already fails the battery. Comparing a red suite's number to the
    # docs produced a bogus '4 stale counts' finding on 2026-09-28.
    suite_for = {"backend": "backend-suite", "cloud": "cloud-suite", "frontend": "frontend-unit"}
    by_id = {r["id"]: r for r in results}
    measured = {"backend": None, "cloud": None, "frontend": None, "total": None}
    not_comparable: dict[str, str] = {}
    for key, suite_id in suite_for.items():
        suite = by_id.get(suite_id)
        if suite is None:
            not_comparable[key] = f"{suite_id} not in this run"
        elif suite["status"] != PASS:
            not_comparable[key] = f"{suite_id} {suite['status']}"
        else:
            measured[key] = suite["details"].get("passed")
    if all(measured[k] is not None for k in suite_for):
        measured["total"] = measured["backend"] + measured["cloud"] + measured["frontend"]
    else:
        not_comparable["total"] = "component suite did not pass"

    doc_check = Check("doc-counts", "TRL8-8", "Live docs quote the measured test counts", "static")
    run_it, why = wanted("doc-counts", None)
    if run_it:
        print("  ▸ doc-counts …", end="", flush=True)
        res = run_doc_counts(measured, log_dir, not_comparable)
        print(f" {res['status']} — {res['summary']}")
    else:
        res = _result(doc_check, SKIP, 0.0, None, why)
    results.append(res)

    counts = {status: sum(1 for r in results if r["status"] == status)
              for status in (PASS, FAIL, BLOCKED, SKIP)}
    executed_failures = counts[FAIL] + counts[BLOCKED]
    verdict = "QUALIFIED" if executed_failures == 0 else "NOT QUALIFIED"

    report = {
        "started_utc": stamp,
        "mode": opts.mode,
        "host": f"{platform.system()} {platform.release()} · {os.cpu_count()} CPU",
        "host_load": host_load,
        "python": sys.version.split()[0],
        "verdict": verdict,
        "counts": counts,
        "measured": measured,
        "results": results,
        "traceability": traceability.CRITERIA,
    }
    (run_dir / "qualification_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_markdown(report, run_dir / "qualification_report.md")
    latest = Path(opts.out) / "latest.json"
    latest.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if opts.write_docs:
        statuses = {r["id"]: r["status"] for r in results}
        write_traceability_doc(REPO / "docs" / "TRL8_TRACEABILITY.md", statuses, stamp)
        print(f"wrote docs/TRL8_TRACEABILITY.md (from {stamp})")

    print(f"\n{verdict}: {counts[PASS]} pass, {counts[FAIL]} fail, "
          f"{counts[BLOCKED]} blocked, {counts[SKIP]} skipped")
    print(f"report: {run_dir / 'qualification_report.md'}")
    for res in results:
        if res["status"] in (FAIL, BLOCKED):
            print(f"  !! {res['id']}: {res['summary']}")

    if opts.allow_blocked:
        return 1 if counts[FAIL] else 0
    return 0 if executed_failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
