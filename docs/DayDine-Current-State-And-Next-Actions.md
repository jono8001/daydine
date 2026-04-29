# DayDine Current State and Next Actions

**Status:** Active handover file  
**Last updated:** 29 April 2026  
**Purpose:** Preserve DayDine project context between long AI/coding conversations. This file should be updated at the end of major work sessions or before starting a new conversation.

---

## 1. How to use this file

When starting a new ChatGPT / Claude / Codex session, paste this instruction:

```text
We are working on the DayDine repo: https://github.com/jono8001/daydine

Before doing any implementation, please read these project-memory files:

1. docs/DayDine-Professional-SaaS-Roadmap.md
2. docs/DayDine-V5-Evidence-Rank-Blueprint.md
3. docs/ADR-002-Authorised-Review-Data-And-V5-Positioning.md
4. docs/DayDine-Client-Dashboard-Pilot-Pattern.md
5. docs/DayDine-Prior-Work-Inventory.md
6. docs/DayDine-Roadmap-Implementation-Control.md
7. docs/DayDine-Current-State-And-Next-Actions.md

Then continue from the current next action. Do not rebuild from scratch. Reuse, migrate, refactor or consciously retire prior work according to the control note.
```

Rule:

> The repo is now the project memory. Long chats should update this file before they end.

---

## 2. Strategic direction locked

DayDine should become a professional UK hospitality intelligence SaaS with:

1. **Public ranking site** for diners, SEO and market authority.
2. **Firebase-authenticated client portal** for restaurant operators.
3. **Firebase-authenticated admin portal** for internal market, report, pipeline and QA workflows.
4. **Low-cost monthly data pipeline** that pulls/enriches data once per month and caches results.
5. **V5 DayDine Evidence Rank** as the next methodology destination.

The central strategic decision remains:

> DayDine must not compete with Tripadvisor by pretending to have more review data. DayDine must compete as a proprietary hospitality intelligence platform that includes authorised review evidence, separates popularity from quality, and identifies Proven Leaders, Hidden Gems, Rising Venues and Overexposed venues across the whole local market.

DayDine can say it includes review evidence because it uses authorised public review data, including Google review rating and Google review volume. It must not imply that Tripadvisor or OpenTable reviews are ingested unless a legal/licensed/API-compatible route is actually in place.

Preferred positioning:

> Ranked by DayDine's proprietary hospitality intelligence model, using authorised review evidence, public trust signals, category context, market visibility and evidence confidence.

Avoid:

```text
We analyse every review across the web.
We include Tripadvisor/OpenTable reviews.
Objectively the best restaurants.
Transparent formula / exact component scorecard.
```

The public methodology should have **transparent principles but proprietary machinery**.

---

## 3. Architecture decision

Accepted target model:

```text
Public rankings/search/methodology = public, fast, generated/cacheable
Client dashboards/admin tools = Firebase Auth + database rules
Monthly data refresh = batch/cached, not live API calls per user page view
```

Current hosting approach:

> Hybrid first: keep public static site on Vercel temporarily, use Firebase Auth/database for client/admin. Move fully to Firebase Hosting later only if useful.

Correct Firebase project:

```text
recursive-research-eu
```

This was confirmed from the existing public UK/FSA establishment lookup in `uk-establishments.html`. Do **not** use `recursive-research-agent` for the DayDine SaaS work unless a deliberate migration decision is made.

Private SaaS paths now live under:

```text
daydine_saas
```

Public FHRS/FSA lookup remains under the existing public path:

```text
daydine/establishments
```

---

## 4. Methodology state

### 4.1 Current baseline

V4 is the strongest current implemented methodology baseline.

Important V4 principles to preserve:

1. FHRS is compliance/trust, not food quality.
2. Review text sentiment should not drive headline ranking.
3. Missing data must not inflate scores.
4. Confidence/rankability must be separate from score.
5. Single-platform customer validation should cap confidence.
6. Entity ambiguity must block or reduce rankability.
7. Operator dashboards and public rankings can have different emphasis.

### 4.2 V5 destination

V5 is now the next methodology build direction, not a speculative idea.

V5 must include:

- authorised review evidence, initially Google rating and review volume;
- capped review-volume benefit;
- Bayesian/shrinkage-aware rating logic;
- evidence confidence bands separate from score;
- category-normalised ranking;
- DayDine Signals: Proven Leader, Hidden Gem, Rising Venue, Overexposed, Under-Evidenced/Profile Only;
- DayDine Gap Signal;
- coverage certificates;
- entity-resolution confidence;
- monthly movement and rank-change logic;
- public methodology that explains principles but not exact weights or formula.

V5 should be built beside V4 and compared before any public cutover.

---

## 5. Current technical state after 29 April build session

### 5.1 Firebase/Auth foundation

Added a first protected SaaS foundation:

```text
/login
/client
/client/venues/:venue
/admin
/admin/reports
/admin/markets
```

New/updated files:

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

Firebase config is centralised in:

```text
assets/daydine-firebase.js
```

Auth/profile/access helpers are centralised in:

```text
assets/daydine-auth.js
```

Database rules are in:

```text
database.rules.json
```

Firebase deployment config is in:

```text
firebase.json
.firebaserc
```

Important caveat:

> Firebase rules have been committed but not deployed from this chat. A human or CI job still needs to run Firebase deploy against `recursive-research-eu`.

### 5.2 Protected client-dashboard framework

Built a generic protected dashboard renderer:

```text
client.html
client-venue.html
```

Target data model:

```text
daydine_saas/users/{uid}
daydine_saas/clients/{clientId}
daydine_saas/venues/{venueId}
daydine_saas/clientVenueAccess/{clientId}_{venueId}
daydine_saas/operatorDashboards/{venueId}/snapshots/{month}
```

Lambs is only the first fixture, not the strategic product focus.

Seed assets added:

```text
data/firebase_daydine_saas_seed_lambs.json
scripts/build_firebase_saas_seed.py
```

Before importing the seed, replace:

```text
REPLACE_WITH_FIREBASE_ADMIN_UID
REPLACE_WITH_FIREBASE_CLIENT_UID
```

with real Firebase Auth UIDs.

### 5.3 Protected admin modules

New protected admin shells:

```text
/admin
/admin/reports
/admin/markets
```

These wrap the previous static admin concepts with Firebase Auth and admin-only role checks.

The older static files remain as legacy/prototype references:

```text
admin-reports.html
admin-markets.html
operator-dashboard.html
assets/operator-dashboards/*
```

### 5.4 Vercel route changes

`vercel.json` now routes:

```text
/login -> login.html
/client -> client.html
/client/venues/:venue -> client-venue.html
/admin -> admin.html
/admin/reports -> admin-reports-protected.html
/admin/markets -> admin-markets-protected.html
```

Legacy operator links now redirect:

```text
/operator/:venue -> /client/venues/:venue
```

This fixes the prior risk where old `/operator/:venue` links could accidentally default to Lambs inside the protected renderer.

### 5.5 Coverage certificates

Added first coverage certificate assets:

```text
assets/coverage/stratford-upon-avon.json
assets/coverage/leamington-spa.json
assets/coverage/index.json
scripts/build_coverage_certificates.py
```

Current certificate summaries:

```text
Stratford-upon-Avon:
- 209 establishments reviewed
- 204 candidate/scored dining venues
- 170 rankable venues
- 30 public ranking venues
- 0 active known-missing venues
- 6 ambiguous Google Place groups

Leamington Spa:
- 292 establishments reviewed
- 287 candidate/scored dining venues
- 252 rankable venues
- 30 public ranking venues
- 0 active known-missing venues
- 7 ambiguous Google Place groups
```

Both markets remain `warning`, not `ready`, because ambiguous Google Place groups still need admin review.

### 5.6 V5 prototype builder

Added:

```text
scripts/build_v5_evidence_rank.py
.github/workflows/v5_evidence_rank.yml
```

The V5 builder reads existing V4 ranking/readiness/coverage inputs and emits experimental outputs under:

```text
assets/v5/
```

V5.0 output fields include:

```text
venue_id
market_slug
canonical_name
category
v5_score_estimate
v5_score_band
v5_overall_rank
v5_category_rank
evidence_confidence
coverage_status
entity_resolution_confidence
daydine_signal
daydine_gap_signal
public_intelligence_note
internal_diagnostics
```

The workflow:

```text
.github/workflows/v5_evidence_rank.yml
```

can be manually dispatched and can optionally commit generated `assets/coverage` and `assets/v5` outputs back to the branch.

Important caveat:

> The V5 generator has been committed, but generated `assets/v5/*.json` outputs have not yet been committed unless the workflow is run with `commit_outputs=true` or the script is run locally and outputs are committed.

---

## 6. Prior assets handled in the 29 April build session

### Reused

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

### Migrated

```text
Lambs dashboard fixture -> Firebase seed shape
Static admin/report concepts -> protected admin modules
Static operator-dashboard concept -> protected generic client dashboard
Readiness counts -> coverage certificate assets
```

### Refactored

```text
Firebase setup -> shared daydine-firebase.js
Auth and role logic -> shared daydine-auth.js
Vercel routes -> protected client/admin routes
Coverage generation -> repeatable script
V5 prototype -> repeatable script + workflow
```

### Archived / retained as legacy reference

```text
operator-dashboard.html
admin-reports.html
admin-markets.html
assets/operator-dashboards/*
```

### Retired

Nothing deleted or retired yet.

---

## 7. Commits made on 29 April 2026

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
```

This handover update is an additional commit after the above list.

---

## 8. Current blockers / risks

1. **Firebase is not yet deployed.** `database.rules.json`, `firebase.json` and `.firebaserc` are committed, but rules still need deploying to `recursive-research-eu`.
2. **No real Firebase Auth users are configured from this chat.** Create admin/client users in Firebase Auth and use their real UIDs in the seed data.
3. **Seed data still contains placeholder UIDs.** Do not import without replacing the placeholders.
4. **Protected pages need browser QA.** Test `/login`, `/client`, `/client/venues/lambs`, `/admin`, `/admin/reports`, `/admin/markets` after Firebase seed/rules deployment.
5. **V5 outputs are not yet generated/committed.** Run the new V5 workflow manually with `commit_outputs=true`, or run scripts locally and commit `assets/v5/*.json`.
6. **Market status remains warning.** Stratford has 6 ambiguous Google Place groups; Leamington has 7. These need admin review before claiming fully clean coverage.
7. **Public methodology/copy still needs update before public V5 cutover.** Do not expose exact formula/weights.
8. **The static prototype pages still exist.** They are retained for reference, but real client use should go through protected routes.

---

## 9. Immediate next 3 actions

### Next action 1 — Firebase deploy and seed

In the Firebase console / local CLI:

```text
1. Confirm project: recursive-research-eu
2. Enable Email/Password sign-in if not already enabled.
3. Create one admin Firebase Auth user.
4. Create one test client Firebase Auth user.
5. Replace placeholder UIDs in data/firebase_daydine_saas_seed_lambs.json.
6. Import/merge the seed under Realtime Database.
7. Deploy database.rules.json.
```

Suggested CLI commands once authenticated locally:

```bash
firebase use recursive-research-eu
firebase deploy --only database
```

### Next action 2 — Generate and validate V5 outputs

Run the GitHub Actions workflow:

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

## 10. Suggested prompt for the next chat

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

Current priority:
1. Deploy Firebase Realtime Database rules and import the seeded Lambs fixture after replacing placeholder UIDs.
2. Run the V5 Evidence Rank Prototype workflow with commit_outputs=true, or run the V5 scripts locally and commit assets/v5 outputs.
3. QA /login, /client, /client/venues/lambs, /admin, /admin/reports, /admin/markets.

Do not restart strategy. Do not rebuild from scratch. Follow the implementation control note and state which prior assets are reused, migrated, refactored, archived or retired.
```

---

## 11. Handover update rule

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

This keeps future chats short and prevents losing the thread.
