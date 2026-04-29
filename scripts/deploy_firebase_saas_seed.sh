#!/usr/bin/env bash
# Deploy DayDine Realtime Database rules and merge the protected SaaS seed.
#
# This script deliberately avoids storing live Firebase Auth UIDs in the repo.
# Pass UIDs/emails through environment variables when running locally.
#
# Required env vars:
#   DAYDINE_ADMIN_UID
#   DAYDINE_ADMIN_EMAIL
#   DAYDINE_CLIENT_UID
#   DAYDINE_CLIENT_EMAIL
#
# Usage:
#   DAYDINE_ADMIN_UID="..." \
#   DAYDINE_ADMIN_EMAIL="admin@example.com" \
#   DAYDINE_CLIENT_UID="..." \
#   DAYDINE_CLIENT_EMAIL="client@example.com" \
#   bash scripts/deploy_firebase_saas_seed.sh

set -euo pipefail

PROJECT_ID="${FIREBASE_PROJECT_ID:-recursive-research-eu}"
OUT_DIR="${DAYDINE_FIREBASE_TMP_DIR:-tmp}"
OUT_FILE="$OUT_DIR/daydine_saas_seed_lambs.json"

require_env() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "ERROR: Missing required environment variable: $name" >&2
    exit 1
  fi
}

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERROR: Missing required command: $cmd" >&2
    echo "Install it first, then rerun this script." >&2
    exit 1
  fi
}

require_env DAYDINE_ADMIN_UID
require_env DAYDINE_ADMIN_EMAIL
require_env DAYDINE_CLIENT_UID
require_env DAYDINE_CLIENT_EMAIL
require_cmd python
require_cmd firebase

mkdir -p "$OUT_DIR"

python scripts/build_firebase_saas_seed.py \
  --admin-uid "$DAYDINE_ADMIN_UID" \
  --admin-email "$DAYDINE_ADMIN_EMAIL" \
  --client-uid "$DAYDINE_CLIENT_UID" \
  --client-email "$DAYDINE_CLIENT_EMAIL" \
  --strict \
  --saas-only \
  --out "$OUT_FILE"

echo "Deploying Realtime Database rules to $PROJECT_ID..."
firebase use "$PROJECT_ID"
firebase deploy --only database --project "$PROJECT_ID"

echo "Merging SaaS seed into /daydine_saas on $PROJECT_ID..."
firebase database:update /daydine_saas "$OUT_FILE" --project "$PROJECT_ID"

echo "Done. QA these routes after deploy/import:"
echo "  /login"
echo "  /client"
echo "  /client/venues/lambs"
echo "  /admin"
echo "  /admin/reports"
echo "  /admin/markets"
