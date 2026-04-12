# DayDine

UK hospitality intelligence. Restaurant rankings built on public market signals.

DayDine ranks UK restaurants using the **Restaurant Confidence Score (RCS)** — a composite 0–10 metric derived from 40 public signals across 7 independent data tiers. The scoring methodology is transparent, the rankings are updated weekly, and the formula is intentionally not published.

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
- **Scoring engine**: `rcs_scoring_stratford.py` — Python 3.11, V3.4 RCS pipeline.
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
├── rcs_scoring_stratford.py    V3.4 scoring engine
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

## Scoring (RCS V3.4)

40 signals across 7 tiers: FSA (23%), Google (24%), Online Presence (13%), Operational (15%), Menu & Offering (10%), Reputation (8%), Companies House (penalty-only). Temporal decay, cross-source convergence, 18 penalty rules, unique tiebreakers. Full documentation in `methodology.html` and `.claude/CLAUDE.md`.
