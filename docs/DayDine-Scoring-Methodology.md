# DayDine Scoring Methodology

**Restaurant Confidence Score (RCS) — Version 3.4**
*Last updated: April 2026*

---

## 1. What This Document Covers

This document explains how DayDine calculates the Restaurant Confidence Score — the 0–10 metric that powers every ranking, report, and competitive benchmark on the platform.

The RCS is an **external blind-spot report**. It surfaces what a well-informed outsider can see about a restaurant from public data alone. It does not require POS integration, internal data feeds, or operator-side instrumentation.

**The score answers one question:** *What does the publicly observable evidence say about this venue's market confidence?*

---

## 2. Score Scale

| Property | Value |
|---|---|
| Range | 0.000 – 10.000 |
| Precision | 3 decimal places |
| Uniqueness | Guaranteed — tiebreaker system ensures no two venues share a rank |
| Update frequency | Weekly |

### Rating Bands

| Band | RCS Range | What It Means |
|---|---|---|
| **Excellent** | 8.000 – 10.000 | Outstanding across multiple dimensions; strong data convergence |
| **Good** | 6.500 – 7.999 | Consistently positive; minor gaps in one area |
| **Generally Satisfactory** | 5.000 – 6.499 | Adequate; notable gaps or mixed signals |
| **Improvement Necessary** | 3.500 – 4.999 | Significant concerns; multiple penalties triggered |
| **Major Improvement** | 2.000 – 3.499 | Critical issues; enforcement actions or consistently poor ratings |
| **Urgent Improvement** | 0.000 – 1.999 | Severe safety or viability concerns |

---

## 3. The 40 Signals Across 7 Tiers

The score is built from **40+ signals** organised into **7 independent tiers**. No single tier or signal can carry a venue on its own. When data is missing for a tier, the remaining tiers are re-weighted proportionally — the score is never inflated by absent evidence.

---

### Tier 1: Food Safety Authority (FSA) — 23% weight

**What it measures:** Official food safety compliance as assessed by local authority inspectors.

| # | Signal | What It Is | How It's Scored |
|---|---|---|---|
| 1 | **Hygiene rating** | The headline FSA rating (0–5) | Rating / 5 → 0–1 scale |
| 2 | **Structural compliance** | Physical condition of premises (0–25 scale, lower is better) | Inverted and normalised to 0–1 |
| 3 | **Confidence in management** | Inspector's assessment of management systems (0–20, lower is better) | Inverted and normalised to 0–1 |
| 4 | **Food hygiene sub-score** | Hygienic handling, preparation, storage (0–25, lower is better) | Inverted and normalised to 0–1 |
| 5 | **Inspection recency** | Days since last inspection | Penalty modifier: >1 year = −5%, >2 years = −10% of tier score |

**Source:** Food Standards Agency API + Firebase RTDB
**Provenance:** Observed (all signals directly from official records)

---

### Tier 2: Google Signals — 24% weight (capped at 30% effective)

**What it measures:** Public reputation, review sentiment, visual presence, and business profile completeness as seen through Google.

| # | Signal | What It Is | How It's Scored |
|---|---|---|---|
| 6 | **Star rating** | Google Places rating (1–5) | Rating / 5 → 0–1 |
| 7 | **Food quality sentiment** | NLP analysis of review text for food-related praise/complaints | Keyword sentiment score 0–1 |
| 8 | **Service quality sentiment** | NLP analysis for service-related mentions | Keyword sentiment score 0–1 |
| 9 | **Ambience sentiment** | NLP analysis for atmosphere/setting mentions | Keyword sentiment score 0–1 |
| 10 | **Value perception sentiment** | NLP analysis for value-for-money mentions | Keyword sentiment score 0–1 |
| 11 | **Wait time sentiment** | NLP analysis for wait/speed-of-service mentions | Keyword sentiment score 0–1 |
| 12 | **Overall review sentiment** | Aggregate sentiment across all review text | Keyword analysis score 0–1 |
| 13 | **Review count** | Total number of Google reviews | log₁₀(count) / log₁₀(1000), capped at 1.0 |
| 14 | **Price level** | Google's price indicator (1–4) | Level / 4 → 0–1 |
| 15 | **Photo count** | Number of photos on the listing | min(count, 10) / 10 → 0–1 |
| 16 | **Place types** | Whether Google classifies as a food venue | Binary: food type present = 1.0 |

**Caps:**
- Google's effective weight is capped at 30% even when other tiers are missing
- Combined Google-derived influence across all tiers is capped at 45%

**Red flag system:** Dozens of critical phrases in review text trigger red flags. 2+ red flags generate a warning and a −15% penalty.

**Source:** Google Places API
**Provenance:** Signals 6, 13–16 are observed; signals 7–12 are derived (computed from review text via NLP)

---

### Tier 3: Online Presence — 13% weight (TripAdvisor primary)

**What it measures:** How the venue appears on independent review platforms and across the web.

| # | Signal | What It Is | How It's Scored |
|---|---|---|---|
| 17 | **TripAdvisor presence** | Whether the venue has a TripAdvisor listing | Boolean: present = 1.0 |
| 18 | **TripAdvisor rating** | TA rating (1–5) | Rating / 5 → 0–1 |
| 19 | **TripAdvisor review count** | Number of TA reviews | log₁₀(count) / log₁₀(1000), capped at 1.0 |
| 20 | **TripAdvisor review recency** | Fraction of reviews less than 6 months old | Ratio 0–1 |
| 21 | **Has website** | Whether the venue has a website | Boolean (confidence layer only — does not affect score) |
| 22 | **Has Facebook** | Whether the venue has a Facebook page | Boolean (confidence layer only) |
| 23 | **Has Instagram** | Whether the venue has Instagram presence | Boolean (confidence layer only) |

**Note:** Signals 21–23 are inferred from Google data and contribute to the confidence grade but not the headline RCS score.

**Source:** TripAdvisor (via Apify scraper), web inference from Google data
**Provenance:** Signals 17–20 are observed when collected; 21–23 are inferred

---

### Tier 4: Operational Signals — 15% weight

**What it measures:** The practical signs of a well-run venue — can a guest book, visit, and access the premises?

| # | Signal | What It Is | How It's Scored |
|---|---|---|---|
| 24 | **Accepts reservations** | Whether the venue accepts bookings | Boolean |
| 25 | **Offers delivery** | Whether delivery is available | Boolean |
| 26 | **Offers takeaway** | Whether takeaway is available | Boolean |
| 27 | **Wheelchair accessible** | Whether the venue is wheelchair accessible | Boolean |
| 28 | **Has parking** | Whether parking is available nearby | Boolean |
| 29 | **Opening hours completeness** | How many days per week have published hours | Days with hours / 7 → 0–1 |

**Source:** Google Places API (types, attributes, hours)
**Provenance:** Mix of observed (from Google attributes) and inferred

---

### Tier 5: Menu & Offering — 10% weight

**What it measures:** Whether the venue's offer is current, clear, and communicated in a way a guest can act on.

| # | Signal | What It Is | How It's Scored |
|---|---|---|---|
| 30 | **Has menu online** | Whether a current menu is publicly accessible | Boolean |
| 31 | **Dietary options count** | Number of dietary accommodations (vegan, GF, halal, etc.) | min(count, 5) / 5 → 0–1 |
| 32 | **Cuisine tags count** | Number of cuisine classifications | min(count, 3) / 3 → 0–1 |
| 33 | **GBP completeness score** | Google Business Profile completeness (10-attribute check) | Attributes present / 10 → 0–1 |

**Source:** Google Places API, website scraping
**Provenance:** Mix of observed and inferred

---

### Tier 6: Reputation & Awards — 8% weight

**What it measures:** Independent editorial recognition — guides, awards, and endorsements from outside the review ecosystem.

| # | Signal | What It Is | How It's Scored |
|---|---|---|---|
| 34 | **Michelin mention** | Star, Bib Gourmand, or Plate listing | Boolean |
| 35 | **AA Rosette rating** | AA restaurant guide rosette | Boolean |
| 36 | **Local awards count** | Regional food awards, tourism board recognition | min(count, 3) / 3 → 0–1 |

**Source:** Michelin Guide, AA Restaurant Guide, local press
**Provenance:** Observed

---

### Tier 7: Companies House — Penalty Only (no base weight)

**What it measures:** Business viability risk signals from public company records. This tier does not contribute positively to the score — it only penalises.

| # | Signal | What It Is | Penalty |
|---|---|---|---|
| 37 | **Company dissolved** | The registered company is dissolved | Hard cap at 3.0 |
| 38 | **Company in liquidation** | The company is in liquidation proceedings | Hard cap at 5.0 |
| 39 | **Accounts overdue** | Company accounts are overdue at Companies House | −0.5 absolute deduction |
| 40 | **Director churn** | 3+ director changes in the past 12 months | −12% of score |

**Source:** Companies House API
**Provenance:** Observed when API key is available; gracefully degraded when absent

---

## 4. Scoring Pipeline

The score is computed in seven sequential stages:

### Stage 1: Signal Collection

Data is collected from all available sources for each establishment:
- Firebase RTDB (FSA base data)
- FSA API (augmented with pubs, bars, takeaways)
- Google Places API (ratings, reviews, photos, types, review text)
- TripAdvisor via Apify (ratings, reviews, cuisine, recency)
- Web inference (website, Facebook, Instagram presence)
- GBP completeness check (10-attribute audit)
- Website scraping (menus, dietary options)
- Editorial check (Michelin, AA, local awards)
- FSA enforcement API (enforcement actions)
- Companies House API (company status, accounts, directors)

### Stage 2: Normalisation

All signals are normalised to a 0–1 scale within their tier. Missing signals are skipped — the tier is re-weighted across available signals only. No signal is ever imputed or assumed.

### Stage 3: Weighted Aggregation

Each tier's score is the weighted average of its available signals. Tier scores are then combined using the tier weights (23%, 24%, 13%, 15%, 10%, 8%). When tiers are missing, weights are redistributed proportionally to active tiers — with the constraint that Google's effective weight never exceeds 30%, and combined Google-derived influence never exceeds 45%.

### Stage 4: Penalty Application

18 penalty rules are applied in order. Penalties either cap the score at a maximum value or reduce it by a percentage:

| # | Condition | Effect |
|---|---|---|
| P1 | FSA rating 0–1 | Hard cap at 2.0 |
| P2 | FSA rating 2 | Hard cap at 4.0 |
| P3 | FSA rating 3 + stale inspection (>2 years) | Hard cap at 7.0 |
| P4 | No inspection in 3+ years | −15% |
| P5 | Google rating < 2.0 | −10% |
| P6 | Google rating 2.0–2.9 | −5% |
| P7 | Zero Google reviews | −5% |
| P8 | Very few reviews (<5 combined) | −3% |
| P9 | No photos at all | −3% |
| P10 | No online presence at all | −10% |
| P11 | TripAdvisor rating < 2.5 | −5% |
| P12 | No opening hours listed (with Google data) | −3% |
| P13 | Multiple red flags (3+) in review text | −15% |
| P14 | Google and TripAdvisor ratings diverge by >2 stars | −5% |
| P15 | Company dissolved | Hard cap at 3.0 |
| P16 | Company in liquidation | Hard cap at 5.0 |
| P17 | Accounts overdue | −0.5 absolute |
| P18 | 3+ director changes in 12 months | −12% |

### Stage 5: Tiebreaker & Ranking

Venues are sorted by final score (descending). Ties are broken in order:
1. More signals available
2. Higher FSA hygiene rating
3. More recent inspection date
4. Higher structural compliance sub-score
5. Higher confidence in management sub-score
6. Alphabetical by business name

Every venue gets a unique rank. No two venues share a position.

### Stage 6: Temporal Decay

Exponential decay is applied to time-sensitive signals so recent evidence carries more weight:

- **FSA inspection age:** ~300-day half-life. Blended: 80% raw score + 20% decay-adjusted.
- **Google review recency:** ~150-day half-life. Applied to the review volume signal when latest review dates are available.

A review from last month carries more weight than one from two years ago. Older signals fade gracefully — they are never simply discarded.

### Stage 7: Cross-Source Convergence

Independent sources (FSA, Google, TripAdvisor) are compared pairwise to assess whether they agree about a venue:

| Condition | Adjustment |
|---|---|
| **Converged** — average divergence ≤ 0.10 | +3% bonus |
| **Neutral** — divergence 0.10–0.20 | No change |
| **Mild divergence** — divergence 0.20–0.30 | −3% penalty |
| **Strong divergence** — divergence > 0.30 | −5% penalty |

Requires at least 2 independent sources. Single-source venues get no convergence adjustment.

---

## 5. Confidence Grading

Every ranked venue carries a confidence grade that communicates how much data underlies its score.

| Confidence Level | Criteria | Score Margin | What It Means |
|---|---|---|---|
| **High** | 20+ signals, 5+ tiers active, 2+ independent sources | ±0.3 | Score is well-supported; diagnosis is reliable |
| **Medium** | 14+ signals, 4+ tiers active | ±0.5 | Core dimensions covered; some lenses limited |
| **Low** | 8+ signals | ±0.8 | Directional only; material gaps remain |
| **Insufficient** | < 8 signals | Not ranked | Cannot produce a meaningful score |

Source independence matters. FSA + Google + TripAdvisor are independent. Google + Google-inferred operational signals are not independent — they count as one source for confidence purposes.

### Signal Provenance

Every signal is classified by how it was obtained:

| Provenance | Definition | Example |
|---|---|---|
| **Observed** | Collected directly from an authoritative source | FSA hygiene rating, Google star rating |
| **Derived** | Computed from observed signals | Aspect sentiment scores (NLP on review text), GBP completeness |
| **Inferred** | Estimated from indirect evidence | Website/Facebook presence inferred from Google data |
| **Not assessed** | Defined but not yet collected for this venue | Companies House when API key is unavailable |

Provenance affects the confidence grade but not the score. Inferred signals carry full weight in scoring — the confidence band communicates the level of trust.

---

## 6. Four Commercial Lenses

The score powers four commercial lenses used in Position & Competitor Reports. Each lens maps to underlying scoring dimensions but is framed in operator language.

### Lens 1: Demand Capture
*Are you converting interest into visits?*

A 7-dimension outside-in audit of the customer journey:

| Dimension | What It Assesses |
|---|---|
| Booking Friction | Can a customer book within 2 clicks from Google Maps? |
| Menu Visibility | Can a customer see the current menu before deciding? |
| CTA Clarity | Does the profile present a clear action path? |
| Photo Mix & Quality | Do the photos sell the experience guests praise? |
| Proposition Clarity | Does the public identity match what guests actually buy? |
| Mobile Usability | Can a mobile user confirm hours, see menu, and book without leaving Maps? |
| Promise vs Path | Is there a gap between what the listing promises and what the path delivers? |

Each dimension receives a verdict: **Clear** / **Partial** / **Missing** / **Broken**.

### Lens 2: Proposition & Guest Signal
*What are guests actually experiencing?*

Multi-platform review intelligence covering aspect-level sentiment (food quality, service, ambience, value, wait times), red-flag detection, cross-source convergence, and the split between reputation baseline and recent movement.

### Lens 3: Trust & Public Risk
*What does the compliance record reveal?*

Official inspection records, structural compliance, management confidence, inspection recency, and business viability screening via Companies House.

### Lens 4: Competitive Market Intelligence
*Where do you sit versus your market?*

Peer benchmarking, category classification (validated across multiple signals with confidence levels), sensitivity analysis, and month-over-month position tracking.

---

## 7. Monthly Delta Tracking

Each scoring run is compared against the prior month's snapshot. The system computes:

- **Rank movement:** Position change (e.g. up 3, down 2, same)
- **Score movement:** RCS change with significance thresholds (<0.2 = negligible, 0.2–0.5 = notable, >0.5 = significant)
- **Per-dimension deltas:** Which signal categories improved or worsened
- **Seasonal classification:** Changes are classified as structural (consistent across 3+ months), seasonal (matches known local patterns), anomaly (single-month deviation), or insufficient data (<3 months history)

Movement is displayed on the public leaderboard as:
- **▲ N** (green) — moved up N positions
- **▼ N** (red) — moved down N positions
- **—** (grey) — no change
- **NEW** (blue) — first appearance

---

## 8. What the Score Is Not

- Not a review of the food or the experience of a particular meal
- Not based on mystery dining, self-reported data, or paid inclusion
- Not a prediction of future performance or financial viability
- Not influenced by advertising, sponsorship, or operator payment
- Not a replacement for internal operating dashboards, management accounts, or compliance audits

---

## 9. Why the Formula Is Not Published

The broad principles behind the ranking are public and explained in this document. The precise weightings, thresholds, penalty multipliers, and processing logic are not.

This is deliberate. A ranking that publishes its exact formula is a ranking that can be gamed — and a gamed ranking is useful to nobody: not diners, not the operators who play fair, and not the industry it exists to measure.

We will always explain *what* the ranking considers. We will not explain it in a way that tells anyone how to manufacture an unearned position.

---

## 10. Data Sources

| Source | What It Provides | Cost |
|---|---|---|
| Food Standards Agency | Hygiene ratings, sub-scores, inspection dates, enforcement actions | Free (public API) |
| Google Places API | Ratings, reviews, review text, photos, types, hours, attributes | Per-request billing |
| TripAdvisor (via Apify) | Ratings, review counts, cuisine tags, review recency | ~£0.003/review |
| Companies House | Company status, accounts filings, director changes | Free (public API) |
| Michelin Guide | Star, Bib Gourmand, Plate listings | Free (web search) |
| AA Restaurant Guide | Rosette ratings | Free (web search) |
| Local press/tourism | Regional food awards | Free (web search) |

All data is publicly accessible. No signal is self-reported by venue operators.

---

## 11. Current Coverage

**Live market:** Stratford-upon-Avon — 190 ranked venues, 210 total establishments assessed.

New markets are added as data pipelines (FSA, Google, TripAdvisor, Companies House) are validated for each Local Authority area.

---

## 12. Version History

| Version | Date | Key Changes |
|---|---|---|
| V1.0 | Feb 2026 | Initial 5-source scoring engine |
| V2.0 | Mar 2026 | 35 signals, 7 tiers, 0–10 scale, unique rankings |
| V2.1 | Mar 2026 | FSA reweighted, Google capped at 30%, confidence bands |
| V3.0 | Mar 2026 | 40 signals, aspect NLP, GBP completeness, TripAdvisor recency, Companies House |
| V3.1 | Mar 2026 | Coverage penalty, provenance classification, cross-tier 45% cap |
| V3.2 | Mar 2026 | Community tier removed (double-counted), SCP removed, tier 3 TripAdvisor-only |
| V3.3 | Apr 2026 | 4 commercial lenses, demand capture audit, implementation framework, barrier diagnosis |
| V3.4 | Apr 2026 | Temporal decay, cross-source convergence, 18 penalty rules, monthly delta tracking |

---

*This document describes the DayDine Restaurant Confidence Score methodology as implemented in `rcs_scoring_stratford.py` (V3.4). The scoring engine implementation, data collection scripts, and front-end rendering are maintained in the DayDine repository.*

*© 2026 DayDine*
