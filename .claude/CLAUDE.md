# DayDine Project State

## What It Is
UK restaurant ranking platform using the **RCS (Restaurant Confidence Score)** — a composite 0-10 score derived from 35 signals across 7 weighted tiers. The scoring engine is transparent, auditable, and designed to surface inconsistencies between data sources while rewarding convergence.

Currently running a **Stratford-upon-Avon trial** (208 FSA-registered restaurants) with Tier 1 (FSA) data fully populated. Google Places enrichment (Tier 2) is built and ready to run.

## Current State (30 March 2026)

### RCS V2 Scoring Engine — IMPLEMENTED
- **Script**: `rcs_scoring_stratford.py` — full V2 pipeline
- **Scale**: 0.000–10.000 (3 decimal places)
- **35 signals** across 7 weighted tiers
- **Unique rankings** guaranteed — tiebreaker system ensures no two restaurants share the same score or rank
- **6 rating bands** on 0-10 scale:

| Band | RCS Range |
|---|---|
| Excellent | 8.000–10.000 |
| Good | 6.500–7.999 |
| Generally Satisfactory | 5.000–6.499 |
| Improvement Necessary | 3.500–4.999 |
| Major Improvement | 2.000–3.499 |
| Urgent Improvement | 0.000–1.999 |

### Tier Weights

| Tier | Weight | Description | Signals |
|---|---|---|---|
| 1. FSA | 20% | Food Safety Authority hygiene data | hygiene_rating, structural, CIM, food_hygiene, inspection_recency |
| 2. Google | 25% | Google Places signals | rating, review_count, price_level, photos_count, place_types |
| 3. Online Presence | 20% | Web & social media presence | website, facebook, instagram, tripadvisor_presence, ta_rating, ta_reviews |
| 4. Operational | 15% | Service capabilities | reservations, delivery, takeaway, wheelchair, parking, hours_completeness |
| 5. Menu & Offering | 10% | Food offering breadth | menu_online, dietary_options, cuisine_tags |
| 6. Reputation & Awards | 5% | Editorial recognition | aa_rating, michelin_mention, local_awards |
| 7. Community | 5% | Engagement & responsiveness | responds_to_reviews, response_time, events, loyalty_program |

### Tiebreaker System
When scores are identical after 3-decimal rounding, ties are broken in order:
1. Higher FSA hygiene rating
2. More recent inspection date
3. Higher structural compliance sub-score
4. Higher confidence in management sub-score
5. Alphabetical by business name

A walk-down algorithm then applies 0.001 decreasing offsets to ensure every final score is numerically unique.

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

### Penalty Rules (implemented)
- FSA rating 0-1: score capped at 2.0
- FSA rating 2: score capped at 4.0
- No inspection in 3+ years: -15%
- Google rating < 2.0: -10%
- Zero Google reviews: -5%
- No online presence at all: -10%

### Stratford Trial Results (208 establishments, Tiers 1+2+inferred)
- Excellent: 149 (71.6%)
- Good: 50 (24.0%)
- Generally Satisfactory: 3 (1.4%)
- Improvement Necessary: 4 (1.9%)
- Major Improvement: 2 (1.0%)
- Signal coverage: 13.4 / 35 avg per record (Tiers 1+2+4+5+7 inferred)
- Tiers populated: FSA 204, Google 207, Ops 172, Menu 66, Community 208
- With TripAdvisor enrichment (Tier 3): expected ~16/35 avg

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

**Tier 3 — Online Presence (TripAdvisor)**
- Script: `.github/scripts/collect_tripadvisor.py` — scrapes TA search + detail pages
- Merge: `.github/scripts/merge_tripadvisor.py` — writes `ta`, `trc`, `ta_present`, `ta_url`, `ta_cuisines` fields
- Workflow: `.github/workflows/collect_tripadvisor.yml` — full pipeline with merge + re-score
- Action needed: Trigger `collect_tripadvisor.yml` workflow from Actions tab
- Remaining: website, Facebook, Instagram presence detection (needs Brave Search or Perplexity API)

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
| `rcs_scoring_stratford.py` | V2 RCS scoring engine — 35 signals, 7 tiers, 0-10 scale, unique rankings |
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
| `stratford_establishments.json` | 208 Stratford-on-Avon establishments from Firebase RTDB |
| `stratford_rcs_scores.csv` | Scored results with rank, per-tier scores, final RCS, band |
| `stratford_rcs_summary.json` | Summary stats: mean, median, band distribution |

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
- `GOOGLE_PLACES_API_KEY` — GitHub repo secret (needs adding). Used by `enrich_google_stratford.py`
- Firebase RTDB URL — public read, hardcoded: `https://recursive-research-eu-default-rtdb.europe-west1.firebasedatabase.app`
- Firebase config — embedded in `index.html` (public read-only)

## Tech Stack
- **Frontend**: Vanilla HTML/CSS/JS, Firebase Realtime Database, Leaflet.js, postcodes.io API
- **Scoring engine**: Python 3.11 (`rcs_scoring_stratford.py`)
- **Data pipeline**: Python scripts + GitHub Actions workflows
- **Hosting**: Vercel (auto-deploys from `main` branch)
- **Database**: Firebase Realtime Database (recursive-research-eu project, EU West 1)

---

## V2 Methodology Spec vs Implementation — Gaps

The `UK-Restaurant-Tracker-Methodology-Spec-V2.docx` defines a more comprehensive system than what is currently implemented. Key differences:

| Aspect | V2 Spec | Current Implementation |
|---|---|---|
| Signals | 36 | 35 (close match) |
| Tier names | Safety & Compliance, Consumer Reviews, Editorial & Awards, Social Presence, Digital Presence, Cross-Source Consistency, Value & Accessibility | FSA, Google, Online Presence, Operational, Menu, Reputation, Community |
| Tier weights | 0.16/0.23/0.18/0.12/0.08/0.13/0.10 | 0.30/0.20/0.15/0.15/0.10/0.05/0.05 |
| Rating bands | 5 bands (Exceptional/Recommended/Acceptable/Caution/Avoid) | 6 bands (Excellent/Good/Generally Satisfactory/Improvement Necessary/Major Improvement/Urgent Improvement) |
| Band thresholds | 8.5/7.0/5.0/3.0/0.0 | 8.0/6.5/5.0/3.5/2.0/0.0 |
| Penalty rules | 34 rules in 6 groups | 6 rules (core penalties only) |
| SCP weighting | Full SCP priors per signal | Not implemented (simplified weighted average) |
| Convergence | Intra-tier + inter-tier pairwise divergence | Not implemented yet |
| Temporal decay | e^(-λt) with λ=0.0023 | Not implemented yet |
| Calibration | Ground-truth correction (β offset) | Passthrough (no calibration data yet) |
| Tiebreakers | Not specified | Implemented (unique rankings guaranteed) |
| Scale | 0-10 | 0-10 (matches) |

**The spec .docx needs updating** to reflect:
- The 6-band system (not 5)
- Updated tier weights (FSA 30% not 16%)
- Tiebreaker/unique ranking requirement
- Simplified penalty rules for MVP

---

## Next Steps (Priority Order)

### 1. Google Places Enrichment
- Add `GOOGLE_PLACES_API_KEY` to GitHub repo secrets
- Trigger `enrich_and_score.yml` workflow
- Expected: Tier 2 signals populated for ~180+ of 208 establishments

### 2. Expand Penalty Rules
- Implement remaining 28 penalty rules from V2 spec
- Add SCP weighting to aggregation formula
- Add temporal decay (λ=0.0023, 300-day half-life)

### 3. Build Tier 3-7 Data Collection
- Priority: Tier 3 (Online Presence) and Tier 6 (Reputation) — highest impact signals
- Use web research APIs (Brave Search, Perplexity) for presence detection
- Scrape Michelin/AA guides for award data

### 4. UI Integration
- Show RCS score (0-10) as primary metric in search results
- Replace FSA-only tier badges with RCS-based bands
- Update map marker colours to RCS bands

### 5. Scale Beyond Stratford
- Run pipeline for other local authorities (start with London boroughs)
- Automate nightly scoring via GitHub Actions cron
