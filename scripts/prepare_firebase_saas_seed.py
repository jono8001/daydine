#!/usr/bin/env python3
"""Prepare a local Firebase Realtime Database seed import for DayDine SaaS.

This helper keeps the committed fixture template safe while producing a local,
gitignored import file with real Firebase Auth UIDs/emails.

Example:
    python scripts/prepare_firebase_saas_seed.py \
      --admin-uid REAL_ADMIN_FIREBASE_UID \
      --admin-email admin@daydine.example \
      --client-uid REAL_CLIENT_FIREBASE_UID \
      --client-email client@example.com

Then import the generated JSON with Firebase CLI, for example:
    firebase database:update / data/firebase_daydine_saas_seed_lambs.import.json --project recursive-research-eu
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "firebase_daydine_saas_seed_lambs.json"
DEFAULT_OUTPUT = ROOT / "data" / "firebase_daydine_saas_seed_lambs.import.json"

ADMIN_PLACEHOLDER = "REPLACE_WITH_FIREBASE_ADMIN_UID"
CLIENT_PLACEHOLDER = "REPLACE_WITH_FIREBASE_CLIENT_UID"
INVALID_RTDB_KEY_CHARS = re.compile(r"[.#$\[\]/]")
EMAILISH = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        fail(f"Input file does not exist: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"Could not parse JSON in {path}: {exc}")


def validate_uid(label: str, value: str) -> str:
    value = (value or "").strip()
    if not value:
        fail(f"{label} UID is required")
    if value in {ADMIN_PLACEHOLDER, CLIENT_PLACEHOLDER} or value.startswith("REPLACE_WITH_"):
        fail(f"{label} UID is still a placeholder")
    if INVALID_RTDB_KEY_CHARS.search(value):
        fail(f"{label} UID contains a character that is invalid in a Realtime Database key: . # $ [ ] /")
    return value


def validate_email(label: str, value: str) -> str:
    value = (value or "").strip()
    if not EMAILISH.match(value):
        fail(f"{label} email does not look valid: {value!r}")
    return value


def assert_template_shape(seed: dict[str, Any]) -> None:
    try:
        users = seed["daydine_saas"]["users"]
    except KeyError:
        fail("Seed must contain daydine_saas/users")
    missing = [key for key in (ADMIN_PLACEHOLDER, CLIENT_PLACEHOLDER) if key not in users]
    if missing:
        fail("Seed template does not contain expected placeholder user key(s): " + ", ".join(missing))


def prepare_seed(args: argparse.Namespace) -> dict[str, Any]:
    seed = load_json(args.input)
    assert_template_shape(seed)
    prepared = deepcopy(seed)
    root = prepared["daydine_saas"]
    users = root["users"]

    admin_uid = validate_uid("Admin", args.admin_uid)
    client_uid = validate_uid("Client", args.client_uid)
    if admin_uid == client_uid:
        fail("Admin UID and client UID must be different")

    admin_email = validate_email("Admin", args.admin_email)
    client_email = validate_email("Client", args.client_email)
    prepared_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    admin_profile = users.pop(ADMIN_PLACEHOLDER)
    client_profile = users.pop(CLIENT_PLACEHOLDER)

    admin_profile.update(
        {
            "email": admin_email,
            "displayName": args.admin_display_name,
            "role": "admin",
            "active": True,
            "seedPreparedAt": prepared_at,
        }
    )
    admin_profile.pop("setupNote", None)

    client_profile.update(
        {
            "email": client_email,
            "displayName": args.client_display_name,
            "role": "client",
            "clientId": args.client_id,
            "active": True,
            "seedPreparedAt": prepared_at,
        }
    )
    client_profile.pop("setupNote", None)

    users[admin_uid] = admin_profile
    users[client_uid] = client_profile

    client_record = root.get("clients", {}).get(args.client_id)
    if client_record:
        client_record["primaryContactEmail"] = client_email
        client_record["seedPreparedAt"] = prepared_at

    if args.clear_example_emails:
        for profile in users.values():
            if profile.get("email") in {"admin@example.com", "client@example.com"}:
                fail("Example email remained in prepared users unexpectedly")

    return prepared


def main() -> None:
    parser = argparse.ArgumentParser(description="Replace Firebase Auth UID placeholders in the DayDine SaaS seed template.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Committed seed template to read")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Local import JSON to write")
    parser.add_argument("--admin-uid", required=True, help="Firebase Auth UID for the admin user")
    parser.add_argument("--admin-email", required=True, help="Email for the admin user profile")
    parser.add_argument("--admin-display-name", default="DayDine Admin", help="Display name for the admin profile")
    parser.add_argument("--client-uid", required=True, help="Firebase Auth UID for the test client user")
    parser.add_argument("--client-email", required=True, help="Email for the test client profile")
    parser.add_argument("--client-display-name", default="Lambs Client Fixture", help="Display name for the client profile")
    parser.add_argument("--client-id", default="lambs", help="Client ID to update in the seed")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite output file if it already exists")
    parser.add_argument("--clear-example-emails", action="store_true", help="Fail if example emails remain in prepared user profiles")
    args = parser.parse_args()

    output = args.output.resolve()
    if output.exists() and not args.overwrite:
        fail(f"Output already exists: {output}. Pass --overwrite to replace it.")

    prepared = prepare_seed(args)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(prepared, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    rel_output = output.relative_to(ROOT) if output.is_relative_to(ROOT) else output
    print(f"Wrote prepared Firebase import seed: {rel_output}")
    print("Next commands:")
    print("  firebase use recursive-research-eu")
    print(f"  firebase database:update / {rel_output} --project recursive-research-eu")
    print("  firebase deploy --only database --project recursive-research-eu")


if __name__ == "__main__":
    main()
