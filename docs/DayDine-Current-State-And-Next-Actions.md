# DayDine Current State and Next Actions

**Status:** Active handover file  
**Last updated:** 28 April 2026  
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

## 2. Current strategic direction

DayDine should become a professional UK hospitality intelligence SaaS with:

1. **Public ranking site** for diners, SEO and market authority.
2. **Firebase-authenticated client portal** for restaurant operators.
3. **Firebase-authenticated admin portal** for internal market, report, pipeline and QA workflows.
4. **Low-cost monthly data pipeline** that pulls/enriches data once per month and caches results.
5. **V5 DayDine Evidence Rank** as the next methodology destination.

### 2.1 Strategic repositioning locked on 28 April 2026

The central strategic decision is now:

> DayDine must not compete with Tripadvisor by pretending to have more review data. DayDine must compete as a proprietary hospitality intelligence platform that includes authorised review evidence, separates popularity from quality, and identifies Proven Leaders, Hidden Gems, Rising Venues and Overexposed venues across the whole local market.

DayDine can say it includes review evidence because it uses authorised public review data, including Google review rating and Google review volume. It must not imply that Tripadvisor or OpenTable reviews are ingested unless a legal/licensed/API-compatible route is actually in place.

Preferred positioning:

> Ranked by DayDine's proprietary hospitality intelligence model, using authorised review evidence, public trust signals, category context, market visibility and evidence confidence.

Avoid:

> We analyse every review across the web.
> We include Tripadvisor/OpenTable reviews.
> Objectively the best restaurants.
> Transparent formula / exact component scorecard.

The public methodology should have **transparent principles but proprietary machinery**. It should create trust and mystique, not expose exact weights or public component scorecards.

---

## 3. Important current decisions

### 3.1 Architecture

Accepted target model:

```text
Public rankings/search/methodology = public, fast, generated/cacheable
Client dashboards/admin tools = Firebase Auth + database rules
Monthly data refresh = batch/cached, not live API calls per user page view
```

Possible hosting approaches:

- **Hybrid first:** keep public static site on Vercel temporarily, use Firebase Auth/database for client/admin.
- **Firebase-first later:** migrate the full site to Firebase Hosting once auth and data model are stable.

Current recommendation:

> Use hybrid first for lower migration risk, then move to Firebase Hosting if/when appropriate.

### 3.2 Data-source strategy

Authoritative source strategy after ADR-002:

- FSA/FHRS remains the venue-universe/compliance backbone.
- Google Places is used monthly/batch with cached Place IDs and field masks.
- Google review rating and review volume are authorised review evidence and can support the ranking.
- Tripadvisor is **not** a launch dependency. It is a strategic target source only via official/licensed/API-compatible routes or future approved data-provider route.
- OpenTable is **not** a core launch dependency. It can be linked externally or revisited through partnership/licence later.
- Companies House remains part of entity/risk/trading-confidence context.
- Expert-recognition sources such as Michelin/AA/local awards are later/manual/licensing-aware additions.
- OSM/Overpass or equivalent coverage cross-checks can be used as missing-venue audit layers.

Key cost principle:

```text
Monthly pipeline -> collect/enrich/cache -> users read cached results
```

Do not:

```text
User opens page -> call Google/Tripadvisor/OpenTable live
```

Do not build the core methodology around unauthorised scraping of Tripadvisor, OpenTable or other protected review platforms.

### 3.3 Methodology claim

Preferred public claim:

> Ranked by DayDine's proprietary hospitality intelligence model.

Alternative:

> DayDine rankings include authorised public review evidence, including Google review rating and review volume, alongside wider trust, category, visibility and market-intelligence signals.

Avoid claiming:

> Objectively the best restaurants.

unless DayDine later adds first-party inspection, verified diner panels, critic partnerships, or licensed editorial review data.

### 3.4 Client dashboard build clarification

The next client-dashboard build is **not** about Lambs as a strategic one-restaurant focus.

The correct build objective is:

> Build a reusable protected client-dashboard framework, then seed one or two existing dashboard records as fixtures to prove that the framework works.

Lambs may be the first fixture only because the repo already has a rich report-aligned prototype dashboard for Lambs. The code must be generic and venue-agnostic. Adding a second venue should require data/config only, not bespoke code.

Reference:

```text
docs/DayDine-Client-Dashboard-Pilot-Pattern.md
```

### 3.5 Prior work preservation

Every roadmap stage must check:

```text
docs/DayDine-Prior-Work-Inventory.md
```

before implementation.

Future implementation must state what existing work is:

```text
reused
migrated
refactored
archived
retired
```

---

## 4. Important repo documents

### Main roadmap

```text
docs/DayDine-Professional-SaaS-Roadmap.md
```

Purpose: staged plan for professional SaaS architecture, Firebase, data pipeline, methodology, security and paid-client readiness. Updated to make V5 Evidence Rank the next methodology destination and to remove Tripadvisor/OpenTable as launch dependencies.

### V5 methodology blueprint

```text
docs/DayDine-V5-Evidence-Rank-Blueprint.md
```

Purpose: technical/product blueprint for the next build phase. It defines V5 as a proprietary Evidence Rank model with authorised review evidence, evidence confidence, category-normalised ranking, DayDine Signals, hidden-gem/overexposure logic and public mystique.

### Authorised review-data ADR

```text
docs/ADR-002-Authorised-Review-Data-And-V5-Positioning.md
```

Purpose: supersedes any planning assumption that DayDine's launch ranking depends on unauthorised Tripadvisor/OpenTable scraping. Locks the competitive position and public methodology style.

### Client dashboard pilot-pattern clarification

```text
docs/DayDine-Client-Dashboard-Pilot-Pattern.md
```

Purpose: clarifies that the SaaS build must create a reusable protected dashboard framework; Lambs is only a possible first fixture, not the strategic product focus.

### Prior work inventory

```text
docs/DayDine-Prior-Work-Inventory.md
```

Purpose: protects previous DayDine work from being lost during the rebuild.

### Roadmap implementation control

```text
docs/DayDine-Roadmap-Implementation-Control.md
```

Purpose: mandatory control rule requiring future stages to check prior work before coding.

### This handover file

```text
docs/DayDine-Current-State-And-Next-Actions.md
```

Purpose: short-term state and next-action memory for future AI/coding sessions.

---

## 5. Current technical state

### 5.1 Public site

Current site is primarily static/generated:

- `.html` pages served directly.
- JSON assets committed under `assets/`.
- Vercel uses static routing/rewrites.
- Client-side JS fetches JSON files.

This is acceptable for public rankings and prototype work, but not enough for paid client/private admin features.

### 5.2 Firebase use

Existing Firebase use appears in the public UK establishment lookup.

Important lesson:

> Reuse the existing Firebase project/config pattern where appropriate, but do not expose private client/admin data through unauthenticated browser reads.

Need next:

- Firebase Auth.
- role-based access.
- Firebase security rules.
- protected client/admin data paths.

### 5.3 Admin pages

Existing admin pages:

```text
/admin/markets
/admin/reports
```

Current state:

- useful static prototypes;
- no real authentication;
- should be treated as internal/prototype only until moved behind Firebase Auth.

### 5.4 Client dashboard prototype

Existing prototype route:

```text
/operator/lambs
```

and dashboard assets:

```text
assets/operator-dashboards/lambs/latest.json
```

Current Lambs dashboard is report-aligned:

- operator rank: #9 of 169;
- category rank: #3 of 56;
- operator V4 score: 8.939;
- confidence class: Rankable-B;
- public diner context preserved separately: #4 of 70, public RCS 9.311;
- booking/contact gap restored;
- top priorities restored from original report.

But:

> This is still static/prototype. The next build must create a generic protected dashboard framework first. Lambs can be used as a first seed fixture only if it helps prove the framework.

---

## 6. Current methodology state

### 6.1 Current baseline

V4 is the strongest current implemented methodology baseline.

Important V4 principles to keep:

1. FHRS is compliance/trust, not food quality.
2. Review text sentiment should not drive headline ranking.
3. Missing data must not inflate scores.
4. Confidence/rankability must be separate from score.
5. Single-platform customer validation should cap confidence.
6. Entity ambiguity must block or reduce rankability.
7. Operator dashboards and public rankings can have different emphasis.

### 6.2 V5 destination

V5 is now the next methodology build direction, not a separate speculative idea.

V5 should be built beside V4 first and compared before cutover.

V5 must include:

- authorised review evidence, initially Google rating and review volume;
- capped review-volume benefit, so huge Google counts do not dominate endlessly;
- Bayesian/shrinkage-aware rating logic;
- evidence confidence bands separate from score;
- category-normalised ranking;
- DayDine Signals: Proven Leader, Hidden Gem, Rising Venue, Overexposed, Under-Evidenced/Profile Only;
- DayDine Gap Signal to identify venues stronger or weaker than their public visibility suggests;
- coverage certificates;
- entity-resolution confidence;
- monthly movement and rank-change logic;
- expert-recognition fields, added manually/licensing-aware at first;
- public methodology that explains principles but not exact weights or full formula.

### 6.3 Public methodology style

Public pages should show:

- rank;
- movement;
- category rank;
- Evidence Confidence band;
- DayDine Signal;
- short editorial-style intelligence note.

Public pages should not show:

- exact weights;
- exact formulas;
- source-by-source component scores;
- a detailed public scorecard explaining every lever;
- public instructions that make the model easy to game.

---

## 7. Current market/data state

### 7.1 Stratford-upon-Avon

Current key market.

Important recent issue resolved:

- Vintner Wine Bar / FHRSID 503480 was missing from the natural Stratford data flow.
- The proper canonical fix was completed so Vintner appears in source/scoring/ranking outputs rather than relying only on a guardrail.

Strategic market learning:

- OpenTable appears to cover only a small set of genuinely Stratford-area bookable venues.
- Tripadvisor appears to cover much more of the Stratford public restaurant universe, but review volume is heavily skewed toward the top venues.
- That skew creates DayDine's opportunity: Proven Leaders, Hidden Gems, Rising Venues and Overexposed venues rather than a Tripadvisor clone.

### 7.2 Leamington Spa

Added as next public/operator market.

Current status:

- Leamington has source and score files.
- Leamington has market config.
- Leamington ranking/readiness outputs exist.
- Status is warning, not blocked.
- Remaining warning: ambiguous/duplicate Google Place groups.

Important fix completed:

- Stratford aliases no longer block Leamington readiness because alias checks became source-aware.

### 7.3 Market pipeline

Existing script:

```text
scripts/run_market_pipeline.py
```

Current role:

- config-driven orchestration;
- deterministic/offline steps;
- ranking/readiness generation;
- no full external collection/enrichment yet.

Future role:

- extend into monthly data refresh pipeline with cost logging, cached API calls, Firebase pipeline-run records and admin publish approval.

---

## 8. Key lessons already learned

1. Public ranking and operator intelligence can use different market contexts. They must be labelled clearly.
2. Static hidden URLs are not security.
3. Client dashboard content must preserve the commercial substance of detailed reports.
4. A dashboard should not expose every monitored signal; use a premium monthly intelligence layer.
5. Methodology must not overclaim objective restaurant quality.
6. The moat is not FSA/Google/Companies House access; it is the cleaned venue graph, monthly history, coverage certificates, entity resolution, category intelligence and interpretation.
7. Google should be called in scheduled batches only, not on user page views.
8. Tripadvisor/OpenTable are not launch dependencies unless authorised/licensed/API-compatible access is secured.
9. Before each major build, check prior work inventory.
10. Public methodology should have mystique: transparent principles, proprietary machinery.
11. Client-dashboard work must be framework-first, not Lambs-specific.

---

## 9. Immediate next actions: BUILD PHASE

The planning lock is now complete enough to move to build.

### Next action 1 — Firebase Auth foundation

Implement the first real SaaS foundation:

```text
/login
/client
/admin
Firebase Auth
role-aware route guard
initial Firebase security rules
```

Implementation must reuse/check:

- existing Firebase config pattern in `uk-establishments.html`;
- static admin/operator pages that need protection;
- prior work inventory.

Acceptance criteria:

- unauthenticated user cannot access client/admin data;
- client user cannot see another client's venue;
- admin user can access admin shell;
- Firebase/security rules enforce access, not only frontend hiding.

### Next action 2 — Protected client-dashboard framework

Build a reusable protected dashboard framework, then seed one existing dashboard as a fixture to prove the pattern.

Possible first fixture:

```text
assets/operator-dashboards/lambs/latest.json
```

Target generic data pattern:

```text
clients/{clientId}
venues/{venueId}
clientVenueAccess/{clientId}_{venueId}
operatorDashboards/{venueId}/snapshots/{month}
```

Acceptance criteria:

- framework is generic and venue-agnostic;
- first seeded client user can see only assigned venue(s);
- admin can see/manage all seeded venues;
- adding a second venue requires data/config only, not bespoke code;
- static `/operator/<venue>` routes are no longer canonical client products.

### Next action 3 — Coverage certificate system

Build coverage certificates for:

```text
stratford-upon-avon
leamington-spa
```

Acceptance criteria:

- public ranking page can show simple coverage confidence;
- admin can see full source/coverage breakdown;
- known missing/ambiguous entities are transparent internally.

### Next action 4 — V5 Evidence Rank prototype

Build V5 beside V4, not as a destructive replacement.

Acceptance criteria:

- V4 outputs are preserved for comparison.
- V5 emits DayDine Signal, Evidence Confidence, category ranks and Gap Signal.
- V5 does not require Tripadvisor/OpenTable data to be valid at launch.
- Public wording remains proprietary and conservative.

---

## 10. Suggested prompt for the next chat

Paste this into a new chat if context is lost:

```text
We are continuing work on the DayDine repo: https://github.com/jono8001/daydine

Please use the GitHub connector/API tool to read these files first:

1. docs/DayDine-Professional-SaaS-Roadmap.md
2. docs/DayDine-V5-Evidence-Rank-Blueprint.md
3. docs/ADR-002-Authorised-Review-Data-And-V5-Positioning.md
4. docs/DayDine-Client-Dashboard-Pilot-Pattern.md
5. docs/DayDine-Prior-Work-Inventory.md
6. docs/DayDine-Roadmap-Implementation-Control.md
7. docs/DayDine-Current-State-And-Next-Actions.md

Then begin the build phase. Do not do more strategy unless a blocker appears.

Current build priority:

1. Firebase Auth + role-based /client and /admin foundations.
2. Build the generic protected client-dashboard framework and seed the first existing fixture only to prove the pattern.
3. Build Stratford and Leamington coverage certificates.
4. Prototype V5 Evidence Rank beside V4.

Important: do not rebuild from scratch. Follow the implementation control note. For any work, say which prior assets are reused, migrated, refactored, archived or retired.
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
