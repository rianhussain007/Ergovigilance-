"""Generate a safety report from a session JSON file (markdown).

Rewritten for the post-pivot API: the legacy ``SafetyReport`` class was
removed; ``backend.services.safety_report`` now exposes the
``analyze_safety(sessions)`` function that powers ``/api/reports/safety-report``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.safety_report import analyze_safety


def _render_markdown(result: dict) -> str:
    if result.get("total_sessions_with_alerts", 0) == 0:
        return f"# Safety Report\n\n{result.get('coverage_statement') or result.get('status', 'No alert data available')}\n"
    density = result.get("alert_density") or {}
    lines = [
        "# Safety Report",
        "",
        f"- Sessions with alert tracking: **{result['total_sessions_with_alerts']}** / {result.get('total_all_sessions')}",
        f"- Date range: {result.get('earliest_session')} → {result.get('latest_session')}",
        f"- Total alerts: **{result.get('total_alerts')}** "
        f"(HIGH+CRITICAL: {result.get('high_severity_total')}, MEDIUM: {result.get('medium_severity_total')}, LOW: {result.get('low_severity_total')})",
        f"- Alert density: {density.get('avg_per_session') or 'n/a'} alerts/session "
        f"({density.get('alerts_per_hour') or 'n/a'} alerts/hour over {density.get('total_monitored_hours') or 'n/a'} h)",
        "",
        result.get("coverage_statement", ""),
        "",
        "## Severity breakdown",
        "",
        "| Severity | Count |",
        "|---|---|",
    ]
    for sev, count in (result.get("severity_breakdown") or {}).items():
        lines.append(f"| {sev} | {count} |")
    lines += ["", "## Trigger-rule breakdown", "", "| Rule | Count | % |", "|---|---|---|"]
    for item in result.get("trigger_rule_breakdown") or []:
        lines.append(f"| {item.get('rule')} | {item.get('count')} | {item.get('pct')} |")
    lines += ["", "## Raw payload", "", "```json", json.dumps(result, indent=2), "```", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a safety report from a session JSON file.")
    parser.add_argument("input", type=str, help="Path to session JSON file (outputs/sessions/session_*.json)")
    parser.add_argument("-o", "--output", type=str, default=None,
                        help="Output path for the markdown report (default: reports/session_report.md)")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: input file not found: {input_path}")
        sys.exit(1)

    output_path = Path(args.output) if args.output else ROOT / "reports" / "session_report.md"

    with open(input_path, encoding="utf-8") as f:
        session = json.load(f)

    result = analyze_safety([session])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_render_markdown(result), encoding="utf-8")
    print(f"Safety report generated: {output_path}")


if __name__ == "__main__":
    main()
