#!/usr/bin/env python3
"""Generate committed market-readiness JSON assets for the admin console.

Reads configured areas from data/ranking_areas.json and writes:
- assets/market-readiness/<market>.json
- assets/market-readiness/index.json

The script is offline/deterministic and delegates per-market QA to
scripts/check_market_readiness.py.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
AREAS_FILE = ROOT / "data" / "ranking_areas.json"
OUT_DIR = ROOT / "assets" / "market-readiness"


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


def load_check_module():
    path = ROOT / "scripts" / "check_market_readiness.py"
    spec = importlib.util.spec_from_file_location("check_market_readiness", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def safe_summary(summary: dict[str, Any]) -> dict[str, Any]:
    """Keep admin console JSON useful but compact."""
    return {
        "generated_at": summary.get("generated_at"),
        "market": summary.get("market"),
        "display_name": summary.get("display_name"),
        "area_type": summary.get("area_type"),
        "public": summary.get("public"),
        "operator": summary.get("operator"),
        "data_source_prefix": summary.get("data_source_prefix"),
        "status": summary.get("status"),
        "counts": summary.get("counts", {}),
        "files": summary.get("files", {}),
        "top_warnings": summary.get("top_warnings", []),
        "alias_missing_from_establishments": summary.get("alias_missing_from_establishments", []),
        "alias_unresolved_without_guardrail": summary.get("alias_unresolved_without_guardrail", []),
        "active_known_missing_venues": summary.get("active_known_missing_venues", []),
        "known_missing_venues": summary.get("known_missing_venues", []),
        "duplicate_or_ambiguous_gpid_groups": summary.get("duplicate_or_ambiguous_gpid_groups", []),
    }


def generate(selected_markets: list[str] | None = None) -> dict[str, Any]:
    checker = load_check_module()
    config = read_json(AREAS_FILE, {"areas": []}) or {"areas": []}
    areas = config.get("areas", []) or []
    selected = {m for m in selected_markets or []}
    generated_at = datetime.now(timezone.utc).isoformat()
    entries = []

    for area in areas:
        slug = area.get("slug")
        if not slug:
            continue
        if selected and slug not in selected:
            continue
        summary = safe_summary(checker.build_summary(slug))
        out_path = OUT_DIR / f"{slug}.json"
        write_json(out_path, summary)
        counts = summary.get("counts", {})
        entries.append({
            "slug": slug,
            "display_name": summary.get("display_name") or area.get("display_name"),
            "area_type": summary.get("area_type") or area.get("area_type"),
            "public": bool(summary.get("public")),
            "operator": bool(summary.get("operator")),
            "status": summary.get("status"),
            "generated_at": summary.get("generated_at"),
            "readiness_url": f"/assets/market-readiness/{slug}.json",
            "counts": counts,
            "warning_count": len(summary.get("top_warnings", []) or []),
            "active_known_missing_venues": counts.get("active_known_missing_venues", 0),
            "duplicate_or_ambiguous_gpid_groups": counts.get("duplicate_or_ambiguous_gpid_groups", 0),
        })

    status_rank = {"blocked": 3, "warning": 2, "ready": 1}
    worst = "ready"
    for entry in entries:
        if status_rank.get(entry.get("status"), 0) > status_rank.get(worst, 0):
            worst = entry.get("status") or worst

    index = {
        "generated_at": generated_at,
        "status": worst,
        "total_markets": len(entries),
        "ready_markets": sum(1 for e in entries if e.get("status") == "ready"),
        "warning_markets": sum(1 for e in entries if e.get("status") == "warning"),
        "blocked_markets": sum(1 for e in entries if e.get("status") == "blocked"),
        "markets": sorted(entries, key=lambda e: (str(e.get("display_name") or "").lower(), str(e.get("slug") or ""))),
    }
    write_json(OUT_DIR / "index.json", index)
    return index


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--market", action="append", help="Optional slug to generate; repeat for multiple markets")
    args = parser.parse_args()
    index = generate(args.market)
    print(f"Generated readiness for {index['total_markets']} market(s). Overall status: {index['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
