#!/usr/bin/env python3
"""Run DayDine V4 scoring with optional Companies House risk input.

This is intentionally a wrapper around rcs_scoring_v4.py, not a replacement for
that engine. The V4 engine already contains the Companies House risk/cap rules;
this runner makes the CLI path pass the enrichment file into score_batch.

Companies House is treated as a conservative risk layer. Raw CH matches are
collected, but negative CH risk signals are only passed into scoring after they
have been explicitly approved in data/companies_house_risk_reviews.json. This
avoids over-penalising a public ranking because a trading venue matched a legacy
or ambiguous legal entity.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rcs_scoring_v4 import score_batch, score_venue

DEFAULT_REVIEW_FILE = ROOT / "data" / "companies_house_risk_reviews.json"
DEFAULT_AUDIT_FILE = ROOT / "stratford_companies_house_review_audit.json"
ACTIVE_COMPANY_STATUSES = {"active"}


def read_json(path: str | Path | None, default: Any) -> Any:
    if not path:
        return default
    p = Path(path)
    if not p.exists():
        return default
    with p.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: str | Path, data: dict[str, Any]) -> None:
    with Path(path).open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def norm(value: Any) -> str:
    return str(value or "").strip().lower()


def review_decision(review: dict[str, Any]) -> str:
    decision = norm(review.get("decision") or review.get("status"))
    if decision in {"approved", "approve", "apply", "accepted"}:
        return "approved"
    if decision in {"rejected", "reject", "ignore", "do_not_apply", "not_applicable"}:
        return "rejected"
    return "pending"


def review_matches(review: dict[str, Any], key: str, risk: dict[str, Any]) -> bool:
    for field in ("fhrsid", "company_number", "venue_name"):
        value = norm(review.get(field))
        if not value:
            continue
        if field == "fhrsid" and value == norm(key):
            return True
        if field == "company_number" and value == norm(risk.get("company_number")):
            return True
        if field == "venue_name" and value == norm(risk.get("venue_name")):
            return True
    return False


def find_review(key: str, risk: dict[str, Any], reviews: list[dict[str, Any]]) -> dict[str, Any] | None:
    for review in reviews:
        if review_matches(review, key, risk):
            return review
    return None


def has_negative_ch_signal(risk: dict[str, Any]) -> bool:
    status = norm(risk.get("company_status"))
    if status and status not in ACTIVE_COMPANY_STATUSES:
        return True
    if risk.get("accounts_overdue") or int(risk.get("accounts_overdue_days") or 0) > 0:
        return True
    if risk.get("confirmation_statement_overdue"):
        return True
    return False


def filter_companies_house_for_review(raw: dict[str, Any], review_config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return scoring-safe CH data plus audit of held/applied records."""
    policy = review_config.get("policy") or {}
    require_review = policy.get("mode") == "review_required_for_risk"
    reviews = [x for x in review_config.get("reviews", []) if isinstance(x, dict)]

    safe: dict[str, Any] = {}
    audit = {
        "policy_mode": policy.get("mode", "none"),
        "raw_matches": len(raw),
        "passed_to_scoring": 0,
        "held_for_review": 0,
        "rejected_by_review": 0,
        "approved_by_review": 0,
        "clean_active_passed": 0,
        "held_records": [],
    }

    for key, risk in raw.items():
        if not isinstance(risk, dict):
            continue
        negative = has_negative_ch_signal(risk)
        review = find_review(str(key), risk, reviews)
        decision = review_decision(review or {}) if review else "pending"

        if require_review and negative:
            if decision == "approved":
                safe[str(key)] = risk
                audit["approved_by_review"] += 1
                audit["passed_to_scoring"] += 1
            elif decision == "rejected":
                audit["rejected_by_review"] += 1
                audit["held_records"].append({
                    "fhrsid": str(key),
                    "venue_name": risk.get("venue_name"),
                    "company_name": risk.get("company_name"),
                    "company_number": risk.get("company_number"),
                    "company_status": risk.get("company_status"),
                    "accounts_overdue_days": risk.get("accounts_overdue_days"),
                    "decision": "rejected",
                })
            else:
                audit["held_for_review"] += 1
                audit["held_records"].append({
                    "fhrsid": str(key),
                    "venue_name": risk.get("venue_name"),
                    "company_name": risk.get("company_name"),
                    "company_number": risk.get("company_number"),
                    "company_status": risk.get("company_status"),
                    "accounts_overdue_days": risk.get("accounts_overdue_days"),
                    "decision": "pending_review",
                })
            continue

        safe[str(key)] = risk
        audit["passed_to_scoring"] += 1
        if not negative:
            audit["clean_active_passed"] += 1

    return safe, audit


def score_records(records: dict[str, Any], editorial: dict[str, Any], companies_house: dict[str, Any], menus: dict[str, Any]) -> dict[str, Any]:
    """Call score_batch where supported, with a safe per-record fallback."""
    try:
        return score_batch(
            records,
            editorial=editorial,
            companies_house=companies_house,
            menus=menus,
        )
    except TypeError:
        scored: dict[str, Any] = {}
        for key, record in records.items():
            scored[key] = score_venue(
                record,
                editorial=editorial.get(str(key)) or editorial.get(key),
                companies_house=companies_house.get(str(key)) or companies_house.get(key),
                menu=menus.get(str(key)) or menus.get(key),
            )
        return scored


def serialise_scores(scores: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, score in scores.items():
        output[str(key)] = score.to_dict() if hasattr(score, "to_dict") else score
    return output


def write_csv(path: str, data: dict[str, Any]) -> None:
    fields = [
        "id", "fhrsid", "name", "rcs_v4_final", "base_score", "adjusted_score",
        "confidence_class", "coverage_status", "rankable", "league_table_eligible",
        "companies_house", "penalties", "caps",
    ]
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for key, row in data.items():
            source_summary = row.get("source_family_summary") or {}
            writer.writerow({
                "id": key,
                "fhrsid": row.get("fhrsid"),
                "name": row.get("name"),
                "rcs_v4_final": row.get("rcs_v4_final"),
                "base_score": row.get("base_score"),
                "adjusted_score": row.get("adjusted_score"),
                "confidence_class": row.get("confidence_class"),
                "coverage_status": row.get("coverage_status"),
                "rankable": row.get("rankable"),
                "league_table_eligible": row.get("league_table_eligible"),
                "companies_house": source_summary.get("companies_house"),
                "penalties": json.dumps(row.get("penalties_applied") or [], ensure_ascii=False),
                "caps": json.dumps(row.get("caps_applied") or [], ensure_ascii=False),
            })


def summarise_companies_house(data: dict[str, Any]) -> dict[str, int]:
    penalties = caps = matched = 0
    for row in data.values():
        source_summary = row.get("source_family_summary") or {}
        if source_summary.get("companies_house") == "matched":
            matched += 1
        penalties += sum(1 for p in row.get("penalties_applied") or [] if str(p.get("code", "")).startswith("CH-"))
        caps += sum(1 for c in row.get("caps_applied") or [] if str(c.get("code", "")).startswith("CH-"))
    return {"matched": matched, "penalties": penalties, "caps": caps}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--menus", default=None)
    parser.add_argument("--editorial", default=None)
    parser.add_argument("--companies-house", default=None)
    parser.add_argument("--companies-house-reviews", default=str(DEFAULT_REVIEW_FILE))
    parser.add_argument("--companies-house-review-audit", default=str(DEFAULT_AUDIT_FILE))
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-csv", required=True)
    args = parser.parse_args()

    records = read_json(args.input, {})
    menus = read_json(args.menus, {})
    editorial = read_json(args.editorial, {})
    raw_companies_house = read_json(args.companies_house, {})
    review_config = read_json(args.companies_house_reviews, {"policy": {"mode": "none"}, "reviews": []})
    companies_house, review_audit = filter_companies_house_for_review(raw_companies_house, review_config)
    write_json(args.companies_house_review_audit, review_audit)

    raw_scores = score_records(records, editorial, companies_house, menus)
    scores = serialise_scores(raw_scores)
    write_json(args.out_json, scores)
    write_csv(args.out_csv, scores)

    summary = summarise_companies_house(scores)
    print(
        "V4 scoring complete: "
        f"records={len(scores)}, companies_house_matched={summary['matched']}, "
        f"ch_penalties={summary['penalties']}, ch_caps={summary['caps']}, "
        f"ch_held_for_review={review_audit['held_for_review']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
