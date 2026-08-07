"""Generate an ergonomic trend report from session history (markdown).

Rewritten for the post-pivot API: the legacy ``TrendAnalysis`` class was
removed from ``backend.services.trend_analysis``; the module now exposes the
``analyze_risk_trend(sessions)`` function that powers ``/api/reports/risk-trend``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.trend_analysis import analyze_risk_trend


def _load_sessions(sessions_dir: Path) -> list[dict]:
    if not sessions_dir.is_dir():
        raise SystemExit(f"Error: sessions directory not found: {sessions_dir}")
    sessions: list[dict] = []
    for path in sorted(sessions_dir.glob("session_*.json")):
        try:
            with open(path, encoding="utf-8") as f:
                sessions.append(json.load(f))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Warning: skipping {path.name}: {exc}")
    return sessions


def _render_markdown(result: dict) -> str:
    if result.get("total_sessions", 0) == 0:
        return f"# Trend Report\n\n{result.get('status', 'No sessions found')}\n"
    rd = result.get("risk_distribution", {})
    lines = [
        "# Trend Report",
        "",
        f"- Sessions analyzed: **{result['total_sessions']}**",
        f"- Date range: {result.get('earliest_session')} → {result.get('latest_session')}",
        f"- Average risk split: LOW {rd.get('low_pct')}% / MEDIUM {rd.get('medium_pct')}% / HIGH {rd.get('high_pct')}%",
        f"- Most common issue: {result.get('most_common_issue') or 'n/a'} (×{result.get('most_common_issue_count', 0)})",
        f"- Most common highest risk: {result.get('most_common_highest_risk')}",
        f"- Overall trend: **{result.get('overall_trend')}**",
        "",
        "## Per-metric averages & trends",
        "",
        "| Metric | Average | Trend |",
        "|---|---|---|",
    ]
    for m in result.get("metrics", []):
        lines.append(f"| {m.get('label', m.get('name'))} ({m.get('unit', '')}) | {m.get('average')} | {m.get('trend')} |")
    lines += ["", "## Raw payload", "", "```json", json.dumps(result, indent=2), "```", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate an ergonomic trend report from session history.")
    parser.add_argument("--sessions-dir", type=str, default=None,
                        help="Path to session JSON directory (default: outputs/sessions)")
    parser.add_argument("-o", "--output", type=str, default=None,
                        help="Output path for the markdown report (default: reports/trend_report.md)")
    args = parser.parse_args()

    sessions_dir = Path(args.sessions_dir) if args.sessions_dir else ROOT / "outputs" / "sessions"
    output_path = Path(args.output) if args.output else ROOT / "reports" / "trend_report.md"

    sessions = _load_sessions(sessions_dir)
    if not sessions:
        print(f"Warning: no session_*.json files found in {sessions_dir}")

    result = analyze_risk_trend(sessions)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_render_markdown(result), encoding="utf-8")
    print(f"Trend report generated: {output_path}")


if __name__ == "__main__":
    main()
