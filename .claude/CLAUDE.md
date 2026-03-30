# DayDine Project State

## What It Is
UK restaurant tracking and ranking platform. MVP shows 264,791 FSA establishments searchable by local authority, business type, rating, and name. Phase 2 adds Google Places enrichment (ratings, review counts, price level). Future phases: TripAdvisor, editorial data, and composite Evidtrace scoring (RCS 0-10).

## Product Vision & Strategy

### Core Thesis
A data-driven awards platform for consumers that gives diners something they can't get from Google, OpenTable, the Good Food Guide or the National Restaurant Awards. Existing incumbents own the "where should I eat?" moment - a copy-and-paste aggregator would be swamped. We must reframe the problem: not "how do we re-build TripAdvisor?" but "what do diners wish existing awards and review sites did better?"

### Competitive Landscape
- **Good Food Guide Best Local Restaurants** - reader nominations + anonymous inspections + editor selection. Builds trust but produces yearly static list, not data-driven.
- **National Restaurant Awards** - 200+ panel of chefs/writers/restaurateurs vote for top-100. Prestige from panel, not data.
- **Datassential 500** - US programme using proprietary sales data, predictive analytics, consumer sentiment for chains. Industry-facing, not consumer.
- **Gap**: No existing service provides up-to-date, data-rich, transparent consumer-facing rankings.

### Available Signals
- UK footfall data is region-level only (BT Active Intelligence). Granular foot-traffic (Huq, O2 Motion) is expensive.
- FSA hygiene scores are public but "not a guide to food quality" - compliance signal only.
- Review platforms strongly influence consumer behaviour - scoring model relies on ratings and review velocity.
- Hygiene, price bands, social media sentiment as secondary signals.
- Proprietary signals (reservations, covers, footfall) require restaurant data sharing - pushes towards operator-facing model.

### Differentiation Strategy
1. **Dynamic real-time awards** - weekly/monthly "most improved" and "rising star" based on review velocity, hygiene updates, menu innovation. Makes site habit-forming.
2. **Theme-based rankings** - "best sustainable restaurants", "hidden gems in towns under 50k residents", measurable sustainability/inclusivity metrics.
3. **Transparent scoring methodology** - publish weights and data sources, invite independent auditors or food writers to review method.
4. **User-nominated awards with data checks** - reader nominations ranked by algorithm. Automates Good Food Guide's nominations+inspections process.
5. **Interactive explorer** - filter by value-for-money, creativity, consistency, neighbourhood, trendiness. Big movers, under-rated spots, consistency over time.

### Commercial Model
- **Revenue**: Members' club model (paid app for full rankings/perks) over advertising to protect neutrality. Restaurants pay for analytics/feedback without influencing ranking.
- **Credibility**: Google Place API terms forbid caching - fetch ratings on demand. Invest in moderation and fake-review detection.
- **Distribution**: Partnerships with travel/lifestyle media. Viral hook: "sustainable dining scorecards".
- **Long-term**: Treat as niche media product, evolve towards B2B analytics once scoring system proven.

### Verdict
Standalone consumer awards site works only if materially different from existing guides. Must be data-rich, regularly updated, transparent, theme-based and interactive. Commercial upside modest vs B2B intelligence.

## Architecture
- Frontend: Single index.html (static) on Vercel at daydine.vercel.app
- Database: Firebase RTDB at https://recursive-research-eu-default-rtdb.europe-west1.firebasedatabase.app under /daydine path
- Firebase project: recursive-research-eu (Spark plan, europe-west1)
- GitHub: jono8001/daydine (auto-deploys to Vercel on push to main)

## What's Built & Deployed
- index.html: Consumer-facing frontend with warm cream (#F5F0E8) theme, amber (#D4942A) accents, Inter font, DayDine branding with amber dot on 'i'
- firebase-rules.json: Public read on /daydine, no public write, indexes on establishments child (la/t/r/pc/n)
- vercel.json: Static site config with SPA fallback
- Firebase web app registered as 'DayDine' with config values injected into index.html
- 264,791 FSA establishments uploaded to Firebase via firebase_upload.py (on local machine)

## Data Schema (per record in /daydine/establishments/{id})
### FSA fields (compact)
- n = name
- a = address
- la = local authority
- pc = postcode
- rd = last inspection date (ISO format, e.g. "2023-04-26T00:00:00")
- t = business type (numeric code)
- r = FSA rating (0-5, may not be present on all records)
- id = FSA establishment ID
- lat/lon = coordinates

### Google Places fields (added by enrich_places.py)
- gid = Google place_id
- gr = Google rating (1.0-5.0)
- grc = Google review count
- gpl = Google price level (e.g. "PRICE_LEVEL_MODERATE")
- gt = Google types array (e.g. ["restaurant", "food", "point_of_interest"])
- goh = Google opening hours (weekday descriptions array)

## Phase 2: Google Places Enrichment
### Setup
- API key: Google Places API (New) key, restricted to Places API only
- Stored in: .env file (GOOGLE_PLACES_API_KEY) — NOT committed to git
- Script: enrich_places.py in repo root

### Usage
```bash
# Install dependencies
pip install requests firebase-admin python-dotenv

# Dry run for a single LA (search but don't write)
python enrich_places.py --la "Camden" --dry-run

# Enrich a single LA
python enrich_places.py --la "Camden"

# Enrich with a limit (e.g. first 50 only)
python enrich_places.py --la "Camden" --limit 50
```

### How it works
1. Queries Firebase for all establishments in the given LA
2. For each establishment without a gid (not yet enriched), calls Google Places Text Search
3. Matches using: "{name}, {address}, {postcode}, UK"
4. Writes enriched fields (gr, grc, gpl, gt, gid, goh) back to the establishment record
5. Rate-limited to 10 requests/sec, backs off on 429 errors
6. Skips already-enriched records (those with gid field)

## Local Files (C:\Users\Jon Swaby\Projects\Daydine)
- fsa_agent.py: Pulls FSA data from api.ratings.food.gov.uk
- consolidate_fsa.py: Merges FSA JSON files into daydine-data.json (61MB)
- firebase_upload.py: Uploads daydine-data.json to Firebase RTDB
- daydine-data.json: 264,791 consolidated records
- fsa_data/: Raw FSA API responses

## Reference Documents (in evidtrace-agents folder)
- UK-Restaurant-Tracker-Plan.docx: Feasibility plan with data sources, scoring weights, architecture, MVP scope, timeline
- UK-Restaurant-Tracker-Methodology-Spec.docx: Formal mathematical model for RCS scoring (weighted aggregation, convergence adjustment, temporal decay, penalty rules, calibration)

### RCS computed field (added by restaurant_confidence.py)
- rcs = Restaurant Confidence Score (0.0-10.0)

## RCS Composite Scoring Engine
### Formula
```
RCS = C(n) * sum(w_i * S_i(t)) - P
```
- S_i(t) = source score (0-10) with temporal decay: S * 2^(-age_days / half_life)
- w_i = source weight, renormalised across available sources
- C(n) = convergence adjustment: 1 - e^(-n), rewards multi-source coverage
- P = penalty deductions for critical violations (FSA 0 or 1)

### Source weights (base, renormalised when sources missing)
- FSA: 0.30 — hygiene rating 0-5 mapped to 0-10, half-life 730 days
- Google: 0.30 — rating 1-5 mapped to 0-10, volume-adjusted by log10(reviews), half-life 365 days
- TripAdvisor: 0.20 — (Phase 3 placeholder)
- Editorial: 0.10 — (Phase 3 placeholder)
- Recency: 0.10 — (Phase 3 placeholder)

### Usage
```bash
# Score a single establishment
python restaurant_confidence.py --id <firebase_key> --dry-run

# Score all in a local authority
python restaurant_confidence.py --la "Camden" --dry-run

# Score and write rcs field to Firebase
python restaurant_confidence.py --la "Camden"
```

## What's Next (Phase 2 remaining + Phase 3)
1. Run enrich_places.py for London boroughs first, then expand
2. Display RCS score in index.html alongside FSA + Google ratings
3. TripAdvisor integration (add ta_rating, ta_review_count fields)
4. Editorial scanning via Brave Search API (add ed_sentiment, ed_count fields)
5. Expandable detail rows with full RCS score breakdown
6. Tier assignment (Exceptional/Recommended/Acceptable/Caution/Avoid)

## Environment
- Windows 11, Python 3.x
- Firebase credentials: C:\Users\Jon Swaby\OneDrive\Documents\evidtrace-agents\firebase_credentials.json
- Database URL env var: FIREBASE_DATABASE_URL
- Google Places API key: in .env (GOOGLE_PLACES_API_KEY)
