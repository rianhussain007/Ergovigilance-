"""Generate worker consent form PDF from HTML template.

Usage:
    python docs/generate_consent_pdf.py
    python docs/generate_consent_pdf.py --output docs/worker_consent_form.pdf
"""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def generate_pdf(output_path: Path | None = None) -> Path:
    """Generate the worker consent form PDF."""
    if output_path is None:
        output_path = ROOT / "docs" / "worker_consent_form.pdf"

    html_path = ROOT / "docs" / "worker_consent_form.html"
    if not html_path.exists():
        raise FileNotFoundError(f"HTML template not found: {html_path}")

    html_content = html_path.read_text(encoding="utf-8")

    # Try weasyprint first (best quality)
    try:
        from weasyprint import HTML
        HTML(string=html_content).write_pdf(str(output_path))
        print(f"PDF generated: {output_path} (weasyprint)")
        return output_path
    except ImportError:
        pass

    # Fallback: use pdfkit (requires wkhtmltopdf)
    try:
        import pdfkit
        pdfkit.from_string(html_content, str(output_path))
        print(f"PDF generated: {output_path} (pdfkit)")
        return output_path
    except ImportError:
        pass

    # Fallback: save HTML and instruct user
    html_output = output_path.with_suffix(".html")
    html_output.write_text(html_content, encoding="utf-8")
    print(f"PDF generation requires weasyprint or pdfkit.")
    print(f"HTML saved to: {html_output}")
    print("Open in browser and print to PDF (Ctrl+P -> Save as PDF)")
    return html_output


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Generate worker consent form PDF")
    ap.add_argument("--output", type=Path, default=None)
    args = ap.parse_args()
    generate_pdf(args.output)
