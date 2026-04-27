# DayDine Prior Work Inventory

**Status:** Working inventory  
**Created:** April 2026  
**Purpose:** Protect existing DayDine work before the professional SaaS rebuild. This document maps the repo's existing methodology, scoring, report, dashboard, data-quality and pipeline assets into the next-stage roadmap so valuable work is reused, migrated or deliberately retired rather than accidentally overwritten.

---

## 1. Why this inventory exists

DayDine already contains substantial prior work:

- V3/V3.4 methodology and scoring history;
- V4 scoring specification and implementation;
- V4 migration/comparison material;
- operator report generation modules;
- monthly report samples;
- revenue opportunity modelling;
- Companies House risk review work;
- entity alias and known-missing venue guardrails;
- market readiness checks;
- static prototype client dashboards;
- public ranking/search/admin pages;
- GitHub Actions pipeline work.

The next professional SaaS stage must not restart from scratch. Each roadmap stage should explicitly decide whether existing assets are:

```text
Reuse as-is
Migrate into Firebase / new architecture
Refactor
Archive as legacy reference
Retire
```

---

## 2. Methodology and scoring assets

### 2.1 Current / future V4 methodology

| Asset | Purpose | Next-stage treatment |
|---|---|---|
| `docs/DayDine-V4-Scoring-Spec.md` | Engineering-level V4 scoring contract: component weights, shrinkage, confidence/rankability, penalties, exclusions and output schema. | Reuse as the baseline technical scoring spec. Do not rewrite without a migration note. |
| `docs/DayDine-Scoring-Methodology.md` | Public-facing methodology draft explaining V4 and V3.4 transition status. | Refactor before launch to remove confusing transition language once the public method is final. |
| `rcs_scoring_v4.py` | V4 scoring engine. | Reuse as current official scoring implementation until V5 prototype is validated. |
| `rcs_scoring_stratford.py` | V3.4 legacy scoring engine. | Preserve for audit/comparison only. Do not present as future public method. |
| `UK-Restaurant-Tracker-Methodology-Spec-V3.md` | Earlier methodology/specification history. | Archive as legacy reference; mine for concepts only if explicitly useful. |

### 2.2 Migration and comparison assets

| Asset | Purpose | Next-stage treatment |
|---|---|---|
| `docs/DayDine-V4-Scoring-Comparison.md` | V3/V4 comparison material. | Reuse during methodology cutover and V5 comparison work. |
| `docs/DayDine-V4-Migration-Note.md` | Migration note for moving from earlier score architecture to V4. | Keep as audit trail. Extend if the product moves to V5 Evidence Rank Model. |
| `compare_v3_v4.py` | Comparison harness. | Reuse/refactor for V4 vs V5 diagnostics. |

### 2.3 Methodology risks to preserve

The prior work correctly established several important rules that must survive the rebuild:

1. FHRS is a trust/compliance signal, not a food-quality signal.
2. Review text and sentiment should not drive headline ranking.
3. Missing data must not inflate scores.
4. Confidence/rankability must be separate from the numeric score.
5. Single-platform customer validation should cap confidence.
6. Entity ambiguity must reduce rankability or block primary ranking.
7. Commercial Readiness is more important for operator dashboards than for public "best restaurant" claims.

---

## 3. Operator intelligence and report assets

### 3.1 Report-generation modules

| Asset | Purpose | Next-stage treatment |
|---|---|---|
| `operator_intelligence/v4_report_generator.py` | Main V4 report generator. | Reuse as source logic for Firebase-backed report generation/export. |
| `operator_intelligence/v4_wording.py` | Wording rules and narrative framing. | Reuse/refactor for dashboard copy, report copy and methodology-safe language. |
| `operator_intelligence/v4_action_cards.py` | Action-card generation. | Reuse directly in client dashboard action priorities. |
| `operator_intelligence/report_spec.py` | Operator report structure/specification. | Reconcile with dashboard data model; do not lose sections that provide commercial value. |
| `operator_intelligence/builders/trust_detail.py` | Trust/compliance detail builder. | Reuse, but ensure FHRS wording remains compliance-focused. |
| `operator_intelligence/builders/long_form.py` | Long-form report section builder. | Reuse for PDF/export layer rather than main dashboard. |
| `operator_intelligence/builders/actions_tracker.py` | Action tracking/report section logic. | Reuse in client portal monthly action history. |

### 3.2 Revenue opportunity work

| Asset | Purpose | Next-stage treatment |
|---|---|---|
| `operator_intelligence/revenue_opportunity.py` | Revenue/rank-band association modelling scaffold. | Reuse carefully. Must remain correlation/rank-band association, not causal "each rank is worth £X". |
| `outputs/examples/Lambs_revenue_opportunity_rank_band_example_2026-04.md` | Example of rank-band revenue opportunity framing. | Reuse as reference for client dashboard commercial-impact module. |

Important guardrail:

> Revenue opportunity claims must stay directional and conservative unless operator first-party sales/cover data is supplied.

---

## 4. Existing report and dashboard outputs

### 4.1 Full report examples

| Asset | Purpose | Next-stage treatment |
|---|---|---|
| `outputs/examples/Lambs_full_operator_report_with_tracking_2026-04.md` | Full Lambs operator intelligence report. | Treat as canonical report-alignment source for Lambs client dashboard. |
| `outputs/examples/Lambs_tracking_snapshot_example.md` | Monthly tracking snapshot example. | Reuse in dashboard movement/history design. |
| `outputs/examples/Lambs_revenue_opportunity_rank_band_example_2026-04.md` | Revenue/rank-band example. | Reuse in commercial-impact module with wording guardrails. |

### 4.2 Monthly sample/report outputs

The repo contains many generated monthly report examples under:

```text
samples/v4/monthly/
outputs/monthly/
```

Examples include:

- `samples/v4/monthly/Lambs_2026-04.md`
- `samples/v4/monthly/Loxleys_Restaurant_and_Wine_Bar_2026-04.md`
- `samples/v4/monthly/The_Roebuck_Inn_Alcester_2026-04.md`
- `outputs/monthly/Soma_2026-04.md`
- `outputs/monthly/No_37_Cafe_2026-04.md`
- `outputs/monthly/Peppers_2026-04.md`
- `outputs/monthly/Sushi_Land_2026-04.md`
- `outputs/monthly/Wildwood_Kitchen_2026-04.md`
- `outputs/monthly/The_George_Hotel_2026-04.md`

Next-stage treatment:

1. Use these as regression examples for future report generation.
2. Extract common sections that should appear in client dashboards.
3. Keep long evidence appendices in PDF/export, not the main dashboard.
4. Do not delete until the new Firebase report/export pipeline reproduces equivalent value.

### 4.3 Prototype dashboard outputs

| Asset | Purpose | Next-stage treatment |
|---|---|---|
| `assets/operator-dashboards/lambs/latest.json` | Prototype dashboard snapshot, now report-aligned. | Migrate into Firebase as first protected client record. |
| `assets/operator-dashboards/*` | Static prototype dashboard snapshots. | Treat as temporary. Do not use as canonical client data after Firebase migration. |
| `operator-dashboard.html` | Prototype dashboard UI. | Reuse UI concepts, but move protected data reads to Firebase. |
| `operator/lambs.html` and `/operator/:venue` route | Prototype route. | Hide/redirect behind login before real client use. |

---

## 5. Companies House and risk-review assets

### 5.1 Existing assets

| Asset | Purpose | Next-stage treatment |
|---|---|---|
| `data/companies_house_risk_reviews.json` | Manual/company-risk review data. | Preserve and migrate into venue identity graph / entity risk model. |
| `scripts/run_v4_scoring_with_risk.py` | Runs V4 scoring with Companies House risk inputs and review audit support. | Reuse in monthly pipeline; refactor to write pipeline run summaries and Firebase records. |
| `*_companies_house_risk.json` / `*_companies_house_review_audit.json` patterns | Risk input/output patterns used by pipeline. | Preserve naming pattern or migrate into structured Firebase storage. |

### 5.2 Companies House product role

Companies House should be used for:

- legal-entity status;
- dissolution/liquidation/administration risk;
- accounts overdue risk;
- director churn risk;
- entity matching confidence;
- public-risk annotation in reports.

Companies House should **not** be used as a direct restaurant-quality signal.

Correct framing:

> Companies House contributes entity-risk and trading-confidence context, not food or service quality.

---

## 6. Entity resolution, aliases and guardrails

### 6.1 Existing assets

| Asset | Purpose | Next-stage treatment |
|---|---|---|
| `data/entity_aliases.json` | Manual trading-name to FHRSID alias table. | Migrate into canonical venue identity graph. Keep source-scoping. |
| `data/known_missing_*_venues.json` | Guardrails for high-confidence venues missing from canonical source slices. | Preserve as temporary guardrails until canonical data includes those venues. |
| `data/public_ranking_overrides.json` | Include/exclude/rename safety valve. | Preserve with audit trail and reviewer fields. |
| `*_entity_resolution_report.json` | Entity/Google duplicate/ambiguity reports. | Reuse in admin place-review queue and coverage certificates. |
| `scripts/check_market_readiness.py` | Deterministic market readiness checker. | Reuse/refactor to write Firebase `marketReadiness` records. |
| `assets/market-readiness/*.json` | Current static readiness outputs. | Migrate into Firebase admin records; retain public-safe summary for coverage pages. |

### 6.2 Existing lessons that must survive

1. The Vintner issue proved that missing venues must be solved canonically, not hidden by guardrails.
2. Alias checks must be source-aware so Stratford aliases do not block Leamington.
3. Duplicate Google Place IDs must be reviewed rather than silently ranked.
4. Multi-tenant sites, private canteens and service-station units need explicit treatment.
5. Known-missing guardrails should be temporary and retired after canonical fixes.

---

## 7. Public ranking, search and market pages

### 7.1 Existing public surfaces

| Asset | Purpose | Next-stage treatment |
|---|---|---|
| `rankings.html` | Market index / live markets. | Reuse, but add coverage certificate display and stable methodology labels. |
| `rankings/stratford-upon-avon.html` | Public ranking page. | Reuse/refactor with coverage and confidence explanation. |
| `search-v2.html` | Rank-board search with autocomplete and UK fallback. | Reuse UI concept. Ensure it searches canonical public markets and handles all UK fallback gracefully. |
| `uk-establishments.html` | Wider UK lookup using Firebase Realtime Database. | Preserve as public lookup, but ensure Firebase rules allow only intended public data. |
| `methodology.html` | Public methodology page. | Rewrite once methodology is stable; remove transitional internal confusion. |
| `for-restaurants.html` | Operator landing page. | Reuse positioning but update to authenticated SaaS/client portal language. |

### 7.2 Public ranking lessons

1. Public ranking needs Top 30 overall and category lists, not just Top 10.
2. Deterministic tie-breaks are required.
3. Public ranking and operator intelligence may use different geographic contexts.
4. The product must explain whether a view is town-centre public ranking or wider operator market context.
5. Search must work across all UK, but only fully scored markets should show RCS/ranking claims.

---

## 8. Pipeline and workflow assets

### 8.1 Existing workflow/pipeline assets

| Asset | Purpose | Next-stage treatment |
|---|---|---|
| `scripts/run_market_pipeline.py` | Generic repo-driven market pipeline wrapper. | Reuse as orchestration base; extend to collect/enrich sources and write Firebase/pipeline run summaries. |
| `.github/workflows/run_market_pipeline.yml` | Market pipeline workflow. | Reuse, but add cost logging, dry-run/publish separation and admin approval. |
| `scripts/build_area_rankings_v4.py` | Builds market area ranking JSON. | Reuse/refactor for public asset generation. Preserve index merge fix. |
| `scripts/generate_market_readiness.py` | Generates readiness assets. | Reuse/refactor to emit Firebase and coverage records. |
| `.github/workflows/generate_operator_dashboards.yml` | Generates prototype operator dashboard assets. | Retire once Firebase dashboard generation is canonical, but reuse tests and logic. |
| `scripts/generate_operator_dashboards.py` | Static dashboard generator with history support. | Migrate logic into Firebase snapshot generation. |
| `scripts/apply_dashboard_report_alignment.py` | Applies report-aligned facts to generated dashboards. | Keep as temporary bridge; later replace with report-aligned dashboard data model. |

### 8.2 Pipeline lessons

1. Single-market runs must not overwrite unrelated market indexes.
2. Market config must separate data-source geography from public diner geography.
3. New towns require source data collection, not just ranking generation.
4. Pipeline outputs must distinguish blocked, warning and ready states.
5. Monthly refreshes need cost logging and API call accounting.

---

## 9. Design and UX assets

### 9.1 Existing assets

| Asset | Purpose | Next-stage treatment |
|---|---|---|
| `assets/daydine.css` | Shared design system. | Reuse. Avoid redesign unless necessary. |
| `assets/daydine.js` | Shared nav behaviour. | Reuse/refactor into app shell if moving to Firebase Hosting. |
| `index.html` | Homepage. | Update with Client Login and refined SaaS positioning. |
| `admin-reports.html` | Static internal report library. | Migrate to authenticated admin report module. |
| `admin-markets.html` | Static readiness/admin market page. | Migrate to authenticated admin market module. |

### 9.2 UX lessons

1. The client dashboard should feel premium and not expose every monitored signal.
2. Use "Monthly intelligence layer" rather than raw watchlist/evidence checklist.
3. Methodology should carry the technical burden, not the dashboard.
4. Public pages need confidence and coverage explanations without overwhelming diners.
5. Admin screens can be technical; client screens should be commercial and concise.

---

## 10. Tests and QA assets

### 10.1 Existing tests

| Asset | Purpose | Next-stage treatment |
|---|---|---|
| `tests/test_market_data_integrity.py` | Checks entity aliases/known-missing guardrails. | Preserve and expand for source-scoped aliases and coverage certificates. |
| `tests/test_run_market_pipeline.py` | Tests generic pipeline behaviour. | Preserve and expand for new markets and dry-run/publish split. |
| `tests/test_generate_operator_dashboards.py` | Tests dashboard generation and movement logic. | Reuse for Firebase snapshot generation tests. |
| `tests/test_collect_tripadvisor_apify.py` | TripAdvisor collection test coverage. | Preserve if using Apify/metadata path; review legal/terms suitability. |

### 10.2 Tests to add

1. Firebase security rules tests.
2. Client cannot access another client's venue.
3. Admin-only writes enforced.
4. Coverage certificate counts reconcile to source records.
5. Ambiguous entity groups cannot enter primary rankable output unless accepted.
6. Companies House dissolved/liquidation caps applied correctly.
7. Google/Tripadvisor API call budget counters work.
8. Public rankings do not include Profile-only-D venues.
9. Public methodology label matches generated scoring version.
10. V4/V5 comparison artifacts are generated and reviewed.

---

## 11. Items that should be migrated into the professional roadmap

The roadmap should explicitly absorb the following prior work:

### 11.1 Into Stage 1 / Firebase Auth

- Keep static admin/operator pages as prototype only.
- Add Firebase rules based on current public lookup Firebase use.

### 11.2 Into Stage 2 / Protected client dashboards

- `assets/operator-dashboards/lambs/latest.json`
- `operator-dashboard.html`
- `scripts/generate_operator_dashboards.py`
- `scripts/apply_dashboard_report_alignment.py`
- Lambs full report and revenue opportunity examples.

### 11.3 Into Stage 3 / Admin console

- `admin-markets.html`
- `admin-reports.html`
- `assets/market-readiness/*.json`
- `assets/operator-reports/manifest.json`
- ambiguous Google Place review display.

### 11.4 Into Stage 4 / Coverage certificates and entity graph

- `data/entity_aliases.json`
- `data/known_missing_*_venues.json`
- `data/public_ranking_overrides.json`
- `*_entity_resolution_report.json`
- Vintner canonical fix work.

### 11.5 Into Stage 5 / Monthly refresh

- `scripts/run_market_pipeline.py`
- `.github/workflows/run_market_pipeline.yml`
- `scripts/build_area_rankings_v4.py`
- `scripts/generate_market_readiness.py`
- Google/TripAdvisor collection scripts under `.github/scripts/` where applicable.

### 11.6 Into Stage 6 / V5 methodology

- `docs/DayDine-V4-Scoring-Spec.md`
- `docs/DayDine-V4-Scoring-Comparison.md`
- `docs/DayDine-V4-Migration-Note.md`
- `compare_v3_v4.py`
- `rcs_scoring_v4.py`
- `rcs_scoring_stratford.py`

### 11.7 Into Stage 8 / SaaS readiness

- `operator_intelligence/revenue_opportunity.py`
- `operator_intelligence/v4_report_generator.py`
- `operator_intelligence/v4_action_cards.py`
- report/export examples.

---

## 12. Reuse/retire rules for future development

Before changing any major subsystem, apply this checklist:

```text
1. Which existing files solve part of this already?
2. Which generated outputs prove prior behaviour?
3. Which tests protect the existing behaviour?
4. Is this a migration, refactor, replacement or deletion?
5. If replacing, what is the migration path?
6. If deleting, what evidence shows it is obsolete?
7. Does the public methodology need updating?
8. Does the operator report/dashboard wording need updating?
9. Does the admin QA workflow need updating?
10. Do we need a new comparison artifact?
```

No future implementation stage should ignore existing report/scoring/pipeline work unless it explicitly records why.

---

## 13. Immediate recommended follow-up

Update `docs/DayDine-Professional-SaaS-Roadmap.md` so it includes this rule:

> Every stage must begin by checking `docs/DayDine-Prior-Work-Inventory.md` and deciding which prior assets are reused, migrated, refactored, archived or retired.

Then create:

```text
docs/DayDine-Launch-Readiness.md
docs/ADR-001-Public-Static-Plus-Firebase-SaaS.md
```

These should reference this inventory directly.
