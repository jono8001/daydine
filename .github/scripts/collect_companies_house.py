#!/usr/bin/env python3
"""
collect_companies_house.py — Check business viability via Companies House API.

Searches for each restaurant as a registered company, extracting
company status, accounts status, director changes, and insolvency.

3-try matching strategy:
  1. Search by venue name
  2. Strip common suffixes and retry
  3. Search by postcode and fuzzy-match name

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

# Suffixes to strip for fuzzy matching
STRIP_SUFFIXES = re.compile(
    r'\b(ltd|limited|plc|llp|inc|& co|the|restaurant|cafe|bar|pub|bistro|grill)\b',
    re.IGNORECASE,
)


def normalise(name):
    """Normalise a name for comparison."""
    name = name.lower().strip()
    name = re.sub(r"[^\w\s]", "", name)
    return re.sub(r"\s+", " ", name).strip()


def strip_suffixes(name):
    """Strip common business suffixes for looser matching."""
    stripped = STRIP_SUFFIXES.sub("", name)
    stripped = re.sub(r"[^\w\s]", "", stripped)
    return re.sub(r"\s+", " ", stripped).strip().lower()


def fuzzy(a, b):
    """Fuzzy match ratio between two names."""
    return difflib.SequenceMatcher(None, normalise(a), normalise(b)).ratio()


def _api_search(query):
    """Run a Companies House search query. Returns list of result items."""
    params = {"q": query, "items_per_page": 10}
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


def _pick_best(results, venue_name, postcode="", threshold=0.5):
    """Pick the best match from search results. Returns (item, score) or (None, 0)."""
    best = None
    best_score = 0

    for item in results:
        title = item.get("title", "")
        score = fuzzy(venue_name, title)

        # Bonus if postcode area matches
        addr = item.get("address_snippet", "").upper()
        pc_prefix = postcode[:4].strip().upper() if postcode else ""
        if pc_prefix and pc_prefix in addr:
            score += 0.15

        # Bonus for food-related SIC codes in snippet
        snippet = (item.get("snippet") or "").lower()
        if any(word in snippet for word in ["restaurant", "cafe", "food", "catering", "pub"]):
            score += 0.05

        if score > best_score:
            best_score = score
            best = item

    if not best or best_score < threshold:
        return None, 0
    return best, best_score


def search_company(name, postcode=""):
    """3-try matching strategy for Companies House lookup.

    Try 1: Search by venue name directly.
    Try 2: Strip common suffixes from name and retry.
    Try 3: Search by postcode, then fuzzy-match name from results.

    Returns (best_match_item, score) or (None, 0).
    """
    # Try 1: Direct name search
    results = _api_search(name)
    best, score = _pick_best(results, name, postcode)
    if best:
        return best, score
    time.sleep(0.3)

    # Try 2: Strip suffixes and retry
    stripped = strip_suffixes(name)
    if stripped and stripped != normalise(name):
        results = _api_search(stripped)
        # Match using stripped versions of both
        best_item = None
        best_score = 0
        for item in results:
            title = item.get("title", "")
            s = difflib.SequenceMatcher(
                None, stripped, strip_suffixes(title)
            ).ratio()
            addr = item.get("address_snippet", "").upper()
            pc_prefix = postcode[:4].strip().upper() if postcode else ""
            if pc_prefix and pc_prefix in addr:
                s += 0.15
            if s > best_score:
                best_score = s
                best_item = item
        if best_item and best_score >= 0.45:
            return best_item, best_score
        time.sleep(0.3)

    # Try 3: Search by postcode and fuzzy-match name
    if postcode and len(postcode) >= 5:
        results = _api_search(postcode)
        best, score = _pick_best(results, name, postcode, threshold=0.35)
        if best:
            return best, score
        time.sleep(0.3)

    return None, 0


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
    """Search and extract Companies House data for a restaurant.

    Returns a dict with ch_* fields, or None if no match found.
    """
    best, match_score = search_company(name, postcode)
    if not best:
        return None

    company_number = best.get("company_number", "")
    details = get_company_details(company_number) if company_number else None

    entry = {
        "ch_company_number": company_number,
        "ch_company_name": best.get("title", ""),
        "ch_status": best.get("company_status", "unknown"),
        "match_score": round(match_score, 2),
    }

    if details:
        # Incorporation date
        created = details.get("date_of_creation")
        if created:
            entry["ch_incorporated"] = created

        # Accounts
        accounts = details.get("accounts", {})
        next_due = accounts.get("next_due")
        last_made = accounts.get("last_accounts", {}).get("made_up_to")
        if next_due:
            entry["ch_accounts_due"] = next_due
        if last_made:
            entry["ch_last_accounts_filed"] = last_made
        entry["ch_accounts_overdue"] = bool(accounts.get("overdue"))

        # SIC codes
        sic = details.get("sic_codes", [])
        entry["sic_codes"] = sic
        entry["is_food_sic"] = bool(set(sic) & FOOD_SIC_CODES)

        # Insolvency
        entry["ch_insolvency"] = bool(details.get("has_insolvency_history"))

    # Director count and recent changes
    if company_number:
        officers = get_officers(company_number)
        active_directors = [
            o for o in officers
            if o.get("officer_role") in ("director", "corporate-director")
            and not o.get("resigned_on")
        ]
        entry["ch_directors"] = len(active_directors)

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
        # Keep existing successful matches (resume support)
        ch_data = {k: v for k, v in existing.items()
                   if v.get("ch_company_number")}
        print(f"Loaded {len(ch_data)} existing CH records (resuming)")

    matched = 0
    no_match = 0
    total = len(establishments)
    for i, (key, record) in enumerate(establishments.items(), 1):
        if key in ch_data:
            matched += 1
            continue
        name = record.get("n", "")
        postcode = record.get("pc", "")
        if not name:
            ch_data[key] = {"ch_status": "no_match", "_reason": "no_name"}
            continue

        result = process_company(name, postcode)
        time.sleep(0.5)  # Rate limit between venues

        if result:
            ch_data[key] = result
            matched += 1
            status = result.get("ch_status", "?")
            score = result.get("match_score", 0)
            print(f"  [{i}/{total}] {name} -> {result['ch_company_name']} "
                  f"({status}, score={score})")
        else:
            # Genuinely not found after 3 tries
            ch_data[key] = {"ch_status": "no_match"}
            no_match += 1
            print(f"  [{i}/{total}] {name} -> no match")

        # Periodic save
        if i % 25 == 0:
            with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
                json.dump(ch_data, f, indent=2, ensure_ascii=False)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(ch_data, f, indent=2, ensure_ascii=False)

    dissolved = sum(1 for v in ch_data.values()
                    if v.get("ch_status") == "dissolved")
    overdue = sum(1 for v in ch_data.values()
                  if v.get("ch_accounts_overdue"))
    insolvency = sum(1 for v in ch_data.values()
                     if v.get("ch_insolvency"))
    print(f"\nDone. Matched: {matched}/{total}, No match: {no_match}")
    print(f"  Dissolved: {dissolved}, Accounts overdue: {overdue}, "
          f"Insolvency history: {insolvency}")


if __name__ == "__main__":
    main()
