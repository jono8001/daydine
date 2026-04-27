# DayDine Roadmap Implementation Control

**Status:** Mandatory control note for future roadmap work  
**Created:** April 2026  
**Applies to:** `docs/DayDine-Professional-SaaS-Roadmap.md`

---

## 1. Purpose

This note prevents the professional SaaS rebuild from accidentally losing valuable work already completed in the DayDine repo.

The professional roadmap remains the main plan:

```text
docs/DayDine-Professional-SaaS-Roadmap.md
```

But every implementation stage must now be checked against:

```text
docs/DayDine-Prior-Work-Inventory.md
```

before coding begins.

---

## 2. Mandatory rule

Before implementing any roadmap stage, the implementer must answer:

```text
1. Which existing DayDine files already solve part of this stage?
2. Which report/methodology/pipeline outputs prove prior behaviour?
3. Which tests protect existing behaviour?
4. Which assets are reused as-is?
5. Which assets are migrated into Firebase or the new architecture?
6. Which assets are refactored?
7. Which assets are archived as legacy references?
8. Which assets are retired, and why?
9. Does the public methodology need updating?
10. Does the operator dashboard/report wording need updating?
```

No roadmap stage should proceed as a clean-room rebuild unless the implementation note explicitly says why prior work is not being reused.

---

## 3. Stage-by-stage prior-work checks

### Stage 1 — Firebase authentication and roles

Check prior assets:

- `uk-establishments.html` for existing Firebase browser integration.
- current static admin/operator pages that must become protected.
- any Firebase project config already used by public lookup.

Decision required:

- whether to continue hybrid Vercel + Firebase or move fully to Firebase Hosting.

---

### Stage 2 — Protected client dashboards

Check prior assets:

- `assets/operator-dashboards/lambs/latest.json`
- `operator-dashboard.html`
- `scripts/generate_operator_dashboards.py`
- `scripts/apply_dashboard_report_alignment.py`
- `outputs/examples/Lambs_full_operator_report_with_tracking_2026-04.md`
- `outputs/examples/Lambs_revenue_opportunity_rank_band_example_2026-04.md`

Decision required:

- which fields become the canonical Firebase dashboard schema;
- which report-aligned fields remain in dashboard vs PDF/export.

---

### Stage 3 — Admin operating console

Check prior assets:

- `admin-markets.html`
- `admin-reports.html`
- `assets/market-readiness/*.json`
- `assets/operator-reports/manifest.json`
- ambiguous Google Place review display in admin markets.

Decision required:

- which static admin JSON outputs move into Firebase;
- which remain public-safe generated summaries.

---

### Stage 4 — Coverage certificates and entity graph

Check prior assets:

- `data/entity_aliases.json`
- `data/known_missing_*_venues.json`
- `data/public_ranking_overrides.json`
- `*_entity_resolution_report.json`
- `scripts/check_market_readiness.py`
- Vintner canonical-fix history and guardrail resolution.

Decision required:

- canonical venue identity schema;
- how manual overrides are audited;
- how known-missing guardrails are retired.

---

### Stage 5 — Monthly low-cost refresh pipeline

Check prior assets:

- `scripts/run_market_pipeline.py`
- `.github/workflows/run_market_pipeline.yml`
- `scripts/build_area_rankings_v4.py`
- `scripts/generate_market_readiness.py`
- `scripts/run_v4_scoring_with_risk.py`
- Google/TripAdvisor collection scripts under `.github/scripts/` where applicable.

Decision required:

- how monthly pipeline cost logging is recorded;
- whether pipeline writes to committed JSON, Firebase, or both during transition;
- how dry-run, review and publish states work.

---

### Stage 6 — Methodology V5 prototype

Check prior assets:

- `docs/DayDine-V4-Scoring-Spec.md`
- `docs/DayDine-Scoring-Methodology.md`
- `docs/DayDine-V4-Scoring-Comparison.md`
- `docs/DayDine-V4-Migration-Note.md`
- `compare_v3_v4.py`
- `rcs_scoring_v4.py`
- `rcs_scoring_stratford.py`

Decision required:

- what remains V4;
- what becomes V5 experimental;
- which public claims are allowed before V5 validation.

---

### Stage 7 — Public methodology and trust layer

Check prior assets:

- `methodology.html`
- `docs/DayDine-Scoring-Methodology.md`
- `docs/DayDine-V4-Scoring-Spec.md`
- coverage/readiness outputs.

Decision required:

- final public wording for "top-ranked", "best-evidenced" and confidence classes;
- whether V3.4/V4 transition language remains internal only.

---

### Stage 8 — Client SaaS readiness

Check prior assets:

- `operator_intelligence/revenue_opportunity.py`
- `operator_intelligence/v4_report_generator.py`
- `operator_intelligence/v4_action_cards.py`
- `operator_intelligence/builders/*`
- report/export examples under `outputs/examples/`, `outputs/monthly/` and `samples/v4/monthly/`.

Decision required:

- what belongs in the dashboard;
- what belongs in PDF/export;
- what belongs in methodology;
- what should remain internal admin-only.

---

## 4. Required implementation note template

Every major implementation PR/commit series should include a short note using this structure:

```text
Roadmap stage:
Prior assets checked:
Assets reused:
Assets migrated:
Assets refactored:
Assets archived/retired:
Tests added/updated:
Methodology impact:
Client/admin security impact:
Remaining risks:
```

---

## 5. Immediate consequence

The next implementation step should not be written as:

```text
Build Firebase Auth from scratch.
```

It should be written as:

```text
Build Firebase Auth foundation, reusing the existing Firebase project/config pattern from uk-establishments.html, while protecting client/admin data with Firebase Auth and rules and preserving public lookup behaviour.
```

Likewise, the client dashboard migration should not be written as:

```text
Build a new client dashboard.
```

It should be written as:

```text
Migrate the existing report-aligned Lambs dashboard and operator intelligence report outputs into a protected Firebase-backed client dashboard, preserving the commercial substance of the prior report.
```

---

## 6. Control status

This document is mandatory for future DayDine professionalisation work until superseded by a formal product/engineering process.
