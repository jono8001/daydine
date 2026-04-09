"""Event & Demand Forecast section builder."""

import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path

EVENTS_DIR = Path("data/events")

# Stratford-upon-Avon postcodes
STRATFORD_POSTCODES = {"CV37"}

# Month names for seasonal fallback
MONTH_SEASONS = {
    1: "January \u2014 post-Christmas quiet period.",
    2: "February \u2014 low season. Valentine\u2019s Day can spike covers mid-month.",
    3: "March \u2014 shoulder season. Mothering Sunday is a peak day.",
    4: "April \u2014 shoulder season. Easter tourism, lighter trade mid-month.",
    5: "May \u2014 bank holiday weekends drive footfall. Half-term towards end of month.",
    6: "June \u2014 summer season building. Father\u2019s Day mid-month.",
    7: "July \u2014 peak summer. School holidays from mid-month.",
    8: "August \u2014 peak summer and school holidays throughout.",
    9: "September \u2014 shoulder season. Back-to-school dip then recovery.",
    10: "October \u2014 half-term mid-month. Halloween end of month.",
    11: "November \u2014 quieter period. Bonfire Night early, Christmas bookings start.",
    12: "December \u2014 Christmas party season peaks weeks 2\u20133. Quiet 26\u201331 Dec.",
}


def _load_json(filename):
    """Load a JSON file from the events directory, or return None."""
    path = EVENTS_DIR / filename
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, IOError):
        return None


def _is_stratford(venue_rec):
    """Check if a venue is in a Stratford-upon-Avon postcode."""
    pc = (venue_rec or {}).get("pc", "")
    prefix = pc[:4].strip().upper() if pc else ""
    return prefix in STRATFORD_POSTCODES


def _parse_date(s):
    """Parse a date string (YYYY-MM-DD) to a date object."""
    try:
        return date.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def _date_range_overlaps(start1, end1, start2, end2):
    """Check if two date ranges overlap."""
    return start1 <= end2 and start2 <= end1


def _format_date_range(start, end):
    """Format a date range for display (e.g. '15-20 Apr')."""
    if start.month == end.month:
        return f"{start.day}\u2013{end.day} {start.strftime('%b')}"
    return f"{start.day} {start.strftime('%b')}\u2013{end.day} {end.strftime('%b')}"


def _build_events(venue_rec, report_start, report_end):
    """Build list of demand events for the forecast window.

    Returns list of dicts with keys:
      start, end, signal, driver, action, segments
    """
    events = []
    is_stratford = _is_stratford(venue_rec)

    # --- Bank Holidays ---
    bh_data = _load_json("bank_holidays.json")
    if bh_data:
        for bh in bh_data.get("bank_holidays", []):
            bh_date = _parse_date(bh.get("date"))
            if not bh_date:
                continue
            # Bank holiday weekend: Friday before to Monday
            # Check if it falls in our window
            bh_start = bh_date - timedelta(days=bh_date.weekday())  # Monday of that week
            # For Good Friday / Easter Monday, create a long weekend
            bh_weekend_start = bh_date - timedelta(days=max(0, bh_date.weekday() - 4))
            bh_weekend_end = bh_date + timedelta(days=max(0, 7 - bh_date.weekday() - 1))
            # Simplify: treat as a 3-4 day peak around the holiday
            evt_start = bh_date - timedelta(days=1) if bh_date.weekday() > 0 else bh_date
            evt_end = bh_date + timedelta(days=1) if bh_date.weekday() < 6 else bh_date

            if not _date_range_overlaps(evt_start, evt_end, report_start, report_end):
                continue

            title = bh.get("title", "Bank Holiday")
            events.append({
                "start": max(evt_start, report_start),
                "end": min(evt_end, report_end),
                "signal": "PEAK",
                "driver": f"Bank holiday: {title}",
                "action": f"Ensure full opening hours are correct on Google for {title}",
                "segments": ["Tourists & Visitors", "Locals"],
            })

    # --- RSC Programme (Stratford only) ---
    if is_stratford:
        rsc_data = _load_json("rsc_programme.json")
        if rsc_data:
            for show in rsc_data.get("shows", []):
                opens = _parse_date(show.get("opens"))
                closes = _parse_date(show.get("closes"))
                title = show.get("title", "RSC Show")
                if not opens or not closes:
                    continue

                # Opening week is PEAK
                opening_end = opens + timedelta(days=6)
                if _date_range_overlaps(opens, opening_end, report_start, report_end):
                    evt_start = max(opens, report_start)
                    evt_end = min(opening_end, report_end)
                    events.append({
                        "start": evt_start,
                        "end": evt_end,
                        "signal": "PEAK",
                        "driver": f"RSC: {title} opens",
                        "action": f"Confirm pre-theatre menu is live on Google before {opens.strftime('%d %b')}",
                        "segments": ["Theatre-Goers"],
                    })

                # Ongoing run is HIGH (only if not already covered by opening)
                run_start = opening_end + timedelta(days=1)
                if _date_range_overlaps(run_start, closes, report_start, report_end):
                    evt_start = max(run_start, report_start)
                    evt_end = min(closes, report_end)
                    # Don't duplicate if opening week already covers the whole window
                    if evt_start <= evt_end and evt_start > (opens + timedelta(days=6)):
                        events.append({
                            "start": evt_start,
                            "end": evt_end,
                            "signal": "HIGH",
                            "driver": f"RSC: {title} in performance",
                            "action": "Pre-theatre covers likely elevated \u2014 staff accordingly for 5:30\u20137pm service",
                            "segments": ["Theatre-Goers"],
                        })

    # --- School Terms / Holidays ---
    terms_data = _load_json("school_terms.json")
    if terms_data:
        for period in terms_data.get("periods", []):
            p_start = _parse_date(period.get("start"))
            p_end = _parse_date(period.get("end"))
            p_type = period.get("type", "")
            p_name = period.get("name", "")
            if not p_start or not p_end:
                continue
            if not _date_range_overlaps(p_start, p_end, report_start, report_end):
                continue

            evt_start = max(p_start, report_start)
            evt_end = min(p_end, report_end)

            if p_type == "holiday":
                events.append({
                    "start": evt_start,
                    "end": evt_end,
                    "signal": "HIGH",
                    "driver": f"School: {p_name}",
                    "action": "Family-friendly offer visible \u2014 check kids menu and highchair mention on Google",
                    "segments": ["Family Diners"],
                })
            elif p_type == "term":
                events.append({
                    "start": evt_start,
                    "end": evt_end,
                    "signal": "STEADY",
                    "driver": f"School: {p_name} (term time)",
                    "action": "\u2014",
                    "segments": [],
                })

    # Sort by start date
    events.sort(key=lambda e: e["start"])

    # Fill gaps with QUIET periods
    filled = []
    cursor = report_start
    for evt in events:
        if evt["start"] > cursor + timedelta(days=1):
            gap_end = evt["start"] - timedelta(days=1)
            filled.append({
                "start": cursor,
                "end": gap_end,
                "signal": "QUIET",
                "driver": "Standard trade \u2014 no major demand drivers",
                "action": "Good time for staff briefings, deep cleaning, or menu updates",
                "segments": [],
            })
        filled.append(evt)
        cursor = max(cursor, evt["end"] + timedelta(days=1))

    if cursor <= report_end:
        filled.append({
            "start": cursor,
            "end": report_end,
            "signal": "QUIET",
            "driver": "Standard trade \u2014 no major demand drivers",
            "action": "Good time for staff briefings, deep cleaning, or menu updates",
            "segments": [],
        })

    return filled


def _find_biggest_opportunity(events, venue_rec):
    """Identify the single biggest opportunity from the event list."""
    peak_events = [e for e in events if e["signal"] == "PEAK"]
    if not peak_events:
        peak_events = [e for e in events if e["signal"] == "HIGH"]
    if not peak_events:
        return None

    # Pick the first PEAK event
    evt = peak_events[0]
    period = _format_date_range(evt["start"], evt["end"])
    segments = ", ".join(evt["segments"]) if evt["segments"] else "all guest types"

    return (
        f"{evt['driver']} ({period}) is your biggest demand opportunity this month. "
        f"Your {segments} segment converts on atmosphere and food quality \u2014 "
        f"ensure your Google photos and menu are updated before the period starts."
    )


def build_event_forecast(w, venue_rec, month_str):
    """Build the Next 30 Days \u2014 Demand Forecast section.

    Args:
        w: line appender function
        venue_rec: venue record dict
        month_str: report month as 'YYYY-MM'
    """
    venue_rec = venue_rec or {}

    # Parse report window
    try:
        report_start = date(int(month_str[:4]), int(month_str[5:7]), 1)
    except (ValueError, IndexError):
        report_start = date.today().replace(day=1)
    report_end = report_start + timedelta(days=29)

    # Check if we have any event data at all
    has_data = any(
        (EVENTS_DIR / f).exists()
        for f in ["bank_holidays.json", "rsc_programme.json", "school_terms.json"]
    )

    if not has_data:
        # Graceful fallback
        month_num = report_start.month
        season_note = MONTH_SEASONS.get(month_num, "")
        w("## Seasonal Context & Upcoming Demand\n")
        w(f"**{season_note}**\n")
        w("*Detailed event forecasting will populate once event data has been "
          "collected for your area.*\n")
        return

    # Build events
    events = _build_events(venue_rec, report_start, report_end)

    if not events:
        month_num = report_start.month
        season_note = MONTH_SEASONS.get(month_num, "")
        w("## Next 30 Days \u2014 Demand Forecast\n")
        w(f"**{season_note}** No specific demand events identified for this period.\n")
        return

    signal_icons = {
        "PEAK": "\U0001f534 PEAK",
        "HIGH": "\U0001f7e1 HIGH",
        "STEADY": "\U0001f7e2 STEADY",
        "QUIET": "\u26aa QUIET",
    }

    w("## Next 30 Days \u2014 Demand Forecast\n")

    w("| Period | Signal | Driver | Recommended Action |")
    w("|---|---|---|---|")
    for evt in events:
        period = _format_date_range(evt["start"], evt["end"])
        signal = signal_icons.get(evt["signal"], evt["signal"])
        w(f"| {period} | {signal} | {evt['driver']} | {evt['action']} |")
    w("")

    # Biggest opportunity callout
    opportunity = _find_biggest_opportunity(events, venue_rec)
    if opportunity:
        w(f"**Biggest opportunity this month:** {opportunity}\n")
