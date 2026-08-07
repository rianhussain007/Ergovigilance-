from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.safety_reporting import SafetyReport


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

    output_path = args.output
    if output_path is None:
        output_path = str(ROOT / "reports" / "session_report.md")

    report = SafetyReport.from_json(input_path)
    saved = report.save(output_path)
    print(f"Safety report generated: {saved}")


if __name__ == "__main__":
    main()
