# UK Restaurant Tracker — Methodology Specification V3

*DayDine RCS (Restaurant Confidence Score) — Version 3.0*
*Last updated: 31 March 2026*

---

## 1. Overview

The Restaurant Confidence Score (RCS) is a composite 0.000–10.000 score that ranks UK restaurants by combining **40 signals** across **8 weighted tiers**. The methodology is transparent, auditable, and designed to surface inconsistencies between data sources while rewarding convergence.

### Design Principles

1. **Multi-source**: No single data source dominates. Google reviews are capped at 30% effective weight.
2. **Verifiable**: Every signal traces to a public data source (FSA, Google Places, TripAdvisor, Companies House).
3. **Penalise risk**: Critical food safety or business viability issues trigger hard score caps.
4. **Reward completeness**: Establishments with more data get higher confidence ratings.
5. **Unique rankings**: Every restaurant gets a numerically distinct score — no ties.

### Score Scale

| Property | Value |
|---|---|
| Range | 0.000 – 10.000 |
| Precision | 3 decimal places |
| Uniqueness | Guaranteed — tiebreaker system ensures no two restaurants share a score |

---

## 2. Rating Bands

| Band | RCS Range | Description |
|---|---|---|
| Excellent | 8.000 – 10.000 | Outstanding across multiple dimensions; strong data convergence |
| Good | 6.500 – 7.999 | Consistently positive; minor gaps in one area |
| Generally Satisfactory | 5.000 – 6.499 | Adequate; notable gaps or mixed signals |
| Improvement Necessary | 3.500 – 4.999 | Significant concerns; multiple penalties triggered |
| Major Improvement | 2.000 – 3.499 | Critical issues; enforcement actions or consistently poor ratings |
| Urgent Improvement | 0.000 – 1.999 | Severe safety or viability concerns |

---

## 3. Tier Structure (8 Tiers, 40 Signals)

### 3.1 Tier 1: Food Safety Authority (FSA) — Weight 20%

**Source**: FSA Ratings API + Firebase RTDB
**SCP**: 0.92 (statutory data, high reliability)

| Signal | Normalisation | Weight within tier |
|---|---|---|
| Hygiene rating (0-5) | `rating / 5` → 0-1 | 40% |
| Structural compliance (0-25, inverted) | `(25 - raw) / 25` → 0-1 | 20% |
| Confidence in management (0-20, inverted) | `(20 - raw) / 20` → 0-1 | 20% |
| Food hygiene sub-score (0-25, inverted) | `(25 - raw) / 25` → 0-1 | 20% |
| Inspection recency | Days since last inspection | Penalty modifier |

**Recency penalties:**
- \>365 days: -5% of tier score
- \>730 days: -10% of tier score

**FSA data augmentation:**
- Primary source: Firebase RTDB (`la = "Stratford-on-Avon"`)
- Augmented via FSA API (LA ID: 320) for business types 1, 7, 14, 7843
- Known-restaurants safety net ensures critical venues are never missed
- Enforcement actions checked per FHRSID via FSA API

### 3.2 Tier 2: Google Signals — Weight 25% (capped at 30% effective)

**Source**: Google Places API (New) — Text Search
**SCP**: 0.72 (large corpus, but susceptible to review manipulation)

| Signal | Normalisation | Weight within tier |
|---|---|---|
| Star rating (1-5) | `rating / 5` → 0-1 | 20% |
| Food Quality aspect score | Keyword NLP, 0-1 | 5% |
| Service Quality aspect score | Keyword NLP, 0-1 | 5% |
| Ambience aspect score | Keyword NLP, 0-1 | 5% |
| Value Perception aspect score | Keyword NLP, 0-1 | 5% |
| Wait Time aspect score | Keyword NLP, 0-1 | 5% |
| Overall review sentiment | Keyword analysis, 0-1 | 10% |
| Review count | `log10(count) / log10(1000)`, cap 1.0 | 20% |
| Price level (1-4) | `level / 4` → 0-1 | 5% |
| Photos count | `min(count, 10) / 10` → 0-1 | 5% |
| Place types | Binary presence = 1.0 | 5% |

**Google weight cap:**
When re-normalisation (due to missing tiers) would push Google's effective weight above 30%, the excess is redistributed proportionally to other active tiers. This prevents Google from dominating when tiers like Online Presence have sparse data.

**Aspect-based NLP sentiment (5 sub-scores):**
Each aspect is scored by counting positive and negative keyword matches in combined Google + TripAdvisor review text:

| Aspect | Positive keywords (sample) | Negative keywords (sample) | SCP |
|---|---|---|---|
| Food Quality | delicious, tasty, fresh, perfectly cooked, authentic | bland, tasteless, stale, undercooked, burnt, inedible | 0.60 |
| Service Quality | friendly, attentive, professional, great service | rude, unfriendly, ignored, slow service, unprofessional | 0.58 |
| Ambience | great atmosphere, cosy, charming, clean, spotless | noisy, cramped, dirty, dingy, run down | 0.55 |
| Value Perception | good value, worth every penny, generous portions | overpriced, rip off, small portions, extortionate | 0.57 |
| Wait Time | quick, prompt, efficient, seated immediately | long wait, waited an hour, took ages, forgot our order | 0.62 |

Formula per aspect: `score = positive_matches / (positive_matches + negative_matches)`
Score is 0-1 where 0 = all negative, 1 = all positive, None = no mentions.

**Overall sentiment scoring:**
```
base = 0.5
+ 0.05 per positive phrase (e.g. "amazing", "highly recommend")
- 0.08 per moderate negative (e.g. "disappointing", "bland")
- 0.15 per red flag (e.g. "food poisoning", "cockroach", "health hazard")
Clamped to [0.0, 1.0]
```

**Red flag system:**
32 critical phrases trigger red flags. 2+ red flags on a single establishment generate a WARNING in the report. Red flag phrases include: "food poisoning", "cockroach", "hair in food", "disgusting", "never again", "health hazard", "rude staff", "avoid at all costs".

### 3.3 Tier 3: Online Presence — Weight 20%

**Sources**: Google Places (inferred), TripAdvisor (Apify API)
**SCP**: 0.55–0.68

| Signal | Normalisation | Weight within tier |
|---|---|---|
| Has website | Boolean (inferred from Google) | 15% |
| Has Facebook | Boolean (inferred from review volume + type) | 10% |
| Has Instagram | Boolean (inferred from type + review volume) | 10% |
| TripAdvisor presence | Boolean (from Apify scrape) | 15% |
| TripAdvisor rating (1-5) | `rating / 5` → 0-1 | 20% |
| TripAdvisor review count | `log10(count) / log10(1000)`, cap 1.0 | 15% |
| TripAdvisor review recency | Fraction of reviews < 6 months old | 15% |

**TripAdvisor data collection:**
- Primary: Apify TripAdvisor Scraper (`automation-lab/tripadvisor-scraper`)
- Cost: ~$0.003/review, ~$0.50 per full run
- Fallback: Direct scraper (blocked by TA, kept as backup)
- Fuzzy name matching (difflib, threshold 0.5) confirms correct restaurant
- Up to 5 review texts extracted per establishment for sentiment analysis

**Web presence inference:**
Website, Facebook, and Instagram presence are inferred from Google Places data rather than actively scraped:
- Chains (Costa, Starbucks, etc.) → assumed all three
- Restaurants with 100+ Google reviews → assumed website + Facebook
- Cafes/bakeries with 50+ reviews → assumed Instagram

### 3.4 Tier 4: Operational Signals — Weight 15%

**Source**: Google Places API (types + opening hours)
**SCP**: 0.65

| Signal | Normalisation | Weight within tier |
|---|---|---|
| Accepts reservations | Boolean | 16.7% |
| Offers delivery | Boolean (or inferred from `food_delivery` type) | 16.7% |
| Offers takeaway | Boolean (or inferred from `meal_takeaway` type) | 16.7% |
| Wheelchair accessible | Boolean | 16.7% |
| Has parking | Boolean | 16.7% |
| Opening hours completeness | `len(goh) / 7` → 0-1 (7 days = complete) | 16.7% |

### 3.5 Tier 5: Menu & Offering — Weight 10%

**Sources**: Google Places types, website scraping, GBP profile
**SCP**: 0.58–0.62

| Signal | Normalisation | Weight within tier |
|---|---|---|
| Has menu online | Boolean (inferred or scraped) | 30% |
| Dietary options count | `min(count, 5) / 5` → 0-1 | 20% |
| Cuisine tags count | `min(count, 3) / 3` → 0-1 (from Google types) | 20% |
| GBP completeness score | 10-attribute check / 10 → 0-1 (SCP 0.62) | 30% |

**GBP Completeness attributes (10 checks):**
1. Has rating
2. Has reviews (count > 0)
3. Has photos (count > 0)
4. Has opening hours
5. Has price level
6. Has place types
7. Has Google Place ID
8. Review count ≥ 10
9. Review count ≥ 100
10. Has website

### 3.6 Tier 6: Reputation & Awards — Weight 5%

**Sources**: Michelin Guide (web search), AA Restaurant Guide, local press
**SCP**: 0.85–0.93

| Signal | Normalisation | Weight within tier |
|---|---|---|
| Michelin mention (star/bib/plate) | Boolean | 33.3% |
| AA Rosette rating | Boolean | 33.3% |
| Local awards count | `min(count, 3) / 3` → 0-1 | 33.3% |

### 3.7 Tier 7: Community & Engagement — Weight 5%

**Sources**: Computed from existing data (recency, review volume, presence breadth)
**SCP**: 0.55

| Signal | Normalisation | Weight within tier |
|---|---|---|
| Responds to reviews | Boolean | 25% |
| Average response time | <1 day=1.0, <3d=0.7, <7d=0.4, else 0.1 | 25% |
| Community events | Boolean | 25% |
| Loyalty program | Boolean | 25% |

**Computed fallback** (when no explicit fields available):
- Inspection recency: <180d=1.0, <365d=0.8, <730d=0.5, else 0.2
- Review volume: `log10(google + TA reviews) / log10(2000)`
- Presence breadth: `count(gr, ta, web, fb, ig present) / 4`

### 3.8 Tier 8: Business Viability (Companies House) — Penalty Rules

**Source**: Companies House API (free, `api.company-information.service.gov.uk`)
**SCP**: 0.94 (statutory company data)

This tier operates as **penalty multipliers** on the final score, not as a weighted tier component. Business viability issues are binary risks that should override quality signals.

| Signal | Penalty | Effect |
|---|---|---|
| Company dissolved | Score → 0.0 | Hard floor — dissolved company cannot operate |
| Company in liquidation | Score × 0.50 | Severe — business winding down |
| Insolvency history | Score × 0.50 | Major risk indicator |
| Accounts overdue | Score × 0.82 | Financial stress signal |
| 3+ director changes in 12 months | Score × 0.88 | Governance instability |

**Matching**: Fuzzy name matching (difflib, threshold 0.5) with postcode area bonus. SIC codes 56101/56102/56103 confirm food service registration.

---

## 4. Scoring Pipeline

### 4.1 Stage 1: Signal Collection

```
Firebase RTDB → FSA data (208 establishments)
FSA API (LA 320) → Augment with pubs/bars/takeaways
Google Places API → Rating, reviews, photos, types, review text
Apify API → TripAdvisor rating, reviews, cuisine, ranking
Web inference → Website, Facebook, Instagram presence
GBP check → Profile completeness score
Menu scrape → Cuisine tags, dietary options
Editorial check → Michelin, AA, local awards
FSA enforcement → Enforcement actions
Companies House → Business status, accounts, directors
```

### 4.2 Stage 2: Normalisation

All signals normalised to 0-1 scale within their tier. Missing signals are skipped, and the tier is re-weighted across available signals only.

### 4.3 Stage 3: Weighted Aggregation

```
For each tier with data:
    tier_score = Σ(signal_weight × signal_value) / Σ(signal_weight)
    (re-weighted across available signals)

effective_weights = normalise(TIER_WEIGHTS for active tiers)
if effective_weights["google"] > 0.30:
    redistribute excess to other tiers

rcs_raw = Σ(effective_weight[tier] × tier_score[tier]) × 10
```

### 4.4 Stage 4: Penalty Application

```
Apply in order:
    FSA 0-1:        cap at 2.0
    FSA 2:          cap at 4.0
    No inspection 3yr: -15%
    Google < 2.0:   -10%
    Zero reviews:   -5%
    No online:      -10%
    CH dissolved:   → 0.0
    CH liquidation: × 0.50
    CH insolvency:  × 0.50
    CH overdue:     × 0.82
    CH director churn: × 0.88

rcs_final = clamp(penalised_score, 0, 10)
```

### 4.5 Stage 5: Tiebreaker & Ranking

After scoring all establishments, ensure unique rankings:

1. Sort by `rcs_final` descending
2. Break ties using (in order):
   a. Higher FSA hygiene rating
   b. More recent inspection date
   c. Higher structural compliance score
   d. Higher confidence in management score
   e. Alphabetical by business name
3. Walk-down algorithm: each score must be strictly less than the one above (offset 0.001)
4. Zero-floor re-spacing for bottom records
5. Assign sequential ranks 1..N

### 4.6 Stage 6: Confidence Assessment

| Level | Criteria | Margin |
|---|---|---|
| High | 20+ signals, 5+ tiers active | ±0.3 |
| Medium | 14+ signals, 4+ tiers active | ±0.5 |
| Low | 8+ signals | ±0.8 |
| Insufficient | <8 signals | Not ranked |

---

## 5. Non-Food Exclusion Filter

Establishments verified as non-food businesses are excluded from rankings:

**Exclusion logic (priority order):**
1. Name blacklist: Slimming World, football clubs, Aston Martin, golf clubs, churches, horse sanctuaries
2. Google food types present → **include** (overrides all below)
3. FSA rating 3+ → **include** (overrides Google misclassification)
4. Food keywords in name (cafe, restaurant, kitchen, etc.) → **include**
5. Google non-food types (gym, insurance, real estate) → **exclude**
6. Sports clubs with no food evidence → **exclude**

Excluded establishments are marked "Not Ranked" in the CSV output.

---

## 6. Category Classification (3-Tier)

### Tier 1: Google Place Types (primary)
Maps Google `*_restaurant` types to 21 categories (Indian, Italian, Chinese, Pub/Bar, Cafe, etc.)

### Tier 2: Name-Based Keyword Matching (fallback)
32 keyword groups with pub name pattern matching (word-boundary safe).

### Tier 3: Web Lookup (stub)
External script for remaining "Other" classifications.

---

## 7. Data Sources & Collection

| Source | Method | Cost | Rate Limit |
|---|---|---|---|
| Firebase RTDB | REST API (public read) | Free | None |
| FSA API | REST API (public) | Free | ~10 req/sec |
| Google Places API (New) | Text Search | Per-request billing | 10 req/sec |
| Apify TripAdvisor | Actor API | ~$0.003/review | Account limits |
| Companies House API | REST API | Free | 600 req/5min |
| Michelin Guide | Web scrape | Free | Throttled 2-3s |

---

## 8. Current Coverage (Stratford-upon-Avon Trial)

| Metric | Value |
|---|---|
| Establishments | 209 |
| Ranked (food service) | 197 |
| Excluded (non-food) | 12 |
| Signals per record (avg) | 19.0 / 40 (47.5%) |
| Tiers active | 7 / 8 |
| Tiers with full coverage | FSA, Google, Online (inferred), Reputation, Community |
| Tiers with partial coverage | Operational (83%), Menu (76%) |
| Tiers pending | Companies House (needs API key) |

### Tier-by-Tier Coverage

| Tier | Weight | Coverage | Source Status |
|---|---|---|---|
| FSA (Tier 1) | 20% | 98% (205/209) | Live |
| Google (Tier 2) | 25% | 99% (208/209) | Live |
| Online Presence (Tier 3) | 20% | 100% (inferred) | Live (web) + Pending (TA via Apify) |
| Operational (Tier 4) | 15% | 83% (173/209) | Inferred from Google |
| Menu & Offering (Tier 5) | 10% | 76% (158/209) | Live |
| Reputation (Tier 6) | 5% | 100% (209/209) | Live |
| Community (Tier 7) | 5% | 100% (209/209) | Computed |
| Business Viability (Tier 8) | Penalties | 0% | Needs COMPANIES_HOUSE_API_KEY |

---

## 9. Environment Variables

| Variable | Purpose | Where to set |
|---|---|---|
| `GOOGLE_PLACES_API_KEY` | Google Places API enrichment + sanity check | GitHub repo secret |
| `APIFY_TOKEN` | TripAdvisor data via Apify scraper | GitHub repo secret |
| `COMPANIES_HOUSE_API_KEY` | Companies House business viability check | GitHub repo secret |

---

## 10. Pipeline Execution

### GitHub Actions Workflow: `full_pipeline.yml`

```
1. Fetch FSA data from Firebase RTDB
2. Augment with FSA API (types 1, 7, 14, 7843)
3. Enrich with Google Places API (rating, reviews, photos, types, review text)
4. Check web presence (website/FB/IG inference)
5. Score GBP completeness
6. Collect TripAdvisor data (Apify) [continue-on-error]
7. Merge TripAdvisor data + compute review recency
8. Collect menu data (cuisine tags, dietary options)
9. Collect editorial data (Michelin, AA, awards)
10. Check FSA enforcement actions
11. Check Companies House business viability [continue-on-error]
12. Run aspect-based sentiment analysis
13. Run V3 RCS scoring engine
14. Run sanity check (coverage validation)
15. Commit all results
```

### Output Files

| File | Description |
|---|---|
| `stratford_rcs_scores.csv` | Full ranked results with per-tier scores |
| `stratford_rcs_summary.json` | Summary statistics, band distribution, category rankings |
| `stratford_rcs_report.md` | Human-readable report with all sections |
| `stratford_establishments.json` | Enriched establishment data |
| `stratford_google_enrichment.json` | Raw Google Places API results |
| `stratford_tripadvisor.json` | TripAdvisor scrape results |
| `stratford_sentiment.json` | Aspect-based sentiment analysis |
| `stratford_sanity_report.json` | Data quality validation report |

---

## 11. Version History

| Version | Date | Changes |
|---|---|---|
| V1.0 | Feb 2026 | Initial 5-source scoring engine (restaurant_confidence.py) |
| V2.0 | Mar 2026 | 35 signals, 7 tiers, 0-10 scale, unique rankings, 6 rating bands |
| V2.1 | Mar 2026 | FSA weight 30%→20%, Google capped 30%, confidence bands, non-food filter |
| V3.0 | Mar 2026 | 40 signals, 8 tiers, aspect NLP (5 sub-scores), GBP completeness, TA recency, Companies House penalties, Apify TripAdvisor |

---

*This specification is maintained in the DayDine repository at `UK-Restaurant-Tracker-Methodology-Spec-V3.md`.*
*The scoring engine implementation is in `rcs_scoring_stratford.py`.*
