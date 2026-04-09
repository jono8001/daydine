#!/usr/bin/env python3
"""
collect_event_data.py — Fetch upcoming events and demand signals.
Populates data/events/ with bank holidays, school terms, and local events.
"""
import json, os, requests
from datetime import datetime, date, timedelta
from pathlib import Path

EVENTS_DIR = Path("data/events")
EVENTS_DIR.mkdir(parents=True, exist_ok=True)

# --- Bank Holidays (free gov.uk API) ---
def fetch_bank_holidays():
    url = "https://www.gov.uk/bank-holidays.json"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        england = data.get("england-and-wales", {}).get("events", [])
        # Filter to next 90 days
        today = date.today()
        cutoff = today + timedelta(days=90)
        upcoming = [
            e for e in england
            if today <= date.fromisoformat(e["date"]) <= cutoff
        ]
        out = {"fetched_at": datetime.utcnow().isoformat(), "bank_holidays": upcoming}
        (EVENTS_DIR / "bank_holidays.json").write_text(json.dumps(out, indent=2))
        print(f"[bank holidays] {len(upcoming)} upcoming fetched")
    except Exception as e:
        print(f"[bank holidays] FAILED: {e}")

# --- RSC Programme (static for now, update quarterly) ---
def write_rsc_static():
    """Static RSC programme for Stratford-upon-Avon Spring/Summer 2026.
    Update this quarterly or replace with a Playwright scraper.
    """
    programme = {
        "venue": "Royal Shakespeare Theatre, Stratford-upon-Avon",
        "fetched_at": datetime.utcnow().isoformat(),
        "source": "static_2026_spring",
        "shows": [
            {"title": "Hamlet", "opens": "2026-04-15", "closes": "2026-08-01", "type": "main_stage"},
            {"title": "The Merry Wives of Windsor", "opens": "2026-05-01", "closes": "2026-07-15", "type": "main_stage"},
            {"title": "A Midsummer Night's Dream", "opens": "2026-06-10", "closes": "2026-09-01", "type": "other_place"},
        ],
        "notes": "Matinees typically Wednesdays and Saturdays. Evening performances typically 7:30pm. Pre-theatre dining demand peaks 5:30-7pm."
    }
    (EVENTS_DIR / "rsc_programme.json").write_text(json.dumps(programme, indent=2))
    print("[RSC] Static programme written")

# --- School Terms (Warwickshire, static) ---
def write_school_terms():
    terms = {
        "authority": "Warwickshire",
        "fetched_at": datetime.utcnow().isoformat(),
        "source": "static_2026",
        "periods": [
            {"name": "Easter holidays", "start": "2026-04-04", "end": "2026-04-19", "type": "holiday"},
            {"name": "Summer term", "start": "2026-04-20", "end": "2026-05-22", "type": "term"},
            {"name": "May half-term", "start": "2026-05-23", "end": "2026-06-01", "type": "holiday"},
            {"name": "Summer term 2", "start": "2026-06-02", "end": "2026-07-17", "type": "term"},
            {"name": "Summer holidays", "start": "2026-07-18", "end": "2026-09-02", "type": "holiday"},
        ]
    }
    (EVENTS_DIR / "school_terms.json").write_text(json.dumps(terms, indent=2))
    print("[school terms] Static terms written")

if __name__ == "__main__":
    fetch_bank_holidays()
    write_rsc_static()
    write_school_terms()
    print("Event data collection complete.")
