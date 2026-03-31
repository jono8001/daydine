#!/usr/bin/env python3
"""
collect_companies_house.py — Check business viability via Companies House API.

Searches for each restaurant as a registered company, extracting
company status, accounts status, director changes, and insolvency.

Free API: https://developer.company-information.service.gov.uk/
SIC codes: 56101 (restaurants), 56102 (takeaway), 56103 (pubs)

Requires: COMPANIES_HOUSE_API_KEY environment variable

Reads:  stratford_establishments.json
Writes: stratford_companies_house.json
"""

import difflib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

import requests

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
INPUT_PATH = os.path.join(REPO_ROOT, "stratford_establishments.json")
OUTPUT_PATH = os.path.join(REPO_ROOT, "stratford_companies_house.json")

API_KEY = os.environ.get("COMPANIES_HOUSE_API_KEY", "")
CH_SEARCH_URL = "https://api.company-information.service.gov.uk/search/companies"
CH_COMPANY_URL = "https://api.company-information.service.gov.uk/company"

FOOD_SIC_CODES = {"56101", "56102", "56103", "56210", "56301", "56302"}
NOW = datetime.now(timezone.utc)


def normalise(name):
    name = name.lower().strip()
    name = re.sub(r"\b(ltd|limited|plc|llp|inc)\b", "", name)
    name = re.sub(r"[^\w\s]", "", name)
    return re.sub(r"\s+", " ", name).strip()


def fuzzy(a, b):
    return difflib.SequenceMatcher(None, normalise(a), normalise(b)).ratio()


def search_company(name, postcode=""):
    """Search Companies House for a company by name."""
    params = {"q": name, "items_per_page": 5}
    try:
        resp = requests.get(CH_SEARCH_URL, params=params,
                            auth=(API_KEY, ""), timeout=15)
        if resp.status_code == 429:
            time.sleep(5)
            resp = requests.get(CH_SEARCH_URL, params=params,
                                auth=(API_KEY, ""), timeout=15)
        resp.raise_for_status()
        return resp.json().get("items", [])
    except requests.RequestException as e:
        print(f"    CH search error: {e}")
        return []


def get_company_details(company_number):
    """Get full company details."""
    try:
        resp = requests.get(f"{CH_COMPANY_URL}/{company_number}",
                            auth=(API_KEY, ""), timeout=15)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException:
        return None


def get_officers(company_number):
    """Get company officers (directors)."""
    try:
        resp = requests.get(f"{CH_COMPANY_URL}/{company_number}/officers",
                            auth=(API_KEY, ""), timeout=15)
        resp.raise_for_status()
        return resp.json().get("items", [])
    except requests.RequestException:
        return []


def process_company(name, postcode):
    """Search and extract Companies House data for a restaurant."""
    results = search_company(name)
    if not results:
        return None

    # Find best match by name + optional postcode
    best = None
    best_score = 0
    for item in results:
        title = item.get("title", "")
        score = fuzzy(name, title)
        # Bonus if postcode area matches
        addr = item.get("address_snippet", "").upper()
        pc_prefix = postcode[:4].strip().upper() if postcode else ""
        if pc_prefix and pc_prefix in addr:
            score += 0.1
        if score > best_score:
            best_score = score
            best = item

    if not best or best_score < 0.5:
        return None

    company_number = best.get("company_number", "")
    details = get_company_details(company_number) if company_number else None

    entry = {
        "ch_name": best.get("title", ""),
        "company_number": company_number,
        "match_score": round(best_score, 2),
        "company_status": best.get("company_status", "unknown"),
    }

    if details:
        # Accounts overdue
        accounts = details.get("accounts", {})
        if accounts.get("overdue"):
            entry["accounts_overdue"] = True

        # Company age
        created = details.get("date_of_creation")
        if created:
            try:
                dt = datetime.fromisoformat(created)
                age_days = (NOW.replace(tzinfo=None) - dt).days
                entry["company_age_years"] = round(age_days / 365.25, 1)
            except (ValueError, TypeError):
                pass

        # SIC codes
        sic = details.get("sic_codes", [])
        entry["sic_codes"] = sic
        entry["is_food_sic"] = bool(set(sic) & FOOD_SIC_CODES)

        # Insolvency
        if details.get("has_insolvency_history"):
            entry["insolvency"] = True

    # Director changes in last 12 months
    if company_number:
        officers = get_officers(company_number)
        recent_changes = 0
        cutoff = NOW.replace(tzinfo=None).replace(year=NOW.year - 1)
        for officer in officers:
            appointed = officer.get("appointed_on", "")
            resigned = officer.get("resigned_on", "")
            try:
                if appointed and datetime.fromisoformat(appointed) > cutoff:
                    recent_changes += 1
                if resigned and datetime.fromisoformat(resigned) > cutoff:
                    recent_changes += 1
            except (ValueError, TypeError):
                pass
        entry["director_changes_12m"] = recent_changes
        time.sleep(0.3)  # Rate limit

    return entry


def main():
    if not API_KEY:
        print("ERROR: COMPANIES_HOUSE_API_KEY not set")
        print("Get a free key at: https://developer.company-information.service.gov.uk/")
        sys.exit(1)

    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        establishments = json.load(f)
    print(f"Loaded {len(establishments)} establishments")

    ch_data = {}
    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
            existing = json.load(f)
        ch_data = {k: v for k, v in existing.items() if v.get("company_number")}
        print(f"Loaded {len(ch_data)} existing CH records (resuming)")

    matched = 0
    total = len(establishments)
    for i, (key, record) in enumerate(establishments.items(), 1):
        if key in ch_data:
            continue
        name = record.get("n", "")
        postcode = record.get("pc", "")
        if not name:
            ch_data[key] = {"_skipped": True}
            continue

        result = process_company(name, postcode)
        time.sleep(0.5)  # Rate limit

        if result:
            ch_data[key] = result
            matched += 1
            status = result.get("company_status", "?")
            print(f"  [{i}/{total}] {name} -> {result['ch_name']} ({status})")
        else:
            ch_data[key] = {"_no_match": True}

        if i % 25 == 0:
            with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
                json.dump(ch_data, f, indent=2, ensure_ascii=False)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(ch_data, f, indent=2, ensure_ascii=False)

    print(f"\nDone. Matched: {matched}/{total}")
    dissolved = sum(1 for v in ch_data.values() if v.get("company_status") == "dissolved")
    overdue = sum(1 for v in ch_data.values() if v.get("accounts_overdue"))
    print(f"  Dissolved: {dissolved}, Accounts overdue: {overdue}")


if __name__ == "__main__":
    main()
