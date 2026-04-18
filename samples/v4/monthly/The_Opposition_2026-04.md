# The Opposition — Monthly Intelligence Report
*2026-04 · Engine v4.0.0 · Rankable-B*

*Also trading as:* Opposition Bistro, The Opposition Bistro

> ⚠️ **Temporarily closed** — excluded from league tables until reopened. Score preserved.

---

## Executive Summary

**What you should fix now:**

1. **Maintain accurate temporary-closure messaging** [FIX] — While `business_status = CLOSED_TEMPORARILY` is set, ensure the public profile communicates the closure window and any e
2. **Publish a reachable phone number or booking link** [FIX] — The booking / contact path sub-signal carries 25% of the Commercial Readiness component weight and is currently absent.

**V4 Score:** 8.895 / 10 · Rankable-B.
**Components:** Trust 8.88; Customer Validation 9.37; Commercial Readiness 7.50.

*External-evidence diagnosis. No POS or internal data required. See Data Basis below.*

## Financial Impact & Value at Stake

*Financial impact cannot be robustly estimated this month.* Commercial Readiness evidence is thin — website inferred rather than observed, and no booking-path signal — which is where most recoverable revenue shows up in the model. Once booking-path evidence lands (a published phone number, an observed reservable attribute, or a linked booking widget) the next report will include a Moderate-confidence estimate. Recommended action: publish a reachable phone number.

## Score, Confidence & Rankability Basis

**Confidence class:** Rankable-B
**Rankable:** Yes  ·  **League-eligible:** No
**Entity match:** confirmed

Acceptable evidence, but venue is temporarily closed — excluded from league tables until reopened.

**Primary evidence families present:**
- FSA / FHRS: present
- Customer platforms: google
- Commercial readiness: full
- Companies House: unmatched

**V4 Score: 8.895 / 10** · Rankable-B

| Component | Score | Evidence |
|---|---:|---|
| Trust & Compliance | 8.883 | compliance; not food quality · signals used: 5 |
| Customer Validation | 9.370 | Google 533 @ 4.8 |
| Commercial Readiness | 7.500 | web ✓ · menu ✓ · hours 7/7 · booking — |

## Operational & Risk Alerts

> *Legal, safety, or reputational red flags detected in review text. Narrative only — these do not feed the V4 score (spec §7.1).*

No operational or risk alerts above baseline this period.

## Trust & Compliance

**Component score:** 8.883 / 10  ·  *compliance signal; not food quality.*

**FHRS decomposition**

| Signal | Value |
|---|---:|
| FHRS headline rating (0–5) | 5 |
| Food hygiene sub-score | 7.5 |
| Structural compliance sub-score | 7.5 |
| Confidence in management sub-score | 10.0 |
| Last inspection date | 2025-07-03T00:00:00 |

## Customer Validation

**Component score:** 9.370 / 10  ·  *public rating metadata; shrinkage applied to low-count evidence.*

| Platform | Raw rating | Reviews | Shrunk rating | Coverage weight |
|---|---:|---:|---:|---:|
| Google | 4.8 | 533 | 4.74 | 1.00 |

*Single customer platform — this class is capped at Rankable-B regardless of score. Peer comparisons are directional.*

## Commercial Readiness / Demand Capture Audit

**Component score:** 7.500 / 10  ·  *can a guest find and book; not a food-quality signal.*

**Commercial Readiness sub-signals (V4 scoring inputs)**

| Sub-signal | Value | In score |
|---|---|---:|
| Website present | Yes | 25% |
| Menu online | Yes | 25% |
| Opening-hours completeness | 7/7 days | 25% |
| Booking / contact path | No (observed: phone or reservable absent) | 25% |

**Demand Capture Audit** — outside-in customer-journey check. *Narrative only — does not feed the score.*

| Dimension | Verdict | Note |
|---|---|---|
| Booking Friction | Partial |  |
| Menu Visibility | Missing |  |
| CTA Clarity | Clear |  |
| Photo Mix & Quality | Clear |  |
| Proposition Clarity | Partial |  |
| Mobile Usability | Clear |  |
| Promise vs Path | Partial |  |

## Market Position

*League-table placement suppressed while this venue is excluded from the default league: venue is temporarily closed.*

## Competitive Market Intelligence

- **Competitive density:** 181 direct competitors within 5 mi. Differentiation is commercially critical; lean on Distinction, Customer Validation top-of-band, and Commercial Readiness to stand apart.

## Management Priorities

### Priority 1: Maintain accurate temporary-closure messaging [FIX | NEW]

While `business_status = CLOSED_TEMPORARILY` is set, ensure the public profile communicates the closure window and any expected reopening date so customers do not arrive to a closed venue.

**Evidence:** business_status: CLOSED_TEMPORARILY.

**Expected upside:** prevents reputation damage from confused arrivals.

*Targets component: Commercial Readiness. V4 components feed the headline — this priority is how the score moves in the direction the observable evidence supports. (No specific score-movement number is forecast.)*

### Priority 2: Publish a reachable phone number or booking link [FIX | NEW]

The booking / contact path sub-signal carries 25% of the Commercial Readiness component weight and is currently absent.

**Evidence:** No phone / reservation_url / reservable observed.

**Expected upside:** adds 25% of the Commercial Readiness component once a contact path publishes.

*Targets component: Commercial Readiness. V4 components feed the headline — this priority is how the score moves in the direction the observable evidence supports. (No specific score-movement number is forecast.)*

## Watch List

No explicit watch items this month. Default monitoring: FHRS inspection recency, Customer Validation platform counts, and any new Companies House filings.

## What Not to Do This Month

- **Don't prioritise:** Don't chase reviews purely to lift the score. Customer Validation Bayesian shrinkage dampens the per-review effect on the shrunk rating until volume clears the platform n_cap / 2 threshold; review-volume growth is a long-game watch item, not a fix.
- **Don't prioritise:** Don't treat photos, price level, social, delivery, takeaway, parking, or wheelchair access as score levers. These are profile attributes only in V4; changing them does not move the headline.

## Profile Narrative & Reputation Signals

> *Narrative only — none of the material below feeds the V4 score. Review text, aspect themes, segment reads, menu intelligence, and trajectory notes are profile-only per spec §7.1 / §8.*

**Review-text confidence tier:** Anecdotal  ·  reviews analysed: 0.

*No review text is available for narrative analysis this month. The aggregate public rating (Customer Validation component, above) is the reputation signal. Review-text narrative will be possible once review text has been collected for this venue.*

## Implementation Framework

| Action | Targets component | Status | Target date | Cost band | Expected upside | Next milestone |
|---|---|---|---|---|---|---|
| Maintain accurate temporary-closure messaging | Commercial Readiness | New | 25 April 2026 | Zero (profile update) | prevents reputation damage from confused arrivals. | Update the Google Business Profile description to include the closure window and expected reopening date. |
| Publish a reachable phone number or booking link | Commercial Readiness | New | 09 May 2026 | Low (< £200) | adds 25% of the Commercial Readiness component once a contact path publishes. | Log into business.google.com → select venue → Info → add a public phone number or booking link. |

*Upside claims cite the observable path they depend on; they do not forecast a specific `rcs_v4_final` movement. See the Evidence column in the Management Priorities section above for the V4 fields each action targets.*

## Next-Month Monitoring Plan

- Track review-count movement on: Google.
- Monitor FHRS re-inspection activity (check quarterly).
- Watch confidence-class movement: any shift between Directional-C ↔ Rankable-B is a material evidence event.

## Data Basis / Coverage & Confidence

**Source families present**

| Family | Status | Notes |
|---|---|---|
| FSA / FHRS | present | Compliance ground truth. |
| Customer platforms | google | Public rating metadata (counts and ratings). |
| Commercial readiness | full | Public customer-path signals. |
| Companies House | unmatched | Business-viability risk (penalty only). |

**Review text** — 0 reviews analysed. Narrative only; not a score input.

**Confidence class:** Rankable-B. Acceptable evidence, but venue is temporarily closed — excluded from league tables until reopened.

## Evidence Appendix

*Factual inventory of the observable data underpinning this report.*

| Field | Value |
|---|---|
| FHRSID | 503481 |
| FSA rating (0–5) | 5 |
| Last inspection date | 2025-07-03T00:00:00 |
| Google rating | 4.8 |
| Google review count | 533 |
| Google place ID | ChIJ7f1ZJjLOcEgREqBVi1vVlKY |
| TripAdvisor rating | — |
| TripAdvisor review count | — |
| TripAdvisor URL | — |
| Website present | True |
| Website URL (observed) | — |
| Phone | — |
| Reservable attribute | — |
| Michelin type | — |
| AA rosettes | — |

## How the Score Was Formed

**Formed from:** Trust 8.88 + Customer 9.37 + Commercial 7.50. Final: 8.895.

<details>
<summary>Raw engine trace (for audit)</summary>

```
TrustCompliance=8.883 (r_norm ok, signals_used=5, recency=0.516)
CustomerValidation=9.370 (google n=533 raw=4.8 shrunk=4.74 w=1.00)
CommercialReadiness=7.500 (web=True, menu=True, hours=1.00, booking=False)
base=8.895; distinction+0.000; adjusted=8.895; final=8.895
class=Rankable-B; rankable=True; league=True
```

</details>

*Engine version: v4.0.0 · Computed at: 2026-04-17T15:59:26Z*


*Report generated by DayDine V4 Operator Report · Engine v4.0.0 · 2026-04*