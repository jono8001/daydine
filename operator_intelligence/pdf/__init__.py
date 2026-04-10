"""
operator_intelligence.pdf — branded PDF renderer for monthly reports.

Renders ``outputs/monthly/{venue}_{month}.json`` snapshots into A4 PDFs
using WeasyPrint + Jinja2. Import from ``operator_intelligence.pdf.renderer``
directly; we avoid eagerly importing ``renderer`` at package load so that
``python -m operator_intelligence.pdf.renderer`` runs cleanly.
"""

__all__ = ["render_pdf_report"]


def __getattr__(name):
    if name == "render_pdf_report":
        from operator_intelligence.pdf.renderer import render_pdf_report
        return render_pdf_report
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
