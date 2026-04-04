# UK Restaurant Tracker — Methodology Specification V3.3

*DayDine RCS (Restaurant Confidence Score)*
*Last updated: 3 April 2026*

---

## 1. What This Product Is

DayDine produces **external blind-spot reports** for premium independent restaurants and small multi-site operators. Every signal is publicly observable — no POS integration, no internal data feeds, no operator-side instrumentation.

The report answers: *what can a well-informed outsider see about your business that you may be missing?*

### What the report is not

- Not a full internal operating dashboard. It cannot see covers, labour cost, or GP%.
- Not a replacement for mystery dining, internal audits, or management accounts.
- Not a compliance tool — it surfaces public compliance signals, not inspection detail.

### Design Principles

1. **Multi-source.** No single data source dominates. Google reviews are capped at 30% effective weight.
2. **Verifiable.** Every signal traces to a public data source (FSA, Google Places, TripAdvisor, Companies House).
3. **Penalise risk.** Critical food safety or business viability issues trigger hard score caps.
4. **Confidence from coverage.** Establishments with more signals and more independent sources get higher confidence ratings.
5. **Diagnosis over score.** The RCS score exists to power structured diagnosis. The report leads with actions and commercial lenses, not the number.

---

## 2. Commercial Lenses

The report is organised around four commercial lenses. Each lens maps to underlying scoring dimensions and signals, but the report itself is framed in operator language, not data-science labels.

| Commercial Lens | What It Answers | Primary Dimensions | Key Signals |
|---|---|---|---|
| **Demand Capture** | Are you converting interest into visits? | Visibility, Conversion | 7-dimension audit: Booking Friction, Menu Visibility, CTA Clarity, Photo Mix & Quality, Proposition Clarity, Mobile Usability, Promise vs Path Consistency |
| **Proposition & Guest Signal** | What are guests actually buying — and is it what you think you sell? | Experience | Google rating, TripAdvisor rating, aspect sentiment, review themes, FSA food hygiene sub-score |
| **Trust & Public Risk** | What does the public compliance record say about risk? | Trust | FSA hygiene rating, structural compliance, management confidence, inspection recency |
| **Competitive Market Intelligence** | How do you sit relative to your local and category peers? | All (peer-relative) | Peer percentile, dimension gaps, competitor scores, market density |

**Prestige** (editorial recognition: Michelin, AA, local awards) is tracked as a signal within Reputation & Awards but is **not** a headline lens. Most premium independents have zero editorial recognition; prestige is a long-cycle outcome, not an operational lever.

---

## 3. Score Scale

| Property | Value |
|---|---|
| Range | 0.000 – 10.000 |
| Precision | 3 decimal places |
| Uniqueness | Guaranteed — tiebreaker system ensures no two restaurants share a rank |

### Rating Bands

| Band | RCS Range | Description |
|---|---|---|
| Excellent | 8.000 – 10.000 | Outstanding across multiple dimensions; strong data convergence |
| Good | 6.500 – 7.999 | Consistently positive; minor gaps in one area |
| Generally Satisfactory | 5.000 – 6.499 | Adequate; notable gaps or mixed signals |
| Improvement Necessary | 3.500 – 4.999 | Significant concerns; multiple penalties triggered |
| Major Improvement | 2.000 – 3.499 | Critical issues; enforcement actions or consistently poor ratings |
| Urgent Improvement | 0.000 – 1.999 | Severe safety or viability concerns |

The score supports diagnosis but does not headline the report. Reports lead with the top commercial leaks and recommended actions; the score provides the structural backbone.

---

## 3a. Review Intelligence — Temporal Honesty

The monthly report is generated on a calendar cadence, but the review data it analyses is **not** filtered to the last 30 days by default. The report must never imply otherwise.

### Two-layer model

Review intelligence is conceptually split into two layers:

| Layer | What it covers | Date requirement | Fallback if dates unavailable |
|---|---|---|---|
| **Reputation Baseline** | What the venue is generally known for across the full available review sample | None — uses all collected reviews regardless of age | Always available when review text exists |
| **Recent Movement** | What changed in the last 30 days (or a stated recent window) | Requires reliable date stamps on individual reviews | Degrade honestly: state that recent movement could not be isolated |

### Source date availability

| Source | Date field | Reliability | Usable for monthly filtering? |
|---|---|---|---|
| TripAdvisor (Apify) | `publishedDate` (ISO datetime) | High — set by TripAdvisor | Yes |
| Google Places API | `time` (relative string, e.g. "6 months ago") | Low — relative to scrape time, month-level precision at best | No — approximate only |

### Rules for report wording

1. **The Reputation Baseline layer must always state the sample scope.** Example: "Based on 25 reviews collected across [date range or 'the available sample']." Never imply these are this month's reviews.
2. **The Recent Movement layer must only appear when date-filtered reviews exist.** If no reviews have reliable dates within the reporting window, the report must state: *"Recent review movement could not be isolated from current source data."*
3. **Trajectory claims ("improving", "declining") must be date-grounded.** Splitting reviews by list position is not temporal evidence. If reviews are not date-sorted, trajectory claims must be labelled as positional, not temporal.
4. **Google review dates are unreliable** and must not be used for precise monthly filtering. They may be used for approximate windowing (±1 month) with an explicit caveat.

---

## 3b. Temporal Layer — Month-over-Month Tracking

Each monthly report stores a complete snapshot of all scoreable dimensions, raw signals, competitive position, demand capture verdicts, and review sentiment. When a prior month's snapshot exists, the report computes deltas and presents a Monthly Movement Summary.

### Snapshot Schema

The monthly JSON stores: dimension scores (5 + overall), raw signals (Google rating/count/photos, TA rating/count, FSA rating/inspection date, price level, GBP completeness), competitive position (local rank/count, catchment rank), demand capture audit verdicts (7 dimensions), review sentiment by topic, and implementation framework state.

### Delta Computation

| Field Type | Delta Method | Significance Thresholds |
|---|---|---|
| Dimension scores | `current - prior` | < 0.2 = negligible, 0.2–0.5 = notable, > 0.5 = significant |
| Google review count | `current - prior` | Absolute count of new reviews |
| Peer position | `prior_rank - current_rank` | Positive = improved |
| Demand capture | Per-dimension verdict comparison | Improved / Unchanged / Worsened |

### Monthly Movement Summary

Appears after the Executive Summary. For baseline months (no prior data): states "first report — all metrics baselined." For subsequent months: What Changed, What Is Stable, What Is Worsening — each with specific numbers.

### Scorecard Delta Reads

When deltas are available, the Dimension Scorecard "Read" column uses directional interpretation:

| Delta | Peer Position | Read |
|---|---|---|
| Up | Above peers | Strengthening lead |
| Up | Below peers | Closing gap |
| Down | Above peers | Lead narrowing |
| Down | Below peers | Falling further behind |
| Stable | Above peers | Stable strength |
| Stable | Below peers | Persistent gap |

### Per-Section Temporal Context

Major sections carry inline temporal context when prior data exists:

| Section | Temporal Context Added |
|---|---|
| Demand Capture Audit | "X dimensions improved, Y unchanged, Z worsened" after summary count |
| Trust Dimension | Inspection date, age in months, re-inspection likelihood note |
| Competitive Market Intelligence | Position movement vs prior month ("Improved from #5 to #4") |
| Implementation Framework | Barrier diagnosis escalation based on recommendation age |
| Review Intelligence | Sample scope + dated recent movement layer (from §3a) |

### Seasonal Pattern Recognition

V1 covers Stratford-upon-Avon with hardcoded seasonality:
- RSC theatre season: Mar–Oct (pre-theatre dining demand elevated)
- Peak tourism: Jun–Sep (review volume ~50% above annual average)
- Quiet period: Nov–Feb (review volume ~40% below average)

The Monthly Movement Summary includes a "What May Be Seasonal Rather Than Structural" subsection that flags when metric changes align with known seasonal patterns.

Metric changes are classified as:
- **Structural** — consistent across 3+ months
- **Seasonal** — matches known seasonal pattern for this location/month
- **Anomaly** — single-month deviation, too early to act on
- **Insufficient data** — fewer than 3 months of history

---

## 3b2. Demand Capture Audit

The Demand Capture lens produces a structured outside-in audit of the venue's public digital presence. Rather than reporting a composite conversion score, it walks through 7 named dimensions of the customer journey from discovery to commitment — using only publicly observable data.

### Audit Dimensions

| # | Dimension | What It Assesses | Key Signals | Verdicts |
|---|---|---|---|---|
| 1 | **Booking Friction** | Can a customer book within 2 clicks from Google Maps? | `restaurant` type (reservation proxy), GBP attributes, TA presence, review text mentioning booking | Clear / Partial / Missing / Broken |
| 2 | **Menu Visibility** | Can a customer see the current menu before deciding? | `has_menu_online`, GBP completeness, review text mentioning menu | Clear / Partial / Missing |
| 3 | **CTA Clarity** | Does the GBP profile present a clear action path? | GBP completeness breakdown (10 attributes), website, phone inferred | Clear / Partial / Missing |
| 4 | **Photo Mix & Quality** | Do the photos sell the experience guests praise? | `gpc` (photo count), peer average comparison, cross-ref vs top review sentiment topics | Clear / Partial / Missing |
| 5 | **Proposition Clarity** | Does the public identity match what guests buy? | Google types vs dominant review themes, category vs praise topics | Clear / Partial / Gap |
| 6 | **Mobile Usability** | Can a mobile user confirm hours, see menu, and book without leaving Maps? | Opening hours completeness (7/7), phone presence, website presence | Clear / Partial / Missing |
| 7 | **Promise vs Path** | Is there a gap between what the listing promises and what the path delivers? | Cross-reference GBP attributes vs review evidence and hours data | Clear / Partial / Broken |

### Verdict Definitions

| Verdict | Meaning |
|---|---|
| **Clear** | No friction detected — signal is present, complete, and consistent |
| **Partial** | Signal is present but incomplete, buried, or not surfaced in the primary discovery path |
| **Missing** | Signal is not available in any public channel |
| **Broken** | Contradictory signals — listing promises something the path doesn't deliver |
| **Gap** | Public identity does not match guest evidence (proposition-specific) |

### Summary Format

The section opens with: *"X of 7 demand capture dimensions are clear. Y have friction. Z are missing."*

Each dimension cites the specific signals evaluated (not just the composite score). Where review text corroborates or contradicts structured signals, it is cross-referenced.

Where a dimension cannot be fully assessed from current data, the report states what is missing and what additional signal would resolve it.

---

## 3c. Implementation Framework

Each active recommendation is presented as a structured action card, not a flat table row. The framework turns intelligence into management instruments with clear deadlines, costs, success measures, and barrier diagnosis.

### Action Card Fields

| Field | What It Shows | How It's Derived |
|---|---|---|
| **Target Date** | Specific calendar date by when this should be done | Report date + cost-band window: Zero/Low = +7 days, Medium = +30 days, High = +90 days |
| **Success Measure** | Externally observable signal DayDine can verify next month | Mapped from dimension + fix type to specific API-verifiable fields |
| **Next Milestone** | Single concrete action completable in one sitting | Specific step (not "update GBP" but "log in → Info → Menu URL → paste link") |
| **Owner** | Role + guidance on who specifically should act | Role (operations/management) + context ("whoever holds GBP admin access") |
| **Cost Band** | Implementation cost | Zero / Low (< £200) / Medium (£200–£1,000) / High (£1,000+) |
| **Expected £ Upside** | Value at stake range with basis | From commercial consequence estimates, carried forward with logic breakdown |
| **Barrier Diagnosis** | Why this hasn't been done yet (for recs aged 3+ months) | Algorithmic: age × cost band × dimension → barrier category |

### Barrier Categories

| Category | When It Applies | Typical Pattern |
|---|---|---|
| **Access barrier** | Low-cost digital fix outstanding 3+ months | GBP admin access lost, no one has the login |
| **Awareness barrier** | Report not reaching the person who can act | Owner ≠ the person managing the specific system |
| **Prioritisation barrier** | Low-cost fix outstanding 6+ months | Never assigned to a specific person with a deadline |
| **Capability barrier** | Experience/quality fix outstanding 3+ months | Requires process changes or training that don't exist yet |
| **Disagreement barrier** | Any fix outstanding 12+ months | Operator may believe the recommendation doesn't apply |

### Escalation Rules

- Month 1–2: Set target date and next milestone. No barrier diagnosis.
- Month 3–5: Add barrier diagnosis. Identify most likely blocker.
- Month 6–11: Escalate barrier language. Note cost of inaction at this duration.
- Month 12+: Flag as chronic. Suggest the operator explicitly accept or reject the recommendation.

### Progress Detection

The report tracks whether the underlying signal has changed since the recommendation was first raised. Partial progress is noted (e.g. "hours now 5/7 days, previously 0/7").

---

## 4. Signal Architecture

### 4.1 Provenance Classification

Every signal is tagged with one of four provenance levels:

| Provenance | Definition | Example |
|---|---|---|
| **observed** | Directly collected from an authoritative API or public source | FSA hygiene rating, Google star rating, TripAdvisor review count |
| **derived** | Computed from observed signals using a defined formula | GBP completeness score (10-attribute check), aspect sentiment scores (NLP on review text) |
| **inferred** | Estimated from indirect evidence; lower confidence | Website/Facebook/Instagram presence inferred from Google review volume and business type |
| **not_assessed** | Signal defined in the methodology but not yet collected for this establishment | Companies House status (when API key unavailable) |

Provenance affects **confidence grading** (see §6) but does not discount the score itself. Inferred signals carry full weight in scoring; the confidence band communicates how much trust to place in the overall result.

### 4.2 Tier Structure (6 Active Tiers + 1 Penalty-Only)

| Tier | Weight | Source | Provenance | Signals |
|---|---|---|---|---|
| 1. FSA | 23% | FSA Ratings API / Firebase | observed | 5 |
| 2. Google | 24% | Google Places API (New) | observed + derived | 11 |
| 3. Online Presence (TripAdvisor) | 13% | Apify TripAdvisor Scraper | observed (when collected) / not_assessed (when pending) | 4–7 |
| 4. Operational | 15% | Google Places API (types + hours) | observed + inferred | 6 |
| 5. Menu & Offering | 10% | Google Places / website scrape | observed + inferred | 4 |
| 6. Reputation & Awards | 8% | Michelin Guide, AA, local press | observed | 3 |
| 7. Companies House | penalty-only | Companies House API | observed (when available) / not_assessed | 5 |

**Removed tiers:** Community & Engagement (former Tier 7) was removed in V3.2. It was entirely computed from proxy signals already present in Tiers 1–3 and had no directly observed data. Its weight was redistributed to FSA (+2%) and Reputation (+3%).

---

### 4.3 Tier Detail

#### Tier 1: Food Safety Authority (FSA) — 23%

| Signal | Normalisation | Weight within tier | Provenance |
|---|---|---|---|
| Hygiene rating (0–5) | `rating / 5` → 0–1 | 40% | observed |
| Structural compliance (0–25, inverted) | `(25 - raw) / 25` → 0–1 | 20% | observed |
| Confidence in management (0–20, inverted) | `(20 - raw) / 20` → 0–1 | 20% | observed |
| Food hygiene sub-score (0–25, inverted) | `(25 - raw) / 25` → 0–1 | 20% | observed |
| Inspection recency | Days since last inspection → penalty modifier | — | observed |

Inspection recency penalties: >365 days: −5% of tier score. >730 days: −10%.

#### Tier 2: Google Signals — 24% (capped at 30% effective)

| Signal | Normalisation | Weight within tier | Provenance |
|---|---|---|---|
| Star rating (1–5) | `rating / 5` → 0–1 | 20% | observed |
| Food Quality aspect score | Keyword NLP, 0–1 | 5% | derived |
| Service Quality aspect score | Keyword NLP, 0–1 | 5% | derived |
| Ambience aspect score | Keyword NLP, 0–1 | 5% | derived |
| Value Perception aspect score | Keyword NLP, 0–1 | 5% | derived |
| Wait Time aspect score | Keyword NLP, 0–1 | 5% | derived |
| Overall review sentiment | Keyword analysis, 0–1 | 10% | derived |
| Review count | `log10(count) / log10(1000)`, cap 1.0 | 20% | observed |
| Price level (1–4) | `level / 4` → 0–1 | 5% | observed |
| Photos count | `min(count, 10) / 10` → 0–1 | 5% | observed |
| Place types | Binary presence = 1.0 | 5% | observed |

**Google weight cap:** When re-normalisation (due to missing tiers) would push Google's effective weight above 30%, the excess is redistributed proportionally to other active tiers.

**Cross-tier dependency cap:** Tiers 2, 3, 4, and 5 all derive some signals from Google data. Combined Google-derived influence is capped at 45% effective weight with an explicit audit trail.

**Red flag system:** 32 critical phrases trigger red flags in review text. 2+ red flags generate a WARNING.

#### Tier 3: Online Presence — 13% (TripAdvisor-primary)

| Signal | Normalisation | Weight within tier | Provenance |
|---|---|---|---|
| TripAdvisor presence | Boolean | 15% | observed (when collected) |
| TripAdvisor rating (1–5) | `rating / 5` → 0–1 | 30% | observed (when collected) |
| TripAdvisor review count | `log10(count) / log10(1000)`, cap 1.0 | 25% | observed (when collected) |
| TripAdvisor review recency | Fraction of reviews < 6 months old | 15% | observed (when collected) |
| Has website | Boolean (inferred from Google data) | — | inferred (confidence layer only) |
| Has Facebook | Boolean (inferred) | — | inferred (confidence layer only) |
| Has Instagram | Boolean (inferred) | — | inferred (confidence layer only) |

Website/Facebook/Instagram presence contributes to the **confidence grade** but not the headline RCS score. These are inferred signals with no direct validation.

#### Tier 4: Operational Signals — 15%

| Signal | Normalisation | Weight within tier | Provenance |
|---|---|---|---|
| Accepts reservations | Boolean | 16.7% | inferred |
| Offers delivery | Boolean | 16.7% | observed (from Google type) or inferred |
| Offers takeaway | Boolean | 16.7% | observed (from Google type) or inferred |
| Wheelchair accessible | Boolean | 16.7% | observed (when available) |
| Has parking | Boolean | 16.7% | inferred |
| Opening hours completeness | `len(hours) / 7` → 0–1 | 16.7% | observed |

#### Tier 5: Menu & Offering — 10%

| Signal | Normalisation | Weight within tier | Provenance |
|---|---|---|---|
| Has menu online | Boolean | 30% | observed (when scraped) or inferred |
| Dietary options count | `min(count, 5) / 5` → 0–1 | 20% | observed (when scraped) |
| Cuisine tags count | `min(count, 3) / 3` → 0–1 | 20% | derived (from Google types) |
| GBP completeness score | 10-attribute check / 10 → 0–1 | 30% | derived |

#### Tier 6: Reputation & Awards — 8%

| Signal | Normalisation | Weight within tier | Provenance |
|---|---|---|---|
| Michelin mention (star/bib/plate) | Boolean | 40% | observed |
| AA Rosette rating | Boolean | 35% | observed |
| Local awards count | `min(count, 3) / 3` → 0–1 | 25% | observed |

#### Tier 7: Companies House — Penalty-Only

Companies House signals operate as **penalty multipliers** on the final score, not as a weighted tier component.

| Signal | Penalty | Provenance |
|---|---|---|
| Company dissolved | Cap at 3.0 | observed (when available) |
| Company in liquidation | Cap at 5.0 | observed (when available) |
| Accounts overdue | −0.5 absolute | observed (when available) |
| 3+ director changes in 12 months | −12% | observed (when available) |

**Launch status:** Companies House data requires a `COMPANIES_HOUSE_API_KEY`. When the key is unavailable, all Companies House signals are `not_assessed` and no penalties are applied. The report's Data Coverage section will state this explicitly. This does not affect the RCS score but does affect the confidence grade.

---

## 5. Scoring Pipeline

### Stage 1: Signal Collection

```
Firebase RTDB → FSA data
FSA API (LA-specific) → Augment with pubs/bars/takeaways
Google Places API → Rating, reviews, photos, types, review text
Apify API → TripAdvisor rating, reviews, cuisine, ranking
Web inference → Website, Facebook, Instagram presence
GBP check → Profile completeness score
Menu scrape → Cuisine tags, dietary options
Editorial check → Michelin, AA, local awards
FSA enforcement → Enforcement actions
Companies House → Business status, accounts, directors (when key available)
```

### Stage 2: Normalisation

All signals normalised to 0–1 within their tier. Missing signals are skipped; the tier is re-weighted across available signals only.

### Stage 3: Weighted Aggregation

```
For each tier with data:
    tier_score = Σ(signal_weight × signal_value) / Σ(signal_weight)

effective_weights = normalise(TIER_WEIGHTS for active tiers)
if effective_weights["google"] > 0.30:
    redistribute excess to other tiers
if combined_google_derived > 0.45:
    redistribute excess to non-Google tiers

rcs_raw = Σ(effective_weight[tier] × tier_score[tier]) × 10
```

### Stage 4: Penalty Application

Applied in order:

| Condition | Effect |
|---|---|
| FSA rating 0–1 | Cap at 2.0 |
| FSA rating 2 | Cap at 4.0 |
| FSA rating 3 + stale inspection (>2yr) | Cap at 7.0 |
| No inspection in 3+ years | −15% |
| Google rating < 2.0 | −10% |
| Google rating 2.0–2.9 | −5% |
| Zero Google reviews | −5% |
| Very few reviews (<5 combined) | −3% |
| No photos | −3% |
| No online presence | −10% |
| TripAdvisor rating < 2.5 | −5% |
| No opening hours (with Google data) | −3% |
| 3+ red flags | −15% |
| Google and TA diverge by >2 stars | −5% |
| Company dissolved | Cap at 3.0 |
| Company in liquidation | Cap at 5.0 |
| Accounts overdue | −0.5 absolute |
| 3+ director changes in 12 months | −12% |

`rcs_final = clamp(penalised_score, 0, 10)`

### Stage 5: Tiebreaker & Ranking

1. Sort by `rcs_final` descending
2. Break ties using (in order): signal count → FSA hygiene rating → inspection recency → structural compliance → management confidence → alphabetical
3. Assign sequential ranks 1..N

Scores are raw (ties allowed in `rcs_final`). Rank breaks ties; scores are not walk-down adjusted.

### Stage 6: Temporal Decay

Exponential decay `e^(−λt)` applied to time-sensitive signals:

- **FSA inspection age:** λ = 0.0023 (~300-day half-life). Blended: 80% raw + 20% decay-adjusted.
- **Google review recency:** λ = 0.0046 (~150-day half-life) applied to review volume signal when latest review date is available.

### Stage 7: Cross-Source Convergence

Compares normalised ratings from independent sources (FSA, Google, TripAdvisor) pairwise:

| Condition | Adjustment |
|---|---|
| Converged (avg divergence ≤ 0.10) | +3% bonus |
| Neutral (0.10–0.20) | No change |
| Mild divergence (0.20–0.30) | −3% |
| Strong divergence (> 0.30) | −5% |

Requires ≥ 2 sources. Single-source establishments get no adjustment.

---

## 6. Confidence & Coverage

### Report Confidence

Confidence grades reflect how much data underlies the assessment. They govern the margin of uncertainty communicated to the operator.

| Level | Criteria | Margin | Meaning |
|---|---|---|---|
| High | 20+ signals available, 5+ tiers active, 2+ independent observed sources | ±0.3 | Score is well-supported; diagnosis is reliable |
| Medium | 14+ signals, 4+ tiers active | ±0.5 | Core dimensions covered; some lenses limited |
| Low | 8+ signals | ±0.8 | Directional only; material gaps remain |
| Insufficient | < 8 signals | Not ranked | Cannot produce a meaningful score |

**Source independence matters.** FSA + Google + TripAdvisor are independent. Google + Google-inferred operational signals are not independent — they count as one source for confidence purposes.

### Coverage Penalty

| Condition | Effect |
|---|---|
| Missing both FSA and Google | ×0.85 |
| Missing FSA only | ×0.92 |
| Missing Google only | ×0.95 |

No upward bonus for high coverage. Confidence grade communicates completeness; the score is not inflated for data richness.

---

## 7. Non-Food Exclusion Filter

Establishments verified as non-food businesses are excluded from rankings.

**Priority order:**
1. Name blacklist (Slimming World, football clubs, etc.) → exclude
2. Google food types present → include (overrides all below)
3. FSA rating 3+ → include (overrides Google misclassification)
4. Food keywords in name → include
5. Google non-food types (gym, insurance, etc.) → exclude
6. Sports clubs with no food evidence → exclude

Excluded establishments are marked "Not Ranked" in output.

---

## 8. Category Classification (Multi-Signal Resolution)

Category is resolved by triangulating across multiple public signals, not relying solely on Google Place Types. The resolution engine produces a primary category with confidence level, evidence summary, and alternatives considered.

### Signal Sources (in order of weight)

| # | Signal | What It Provides | Weight |
|---|---|---|---|
| 1 | Google Place Types | What Google calls this venue | Primary |
| 2 | Review Language Analysis | What guests call it (scan for "restaurant", "pub", "café", etc.) | Strong (5+ matches) |
| 3 | Service Model Indicators | Table service, reservations, set menu, named staff (from reviews) | Supportive |
| 4 | TripAdvisor Cuisine/Type | How TA categorises the food and venue | Corroborating |
| 5 | Price Level | Positioning signal (budget → fine dining) | Supportive |
| 6 | Venue Name | Name contains category terms ("Wine Bar", "Bistro") | Supportive |

### Confidence Levels

| Level | When Applied |
|---|---|
| **High** | 3+ signals agree on the same category |
| **Medium** | Primary signal (Google) partially conflicts with review language or service model |
| **Low** | Signals conflict significantly or insufficient data for resolution |

### Peer Set Transparency

The report includes a Category & Peer Validation section that explains:
- Why this venue is in this cohort (resolved category + evidence)
- Peer justification (for each peer: distance, type, price band, validity)
- Sensitivity analysis (what changes if categorisation changes — peer set delta and position shift)

### Sensitivity Analysis

Runs the peer comparison under the primary and alternative categories. If competitive position barely changes, conclusions are robust. If it swings materially, the report flags that competitive analysis is category-dependent.

---

## 9. Data Sources

| Source | Method | Cost | Provenance |
|---|---|---|---|
| Firebase RTDB | REST API (public read) | Free | observed |
| FSA API | REST API (public) | Free | observed |
| Google Places API (New) | Text Search | Per-request billing | observed |
| Apify TripAdvisor | Actor API | ~$0.003/review | observed |
| Companies House API | REST API | Free (when key available) | observed / not_assessed |
| Michelin Guide | Web search | Free | observed |

---

## 10. Environment Variables

| Variable | Purpose | Launch Status |
|---|---|---|
| `GOOGLE_PLACES_API_KEY` | Google Places API enrichment | Required |
| `APIFY_TOKEN` | TripAdvisor data via Apify scraper | Required for Tier 3 |
| `COMPANIES_HOUSE_API_KEY` | Companies House business viability | Optional — gracefully degraded when absent |

---

## 11. Version History

| Version | Date | Changes |
|---|---|---|
| V1.0 | Feb 2026 | Initial 5-source scoring engine |
| V2.0 | Mar 2026 | 35 signals, 7 tiers, 0–10 scale, unique rankings |
| V2.1 | Mar 2026 | FSA 30%→20%, Google capped 30%, confidence bands |
| V3.0 | Mar 2026 | 40 signals, 8 tiers, aspect NLP, GBP, TA recency, Companies House |
| V3.1 | Mar 2026 | Coverage bonus/penalty, provenance weighting, cross-tier 45% cap, band calibration |
| V3.2 | Mar 2026 | Corrective: removed Community tier, SCP, inferred discount, band calibration, upward bonus. Tier 3 TripAdvisor-only. Tier 6 reweighted. Raw scores (ties allowed). |
| V3.3 | Apr 2026 | Repositioned as zero-integration external blind-spot product. 4 commercial lenses (Demand Capture, Proposition & Guest Signal, Trust & Public Risk, Competitive Market Intelligence). Prestige demoted from headline dimension. Provenance classification added (observed/derived/inferred/not_assessed). Confidence logic tightened to require source independence. Companies House described as gracefully degraded when unavailable. Removed legacy corrective notes and contradictory statements. |

---

*This specification is maintained at `UK-Restaurant-Tracker-Methodology-Spec-V3.md`.*
*The scoring engine implementation is in `rcs_scoring_stratford.py`.*
