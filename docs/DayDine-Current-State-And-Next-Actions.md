# DayDine Current State and Next Actions

**Status:** Active handover file  
**Last updated:** April 2026  
**Purpose:** Preserve DayDine project context between long AI/coding conversations. This file should be updated at the end of major work sessions or before starting a new conversation.

---

## 1. How to use this file

When starting a new ChatGPT / Claude / Codex session, paste this instruction:

```text
We are working on the DayDine repo: https://github.com/jono8001/daydine

Before doing any implementation, please read these project-memory files:

1. docs/DayDine-Professional-SaaS-Roadmap.md
2. docs/DayDine-Prior-Work-Inventory.md
3. docs/DayDine-Roadmap-Implementation-Control.md
4. docs/DayDine-Current-State-And-Next-Actions.md

Then continue from the current next action. Do not rebuild from scratch. Reuse, migrate, refactor or consciously retire prior work according to the control note.
```

Rule:

> The repo is now the project memory. Long chats should update this file before they end.

---

## 2. Current strategic direction

DayDine should become a professional UK restaurant intelligence SaaS with:

1. **Public ranking site** for diners and SEO.
2. **Firebase-authenticated client portal** for restaurant operators.
3. **Firebase-authenticated admin portal** for internal market, report, pipeline and QA workflows.
4. **Low-cost monthly data pipeline** that pulls/enriches data once per month and caches results.
5. **Defensible public methodology** based on public-evidence confidence, coverage certificates, entity-resolution quality and monthly movement.

Current agreed principle:

> Do not keep expanding static private dashboards. The next serious product step is Firebase Auth + protected client/admin portal foundations.

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

Accepted source strategy:

- FSA/FHRS remains the venue-universe/compliance backbone.
- Google Places is used monthly/batch with cached Place IDs and field masks.
- Tripadvisor is added for metadata/cross-platform validation, also monthly/batch.
- OpenTable/booking-platform sources are deferred until later.
- Companies House remains part of entity/risk/trading-confidence context.
- Expert-recognition sources such as Michelin/AA are later/manual/licensing-aware additions.

Key cost principle:

```text
Monthly pipeline -> collect/enrich/cache -> users read cached results
```

Do not:

```text
User opens page -> call Google/Tripadvisor live
```

### 3.3 Methodology claim

Preferred public claim:

> Top-ranked by DayDine's public-evidence confidence model.

or:

> Best-evidenced restaurants in this market, based on public trust, customer validation, recognition, visibility and confidence signals.

Avoid claiming:

> Objectively the best restaurants.

unless DayDine later adds first-party inspection, verified diner panels, critic partnerships or licensed editorial review data.

### 3.4 Prior work preservation

Every roadmap stage must now check:

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

## 4. Important repo documents now created

### Main roadmap

```text
docs/DayDine-Professional-SaaS-Roadmap.md
```

Purpose: full staged plan for professional SaaS architecture, Firebase, data pipeline, methodology, security and paid-client readiness.

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

Current Lambs dashboard is now report-aligned:

- operator rank: #9 of 169;
- category rank: #3 of 56;
- operator V4 score: 8.939;
- confidence class: Rankable-B;
- public diner context preserved separately: #4 of 70, public RCS 9.311;
- booking/contact gap restored;
- top priorities restored from original report.

But:

> This is still static/prototype. It must be migrated into Firebase before being used as a real client product.

---

## 6. Current methodology state

### 6.1 Current baseline

V4 is the strongest current methodology implementation.

Important V4 principles to keep:

1. FHRS is compliance/trust, not food quality.
2. Review text sentiment should not drive headline ranking.
3. Missing data must not inflate scores.
4. Confidence/rankability must be separate from score.
5. Single-platform customer validation should cap confidence.
6. Entity ambiguity must block or reduce rankability.
7. Operator dashboards and public rankings can have different emphasis.

### 6.2 Future direction

Roadmap calls for a future V5-style **DayDine Evidence Rank Model** with:

- venue-universe completeness;
- entity-resolution confidence;
- multi-platform customer validation;
- expert-recognition layer;
- trust/compliance layer;
- commercial-accessibility layer;
- uncertainty intervals;
- rank probabilities;
- coverage certificates.

Do not jump to V5 implementation before preserving V4 comparison and migration work.

---

## 7. Current market/data state

### 7.1 Stratford-upon-Avon

Current key market.

Important recent issue resolved:

- Vintner Wine Bar / FHRSID 503480 was missing from the natural Stratford data flow.
- The proper canonical fix was completed so Vintner appears in source/scoring/ranking outputs rather than relying only on a guardrail.

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
4. A dashboard should not expose every monitored signal; use a premium “Monthly intelligence layer.”
5. Methodology must not overclaim objective restaurant quality.
6. The moat is not FSA/Google/Companies House access; it is the cleaned venue graph, monthly history, coverage certificates, entity resolution and interpretation.
7. Google/Tripadvisor should be called in scheduled batches only, not on user page views.
8. Before each major build, check prior work inventory.

---

## 9. Immediate next actions

### Next action 1 — Stage 0 completion docs

Create:

```text
docs/DayDine-Launch-Readiness.md
docs/ADR-001-Public-Static-Plus-Firebase-SaaS.md
```

Purpose:

- make current limitations explicit;
- document the chosen architecture;
- define blockers before real clients/public expansion.

### Next action 2 — Firebase Auth foundation

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

### Next action 3 — Protected Lambs dashboard migration

Migrate the current report-aligned Lambs static dashboard into Firebase:

```text
venues/lambs
clients/lambs
clientVenueAccess/client_lambs_lambs
operatorDashboards/lambs/snapshots/2026-04
```

Acceptance criteria:

- Lambs client user can see Lambs only.
- Admin can see/manage Lambs.
- Static `/operator/lambs` is no longer the canonical client product.

### Next action 4 — Coverage certificate system

Build coverage certificates for:

```text
stratford-upon-avon
leamington-spa
```

Acceptance criteria:

- public ranking page can show simple coverage confidence;
- admin can see full source/coverage breakdown;
- known missing/ambiguous entities are transparent internally.

---

## 10. Suggested prompt for the next chat

Paste this into a new chat if context is lost:

```text
We are continuing work on the DayDine repo: https://github.com/jono8001/daydine

Please use the GitHub connector/API tool to read these files first:

1. docs/DayDine-Professional-SaaS-Roadmap.md
2. docs/DayDine-Prior-Work-Inventory.md
3. docs/DayDine-Roadmap-Implementation-Control.md
4. docs/DayDine-Current-State-And-Next-Actions.md

Then continue from the next action in the handover file.

Important: do not rebuild from scratch. Follow the implementation control note. For any work you do, say which prior assets are reused, migrated, refactored, archived or retired.

The current priority is to complete Stage 0 documents and then build Firebase Auth + protected /client and /admin foundations.
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
