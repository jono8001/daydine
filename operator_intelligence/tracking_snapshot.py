"""Operator tracking snapshot for DayDine V4 reports.

This module turns the monthly operator report into a tracking product by
adding exact market position, category position, public-visibility status,
gap-to-public thresholds and nearest competitors.

Important guardrail: it only renders for league-eligible Rankable reports.
Directional-C and Profile-only-D reports must not leak rank claims.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

from operator_intelligence.v4_adapter import (
    ReportInputs,
    MODE_RANKABLE_A,
    MODE_RANKABLE_B,
)

ROOT = Path(__file__).resolve().parents[1]


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _score(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt(value: float | None) -> str:
    return "—" if value is None else f"{value:.3f}"


def _short_category(cat: str | None) -> str:
    return str(cat or "Restaurant").replace(" (General)", "")


def _market_for_inputs(inputs: ReportInputs) -> dict[str, str] | None:
    """Map known fully scored areas to their score and establishment files."""
    pc = (inputs.postcode or "").upper().replace(" ", "")
    la = _norm(inputs.la)
    address = _norm(inputs.address)

    if pc.startswith("CV37") or "stratford" in la or "stratford" in address:
        return {
            "label": "Stratford-upon-Avon",
            "scores": "stratford_rcs_v4_scores.json",
            "establishments": "stratford_establishments.json",
        }
    if pc.startswith("CV31") or pc.startswith("CV32") or "leamington" in address:
        return {
            "label": "Leamington Spa",
            "scores": "leamington_rcs_v4_scores.json",
            "establishments": "leamington_establishments.json",
        }
    return None


def _load_json(path: str) -> dict[str, Any]:
    p = ROOT / path
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _category(record: dict[str, Any]) -> str:
    """Small local category helper matching the public guide vocabulary."""
    name = _norm(record.get("n"))
    bt = _norm(record.get("fsa_business_type") or record.get("bt"))
    gty = {_norm(t).replace(" ", "_") for t in (record.get("gty") or [])}

    if {"pub", "bar", "wine_bar", "cocktail_bar", "night_club"} & gty or any(x in name for x in [" pub", " bar", " inn"]):
        return "Pub / Bar"
    if {"hotel", "lodging", "bed_and_breakfast", "guest_house"} & gty or "hotel" in bt:
        return "Hotel / Accommodation"
    if "bakery" in gty or any(x in name for x in ["bakery", "baker", "patisserie", "gail"]):
        return "Bakery"
    if {"cafe", "coffee_shop", "tea_house"} & gty or any(x in name for x in ["cafe", "coffee", "tearoom"]):
        return "Cafe / Coffee Shop"
    if {"meal_takeaway", "fast_food_restaurant", "sandwich_shop"} & gty or "takeaway" in bt:
        return "Takeaway / Delivery"
    return "Restaurant (General)"


def _row_for(key: str, score_block: dict[str, Any], establishments: dict[str, Any]) -> dict[str, Any] | None:
    score = _score(score_block.get("rcs_v4_final"))
    if score is None:
        return None
    if not score_block.get("league_table_eligible"):
        return None
    record = establishments.get(str(key)) or establishments.get(str(score_block.get("fhrsid"))) or {}
    name = score_block.get("name") or record.get("public_name") or record.get("n") or str(key)
    return {
        "key": str(key),
        "fhrsid": str(score_block.get("fhrsid") or record.get("fhrsid") or record.get("id") or key),
        "name": name,
        "postcode": record.get("pc") or "",
        "score": score,
        "category": _category(record),
    }


def _current_row_key(inputs: ReportInputs, rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    fhrsid = str(inputs.fhrsid or "")
    name = _norm(inputs.name)
    postcode = _norm(inputs.postcode)
    for row in rows:
        if fhrsid and row.get("fhrsid") == fhrsid:
            return row
    for row in rows:
        if name and _norm(row.get("name")) == name and (not postcode or _norm(row.get("postcode")) == postcode):
            return row
    for row in rows:
        if name and _norm(row.get("name")) == name:
            return row
    return None


def _prior_metric(inputs: ReportInputs, *keys: str) -> Any:
    prior = inputs.prior_snapshot or {}
    for key in keys:
        if key in prior:
            return prior.get(key)
    return None


def _movement_text(inputs: ReportInputs, rank: int, category_rank: int, score: float) -> str:
    prior_rank = _prior_metric(inputs, "overall_rank", "rank", "market_rank")
    prior_cat = _prior_metric(inputs, "category_rank")
    prior_score = _prior_metric(inputs, "rcs_v4_final", "score", "rcs")
    parts: list[str] = []
    if isinstance(prior_rank, int):
        delta = prior_rank - rank
        if delta > 0:
            parts.append(f"overall rank up {delta}")
        elif delta < 0:
            parts.append(f"overall rank down {abs(delta)}")
        else:
            parts.append("overall rank unchanged")
    if isinstance(prior_cat, int):
        delta = prior_cat - category_rank
        if delta > 0:
            parts.append(f"category rank up {delta}")
        elif delta < 0:
            parts.append(f"category rank down {abs(delta)}")
        else:
            parts.append("category rank unchanged")
    try:
        if prior_score is not None:
            ds = score - float(prior_score)
            parts.append(f"RCS {'+' if ds >= 0 else ''}{ds:.3f}")
    except (TypeError, ValueError):
        pass
    return "; ".join(parts) if parts else "No prior snapshot supplied yet — this becomes the baseline month."


def _gap_text(rank: int, current_score: float, rows: list[dict[str, Any]], threshold_index: int, label: str) -> str:
    if len(rows) < threshold_index:
        return f"No {label} threshold yet."
    threshold = rows[threshold_index - 1]["score"]
    if rank <= threshold_index:
        return f"Already inside {label}."
    return f"+{max(0.0, threshold - current_score):.3f} RCS points to reach the current {label} threshold ({threshold:.3f})."


def _visibility(rank: int, category_rank: int) -> str:
    if rank <= 10:
        return "Public top 10 overall"
    if category_rank <= 3:
        return "Public category top 3"
    return "Tracked, but not currently public-shortlisted"


def _load_market_rows(inputs: ReportInputs) -> tuple[dict[str, str] | None, list[dict[str, Any]], dict[str, Any] | None]:
    market = _market_for_inputs(inputs)
    if not market:
        return None, [], None
    scores = _load_json(market["scores"])
    establishments = _load_json(market["establishments"])
    rows = []
    for key, block in scores.items():
        row = _row_for(str(key), block, establishments)
        if row:
            rows.append(row)
    rows.sort(key=lambda r: r["score"], reverse=True)
    current = _current_row_key(inputs, rows)
    return market, rows, current


def render_operator_tracking_snapshot(out: Callable[[str], None], inputs: ReportInputs) -> None:
    """Render the operator tracking snapshot.

    Called from the main report generator after the V4 score card. It is
    deliberately silent when rank claims are not allowed.
    """
    if inputs.report_mode not in {MODE_RANKABLE_A, MODE_RANKABLE_B}:
        return
    if not inputs.league_table_eligible or inputs.rcs_v4_final is None:
        return

    market, rows, current = _load_market_rows(inputs)
    if not market or not rows or not current:
        out("## Monthly Tracking Snapshot")
        out("")
        out("This venue is fully scored, but no local market ranking file was available for this report run. The next generated report should include exact position, category rank and competitor gap once the local market file is present.")
        out("")
        return

    current_score = current["score"]
    rank = next(i for i, row in enumerate(rows, 1) if row is current)
    category = current["category"]
    category_rows = [row for row in rows if row["category"] == category]
    category_rank = next(i for i, row in enumerate(category_rows, 1) if row is current)

    top10_gap = _gap_text(rank, current_score, rows, 10, "public top 10")
    cat3_gap = _gap_text(category_rank, current_score, category_rows, 3, f"{_short_category(category)} top 3")
    public_visibility = _visibility(rank, category_rank)
    movement = _movement_text(inputs, rank, category_rank, current_score)

    out("## Monthly Tracking Snapshot")
    out("")
    out("This is the commercial tracking layer: it shows whether the venue is publicly visible, how far it is from the public shortlist, and which nearby competitors define the current gap.")
    out("")
    out("| Tracking metric | Current position | Commercial meaning |")
    out("|---|---:|---|")
    out(f"| Local market | {market['label']} | Fully scored DayDine market |")
    out(f"| Overall DayDine position | #{rank} of {len(rows)} | {public_visibility} |")
    out(f"| Category position | #{category_rank} of {len(category_rows)} {_short_category(category).lower()} venues | Public category visibility starts at top 3 |")
    out(f"| DayDine RCS | {_fmt(current_score)} | Current baseline for future movement tracking |")
    out(f"| Gap to public top 10 | {top10_gap} | Shows whether the venue is close to public overall visibility |")
    out(f"| Gap to category top 3 | {cat3_gap} | Shows whether the venue is close to category visibility |")
    out(f"| Monthly movement | {movement} | Used to track whether actions are translating into visible progress |")
    out("")

    lower = max(0, rank - 3)
    upper = min(len(rows), rank + 2)
    neighbours = rows[lower:upper]
    if neighbours:
        out("**Nearest overall competitors**")
        out("")
        out("| Rank | Venue | Category | RCS | Gap vs you |")
        out("|---:|---|---|---:|---:|")
        for idx, row in enumerate(neighbours, lower + 1):
            gap = row["score"] - current_score
            marker = "you" if row is current else (f"{gap:+.3f}")
            out(f"| #{idx} | {row['name']} | {_short_category(row['category'])} | {_fmt(row['score'])} | {marker} |")
        out("")

    out("**Operator focus for next month**")
    out("")
    if rank <= 10 or category_rank <= 3:
        out("- Protect current public visibility: keep the listing complete, maintain review momentum, and avoid hygiene/compliance issues that could cap the score.")
    else:
        out("- Treat the top-10/category-top-3 gap as the monthly target: focus first on missing commercial-readiness signals, then review volume/validation, then any trust/compliance caps.")
    out("- Use this section month by month: the paid report should show whether position, category rank and RCS are moving, not just explain the current score.")
    out("")
