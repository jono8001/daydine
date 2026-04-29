# DayDine Current State and Next Actions

**Status:** Active handover file  
**Last updated:** 29 April 2026  
**Purpose:** Preserve DayDine context between long AI/coding sessions. The repo is the project memory; update this file before ending a major session.

---

## 1. Strategic direction

DayDine is being built as a professional UK hospitality intelligence SaaS with:

- a public ranking/search/methodology site for diners;
- Firebase-authenticated client dashboards for operators;
- Firebase-authenticated admin tooling for internal market, report, pipeline and QA workflows;
- low-cost monthly batch refreshes rather than live paid API calls on page views;
- V5 DayDine Evidence Rank as the next methodology destination, built beside V4 before any cutover.

Core positioning remains:

> DayDine must not compete with Tripadvisor by pretending to have more review data. DayDine should compete as a proprietary hospitality intelligence platform that includes authorised review evidence, separates popularity from quality, and identifies Proven Leaders, Hidden Gems, Rising Venues and Overexposed venues across the whole local market.

Allowed public wording: authorised public review evidence, including Google rating and Google review volume.  
Avoid: claiming Tripadvisor/OpenTable ingestion, full cross-web review coverage, objective restaurant-quality judgement, exact public formula or exact weights.

---

## 2. Architecture and Firebase decision

Accepted model:

```text
Public rankings/search/methodology = public, fast, generated/cacheable
Client dashboards/admin tools = Firebase Auth + database rules
Monthly data refresh = batch/cached, not live API calls per user page view
```

Current hosting approach: **hybrid first**. Keep the public static site on Vercel temporarily; use Firebase Auth/database for client/admin.

Correct Firebase project:

```text
recursive-research-eu
```

Do **not** use `recursive-research-agent` for current DayDine SaaS/Auth work unless a deliberate migration decision is made. `recursive-research-eu` was confirmed from the existing public UK/FSA establishment lookup in `uk-establishments.html`.

Private SaaS data root:

```text
daydine_saas
```

Existing public FHRS/FSA lookup root remains:

```text
daydine/establishments
```

---

## 3. Current technical state

### Firebase/Auth foundation

Protected SaaS routes have been committed:

```text
/login
/client
/client/venues/:venue
/admin
/admin/reports
/admin/markets
```

Key files:

```text
assets/daydine-firebase.js
assets/daydine-auth.js
login.html
client.html
client-venue.html
admin.html
admin-reports-protected.html
admin-markets-protected.html
database.rules.json
firebase.json
.firebaserc
vercel.json
```

Firebase config is centralised in `assets/daydine-firebase.js`. Auth/profile/access helpers are centralised in `assets/daydine-auth.js`.

Repo configuration points to:

```text
recursive-research-eu
recursive-research-eu-default-rtdb.europe-west1.firebasedatabase.app
```

Rules/config are committed but still need deploying to `recursive-research-eu` from an authenticated local Firebase CLI or authorised deploy environment.

### Live Firebase status verified by user on 29 April 2026

```text
Project: recursive-research-eu
Realtime Database instance: recursive-research-eu-default-rtdb, europe-west1
Email/password auth: enabled
Admin Firebase Auth user: created and verified outside repo
Client Firebase Auth user: created and verified outside repo
Current live top-level DB nodes: daydine, evidtrace
Current live DB does not yet have daydine_saas
```

Important decision: **do not commit live Firebase UIDs or live account emails to the public repo.** Generate the live seed locally with CLI args/environment variables only.

`evidtrace` is a separate concern and not part of DayDine. The DayDine rules file does not include an `evidtrace` rule. The current accepted decision is to disregard it and allow it to be locked out by the DayDine rules deploy unless a future separate decision says otherwise.

### Protected client-dashboard framework

A generic protected dashboard renderer exists in:

```text
client.html
client-venue.html
```

Target model:

```text
daydine_saas/users/{uid}
daydine_saas/clients/{clientId}
daydine_saas/venues/{venueId}
daydine_saas/clientVenueAccess/{clientId}_{venueId}
daydine_saas/operatorDashboards/{venueId}/snapshots/{month}
```

Lambs is only the first fixture, not the strategic product focus.

Seed assets:

```text
data/firebase_daydine_saas_seed_lambs.json
scripts/build_firebase_saas_seed.py
scripts/deploy_firebase_saas_seed.sh
```

`data/firebase_daydine_saas_seed_lambs.json` remains a template/reference seed and should not be edited with live UIDs/emails. Live import should be generated locally with:

```bash
python3 scripts/build_firebase_saas_seed.py \
  --admin-uid "<admin Firebase Auth UID>" \
  --admin-email "<admin email>" \
  --client-uid "<client Firebase Auth UID>" \
  --client-email "<client email>" \
  --strict \
  --saas-only \
  --out tmp/daydine_saas_seed_lambs.json
```

### Protected admin modules

Protected admin shells now exist for `/admin`, `/admin/reports` and `/admin/markets`. Older static files remain as legacy/prototype references only:

```text
admin-reports.html
admin-markets.html
operator-dashboard.html
assets/operator-dashboards/*
```

### Vercel routes

`vercel.json` routes protected pages to the new shells. Legacy operator links redirect:

```text
/operator/:venue -> /client/venues/:venue
```

### Coverage certificates

Coverage certificate assets exist:

```text
assets/coverage/stratford-upon-avon.json
assets/coverage/leamington-spa.json
assets/coverage/index.json
scripts/build_coverage_certificates.py
```

Current summaries:

```text
Stratford-upon-Avon: 209 establishments reviewed, 204 candidate/scored dining venues, 170 rankable venues, 30 public ranking venues, 0 active known-missing venues, 6 ambiguous Google Place groups.

Leamington Spa: 292 establishments reviewed, 287 candidate/scored dining venues, 252 rankable venues, 30 public ranking venues, 0 active known-missing venues, 7 ambiguous Google Place groups.
```

Both markets remain `warning`, not `ready`, because ambiguous Google Place groups still need admin review.

### V5 prototype outputs

V5 prototype builder and workflow exist:

```text
scripts/build_v5_evidence_rank.py
.github/workflows/v5_evidence_rank.yml
```

V5 outputs have now been generated and committed under:

```text
assets/v5/index.json
assets/v5/stratford-upon-avon.json
assets/v5/leamington-spa.json
```

Current `assets/v5/index.json` summary:

```text
Generated: 2026-04-29T16:29:09Z
Status: experimental
Markets: 2
Stratford-upon-Avon: 70 V5 records
Leamington Spa: 117 V5 records
```

V5 remains experimental and must not be publicly cut over until QA and public methodology copy are reviewed.

---

## 4. Prior assets handled in the build phase

Reused:

```text
uk-establishments.html Firebase config
assets/operator-dashboards/lambs/latest.json
assets/operator-dashboards/manifest.json
operator-dashboard.html dashboard structure
admin-reports.html report-library concept
admin-markets.html market-readiness concept
assets/market-readiness/*.json
assets/rankings/*.json
assets/coverage/*.json
V4 score files
scripts/build_coverage_certificates.py
scripts/build_v5_evidence_rank.py
```

Migrated:

```text
Lambs dashboard fixture -> Firebase seed shape
Static admin/report concepts -> protected admin modules
Static operator-dashboard concept -> protected generic client dashboard
Readiness counts -> coverage certificate assets
V4/ranking/coverage inputs -> V5 experimental assets
```

Refactored:

```text
Firebase setup -> shared daydine-firebase.js
Auth and role logic -> shared daydine-auth.js
Vercel routes -> protected client/admin routes
Coverage generation -> repeatable script
V5 prototype -> repeatable script + workflow
Firebase seed generation -> deployment-safe strict builder with local UID args
```

Archived/retained as legacy reference:

```text
operator-dashboard.html
admin-reports.html
admin-markets.html
assets/operator-dashboards/*
```

Retired: nothing deleted or retired yet.

---

## 5. Latest session update — 29 April 2026 Firebase/V5 operational handover

### What changed in this session

- Re-read the required control docs and continued from the existing DayDine build phase rather than restarting strategy.
- Confirmed that the correct Firebase project remains `recursive-research-eu` and the SaaS private root remains `daydine_saas`.
- Confirmed the user created and verified one admin Firebase Auth user and one test client Firebase Auth user outside the repo.
- Confirmed live Realtime Database currently has `daydine` and `evidtrace`, but no `daydine_saas`; therefore the SaaS import will be additive if targeted correctly.
- Confirmed current live Firebase rules are loose, while repo `database.rules.json` is the locked-down DayDine ruleset to deploy.
- Confirmed V5 Evidence Rank prototype outputs were generated and committed to `assets/v5/`.
- Confirmed Vercel status check on the V5 output commit was green.
- Established that live Firebase UIDs/emails should not be committed to the public repo; the seed should be generated locally with CLI args and `--strict --saas-only`.
- Provided the exact local Firebase CLI sequence for generating the live seed, deploying rules, merging `/daydine_saas`, and verifying Firebase paths.
- Did **not** deploy Firebase rules or import live Firebase data from ChatGPT, because this chat has no authenticated Firebase CLI/admin deployment tool.

### Files changed in this session

```text
scripts/deploy_firebase_saas_seed.sh
docs/DayDine-Current-State-And-Next-Actions.md
```

Notes:

```text
scripts/deploy_firebase_saas_seed.sh was added before the later decision to prefer direct local CLI commands. It contains no live UIDs or live emails and can be ignored or removed in a later cleanup if desired.
No live Firebase UID/email seed was committed to the repo.
```

### Commits made / confirmed in this session

```text
410392c0 - Generate V5 Evidence Rank prototype outputs
af0b3b8 - Add safe Firebase SaaS seed deploy helper
```

This handover update is also being committed as:

```text
Update DayDine handover after Firebase deploy preparation
```

### Decisions made

1. Do not restart strategy or rebuild; continue implementation from the existing Firebase/Auth/V5 foundation.
2. Keep `recursive-research-eu` as the active Firebase project.
3. Keep `daydine_saas` as the private SaaS root.
4. Do not commit live Firebase UIDs or live account emails to the public repo.
5. Generate the live seed locally using `scripts/build_firebase_saas_seed.py` with `--strict --saas-only` and CLI args.
6. Use `firebase database:update /daydine_saas ...`, never `firebase database:set`, for the SaaS import.
7. Do not touch `/daydine` or `/daydine/establishments` during the SaaS import.
8. Disregard `evidtrace` as non-DayDine; accept that deploying DayDine rules will lock it unless separately handled later.
9. Treat V5 outputs as experimental and not a public cutover.
10. Treat Lambs as the first protected dashboard fixture only, not the strategic product focus.

---

## 6. Current blockers / risks

1. Firebase rules are committed in repo but still need to be deployed to `recursive-research-eu` from an authenticated Firebase CLI/session.
2. `/daydine_saas` does not yet exist in the live Realtime Database until the local import is run.
3. Protected browser QA cannot be completed until rules are deployed and `/daydine_saas` is imported.
4. The current live Firebase rules are loose; deploying repo rules will lock down the database. This is desired for DayDine, but it will also lock `evidtrace` because no rule is included for it.
5. V5 outputs exist, but both Stratford and Leamington remain `warning` because ambiguous Google Place groups still need admin review.
6. Public methodology/copy still needs review before any V5 public cutover.
7. Static prototype pages still exist and must be treated as reference only, not the real client product.
8. `scripts/deploy_firebase_saas_seed.sh` exists as an optional helper but the current preferred operational instruction is the direct local CLI command sequence, not committing filled UID/email values.

---

## 7. Next 3 actions

### Next action 1 — Run local Firebase deploy/import

From the DayDine repo root, run the direct local sequence using the verified Firebase Auth UID/email values held outside the repo:

```bash
git checkout main
git pull --ff-only origin main
mkdir -p tmp

python3 scripts/build_firebase_saas_seed.py \
  --admin-uid "<admin Firebase Auth UID>" \
  --admin-email "<admin email>" \
  --client-uid "<client Firebase Auth UID>" \
  --client-email "<client email>" \
  --strict \
  --saas-only \
  --out tmp/daydine_saas_seed_lambs.json

grep -q "REPLACE_WITH_FIREBASE" tmp/daydine_saas_seed_lambs.json && echo "ERROR: placeholder still present" || echo "OK: no placeholders"
python3 -m json.tool tmp/daydine_saas_seed_lambs.json >/dev/null && echo "OK: valid JSON"

firebase use recursive-research-eu
firebase deploy --only database --project recursive-research-eu
firebase database:update /daydine_saas tmp/daydine_saas_seed_lambs.json \
  --project recursive-research-eu \
  --instance recursive-research-eu-default-rtdb
```

Expected success signals:

```text
Strict validation passed: no placeholder Firebase Auth UIDs remain.
OK: no placeholders
OK: valid JSON
Deploy complete!
Data updated successfully
```

### Next action 2 — Run Firebase sanity checks

Check these live paths after import:

```bash
firebase database:get /daydine_saas/users/<adminUid>/role \
  --project recursive-research-eu \
  --instance recursive-research-eu-default-rtdb

firebase database:get /daydine_saas/users/<clientUid>/clientId \
  --project recursive-research-eu \
  --instance recursive-research-eu-default-rtdb

firebase database:get /daydine_saas/users/<clientUid>/venueIds/lambs \
  --project recursive-research-eu \
  --instance recursive-research-eu-default-rtdb

firebase database:get /daydine_saas/operatorDashboards/lambs/snapshots/2026-04/venue \
  --project recursive-research-eu \
  --instance recursive-research-eu-default-rtdb

firebase database:get /daydine/establishments \
  --project recursive-research-eu \
  --instance recursive-research-eu-default-rtdb \
  --shallow
```

Expected results:

```text
"admin"
"lambs"
true
"Lambs"
/daydine/establishments returns a JSON object of keys, not null
```

### Next action 3 — QA protected SaaS routes on Vercel

After Firebase deploy/import, test:

```text
https://daydine.vercel.app/login
https://daydine.vercel.app/client
https://daydine.vercel.app/client/venues/lambs
https://daydine.vercel.app/admin
https://daydine.vercel.app/admin/reports
https://daydine.vercel.app/admin/markets
https://daydine.vercel.app/operator/lambs
```

Acceptance checks:

```text
Signed out/incognito users are redirected to /login for /client and /admin routes.
Admin user can access /client, /client/venues/lambs, /admin, /admin/reports and /admin/markets.
Client user can access /client and /client/venues/lambs only.
Client user cannot access /admin, /admin/reports or /admin/markets.
/operator/lambs redirects to /client/venues/lambs.
Protected pages read Firebase /daydine_saas data, not public operator JSON.
```

---

## 8. Suggested prompt for the next chat

```text
We are continuing work on the DayDine repo: https://github.com/jono8001/daydine

Please use the GitHub connector/API tool to read these files first:

1. docs/DayDine-Current-State-And-Next-Actions.md
2. docs/DayDine-Professional-SaaS-Roadmap.md
3. docs/DayDine-V5-Evidence-Rank-Blueprint.md
4. docs/ADR-002-Authorised-Review-Data-And-V5-Positioning.md
5. docs/DayDine-Client-Dashboard-Pilot-Pattern.md
6. docs/DayDine-Prior-Work-Inventory.md
7. docs/DayDine-Roadmap-Implementation-Control.md

Current state:
- Firebase Auth/client/admin shells are committed.
- Correct Firebase project is recursive-research-eu.
- SaaS private data root is daydine_saas.
- database.rules.json, firebase.json and .firebaserc are committed.
- Admin and client Firebase Auth users have been created and verified outside the repo.
- Do not commit live Firebase UIDs/emails to the public repo.
- Live Realtime Database currently has daydine and evidtrace, but no daydine_saas yet.
- The repo rules file intentionally locks root read/write to false and permits public read for daydine/establishments while protecting daydine_saas.
- Lambs is only the first protected dashboard fixture, not the strategic product focus.
- Coverage certificates exist for Stratford and Leamington.
- V5 Evidence Rank outputs have been generated and committed under assets/v5/ in commit 410392c0.
- Firebase rules and the /daydine_saas seed still need to be deployed/imported locally via Firebase CLI.

Current priority:
1. Run the local Firebase CLI sequence to generate tmp/daydine_saas_seed_lambs.json with --strict --saas-only, deploy database.rules.json, and merge-import only /daydine_saas using firebase database:update.
2. Verify live Firebase paths: admin role, client clientId, client venueIds/lambs, Lambs dashboard snapshot, and that /daydine/establishments still exists.
3. QA /login, /client, /client/venues/lambs, /admin, /admin/reports, /admin/markets and /operator/lambs on daydine.vercel.app with admin, client and signed-out sessions.

Do not restart strategy. Do not rebuild from scratch. Follow the implementation control note and state which prior assets are reused, migrated, refactored, archived or retired.
```

---

## 9. Handover update rule

At the end of every major DayDine session, update this file with:

```text
What changed
Files changed
Commits made
Decisions made
Current blockers
Next 3 actions
Suggested next-chat prompt if changed
```
