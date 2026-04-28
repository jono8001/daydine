# ADR-002: Authorised review data, proprietary V5 positioning, and no Tripadvisor/OpenTable launch dependency

*Status:* Accepted, 2026-04-28.  
*Deciders:* jono8001 (product); ChatGPT (planning support).  
*Supersedes/extends:* ADR-001 remains accepted. This ADR extends ADR-001 from an operational Tripadvisor deferral into a strategic positioning decision for V5 and launch planning.

---

## 1. Context

DayDine is being developed as a UK hospitality intelligence product with public rankings, operator intelligence and later SaaS dashboards.

Recent strategic work clarified three facts:

1. **OpenTable coverage is narrow in Stratford-upon-Avon.** It is useful for a small number of bookable restaurants, but it is not a town-wide coverage benchmark.
2. **Tripadvisor coverage is broad and review-rich, but skewed.** Tripadvisor appears to cover much more of the Stratford restaurant universe, but review volume is heavily concentrated among the already-visible top venues. The long tail is often thinly evidenced.
3. **DayDine cannot outgun Tripadvisor by pretending to have more review data.** DayDine must outgun Tripadvisor by becoming a different product: a proprietary hospitality intelligence engine that includes authorised review evidence, separates popularity from quality, and surfaces hidden-gem / overexposure / momentum signals.

ADR-001 already records that Tripadvisor collection is deferred and that Google Places is the canonical entity-resolution layer. It also preserves Rankable-A semantics and prevents Google Places identity facts from being counted as a second review platform.

This ADR records the broader product/methodology decision needed before the next build phase.

---

## 2. Decision

### 2.1 DayDine will not depend on unauthorised Tripadvisor/OpenTable review ingestion

DayDine's launch methodology must not depend on unauthorised scraping of Tripadvisor, OpenTable or other protected review platforms.

Tripadvisor and OpenTable may be used later only through:

- official API or partner/licensed routes;
- a legally reviewed third-party data-provider route;
- manual/licensing-aware references where appropriate;
- public outbound links that do not ingest or republish their review data.

This decision does not prohibit future use of Tripadvisor/OpenTable. It prohibits treating unauthorised scraping as a core launch foundation.

### 2.2 Google review rating and review volume are valid authorised review evidence

DayDine can say that its rankings include review evidence because Google rating and Google review volume are genuine public review signals when collected through the permitted Google Places route.

However, DayDine must not imply that it has full cross-web review coverage.

Approved wording:

> DayDine rankings include authorised public review evidence, including Google review rating and review volume, alongside trust, category, visibility and market-intelligence signals.

Prohibited wording unless data access changes:

> DayDine analyses all reviews across the web.
> DayDine includes Tripadvisor and OpenTable reviews.
> DayDine's ranking is based on the full universe of customer reviews.

### 2.3 V5 is the strategic destination

V4 remains the strongest current implemented baseline. V5 is the next methodology destination and should now be built beside V4, not as a destructive replacement.

V5 should be the **DayDine Evidence Rank Model**:

> A proprietary hospitality intelligence model that includes authorised review evidence but does not behave like a simple review aggregator.

V5 must remain valid without Tripadvisor/OpenTable data at launch.

### 2.4 Public methodology should have mystique

DayDine should publish transparent principles, not a fully transparent formula.

Public pages may show:

- overall rank;
- category rank;
- monthly movement;
- Evidence Confidence band;
- DayDine Signal;
- concise intelligence note;
- simple coverage summary.

Public pages should not show:

- exact formula;
- exact source weights;
- source-by-source component scorecards;
- detailed public improvement levers that make the model easy to game.

The commercial principle is:

> Transparent principles. Proprietary machinery. No pay-to-play.

---

## 3. Competitive positioning

Tripadvisor is a review platform. OpenTable is primarily a booking/review platform. DayDine should be positioned as a hospitality intelligence platform.

Core positioning:

> Tripadvisor shows who is already popular. DayDine reveals who is proven, under-discovered, rising or overexposed.

V5 should create distinct public views and operator insights around:

- **Proven Leaders** — venues with strong position and strong evidence.
- **Hidden Gems** — venues with strong underlying signals but lower public visibility.
- **Rising Venues** — venues with improving market signals or ranking movement.
- **Overexposed Venues** — venues with high visibility but weaker supporting signals.
- **Under-Evidenced / Profile Only** — venues where evidence is insufficient for strong claims.

The key proprietary concept is the **DayDine Gap Signal**:

> The gap between public popularity and underlying DayDine intelligence signals.

Positive gap:

> This venue may be stronger than its current public visibility suggests.

Negative gap:

> This venue may be more visible than its supporting signals justify.

---

## 4. Implications for methodology

### 4.1 Review volume must be capped

Google review count should increase confidence, but it must not endlessly dominate quality ranking.

Principle:

> More reviews should improve confidence, not mechanically swamp all other evidence.

V5 should use capped / saturating review-volume logic and Bayesian shrinkage.

### 4.2 Confidence must remain separate from score

Each venue should have at least:

```text
rank
score_estimate or internal score
Evidence Confidence
DayDine Signal
category_rank
movement
coverage_status
```

Public confidence labels should be directional and premium rather than spreadsheet-like.

### 4.3 FHRS remains trust/compliance, not food quality

FHRS/FSA should remain a trust and compliance layer. It should operate through gates, caps and confidence effects more than through large positive quality weighting.

A poor FHRS result can reduce trust. A good FHRS result should not by itself make a restaurant great.

### 4.4 Category-normalised ranking is mandatory

V5 must not rely only on one overall table. It must support:

- overall rank;
- category rank;
- occasion/category views;
- hidden-gem/rising/proven-leader views.

This prevents tourist-heavy casual venues from dominating all lists through raw visibility.

---

## 5. Implications for data-source strategy

### Core launch sources

- FSA/FHRS: venue universe and compliance/trust backbone.
- Google Places: identity, location, contact, website/hours and authorised review rating/count.
- Companies House: entity/trading-confidence context where matched.
- Manual local QA: high-value missing/ambiguous venue review.
- Expert recognition: manual/licensing-aware layer for Michelin/AA/local awards where appropriate.
- OSM/Overpass or equivalent: coverage cross-check, not primary ranking proof.

### Deferred / conditional sources

- Tripadvisor: only official/licensed/API-compatible or legally reviewed route.
- OpenTable: only partnership/licence/API-compatible route, or link out without ingesting reviews.
- Full review text: not a launch dependency and not a headline-ranking input.

---

## 6. Implications for public copy

Approved public framing:

> DayDine ranks restaurants using a proprietary hospitality intelligence model. Rankings include authorised public review evidence, including Google rating and review volume, alongside trust signals, venue information, category context, market visibility and evidence confidence.

Approved shorter framing:

> Ranked by DayDine Intelligence: authorised review evidence, trust signals, category context and market momentum.

Avoid:

> 40+ signals across 7 categories, unless this is implemented and true.
> Aspect-level review intelligence, unless licensed review text exists and is used.
> Cross-source review convergence, unless at least two independent review platforms are populated.
> Fully transparent ranking formula.

---

## 7. Required repo follow-up

1. Update `docs/DayDine-Current-State-And-Next-Actions.md` so the next phase is build, not more strategy.
2. Update `docs/DayDine-Professional-SaaS-Roadmap.md` so V5 is the next methodology build and Tripadvisor/OpenTable are not launch dependencies.
3. Create `docs/DayDine-V5-Evidence-Rank-Blueprint.md`.
4. Update `docs/DayDine-Launch-Readiness.md` to include authorised-review-data and public-mystique requirements.
5. Later, update `methodology.html` and public copy before public beta/cutover.

---

## 8. Acceptance criteria before V5 build starts

The planning docs are ready for build when they clearly state:

```text
[ ] V4 is the preserved implemented baseline.
[ ] V5 is the next methodology build direction.
[ ] V5 does not require Tripadvisor/OpenTable launch data.
[ ] Google review rating/count can be described as authorised review evidence.
[ ] Public methodology uses principles, not exact formula or public scorecards.
[ ] DayDine Signals are part of the V5 output contract.
[ ] Firebase Auth/client/admin build remains the immediate engineering priority.
[ ] Coverage certificates remain a required trust layer.
```

---

## 9. Consequences

Positive:

- DayDine no longer depends on fragile or unauthorised review scraping.
- Public claims become safer and more defensible.
- V5 has a distinctive strategic wedge against Tripadvisor.
- The product can move to build without waiting for Tripadvisor/OpenTable access.

Negative / risk:

- DayDine cannot claim full review-universe coverage at launch.
- Some users may still compare it directly with Tripadvisor unless positioning is clear.
- Public methodology must be rewritten carefully to avoid both over-transparency and overclaiming.

This ADR accepts those risks because the alternative — building a ranking business on unauthorised platform data or pretending Google alone equals the full review universe — is strategically weaker.
