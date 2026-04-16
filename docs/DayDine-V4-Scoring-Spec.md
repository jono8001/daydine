# DayDine V4 Scoring Specification

**Status:** Draft — implementation target
**Supersedes:** V3.4 (`rcs_scoring_stratford.py`)
**Scale:** 0.000–10.000 (3 decimal places)
**Audience:** Engineers implementing the V4 scoring engine

---

## 1. Core Principles

These principles are normative. Any rule in this spec that appears to violate a principle must be rejected.

1. **External / public data only.** The engine consumes only public or licensed third-party data (FSA/FHRS, Google Places metadata, TripAdvisor metadata, Companies House, Michelin, AA). No private user data, no scraped personal content, no proprietary partner feeds.
2. **Conservative under uncertainty.** When evidence is thin, scores move toward the prior, not toward the extremes. Absence of data is never rewarded.
3. **Missing data must not inflate scores.** A missing signal contributes zero to its component and reduces the component's achievable weight; it does not receive a neutral midpoint fill.
4. **Source families must be treated correctly.** FHRS is a trust/compliance signal, not a food-quality signal. Platform ratings are customer validation, not compliance. Structural data (hours, website) is commercial readiness, not quality.
5. **Weak evidence reduces confidence, not precision.** Low review counts or thin source coverage change the confidence class and the report wording. They do not produce a high-precision headline number.
6. **Ranking logic is separate from report narrative logic.** The headline score drives rank ordering and league tables. Review text, aspect sentiment, and AI summaries feed only report narrative, never the headline.

---

## 2. Headline Score Structure

The final V4 score `rcs_v4_final` is a 0.000–10.000 number produced by:

```
base = 0.40 * TrustCompliance
     + 0.45 * CustomerValidation
     + 0.15 * CommercialReadiness
     (each component on 0–10)

adjusted = base + DistinctionModifier        # capped, additive, small
adjusted = apply_penalties_and_caps(adjusted)
final    = gating(adjusted, confidence_class)
```

### 2.1 Component Weights

| Component | Weight | Source Family |
|---|---|---|
| Trust & Compliance | 40% | FSA / FHRS |
| Customer Validation | 45% | Google, TripAdvisor, OpenTable (when present) |
| Commercial Readiness | 15% | Public customer-path signals |

Weights are fixed. They do not rescale when a component is missing — a missing component contributes 0 and the effective achievable max decreases, feeding directly into `confidence_class`.

### 2.2 Distinction Modifier

- Additive to `base`.
- Strict cap: **+0.30** absolute on the 0–10 scale, regardless of how many distinctions apply.
- Sources: Michelin (star / Bib Gourmand / Green Star / Guide listing), AA Rosette. No other award sources count.
- See §7.1 for the exact table.

### 2.3 Penalties and Caps

Applied after the modifier. Caps are hard; multiplicative penalties compose by multiplication; absolute penalties subtract. See §7.

### 2.4 Confidence / Rankability Gating

- Scores for venues whose confidence class is `Profile-only-D` are not published as headline rankings; they appear only as profile pages.
- `Directional-C` venues receive a headline score but are flagged and excluded from league-table ranks by default (surfaced in a separate "Directional" list).
- `Rankable-A` and `Rankable-B` enter league tables. See §8.

---

## 3. Trust & Compliance (40%)

**Frame:** FHRS/FSA is a **trust and compliance signal**, not a food-quality signal. A 5-rated venue is not "better food"; it is "meets hygiene and management standards." The report UI must render this component with that framing.

### 3.1 Allowed Signals (exhaustive)

| Signal | Field | Source | Weight within component |
|---|---|---|---|
| FHRS headline rating | `r` (0–5) | FSA | 0.45 |
| Food hygiene sub-score | `sh` | FSA | 0.20 |
| Structural compliance | `ss` | FSA | 0.15 |
| Confidence in management | `sm` | FSA | 0.15 |
| Inspection recency | derived from `rd` | FSA | 0.05 |

No other signals may contribute to this component.

### 3.2 Normalisation

- `r`: map `{0→0.0, 1→0.2, 2→0.4, 3→0.6, 4→0.8, 5→1.0}`. Ratings `AwaitingInspection`, `Exempt`, `Pass` (Scotland) → component unavailable; set `trust_available = false`.
- `sh`, `ss`, `sm`: FSA sub-scores are inverse (lower = better). Normalise with `norm = 1 - min(raw, 20) / 20`.
- Inspection recency: `recency = exp(-λ * days_since_rd)` with **λ = 0.0023** (~300-day half-life). If `rd` missing → recency = 0.

### 3.3 Component Assembly

```
TrustCompliance_0_1 = 0.45*r_norm + 0.20*sh_norm + 0.15*ss_norm + 0.15*sm_norm + 0.05*recency
TrustCompliance    = 10 * TrustCompliance_0_1
```

If `trust_available = false`, `TrustCompliance = None` and the 40% weight is unachievable (feeds rankability, §8).

### 3.4 Stale Inspection Logic

See §7.3. Stale inspections cap, not zero.

---

## 4. Customer Validation (45%)

**Frame:** Platform rating/count metadata only. **Review text, aspect sentiment, and AI summaries are not inputs here.** See §6 and §9.

### 4.1 Allowed Platforms

| Platform | Rating field | Count field | Required to be present |
|---|---|---|---|
| Google | `gr` (0–5) | `grc` | No — but used when available |
| TripAdvisor | `ta` (0–5) | `trc` | No |
| OpenTable | `ot_rating` (0–5) | `ot_count` | No — schema reserved for later |

No other rating platforms feed this component. Yelp, Facebook ratings, Instagram signals, and blog mentions are excluded.

### 4.2 Bayesian Shrinkage (per platform)

For each platform `p` with rating `R_p ∈ [0,5]` and count `N_p`:

```
shrunk_p = (N_p * R_p + k_p * m_p) / (N_p + k_p)
```

Where:

| Platform | Prior mean `m_p` | Pseudo-count `k_p` |
|---|---|---|
| Google | 3.8 | 30 |
| TripAdvisor | 3.6 | 25 |
| OpenTable | 4.0 | 20 |

The prior means reflect observed global distributions on each platform (Google skews high, TA lower, OT higher). Pseudo-counts are the number of synthetic "average" reviews blended in; a venue with `N_p << k_p` is pulled strongly toward `m_p`.

Normalise each `shrunk_p` to 0–1 via `shrunk_p / 5`.

### 4.3 Combination Across Platforms

Weight each platform's contribution by `min(N_p, N_cap_p) / N_cap_p` where `N_cap_p` is the count at which the platform is considered "fully evidenced":

| Platform | `N_cap_p` |
|---|---|
| Google | 200 |
| TripAdvisor | 150 |
| OpenTable | 100 |

Let `w_p = min(N_p, N_cap_p) / N_cap_p` for each available platform, floor `w_p ≥ 0.05` to preserve some signal from very small samples while letting shrinkage do its job.

```
CV_0_1 = Σ_p (w_p * shrunk_p_norm) / Σ_p w_p
CustomerValidation = 10 * CV_0_1
```

### 4.4 Single-Platform Case

If only one platform is present, `CustomerValidation` is computed from that platform alone via the same shrinkage. The confidence class is capped at `Rankable-B` (see §8).

### 4.5 Very Low Review Counts

- `N_p < 5` on a platform: that platform still contributes but its `w_p` is floored at 0.05 and the venue is capped at `Directional-C` unless another platform with `N >= 30` is present.
- All platforms have `N_p < 5` combined: `CustomerValidation` still computes (heavy shrinkage), but the venue is forced to `Directional-C` at best.
- No platforms present: `CustomerValidation = None`. 45% weight unachievable. Venue → `Profile-only-D` unless trust + commercial compensate (see §8).

### 4.6 Explicit Exclusions

No sentiment, no aspect scores, no review text parsing, no photo counts, no "recent review velocity" bonuses. Recency of reviews does **not** adjust `CustomerValidation` in V4.

---

## 5. Commercial Readiness (15%)

**Frame:** Public customer-path signals — can a customer find, contact, and transact with this venue? This is **not** a food-quality component and the report must label it accordingly ("Easy to find and book" vs "Hard to reach").

### 5.1 Allowed Signals

| Signal | Boolean / scalar | Weight |
|---|---|---|
| Website present | bool | 0.25 |
| Menu online (linked from website or Google) | bool | 0.25 |
| Opening hours completeness (7/7 days populated, non-empty) | 0–1 (days_with_hours / 7) | 0.25 |
| Booking or contact path (phone OR reservation link OR booking widget) | bool | 0.25 |

### 5.2 Normalisation and Assembly

Each boolean → `{true: 1.0, false: 0.0}`. Sum weighted components into `CR_0_1`, then `CommercialReadiness = 10 * CR_0_1`.

If zero signals are observable (no Google place record and no alternate source), `CommercialReadiness = None`.

### 5.3 Hard Exclusions From This Component

Delivery, takeaway, parking, wheelchair access, dog-friendly, outdoor seating, payment methods — **not** used as generic positive-quality proxies. They may appear on the profile page as attributes but do not feed the score.

---

## 6. Explicit Removals From Headline Score

The following are **removed** from headline scoring in V4. They may be retained for profile display or narrative generation but must not influence `rcs_v4_final`.

| Removed input | V3.4 behaviour | V4 behaviour |
|---|---|---|
| Review-text sentiment | Fed Tier 2 with red-flag penalties | Report-only (§9) |
| Aspect sentiment (food/service/ambience/value/cleanliness) | Tier 2 sub-signals | Report-only |
| Google AI summaries | Ingested as sentiment | Excluded entirely |
| Photo count | Tier 2 sub-signal | Profile attribute only |
| Price level | Tier 2 sub-signal | Profile attribute only |
| Place types (`gty`) | Tier 2 sub-signal + operational inference | Used only for non-food exclusion and cuisine labelling |
| Delivery / takeaway / parking / wheelchair | Operational tier positive signals | Profile attributes only |
| Social presence (FB, IG, website inferred from Google) | Online presence tier | Only `website present` in §5 |
| Cross-source convergence bonus | ±3%/±5% multiplier | Removed entirely |

Rationale: these either double-count signals already captured by rating metadata, or introduce high-variance text-derived noise that does not survive the "conservative under uncertainty" principle.

---

## 7. Modifiers and Penalties

### 7.1 Distinction Modifier (Michelin / AA only)

Additive, after component assembly, before penalties. Total cap **+0.30** on the 0–10 scale.

| Distinction | Modifier | Notes |
|---|---|---|
| Michelin 3 Star | +0.30 | Cap reached by this alone |
| Michelin 2 Star | +0.25 | |
| Michelin 1 Star | +0.20 | |
| Michelin Bib Gourmand | +0.12 | |
| Michelin Green Star | +0.08 | Stackable with food stars, subject to cap |
| Michelin Guide listing (no award) | +0.05 | |
| AA 5 Rosette | +0.20 | |
| AA 4 Rosette | +0.15 | |
| AA 3 Rosette | +0.10 | |
| AA 2 Rosette | +0.06 | |
| AA 1 Rosette | +0.03 | |

Stack by summing, then clamp to **+0.30**. No other awards (local press, tourism boards, trade press) feed this modifier in V4.

### 7.2 Companies House Risk Penalties and Caps

Applied to `adjusted` after distinction modifier.

| Rule | Condition | Effect |
|---|---|---|
| CH-1 | Company status = `dissolved` | Hard cap at **3.0**; flag `entity_dissolved = true` |
| CH-2 | Company status = `liquidation` or `administration` | Hard cap at **5.0** |
| CH-3 | Accounts overdue > 90 days | `-0.30` absolute |
| CH-4 | Director churn ≥ 3 in trailing 12 months | `×0.92` multiplier |
| CH-5 | No Companies House match and venue is not a sole trader / exempt form | No penalty, but `entity_match = ambiguous` feeds rankability |

If the venue's Companies House entity cannot be matched with confidence, treat as **CH-5** — no penalty, but confidence class degrades (see §8).

### 7.3 Stale Inspection Logic

Applied to `TrustCompliance` before component assembly contributes to `base`.

| Condition | Effect |
|---|---|
| `rd` missing | Recency = 0 (already in §3.2); no further action |
| Days since `rd` > 730 AND `r ≥ 3` | Soft cap: `TrustCompliance = min(TrustCompliance, 7.0)` |
| Days since `rd` > 1095 | `-15%` multiplier on `TrustCompliance` |
| Days since `rd` > 1825 (5 yr) | Hard cap `TrustCompliance ≤ 5.0` |

### 7.4 Closure / Dissolution / Unmatched Entity

| Condition | Treatment |
|---|---|
| FSA record flagged closed OR Google `business_status = CLOSED_PERMANENTLY` | Remove from rankings. Profile marked "Closed". No score published. |
| `business_status = CLOSED_TEMPORARILY` | Score computed; flag set; excluded from league tables until reopened |
| Companies House = dissolved AND no active FSA inspection in last 12 months | Remove from rankings |
| **No valid entity match** (cannot resolve to an FSA record AND no Google Place match) | **Unranked.** No score output. Profile-only stub or dropped entirely at pipeline discretion. |

---

## 8. Confidence and Rankability

Four classes. Every scored venue is assigned exactly one.

### 8.1 Classes

| Class | Meaning | League table? |
|---|---|---|
| `Rankable-A` | Strong multi-source evidence; safe to rank | Yes — primary |
| `Rankable-B` | Acceptable evidence but single-platform or thinner | Yes — secondary |
| `Directional-C` | Score computed but not reliable for ranking | No — "Directional" list only |
| `Profile-only-D` | Insufficient for a headline number | No — profile page only, no score shown |

### 8.2 Evidence and Source-Family Requirements

A "source family" is one of: **FSA/FHRS**, **Customer platforms** (Google/TA/OT), **Commercial readiness** (public customer-path). Companies House is a modifier family, not a primary evidence family.

| Class | Required source families | Minimum signals | Minimum review count | Other gates |
|---|---|---|---|---|
| Rankable-A | All 3 primary families present | ≥ 10 populated signals across components | ≥ 50 combined reviews across platforms, OR ≥ 30 on a single platform | No active CH-1/CH-2 cap; `entity_match = confirmed` |
| Rankable-B | ≥ 2 primary families | ≥ 7 populated signals | ≥ 10 combined reviews | `entity_match ∈ {confirmed, probable}` |
| Directional-C | ≥ 1 primary family | ≥ 4 populated signals | Any, including 0 if FSA + Commercial cover | Ambiguous entity match allowed |
| Profile-only-D | Fails Directional-C gates | — | — | — |

### 8.3 Full Rankability

A venue is **fully rankable** (eligible for default league tables and "Top N" lists) iff `class ∈ {Rankable-A, Rankable-B}` AND none of the following:

- `business_status = CLOSED_*`
- `entity_dissolved = true`
- Stale inspection hard cap active (§7.3 row 4)
- Zero customer-platform data (pure FSA score only)

### 8.4 Ambiguity Handling

- If two candidate entities match a venue (e.g., duplicate Google Place IDs or two FSA records at one address) with no resolver, class is capped at `Directional-C` until disambiguated.
- If the FHRS record is `AwaitingInspection` and no customer-platform data exists, class is `Profile-only-D`.
- If Google returns `business_status = OPERATIONAL` but FSA has no matching inspection within 5 years, class is capped at `Rankable-B`.

### 8.5 Single-Platform Customer Validation Cap

Per §4.4, venues with only one customer-validation platform are capped at `Rankable-B`.

---

## 9. Handling sparse review text and small samples

This section is normative for both the engine and any downstream report generator.

- **Google 5-review text is not used in headline scoring.** Neither the text nor any sentiment derived from it contributes to `CustomerValidation`, `TrustCompliance`, or `CommercialReadiness`.
- **Review text is report-only.** Text may be surfaced to users in the profile ("Recent guest comments") and may inform narrative language, but never the score.
- **Low review volume triggers shrinkage, not sentiment scoring.** When `N_p` is small, the Bayesian shrinkage in §4.2 pulls `shrunk_p` toward the platform prior. The engine does not attempt to extract "more signal" from text to compensate.
- **Weak text evidence may affect confidence or report language only.** If a narrative generator sees thin or contradictory text, it must soften language (e.g., "limited reviews available") and may feed a `text_evidence_weak` flag into the confidence annotation — but must not alter `rcs_v4_final`.
- **No aspect sentiment backfill.** V3.4's food/service/ambience/value/cleanliness aspect sentiment is removed entirely from scoring. If present in the data pipeline, it is ignored by the V4 engine.

Implementation: the V4 engine must refuse to read any `sentiment_*`, `aspect_*`, `ai_summary`, or `review_text` fields from its input. A linter check in CI should fail the build if the V4 scoring module imports these.

---

## 10. Output and Compatibility

### 10.1 Per-Venue Output Schema

The V4 engine emits one record per venue:

```json
{
  "fhrsid": "...",
  "name": "...",
  "components": {
    "trust_compliance": { "score": 8.200, "available": true, "signals_used": 5 },
    "customer_validation": {
      "score": 7.450,
      "available": true,
      "platforms": {
        "google":      { "raw": 4.3, "count": 412, "shrunk": 4.24, "weight": 1.00 },
        "tripadvisor": { "raw": 4.0, "count": 58,  "shrunk": 3.88, "weight": 0.39 }
      }
    },
    "commercial_readiness": { "score": 7.500, "available": true, "signals_used": 3 }
  },
  "modifiers": {
    "distinction": { "value": 0.12, "sources": ["michelin_bib_gourmand"] }
  },
  "penalties_applied": [
    { "code": "CH-3", "effect": "-0.30 absolute", "reason": "accounts_overdue_days=142" }
  ],
  "caps_applied": [],
  "base_score": 7.742,
  "adjusted_score": 7.862,
  "rcs_v4_final": 7.562,
  "confidence_class": "Rankable-A",
  "rankable": true,
  "league_table_eligible": true,
  "source_family_summary": {
    "fsa": "present",
    "customer_platforms": ["google", "tripadvisor"],
    "commercial": "partial",
    "companies_house": "matched"
  },
  "audit": {
    "engine_version": "v4.0.0",
    "computed_at": "2026-04-16T12:00:00Z",
    "input_snapshot_hash": "sha256:...",
    "decision_trace": [
      "TrustCompliance=8.200 (r=5, sh=0, ss=0, sm=0, recency=0.78)",
      "CustomerValidation=7.450 (google w=1.00 shrunk=4.24; ta w=0.39 shrunk=3.88)",
      "CommercialReadiness=7.500 (website+menu+hours=1.0; booking=0)",
      "base=7.742; distinction+0.12; CH-3 -0.30; final=7.562",
      "class=Rankable-A (3 families, 12 signals, 470 reviews)"
    ]
  }
}
```

### 10.2 Required Output Files

| File | Purpose |
|---|---|
| `*_rcs_v4_scores.csv` | One row per venue, rank, component scores, final score, class, flags |
| `*_rcs_v4_scores.json` | Full per-venue records per §10.1 |
| `*_rcs_v4_summary.json` | Aggregate stats: class distribution, mean/median/stdev, source-family coverage |
| `*_rcs_v4_report.md` | Human-readable narrative (may use report-only signals per §9) |

### 10.3 V3.4 Compatibility

Column names remain backwards-compatible where semantics align:

| V3.4 column | V4 column | Compatible? |
|---|---|---|
| `rcs_final` | `rcs_v4_final` | Same scale, different semantics — do not compare directly |
| `confidence_band` | `confidence_class` | Renamed; mapping: High↔Rankable-A, Medium↔Rankable-B, Low↔Directional-C, Insufficient↔Profile-only-D (approximate) |
| Tier 1 score | `components.trust_compliance.score` | Same scale 0–10 |
| Tier 2 score | `components.customer_validation.score` | Same scale; **different composition** (no sentiment, no aspects) |
| Tier 3–6 scores | Folded into `commercial_readiness` or removed | Not 1:1 comparable |

During cutover, the engine must emit **both** V3.4 and V4 output files for the same input snapshot, so deltas can be diffed per venue. See §11.

---

## 11. Migration from V3.4

### 11.1 What Remains Legacy

The V3.4 engine (`rcs_scoring_stratford.py`) stays in the repo unchanged until V4 ships. It continues to produce `stratford_rcs_scores.csv` until V4 is cut over.

### 11.2 What Will Be Deprecated

On V4 cutover:

- **Deprecated immediately:** aspect sentiment ingestion, Google AI summary ingestion, cross-source convergence bonus/penalty, Community tier (already removed in V3.4), photo/price/types as score inputs, delivery/takeaway/parking as positive quality signals, V3.4's 18-rule penalty table (replaced by §7).
- **Deprecated but retained for profile display:** review text, photo counts, place types (for cuisine labelling and non-food exclusion only), attribute booleans (parking, wheelchair, etc.).
- **Removed from the codebase:** any code path that reads `sentiment_*`, `aspect_*`, `ai_summary` into scoring. Enforcement by CI lint per §9.

### 11.3 Required Comparison Artifacts Before Cutover

Before V4 is declared primary, produce and review:

1. **Dual-score CSV** — one row per Stratford venue with `rcs_v3_4_final`, `rcs_v4_final`, delta, confidence_band (V3.4), confidence_class (V4), and a `movement_reason` column listing which V4 rules caused the change.
2. **Rank migration table** — per-venue rank under V3.4 vs V4, sorted by absolute rank change. Flag any venue moving > 25 ranks.
3. **Class reclassification matrix** — 4×4 (V3.4 band → V4 class) count table.
4. **Band distribution diff** — V3.4 band counts vs V4 class counts side by side.
5. **Removed-signal impact audit** — for each removed input (aspect sentiment, convergence bonus, etc.), the list of venues whose V3.4 score materially depended on it (`|delta| > 0.5`).
6. **Top-20 delta review** — top 20 biggest upward and top 20 biggest downward movers with human-readable decision traces.

Cutover is gated on: (a) no unexplained movers beyond ±1.0 on the 0–10 scale, (b) class reclassification matrix reviewed, (c) `Profile-only-D` set manually spot-checked to confirm no ranked venue was dropped by accident.

### 11.4 Versioning

- Engine version string: `v4.0.0` in `audit.engine_version`.
- Bump minor for prior/pseudo-count adjustments. Bump major only for weight structure changes.
