"""Build the public sample Position & Competitor Report PDF.

Renders the fictional fixture under
``operator_intelligence/pdf/samples/The_Harvest_Table_sample.md`` (with its
sibling .json) into ``assets/reports/daydine-sample-report.pdf`` using the
same WeasyPrint pipeline that generates real monthly reports.

The resulting PDF is the file linked from /sample, /reports and the
homepage. Re-run this script whenever the fixture or the renderer template
changes.

    python scripts/build_sample_report.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

FIXTURE_MD = REPO_ROOT / "operator_intelligence" / "pdf" / "samples" / "The_Harvest_Table_sample.md"
OUT_PDF = REPO_ROOT / "assets" / "reports" / "daydine-sample-report.pdf"


def main() -> int:
    from operator_intelligence.pdf.renderer import render_pdf_report

    if not FIXTURE_MD.exists():
        print(f"error: fixture not found: {FIXTURE_MD}", file=sys.stderr)
        return 1

    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    final = render_pdf_report(FIXTURE_MD, OUT_PDF)
    size = OUT_PDF.stat().st_size
    print(f"wrote {final} ({size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
