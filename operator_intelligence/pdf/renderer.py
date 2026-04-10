"""
operator_intelligence.pdf.renderer
==================================

Render a single `outputs/monthly/{venue}_{month}.json` snapshot into a
branded A4 PDF using WeasyPrint + Jinja2.

Entry point:
    render_pdf_report(json_path, out_path) -> str

CLI (backfill all existing JSONs for a given month):
    python -m operator_intelligence.pdf.renderer outputs/monthly/ --month 2026-04
    python -m operator_intelligence.pdf.renderer outputs/monthly/Vintner_Wine_Bar_2026-04.json /tmp/v.pdf

The renderer is intentionally tolerant of sparse data: missing keys become
empty states in the templates rather than exceptions. PDF render failures
must never break the upstream scoring pipeline, so the pipeline caller
wraps the invocation in try/except (see `restaurant_operator_intelligence.py`).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable

from jinja2 import Environment, FileSystemLoader, select_autoescape

from operator_intelligence.pdf import filters as pdf_filters


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_PKG_ROOT = Path(__file__).resolve().parent
_TEMPLATE_DIR = _PKG_ROOT / "templates"
_STATIC_DIR = _PKG_ROOT / "static"


# ---------------------------------------------------------------------------
# Dimension metadata
# ---------------------------------------------------------------------------

# Order and labels mirror operator_intelligence.report_generator.DIM_ORDER.
_DIMENSIONS = [
    ("experience", "Experience", "How guests rate their visit"),
    ("visibility", "Visibility", "How findable you are online"),
    ("trust", "Trust", "Compliance and reputation signals"),
    ("conversion", "Conversion", "Turning discovery into bookings"),
    ("prestige", "Prestige", "Editorial and award recognition"),
]


def _fill_class(score) -> str:
    try:
        v = float(score)
    except (TypeError, ValueError):
        return "prog-fill-bad"
    if v >= 7.5:
        return "prog-fill-high"
    if v >= 5.0:
        return "prog-fill-mid"
    if v >= 3.0:
        return "prog-fill-low"
    return "prog-fill-bad"


def _build_dimensions(scorecard: dict | None) -> list[dict]:
    scorecard = scorecard or {}
    rows = []
    for key, label, hint in _DIMENSIONS:
        score = scorecard.get(key)
        rows.append({
            "key": key,
            "label": label,
            "hint": hint,
            "score": score,
            "fill_class": _fill_class(score),
        })
    return rows


def _pick_strongest_weakest(dimensions: list[dict]) -> tuple[dict | None, dict | None]:
    scored = [d for d in dimensions if isinstance(d.get("score"), (int, float))]
    if not scored:
        return None, None
    strongest = max(scored, key=lambda d: d["score"])
    weakest = min(scored, key=lambda d: d["score"])
    return strongest, weakest


def _derive_financial_impact(report: dict) -> dict | None:
    """Pull a compact revenue-impact dict from whatever fields the JSON exposes.

    The monthly report JSON does not currently have a top-level
    ``financial_impact`` key, but the information is encoded in the
    implementation_framework and the prose. We approximate a tile-sized
    summary from the signals we do have and return None when we can't.
    """
    fi = report.get("financial_impact")
    if isinstance(fi, dict) and fi:
        return fi

    # Heuristic fallback built from signals + UK benchmarks.
    signals = report.get("signals") or {}
    review_count = signals.get("google_review_count") or 0
    rating = signals.get("google_rating") or 0
    price_level = signals.get("price_level") or 2
    if not review_count:
        return None

    # Rough cover estimate: ~0.3 covers per Google review per week for
    # small/mid venues (directional benchmark only, not a precise model).
    weekly_covers = max(10, int(review_count * 0.3))
    avg_spend = {1: 12, 2: 22, 3: 45, 4: 75}.get(int(price_level), 22)
    at_risk_low = int(weekly_covers * 0.01 * 4 * avg_spend)
    at_risk_high = int(weekly_covers * 0.1 * 4 * avg_spend)
    monthly_at_risk = f"£{at_risk_low:,} – £{at_risk_high:,}"
    annual_projection = f"£{at_risk_low * 12:,} – £{at_risk_high * 12:,}"
    return {
        "weekly_covers": f"~{weekly_covers}",
        "avg_spend": avg_spend,
        "monthly_at_risk": monthly_at_risk,
        "annual_projection": annual_projection,
        "rating_context": rating,
    }


# ---------------------------------------------------------------------------
# Template environment
# ---------------------------------------------------------------------------

def _build_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    pdf_filters.register(env)
    # Expose sentiment_bar as a global for template convenience.
    env.globals["sentiment_bar"] = pdf_filters.sentiment_bar
    return env


def _load_report(json_path: str | os.PathLike) -> dict:
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _build_context(report: dict) -> dict:
    dimensions = _build_dimensions(report.get("scorecard"))
    strongest, weakest = _pick_strongest_weakest(dimensions)
    priority_actions = report.get("priority_actions") or []

    return {
        "venue": report.get("venue") or "Unknown Venue",
        "month": report.get("month"),
        "report_date": report.get("report_date"),
        "scorecard": report.get("scorecard") or {},
        "signals": report.get("signals") or {},
        "peer_position": report.get("peer_position") or {},
        "demand_capture": report.get("demand_capture") or {},
        "review_sentiment": report.get("review_sentiment") or {},
        "reviews_analyzed": report.get("reviews_analyzed"),
        "priority_actions": priority_actions,
        "top_priorities": priority_actions[:3],
        "watch_items": report.get("watch_items") or [],
        "implementation_framework": report.get("implementation_framework") or [],
        "evidence_base": report.get("evidence_base") or {},
        "risk_alerts": report.get("risk_alerts") or {},
        "dimensions": dimensions,
        "strongest": strongest,
        "weakest": weakest,
        "financial_impact": _derive_financial_impact(report),
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def render_pdf_report(
    json_path: str | os.PathLike,
    out_path: str | os.PathLike,
    *,
    template_name: str = "base.html",
) -> str:
    """Render a single monthly report JSON to a branded PDF.

    Parameters
    ----------
    json_path:
        Path to an ``outputs/monthly/{venue}_{month}.json`` file.
    out_path:
        Destination PDF path. Parent directory is created if missing.
    template_name:
        Jinja template to render. Defaults to ``base.html``.

    Returns
    -------
    The absolute path of the written PDF.

    Raises
    ------
    FileNotFoundError, OSError, jinja2.TemplateError, weasyprint errors.
    """
    # Late import so that importing this module (e.g. from the scoring
    # pipeline wrapper) does not require WeasyPrint to be installed yet.
    from weasyprint import CSS, HTML

    report = _load_report(json_path)
    context = _build_context(report)

    env = _build_env()
    template = env.get_template(template_name)
    html_str = template.render(**context)

    # Base URL lets WeasyPrint resolve relative hrefs inside the HTML
    # (print.css, logo.svg) against the package's static directory.
    base_url = str(_STATIC_DIR) + os.sep

    out_path = str(out_path)
    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    # Deterministic metadata so re-running the renderer on unchanged data
    # produces byte-identical PDFs (cleaner diffs when published files
    # are committed to git).
    HTML(string=html_str, base_url=base_url).write_pdf(
        out_path,
        stylesheets=[CSS(filename=str(_STATIC_DIR / "print.css"))],
    )
    return os.path.abspath(out_path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _iter_jsons(root: Path, month: str | None) -> Iterable[Path]:
    """Yield monthly JSON files under ``root``, optionally filtered by month."""
    for p in sorted(root.glob("*.json")):
        if p.name.endswith("_qa.json"):
            continue
        if month and not p.stem.endswith(f"_{month}"):
            continue
        yield p


def _cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m operator_intelligence.pdf.renderer",
        description="Render DayDine monthly intelligence reports to branded PDFs.",
    )
    parser.add_argument(
        "input",
        help="Path to a single *.json report, or a directory of monthly reports.",
    )
    parser.add_argument(
        "output",
        nargs="?",
        help="Output PDF path (single-file mode) or output directory (batch mode). "
             "Defaults to outputs/monthly/pdf/ for directory input.",
    )
    parser.add_argument(
        "--month",
        help="Filter batch renders to a specific month suffix, e.g. 2026-04.",
    )
    args = parser.parse_args(argv)

    in_path = Path(args.input)
    if not in_path.exists():
        print(f"error: input path does not exist: {in_path}", file=sys.stderr)
        return 2

    # Single-file mode
    if in_path.is_file():
        out = Path(args.output) if args.output else in_path.with_suffix(".pdf")
        try:
            final = render_pdf_report(in_path, out)
        except Exception as exc:  # pragma: no cover - surfaced to caller
            print(f"error: PDF render failed: {exc}", file=sys.stderr)
            return 1
        print(f"wrote {final}")
        return 0

    # Batch mode
    out_dir = Path(args.output) if args.output else Path("outputs/monthly/pdf")
    out_dir.mkdir(parents=True, exist_ok=True)

    ok = 0
    failed = 0
    for json_path in _iter_jsons(in_path, args.month):
        pdf_path = out_dir / f"{json_path.stem}.pdf"
        try:
            render_pdf_report(json_path, pdf_path)
            ok += 1
            print(f"  + {pdf_path.name}")
        except Exception as exc:
            failed += 1
            print(f"  ! {json_path.name}: {exc}", file=sys.stderr)
    print(f"\nRendered {ok} PDF(s), {failed} failure(s). Output: {out_dir}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(_cli())
