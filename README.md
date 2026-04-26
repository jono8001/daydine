# DayDine

UK hospitality intelligence. Restaurant rankings built on public market signals.

DayDine ranks UK restaurants using the **Restaurant Confidence Score (RCS)** — a composite 0–10 metric derived from public market signals. The V4 framework is the current scoring framework, built from three weighted components: Trust & Compliance (40%, FSA/FHRS), Customer Validation (45%, platform rating metadata with Bayesian shrinkage), and Commercial Readiness (15%, customer-path signals). The V3.4 engine remains available for audit/comparison during migration.

**Live at [daydine.vercel.app](https://daydine.vercel.app)**

## Product

| Surface | Description |
|---|---|
| **Market Rankings** | Public leaderboards for fully scored markets. Top 30 overall, category lists, confidence bands and deterministic tie-breaks. |
| **Rank-board Search** | `/search` serves the ranked-market search experience from `search-v2.html`. It searches fully scored markets and sends wider-area queries to the UK lookup. |
| **UK Establishment Lookup** | `/uk-establishments` searches wider UK establishment records by town, city, borough, local authority or postcode. These are partial records until a market is fully processed. |
| **Operator Reports** | Internal/generated operator intelligence reports and monthly tracking outputs. |
| **Admin Reports** | `/admin/reports` is a static internal report library. It is not authentication or CRM yet. |
| **Admin Markets** | `/admin/markets` is a read-only market-readiness view. New towns are still added through repo config and GitHub Actions. |
| **Methodology** | Documentation of scoring principles, data sources, confidence handling, and update logic. |

## Coverage

Stratford-upon-Avon is the first fully ranked public market. The configured public town area is defined in `data/ranking_areas.json` and currently uses a 4km town-centre radius over the Stratford-on-Avon source dataset. A wider Stratford-on-Avon District operator-only view is also configured.

Pipeline markets and live ranking outputs are tracked in `/assets/rankings/index.json`. New markets currently require a repo/GitHub Actions pipeline run; the admin page is read-only until an authenticated pipeline trigger is added.

## Tech Stack

- **Frontend**: Static HTML/CSS/JS deployed on Vercel. No build step.
- **Design system**: `assets/daydine.css` — shared tokens, components, responsive breakpoints.
- **Data**: Firebase Realtime Database for wider establishment lookup; committed JSON ranking and operator-report outputs for public/static pages.
- **Scoring engines**: `rcs_scoring_v4.py` (V4, current) and `rcs_scoring_stratford.py` (V3.4 legacy/audit). Python 3.11. Comparison harness: `compare_v3_v4.py`.
- **Data collection**: GitHub Actions workflows for FSA/Firebase base pulls, Google Places, TripAdvisor, Companies House, scoring, ranking generation and report QA.

## Repo Structure

```
/                              Static site root (Vercel serves from here)
├── index.html                 Homepage — UK hospitality intelligence positioning
├── rankings.html              Market index — active markets and pipeline markets
├── rankings/
│   └── stratford-upon-avon.html Public market leaderboard page
├── search.html                Legacy redirect/shim for /search
├── search-v2.html             Rank-board search for fully scored markets
├── uk-establishments.html     Wider UK establishment lookup
├── admin-reports.html         Static internal operator-report library
├── admin-markets.html         Read-only market-readiness admin view
├── methodology.html           Scoring methodology, principles, data sources
├── for-restaurants.html       Operator landing page and report preview
├── 404.html                   Error page
├── assets/
│   ├── daydine.css            Shared design system
│   ├── daydine.js             Shared nav behaviour + hamburger toggle
│   ├── rankings/
│   │   ├── index.json         Market registry
│   │   └── stratford-upon-avon.json Public venue rankings data
│   └── operator-reports/
│       └── manifest.json      Static report-library manifest
├── data/
│   ├── ranking_areas.json     Public/operator market geography config
│   ├── entity_aliases.json    Manual trading-name/FHRSID alias table
│   ├── public_ranking_overrides.json Public ranking include/exclude/rename safety valve
│   └── known_missing_*_venues.json Guardrails for high-confidence venues missing from canonical source slices
├── scripts/
│   ├── build_area_rankings_v4.py
│   ├── build_rankings_v4.py
│   ├── check_market_readiness.py
│   └── generate_v4_samples.py
├── tests/
│   ├── test_market_data_integrity.py
│   └── test_collect_tripadvisor_apify.py
├── rcs_scoring_v4.py          V4 scoring engine
├── rcs_scoring_stratford.py   V3.4 scoring engine retained for audit
├── docs/                      Methodology, ADRs, readiness notes and diagnostics
├── .github/
│   ├── scripts/               Data collection + enrichment scripts
│   └── workflows/             GitHub Actions pipelines and QA gates
└── vercel.json                Deployment config (clean URLs, rewrites, cache headers)
```

## Market pipeline model

The current market pipeline is config/repo driven:

1. Configure public/operator geography in `data/ranking_areas.json`.
2. Refresh the source establishment dataset through the appropriate GitHub Action.
3. Enrich FSA/FHRS, Google Places, Companies House and optional review-platform data.
4. Resolve entities and apply aliases/ambiguity handling.
5. Run `rcs_scoring_v4.py`.
6. Build public ranking JSON using `scripts/build_area_rankings_v4.py`.
7. Run QA with `python scripts/check_market_readiness.py --market <slug>`.
8. Review `/admin/markets` and public pages before selling/reporting against the market.

The admin market page is deliberately read-only. It should not trigger pipelines until authentication, permissions and dry-run/publish separation are implemented.

## Data integrity guardrails

- `data/entity_aliases.json` maps manually reviewed trading names to FHRSIDs.
- `data/known_missing_*_venues.json` records high-confidence venues that must not silently disappear when a trial slice or generated asset misses them.
- `tests/test_market_data_integrity.py` checks that aliases either exist in the canonical establishments file or are explicitly covered by a known-missing guardrail.
- `scripts/check_market_readiness.py` emits a deterministic JSON summary of market counts, warnings, alias gaps, known-missing venues and ambiguous Google Place groups.

Known-missing guardrails are temporary. They should be removed once the canonical establishment pull and generated ranking outputs include the venue naturally.

## Design System

The shared design system (`assets/daydine.css`) provides:

- **Tokens**: Porcelain surfaces, graphite text, burnished gold accent, RCS band palette, neutral shadows, spacing scale
- **Components**: Nav, footer, cards, score badges, rank tables, filter bars, convergence indicators, proof bars, FAQ accordions, checklists, market cards
- **Responsive**: Mobile-first breakpoints at 980px, 760px, 440px
- **Accessibility**: Skip links, focus-visible states, semantic landmarks

## Scoring (RCS V4)

Three-component structure: **Trust & Compliance** (40%, FSA/FHRS only), **Customer Validation** (45%, Bayesian shrinkage on Google + TripAdvisor + OpenTable rating metadata), **Commercial Readiness** (15%, public customer-path signals). Fixed weights — missing components do not renormalise; they reduce the confidence class.

Capped Michelin + AA distinction modifier (+0.30). Companies House penalties and caps. Four-class confidence/rankability gating (Rankable-A / Rankable-B / Directional-C / Profile-only-D) decides league-table eligibility.

Review-text sentiment, aspect sentiment and AI summaries are not in the headline score. They belong in report-only layers where used. Full spec: `docs/DayDine-V4-Scoring-Spec.md`. Public methodology: `docs/DayDine-Scoring-Methodology.md`.

### V3.4 legacy

V3.4 (`rcs_scoring_stratford.py`) is retained for audit/comparison. The public product should present one clear external methodology label, while internal comparison artifacts can retain V3.4/V4 naming for traceability.
