#!/usr/bin/env python3
"""Build an importable Firebase Realtime Database seed for the first DayDine SaaS fixture.

This intentionally reuses the existing report-aligned Lambs dashboard snapshot instead
of duplicating or rebuilding dashboard content. The output is a root-level JSON import
that can be imported into the recursive-research-eu Realtime Database.

Usage:
    python scripts/build_firebase_saas_seed.py

Then import data/firebase_daydine_saas_seed_lambs.json into Realtime Database, or merge
its daydine_saas object into the existing database.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAMB_SNAPSHOT = ROOT / "assets" / "operator-dashboards" / "lambs" / "latest.json"
OUT = ROOT / "data" / "firebase_daydine_saas_seed_lambs.json"

ADMIN_UID = "REPLACE_WITH_FIREBASE_ADMIN_UID"
CLIENT_UID = "REPLACE_WITH_FIREBASE_CLIENT_UID"


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_seed() -> dict:
    snapshot = load_json(LAMB_SNAPSHOT)
    now = datetime.now(timezone.utc).isoformat()
    venue_id = snapshot.get("venue_slug", "lambs")
    client_id = "lambs"
    month = snapshot.get("month", "2026-04")

    venue = {
        "publicName": snapshot.get("venue", "Lambs"),
        "canonicalName": snapshot.get("venue", "Lambs"),
        "marketSlug": snapshot.get("market_slug", "stratford-upon-avon"),
        "marketName": snapshot.get("market", "Stratford-upon-Avon"),
        "category": snapshot.get("category", "Restaurant (General)"),
        "fhrsid": snapshot.get("evidence", {}).get("fhrsid"),
        "googlePlaceId": snapshot.get("evidence", {}).get("google_place_id"),
        "entityResolutionStatus": snapshot.get("scores", {}).get("entity_match", "confirmed"),
        "entityResolutionConfidence": "high",
        "evidenceConfidence": snapshot.get("scores", {}).get("confidence_class", "Rankable-B"),
        "daydineSignal": "Protected dashboard fixture",
        "latestSnapshotMonth": month,
        "status": snapshot.get("status", "ready"),
        "createdAt": now,
        "seedSource": "assets/operator-dashboards/lambs/latest.json",
    }

    seed = {
        "daydine_saas": {
            "users": {
                ADMIN_UID: {
                    "email": "admin@example.com",
                    "displayName": "DayDine Admin",
                    "role": "admin",
                    "active": True,
                    "createdAt": now,
                    "setupNote": "Replace this UID and email with the Firebase Auth UID/email for the real admin user before importing.",
                },
                CLIENT_UID: {
                    "email": "client@example.com",
                    "displayName": "Lambs Client Fixture",
                    "role": "client",
                    "clientId": client_id,
                    "venueIds": {venue_id: True},
                    "active": True,
                    "createdAt": now,
                    "setupNote": "Replace this UID and email with the Firebase Auth UID/email for the real client user before importing.",
                },
            },
            "clients": {
                client_id: {
                    "name": "Lambs",
                    "billingStatus": "trial",
                    "plan": "pilot",
                    "primaryContactEmail": "client@example.com",
                    "createdAt": now,
                    "notes": "First protected dashboard fixture. Used to prove generic client portal access control and dashboard rendering.",
                }
            },
            "venues": {venue_id: venue},
            "clientVenueAccess": {
                f"{client_id}_{venue_id}": {
                    "clientId": client_id,
                    "venueId": venue_id,
                    "accessLevel": "owner",
                    "active": True,
                    "createdAt": now,
                }
            },
            "operatorDashboards": {
                venue_id: {
                    "snapshots": {
                        month: snapshot
                    }
                }
            },
        }
    }
    return seed


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    seed = build_seed()
    OUT.write_text(json.dumps(seed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}")
    print("Before importing, replace REPLACE_WITH_FIREBASE_ADMIN_UID and REPLACE_WITH_FIREBASE_CLIENT_UID with real Firebase Auth UIDs.")


if __name__ == "__main__":
    main()
