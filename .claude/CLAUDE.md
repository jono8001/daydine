# DayDine Project State

## What It Is
UK restaurant ranking platform using the **RCS (Restaurant Confidence Score)** — a composite 0-10 score derived from 40 signals across 8 weighted tiers. The scoring engine is transparent, auditable, and designed to surface inconsistencies between data sources while rewarding convergence.

Currently running a **Stratford-upon-Avon trial** (210 establishments, 197 ranked) with Tiers 1-2 and 4-5 populated. Google Places enrichment (Tier 2) complete. TripAdvisor (Tier 3) and editorial (Tier 6) ready to run.

## Current State (1 April 2026)

### RCS V3.4 Scoring Engine — IMPLEMENTED
- **Script**: `rcs_scoring_stratford.py` — full V3.4 pipeline
- **Scale**: 0.000–10.000 (3 decimal places)
- **40 signals** across 8 weighted tiers (7 active + Companies House penalties)
- **Temporal decay**: e^(-λt) applied to FSA inspection age and review recency (λ=0.0023, ~300-day half-life)
- **Cross-source convergence**: bonus/penalty when Google, TripAdvisor, and FSA ratings agree or diverge
- **18 penalty rules** (expanded from 10 in V3.2)
- **Unique rankings** guaranteed — tiebreaker system ensures no two restaurants share the same rank
- **6 rating bands** on 0-10 scale:

| Band | RCS Range |
|---|---|
| Excellent | 8.000–10.000 |
| Good | 6.500–7.999 |
| Generally Satisfactory | 5.000–6.499 |
| Improvement Necessary | 3.500–4.999 |
| Major Improvement | 2.000–3.499 |
| Urgent Improvement | 0.000–1.999 |

### Tier Weights (V3.4)

| Tier | Weight | Description | Signals |
|---|---|---|---|
| 1. FSA | 22% | Food Safety Authority hygiene data | hygiene_rating, structural, CIM, food_hygiene, inspection_recency |
| 2. Google | 24% | Google Places + aspect sentiment | rating, 5 aspect scores, sentiment, review_count, price_level, photos, types |
| 3. Online Presence | 12% | TripAdvisor-only (web/FB/IG → confidence layer) | ta_present, ta_rating, ta_reviews, ta_recency |
| 4. Operational | 15% | Service capabilities | reservations, delivery, takeaway, wheelchair, parking, hours_completeness |
| 5. Menu & Offering | 10% | Food offering breadth | menu_online, dietary_options, cuisine_tags, gbp_completeness |
| 6. Reputation & Awards | 8% | Editorial recognition | michelin_mention, aa_rating, local_awards |
| 7. Community | 2% | Engagement & responsiveness (reactivated V3.4) | responds_to_reviews, response_time, events, loyalty_program |
| 8. Companies House | penalty-only | Business viability | company_status, accounts_overdue, director_changes |

### Temporal Decay (V3.4)
Exponential decay e^(-λt) applied to time-sensitive signals:
- **FSA inspection age**: λ=0.0023 (~300-day half-life). Blended: 80% raw + 20% decay-adjusted.
- **Google review recency**: λ=0.0046 (~150-day half-life) applied to review volume signal when latest review date is available.
- Effect: recent inspections/reviews carry full weight; 2-year-old data loses ~10-20% of its signal contribution.

### Cross-Source Convergence (V3.4)
Compares normalised ratings from independent sources (FSA, Google, TripAdvisor) pairwise:
- **Converged** (avg divergence ≤0.10 on 0-1 scale): +3% score bonus
- **Neutral** (0.10–0.20): no adjustment
- **Mild divergence** (0.20–0.30): -3% penalty
- **Strong divergence** (>0.30): -5% penalty
- Requires ≥2 sources; single-source establishments get no adjustment.

### Tiebreaker System
Scores can tie in `rcs_final` after 3-decimal rounding. Ties are broken in rank assignment only:
1. More signals available
2. Higher FSA hygiene rating
3. More recent inspection date
4. Higher structural compliance sub-score
5. Higher confidence in management sub-score
6. Alphabetical by business name

### Non-Food Exclusion Filter
Establishments verified as non-food businesses are excluded from rankings:
- Checks Google types for food service (restaurant, cafe, pub, food, etc.)
- FSA rating 3+ overrides Google misclassification (keeps cafes in gyms, etc.)
- Name blacklist catches Slimming World, football clubs, Aston Martin, etc.
- Hotels assumed to have food service (kept in rankings)
- Excluded establishments marked "Not Ranked" in CSV

### Confidence Bands
Each ranked restaurant gets a confidence level based on signal coverage:
- **High** (±0.3): 20+ signals, 5+ tiers active
- **Medium** (±0.5): 14+ signals, 4+ tiers active
- **Low** (±0.8): 8+ signals
- **Insufficient** (not ranked): <8 signals — marked "Insufficient Data"

### Penalty Rules (18 rules, V3.4)

**FSA-based caps:**
- P1: FSA rating 0-1 → hard cap at 2.0
- P2: FSA rating 2 → hard cap at 4.0
- P3 (V3.4): FSA rating 3 with stale inspection (>2yr) → cap at 7.0
- P4: No inspection in 3+ years → -15%

**Google-based:**
- P5: Google rating < 2.0 → -10%
- P6 (V3.4): Google rating < 3.0 (≥2.0) → -5%
- P7: Zero Google reviews → -5%
- P8 (V3.4): Very few reviews (<5 combined) → -3%
- P9 (V3.4): No photos at all → -3%

**Online presence:**
- P10: No online presence at all → -10%
- P11 (V3.4): TripAdvisor rating < 2.5 → -5%
- P12 (V3.4): No opening hours listed (with Google data) → -3%

**Sentiment:**
- P13 (V3.4): Multiple red flags (3+) → -15%

**Rating inconsistency:**
- P14 (V3.4): Google and TA diverge by >2 stars → -5%

**Companies House:**
- P15: Dissolved company → cap at 3.0
- P16: In liquidation → cap at 5.0
- P17: Accounts overdue → -0.5 absolute
- P18: Director churn (3+ in 12mo) → -12%

### Stratford Trial Results (V3.4 — 210 establishments, 197 ranked)
- Excellent: 24 (12.2%)
- Good: 138 (70.1%)
- Generally Satisfactory: 25 (12.7%)
- Improvement Necessary: 7 (3.6%)
- Major Improvement: 1 (0.5%)
- Urgent Improvement: 2 (1.0%)
- Mean RCS: 7.15, Median: 7.38, Stdev: 1.06
- Signal coverage: 16.2 / 40 avg per record
- Convergence: 107 converged, 47 neutral, 19 mild divergence, 17 diverged, 7 insufficient
- Non-food excluded: 12, Insufficient data: 1

### Live Frontend (daydine.vercel.app)
- Location-based search using postcodes.io
- Place autocomplete, distance filtering (1/3/5/10/25 miles)
- Interactive Leaflet map with colour-coded markers by FSA rating
- Table/Map toggle, expandable detail rows
- Mobile-responsive layout, DayDine branding with Beta badge
- 264,791 FSA establishments in Firebase RTDB

---

## Data Collection Status

| Tier | Status | Signals Available | Source |
|---|---|---|---|
| 1. FSA | **COMPLETE** | 5/5 | Firebase RTDB (`r`, `sh`, `ss`, `sm`, `rd`) |
| 2. Google | **READY TO RUN** | 0/5 | Google Places API — script built, needs `GOOGLE_PLACES_API_KEY` secret |
| 3. Online Presence | **READY TO RUN** | 0/6 | TripAdvisor scraper built, needs workflow trigger |
| 4. Operational | **INFERRED** | 3/6 | Inferred from Google types (takeaway/delivery) + opening hours |
| 5. Menu & Offering | **READY TO RUN** | 1/3 | Cuisine count inferred from Google types; menu scraper built |
| 6. Reputation | **READY TO RUN** | 0/3 | Editorial/awards scraper built, needs workflow trigger |
| 7. Community | **COMPUTED** | 3/4 | Computed from inspection recency + review volume + presence breadth |

### Data Collection Plan (remaining 30 signals)

**Tier 1+ — FSA Augmentation**
- Script: `.github/scripts/augment_fsa_stratford.py`
- FSA LA ID for Stratford-on-Avon: **320** (not 197 which is Aberdeen)
- Fetches ALL food business types (1, 7, 14, 7843) not just Restaurant/Cafe/Canteen
- Known-restaurants list ensures important establishments (The Vintner, Dirty Duck, etc.) are never missed
- Action needed: Trigger full pipeline workflow to augment dataset

**Tier 2 — Google Places API (New)**
- Script: `.github/scripts/enrich_google_stratford.py`
- Fields: `gr` (rating), `grc` (review count), `gpl` (price level), `gpc` (photo count), `gty` (types)
- Action needed: Add `GOOGLE_PLACES_API_KEY` as GitHub repo secret, then trigger `enrich_and_score.yml` workflow

**Tier 3 — Online Presence (TripAdvisor + Web Presence)**
- TripAdvisor: `.github/scripts/collect_tripadvisor_apify.py` — uses Apify scraper API (~$0.50 per run)
- Web presence: `.github/scripts/check_web_presence.py` — infers website/FB/IG from Google data
- Merge: `.github/scripts/merge_tripadvisor.py` — writes `ta`, `trc`, `ta_present`, `ta_url`, `ta_cuisines`, `ta_reviews`
- Direct scraper (blocked): `.github/scripts/collect_tripadvisor.py` — kept as fallback
- Action needed: Add `APIFY_TOKEN` as GitHub repo secret, then trigger full pipeline
- Web presence already active: 143 websites, 137 Facebook, 126 Instagram inferred from Google data

**Tier 4 — Operational Signals**
- Extended Google Places fields: wheelchair accessibility, delivery, takeaway
- Web research for parking, reservations, opening hours completeness
- Some fields available from Google Places API response (extend `enrich_google_stratford.py`)

**Tier 5 — Menu & Offering**
- Scrape restaurant websites for online menu presence
- Count dietary options (vegan, gluten-free, halal, etc.) from menus
- Extract cuisine tags from Google types + menu analysis

**Tier 6 — Reputation & Awards**
- Scrape Michelin Guide (guide.michelin.com) for stars/Bib Gourmand
- AA Restaurant Guide for rosette ratings
- Local food award lists (regional tourism boards, local press)

**Tier 7 — Community & Engagement**
- Google Places API: owner response rate to reviews
- Web research: community events, loyalty programs
- Calculate average response time from review timestamps

---

## Repository Files

### Core Scripts
| File | Description |
|---|---|
| `rcs_scoring_stratford.py` | V3.4 RCS scoring engine — 40 signals, 8 tiers, temporal decay, convergence, 18 penalties |
| `run_daydine.py` | Pipeline orchestrator — coordinates all tiers and scoring |
| `restaurant_confidence.py` | V1 scoring engine (legacy, superseded by V2) |
| `enrich_places.py` | Google Places enrichment for any LA via Firebase (local use) |
| `fetch_stratford.py` | Fetch Stratford data from Firebase RTDB (local use) |

### GitHub Actions Scripts
| File | Description |
|---|---|
| `.github/scripts/fetch_firebase_stratford.py` | Fetches Stratford-on-Avon data from Firebase RTDB |
| `.github/scripts/enrich_google_stratford.py` | Enriches establishments with Google Places API data |
| `.github/scripts/merge_enrichment.py` | Merges Google enrichment into establishments JSON |
| `.github/scripts/collect_tripadvisor.py` | Scrapes TripAdvisor for ratings, reviews, cuisine tags |
| `.github/scripts/merge_tripadvisor.py` | Merges TripAdvisor data into establishments JSON |
| `.github/scripts/collect_menus.py` | Collects menu, dietary, cuisine data from websites |
| `.github/scripts/merge_menus.py` | Merges menu data into establishments JSON |
| `.github/scripts/collect_editorial.py` | Checks Michelin Guide, AA, GFG for awards |
| `.github/scripts/merge_editorial.py` | Merges editorial/awards data into establishments JSON |
| `.github/scripts/collect_enforcement.py` | Queries FSA API for enforcement actions |
| `.github/scripts/merge_enforcement.py` | Merges enforcement data into establishments JSON |
| `.github/scripts/classify_remaining.py` | Tier 3 web-lookup category classifier (stub) |
| `.github/scripts/fetch_fsa_stratford.py` | FSA API fetcher (unused — Firebase used instead) |

### GitHub Actions Workflows
| File | Description |
|---|---|
| `.github/workflows/fetch_and_score.yml` | Fetch Firebase data → run RCS scoring → commit results |
| `.github/workflows/enrich_and_score.yml` | Fetch Firebase → Google enrichment → merge → score → commit |
| `.github/workflows/collect_tripadvisor.yml` | Fetch Firebase → Google merge → TripAdvisor scrape → merge → score → commit |
| `.github/workflows/collect_menus.yml` | Collect menu/dietary data → merge → score → commit |
| `.github/workflows/collect_editorial.yml` | Collect editorial/awards data → merge → score → commit |

### Data Files
| File | Description |
|---|---|
| `stratford_establishments.json` | 210 Stratford-on-Avon establishments from Firebase RTDB |
| `stratford_rcs_scores.csv` | V3.4 scored results with rank, per-tier scores, convergence, final RCS, band |
| `stratford_rcs_summary.json` | V3.4 summary stats: mean, median, band distribution, convergence breakdown |
| `stratford_rcs_report.md` | V3.4 full Markdown report with rankings, categories, convergence |

### Frontend & Config
| File | Description |
|---|---|
| `index.html` | Single-page app (Firebase + Leaflet + postcodes.io) |
| `firebase-rules.json` | RTDB rules (public read, no write) |
| `vercel.json` | Vercel deployment config |
| `UK-Restaurant-Tracker-Methodology-Spec-V2.docx` | Full V2 methodology specification |
| `.claude/CLAUDE.md` | This file — project state and instructions |

### Firebase RTDB Structure
- Path: `daydine/establishments/{fhrsid}`
- Fields: `n` (name), `a` (address), `pc` (postcode), `la` (local authority), `r` (FSA rating 1-5), `rd` (rating date), `s` (overall score 0-10), `sh` (hygiene sub 0-10), `ss` (structural sub 0-10), `sm` (management sub 0-10), `lat`, `lon`, `id` (FHRSID), `t` (business type)
- Google enrichment fields (when populated): `gr`, `grc`, `gpl`, `gpc`, `gty`, `gpid`, `goh`

---

## Environment Variables
- `GOOGLE_PLACES_API_KEY` — GitHub repo secret. Used by `enrich_google_stratford.py` and `sanity_check_coverage.py`
- `APIFY_TOKEN` — GitHub repo secret (needs adding). Used by `collect_tripadvisor_apify.py`. Get from apify.com/account/integrations
- Firebase RTDB URL — public read, hardcoded: `https://recursive-research-eu-default-rtdb.europe-west1.firebasedatabase.app`
- Firebase config — embedded in `index.html` (public read-only)

## Tech Stack
- **Frontend**: Vanilla HTML/CSS/JS, Firebase Realtime Database, Leaflet.js, postcodes.io API
- **Scoring engine**: Python 3.11 (`rcs_scoring_stratford.py`)
- **Data pipeline**: Python scripts + GitHub Actions workflows
- **Hosting**: Vercel (auto-deploys from `main` branch)
- **Database**: Firebase Realtime Database (recursive-research-eu project, EU West 1)

---

## V2 Methodology Spec vs V3.4 Implementation

The `UK-Restaurant-Tracker-Methodology-Spec-V2.docx` defines the original spec. V3.4 has evolved significantly:

| Aspect | V2 Spec | V3.4 Implementation |
|---|---|---|
| Signals | 36 | 40 (expanded with aspect sentiment + Companies House) |
| Tiers | 7 | 8 (7 active + Companies House penalty-only) |
| Tier weights | 0.16/0.23/0.18/0.12/0.08/0.13/0.10 | 0.22/0.24/0.12/0.15/0.10/0.08/0.02 + penalties |
| Rating bands | 5 bands | 6 bands (Excellent/Good/Generally Satisfactory/Improvement Necessary/Major Improvement/Urgent Improvement) |
| Band thresholds | 8.5/7.0/5.0/3.0/0.0 | 8.0/6.5/5.0/3.5/2.0/0.0 |
| Penalty rules | 34 rules in 6 groups | 18 rules in 6 groups |
| SCP weighting | Full SCP priors per signal | Not implemented (simplified weighted average) |
| Convergence | Intra-tier + inter-tier pairwise divergence | **Implemented V3.4**: pairwise cross-source (FSA/Google/TA) with ±3-5% adjustment |
| Temporal decay | e^(-λt) with λ=0.0023 | **Implemented V3.4**: λ=0.0023 for FSA, λ=0.0046 for review recency |
| Calibration | Ground-truth correction (β offset) | Passthrough (no calibration data yet) |
| Tiebreakers | Not specified | Implemented (unique rankings guaranteed) |
| Google caps | Not specified | 30% single-tier cap, 45% cross-tier cap |
| Scale | 0-10 | 0-10 (matches) |

### V3.4 Version History
| Version | Date | Key Changes |
|---|---|---|
| V2 | Dec 2025 | Original 35-signal, 7-tier scoring engine |
| V3.1 | Mar 2026 | Aspect-based sentiment, Companies House penalties, 3-tier classifier |
| V3.2 | Mar 2026 | Community tier removed, SCP removed, Google caps, provenance tracking |
| V3.4 | Apr 2026 | Temporal decay, cross-source convergence, 18 penalty rules, community reactivated at 2% |

---

## Next Steps (Priority Order)

### 1. TripAdvisor Enrichment (Tier 3)
- Add `APIFY_TOKEN` to GitHub repo secrets
- Trigger `collect_tripadvisor.yml` workflow
- Expected: ta_rating, ta_reviews, ta_recency for ~150+ establishments
- Will activate convergence scoring for most records (currently 107 converged from FSA+Google only)

### 2. Google Places Enrichment (refresh)
- Trigger `enrich_and_score.yml` to refresh Google data and populate `g_latest_review_date` for temporal decay on review volume

### 3. Build Tier 6 Data Collection (Reputation)
- Trigger `collect_editorial.yml` for Michelin/AA/local awards data
- At 8% weight, reputation tier has material impact on scores

### 4. SCP Weighting
- Implement signal confidence priors from V2 spec
- Per-signal reliability weights based on source trustworthiness

### 5. UI Integration
- Show RCS score (0-10) as primary metric in search results
- Replace FSA-only tier badges with RCS-based bands
- Show convergence status and confidence margin
- Update map marker colours to RCS bands

### 6. Scale Beyond Stratford
- Run pipeline for other local authorities (start with London boroughs)
- Automate nightly scoring via GitHub Actions cron
