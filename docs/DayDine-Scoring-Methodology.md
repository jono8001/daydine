# DayDine Scoring Methodology

**Restaurant Confidence Score (RCS) — V4 (current framework)**
*Last updated: April 2026*

> **Transition notice.** V4 is the current scoring framework. V3.4 remains in
> the repository and is still computed in parallel on each run so V4's behaviour
> can be audited venue-by-venue against the legacy output. Public leaderboards
> will cut over to V4 once the calibration work documented in
> `DayDine-V4-Scoring-Comparison.md` completes. Anything on this page that is
> specific to the legacy model is labelled **V3.4 legacy**.

---

## 1. What This Document Covers

How DayDine derives the 0–10 Restaurant Confidence Score, what the score is
built from, what it is not, and which pieces of prior methodology have been
removed in V4.

The RCS is an **external public-evidence score**. It reflects what an
informed outsider can infer from public and licensed third-party data. It is
not a mystery-diner review and is not a prediction of financial performance.

---

## 2. Score Scale

| Property | Value |
|---|---|
| Range | 0.000 – 10.000 |
| Precision | 3 decimal places |
| Update frequency | Weekly |

V4 no longer publishes a six-band verbal ranking as its primary surface. The
score still produces a 0–10 number; the primary categorical output is the
**confidence class** (see §5), which decides whether the venue appears in a
league table at all.

> **V3.4 legacy.** The six verbal bands (Excellent / Good / Generally
> Satisfactory / Improvement Necessary / Major Improvement / Urgent
> Improvement) are retained in the legacy output for migration comparison
> only. They are not authoritative under V4.

---

## 3. V4 Score Structure

V4 is built from three components with **fixed weights**. When a component is
missing, it contributes zero — the weights do not redistribute. Missing data
feeds the confidence class instead of inflating the score.

| Component | Weight | Source family | Frame |
|---|---|---|---|
| Trust & Compliance | 40% | FSA / FHRS | Compliance, not food quality |
| Customer Validation | 45% | Google, TripAdvisor, OpenTable (when present) | Public rating metadata |
| Commercial Readiness | 15% | Public customer-path signals | Can a guest find and book? |

On top of the components V4 applies a capped distinction modifier, a small
set of penalties and caps, and confidence-class gating.

```
base     = 0.40 * TrustCompliance + 0.45 * CustomerValidation + 0.15 * CommercialReadiness
adjusted = base + DistinctionModifier   (hard cap +0.30)
adjusted = apply_penalties_and_caps(adjusted)
final    = gating(adjusted, confidence_class)
```

Full rules are in `docs/DayDine-V4-Scoring-Spec.md`. Implementation is in
`rcs_scoring_v4.py`.

### 3.1 Trust & Compliance (40%)

FHRS is a **trust-and-compliance signal**, not a food-quality signal. A
5-rated venue meets hygiene and management standards; it is not "better
food".

| Signal | Source | Sub-weight |
|---|---|---|
| FHRS headline rating (0–5) | FSA | 0.45 |
| Food hygiene sub-score | FSA | 0.20 |
| Structural compliance sub-score | FSA | 0.15 |
| Confidence in management sub-score | FSA | 0.15 |
| Inspection recency (decayed) | FSA | 0.05 |

Recency uses exponential decay with λ = 0.0023 (~300-day half-life). Ratings
`AwaitingInspection`, `Exempt`, or `Pass` (Scotland) make the whole component
unavailable.

### 3.2 Customer Validation (45%)

**Platform rating and count metadata only. No review-text sentiment, no
aspect scoring, no AI summaries.** Each platform is shrunk Bayesianly toward
a platform-specific prior, then combined by coverage weight.

| Platform | Prior mean | Pseudo-count | "Full evidence" n_cap |
|---|---|---|---|
| Google | 3.8 | 30 | 200 |
| TripAdvisor | 3.6 | 25 | 150 |
| OpenTable | 4.0 | 20 | 100 |

Per-platform shrinkage: `shrunk = (n*rating + k*prior) / (n+k)`. Combination
weight: `w = min(n, n_cap) / n_cap`, floored at 0.05. Very small counts still
contribute but cannot dominate.

When only one platform is present, the venue can reach Rankable-B at best
(see §5). With all platforms below five reviews each, the venue cannot exceed
Directional-C.

### 3.3 Commercial Readiness (15%)

Four equal public customer-path signals. This is a convenience component, not
a quality component.

| Signal | Weight |
|---|---|
| Website present | 0.25 |
| Menu online | 0.25 |
| Opening hours completeness (days/7) | 0.25 |
| Booking or contact path (phone / reservation / booking widget) | 0.25 |

Attributes like parking, wheelchair access, delivery, and takeaway are
surfaced on venue profiles but do not feed the score.

### 3.4 Distinction Modifier

Additive, capped at **+0.30** on the 0–10 scale.

| Award | Modifier |
|---|---|
| Michelin 3 / 2 / 1 Star | +0.30 / +0.25 / +0.20 |
| Michelin Bib Gourmand | +0.12 |
| Michelin Green Star | +0.08 |
| Michelin Guide listing (no award) | +0.05 |
| AA 5 / 4 / 3 / 2 / 1 Rosette | +0.20 / +0.15 / +0.10 / +0.06 / +0.03 |

No other awards feed the score.

### 3.5 Penalties and Caps

- **Companies House risk.** Dissolved → cap 3.0. Liquidation/administration →
  cap 5.0. Accounts overdue > 90 days → −0.30. Director churn ≥ 3 in 12 months
  → ×0.92.
- **Stale inspection.** > 2 years with FHRS ≥ 3 → Trust component soft cap 7.0.
  > 3 years → Trust × 0.85. > 5 years → Trust hard cap 5.0.
- **Closure.** FSA-closed or Google `CLOSED_PERMANENTLY` → removed from
  rankings. `CLOSED_TEMPORARILY` → scored but excluded from league tables.
- **No valid entity match.** Unranked; profile-only or dropped.

---

## 4. Source-Family Discipline

V4 treats data by source family, not by signal count:

| Family | Signals | Role |
|---|---|---|
| FSA / FHRS | rating, sub-scores, recency | Trust & Compliance |
| Customer platforms | Google, TripAdvisor, OpenTable | Customer Validation |
| Customer-path | web, menu, hours, booking | Commercial Readiness |
| Companies House | status, accounts, directors | Penalty / risk only |

Google-derived sub-signals (photos, price level, place types, delivery,
takeaway, wheelchair, parking) are **not** treated as independent evidence —
they come from one family. They are not in the score.

---

## 5. Confidence Class and Rankability

Every scored venue is assigned exactly one class. The class decides whether
the venue enters league tables — it is not a "margin-of-error" badge.

| Class | Primary families required | Signals | Review count | League table? |
|---|---|---|---|---|
| **Rankable-A** | All 3 | ≥ 10 | ≥ 50 combined or ≥ 30 on one platform | Yes — primary |
| **Rankable-B** | ≥ 2 | ≥ 7 | ≥ 10 combined | Yes — secondary |
| **Directional-C** | ≥ 1 | ≥ 4 | any | No — "Directional" list |
| **Profile-only-D** | fails the above | — | — | No — profile page only, no score shown |

Ambiguous entity matches cap the class at Directional-C. Single-platform
customer validation caps at Rankable-B. Stale-inspection hard caps, closures,
and dissolved-entity flags all prevent league-table eligibility even if the
class is Rankable.

---

## 6. What V4 Does Not Use

The following were in V3.4 and are **removed from V4 headline scoring**. Some
still appear on profile pages; none affect the score.

| Removed input | V3.4 role | V4 status |
|---|---|---|
| Review-text sentiment | Google tier + red flags | Report-only |
| Aspect sentiment (food / service / ambience / value / cleanliness) | Google tier sub-signals | Report-only |
| Google AI summaries | Ingested as sentiment | Excluded entirely |
| Photo count | Google tier signal | Profile attribute |
| Price level | Google tier signal | Profile attribute |
| Place types (`gty`) | Google tier + operational inference | Used only for non-food exclusion and cuisine labelling |
| Delivery / takeaway / parking / wheelchair | Operational tier positives | Profile attributes |
| Social presence (Facebook, Instagram) | Online presence tier | Profile attributes |
| Cross-source convergence bonus (±3–5%) | Post-hoc adjustment | Removed |
| Community tier | Removed in V3.4 already | Still removed |

---

## 7. Handling Sparse Review Text and Small Samples

- Low review counts trigger Bayesian shrinkage toward the platform prior.
  They do **not** trigger text analysis to "recover more signal".
- Review text is report-only in V4. It may inform narrative language on a
  venue profile but never the score or the rank.
- Google's 5-review text API is not used in headline scoring.
- When text evidence is thin or contradictory, the confidence class or the
  narrative is softened — the score stays put.

---

## 8. What the Score Is Not

- Not a review of the food or any specific meal.
- Not based on mystery dining, self-reporting, or paid inclusion.
- Not a prediction of future performance or financial viability.
- Not influenced by advertising, sponsorship, or operator payment.
- Not a replacement for operating dashboards, management accounts, or
  compliance audits.

---

## 9. V4 Outputs

Every scored venue emits: per-component scores, distinction modifier value,
penalties and caps applied, base and adjusted scores, final score, confidence
class, rankability flag, league-table eligibility, source-family summary,
entity-match status, and a decision trace. Exact schema in
`DayDine-V4-Scoring-Spec.md` §10.

---

## 10. Migration and Deprecation

### Deprecated from V3.4

- 40-signal / 7-tier structure
- Six verbal rating bands as the primary surface
- Aspect sentiment and red-flag scoring
- Google AI summary ingestion
- Cross-source convergence bonus / penalty
- Tier re-weighting when signals are missing (replaced by fixed weights +
  confidence-class gating)
- The 18-rule V3.4 penalty table (replaced by the V4 penalties in §3.5)

### Retained for legacy comparison only

- `rcs_scoring_stratford.py` — still runs during migration
- `stratford_rcs_scores.csv`, `stratford_rcs_summary.json`, and
  `stratford_rcs_report.md` — legacy outputs produced alongside V4
- Sentiment, aspect, photo, types, and attribute fields on profiles — shown
  to users but not scored

### Work remaining before full cutover

1. Collect TripAdvisor data across the trial set so Rankable-A is reachable.
2. Calibrate Customer Validation spread (top-half compression currently
   concentrates 50.8% of rankable venues above 8.0).
3. Collect phone / booking URL data so Commercial Readiness is not capped at
   0.75 for every venue.
4. Build an entity-match resolver to handle trading-name vs legal-entity
   mismatches (Dirty Duck, Church Street Townhouse, etc.).
5. Regenerate the comparison artifacts after each calibration change.

### Report layer

Report and leaderboard restructuring happens after cutover, not before. The
report currently rendered from V3.4 output (`stratford_rcs_report.md`,
profile pages, rankings pages) will need to:

- Show confidence class instead of confidence band.
- Exclude Directional-C from the default league view and surface it as a
  separate "Directional" list.
- Render sentiment and aspect data as report-only context, clearly separated
  from the score.
- Replace the six verbal bands with the confidence classes and a small
  number of score tiers within Rankable-A/B.

---

## 11. Data Sources

| Source | What it provides | Cost |
|---|---|---|
| Food Standards Agency | Hygiene rating, sub-scores, inspection dates | Free (public API) |
| Google Places | Rating, review count, place metadata (score-relevant: rating + count only) | Per-request billing |
| TripAdvisor (Apify) | Rating, review count | Per-run |
| OpenTable | Rating, review count | Schema reserved; not yet collected |
| Companies House | Company status, accounts, director changes | Free (public API) |
| Michelin Guide | Stars, Bib Gourmand, Green Star, listings | Web scrape |
| AA Restaurant Guide | Rosette rating | Web scrape |

All data is publicly accessible. No signal is self-reported by venue
operators.

---

## 12. Current Coverage

**Live trial market:** Stratford-upon-Avon — 210 establishments scored under
both V3.4 and V4. Under V4: 1 Rankable-A, 190 Rankable-B, 18 Directional-C,
1 Profile-only-D. Mean score 7.85 across rankable venues.

New markets are added as data pipelines (FSA, Google, TripAdvisor, Companies
House) are validated per local authority.

---

## 13. Version History

| Version | Date | Key changes |
|---|---|---|
| V1.0 | Feb 2026 | Initial 5-source engine |
| V2.0 | Mar 2026 | 35 signals, 7 tiers, 0–10 scale |
| V2.1 | Mar 2026 | Google capped at 30%, confidence bands |
| V3.0 | Mar 2026 | 40 signals, aspect NLP, Companies House |
| V3.1 | Mar 2026 | Coverage penalty, provenance classification |
| V3.2 | Mar 2026 | Community tier removed, SCP removed |
| V3.3 | Apr 2026 | Commercial lenses introduced |
| V3.4 | Apr 2026 | Temporal decay, convergence bonus, 18 penalty rules |
| **V4** | **Apr 2026** | **3-component structure (40/45/15), Bayesian shrinkage on platform ratings, four-class confidence/rankability gating, sentiment and aspect scoring removed, convergence bonus removed, fixed weights (no renormalisation on missing data)** |

---

*V4 methodology is implemented in `rcs_scoring_v4.py` and specified in
`docs/DayDine-V4-Scoring-Spec.md`. V3.4 (`rcs_scoring_stratford.py`) runs in
parallel during migration. Comparison diagnostics are in
`docs/DayDine-V4-Scoring-Comparison.md`.*

*© 2026 DayDine*
