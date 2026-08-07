from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.trend_analysis import TrendAnalysis


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate an ergonomic trend report from session history.")
    parser.add_argument("--sessions-dir", type=str, default=None,
                        help="Path to session JSON directory (default: outputs/sessions)")
    parser.add_argument("-o", "--output", type=str, default=None,
                        help="Output path for the markdown report (default: reports/trend_report.md)")
    args = parser.parse_args()

    sessions_dir = args.sessions_dir
    if sessions_dir is None:
        sessions_dir = str(ROOT / "outputs" / "sessions")

    output_path = args.output
    if output_path is None:
        output_path = str(ROOT / "reports" / "trend_report.md")

    ta = TrendAnalysis(sessions_dir)
    saved = ta.save_report(output_path)
    print(f"Trend report generated: {saved}")


if __name__ == "__main__":
    main()
