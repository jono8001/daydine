#!/usr/bin/env python3
"""Apply report-aligned facts to generated operator dashboards.

The dashboard generator pulls live/current ranking assets. For venues that also
have a detailed operator report, this script overlays the report's commercial
facts so the client screen remains aligned with the report narrative while still
showing the live public diner view separately.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
TARGETS_FILE = ROOT / "data" / "operator_dashboard_targets.json"
OUT_DIR = ROOT / "assets" / "operator-dashboards"


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def apply_alignment(snapshot: dict[str, Any], aligned: dict[str, Any]) -> dict[str, Any]:
    public_context = {
        "label": "Current public diner view",
        "market": snapshot.get("market"),
        "overall_rank": snapshot.get("headline", {}).get("overall_rank"),
        "overall_total": snapshot.get("headline", {}).get("overall_total"),
        "category_rank": snapshot.get("headline", {}).get("category_rank"),
        "category_total": snapshot.get("headline", {}).get("category_total"),
        "public_rcs": snapshot.get("scores", {}).get("public_rcs"),
        "visibility": snapshot.get("headline", {}).get("public_visibility"),
        "note": "This reflects the current public town-market ranking asset and may differ from the wider operator intelligence report view.",
    }
    operator_context = {
        "label": "Operator intelligence view",
        "report_label": aligned.get("report_label"),
        "market": aligned.get("operator_market_name") or snapshot.get("market"),
        "overall_rank": aligned.get("operator_market_rank"),
        "overall_total": aligned.get("operator_market_total"),
        "category_rank": aligned.get("operator_category_rank"),
        "category_total": aligned.get("operator_category_total"),
        "category_label": aligned.get("operator_category_label"),
        "operator_v4_score": aligned.get("operator_v4_score"),
        "visibility": aligned.get("public_visibility"),
        "note": "This is the report-aligned commercial/operator view used for client interpretation and recommendations.",
    }

    snapshot["report_aligned"] = True
    snapshot["alignment_applied_at"] = datetime.now(timezone.utc).isoformat()
    snapshot["operator_context"] = operator_context
    snapshot["public_context"] = public_context

    snapshot["headline"]["overall_rank"] = aligned.get("operator_market_rank", snapshot["headline"].get("overall_rank"))
    snapshot["headline"]["overall_total"] = aligned.get("operator_market_total", snapshot["headline"].get("overall_total"))
    snapshot["headline"]["category_rank"] = aligned.get("operator_category_rank", snapshot["headline"].get("category_rank"))
    snapshot["headline"]["category_total"] = aligned.get("operator_category_total", snapshot["headline"].get("category_total"))
    snapshot["headline"]["public_visibility"] = aligned.get("public_visibility", snapshot["headline"].get("public_visibility"))
    snapshot["headline"]["tracking_status"] = aligned.get("tracking_status", snapshot["headline"].get("tracking_status"))

    snapshot["scores"]["operator_v4_score"] = aligned.get("operator_v4_score", snapshot["scores"].get("operator_v4_score"))
    snapshot["scores"]["confidence_class"] = aligned.get("confidence_class", snapshot["scores"].get("confidence_class"))
    snapshot["scores"]["rankable"] = aligned.get("rankable", snapshot["scores"].get("rankable"))
    snapshot["scores"]["league_eligible"] = aligned.get("league_eligible", snapshot["scores"].get("league_eligible"))
    snapshot["scores"]["entity_match"] = aligned.get("entity_match", snapshot["scores"].get("entity_match"))

    if aligned.get("components"):
        snapshot["components"] = aligned["components"]
    if aligned.get("priorities"):
        snapshot["priorities"] = aligned["priorities"]
    if aligned.get("commercial_impact"):
        snapshot["commercial_impact"] = aligned["commercial_impact"]
    if aligned.get("what_not_to_do"):
        snapshot["what_not_to_do"] = aligned["what_not_to_do"]
    if aligned.get("final_takeaway"):
        snapshot["final_takeaway"] = aligned["final_takeaway"]
    if aligned.get("commercial_readiness_gap"):
        snapshot["commercial_readiness_gap"] = aligned["commercial_readiness_gap"]
    if aligned.get("commercial_readiness_score") is not None:
        snapshot["commercial_readiness_score"] = aligned["commercial_readiness_score"]

    # Ensure history tracks the report-aligned headline after overlay.
    current_month = snapshot.get("month")
    for row in snapshot.get("history", []):
        if row.get("month") == current_month:
            row["overall_rank"] = snapshot["headline"].get("overall_rank")
            row["category_rank"] = snapshot["headline"].get("category_rank")
            row["operator_v4_score"] = snapshot["scores"].get("operator_v4_score")
            row["confidence_class"] = snapshot["scores"].get("confidence_class")
    return snapshot


def main() -> int:
    config = read_json(TARGETS_FILE, {"dashboards": []}) or {}
    updated = []
    for target in config.get("dashboards", []) or []:
        aligned = target.get("report_aligned") or {}
        if not aligned.get("enabled"):
            continue
        slug = target.get("venue_slug")
        month = config.get("month", "2026-04")
        paths = [OUT_DIR / slug / f"{month}.json", OUT_DIR / slug / "latest.json"]
        for path in paths:
            snapshot = read_json(path, None)
            if not isinstance(snapshot, dict):
                continue
            write_json(path, apply_alignment(snapshot, aligned))
            updated.append(str(path.relative_to(ROOT)))
    manifest_path = OUT_DIR / "manifest.json"
    manifest = read_json(manifest_path, {}) or {}
    for item in manifest.get("dashboards", []) or []:
        if any(item.get("venue_slug") == (t.get("venue_slug")) for t in config.get("dashboards", []) if (t.get("report_aligned") or {}).get("enabled")):
            item["report_aligned"] = True
            item["notes"] = "Generated dashboard with report-aligned commercial facts and retained monthly history."
    if manifest:
        write_json(manifest_path, manifest)
    print(f"Applied report alignment to {len(updated)} dashboard file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
