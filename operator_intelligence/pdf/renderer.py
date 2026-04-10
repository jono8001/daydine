"""
operator_intelligence.pdf.renderer
==================================

Render the full monthly intelligence report (the ``.md`` file that
``operator_intelligence.report_generator`` emits, with every word of
narrative preserved) into a branded A4 PDF using WeasyPrint + Jinja2.

Source of truth is the markdown file at
``outputs/monthly/{safe_name}_{month}.md``; the sibling ``.json`` is used
only to populate the cover page (venue name, month, rank, overall score).

Entry point:
    render_pdf_report(md_path_or_json_path, out_path) -> str

CLI (batch render all monthly reports for a given month):
    python -m operator_intelligence.pdf.renderer outputs/monthly/ --month 2026-04
    python -m operator_intelligence.pdf.renderer outputs/monthly/Vintner_Wine_Bar_2026-04.md /tmp/v.pdf

PDF render failures must never break the upstream scoring pipeline, so
the pipeline caller wraps the invocation in try/except (see
``restaurant_operator_intelligence.py``).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Iterable

import markdown as md_lib
from jinja2 import Environment, FileSystemLoader, select_autoescape

from operator_intelligence.pdf import filters as pdf_filters


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_PKG_ROOT = Path(__file__).resolve().parent
_TEMPLATE_DIR = _PKG_ROOT / "templates"
_STATIC_DIR = _PKG_ROOT / "static"


# ---------------------------------------------------------------------------
# Markdown → HTML
# ---------------------------------------------------------------------------

# Match the leading ``# Venue — ... Report`` H1, optional italic metadata
# line, and first horizontal rule. Everything above is rendered on the
# branded cover page, so we strip it from the markdown body.
_FRONTMATTER_RE = re.compile(
    r"\A\s*#\s[^\n]*\n"          # H1 line
    r"(?:\*[^\n]*\*\s*\n)?"       # optional italic subtitle
    r"\s*(?:---+|\*\*\*+)\s*\n",  # horizontal rule
    re.MULTILINE,
)


def _strip_frontmatter(md_src: str) -> str:
    """Remove the generated H1/subtitle/HR block from the top of the markdown."""
    m = _FRONTMATTER_RE.match(md_src)
    if m:
        return md_src[m.end():]
    return md_src


def _render_markdown_body(md_src: str) -> str:
    """Convert the narrative markdown to HTML with tables, fenced code, etc.

    The ``toc`` extension attaches stable ``id`` attributes to every heading
    (h1–h6), which lets the template's contents page link to each ``h2`` via
    ``#id`` and WeasyPrint resolve the page number via ``target-counter()``.
    """
    md_src = _strip_frontmatter(md_src)
    html = md_lib.markdown(
        md_src,
        extensions=[
            "extra",       # tables, fenced code, abbr, footnotes, attr_list
            "sane_lists",
            "nl2br",
            "toc",         # auto-assigns id="…" to every heading
        ],
        extension_configs={
            "toc": {
                "title": "",
                "anchorlink": False,
                "permalink": False,
            },
        },
        output_format="html5",
    )
    return html


# Capture ``<h2 id="slug">Title</h2>`` — python-markdown's toc extension emits
# exactly this shape with autoslug ids.
_H2_RE = re.compile(
    r'<h2\b[^>]*\bid="([^"]+)"[^>]*>(.*?)</h2>',
    re.DOTALL,
)

_TAG_RE = re.compile(r"<[^>]+>")


def _extract_toc(body_html: str) -> list[dict]:
    """Pull every ``h2`` (id + plain-text title) from the rendered body HTML.

    Used to build the contents page. Only h2 is included — matches the
    "main sections only" requirement.
    """
    entries: list[dict] = []
    for m in _H2_RE.finditer(body_html):
        anchor_id = m.group(1)
        # Strip inline tags from the title and unescape basic entities.
        title = _TAG_RE.sub("", m.group(2))
        title = (
            title.replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&quot;", '"')
            .replace("&#39;", "'")
            .strip()
        )
        entries.append({"id": anchor_id, "title": title})
    return entries


# ---------------------------------------------------------------------------
# Cover metadata (from JSON)
# ---------------------------------------------------------------------------

_DIMENSIONS = [
    ("experience", "Experience"),
    ("visibility", "Visibility"),
    ("trust",      "Trust"),
    ("conversion", "Conversion"),
    ("prestige",   "Prestige"),
]


def _load_json(json_path: Path) -> dict | None:
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _build_cover_context(md_path: Path, json_data: dict | None) -> dict:
    """Derive cover-page variables from the JSON snapshot (with md-filename fallback).

    The markdown file's first line is ``# <Venue> — Monthly Intelligence Report``;
    if the JSON is missing we still want a usable venue name, so fall back to
    stripping the filename suffix.
    """
    data = json_data or {}
    scorecard = data.get("scorecard") or {}
    peer = data.get("peer_position") or {}

    venue = data.get("venue")
    if not venue:
        # Fallback: derive from md filename like ``Vintner_Wine_Bar_2026-04``
        stem = md_path.stem
        stem = re.sub(r"_\d{4}-\d{2}$", "", stem)
        venue = stem.replace("_", " ")

    return {
        "venue": venue,
        "month": data.get("month"),
        "report_date": data.get("report_date"),
        "overall_score": scorecard.get("overall"),
        "local_rank": peer.get("local_rank"),
        "local_of": peer.get("local_of"),
        "local_peer_avg": peer.get("local_peer_avg"),
        "strongest": _pick_strongest_weakest(scorecard)[0],
        "weakest": _pick_strongest_weakest(scorecard)[1],
    }


def _pick_strongest_weakest(scorecard: dict) -> tuple[tuple[str, float] | None, tuple[str, float] | None]:
    scored = [
        (label, scorecard.get(key))
        for key, label in _DIMENSIONS
        if isinstance(scorecard.get(key), (int, float))
    ]
    if not scored:
        return None, None
    strongest = max(scored, key=lambda t: t[1])
    weakest = min(scored, key=lambda t: t[1])
    return strongest, weakest


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
    return env


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def _resolve_paths(source: os.PathLike | str) -> tuple[Path, Path]:
    """Return ``(md_path, json_path)`` tuple regardless of which input the
    caller supplied.

    Accepts either a markdown path or a JSON path and finds the sibling.
    """
    p = Path(source)
    if p.suffix == ".md":
        return p, p.with_suffix(".json")
    if p.suffix == ".json":
        return p.with_suffix(".md"), p
    raise ValueError(f"Unsupported input: {p} (expected .md or .json)")


def render_pdf_report(
    source: os.PathLike | str,
    out_path: os.PathLike | str,
    *,
    template_name: str = "base.html",
) -> str:
    """Render a monthly report to a branded PDF.

    Parameters
    ----------
    source:
        Path to either the ``.md`` narrative file or its sibling ``.json``
        snapshot under ``outputs/monthly/``. Both files are read — the
        markdown provides the full narrative body, the JSON supplies the
        cover page metadata.
    out_path:
        Destination PDF path. Parent directory created if missing.
    template_name:
        Jinja template to render. Defaults to ``base.html``.

    Returns
    -------
    Absolute path of the written PDF.
    """
    # Late import so merely importing this module doesn't require WeasyPrint.
    from weasyprint import CSS, HTML

    md_path, json_path = _resolve_paths(source)
    if not md_path.exists():
        raise FileNotFoundError(f"Markdown report not found: {md_path}")

    with open(md_path, "r", encoding="utf-8") as f:
        md_src = f.read()
    body_html = _render_markdown_body(md_src)
    toc = _extract_toc(body_html)

    cover = _build_cover_context(md_path, _load_json(json_path))

    context = {
        **cover,
        "body_html": body_html,
        "toc": toc,
    }

    env = _build_env()
    template = env.get_template(template_name)
    html_str = template.render(**context)

    base_url = str(_STATIC_DIR) + os.sep

    out_path = str(out_path)
    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    HTML(string=html_str, base_url=base_url).write_pdf(
        out_path,
        stylesheets=[CSS(filename=str(_STATIC_DIR / "print.css"))],
    )
    return os.path.abspath(out_path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _iter_md_reports(root: Path, month: str | None) -> Iterable[Path]:
    """Yield monthly markdown reports under ``root``, optionally by month suffix."""
    for p in sorted(root.glob("*.md")):
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
        help="Path to a single monthly report (*.md or *.json) "
             "or a directory of monthly reports.",
    )
    parser.add_argument(
        "output",
        nargs="?",
        help="Output PDF path (single-file mode) or output directory "
             "(batch mode). Defaults to outputs/monthly/pdf/ for batch.",
    )
    parser.add_argument(
        "--month",
        help="Filter batch renders to a specific month, e.g. 2026-04.",
    )
    args = parser.parse_args(argv)

    in_path = Path(args.input)
    if not in_path.exists():
        print(f"error: input path does not exist: {in_path}", file=sys.stderr)
        return 2

    if in_path.is_file():
        out = Path(args.output) if args.output else in_path.with_suffix(".pdf")
        try:
            final = render_pdf_report(in_path, out)
        except Exception as exc:  # pragma: no cover
            print(f"error: PDF render failed: {exc}", file=sys.stderr)
            return 1
        print(f"wrote {final}")
        return 0

    out_dir = Path(args.output) if args.output else Path("outputs/monthly/pdf")
    out_dir.mkdir(parents=True, exist_ok=True)

    ok = 0
    failed = 0
    for md_path in _iter_md_reports(in_path, args.month):
        pdf_path = out_dir / f"{md_path.stem}.pdf"
        try:
            render_pdf_report(md_path, pdf_path)
            ok += 1
            print(f"  + {pdf_path.name}")
        except Exception as exc:
            failed += 1
            print(f"  ! {md_path.name}: {exc}", file=sys.stderr)
    print(f"\nRendered {ok} PDF(s), {failed} failure(s). Output: {out_dir}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(_cli())
