# DayDine Review Data Collection Strategy

**Version:** 1.0
**Date:** 5 April 2026
**Status:** Approved for implementation
**Scope:** Stratford-upon-Avon trial (210 establishments), extensible to UK-wide rollout

---

## Table of Contents

1. [Current State Audit](#1-current-state-audit)
2. [Source-by-Source Evaluation](#2-source-by-source-evaluation)
3. [Legal & Practical Risk Assessment](#3-legal--practical-risk-assessment)
4. [Recommended Strategy](#4-recommended-strategy)
5. [Implementation Roadmap](#5-implementation-roadmap)

---

## 1. Current State Audit

### 1.1 Executive Summary

The DayDine platform's review data infrastructure is critically underpopulated. Despite a 34-module operator intelligence pipeline designed around rich review text, the system currently holds **only 40 review texts** across the entire 210-establishment Stratford dataset. This represents approximately 2% of the system's designed capacity.

### 1.2 Current Data Sources

| Source | Status | Records | Data Quality | Automation |
|---|---|---|---|---|
| FSA Hygiene (Firebase RTDB) | **Working** | 208/208 (100%) | Authoritative | Manual trigger |
| Google Places API (ratings/counts) | **Working** | 228/240 matched | High | Manual trigger |
| Google Places API (review text) | **Severely limited** | 4 venues, 20 texts | API hard limit of 5/venue | Manual trigger |
| TripAdvisor (bulk Apify) | **Broken** | 0/210 matched | N/A — zero data collected | Manual trigger, continues-on-error |
| TripAdvisor (one-off Vintner) | **One-time success** | 1 venue, 20 texts | Good quality, date anomalies | None — manual one-off |
| Menu/dietary data | **Working** | 171/240 with menus | Reasonable | Manual trigger |
| Editorial/awards | **Working (low data)** | 1/240 with data | Low coverage expected | Manual trigger |
| Companies House | **Non-functional** | 0/240 checked | All records show "not_checked" | Manual trigger, continues-on-error |
| Sentiment analysis | **Working (no input)** | 4/240 analysed | Depends on review text | Manual trigger |
| Web presence | **Working** | 143 websites, 137 FB, 126 IG | Inference-based | Manual trigger |

### 1.3 Key Findings

**Review text is the critical bottleneck:**
- Total review texts in the system: **40** (20 Google + 20 TripAdvisor one-off)
- Only **4 unique venues** have any review text at all
- 12 of 34 operator intelligence modules directly scan raw review text
- The system is operating at ~2% of its designed capacity

**TripAdvisor bulk collection is completely broken:**
- 210 establishments searched, **0 matched** — 195 returned `_no_match`, 15 returned `_skipped`
- Uses `automation-lab/tripadvisor-scraper` actor with fuzzy name matching (threshold 0.5)
- The `collect_tripadvisor.yml` workflow uses a direct web scraper that is blocked from CI environments
- The `full_pipeline.yml` uses the Apify version but with `continue-on-error: true`, silently swallowing failures

**Google's 5-review hard limit is a ceiling:**
- The Google Places API (New) returns a maximum of 5 reviews per venue — no pagination, no sort control
- Only 4 of 228 matched establishments have `g_reviews` text in the enrichment file
- The enrichment script requests reviews but they are only populated for a subset

**Companies House integration is non-functional:**
- Script and workflow exist, but all 240 records show `company_status: "not_checked"`
- `COMPANIES_HOUSE_API_KEY` secret may not be configured, or the API integration failed silently

**No automated scheduling:**
- All 6 workflows are `workflow_dispatch` only (manual trigger)
- No cron triggers, no push-triggered runs, no scheduled data refreshes
- Data staleness increases over time without manual intervention

**43 missing high-profile establishments:**
- Sanity check identifies missing venues including The Golden Bee (4,931 Google reviews), Caffeine & Machine (4,579), Dirty Duck (3,262)
- These are significant gaps in the Stratford dataset

**Score inflation from missing data:**
- Average signal coverage: 10.5 of 40 signals (26%)
- ALL establishments have confidence: "Low" (margin ±0.8)
- Mean RCS: 8.17 with 62% rated "Excellent" — heavily inflated by interpolation

### 1.4 Review Data Detail

| Venue | FHRSID | Google Reviews | TripAdvisor Reviews | Total |
|---|---|---|---|---|
| The Fox Inn | 1344517 | 5 | 0 | 5 |
| Arrow Mill | 503282 | 5 | 0 | 5 |
| Vintner Wine Bar | 503480 | 5 | 20 | 25 |
| (unnamed) | 503104 | 5 | 0 | 5 |
| **Total** | | **20** | **20** | **40** |

The Vintner Wine Bar is the only venue with multi-source review data. Its 25 reviews provide "Directional" confidence per the system's own thresholds — well below the "Reliable" tier (50-99 reviews) needed for actionable intelligence.

---

## 2. Source-by-Source Evaluation

### 2.1 Evaluation Matrix

| Source | Official API | Apify Actor Available | Data Quality | UK Volume (per venue/month) | Recommendation |
|---|---|---|---|---|---|
| **Google Maps** | Partial (5 reviews, Enterprise tier) | Yes — best-in-class | High (text, rating, date, sub-ratings) | High (15-200+) | **Primary** |
| **TripAdvisor** | Severely limited (5 reviews) | Yes — multiple actors | Highest (sub-ratings, trip type, visit date) | Medium (2-80) | **Secondary** |
| **Facebook** | Own pages only (admin required) | Available but fragile | Medium (binary positive/negative) | Low (5-20) | Skip Phase 1 |
| **Yelp** | 3 truncated snippets only | Available | Low (snippets only via API) | Very low (<5) | **Skip** |
| **OpenTable** | Reservations only (no reviews) | Yes — multiple actors | Very high (all verified diners) | Medium (5-30 if listed) | **Phase 2** |
| **Booking.com** | Hotels only (internal) | Available (hotels only) | Medium | Very low (irrelevant for restaurants) | **Skip** |
| **Deliveroo/UberEats/JustEat** | None | Limited, fragile | Low (short, delivery-focused) | Low (delivery-only) | **Skip** |
| **Instagram** | Own pages only | Available | Low (unstructured captions) | High volume, low quality | Skip Phase 1 |
| **Twitter/X** | $100/mo minimum | N/A | Very low (280 chars, unstructured) | Low | **Skip** |
| **TikTok** | Research API (restricted) | Available | Very low (video, unstructured) | Growing, unstructured | **Skip** |

### 2.2 Detailed Source Assessments

#### Google Maps (Primary Source)

**Official API (Places API New):**
- Returns up to 5 reviews per venue — hard limit, no pagination
- Review fields: text, rating, reviewer name, publish date, visit date (added Oct 2025), sub-ratings (Food/Service/Atmosphere), owner response, photos, language
- Pricing: Enterprise + Atmosphere SKU required for reviews
- Verdict: Useless for volume collection; only suitable for display badges

**Apify actor: `compass/crawler-google-places`**
- Rating: 4.7/5 (1,097 reviews), 341,000+ users, 21,000 monthly active
- Pricing: from $2.10/1,000 places + review add-on (~$1-5/1,000 reviews)
- Capacity: up to 5,000 reviews per venue (pages through all reviews)
- Fields: full text, rating, date, reviewer info (name, ID, IsLocalGuide), owner response, review photos, detailed sub-ratings (Food/Service/Atmosphere)
- Maintained: updated within 3 days of research date

**UK review volume benchmarks:**

| Venue tier | Google reviews per month |
|---|---|
| New/small (<200 total) | 3-15 |
| Established mid-range (200-1,000 total) | 15-50 |
| Popular/destination (1,000+ total) | 50-200+ |

#### TripAdvisor (Secondary Source)

**Official API (Content API):**
- Returns up to 5 reviews per location — same hard limit as Google
- Requires partner application and approval
- Must display TripAdvisor branding — not suitable for competing platforms
- Verdict: Useless for volume; rejected

**Apify actor: `scrapapi/tripadvisor-review-scraper`**
- Pricing: $1.00/1,000 reviews
- Fields: full text, rating, title, trip type (FAMILY/COUPLES/SOLO/BUSINESS), travel date (month/year), sub-ratings (Food/Service/Value/Atmosphere), reviewer profile + location, helpful votes, owner response, language
- TripAdvisor provides the **richest structured review data** of any platform — trip type and visit date are unique and valuable for segmentation

**UK review volume benchmarks:**

| Venue type | TripAdvisor reviews per month |
|---|---|
| Small independent | 2-10 |
| Established mid-range | 8-30 |
| Popular London destination | 20-80 |

**Known issue from current implementation:** The `automation-lab/tripadvisor-scraper` actor used in `collect_tripadvisor_apify.py` produced zero matches. Replace with `scrapapi/tripadvisor-review-scraper` which has better venue resolution using coordinates.

#### OpenTable (Phase 2 Supplementary)

**Apify actor: `scraped/opentable-review-scraper`**
- Pricing: $8.00/1,000 results
- Fields: full text, overall rating, sub-ratings (Food/Service/Atmosphere), reviewer first name, visit date, verified diner badge (implicit — all OpenTable reviews are from completed bookings)
- Major advantage: **all reviews are from verified diners** — eliminates fake reviews
- Major limitation: only restaurants using OpenTable have reviews; excludes pubs, casual venues, non-OpenTable bookers

#### Sources Skipped

**Yelp:** Negligible UK coverage. API returns only 3 truncated snippets. Declining UK relevance. Engineering effort-to-value ratio is poor.

**Booking.com:** Hotel-focused only. Standalone restaurants are not listed. Reviews conflate accommodation and dining quality.

**Deliveroo/Uber Eats/Just Eat:** No public APIs. Reviews are short, delivery-focused, and irrelevant for dine-in venues. A wine bar is unlikely to be listed at all.

**Facebook:** API requires page admin permission (not scalable for third-party collection). Binary positive/negative system limits scoring granularity. Text is typically brief. Revisit if restaurant onboarding flow is built.

**Instagram/TikTok/Twitter:** Unstructured content (captions, videos, short posts). No standardised rating. Useful as a "social buzz" signal layer in Phase 2 but not suitable for structured review analysis in Phase 1.

---

## 3. Legal & Practical Risk Assessment

### 3.1 Risk Matrix

| Source | Method | Legal Risk | Practical Risk | Recommendation |
|---|---|---|---|---|
| Google | Official Places API | ✅ Low | ✅ Low (but 5-review limit) | Use for metadata only |
| Google | Apify (`compass/crawler-google-places`) | 🟡 Medium | 🟡 Medium (anti-bot, CAPTCHAs) | **Use — primary review source** |
| Google | Direct web scraping | 🔴 High | 🔴 High (blocked, maintenance) | Avoid |
| TripAdvisor | Official Content API | ✅ Low | ✅ Low (but 5-review limit) | Use for metadata only |
| TripAdvisor | Apify (`scrapapi/tripadvisor-review-scraper`) | 🟡 Medium | 🟡 Medium (anti-bot, fingerprinting) | **Use — secondary review source** |
| TripAdvisor | Direct web scraping | 🔴 High | 🔴 High (blocked from CI) | Avoid (already proven blocked) |
| Facebook | Graph API (own pages) | ✅ Low | 🟡 Medium (requires admin access) | Skip Phase 1 |
| Facebook | Apify/scraping | 🔴 High | 🔴 High (fingerprinting, login walls) | Avoid |
| Yelp | Fusion API | ✅ Low | ✅ Low (3 snippets only) | Skip — negligible UK value |
| Yelp | Apify/scraping | 🟡 Medium | 🟡 Medium (CAPTCHAs) | Skip — negligible UK value |
| OpenTable | Apify (`scraped/opentable-review-scraper`) | 🟡 Medium | ✅ Low | **Phase 2 — verified diners** |

### 3.2 Legal Framework

**UK legal position on scraping publicly accessible data:**
- The Computer Misuse Act 1990 applies to unauthorised access; public data (no login required) is generally lawful to access
- The hiQ Labs v. LinkedIn ruling (US) and subsequent cases establish that scraping public data does not constitute computer fraud
- EU Database Directive (retained in UK law) protects databases with substantial investment — but individual reviews are user-generated content, not the platform's creative work
- ToS-as-contract argument (civil breach) is the main risk, not criminal liability

**Practical enforcement reality:**
- Google has not pursued legal action against review scrapers — enforcement is technical (blocking, CAPTCHAs)
- TripAdvisor has not pursued UK legal action against review data collection for research/ranking platforms
- No known UK enforcement action against restaurant review aggregation
- The FTC Consumer Review Rule (Oct 2024) targets **fake reviews**, not data collection

**GDPR considerations:**
- Reviews contain personal data (reviewer names, locations)
- Lawful basis: legitimate interests for research/ranking (likely applicable)
- Mitigation: pseudonymise reviewer names in stored data; display only aggregate data to end users
- Recommended: legal review before UK-wide launch

### 3.3 Mitigation Strategy

1. Use Apify's residential proxies (avoids direct IP attribution)
2. Respect `robots.txt` where possible
3. Do not republish raw review text verbatim in consumer-facing output
4. Maintain responsible rate limiting (built into Apify actors)
5. Store reviewer names but pseudonymise in reports and public output
6. Conduct formal legal review before scaling beyond Stratford trial

---

## 4. Recommended Strategy

### 4.1 Primary Sources

| Source | Apify Actor | Role | Collection Frequency |
|---|---|---|---|
| **Google Maps** | `compass/crawler-google-places` | Primary review source — highest UK volume | Fortnightly (1st and 15th) |
| **TripAdvisor** | `scrapapi/tripadvisor-review-scraper` | Secondary source — richest structured data | Fortnightly (1st and 15th) |

### 4.2 Secondary Sources (Phase 2)

| Source | Apify Actor | Role | When to Add |
|---|---|---|---|
| **OpenTable** | `scraped/opentable-review-scraper` | Supplementary for listed venues — verified diners | After primary sources stable |

### 4.3 Sources to Skip (Phase 1)

- **Yelp** — Negligible UK coverage, API returns truncated snippets only
- **Booking.com** — Hotel-focused, irrelevant for standalone restaurants
- **Deliveroo/Uber Eats/Just Eat** — No APIs, delivery-focused reviews irrelevant for dine-in
- **Facebook** — Requires admin access, binary system, lower quality
- **Instagram/TikTok/Twitter** — Unstructured, no standardised ratings, Phase 2 social signal layer

### 4.4 Minimum Viable Data Specification

For a venue report to achieve "Reliable" confidence:

| Metric | Minimum Threshold | Ideal Target |
|---|---|---|
| Total reviews | 50 | 100+ |
| Reviews with text (not rating-only) | 30 | 75+ |
| Minimum words per review (for theme analysis) | 20 | 50+ |
| Number of platforms | 2 | 3 |
| Date coverage (reporting period) | 6 months | 12 months |

**Data confidence tiers:**

| Tier | Total Reviews | Description |
|---|---|---|
| **Robust** | 100+ | Statistically significant, multi-source, full theme extraction |
| **Reliable** | 50-99 | Actionable intelligence, clear patterns, some gaps possible |
| **Directional** | 25-49 | Indicative trends, handle with caveats |
| **Indicative** | <25 | Limited signal, rating-only analysis recommended |

### 4.5 Data Quality Rules

Each collected review is classified into a quality tier:

| Quality Tier | Criteria | Treatment |
|---|---|---|
| **HIGH** | 50+ words, mentions food/service/atmosphere/value keywords | Full theme and sentiment analysis |
| **MEDIUM** | 20-50 words, at least one specific mention | Theme extraction with reduced confidence |
| **LOW** | <20 words or rating-only (no text) | Rating signal only, no theme extraction |
| **EXCLUDE** | <5 words (excluding rating-only), detected spam patterns, duplicate text, staff reviews | Excluded from all analysis |

**Spam detection patterns:**
- Repeated identical text across venues
- Keyword stuffing (SEO-style content)
- Reviews containing competitor business names as endorsements
- Reviews with dates in the future (known TripAdvisor Apify actor artifact)

**Deduplication rules:**
- Same source + same review ID = exact duplicate (remove)
- Cross-source: fuzzy text similarity >80% (difflib.SequenceMatcher) + same calendar day = duplicate (keep the version with richer metadata)

### 4.6 Collection Schedule

**Frequency:** Fortnightly — 1st and 15th of each month at 2:00 AM UTC

Rationale:
- Monthly is too infrequent for tracking emerging trends or operational issues
- Weekly is unnecessary for Stratford-scale venues (most receive <50 reviews/month)
- Fortnightly balances data freshness with Apify cost efficiency
- 2:00 AM UTC minimises load on source platforms and GitHub Actions runners

**Workflow:** `.github/workflows/collect_reviews.yml`
- Triggered by cron schedule AND manual `workflow_dispatch`
- Collects Google reviews, then TripAdvisor reviews (sequential, not parallel — avoids Apify concurrent run limits on Starter plan)
- Merges multi-source reviews with deduplication
- Runs collection health monitor
- Commits results to repository

### 4.7 Cost Estimates

**Apify Starter Plan ($29/month):**

| Item | 10 restaurants | 50 restaurants |
|---|---|---|
| Google reviews (Compass actor) | ~$2-5/run | ~$10-20/run |
| TripAdvisor reviews (scrapapi actor) | ~$1-2/run | ~$5-8/run |
| Residential proxy data (~0.5GB/run) | ~$4/run | ~$8/run |
| **Monthly (2 runs)** | **~$14-22** | **~$46-72** |
| **Platform subscription** | $29 | $29 (Starter) or $199 (Scale) |
| **Total monthly** | **~$29-35** | **~$29-40** (Starter, within credits) |

For 50+ restaurants, the Scale plan ($199/month) provides better unit economics with $199 in credits and lower proxy rates ($7.50/GB vs $8.00/GB).

**Initial historical pull (one-time cost):**
- 10 restaurants, ~500 Google + ~200 TripAdvisor reviews each: ~$12-15
- 50 restaurants: ~$40-60
- Well within Starter plan monthly credits

---

## 5. Implementation Roadmap

### Phase 1: Foundation (This Week)

- [ ] Set up Apify Google Reviews actor (`compass/crawler-google-places`)
  - Create `.github/scripts/collect_google_reviews_apify.py`
  - Test with 5 Stratford venues
  - Validate output format and review field coverage
- [ ] Fix TripAdvisor collection
  - Create `.github/scripts/collect_tripadvisor_reviews_apify.py` using `scrapapi/tripadvisor-review-scraper`
  - Use coordinates (lat/lon from Google data) for venue matching instead of name-only fuzzy match
  - Test with 5 Stratford venues
  - Validate date handling (flag future dates from Apify actor artifact)
- [ ] Create data directory structure
  - `data/raw/google/`, `data/raw/tripadvisor/`, `data/raw/opentable/`, `data/processed/`
- [ ] Build collection monitoring
  - Create `.github/scripts/review_data_monitor.py`
  - Generate `data/collection_health.json` with per-venue stats
  - Maintain `data/collection_log.txt` with timestamped entries
- [ ] Migrate existing data
  - Copy `vintner_ta_raw.json` to `data/raw/tripadvisor/vintner_wine_bar_2026-04-01.json`
  - Extract `g_reviews` from `stratford_google_enrichment.json` for 4 venues to `data/raw/google/`

### Phase 2: Automation (This Month)

- [ ] Build automated collection schedule via GitHub Actions
  - Create `.github/workflows/collect_reviews.yml` with fortnightly cron
  - Sequential: Google collection -> TripAdvisor collection -> Merge -> Monitor -> Commit
- [ ] Add deduplication logic
  - Cross-source fuzzy text matching (80%+ similarity + same-day date)
  - Same-source exact ID matching
- [ ] Add data quality filtering
  - HIGH/MEDIUM/LOW/EXCLUDE classification
  - Spam pattern detection
  - Future date flagging and correction
- [ ] Integrate with report pipeline
  - Update `operator_intelligence/report_generator.py` with data confidence warnings
  - Update `operator_intelligence/builders/data_basis.py` with source breakdown and confidence tier
  - Add multi-source review reading from `data/processed/` combined files

### Phase 3: Expansion (Next Month)

- [ ] Add OpenTable for listed restaurants
  - Create OpenTable collection script using `scraped/opentable-review-scraper`
  - Identify Stratford venues listed on OpenTable
  - Add to fortnightly collection workflow
- [ ] Build volume monitoring alerts
  - Alert when collection success rate drops below 80%
  - Alert when any venue falls below minimum review threshold for >2 collection cycles
  - GitHub Actions job failure notifications
- [ ] Optimise collection costs
  - Track per-run Apify credit usage
  - Implement delta-only collection (skip venues with recent data)
  - Reduce proxy usage by tuning actor concurrency settings

### Phase 4: Future Enhancements (Ongoing)

- [ ] Evaluate social media signals (Instagram location tags, TikTok mentions)
- [ ] Track costs per venue per month; optimise actor selection based on cost-per-review
- [ ] Consider Facebook partnerships (restaurant onboarding with page access grants)
- [ ] Build SerpAPI/Outscraper integration as Google Apify actor backup
- [ ] Implement review text pseudonymisation for GDPR compliance before UK-wide launch
- [ ] Add Google review deletion tracking (240M+ reviews deleted in 2024; affects corpus stability)

---

## Appendix A: Architecture

```
Collection Layer (Apify)
    |
    +-- compass/crawler-google-places (fortnightly)
    +-- scrapapi/tripadvisor-review-scraper (fortnightly)
    +-- scraped/opentable-review-scraper (Phase 2, fortnightly)
    |
    v
Raw Storage (data/raw/{source}/)
    |  {slug}_{YYYY-MM-DD}.json per venue per collection
    |
    v
Merge & Quality Filter (merge_multi_source_reviews.py)
    |  Deduplication, quality classification, spam removal
    |
    v
Processed Storage (data/processed/)
    |  {slug}_{YYYY-MM}_combined.json (included reviews)
    |  {slug}_{YYYY-MM}_excluded.json (excluded reviews)
    |
    v
Analysis Pipeline
    +-- rcs_scoring_stratford.py (aggregate signals only: ratings, counts)
    +-- operator_intelligence/ (full review text analysis: themes, risk, segments)
    |
    v
Reports (outputs/monthly/, outputs/quarterly/)
    +-- Per-venue operator intelligence reports
    +-- Confidence warnings when below thresholds
```

## Appendix B: Apify Actor Quick Reference

| Actor | ID | Cost | Use Case |
|---|---|---|---|
| Google Maps Scraper | `compass/crawler-google-places` | $2.10/1K places + reviews | Full Google review history |
| Google Reviews Scraper | `web_wanderer/google-reviews-scraper` | $0.35/1K reviews | Budget Google backup |
| TripAdvisor Review Scraper | `scrapapi/tripadvisor-review-scraper` | $1.00/1K reviews | Full TA review data |
| TripAdvisor Reviews (Camoufox) | `marklp/tripadvisor-reviews-scraper` | $1.00/1K reviews | TA backup (anti-detection) |
| OpenTable Review Scraper | `scraped/opentable-review-scraper` | $8.00/1K results | Verified diner reviews |
| Restaurant Review Aggregator | `tri_angle/restaurant-review-aggregator` | Per event | Multi-platform bundle |

## Appendix C: Current vs Target Data Coverage

| Metric | Current State | Phase 1 Target | Phase 2 Target |
|---|---|---|---|
| Venues with review text | 4 (1.9%) | 50+ (24%) | 150+ (71%) |
| Total review texts | 40 | 2,500+ | 10,000+ |
| Average reviews per venue | 0.19 | 50+ | 100+ |
| Sources active | 1 (Google, 5/venue) | 2 (Google + TripAdvisor) | 3 (+OpenTable) |
| Collection frequency | Manual, ad-hoc | Fortnightly automated | Fortnightly automated |
| Confidence tier (average) | Indicative | Directional-Reliable | Reliable-Robust |

---

*Strategy document prepared 5 April 2026. Based on repository audit (commit 3e29d38) and source research completed same date.*
