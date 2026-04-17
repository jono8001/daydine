# DayDine

UK hospitality intelligence. Restaurant rankings built on public market signals.

DayDine ranks UK restaurants using the **Restaurant Confidence Score (RCS)** — a composite 0–10 metric derived from public market signals. The V4 framework (current) is built from three weighted components: Trust & Compliance (40%, FSA/FHRS), Customer Validation (45%, platform rating metadata with Bayesian shrinkage), and Commercial Readiness (15%, customer-path signals). The V3.4 engine runs in parallel during migration for comparison; public leaderboards will cut over to V4 once calibration completes.

**Live at [daydine.vercel.app](https://daydine.vercel.app)**

## Product

| Surface | Description |
|---|---|
| **Market Rankings** | Ranked leaderboards by Local Authority area. Category filters, convergence indicators, confidence bands. |
| **Restaurant Search** | Search 264,791 UK establishments by town, city, or postcode. FSA hygiene ratings, Google scores, inspection data. |
| **Operator Reports** | Position & Competitor Report (£49 one-time / £39/month). Competitive benchmark, gap analysis, prioritised actions. |
| **Methodology** | Full documentation of scoring principles, data sources, confidence handling, and update logic. |

## Coverage

Stratford-upon-Avon is the first fully ranked market (190 venues). Additional markets are added as data pipelines — FSA, Google Places, TripAdvisor, Companies House — are validated for each Local Authority area.

Pipeline markets are tracked in `/assets/rankings/index.json`.

## Tech Stack

- **Frontend**: Static HTML/CSS/JS deployed on Vercel. No build step.
- **Design system**: `assets/daydine.css` — shared tokens, components, responsive breakpoints.
- **Data**: Firebase Realtime Database (264K establishments), JSON rankings files.
- **Scoring engines**: `rcs_scoring_v4.py` (V4, current) and `rcs_scoring_stratford.py` (V3.4 legacy, runs in parallel for comparison). Python 3.11. Comparison harness: `compare_v3_v4.py`.
- **Data collection**: GitHub Actions workflows for FSA, Google Places, TripAdvisor, editorial, and enforcement data.

## Repo Structure

```
/                           Static site root (Vercel serves from here)
├── index.html              Homepage — UK hospitality intelligence positioning
├── rankings.html           Market index — active markets, pipeline, featured leaderboard
├── rankings/
│   └── stratford-on-avon.html  Market leaderboard with filters and convergence
├── search.html             UK restaurant database (264K establishments, Leaflet map)
├── reports.html            Operator intelligence — Position & Competitor Reports
├── methodology.html        Scoring methodology, principles, data sources
├── pricing.html            Pricing tiers and comparison (noindex)
├── for-restaurants.html    Cold outreach landing page (noindex)
├── sample.html             Sample report viewer/download
├── 404.html                Error page
├── assets/
│   ├── daydine.css         Shared design system
│   ├── daydine.js          Shared nav behaviour + hamburger toggle
│   ├── daydine-logo.png    Brand mark
│   ├── favicon.svg         Favicon
│   ├── rankings/
│   │   ├── index.json      Market registry (available + pipeline)
│   │   └── stratford-on-avon.json  Venue rankings data
│   └── reports/
│       └── daydine-sample-report.pdf
├── rcs_scoring_v4.py          V4 scoring engine (current framework)
├── rcs_scoring_stratford.py   V3.4 scoring engine (legacy, parallel during migration)
├── compare_v3_v4.py           V3.4 vs V4 comparison harness
├── docs/
│   ├── DayDine-Scoring-Methodology.md   Public methodology (V4)
│   ├── DayDine-V4-Scoring-Spec.md       Implementation spec (V4)
│   ├── DayDine-V4-Scoring-Comparison.md V3.4 vs V4 diagnostics
│   └── DayDine-V4-Migration-Note.md     Migration guidance
├── .github/
│   ├── scripts/            Data collection + enrichment scripts
│   └── workflows/          GitHub Actions pipelines
└── vercel.json             Deployment config (cleanUrls, rewrites)
```

## Design System

The shared design system (`assets/daydine.css`) provides:

- **Tokens**: Porcelain surfaces, graphite text, burnished gold accent, RCS band palette, neutral shadows, spacing scale
- **Components**: Nav (with mobile hamburger), footer (4-column grid), cards, score badges, rank tables, filter bars, convergence indicators, proof bars, FAQ accordions, checklists, market cards
- **Responsive**: Mobile-first breakpoints at 980px, 760px, 440px. Rank tables collapse to cards, filters scroll horizontally, footer stacks.
- **Accessibility**: Skip links, focus-visible states, WCAG AA contrast, semantic landmarks

## Scoring (RCS V4)

Three-component structure: **Trust & Compliance** (40%, FSA/FHRS only), **Customer Validation** (45%, Bayesian shrinkage on Google + TripAdvisor + OpenTable rating metadata), **Commercial Readiness** (15%, public customer-path signals). Fixed weights — missing components do not renormalise, they reduce the confidence class.

Capped Michelin + AA distinction modifier (+0.30). Companies House penalties and caps. Four-class confidence/rankability gating (Rankable-A / Rankable-B / Directional-C / Profile-only-D) decides league-table eligibility.

Review-text sentiment, aspect sentiment, AI summaries, photo count, price level, place types, social presence, and the cross-source convergence bonus are **not** in the headline score — they are report-only (some) or excluded entirely (some). Full spec: `docs/DayDine-V4-Scoring-Spec.md`. Public methodology: `docs/DayDine-Scoring-Methodology.md`.

### V3.4 legacy (parallel during migration)

V3.4 (`rcs_scoring_stratford.py`) still runs on each pipeline invocation to produce side-by-side comparison artifacts. Its 40-signal / 7-tier output (`stratford_rcs_scores.csv`, `stratford_rcs_summary.json`, `stratford_rcs_report.md`) is retained for audit only — public leaderboards will migrate to V4 once calibration completes. See `docs/DayDine-V4-Migration-Note.md`.
