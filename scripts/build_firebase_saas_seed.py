#!/usr/bin/env python3
"""Build an importable Firebase Realtime Database seed for DayDine SaaS fixtures.

This intentionally reuses the existing report-aligned Lambs dashboard snapshot instead
of duplicating or rebuilding dashboard content. The default output is a root-level JSON
import that contains the `daydine_saas` object used by the recursive-research-eu
Realtime Database.

Default usage keeps placeholder UIDs for local/template generation:

    python scripts/build_firebase_saas_seed.py

Production/deploy usage must pass real Firebase Auth UIDs and strict validation:

    python scripts/build_firebase_saas_seed.py \
      --admin-uid "$ADMIN_UID" \
      --admin-email "admin@daydine.example" \
      --client-uid "$CLIENT_UID" \
      --client-email "client@example.com" \
      --strict \
      --out /tmp/daydine_saas_seed_lambs.json

Then merge the generated `daydine_saas` object into Realtime Database. Do not import
placeholder UIDs into the live database.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LAMB_SNAPSHOT = ROOT / "assets" / "operator-dashboards" / "lambs" / "latest.json"
OUT = ROOT / "data" / "firebase_daydine_saas_seed_lambs.json"

ADMIN_UID_PLACEHOLDER = "REPLACE_WITH_FIREBASE_ADMIN_UID"
CLIENT_UID_PLACEHOLDER = "REPLACE_WITH_FIREBASE_CLIENT_UID"


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_seed(
    *,
    admin_uid: str,
    admin_email: str,
    admin_name: str,
    client_uid: str,
    client_email: str,
    client_name: str,
    now: str,
) -> dict[str, Any]:
    snapshot = load_json(LAMB_SNAPSHOT)
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
                admin_uid: {
                    "email": admin_email,
                    "displayName": admin_name,
                    "role": "admin",
                    "active": True,
                    "createdAt": now,
                    "setupNote": "Firebase Auth admin user mapped to DayDine SaaS admin role.",
                },
                client_uid: {
                    "email": client_email,
                    "displayName": client_name,
                    "role": "client",
                    "clientId": client_id,
                    "venueIds": {venue_id: True},
                    "active": True,
                    "createdAt": now,
                    "setupNote": "Firebase Auth client user mapped to the first protected client-dashboard fixture.",
                },
            },
            "clients": {
                client_id: {
                    "name": "Lambs",
                    "billingStatus": "trial",
                    "plan": "pilot",
                    "primaryContactEmail": client_email,
                    "createdAt": now,
                    "notes": "First protected client-dashboard fixture. Used to prove generic client portal access control and dashboard rendering.",
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
            "operatorDashboards": {venue_id: {"snapshots": {month: snapshot}}},
        }
    }
    return seed


def walk_values(value: Any):
    if isinstance(value, dict):
        for child in value.values():
            yield from walk_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_values(child)
    else:
        yield value


def validate_seed(seed: dict[str, Any], *, strict: bool) -> list[str]:
    errors: list[str] = []
    root = seed.get("daydine_saas")
    if not isinstance(root, dict):
        errors.append("Missing root key: daydine_saas")
        return errors

    users = root.get("users") or {}
    venues = root.get("venues") or {}
    dashboards = root.get("operatorDashboards") or {}
    access = root.get("clientVenueAccess") or {}

    admin_users = [uid for uid, row in users.items() if isinstance(row, dict) and row.get("role") == "admin"]
    client_users = [uid for uid, row in users.items() if isinstance(row, dict) and row.get("role") == "client"]
    if not admin_users:
        errors.append("Seed must include at least one admin user profile.")
    if not client_users:
        errors.append("Seed must include at least one client user profile.")
    if "lambs" not in venues:
        errors.append("Seed must include venues/lambs.")
    if "lambs_lambs" not in access:
        errors.append("Seed must include clientVenueAccess/lambs_lambs.")
    if not (((dashboards.get("lambs") or {}).get("snapshots") or {}).get("2026-04")):
        errors.append("Seed must include operatorDashboards/lambs/snapshots/2026-04.")

    if strict:
        uid_values = set(users.keys())
        if ADMIN_UID_PLACEHOLDER in uid_values or CLIENT_UID_PLACEHOLDER in uid_values:
            errors.append("Strict mode forbids placeholder Firebase Auth UIDs.")
        for value in walk_values(seed):
            if isinstance(value, str) and value.startswith("REPLACE_WITH_FIREBASE_"):
                errors.append(f"Strict mode forbids placeholder value: {value}")
                break

    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an importable DayDine SaaS Realtime Database seed.")
    parser.add_argument("--admin-uid", default=ADMIN_UID_PLACEHOLDER, help="Firebase Auth UID for the DayDine admin user")
    parser.add_argument("--admin-email", default="admin@example.com", help="Email for the admin profile")
    parser.add_argument("--admin-name", default="DayDine Admin", help="Display name for the admin profile")
    parser.add_argument("--client-uid", default=CLIENT_UID_PLACEHOLDER, help="Firebase Auth UID for the test/client user")
    parser.add_argument("--client-email", default="client@example.com", help="Email for the client profile")
    parser.add_argument("--client-name", default="Lambs Client Fixture", help="Display name for the client profile")
    parser.add_argument("--out", default=str(OUT), help="Output JSON path")
    parser.add_argument("--saas-only", action="store_true", help="Write only the daydine_saas object rather than a root-level import object")
    parser.add_argument("--strict", action="store_true", help="Fail if placeholder Firebase Auth UIDs remain")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    seed = build_seed(
        admin_uid=args.admin_uid,
        admin_email=args.admin_email,
        admin_name=args.admin_name,
        client_uid=args.client_uid,
        client_email=args.client_email,
        client_name=args.client_name,
        now=utc_now(),
    )
    errors = validate_seed(seed, strict=args.strict)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)

    out_path = Path(args.out)
    output = seed["daydine_saas"] if args.saas_only else seed
    write_json(out_path, output)
    print(f"Wrote {out_path}")
    if not args.strict:
        print("Template mode: before live import, rerun with --strict and real Firebase Auth UIDs.")
    else:
        print("Strict validation passed: no placeholder Firebase Auth UIDs remain.")


if __name__ == "__main__":
    main()
