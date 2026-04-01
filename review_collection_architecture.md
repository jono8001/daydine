# Review Collection Architecture — Technical Recommendation

*DayDine Operator Intelligence | April 2026*

---

## Current State

| Source | Method | Reviews per venue | Sort control | Cost | Status |
|--------|--------|------------------:|:------------:|------|--------|
| Google Places API (New) | Text Search / Place Details | 5 | None (most relevant only) | ~$0.03/venue | Active |
| TripAdvisor (Apify) | Actor API | 5-20 | Newest | ~$0.003/review | Blocked (needs APIFY_TOKEN) |
| TripAdvisor (direct) | Web scraper | 0 (metadata only) | N/A | Free | Blocked (network proxy) |

**Current evidence tier for all venues: Anecdotal (5 texts, 1 source).**

Target: **Indicative** (15+ texts, 2 sources) minimum. **Directional** (30+ texts, 2+ sources) preferred.

---

## Collection Options Assessed

### 1. Google Places API — cannot exceed 5 reviews

The Google Places API (New) returns a maximum of 5 reviews per venue. This is a hard API constraint:
- Text Search endpoint: 5 reviews, no sort parameter, no pagination
- Place Details endpoint: 5 reviews, no sort parameter, no pagination
- Legacy Places API: supports `reviews_sort=newest` but still caps at 5, and requires separate API enablement

**Verdict: Maxed out. Cannot improve within API constraints.**

### 2. TripAdvisor via Apify — best near-term option

The `collect_tripadvisor_apify.py` script is already built and tested. It uses the `automation-lab/tripadvisor-scraper` Apify actor.

- **Reviews per venue:** Up to 20 (configurable, default 5)
- **Sort:** Newest first (most useful for trend detection)
- **Cost:** ~$0.003/review → ~$0.06/venue at 20 reviews → ~$12.60 for 210 venues
- **Matching:** Fuzzy name match with difflib (threshold 0.5)
- **Output:** Rating, review count, cuisines, price range, ranking, review text

**Requirements:**
1. `APIFY_TOKEN` — get from apify.com/account/integrations (free tier includes $5/month credit)
2. `pip install apify-client`

**Impact:** Would move all matched venues from Anecdotal (5 texts, 1 source) to Indicative (10-25 texts, 2 sources). Combined Google + TA corpus of 10-25 reviews per venue enables genuine theme analysis and cross-source validation.

**Verdict: Highest ROI next step. Unlocks Indicative tier estate-wide for ~$13.**

### 3. Google Reviews via SerpAPI or third-party scraper

Services like SerpAPI, Outscraper, or Bright Data can return 20-100+ Google reviews per venue with sort control (newest, lowest-rated, highest-rated).

- **SerpAPI Google Maps Reviews:** $50/month for 5,000 searches. Returns up to 10 reviews per page with pagination.
- **Outscraper Google Maps Reviews:** Pay-per-use, ~$2 per 1,000 reviews. Can extract all reviews for a venue.
- **Bright Data Google Maps scraper:** Enterprise pricing, fully managed.

**Legal considerations:**
- Scraping Google review content may violate Google's Terms of Service
- SerpAPI operates as a search results API (grey area)
- Outscraper explicitly markets review extraction (higher legal risk)
- For a B2B operator intelligence product, the risk is reputational, not typically enforcement-driven at this scale

**Verdict: Technically capable, legally grey. Consider if Apify + Google API is insufficient.**

### 4. Direct web scraping (Google or TripAdvisor)

- Google reviews: Heavy anti-scraping protection (reCAPTCHA, dynamic rendering). Not practical without headless browser infrastructure.
- TripAdvisor: Aggressive bot detection. The existing direct scraper (`collect_tripadvisor.py`) was blocked in testing. Works intermittently from residential IPs but not from cloud/CI environments.

**Verdict: Not reliable for production use.**

### 5. Other review sources

| Source | Feasibility | Review volume (UK restaurants) | Notes |
|--------|:-----------:|-------------------------------:|-------|
| Booking.com (for hotels with restaurants) | Medium | 5-50 per venue | Only applicable to hotel dining venues (~17 in Stratford) |
| Facebook reviews | Low | Variable | Requires Facebook Graph API access, increasingly restricted |
| Yelp | Very low | Negligible in UK | Yelp has minimal UK restaurant coverage |
| OpenTable | Low | Variable | No public API for review text |

**Verdict: Not worth pursuing at this stage. Google + TripAdvisor covers 90%+ of UK restaurant review volume.**

---

## Recommended Architecture

### Phase 1: Immediate (cost: ~$13)

```
Google Places API (5 reviews, most relevant)
  + TripAdvisor Apify (20 reviews, newest)
  = 25 reviews per venue, 2 sources
  → Indicative confidence tier
```

**Action:** Add `APIFY_TOKEN` as environment variable / GitHub secret, then run:
```bash
APIFY_TOKEN=your_token python3 .github/scripts/collect_tripadvisor_apify.py
python3 .github/scripts/merge_tripadvisor.py
```

### Phase 2: Medium-term (cost: ~$50/month)

```
Google Places API (5 reviews, most relevant)
  + TripAdvisor Apify (20 reviews, newest)
  + SerpAPI Google Maps Reviews (20 reviews, newest + lowest-rated)
  = 45 reviews per venue, 2 sources (3 retrieval paths)
  → Directional confidence tier
```

This adds the negative review signal that Google's 'most relevant' API misses. SerpAPI's `google_maps_reviews` endpoint supports sorting by `newest` and `lowest_rated`, giving access to the complaint signal that is currently invisible.

### Phase 3: Longer-term

```
All Phase 2 sources
  + Monthly delta collection (only new reviews since last run)
  + Review response tracking (does the venue reply?)
  + Cross-venue comparison corpus
  = 45+ reviews per venue, refreshed monthly
  → Established confidence tier (after 3 months of accumulation)
```

---

## Confidence Tier Targets

| Tier | Text count | Sources | Claim level | Current venues | After Phase 1 |
|------|----------:|--------:|-------------|---------------:|--------------:|
| None | 0 | 0 | No claims | ~200 | 0 |
| Anecdotal | 1-5 | 1 | Observe themes | ~2 | ~30 (TA no-match) |
| Indicative | 6-15 | 1-2 | Direction + early claims | 0 | ~170 |
| Directional | 16-30 | 2+ | Supported claims | 0 | ~10 (high-match) |
| Established | 30+ | 2+ | Confident claims | 0 | 0 (needs Phase 2) |

---

## Implementation Priority

1. **Get APIFY_TOKEN** — free tier covers this. Set as env var or GitHub secret.
2. **Run TripAdvisor collection** — existing script, ~30 minutes for 210 venues.
3. **Merge and re-score** — existing merge script handles this.
4. **Regenerate reports** — all venues automatically upgrade confidence tier.
5. **Evaluate SerpAPI** — if TripAdvisor coverage is insufficient or negative signal is needed.

---

*This document is maintained at `review_collection_architecture.md` in the DayDine repository.*
