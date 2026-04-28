# DayDine V5 Evidence Rank Blueprint

**Status:** Build-ready methodology blueprint  
**Created:** 28 April 2026  
**Purpose:** Define the next DayDine methodology build so implementation can proceed beside V4 without more strategic ambiguity.

---

## 1. Executive summary

V5 is the next DayDine methodology direction.

V4 remains the strongest implemented baseline and must be preserved for comparison. V5 should be built beside V4, tested on Stratford-upon-Avon and Leamington Spa, and only promoted after comparison, QA and public-copy review.

V5 should not be a simple review aggregator.

V5 should be:

> A proprietary hospitality intelligence model that includes authorised public review evidence, but separates popularity from quality, confidence from score, and proven venues from hidden-gem or overexposed venues.

The competitive objective is not to claim that DayDine has more review data than Tripadvisor. Tripadvisor has a major review-data advantage, especially among already-visible top venues. DayDine's advantage should be the ability to interpret the whole local market with evidence confidence, category context, hidden-gem detection, overexposure detection, monthly movement and operator intelligence.

---

## 2. Strategic rules

### 2.1 Valid from day one without Tripadvisor/OpenTable

V5 must be valid at launch without Tripadvisor or OpenTable data.

Tripadvisor and OpenTable can improve future confidence if obtained through an approved route, but V5 must not require them to function.

### 2.2 Authorised review evidence is allowed

Google review rating and Google review volume can be used and described as authorised public review evidence.

DayDine may say:

> Rankings include authorised public review evidence, including Google review rating and review volume.

DayDine must not say:

> Rankings include Tripadvisor/OpenTable reviews.

unless that becomes true through approved access.

### 2.3 Proprietary methodology, not public formula

Public methodology should explain principles but not expose exact weights or component-level scorecards.

Public surfaces should use:

- rank;
- movement;
- category rank;
- Evidence Confidence;
- DayDine Signal;
- short intelligence note;
- simple coverage summary.

Internal/admin surfaces may expose more diagnostics.

---

## 3. V5 output contract

Each ranked venue should emit an internal output record with at least:

```text
venue_id
market_slug
canonical_name
category
subcategory/occasion tags where available
v5_score_estimate
v5_score_band or uncertainty range
v5_overall_rank
v5_category_rank
v5_expected_rank if simulation exists
v5_rank_band if simulation exists
v5_top_10_probability if simulation exists
v5_top_30_probability if simulation exists
evidence_confidence
coverage_status
entity_resolution_confidence
daydine_signal
daydine_gap_signal
movement_30d
movement_previous_period
last_updated
source_refresh_summary
public_intelligence_note
internal_diagnostics
```

Public JSON should exclude sensitive/internal diagnostics and exact component weights.

---

## 4. Public labels

### 4.1 Evidence Confidence

Suggested public bands:

| Band | Meaning |
|---|---|
| **Very High** | Strong evidence depth, stable identity, strong customer validation and low ambiguity. |
| **High** | Good evidence base with no major coverage or entity weakness. |
| **Medium** | Useful evidence, but some source breadth or confidence limitations. |
| **Low** | Thin or incomplete evidence; rank should be treated cautiously. |
| **Profile Only** | Venue listed but not strongly ranked. |

Single-platform review evidence can still rank, but should cap confidence until cross-platform authorised data exists.

### 4.2 DayDine Signal

Use signals rather than public component scorecards.

| Signal | Meaning |
|---|---|
| **Proven Leader** | Strong position with strong evidence. |
| **Established Favourite** | Durable public reputation and stable market presence. |
| **Hidden Gem** | Strong underlying indicators relative to current public visibility. |
| **Rising Venue** | Improving evidence, visibility or rank movement. |
| **Specialist Pick** | Particularly strong within a category, occasion or niche. |
| **Overexposed** | High visibility but weaker supporting evidence relative to comparable venues. |
| **Under-Evidenced** | Evidence is too thin for a strong judgement. |
| **Profile Only** | Listed for coverage, not confidently ranked. |

### 4.3 DayDine Gap Signal

The Gap Signal measures the distance between public popularity and underlying DayDine evidence/intelligence.

Positive gap:

> Stronger than public visibility suggests.

Negative gap:

> More visible than supporting signals suggest.

Neutral:

> Public visibility broadly matches supporting evidence.

Public display should be elegant, for example:

```text
DayDine Signal: Hidden Gem
Evidence Confidence: Medium
Category Rank: #4
Movement: ▲ 8

A strong underlying profile relative to its current public visibility.
```

Do not show exact gap formula publicly.

---

## 5. Evidence families

V5 should use evidence families rather than a single public component table.

### 5.1 Authorised Review Evidence

Initial fields:

```text
google_rating
google_user_ratings_total
google_business_status
last_google_refresh
```

Future optional fields if authorised:

```text
tripadvisor_rating
tripadvisor_review_count
opentable_rating
opentable_review_count
other_platform_rating/count
```

Rules:

- Use Bayesian/shrinkage-aware logic.
- Cap/saturate review-count benefit.
- Review count increases confidence more than quality.
- Do not use review text in headline ranking unless the source is authorised and the methodology is reviewed.

### 5.2 Trust and Compliance

Initial fields:

```text
fhrsid
fhrs_rating
fhrs_rating_date
local_authority
inspection_recency
closed/dissolved/permanently_closed indicators
```

Rules:

- FHRS is trust/compliance, not food quality.
- Use poor trust results as gates/caps/penalties.
- A high FHRS rating should not by itself imply high restaurant quality.

### 5.3 Venue Identity and Entity Resolution

Fields:

```text
canonical_name
trading_names
fsa_match_status
google_place_id
google_match_status
address_match_score
postcode_match
lat/lon distance
entity_resolution_confidence
ambiguity_flags
human_reviewer_notes
```

Rules:

- Ambiguous venues should not be silently ranked.
- Entity uncertainty should reduce confidence or mark as profile-only.

### 5.4 Commercial Accessibility / Venue Surface

Fields:

```text
website_url
menu_url
phone
opening_hours
booking_url/contact path
price/category if available
photos/profile completeness where available
```

Rules:

- Important for public usefulness and operator intelligence.
- Should not over-dominate public quality ranking.
- More heavily weighted in operator dashboards than public rankings.

### 5.5 Category and Occasion Context

Fields:

```text
primary_category
secondary_categories
occasion_tags
cuisine_tags
pub/cafe/fine-dining/casual/takeaway/hotel restaurant flags
```

Rules:

- Always emit category-normalised ranks.
- Do not compare cafés, pubs, fine dining, hotel restaurants and takeaways solely in one undifferentiated list.

### 5.6 Recognition Layer

Manual/licensing-aware fields:

```text
michelin_listing
michelin_star_level
michelin_bib_gourmand
aa_rosette_level
local_awards
credible_press_mentions
expert_source_urls
last_verified
```

Rules:

- Add manually or through legally clean APIs/data providers.
- Recognition can influence category and Proven Leader status.
- Do not scrape protected guide content as a core dependency.

### 5.7 Market Presence and Momentum

Fields:

```text
current_rank
previous_rank
rank_movement
rating_movement
review_volume_movement
website/contact/profile completeness changes
visibility indicators if available
```

Rules:

- Monthly movement should become a core DayDine differentiator.
- Movement should be smoothed to avoid noise.
- Public arrows should avoid over-precision.

### 5.8 Coverage and Source Confidence

Fields:

```text
market_coverage_certificate_id
source_count
source_refresh_age
known_missing_flag
ambiguous_entity_flag
profile_only_reason
rankability_class
```

Rules:

- Coverage confidence must be visible enough to build trust.
- Exact source mechanics remain internal.

---

## 6. Suggested internal scoring architecture

Do not publish exact weights publicly. Internally, V5 can start with family-level score components and then move toward uncertainty simulation.

Suggested internal family directions:

| Family | Internal role |
|---|---|
| Authorised Review Evidence | Main public reputation input, shrinkage-aware and volume-capped. |
| Trust & Compliance | Gates, caps, confidence modifier and limited positive signal. |
| Venue Surface / Accessibility | Public usefulness + operator actionability. |
| Category Context | Normalisation and fair comparison. |
| Recognition | Distinction signal and category reinforcement. |
| Market Presence / Momentum | Movement, durability and current market strength. |
| Entity/Coverage Confidence | Rankability gate and confidence factor. |

Important principle:

> Evidence confidence is not the same as quality. Do not collapse them into one public number.

---

## 7. Mathematical requirements

### 7.1 Bayesian rating/shrinkage

V5 should preserve Bayesian/shrinkage logic:

```text
shrunk_rating = (n * observed_rating + k * prior) / (n + k)
```

Use market/category priors where possible.

### 7.2 Saturating review count

Review-count benefit should saturate.

Example principle:

```text
30 reviews -> basic evidence
100 reviews -> useful evidence
250 reviews -> strong evidence
750+ reviews -> very strong evidence, but limited further quality benefit
```

The exact thresholds should be calibrated by market/category and kept internal.

### 7.3 Confidence bands

Each venue should carry evidence confidence independent of rank.

Factors:

- review volume;
- source breadth;
- source recency;
- entity certainty;
- coverage certificate status;
- ambiguity flags;
- missing data.

### 7.4 Rank uncertainty / simulation

Later V5 should support:

```text
expected_rank
likely_rank_band
top_10_probability
top_30_probability
```

This can be introduced after the first V5 deterministic prototype.

---

## 8. Public methodology copy direction

Use public language like:

> DayDine ranks restaurants using a proprietary hospitality intelligence model. Rankings include authorised public review evidence, including Google rating and review volume, alongside trust signals, venue information, category context, market visibility, recognition signals and evidence confidence.

Also state:

> We do not publish exact weights or the full formula because rankings must remain resistant to manipulation. We publish principles, coverage notes and confidence bands so diners and operators can understand the nature of each ranking.

Avoid:

- exact public weights;
- public component scorecards;
- 40+ signal claims unless implemented;
- aspect-level review-intelligence claims unless authorised review text exists;
- cross-source review-convergence claims unless at least two populated independent review platforms exist.

---

## 9. Public UX requirements

Ranking cards should move toward:

```text
#12 Venue Name
DayDine Signal: Proven Leader
Evidence Confidence: High
Category Rank: #3 Modern British
Movement: ▲ 2

Short intelligence note.
```

Recommended public ranking views:

1. Proven Leaders
2. Hidden Gems
3. Rising Venues
4. Category Champions
5. Full Market Board
6. Most Trusted by Evidence

A single overall leaderboard can exist, but it should not be the only product surface.

---

## 10. Operator/report requirements

Operator dashboards can expose more actionable diagnosis than public pages, but still should not reveal exact model weights.

Operator-facing insights should include:

- current overall/category rank;
- movement;
- Evidence Confidence;
- DayDine Signal;
- nearest competitors;
- visibility gaps;
- booking/contact/menu/profile gaps;
- confidence gaps;
- why the venue is likely rising/flat/falling;
- actions likely to improve public evidence or commercial capture.

Keep the language directional:

> Most likely limiting factor: weak booking/contact path.

Rather than formula-revealing:

> Booking URL contributes exactly X% of the score.

---

## 11. Build plan

### Phase V5.0 — Deterministic prototype beside V4

Tasks:

```text
[ ] Create V5 output schema.
[ ] Map existing V4/FSA/Google fields into V5 evidence families.
[ ] Add DayDine Signal classifier.
[ ] Add Evidence Confidence classifier.
[ ] Add Gap Signal classifier.
[ ] Add category-normalised ranking.
[ ] Preserve V4 outputs unchanged.
[ ] Compare Stratford V4 vs V5 top 30.
[ ] Compare Leamington V4 vs V5 top 30.
```

### Phase V5.1 — Coverage and movement

Tasks:

```text
[ ] Generate coverage certificates for Stratford and Leamington.
[ ] Add simple public coverage summaries.
[ ] Add previous-period rank input where available.
[ ] Emit movement arrows.
[ ] Add admin diagnostics for profile-only/under-evidenced venues.
```

### Phase V5.2 — Recognition and market QA

Tasks:

```text
[ ] Add expert-recognition schema.
[ ] Add manual QA fields.
[ ] Add missing-venue audit layer.
[ ] Spot-check top 30 and Hidden Gems list manually.
[ ] Record QA notes in admin/internal artifacts.
```

### Phase V5.3 — Rank uncertainty

Tasks:

```text
[ ] Add score uncertainty ranges.
[ ] Add expected rank / rank band simulation.
[ ] Add top-10/top-30 probability where stable.
[ ] Keep public display simple.
```

---

## 12. Acceptance criteria before public cutover

V5 is ready for public beta when:

```text
[ ] V4 remains available for comparison.
[ ] V5 produces stable outputs for Stratford.
[ ] V5 produces stable outputs for Leamington or clearly labels warnings.
[ ] Top 30 in each market are manually spot-checked.
[ ] Hidden Gems list does not contain obvious poor/irrelevant venues.
[ ] Overexposed label is used carefully or held for internal/operator use if too commercially sensitive.
[ ] Public methodology copy is updated.
[ ] Public copy includes authorised review evidence but not Tripadvisor/OpenTable claims.
[ ] Coverage certificate exists for each public market.
[ ] Entity ambiguity gates are respected.
[ ] Firebase/client/admin work is not blocked by methodology uncertainty.
```

---

## 13. Immediate next implementation instruction

The next build phase should proceed in this order:

1. Build Firebase Auth + role-based `/client` and `/admin` foundations.
2. Migrate Lambs dashboard into protected Firebase data.
3. Build Stratford and Leamington coverage certificates.
4. Prototype V5 deterministic outputs beside V4.

Do not pause for further methodology strategy unless a concrete implementation blocker appears.
