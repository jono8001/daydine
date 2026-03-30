# DayDine Project State

## What It Is
UK restaurant tracking and ranking platform. MVP shows 264,791 FSA establishments searchable by location (town/city/postcode), with distance-based results, interactive Leaflet map, and tier badges. Phase 2 adds Google Places enrichment. Phase 3 implements the full Evidtrace RCS composite scoring engine.

## Current State (30 March 2026)

### Live Features (daydine.vercel.app)
- Location-based search using postcodes.io (type town, city or postcode)
- Place autocomplete suggestions as you type
- Distance-based results sorted by proximity (Haversine formula)
- Distance dropdown filter (1/3/5/10/25 miles)
- Interactive Leaflet map with colour-coded markers by FSA rating
- Table/Map toggle view
- Expandable detail rows (address, FSA sub-scores, Google data when available)
- Tier badges based on FSA rating (Excellent/Good/Generally Satisfactory/Improvement Necessary/Major Improvement/Urgent Improvement)
- Mobile-responsive layout
- DayDine branding with Beta badge
- Near Me geolocation button

### Repository Files
- `index.html` — Single-page app (Firebase + Leaflet + postcodes.io)
- `enrich_places.py` — Google Places enrichment script (ready to run locally)
- `restaurant_confidence.py` — RCS scoring engine (NEEDS FULL REWRITE - see below)
- `firebase-rules.json` — Realtime Database rules
- `vercel.json` — Deployment config

### Firebase Structure
- `establishments/{la_name}/{index}` — FSA data with fields: n (name), a1/a2/a3/a4 (address), pc (postcode), la (local authority), bt (business type), rv (rating value), rd (rating date), lat, lng, fhrsid
- `la_index/{la_name}` — Local authority index for search
- Google enrichment fields (when populated): gr (Google rating), grc (Google review count), gpl (price level), gty (types), goh (opening hours), gpid (place ID)

## Product Vision & Strategy

### Core Thesis
A data-driven awards platform for consumers that gives diners something they can't get from Google, OpenTable, the Good Food Guide or the National Restaurant Awards. We must reframe the problem: not "how do we re-build TripAdvisor?" but "what do diners wish existing awards and review sites did better?"

### Competitive Landscape
- **Good Food Guide** — reader nominations + anonymous inspections. Yearly static list, not data-driven.
- **National Restaurant Awards** — 200+ panel vote for top-100. Prestige from panel, not data.
- **Datassential 500** — US, proprietary sales data for chains. Industry-facing, not consumer.
- **Gap**: No existing service provides up-to-date, data-rich, transparent consumer-facing rankings.

### Differentiation Strategy
1. **Dynamic real-time awards** — weekly/monthly "most improved" and "rising star"
2. **Theme-based rankings** — "best sustainable restaurants", "hidden gems in towns under 50k"
3. **Transparent scoring methodology** — publish weights and data sources
4. **User-nominated awards with data checks** — reader nominations ranked by algorithm
5. **Interactive explorer** — filter by value-for-money, creativity, consistency, trendiness

### Commercial Model
- **Revenue**: Members' club model over advertising to protect neutrality
- **Credibility**: Google Place API terms forbid caching - fetch on demand
- **Distribution**: Partnerships with travel/lifestyle media
- **Long-term**: Niche media product, evolve towards B2B analytics

---

## TASK BACKLOG (Priority Order)

### PRIORITY 1: UI Fixes (Next Claude Code Session)

#### Task 1.1: Map View Button Refactor
- Rename "Near Me" button to "Map View"
- When clicked: toggle between table and map view for current search results
- If no search done yet: show message "Search for a location first"
- Remove the separate Table/Map toggle buttons (replaced by Map View button)
- Move geolocation (GPS detect) into the Location input field as a small location pin icon inside the field (like Google Maps search bar)

#### Task 1.2: Hide Empty Google Column
- Hide the "GOOGLE" column in results table when no establishments in current results have Google data (gr field)
- Show column automatically once enrichment data exists
- Avoids confusing users with a column of dashes

#### Task 1.3: Fix Tier Badges
- Current tier badges are based ONLY on FSA hygiene rating — this is WRONG for the final product
- Interim: keep FSA-based badges but label them clearly as "FSA Hygiene" not just "Tier"
- Future: replace with RCS-based tiers once scoring engine is complete (see Priority 3)

### PRIORITY 2: Data Enrichment

#### Task 2.1: Run Google Places Enrichment (LOCAL — not Claude Code)
- Run `enrich_places.py` locally for London boroughs first
- Command: `python enrich_places.py --la "Camden" --dry-run` (test first)
- Then: `python enrich_places.py --la "Camden"` (for real)
- Work through all London LAs, then expand nationally
- Requires GOOGLE_PLACES_API_KEY in .env

#### Task 2.2: Upload Methodology Spec to Repo
- Add `UK-Restaurant-Tracker-Methodology-Spec.docx` to repo (or convert to .md)
- Claude Code needs this as reference for the scoring engine rewrite

### PRIORITY 3: Scoring Engine — FULL REWRITE of restaurant_confidence.py

The current `restaurant_confidence.py` is a basic scaffold that does NOT implement the methodology spec. It must be completely rewritten to implement the full Evidtrace 7-stage pipeline.

#### RCS Methodology Spec Summary (from UK-Restaurant-Tracker-Methodology-Spec.docx)

**Source Credibility Priors (SCP):**
| Source | SCP | Update Freq |
|---|---|---|
| FSA Food Hygiene | 0.92 | Inspection-driven |
| Google Places | 0.72 | Real-time |
| TripAdvisor | 0.68 | Real-time |
| Michelin/Good Food Guide | 0.90 | Annual |
| Local Press/Food Critics | 0.75 | Irregular |
| Environmental Health Records | 0.94 | Event-driven |

**Signal Normalisation (all to 0-10 scale):**
- FSA: `(hygiene_rating / 5) * 10`
- Google: `(star_rating / 5) * 10`
- TripAdvisor: `(star_rating / 5) * 10`
- Editorial: award tier score (Michelin 3→10, 2→9, 1→8, Bib→7; GFG proportional)
- Enforcement: `10 - (penalty_count * severity_weight)`

**Category Weights:**
| Signal Category | Weight | Rationale |
|---|---|---|
| Food Hygiene (FSA) | 0.20 | Statutory safety baseline |
| Primary Review (Google) | 0.25 | Largest review corpus |
| Secondary Review (TripAdvisor) | 0.12 | Tourist-skewed but useful for convergence |
| Editorial Recognition | 0.18 | Expert judgment, high signal-to-noise |
| Review Consistency | 0.15 | Penalises high variance across sources |
| Recency Trend | 0.10 | Temporal weighting recent vs historical |

**7-Stage Scoring Pipeline:**
1. **NORMALISE** — Raw signals to 0-10 scale
2. **TEMPORAL DECAY** — `T_weight(t) = e^(-λt)` where λ=0.0023 (300-day half-life). Signals >18 months flagged stale. >24 months excluded.
3. **PENALTY RULES** — 16+ rules across 5 groups (Review Integrity, Hygiene, Editorial, Consistency, Temporal). Multipliers 0.60x to 1.05x boost. Anti-accumulation cap: 4 most severe at full weight, additional at 0.95x each.
4. **WEIGHTED AGGREGATION** — `RCS_base = Σ(w_i * SCP_i * S_i) / Σ(w_i * SCP_i)`
5. **CONVERGENCE ADJUSTMENT** — Pairwise divergence matrix with source-pair credibility weighting. `C_factor = 1.0 - α * D_weighted` where α=0.15. Divergence flags: HYGIENE-RATING SPLIT, REVIEW PLATFORM CONFLICT, EDITORIAL ORPHAN, STALE CONSENSUS.
6. **CALIBRATION CORRECTION** — Ground-truth cases (known-excellent, known-problematic, known-mid-range). Target: correct+close ≥ 75%.
7. **TIER ASSIGNMENT** — Exceptional (8.5-10), Recommended (7.0-8.4), Acceptable (5.0-6.9), Caution (3.0-4.9), Avoid (0.0-2.9). Confidence bands widen as scores decrease.

**Penalty Rules (16+ rules):**
- Review Integrity: fake review spike (0.75x), review bombing (0.80x), owner response rate (1.03x boost), low review volume (0.90x)
- Hygiene: FSA rating decline (0.80x), enforcement action (0.60x), score improvement post-action (0.95x), awaiting inspection (0.88x)
- Editorial: award recency >2yr (0.90x), multi-guide recognition (1.05x boost), guide delisting (0.78x)
- Consistency: rating-hygiene divergence (0.85x), platform divergence (0.88x), sentiment-rating mismatch (0.90x)
- Temporal: declining trend (0.88x), improving trend (1.04x boost), new establishment <6mo (0.92x)

### PRIORITY 4: UI Updates Post-Scoring Engine

#### Task 4.1: RCS Score Display
- Replace current FSA-only tier badges with RCS-based tiers
- Show RCS score (0-10) as primary metric in results
- Show confidence level (High/Medium/Low)
- Expandable details show: individual source scores, divergence flags, penalties applied, score breakdown

#### Task 4.2: Map Colours Based on RCS
- Update map marker colours to use RCS tiers instead of FSA rating
- Exceptional=green, Recommended=teal, Acceptable=amber, Caution=orange, Avoid=red

### PRIORITY 5: Additional Data Sources

#### Task 5.1: TripAdvisor Integration
- Add ta (TripAdvisor rating), trc (review count) fields to Firebase schema
- Build enrichment script similar to enrich_places.py

#### Task 5.2: Editorial Scanning
- Brave Search API for editorial mentions/reviews
- Michelin/Good Food Guide recognition data

#### Task 5.3: Environmental Health Records
- FSA enforcement actions data

### PRIORITY 6: Calibration Framework
- Build calibration case set (known-excellent, known-problematic, known-mid-range restaurants)
- Implement accuracy metrics (correct + close ≥ 75%)
- Calibration feedback loop for rule adjustment

---

## Environment Variables Required
- `GOOGLE_PLACES_API_KEY` — For enrich_places.py
- Firebase config is embedded in index.html (public read-only)

## Tech Stack
- Frontend: Vanilla HTML/CSS/JS, Firebase Realtime Database, Leaflet.js, postcodes.io API
- Backend scripts: Python (enrich_places.py, restaurant_confidence.py)
- Hosting: Vercel (auto-deploys from main branch)
- Database: Firebase Realtime Database (recursive-research-eu project)
