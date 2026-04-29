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

Firebase config is centralised in `assets/daydine-firebase.js`. Auth/profile/access helpers are centralised in `assets/daydine-auth.js`. Rules/config are committed but still need deploying to `recursive-research-eu`.

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
```

Before importing the seed, replace the placeholder admin/client UIDs with real Firebase Auth UIDs.

### Protected admin modules

Protected admin shells now exist for `/admin`, `/admin/reports` and `/admin/markets`. Older static files remain as legacy/prototype references only:

```text
admin-reports.html
admin-markets.html
operator-dashboard.html
assets/operator-dashboards/*
```

### Vercel routes

`vercel.json` now routes protected pages to the new shells. Legacy operator links redirect:

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

### V5 prototype builder

Added:

```text
scripts/build_v5_evidence_rank.py
.github/workflows/v5_evidence_rank.yml
```

The V5 builder reads existing V4 ranking/readiness/coverage inputs and emits experimental outputs under `assets/v5/`. Generated `assets/v5/*.json` outputs still need to be produced/committed unless the workflow has been run with `commit_outputs=true`.

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
V4 score files
```

Migrated:

```text
Lambs dashboard fixture -> Firebase seed shape
Static admin/report concepts -> protected admin modules
Static operator-dashboard concept -> protected generic client dashboard
Readiness counts -> coverage certificate assets
```

Refactored:

```text
Firebase setup -> shared daydine-firebase.js
Auth and role logic -> shared daydine-auth.js
Vercel routes -> protected client/admin routes
Coverage generation -> repeatable script
V5 prototype -> repeatable script + workflow
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

## 5. Latest session update — 29 April 2026 handover sync

### What changed in this session

- Synced the current DayDine state after the user continued some work from an iPhone and noted that the earlier visible chat context was stale.
- Re-read the latest repo handover and recent repo history rather than relying on the older visible chat section.
- Confirmed the correct Firebase project is `recursive-research-eu`, not `recursive-research-agent`.
- Confirmed that the current repo is already past initial Firebase/Auth implementation: protected shells, rules, seed fixture, coverage certificates, V5 builder and V5 workflow are committed.
- No application/scoring/Firebase/workflow implementation was changed in this mini-session; this was a handover/state-preservation update only.

### Files changed in this session

```text
docs/DayDine-Current-State-And-Next-Actions.md
```

### Commits made

Recent build-phase commits already present before this handover sync include:

```text
f65227f - Extend DayDine Firebase bootstrap for SaaS auth
672009a - Add shared Firebase auth and role guards
1cac8d6 - Add Firebase login page for client and admin portals
6cdf0e2 - Add protected client portal shell
4010dd0 - Add protected generic client dashboard renderer
13d6de7 - Add protected admin portal shell
d516727 - Add protected admin reports module
7b87d34 - Add protected admin markets module
310e974 - Wire protected client and admin routes
14e46d2 - Add Realtime Database rules for DayDine SaaS roles
5a1447f - Add Firebase SaaS seed builder for first dashboard fixture
e90c8d1 - Add Stratford coverage certificate
26b6185 - Add Leamington coverage certificate
5bcb567 - Add coverage certificate index
9dcfba9 - Add Firebase SaaS seed fixture for Lambs dashboard
ca261df - Tighten SaaS database rules for admin collection reads
6039a14 - Add repeatable coverage certificate builder
bbe4463 - Add V5 Evidence Rank prototype builder
3089aa7 - Add Firebase deployment config for SaaS rules
4cd344f - Pin Firebase project for DayDine SaaS rules
cc5d7cd - Redirect legacy operator links to protected client dashboards
879a655 - Add V5 Evidence Rank generation workflow
8410b0a - Update DayDine handover after Firebase and V5 build phase
```

This handover sync is the only commit made during the present mini-session.

### Decisions made

1. Treat the 29 April handover and latest repo history as the source of truth, not the older visible chat section.
2. Continue with the already-built Firebase/Auth/client/admin foundation rather than restarting the build from scratch.
3. Keep `recursive-research-eu` as the active Firebase project for DayDine because it already holds the public FSA/FHRS lookup data and the new SaaS paths are configured there.
4. Keep Lambs as a first dashboard fixture only; the strategic product remains the generic protected client-dashboard framework.
5. The next work should be operational deployment/QA and V5 output generation, not more methodology strategy.

---

## 6. Current blockers / risks

1. Firebase rules are committed but not deployed to `recursive-research-eu`.
2. Real Firebase Auth users still need to be created/configured outside ChatGPT.
3. Seed data still contains placeholder UIDs and must not be imported until replaced.
4. Protected pages need browser QA after seed/rules deployment.
5. V5 outputs under `assets/v5/` still need to be generated and committed.
6. Stratford has 6 ambiguous Google Place groups; Leamington has 7, so both markets remain `warning`.
7. Public methodology/copy still needs review before any V5 public cutover.
8. Static prototype pages still exist and must be treated as reference only, not the real client product.

---

## 7. Next 3 actions

### Next action 1 — Firebase deploy and seed

In Firebase/local CLI:

```text
1. Confirm project: recursive-research-eu.
2. Enable Email/Password sign-in if not already enabled.
3. Create one admin Firebase Auth user.
4. Create one test client Firebase Auth user.
5. Replace placeholder UIDs in data/firebase_daydine_saas_seed_lambs.json.
6. Import/merge the seed under Realtime Database.
7. Deploy database.rules.json.
```

Suggested CLI:

```bash
firebase use recursive-research-eu
firebase deploy --only database
```

### Next action 2 — Generate and validate V5 outputs

Run GitHub Actions workflow:

```text
V5 Evidence Rank Prototype
commit_outputs = true
```

or locally:

```bash
python scripts/build_coverage_certificates.py --markets stratford-upon-avon leamington-spa
python scripts/build_v5_evidence_rank.py --markets stratford-upon-avon leamington-spa
git add assets/coverage assets/v5
git commit -m "Generate V5 Evidence Rank prototype outputs"
git push
```

Then inspect:

```text
assets/v5/stratford-upon-avon.json
assets/v5/leamington-spa.json
assets/v5/index.json
```

### Next action 3 — QA protected SaaS routes

After Firebase deploy/seed, test:

```text
/login
/client
/client/venues/lambs
/admin
/admin/reports
/admin/markets
/operator/lambs -> should redirect to /client/venues/lambs
```

Acceptance checks:

```text
Unauthenticated users are redirected to login.
Client user sees only assigned venue(s).
Client user cannot read another venue dashboard.
Admin user can access admin shell and all seeded venues.
Protected pages read Firebase data, not public operator JSON.
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
- Firebase Auth/client/admin shells have been committed.
- Correct Firebase project is recursive-research-eu.
- SaaS private data root is daydine_saas.
- database.rules.json, firebase.json and .firebaserc are committed.
- Lambs is only the first protected dashboard fixture, not the strategic product focus.
- Coverage certificates exist for Stratford and Leamington.
- scripts/build_v5_evidence_rank.py and .github/workflows/v5_evidence_rank.yml exist.
- The last session was a handover sync only: no implementation files were changed beyond docs/DayDine-Current-State-And-Next-Actions.md.

Current priority:
1. Deploy Firebase Realtime Database rules and import the seeded Lambs fixture after replacing placeholder UIDs.
2. Run the V5 Evidence Rank Prototype workflow with commit_outputs=true, or run the V5 scripts locally and commit assets/v5 outputs.
3. QA /login, /client, /client/venues/lambs, /admin, /admin/reports, /admin/markets.

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
