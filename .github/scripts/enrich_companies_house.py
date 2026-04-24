#!/usr/bin/env python3
"""Enrich Stratford establishments with conservative Companies House risk data.

This uses the official Companies House API and is deliberately conservative:
- it only writes high-confidence company matches;
- it does not scrape websites or infer weak matches;
- it is used as a risk/cap layer, not as a positive ranking booster;
- if COMPANIES_HOUSE_API_KEY is absent, it writes an empty risk file and exits 0.

Output:
    stratford_companies_house.json
    stratford_companies_house_coverage.json
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import requests

INPUT_PATH = Path("stratford_establishments.json")
OUTPUT_PATH = Path("stratford_companies_house.json")
COVERAGE_PATH = Path("stratford_companies_house_coverage.json")
BASE_URL = "https://api.company-information.service.gov.uk"
RATE_LIMIT_SECONDS = 0.18
LEGAL_SUFFIX_RE = re.compile(r"\b(ltd|limited|llp|plc|cic)\b", re.I)
LEGAL_SUFFIX_STRIP_RE = re.compile(r"\b(ltd|limited|llp|plc|cic)\b\.?", re.I)
GENERIC_WORDS = {"the", "and", "of", "at", "in", "upon", "on", "restaurant", "cafe", "bar", "pub", "hotel", "limited", "ltd"}


def normalise_name(value: Any, strip_suffix: bool = True) -> str:
    text = str(value or "").lower().replace("&", " and ")
    if strip_suffix:
        text = LEGAL_SUFFIX_STRIP_RE.sub(" ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def tokens(value: str) -> set[str]:
    return {t for t in value.split() if t and t not in GENERIC_WORDS}


def has_legal_suffix(value: Any) -> bool:
    return bool(LEGAL_SUFFIX_RE.search(str(value or "")))


def record_key(key: str, record: dict[str, Any]) -> str:
    return str(record.get("fhrsid") or record.get("id") or key)


def candidate_names(record: dict[str, Any]) -> list[tuple[str, str]]:
    seen = set()
    names: list[tuple[str, str]] = []
    for source, value in (
        ("fsa_business_name", record.get("fsa_business_name")),
        ("public_name", record.get("public_name")),
        ("name", record.get("n")),
    ):
        text = str(value or "").strip()
        if not text:
            continue
        canon = normalise_name(text)
        if not canon or canon in seen:
            continue
        seen.add(canon)
        names.append((source, text))
    return names


def api_get(path: str, api_key: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
    response = requests.get(
        f"{BASE_URL}{path}",
        params=params or {},
        auth=(api_key, ""),
        timeout=25,
    )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


def search_companies(query: str, api_key: str) -> list[dict[str, Any]]:
    payload = api_get("/search/companies", api_key, {"q": query, "items_per_page": 5})
    if not payload:
        return []
    return [x for x in payload.get("items", []) if isinstance(x, dict)]


def choose_match(candidate: str, items: list[dict[str, Any]]) -> dict[str, Any] | None:
    cand_norm = normalise_name(candidate)
    cand_full_norm = normalise_name(candidate, strip_suffix=False)
    cand_tokens = tokens(cand_norm)
    candidate_has_suffix = has_legal_suffix(candidate)

    best: dict[str, Any] | None = None
    for item in items:
        title = item.get("title") or ""
        title_norm = normalise_name(title)
        title_full_norm = normalise_name(title, strip_suffix=False)
        title_tokens = tokens(title_norm)

        exact_full = cand_full_norm == title_full_norm
        exact_stripped = cand_norm == title_norm
        strong_token_overlap = bool(cand_tokens) and cand_tokens == title_tokens and len(cand_tokens) >= 2

        if candidate_has_suffix and (exact_full or exact_stripped):
            score = 100
        elif exact_stripped and len(cand_tokens) >= 2:
            score = 95
        elif strong_token_overlap:
            score = 90
        else:
            continue

        if best is None or score > best["_match_score"]:
            best = dict(item)
            best["_match_score"] = score

    return best


def days_overdue(due_on: Any) -> int | None:
    if not due_on:
        return None
    try:
        due = datetime.fromisoformat(str(due_on)).date()
    except ValueError:
        return None
    return max(0, (date.today() - due).days)


def extract_company_profile(company_number: str, api_key: str) -> dict[str, Any] | None:
    return api_get(f"/company/{company_number}", api_key)


def to_risk_record(record: dict[str, Any], source_name: str, match: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    accounts = profile.get("accounts") or {}
    next_accounts = accounts.get("next_accounts") or {}
    confirmation = profile.get("confirmation_statement") or {}
    due_on = next_accounts.get("due_on") or accounts.get("next_due")
    overdue = days_overdue(due_on)
    accounts_overdue = bool(next_accounts.get("overdue") or accounts.get("overdue") or (overdue is not None and overdue > 0))

    return {
        "source": "companies_house_api",
        "match_confidence": "high",
        "match_source": source_name,
        "company_number": profile.get("company_number") or match.get("company_number"),
        "company_name": profile.get("company_name") or match.get("title"),
        "company_status": profile.get("company_status") or match.get("company_status"),
        "company_type": profile.get("type"),
        "date_of_creation": profile.get("date_of_creation"),
        "sic_codes": profile.get("sic_codes") or [],
        "registered_office_postal_code": (profile.get("registered_office_address") or {}).get("postal_code"),
        "accounts_next_due": due_on,
        "accounts_overdue": accounts_overdue,
        "accounts_overdue_days": overdue or 0,
        "confirmation_statement_overdue": bool(confirmation.get("overdue")),
        "matched_query_name": record.get("fsa_business_name") or record.get("n"),
        "fsa_business_name": record.get("fsa_business_name"),
        "venue_name": record.get("n"),
    }


def main() -> int:
    api_key = os.environ.get("COMPANIES_HOUSE_API_KEY")
    if not INPUT_PATH.exists():
        print(f"ERROR: {INPUT_PATH} not found", file=sys.stderr)
        return 1

    establishments = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    if not isinstance(establishments, dict):
        print(f"ERROR: {INPUT_PATH} is not a dict", file=sys.stderr)
        return 1

    if not api_key:
        OUTPUT_PATH.write_text("{}\n", encoding="utf-8")
        COVERAGE_PATH.write_text(json.dumps({
            "enabled": False,
            "reason": "COMPANIES_HOUSE_API_KEY not set",
            "total_establishments": len(establishments),
            "matched": 0,
            "unmatched": len(establishments),
        }, indent=2) + "\n", encoding="utf-8")
        print("COMPANIES_HOUSE_API_KEY not set; wrote empty Companies House risk file")
        return 0

    risk: dict[str, Any] = {}
    stats = {
        "enabled": True,
        "total_establishments": len(establishments),
        "searched": 0,
        "matched": 0,
        "unmatched": 0,
        "api_errors": 0,
        "match_policy": "high-confidence exact/strong name matches only",
    }

    for key, record in establishments.items():
        if not isinstance(record, dict):
            continue
        matched = False
        names = candidate_names(record)
        # Prefer legal-looking names first; then exact stripped-name candidates.
        names.sort(key=lambda pair: 0 if has_legal_suffix(pair[1]) else 1)
        for source_name, query in names:
            try:
                stats["searched"] += 1
                items = search_companies(query, api_key)
                time.sleep(RATE_LIMIT_SECONDS)
                match = choose_match(query, items)
                if not match:
                    continue
                company_number = match.get("company_number")
                if not company_number:
                    continue
                profile = extract_company_profile(company_number, api_key)
                time.sleep(RATE_LIMIT_SECONDS)
                if not profile:
                    continue
                risk[record_key(str(key), record)] = to_risk_record(record, source_name, match, profile)
                stats["matched"] += 1
                matched = True
                print(f"Matched CH: {record.get('n')} -> {profile.get('company_name')} ({company_number})")
                break
            except Exception as exc:
                stats["api_errors"] += 1
                print(f"Companies House lookup failed for {record.get('n') or key}: {exc}", file=sys.stderr)
                break
        if not matched:
            stats["unmatched"] += 1

    OUTPUT_PATH.write_text(json.dumps(risk, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    COVERAGE_PATH.write_text(json.dumps(stats, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Companies House enrichment complete: matched={stats['matched']}, unmatched={stats['unmatched']}, errors={stats['api_errors']}")
    # Do not fail the ranking refresh for partial CH coverage; this is a risk layer.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
