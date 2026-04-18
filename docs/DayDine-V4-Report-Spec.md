# DayDine V4 Operator Report Specification

**Status:** Implementation-grade draft, Stack B.
**Audience:** Engineers implementing the operator monthly / quarterly report generator.
**Source of truth for scoring:** `rcs_scoring_v4.py` + `docs/DayDine-V4-Scoring-Spec.md`.
**Related internal docs:** `docs/DayDine-V4-Migration-Note.md`, `docs/DayDine-V4-Readiness-For-Stack-B.md`, `docs/DayDine-V4-Scoring-Comparison.md`.

> **Scope note.** This document defines the **operator-facing report**. It is not the public leaderboard, not the public methodology page, and not the consumer site. Those surfaces stay on V3.4 until the cutover gate closes. Nothing in this spec is a directive to change consumer-facing copy.

---

## 1. Report Purpose

The DayDine monthly operator report is an **external blind-spot diagnosis** for a venue operator. It tells an operator what an informed outsider can see about their venue using only public and licensed third-party data, how much confidence that evidence carries, and what commercial consequences follow.

### 1.1 What the report is

- **Operator-facing.** Written for the person running the venue, not for diners.
- **External-evidence-only.** Built from FSA / FHRS, Google Places metadata, TripAdvisor metadata, Companies House, Michelin, AA. No POS integration, no internal instrumentation.
- **Diagnostic, not prescriptive ranking.** It explains where the venue sits against public evidence and where there is commercial slack; it does not claim to be a ranking authority of last resort.
- **Separated by evidence type** (this is the core architectural rule of V4):
  1. **Score-based evidence** — the V4 components, distinction modifier, penalties, caps, and the final `rcs_v4_final` score. These drive the headline.
  2. **Confidence and rankability** — the V4 `confidence_class`, `rankable`, `league_table_eligible`, `entity_match_status`, and `source_family_summary`. These gate what claims the report is allowed to make.
  3. **Penalties and caps** — `penalties_applied[]`, `caps_applied[]`. Surfaced explicitly; never implicit.
  4. **Profile-only narrative and diagnostics** — review text, aspect themes, segment intelligence, menu-mention analysis, demand-capture audit, seasonal context, risk-phrase detection. Used for narrative only; never fed back into the score.

### 1.2 What the report is not

- Not the public leaderboard. The public league table runs on V3.4 until cutover; the operator report runs on V4 today.
- Not a copy of any ranking page. Peer position appears in the operator report but only inside the V4 rankability contract (see §4.5 / §5).
- Not a replacement for operator-side dashboards, management accounts, or compliance audits.
- Not a vehicle for score-driving any input the V4 spec forbids. Review text, sentiment, aspect sentiment, AI summaries, photo counts, price level, non-gating place types, delivery / takeaway / parking / wheelchair, social presence, and cross-source convergence are all **narrative-only** in the report; they have zero effect on the score.

### 1.3 Why a separate spec

The previous (V3.4-era) report is commercially strong: actions-led executive summary, financial impact near the top, demand capture audit, segment intelligence, menu intelligence, trust decomposition, peer ring analysis, implementation framework. Those investments **stay**. What changes is the *scoring frame under them*. Every section must now read its scorecard from the V4 engine output and label its claims against the V4 confidence class. This spec exists to make that re-seating explicit and testable.

---

## 2. Authoritative Report Inputs

Every report is built from a single **ReportInputs** payload. The payload is assembled by an adapter (planned as `operator_intelligence/v4_adapter.py`) and must pass a strict allow-list check before any builder reads it.

### 2.1 Required V4 fields (score-driving)

These come verbatim from `V4Score.to_dict()` (per scoring spec §10.1) and are the **only** values that may drive the headline, per-component scores, penalty surface, or rankability caveats:

| Field | Type | Report usage |
|---|---|---|
| `fhrsid`, `name` | str | Venue identity anchor |
| `rcs_v4_final` | float \| None | Headline score. `None` = no published score (permanent closure per scoring spec §7.4). |
| `base_score`, `adjusted_score` | float | Auditable intermediate values for the "how the score was formed" block. |
| `components.trust_compliance.{score, available, signals_used}` | nested | Trust & Compliance section |
| `components.customer_validation.{score, available, platforms.*.{raw, count, shrunk, weight}}` | nested | Customer Validation section |
| `components.commercial_readiness.{score, available, signals_used}` | nested | Commercial Readiness / Demand Capture section |
| `modifiers.distinction.{value, sources[]}` | nested | Distinction (Michelin / AA) row in the headline card |
| `penalties_applied[]` (each: `code, effect, reason`) | list | Decision-trace appendix + any section that touches the corresponding domain |
| `caps_applied[]` (each: `code, effect, reason`) | list | Same as above; also drives league-eligibility caveats |
| `confidence_class` ∈ `{Rankable-A, Rankable-B, Directional-C, Profile-only-D}` | str | Class banner on every page; gating for peer / financial claims |
| `rankable` | bool | League-table placement rules |
| `league_table_eligible` | bool | "Top-N" surfaces |
| `entity_match_status` ∈ `{confirmed, probable, ambiguous, none}` | str | Entity-match banner; trading-name fallback |
| `source_family_summary.{fsa, customer_platforms[], commercial, companies_house}` | nested | Data Basis section |
| `audit.engine_version` | str (`v4.0.0`) | Footer / decision trace header |
| `audit.computed_at` | ISO 8601 str | Footer / decision trace header |
| `audit.decision_trace[]` | list[str] | "How the score was formed" block |

### 2.2 Allowed narrative inputs (profile-only, never score-driving)

The following are permitted in the report but **must not** be presented as inputs to the score. Builders that use them must be covered by the §7 narrative guardrails.

| Input | Source | Report section(s) |
|---|---|---|
| Review text (individual review bodies) | `g_reviews[]`, `ta_reviews[]` (read only via the review-intel side channel, not via `record.get()`) | Profile Narrative & Reputation Signals; Review-by-Review Appendix |
| Aspect themes (food / service / ambience / value / speed / cleanliness / safety / booking) | `operator_intelligence/review_analysis.py` | Profile Narrative |
| Segment intelligence (theatre-goers, couples, tourists, locals, business, family) | `operator_intelligence/segment_analysis.py` | Guest Segment Intelligence |
| Risk phrase detection | `operator_intelligence/risk_detection.py` | Operational & Risk Alerts |
| Menu dish mentions | `operator_intelligence/builders/menu_intelligence.py` | Menu & Dish Intelligence |
| Demand forecast (bank holidays, RSC calendar, school terms) | `operator_intelligence/builders/event_forecast.py` | Next-30-Days Demand Forecast |
| Monthly movement deltas | Prior-month JSON snapshot | Monthly Movement Summary |
| Peer benchmarks | `operator_intelligence/peer_benchmarking.py` | Market Position / Competitive Market Intelligence |
| Trading-name aliases | `data/entity_aliases.json` via the resolver | Venue Identity header |

These inputs populate narrative. They do not populate `rcs_v4_final`. Any report prose that states or implies otherwise is a guardrail violation (see §10).

### 2.3 Forbidden as score drivers (hard allow-list)

The report must explicitly state, and the generator must enforce, that the following are **not** score inputs in V4. They may appear as narrative context (where §2.2 permits) but never as reasons the score is what it is:

- Review text
- Sentiment scores (overall, aspect-level, AI-derived)
- AI summaries
- Photo count (`gpc`)
- Price level (`gpl`)
- Place types (`gty`) other than non-food exclusion and cuisine labelling
- Social presence (`fb`, `ig`) — only `web` feeds Commercial Readiness
- Delivery, takeaway, parking, wheelchair access, dog-friendly, outdoor seating (profile attributes only)
- Cross-source convergence bonus / penalty (removed in V4)
- Community-tier signals (removed in V3.4 already; remain removed)

The adapter must raise on any attempt to pass a field from this list into `ReportInputs`. This mirrors `FORBIDDEN_FIELDS` in the scoring engine.

### 2.4 Supporting inputs (non-scoring, non-narrative)

| Input | Purpose |
|---|---|
| `stratford_menus.json` entry | `has_menu_online` flag for Commercial Readiness section |
| `stratford_editorial.json` entry | Distinction modifier sources (verification only — the scoring engine has already consumed this) |
| `stratford_tripadvisor.json` (side file) | Trading-name / URL context only; headline TA rating / count already in the venue record |
| Prior month `*_report_v4.json` | Month-over-month delta computation |
| `stratford_entity_resolution_report.json` | Ambiguous-gpid groupings, named-unresolved list (for search / UI context only) |

### 2.5 ReportInputs contract (rule, not full schema)

The implementation must define `ReportInputs` as an explicit dataclass with named fields — no `**kwargs`, no generic dict passthroughs. Field renames are then a one-location change. The construction path is:

```
V4Score.to_dict()  +  venue record  +  menu entry  +  editorial entry
      +  review intelligence (text)  +  peer benchmarks  +  prior-month snapshot
      -> ReportInputs(...)
```

Adapter construction fails (raises) if any field in §2.3 is present in the input dict. The generator does not work around this — it surfaces the error as a QA failure.

---

## 3. Report Types

The report generator produces one of five rendering modes. The mode is derived directly from the V4 engine output, not from any secondary heuristic. Every builder in §5 declares per-mode behaviour.

### 3.1 `Rankable-A`

**Meaning:** Strong multi-source evidence; `entity_match_status = confirmed`; ≥2 primary families populated for customer validation; trust and commercial families present; ≥ 50 combined reviews (or ≥ 30 on one platform); no active CH-1/CH-2 cap.

**Report behaviour:**
- Full monthly report renders as specified in §5.
- Peer-position sections compare against the `Rankable-A ∪ Rankable-B` pool.
- Financial Impact section may render with **Moderate-to-High confidence** where evidence supports it (see §6).
- Narrative may make directional claims about category position where peer data corroborates.
- Distinction modifier is rendered alongside the score.
- Full Implementation Framework and action tracker.

### 3.2 `Rankable-B`

**Meaning:** Acceptable evidence, typically single-platform customer validation, or thinner review counts, or only two of three primary families. `entity_match_status` ∈ {`confirmed`, `probable`}.

**Report behaviour:**
- Full monthly report renders.
- Peer-position sections still render but must add a caveat line: "Single-platform evidence — peer comparison is directional." when only one customer platform is present.
- Financial Impact section renders with **Moderate confidence** by default; **Low** if any CR sub-signal beyond website / hours is missing.
- Narrative must soften "category leader" / "leads the field" language — this class supports "performs well locally" but not "market leader".
- Distinction modifier rendered if present.
- Full action tracker.

### 3.3 `Directional-C`

**Meaning:** Score computed but not reliable for ranking. Causes include: all customer platforms at N<5 without a bigger other platform (§4.5 of scoring spec), ambiguous entity match, only one primary family populated, duplicate-gpid conflict.

**Report behaviour:**
- Report renders, with a mandatory **class banner** at the top: "Directional — not league-ranked. [reason]." The reason is drawn from the evidence: ambiguous entity, thin reviews, single family.
- Peer-position sections are **replaced** by a short "Why not ranked" explainer pulling from `confidence_class`, `entity_match_status`, `customer.platforms_count`, and `source_family_summary`.
- Financial Impact section renders at **Low confidence** or is suppressed entirely if CR is unavailable or customer validation is absent. Never render £ figures as if they were actionable.
- Narrative may discuss reputation signals but must use hedged language ("review evidence suggests …", not "guests consistently say …").
- The ambiguity reason is surfaced: if `entity_ambiguous` is true, the report lists the conflicting FHRSIDs / names so the operator can see what the ambiguity is.
- Implementation Framework still renders but is demoted in prominence; the first-call action is usually "resolve entity ambiguity" or "collect additional platform evidence".

### 3.4 `Profile-only-D`

**Meaning:** Insufficient evidence for a headline score. Primary families < 1 or signals < 4 or `entity_match_status = none`.

**Report behaviour:**
- Report renders as a **profile stub**, not a full report.
- No `rcs_v4_final` number is shown. The class banner reads: "Profile only — insufficient evidence for a published score."
- No peer sections. No Financial Impact section. No league-table references.
- Evidence Appendix renders (what data we do have) — this is the whole point of the profile stub.
- Narrative, if any, is limited to structural facts (FSA rating if present, business name, postcode, address).
- No Implementation Framework. Instead: a "How to unlock full scoring" block describing what additional data would lift the venue to `Rankable-*` (typically: one customer platform with ≥ 5 reviews, or entity-match resolution).

### 3.5 Closed (no published score)

**Meaning:** `rcs_v4_final` is `None` because closure was detected — Google `business_status = CLOSED_PERMANENTLY` or FSA `fsa_closed = true`.

**Report behaviour:**
- Report renders as a **closure notice**, not a diagnostic report.
- Header: "Closed — no score published." Include the closure evidence (Google business status, FSA flag, date observed).
- No component scores rendered.
- No peer sections.
- No Financial Impact section.
- No action tracker.
- Evidence Appendix may render (for audit / historical context).
- Monthly Movement Summary may render if a prior-month snapshot exists and the closure is newly detected — this is how the operator discovers the closure flag landed.

`CLOSED_TEMPORARILY` is **not** in this mode — those venues fall into the normal `Rankable-*` / `Directional-C` modes above with `league_table_eligible = False` and a "temporarily closed" flag surfaced in the header. See §4.6.

### 3.6 Summary table

| Mode | Score shown | Peer position | Financial Impact | Full sections | Mandatory banner |
|---|---|---|---|---|---|
| Rankable-A | Yes | Yes | Yes (Moderate–High) | Yes | None |
| Rankable-B | Yes | Yes with caveat | Yes (Moderate, Low if CR gaps) | Yes | Single-platform caveat if applicable |
| Directional-C | Yes with caveat | **No**, replaced by explainer | Low or suppressed | Yes, demoted | "Directional — not league-ranked" |
| Profile-only-D | **No** | No | **No** | Stub only | "Profile only — insufficient evidence" |
| Closed | **No** | No | **No** | Closure notice | "Closed — no score published" |

---

## 4. Report Headline Logic

The headline is the first screen an operator sees. It must convey score, confidence, rankability, and any immediate disqualifiers (closure, dissolution, ambiguity) before the operator scrolls. It preserves the V3.4 "lead with the money" instinct — Executive Summary, then Financial Impact — but re-seats every element in the V4 contract.

### 4.1 Main headline statement

The top-of-report H1 reads:

```
# {venue_name} — Monthly Intelligence Report
*{month_str} | Engine v4.0.0 | {class_banner_compact}*
```

`class_banner_compact` is one of:
- `Rankable-A` — no suffix.
- `Rankable-B` — no suffix.
- `Rankable-B · single-platform` — when `customer.platforms_count == 1`.
- `Directional-C · {reason}` — reason from the first truthy of: `entity_ambiguous`, "thin reviews", "single family", "unmatched entity".
- `Profile-only-D · insufficient evidence`.
- `Closed` — no ancillary text.

When the operator has a `public_name` distinct from the FSA `n`, the H1 uses `public_name`; the FSA legal entity appears in the venue-identity card below.

### 4.2 V4 score presentation

Directly under the H1, a **score card** is rendered. Never a dimension table. The card is mandatory in all modes except `Profile-only-D` and `Closed`.

```
V4 Score            7.562 / 10           Rankable-A
─────────────────────────────────────────────────────
Trust & Compliance     8.200 / 10   (compliance; not food quality)
Customer Validation    7.450 / 10   Google 412 @ 4.3 · TA 58 @ 4.0
Commercial Readiness   7.500 / 10   web · menu · hours 7/7 · booking —
Distinction            +0.12        Michelin Bib Gourmand
```

Presentation rules:
- `rcs_v4_final` rendered to 3 decimal places where it is a valid float. Never rendered as "0.0" when the mode is `Closed` or `Profile-only-D`; those modes suppress the number entirely.
- Each component shows score and the evidence it was built from. Never a freeform qualitative label like "strong" / "weak" that implies a band.
- Distinction row only renders when `distinction.value > 0`; list the `sources[]`.
- When a component is `available = false`, the row reads `— / 10 (insufficient evidence)` with the reason from `source_family_summary`.
- When a cap is active (e.g. `STALE-2Y` soft-caps Trust at 7.0), the Trust row adds a trailing note: "soft cap applied (days_since_rd = 812, r = 4)". Full details move to the decision-trace block.

### 4.3 Confidence class presentation

Confidence class is rendered **before** the commercial narrative, never after. It sits directly under the score card in a one-line banner with a short explanation:

- **Rankable-A** → "Strong multi-source evidence. Eligible for the primary league table."
- **Rankable-B** → "Acceptable evidence. Eligible for the secondary league table." If single-platform, add: "Single customer platform only — peer comparisons are directional."
- **Directional-C** → "Not league-ranked. [reason]. Narrative below should be treated as indicative; peer comparisons suppressed."
- **Profile-only-D** → "Insufficient evidence for a published score. Profile only."

The reason text for Directional-C is derived, in priority order, from:
1. `entity_match_status == "ambiguous"` → "Entity match ambiguous — multiple FHRSIDs share identifiers."
2. `entity_match_status == "none"` → "No entity match — unable to reconcile FSA and Google identifiers."
3. `customer.platforms_count == 0` → "No customer-platform evidence."
4. Low-review-cap active (any platform N<5, no other ≥30) → "Thin review evidence — below the minimum threshold for ranking."
5. `primary_families_available == 1` → "Only one primary evidence family present."

### 4.4 Rankability / league-eligibility presentation

Two flags matter:
- `rankable` — does this venue appear in *any* league table?
- `league_table_eligible` — does it appear in the *default / primary* league surface?

Rendering rules:
- If `rankable == True` and `league_table_eligible == True`: no additional banner. Peer sections render normally.
- If `rankable == True` and `league_table_eligible == False`: render a yellow-tone note explaining why (from `caps_applied[]`: `STALE-5Y` hard cap, CH-1/CH-2 cap, `CLOSED_TEMPORARILY`, or "zero customer data"). Peer sections render but add the same caveat.
- If `rankable == False` and the class is `Directional-C`: "Not ranked — [reason]". Replace the peer section with the explainer described in §4.3.
- If `rankable == False` and the class is `Profile-only-D`: "Profile only — not ranked." No peer sections.

The report never says "this venue is ranked X of Y" when the venue is not `league_table_eligible`.

### 4.5 Directional-C specifics

In addition to §3.3 and §4.3:

- The headline explicitly names the reason in plain English — not a code.
- If the reason is `entity_ambiguous`, list the conflicting FHRSIDs and names (pulled from the resolver report). Operators need to see the ambiguity, not just a flag.
- Peer sections are replaced by a short **"Why this venue isn't league-ranked yet"** block with a one-action unblock path ("disambiguate FHRS records", "add a TripAdvisor listing", "await next FSA inspection to lift evidence above threshold").
- Financial Impact section is either:
  - rendered at **Low confidence** with a visible "directional estimate" caveat and smaller figures (the wide range this produces is part of the signal), **or**
  - suppressed entirely when Commercial Readiness is unavailable.

### 4.6 Profile-only-D specifics

- No score card. The slot is replaced by a **Profile Stub** card with venue identity (name, address, postcode, FSA rating if any, any distinction).
- No peer, financial, or action sections.
- A single section called "How to unlock full scoring" describes what evidence would move the venue out of D: typically, resolving entity match and / or getting one customer platform above 5 reviews.
- Evidence Appendix still renders — it is the point of the stub.

### 4.7 Closed specifics

- No score card. Top area shows the closure evidence (source: `business_status = CLOSED_PERMANENTLY` or `fsa_closed = true`) and the date observed.
- If a prior-month V4 snapshot exists and the closure is new, surface the last-known score in a "Last observed score before closure" footnote — but do not present it as live.
- No action tracker; no financial impact; no peer sections.
- Evidence Appendix may render for audit.

### 4.8 Temporary closure specifics

- Handled in the `Rankable-*` / `Directional-C` modes with an extra header flag: "Temporarily closed — excluded from league tables until reopened."
- Score is preserved and shown (spec 7.4 row 2).
- Financial Impact section is either suppressed or rendered only as "covers at stake on reopening", with confidence ≤ Low.
- Action tracker may focus on "reopening checklist" items sourced from risk alerts and commercial readiness gaps; must not imply the venue is currently trading.

---

## 5. Core Report Structure

Every section below is either **mandatory** (M) or **conditional** (C). The generator renders in order. Sections that are suppressed in a given mode render nothing — not a stub heading. Builders consume only the `ReportInputs` dataclass from §2.5.

### 5.1 Executive Summary — M (all modes except Closed)

**Purpose.** The operator's answer to "what should I fix now?" in ≤ 200 words. Preserves the V3.4 actions-led lead.

**Evidence allowed:** top 3 recommendations with their dimension code (mapped to V4 components), confidence class, whether `league_table_eligible`, component scores. Deltas if prior snapshot exists.

**Must not imply:** that sentiment or review themes drove a specific action score; that a venue is a category leader unless `Rankable-A` and peer-top.

**Class variation:**
- Rankable-A / B: three priority actions + watch + do-not-prioritise.
- Directional-C: top action is typically "unblock to become rankable" (resolve entity, add platform).
- Profile-only-D / Closed: suppressed.

### 5.2 Financial Impact & Value at Stake — M (A/B), C (C), suppressed (D/Closed)

See §6 for the full discipline. Preserves the V3.4 "lead with the money" instinct but with explicit confidence labels.

### 5.3 Score, Confidence & Rankability Basis — M (all modes)

**Purpose.** A dedicated block that shows exactly which class the venue is in and why. This is new in V4; it replaces the V3.4 "How scores work" appendix as a front-of-report concern.

**Evidence:** `confidence_class`, `rankable`, `league_table_eligible`, `entity_match_status`, `source_family_summary`, and the first-order caveat from §4.3.

**Must not imply:** that confidence class is a quality judgement of the venue. It is an evidence judgement.

**Class variation:**
- Rankable-A / B: one-liner confirming class; short list of primary families present.
- Directional-C: the "why not ranked" explainer with reason and unblock path.
- Profile-only-D: the "how to unlock full scoring" block.
- Closed: closure evidence table.

### 5.4 Operational & Risk Alerts — M (all modes with reviews, else C)

**Purpose.** Surface legal / safety / reputational red flags from review-text scanning (existing `risk_detection.py`). Preserved wholesale from V3.4.

**Evidence allowed:** risk-phrase detections, up to 3 quoted review fragments per alert.

**Must not imply:** that risk detections affect the V4 score. They do not. They inform the operator and may inform the report's narrative caveats.

**Class variation:** same content in all modes where reviews exist. Profile-only-D: omitted. Closed: omitted unless reviews are part of the closure explanation.

### 5.5 Trust & Compliance — M (all modes where Trust available)

**Purpose.** V4-native replacement for the old "Trust dimension" and "Trust — Behind the Headline" sections. Preserves the FSA sub-score decomposition and Companies House business-health table from V3.4.

**Evidence allowed:** FSA headline rating (`r`), sub-scores (`sh`, `ss`, `sm`), inspection recency (`rd`), active Trust-related caps (`STALE-2Y`, `STALE-3Y`, `STALE-5Y`), Companies House penalties (`CH-1`…`CH-4`).

**Presentation:**
- Top: Trust & Compliance score (0–10) + "compliance, not food quality" framing line.
- Decomposition table (FHRS rating + hygiene / structural / management sub-scores + recency).
- Companies House row if any CH data is populated, explicitly labelled "business-viability risk signals" rather than "trust signals".
- Active cap callouts if present (e.g. "Trust capped at 7.0 — last inspected 812 days ago, FHRS ≥ 3"). These are drawn from `caps_applied[]`.

**Must not imply:** hygiene = food quality. Spec §3 of scoring explicitly forbids this framing.

**Class variation:**
- All Rankable + Directional: full section.
- Profile-only-D: reduced to just the FHRS headline if present.
- Closed: omitted; the closure notice stands alone.

### 5.6 Customer Validation — M (all modes where Customer available)

**Purpose.** V4-native replacement for the V3.4 "Experience" + "Visibility" dimensions as a *metadata* component. Preserves the public-rating lens but strips any implication that stars = quality.

**Evidence allowed:** Google / TripAdvisor / OpenTable (`raw`, `count`, `shrunk`, `weight` per platform); Customer Validation component score; any active low-review cap (spec §4.5).

**Presentation:**
- Component score line with framing: "public rating metadata; shrinkage applied to low-count evidence."
- Per-platform table: raw rating, count, Bayesian shrunk value, coverage weight.
- Explicit note where shrinkage materially pulled the score ("Google count 14 < n_cap; raw 4.8 shrunk to 3.92 using the platform prior").
- Trajectory / recent-movement narrative is **not** in this section. That lives in §5.13 (Profile Narrative).

**Must not imply:** that review text drove the score; that a 4.8 rating is a quality attestation; that volume = quality.

**Class variation:**
- Rankable-A / B: full section.
- Directional-C (thin reviews): section renders but the prose explicitly foregrounds the cap. No peer comparison inside this section.
- Profile-only-D: omitted.
- Closed: omitted.

### 5.7 Commercial Readiness / Demand Capture Audit — M (all modes where CR available)

**Purpose.** Consolidates the V4 Commercial Readiness component with the V3.4 Demand Capture Audit (7-dimension customer-journey check). The CR component answers "does the score see the booking path"; the demand capture audit answers "what is a real customer's journey like on the ground". Both are preserved.

**Evidence allowed:**
- Commercial Readiness component score + its four sub-signals (website, menu online, hours completeness, booking/contact path).
- Demand capture audit dimensions (Booking Friction, Menu Visibility, CTA Clarity, Photo Mix & Quality, Proposition Clarity, Mobile Usability, Promise vs Path).
- Any reservable-attribute signal if observed from Google.

**Presentation:**
- Component card at top (score + sub-signal checklist).
- Demand capture audit table below (7 rows, verdicts: Clear / Partial / Missing / Broken).
- Relationship line explicitly: "Commercial Readiness feeds the V4 score; Demand Capture Audit is a narrative extension that does not."

**Must not imply:** that demand-capture audit verdicts feed the score. They do not.

**Class variation:**
- Rankable-A / B: full.
- Directional-C: full but with caveat that scoring headline is not league-ranked.
- Profile-only-D: omitted.
- Closed: omitted.

### 5.8 Market Position — C (Rankable-A / B with league eligibility)

**Purpose.** Preserves the V3.4 three-ring peer analysis (5 mi local, 15 mi catchment, UK cohort) but scopes the peer pool to `Rankable-A ∪ Rankable-B` only.

**Evidence allowed:** peer-ring percentiles, rank within ring, peer mean and top, peer counts. Derived from `peer_benchmarking.py` with a V4-aware filter that excludes `Directional-C` / `Profile-only-D` from the denominator.

**Must not imply:** that `Directional-C` venues are peers (they are counted separately); that a venue leads the field without peer evidence to back it.

**Class variation:**
- Rankable-A / B with `league_table_eligible`: full.
- Rankable-* without `league_table_eligible` (stale hard cap, closed_temporarily, zero customer data): replaced by the "why not league-ranked" explainer.
- Directional-C / Profile-only-D / Closed: suppressed entirely.

### 5.9 Competitive Market Intelligence — C (Rankable-A / B)

**Purpose.** Preserves V3.4 competitor-read logic (competitive density, distinguishing features, market positioning). Reformulated to reference V4 components and confidence class instead of V3.4 dimensions.

**Evidence allowed:** peer counts in each ring, component-level gaps vs peer mean, distinction modifier comparisons, any conditional-block triggers (competitive density, compliance risk, visibility gap re-framed as Commercial Readiness gap).

**Must not imply:** that any V3.4 tier ranking is still authoritative. Peer language must use V4 components.

**Class variation:**
- Rankable-A / B: full, scoped to Rankable-* peer pool.
- Directional-C: replaced by a reduced "how peers compare — directional" note, without specific percentile claims.
- Profile-only-D / Closed: suppressed.

### 5.10 Management Priorities — M (A / B), reduced (C), suppressed (D/Closed)

**Purpose.** Preserves V3.4 ranked-priority actions with commercial consequence framing. Each priority is framed by the V4 component it targets, not by the old five dimensions.

**Evidence allowed:** recommendation engine output (`recs`), mapped to components (trust / customer / commercial / distinction). Action status (new, ongoing, resolved). Commercial consequence lines only where CR evidence supports a costed estimate (see §6).

**Must not imply:** that a recommendation will move the score by a specific amount; that sentiment-driven recommendations exist. Recommendations must cite observable evidence (missing menu, stale inspection, low Google count, absent phone), not review-text interpretations.

**Class variation:**
- Rankable-A / B: three priorities with commercial consequence.
- Directional-C: top priority is the unblock-to-rankable action; others follow.
- Profile-only-D / Closed: suppressed.

### 5.11 Watch List — M (A / B), C (C), suppressed (D / Closed)

**Purpose.** Preserved from V3.4 — lighter-touch items the operator should track without acting on this month.

**Evidence allowed:** second-tier items from the recommendation engine; early-warning signals from Monthly Movement deltas.

**Must not imply:** that watch items are cost-free. Preserve the V3.4 phrasing around monitoring without action.

### 5.12 What Not to Do This Month — M (A / B), C (C), suppressed (D / Closed)

**Purpose.** Preserved wholesale. Prevents the operator from chasing false levers.

**Evidence allowed:** V3.4 "do-not-prioritise" logic retuned to V4 components. A frequent item: "don't chase new reviews to lift the score — Customer Validation shrinkage dampens the effect until count is above n_cap / 2."

**Must not imply:** that any banned V4 input (photos, price level, social, convergence) would help the score. This section is also where the report teaches that explicitly.

### 5.13 Profile Narrative & Reputation Signals — M (where review text exists)

**Purpose.** The home for everything the V4 score does not use. Preserves "What This Venue Is Becoming Known For", Guest Segment Intelligence, Menu & Dish Intelligence, and review-text synthesis — relocated and explicitly labelled as **profile-only**.

**Evidence allowed:** aspect themes, segment intelligence, menu dish mentions, praise/criticism synthesis, trajectory narrative (improving/declining/stable), review-confidence tier (anecdotal / indicative / directional / established).

**Must not imply:** that any of this affected the V4 score. Every subsection carries a one-line header: "Narrative only — not a score input." See §7 guardrails.

**Class variation:**
- All Rankable: full when ≥ some minimum review count (configurable; default 5).
- Directional-C: renders with hedged language; "review evidence suggests …" rather than "guests consistently …".
- Profile-only-D / Closed: suppressed (except Closed may render a "last-known reputation signal" footnote if prior-month data exists).

### 5.14 Implementation Framework / Recommendation Tracker — M (A / B), reduced (C), suppressed (D / Closed)

**Purpose.** Preserved from V3.4. Tracks recommendation lifecycle (new / ongoing / stale / chronic), cost band, expected upside, target date, barrier category, evidence.

**Evidence allowed:** recommendation engine output, prior-month statuses, action cards.

**Must not imply:** that "expected upside" is guaranteed. All upside must cite the observable path it depends on ("if CR booking-path lands, ≈ 3.75 points of the 15% CR weight become recoverable").

**Class variation:**
- Rankable-A / B: full.
- Directional-C: shorter, anchored on unblock-to-rankable items.
- Others: suppressed.

### 5.15 Next-Month Monitoring Plan — M (A / B), C (C), suppressed (D / Closed)

**Purpose.** Preserved — external leading indicators to watch before the next report.

**Evidence allowed:** same as V3.4; now also recommends watching confidence-class change, any newly active caps, entity-resolution updates.

### 5.16 Data Basis / Coverage & Confidence — M (all modes)

**Purpose.** Replaces and upgrades the V3.4 three-layer evidence pyramid. Grounds every claim in the report in its data source.

**Evidence allowed:** `source_family_summary` (FSA / customer platforms / commercial / Companies House), review-text counts, confidence-class criteria reminder, any missing pieces flagged.

**Must not imply:** that cross-source agreement raises the score (convergence is removed in V4). May note descriptively that sources agree.

**Class variation:** always rendered. Content scales — for `Profile-only-D` this section is a large fraction of the output.

### 5.17 Evidence Appendix — M (all modes)

**Purpose.** Factual inventory of what data exists for this venue — FSA / Google / TripAdvisor / Companies House fields. Preserved wholesale from V3.4 as a "show your working" artefact.

**Evidence allowed:** raw signal dump with provenance. Nothing derived.

**Must not imply:** anything. It is a table of facts.

### 5.18 How the Score Was Formed — M (all modes except Closed where `rcs_v4_final is None`)

**Purpose.** The V4 replacement for "Appendix: How Scores Work". Renders the audit/decision trace plus the penalties and caps that fired.

See §9 for full rules.

---

## 6. Financial Impact & Value at Stake — Discipline

The V3.4 report placed Financial Impact near the top and used specific £ ranges drawn from price-level proxies. That instinct — "lead with the money" — is preserved, but the discipline changes. V4 financial claims must be disclosable; claims outside what the evidence supports must not appear.

### 6.1 When to render

| Mode | Section renders? | Default confidence |
|---|---|---|
| Rankable-A, `league_table_eligible` | Yes | Moderate – High |
| Rankable-B, `league_table_eligible` | Yes | Moderate |
| Rankable-B, thin CR (≥ 1 CR sub-signal missing) | Yes, with fallback wording | Low |
| Rankable-B without `league_table_eligible` (stale cap / temp closure / zero customer) | Yes with caveat OR suppress | Low or suppressed |
| Directional-C | Conditional — see §6.4 | Low |
| Profile-only-D | **Suppressed** | — |
| Closed | **Suppressed** | — |

### 6.2 What the section may claim

Allowed outputs:
- **Value at stake.** A range of monthly / annual revenue potentially recoverable from closing observed commercial-readiness gaps. Never a point estimate.
- **Cost band.** One of `< £200 / £200–£1,000 / £1,000–£5,000 / > £5,000` with the specific action that maps to that band.
- **Payback window.** One of `< 1 month / 1–3 months / 3–6 months / 6–12 months / > 12 months`.
- **Confidence level.** A mandatory tag on every figure, drawn from §6.3.
- A one-line caveat: "Ranges are directional. Exact figures require internal cover and spend data."

Nothing in this section may be presented as a precise number. `£3,247.50/month` is forbidden. `£400–£1,800/month` is the shape.

### 6.3 Confidence labels (mandatory)

Every figure or range carries a confidence tag. The tag is computed from the available evidence, not from writer preference.

| Label | Criteria | Render |
|---|---|---|
| **High** | Rankable-A; all three primary families present; observed phone and observed website; CR component score ≥ 7.0 | "High confidence — figures are directional but evidence is strong." |
| **Moderate** | Rankable-A or B; CR ≥ 6.0; at least website **or** phone observed (not inferred); customer validation with at least one platform at ≥ 30 reviews | "Moderate confidence — evidence supports the shape; exact figures require internal data." |
| **Low** | Rankable-B with thin CR; or Directional-C where rendered; or any case where CR components are mostly inferred | "Low confidence — indicative only. Treat figures as illustrative." |
| **Not available** | Profile-only-D, Closed, or CR component `available = false` | Section is suppressed rather than rendered with this label. |

### 6.4 Honest fallback wording

When robust estimation is not possible, the section must say so rather than producing figures anyway. Two fallback shapes:

1. **Thin evidence fallback** (Rankable-B / Directional-C with weak CR):

   > *Financial impact cannot be robustly estimated this month. Your Commercial Readiness evidence is thin (website inferred; no observed phone or booking-path signal), which is where most recoverable revenue shows up in the model. Once booking-path evidence lands — a published phone number, an observed reservable attribute, or a linked booking widget — the next report will include a Moderate-confidence estimate. Recommended action: publish a reachable phone number.*

2. **Directional-C fallback** where the headline class itself disqualifies the estimate:

   > *Financial impact is not rendered while this venue is classified Directional. The headline score is indicative, not league-ranked, so any £ figure here would carry the same uncertainty. See "Why this venue isn't league-ranked yet" above for the unblock path.*

### 6.5 What it must never imply

- That a specific recommendation will unlock a specific £ value with precision.
- That a 25%/15%/8% leakage rate applies to this venue — such rates exist in hospitality benchmarks but this report must not claim them as observed for this venue.
- That price-level (`gpl`) alone justifies a revenue projection. `gpl` is excluded from V4 scoring; using it as the sole basis for a commercial estimate re-introduces a forbidden score-driver by the back door.
- That Financial Impact figures are audited or contractual. They are directional estimates with the stated confidence tag.
- That closing the identified gap will raise the V4 score by a specific amount. The report may note which component a fix targets (e.g. "lifts CR from 5.0 to 7.5 when `phone` lands") but must not forecast the overall `rcs_v4_final` movement as a number.

### 6.6 Structural form

When rendered, the section is ordered:

1. One-sentence headline ("Approximately 3–30 covers per week at risk …").
2. A short table — covers, weekly revenue impact, monthly, annual — with `—` rather than a number in any cell the evidence cannot support.
3. The recommended action, its cost band, and its payback window.
4. The confidence label with the criteria that triggered it.
5. The one-line directional caveat.

This preserves the V3.4 shape (operators recognise it) and retrofits the discipline above. No other figures may appear.

---

## 7. Narrative Guardrails

This section is normative for every builder that produces prose. The QA layer (§10) enforces it.

### 7.1 Profile-only diagnostics may be discussed, never as score drivers

- Aspect themes, segment intelligence, menu intelligence, risk phrases, and demand-capture audit verdicts are diagnostic lenses the operator values. They are preserved and prominent. They do not feed the V4 score.
- Every section that surfaces one of these must carry a one-line tag: *"Narrative only — not a score input."* The tag appears once per section, not per bullet.
- Prose must never explain a V4 score movement by a narrative signal. Forbidden: "Customer Validation fell because of negative sentiment in recent reviews." Acceptable: "Customer Validation fell because the Google rating dropped from 4.6 to 4.3 across 412 reviews; review text evidence, which does not drive the score, is summarised in §5.13."

### 7.2 Review text is narrative-only

- The report may quote review text in the Profile Narrative and Review-by-Review appendix.
- The report may discuss themes, segments, and trajectories from review text.
- The report **must not** say or imply that review text, sentiment, or aspect scoring entered the V4 headline number. Not via phrasing like "the score reflects reviewer sentiment", not via cross-references that conflate the narrative with the score.
- The report must retain the V3.4 review-confidence tiers (anecdotal / indicative / directional / established) for narrative language gating — they bound how strongly review-text observations may be asserted regardless of the V4 class.

### 7.3 Directional-C and Profile-only-D require stronger caveats

- Directional-C: the "not league-ranked" banner repeats at the top of every commercial section (Financial Impact, Market Position, Competitive, Management Priorities). Not just once at the top of the report. Repetition is deliberate; it guards against operators reading a single section in isolation.
- Profile-only-D: the report is a profile stub. Any narrative that appears must be hedged to structural facts. No "leads the field" / "category leader" / "market position" language at all.
- Both classes must not use absolute commercial language ("will lose", "will recover") — use conditional ("may", "tends to").

### 7.4 Pre-cutover distribution numbers are not public copy

- The current Stratford trial distribution (1 Rankable-A, 181 Rankable-B, 27 Directional-C, 1 Profile-only-D, rankable mean 7.999, 56.0% ≥ 8.0, etc.) is a snapshot, not a published claim.
- These numbers appear in internal diagnostics (`stratford_v3_v4_distribution.json`, readiness memo, etc.).
- They must **not** appear hard-coded inside operator-report prose. Specifically forbidden in report templates:
  - "Only 0.5% of venues reach Rankable-A" / similar population framing.
  - "Most venues in Stratford are Rankable-B" / similar distribution claims.
  - "56% of rankable venues score ≥ 8.0" / similar calibration claims.
- If a report references peer population, it uses the *live* peer-benchmark numbers computed for that report, not a hard-coded sentence.

### 7.5 Public methodology page is out of scope for Stack B

- This spec defines the operator-facing report.
- `docs/DayDine-Scoring-Methodology.md` (and its HTML counterpart) is a separate concern gated on the data-coverage blockers in `docs/DayDine-V4-Readiness-For-Stack-B.md`.
- Stack B must not regenerate or rephrase public methodology content as a side effect of report work.
- Internal docs (`DayDine-V4-Report-Spec.md`, future `DayDine-V4-Report-Migration-Note.md`, `DayDine-V4-Report-QA-Guide.md`) are the Stack B surface; other docs are frozen.

### 7.6 Other forbidden phrasings (explicit)

| Forbidden | Why |
|---|---|
| "The score reflects …" (followed by any §2.3 item) | Implies banned input drove the score |
| "Cross-source convergence boosts the score" | Convergence removed in V4 |
| "Your photos / price level / place types are pulling your score up / down" | All are profile-only in V4 |
| "Delivery / takeaway / parking / wheelchair access is a positive signal" | Profile attributes, not score inputs |
| "Your Facebook / Instagram presence is helping visibility" | Social is not a score driver |
| "You are rated X of Y in Stratford" when not `league_table_eligible` | Violates §4.4 |
| "You are the category leader" when not `Rankable-A` | Requires A-class evidence |
| "Your score will rise by £N / X points if …" | No precise score-movement forecasts |
| "Industry benchmarks say you lose 8% of covers …" | Treats an external rate as observed-for-this-venue |

Builders must not produce these phrases. The QA layer (§10) blocks any that slip through.

---

## 8. Review Narrative Rules

Review text is preserved as a first-class narrative input — themes, segments, dish mentions, trajectories, risk detections all continue. It is where the report earns its operator-facing depth. But the relationship to the V4 score is explicit: **none**.

### 8.1 Where review text may appear

- **§5.4 Operational & Risk Alerts** — up to 3 quoted fragments per alert, anchored in the risk-phrase detection.
- **§5.13 Profile Narrative & Reputation Signals** — the full review synthesis: aspect themes, praise/criticism, trajectory, segment intelligence, menu intelligence, recent movement, narrative shifts.
- **Review-by-Review Summary + Full Review Text Appendix** — an appendix with the raw evidence.

It does not appear anywhere else. Specifically not inside §5.5, §5.6, §5.7, §5.10 (where it would blur into score-driver framing).

### 8.2 Evidence tiers — must be respected

The existing V3.4 review confidence tiers remain in force for how strongly review-derived claims may be phrased:

| Tier | Criteria | Allowed language |
|---|---|---|
| **Anecdotal** | < 5 reviews | "Early impressions suggest …"; "A handful of reviews mention …" |
| **Indicative** | 5–14 reviews | "Reviews point to …"; "Recent reviews mention …" |
| **Directional** | 15–49 reviews | "Review evidence is directional: …"; "Patterns across reviews suggest …" |
| **Established** | ≥ 50 reviews | "Reviews consistently note …"; "A clear pattern of …" |

The tier is derived from review-text count, not from the V4 class. But the V4 class imposes an additional ceiling: a `Directional-C` venue may not use "Established" language even if it has ≥ 50 reviews — because the overall confidence is already hedged at the class level. In that case, language drops one tier.

For `Profile-only-D`: review language tier collapses to Anecdotal at best, and usually the section is suppressed entirely.

### 8.3 No language implying sentiment drives score

- Forbidden: "Sentiment is pulling your score down."
- Forbidden: "Your aspect scores for food / service / ambience are weighing on the headline."
- Forbidden: "AI-detected risk flags cap your score."
- Acceptable: "The Customer Validation component reflects the 4.3 Google rating across 412 reviews. Separately, review text indicates a pattern of … (narrative only)."

Every subsection in §5.13 carries the "narrative only — not a score input" tag from §7.1.

### 8.4 No "customers consistently…" without threshold support

The V3.4 generator sometimes produced "guests consistently say …" against very thin review sets. V4 forbids this:

- "Consistently" / "routinely" / "repeatedly" require the Established tier (≥ 50 reviews).
- "Often" / "frequently" require Directional (≥ 15).
- "Some reviews note" / "a handful mention" are the default for Indicative and Anecdotal.
- When `Directional-C` demotes the tier (§8.2), the strongest language the venue can use is Directional regardless of review count.

### 8.5 Handling zero-review venues

- Do not synthesise reputation prose from structural signals alone. The V3.4 Lambs sample (*"well-established British dining venue with a strong public reputation"* on 0 deeply-analysed reviews) is the failure case.
- When review text is absent: §5.13 renders a short explicit block: "No review text is available for narrative analysis this month. The aggregate public rating (Customer Validation component, §5.6) is the reputation signal. Review-text narrative will be possible once [X] reviews have been collected."
- No trajectories, no segment reads, no theme prose without text to ground them.

### 8.6 Quoting reviews

- Quotes appear in Operational & Risk Alerts, Profile Narrative, and the Review-by-Review Appendix.
- Each quote must carry its source (google / tripadvisor), its rating, and its date (when dated).
- Quotes are displayed verbatim with no silent editing; elisions are marked "[…]".
- Reviewer names are shown only if they are already public on the source platform; no additional PII is introduced.
- Owner-response text is filtered out before quoting (the existing V3.4 filter stays).

### 8.7 Aspect themes — scope

The aspect taxonomy (food_quality, service, ambience, value, speed, cleanliness, safety, booking) is preserved from V3.4. Aspect scores are **not** rendered as numbers in V4 reports (that was the V3.4 error that made them look score-driving). Aspect findings are rendered as textual themes only: "Service receives consistently strong mentions"; "Value is flagged as mixed — some reviews commend portion size, others note pricing concerns."

Numerical aspect scores may still be computed internally by `review_analysis.py` for trajectory / delta purposes, but they are not exposed in the rendered report.

### 8.8 Trajectories and deltas

- Month-over-month shifts in review themes remain a valued signal and appear in Profile Narrative → Recent Movement / Narrative Shifts.
- Trajectory claims ("improving", "declining", "stable") require at least Directional-tier evidence on both sides of the comparison.
- A trajectory cannot imply the V4 score is moving in the same direction unless the scoring engine's monthly delta confirms it separately. The report may state both ("Review-text themes shifted from mixed to positive; Customer Validation score unchanged across the window due to no material Google rating move") — two independent facts, not one fact dressed two ways.

---

## 9. Decision-Trace Usage

The V4 engine emits `audit.decision_trace[]` — a human-readable record of how the score was formed. The report surfaces this visibly but does not dump it.

### 9.1 Principle

The decision trace is **explanatory, not raw**. It gives the operator the shortest story that (a) justifies the score, (b) surfaces any caps or penalties that fired, and (c) grounds the confidence class. If the operator disputes a score, this section is where they can see why.

### 9.2 Placement

A dedicated block titled **"How the score was formed"** renders as §5.18. Near the end of the report, above the Evidence Appendix. Present in every mode except Closed (where there is no score to justify) and Profile-only-D without a computed score.

It is not in an appendix — it is part of the main body. The purpose is trust; burying it defeats the purpose. But the formatting is compact (§9.3).

### 9.3 Rendering shape

Two tight blocks.

**Block 1 — Component trace (from `audit.decision_trace`):**

```
TrustCompliance = 8.200    (r_norm ok, signals_used=5, recency=0.78)
CustomerValidation = 7.450 (google n=412 raw=4.3 shrunk=4.24 w=1.00;
                            tripadvisor n=58 raw=4.0 shrunk=3.88 w=0.39)
CommercialReadiness = 7.500 (web ✓, menu ✓, hours 1.0, booking ✗)
base = 7.742 → +distinction 0.120 → +CH penalties -0.300 → final = 7.562
class = Rankable-A (3 families · 12 signals · 470 reviews)
```

This is the engine's own trace, re-formatted for readability (line-wrapping, bullet alignment, arrows for the additive chain). Content stays verbatim — the report does not rewrite the engine's explanation.

**Block 2 — Penalties & caps (from `penalties_applied[]` and `caps_applied[]`):**

A small table, only rendered if either list is non-empty. Shape:

| Code | Effect | Reason |
|---|---|---|
| `CH-3` | −0.30 absolute | accounts_overdue_days = 142 |
| `STALE-2Y` | Trust soft cap 7.0 | days_since_rd = 812, r = 4 |

Every cap or penalty referenced in headline prose or component cards must show here. No cap fires silently.

### 9.4 What the block must include

- Component scores, with the same precision as the headline card.
- Base / adjusted / final chain, with every additive or multiplicative step the engine recorded.
- Confidence-class line with evidence summary (families / signals / reviews).
- Every entry from `penalties_applied[]` and `caps_applied[]`.
- `engine_version` and `computed_at` as a footer.

### 9.5 What the block must not include

- Speculative "if X changed, your score would be Y" projections. Those live in §5.14 (Implementation Framework) with their evidential caveats.
- Marketing language ("your score is ready for the top tier" etc.) — this block is audit copy, not sales copy.
- Any input from §2.3 (forbidden score drivers). If `FORBIDDEN_FIELDS` ever appear here the engine has been misconfigured — the QA layer (§10) must flag.
- Duplicate information that already appears in the headline card. The block may reference the headline card but not restate it.

### 9.6 Compact shape for Directional-C and Profile-only-D

- Directional-C: renders the full block but prefaces with "This score is Directional — see §5.3 for why. The trace below explains how the number was formed; it does not license a league-ranking interpretation."
- Profile-only-D (when the engine still computed a score internally, e.g. `final = 0.0`): block may render at engineer discretion as a compact three-line explanation of why the class is D, pulled from `source_family_summary` and `entity_match_status`. No component / penalty detail.
- Closed: block is suppressed — no score was published.

### 9.7 Operator-facing tone

Compact, factual, no hedging, one short lead-in sentence ("Your V4 score was formed as follows:"). The block exists for operators who want to challenge a result; it must answer the question *"why is it that number?"* in a single scroll.

---

## 10. QA and Validation

Every report generated in V4 mode goes through two layers of automated validation before it is written to disk. Both layers must pass for the report to be marked clean; failures are surfaced in the companion QA JSON (`*_qa.json`) so reviewers can fix content or templates deterministically.

### 10.1 Layer 1 — Structural validation (extends V3.4 `validate_report`)

Runs against the rendered markdown plus the `ReportInputs` payload. Checks:

- Every mandatory section for the current mode (§5) is present with non-empty content.
- Mandatory banners are rendered (class banner for Directional-C / Profile-only-D; closure banner; temporary-closure banner; single-platform caveat).
- Component cards render for every component where `available == true`; suppressed components render the "insufficient evidence" line rather than the number.
- `rcs_v4_final` is rendered to 3 dp where it is a float, or not rendered at all where it is `None`.
- Every code referenced in headline prose or component cards (`STALE-2Y`, `CH-3`, etc.) appears in the penalties / caps table in §5.18.
- Every cross-reference (`§5.6`, `§5.13`, etc.) resolves to an actual heading.
- JSON snapshot (`*_report_v4.json`) contains all fields declared in the V4 report schema (per §2).

### 10.2 Layer 2 — Narrative guardrail validation (new)

Runs against the rendered markdown only, using a rule engine. The ruleset below is normative. Each rule is a regex / pattern match with a severity; `error` means the report is blocked, `warn` means the report ships with a QA-JSON note.

**Banned score-driver language (error).** Matches any phrase that attributes the score to a §2.3 forbidden input:
- `"(score|rating).*(reflects|driven by|shaped by|caused by).*(sentiment|aspect|AI|photo|price level|social|convergence|delivery|takeaway|parking|wheelchair|Facebook|Instagram)"`.
- `"cross-source convergence.*(boost|uplift|premium)"`.
- `"(photos?|price level|place types|delivery|takeaway|parking|wheelchair) (is|are|helped|pulled) .* (score|rating)"`.

**V3-era tier framing (error).** Matches any residual V3.4 dimension vocabulary presented as a score driver:
- `"dimension (score|scorecard|dimension)"` where not in a V3.4-comparison appendix.
- `"(experience|visibility|trust|conversion|prestige) dimension"`.
- `"(Excellent|Generally Satisfactory|Improvement Necessary|Major Improvement|Urgent Improvement) band"` where the band is presented as the venue's label.
- `"DayDine Premium v3\\.[0-9]"` (watermark).

**Overclaiming about sentiment (error).**
- `"customers (consistently|routinely|repeatedly)"` where the review-text tier is below Established, or where the V4 class is Directional-C.
- `"sentiment.*(drives|affects|caps|lifts).*score"`.
- `"AI(-based)? (analysis|summary|summarisation)"` as input to the score (acceptable only as narrative disclosure of what was excluded).

**Directional-C / Profile-only-D handling (error).**
- Directional-C report without the class banner in the header → error.
- Directional-C report with `"#\\d+ of \\d+"` peer-rank claims → error.
- Directional-C report with Financial Impact rendered at Moderate or High confidence → error.
- Profile-only-D report with a `rcs_v4_final` figure in the headline → error.
- Profile-only-D report with peer / Financial Impact / Implementation sections rendered → error.
- Profile-only-D report without the "how to unlock full scoring" block → error.

**Closed handling (error).**
- Closed report showing `"0\\.0"` as the score → error (must show "no published score" or be absent).
- Closed report rendering any action tracker, peer section, or Financial Impact → error.
- Closed report without closure evidence in the header → error.

**Profile-only signals presented as score drivers (error).**
- Any text attributing a `rcs_v4_final` movement to a §2.3 input (covered above) also triggers here to cross-check.
- Any Implementation Framework action whose "expected upside" claims an `rcs_v4_final` movement of a specific magnitude → warn.

**Distribution number hard-coding (warn).**
- Any of the pre-cutover Stratford trial figures (1 Rankable-A, 181 Rankable-B, 27 Directional-C, 56.0% ≥ 8.0, 0.5% Rankable-A, etc.) appearing inside generated operator-facing prose → warn (§7.4).

**Consistency cross-checks (existing V3.4 checker, extended):**
- Number of priority actions claimed in the summary matches number rendered in §5.10.
- Peer rank numbers in the executive summary match those in §5.8.
- Class banner in the header matches `confidence_class` in the ReportInputs payload.

### 10.3 QA JSON artefact

The existing `*_qa.json` companion gains V4-specific fields:

```
{
  "engine_version": "v4.0.0",
  "report_mode": "Rankable-A" | "Rankable-B" | "Directional-C" | "Profile-only-D" | "Closed",
  "guardrail_check": {
    "run": true,
    "passed": true | false,
    "errors": [{"rule": "...", "match": "...", "location": "..."}],
    "warnings": [...]
  },
  "structural_check": {
    "mandatory_sections_present": true | false,
    "missing_sections": [...],
    "missing_banners": [...]
  },
  "consistency_check": { ... existing V3.4 shape ... }
}
```

Errors in either layer fail the run (exit non-zero). Warnings are preserved for human review. A report that fails validation must not be committed to `outputs/monthly/`.

### 10.4 Validation against sample set

Before Stack B declares a phase complete (see the implementation plan), the following sample venues must generate a clean report with no errors in either layer:

- Rankable-A: Vintner Wine Bar (503480).
- Rankable-B: Lambs (503316), Loxleys (502816), The Opposition (503481), Arrow Mill (503282).
- Directional-C (ambiguous entity): Soma (1847445) or The Tempest (1589295).
- Directional-C (thin reviews): a low-count venue from the current Stratford set.
- Profile-only-D: Digby's Events (1774610) — the current single D.
- Closed (synthetic, via `fsa_closed=true` on a picked record): a permanent-closure test case.
- Temporary closure (synthetic `business_status = CLOSED_TEMPORARILY`): a temp-closure test case.

This sample set covers every branch of the generator. Any new branch added later must land in this list.

### 10.5 Linting requirements

A CI lint step must be added to the scoring repo:
- Grep `operator_intelligence/` for any of `FORBIDDEN_FIELDS`, `sentiment_`, `aspect_`, `ai_summary`, `review_text` used as a score-driving path (i.e. consumed by a builder that renders into a component card, headline, or Implementation Framework upside). This mirrors the scoring-engine lint item (D-12 in the readiness memo).
- Failure blocks merge.

---

## 11. Section Preservation Map

The V3.4 report accumulated significant commercial investment. V4 preserves that investment wherever the section's function survives — only the scoring frame around it changes. This table is the explicit mapping.

| Previous section (V3.4) | Decision | V4 target section | Notes |
|---|---|---|---|
| Executive Summary | **Keep but rewrite** | §5.1 | Preserve actions-led, three-priority shape. Rewrite headline from "overall 6.5/10" to V4 score card + class banner. Strongest/weakest dimension line becomes "component availability + any active caps". Peer-position line gated on `league_table_eligible`. |
| Next 30 Days — Demand Forecast | **Keep as-is** | §5.4 (precedes risk alerts) | Event forecast is independent of V4. Generalisation beyond Stratford is separate work (event data module). |
| Financial Impact & Value at Stake | **Keep but rewrite** | §5.2 | Preserve front-of-report placement and commercial framing. Retrofit the discipline in §6 — confidence labels, honest fallback, no false precision, no hard-coded loss rates. |
| Operational & Risk Alerts | **Keep as-is** | §5.4 | Risk-phrase detection is spec-compatible. Preserve emoji severity. Update consequence language for V4 ("excluded from league tables while open investigation" rather than dimension caps). |
| Data Basis (three-layer pyramid) | **Keep but rewrite** | §5.16 | Preserve three-layer structure. Rewrite "independent sources corroborate" framing — this was an implicit convergence-uplift claim. Replace with V4 source-family summary + confidence-class explainer. |
| Monthly Movement Summary | **Keep** (field rename) | §5 (follows §5.16 or §5.1 depending on prior-month availability) | Delta logic portable. Swap V3.4 dimension deltas for V4 component deltas + distinction modifier delta + confidence-class change. |
| What This Venue Is Becoming Known For | **Merge** | §5.13 Profile Narrative | Folded into Profile Narrative & Reputation Signals. Preserve the prose shape but anchor claims in Customer Validation metadata + review text tiers (not "dimension synthesis"). Removes the "category leader" phrasing unless Rankable-A. |
| Guest Segment Intelligence | **Merge** | §5.13 Profile Narrative | Preserved wholesale as a profile-only sub-block. Attach the "narrative only" tag. |
| Management Priorities | **Keep but rewrite** | §5.10 | Preserve ranked three-priority shape + commercial consequence prose. Rewrite priority dimension codes from V3.4 five-dim to V4 three-component. Remove implicit score-movement forecasts. |
| Protect / Improve / Ignore | **Appendix only** | Appendix | Preserve as a strategic recap in an appendix. Decision thresholds were V3.4-calibrated; rebuild on V4 calibration before promoting back to main body. |
| Demand Capture Audit | **Keep** (merge into CR section) | §5.7 | Preserve the 7-dimension audit table wholesale. Merge with V4 Commercial Readiness component card so the operator sees both in one place. Add the explicit "audit verdicts do not feed the score" line. |
| Commercial Diagnosis (constraint model) | **Keep but rewrite** | §5.10 Management Priorities (commercial consequence framing) | Preserve the "primary constraint / secondary drag / false comfort" thinking. Retune thresholds to V4 components. |
| Review & Reputation Intelligence | **Keep but rewrite** | §5.13 Profile Narrative | Preserve the narrative / trajectory / segment / appendix shape. Retrofit §7 / §8 guardrails (no number-driven aspect scores; tier language gated by V4 class). |
| Menu & Dish Intelligence | **Keep** (field rename) | §5.13 Profile Narrative sub-block | Preserved wholesale. Annually rotate trends dict. Attach the "narrative only" tag. |
| Public Proof vs Operational Reality | **Keep but rewrite** | §5.7 (merged with CR + Demand Capture) | The V4-native framing is "Customer Validation (public) vs Commercial Readiness (operator-controllable)". Preserve the table comparing public-facing signals to operational ones. |
| Category & Peer Validation | **Keep but rewrite** | §5.9 | Preserve the category-comparison framing. Gate peer set on `Rankable-A ∪ Rankable-B` only. Add a "Directional-C peer note" sidebar where relevant. |
| Competitive Market Intelligence | **Keep but rewrite** | §5.9 | Preserve competitive-density, positioning, and conditional-block logic. Relabel V3.4 dimension gaps as V4 component gaps. |
| Market Position (3-ring peer analysis) | **Keep but rewrite** | §5.8 | Preserve 3-ring structure (5 mi / 15 mi / UK). Scope peer pool to Rankable-*. Render "why not league-ranked" when applicable. |
| Dimension Scorecard (table) | **Remove** | — | Remove entirely. Replaced by §4.2 V4 score card + §5.3 confidence/rankability basis. |
| Dimension-by-Dimension Diagnosis | **Remove** | — | Remove entirely. Replaced by the V4 per-component sections (§5.5, §5.6, §5.7). |
| Trust — Behind the Headline | **Keep but rewrite** | §5.5 | Preserve FSA decomposition + Companies House business-health block. Frame as the Trust & Compliance component detail. Remove "hygiene = food quality" implication. |
| Watch List | **Keep as-is** | §5.11 | Portable. |
| What Not to Do | **Keep as-is** | §5.12 | Portable. Add V4-specific items (e.g. "don't chase photo counts / reviews below count threshold to move score"). |
| Implementation Framework | **Keep** (field rename) | §5.14 | Preserved wholesale. Map `dimension` field from V3.4 dimensions to V4 components. Upside claims cite the component path, not a score delta. |
| Next-Month Monitoring Plan | **Keep as-is** | §5.15 | Portable. |
| Data Coverage & Confidence | **Keep but rewrite** | §5.16 (merged with Data Basis) | Preserve coverage framing. Replace V3.4 "signals per tier" language with V4 source-family summary + class criteria. |
| Evidence Appendix | **Keep as-is** | §5.17 | Factual inventory. Portable. |
| Review-by-Review Summary + Full Review Text Appendix | **Keep as-is** | Appendix (under §5.13) | Portable. |
| Appendix: How Scores Work | **Remove** | — | Remove entirely. Replaced by §5.18 "How the score was formed" (decision trace + penalties / caps). |
| — | **New** | §5.3 Score, Confidence & Rankability Basis | Front-of-report class + rankability block. |
| — | **New** | §5.18 How the Score Was Formed | Decision trace + penalties / caps table (§9). |
| — | **New (conditional)** | "Why this venue isn't league-ranked yet" | Directional-C replacement for peer sections (§4.5). |
| — | **New (conditional)** | "How to unlock full scoring" | Profile-only-D single-section block (§3.4). |

### 11.1 What is kept unchanged

Eight sections survive V4 without structural change, only field renames: Demand Forecast, Operational & Risk Alerts, Monthly Movement (structure), Watch List, What Not to Do, Next-Month Monitoring Plan, Evidence Appendix, Review-by-Review Summary. These represent the durable operator-facing value of the V3.4 report and must not be disturbed except to swap V3.4 dimension references for V4 component references where they appear.

### 11.2 What is remapped, not rebuilt

Eleven sections keep their commercial purpose but are re-seated on the V4 contract: Executive Summary, Financial Impact, Data Basis, Management Priorities, Review & Reputation Intelligence, Trust (Behind the Headline), Market Position, Category & Peer Validation, Competitive Market Intelligence, Implementation Framework, and the merged Public-vs-Reality / Demand Capture / Commercial Readiness block. These are the sections where V3.4 built lasting value and where rebuilding would be wasteful.

### 11.3 What is removed entirely

Three constructs disappear in V4:
- **Dimension Scorecard table** (the 5-dim / 4-headline table) — replaced by the 3-component V4 card.
- **Dimension-by-Dimension Diagnosis** (the per-dim narrative section) — replaced by the V4 component sections (§5.5 – §5.7).
- **"Appendix: How Scores Work" V3.4 boilerplate** — replaced by §5.18's decision-trace block.

### 11.4 What moves to appendix

Two constructs demote from main body to appendix pending V4 recalibration:
- **Protect / Improve / Ignore** — strategic framing; decision thresholds need V4 calibration work.
- **V3.4 comparison** (if any is shown to the operator during the cutover window) — an explicit appendix labelled "previous methodology" (only if a venue's V3.4 report is rendered alongside V4 during migration).

---

## 12. Stack B Constraints During Pre-Cutover Phase

Stack B (report redesign) is implemented before the public leaderboard cutover is complete. This section is the set of guardrails that keep the two workstreams separated until data coverage clears the cutover gate.

### 12.1 Reports may be redesigned now

- The V4 operator report may be built, generated, and used internally as soon as this spec is approved.
- Sample reports may be produced for every venue in the Stratford trial and reviewed internally.
- V4 report output files (`*_report_v4.md`, `*_report_v4.json`, `*_qa.json`) may be written to `outputs/monthly/` alongside the existing V3.4 outputs. Parallel emission is the expected state during migration.
- The V4 report generator may be wired into the existing monthly pipeline as an additional (not replacement) path.

### 12.2 Public leaderboard cutover remains separate

- Nothing in Stack B touches the public leaderboard. The frontend (`rankings.html`, `index.html`, `methodology.html`, `assets/rankings/*.json`) continues to read V3.4 outputs.
- The leaderboard cutover is blocked by the data-coverage items in `docs/DayDine-V4-Readiness-For-Stack-B.md` §F (Google enrichment pass, TripAdvisor pass, FSA slice expansion, duplicate-gpid disambiguation, post-enrichment recalibration). None of those are Stack B responsibilities.
- Stack B must not regenerate `assets/rankings/` JSON from V4 outputs. Those files stay V3.4 until cutover.

### 12.3 Public methodology page is not rewritten as final public truth

- `docs/DayDine-Scoring-Methodology.md` currently overclaims V4 as the current framework (flagged in the readiness memo §C.1 / §D).
- Stack B may author **internal** docs only: this spec, a future `DayDine-V4-Report-Migration-Note.md`, a `DayDine-V4-Report-QA-Guide.md`, and the existing scoring / readiness docs.
- Stack B **must not** rewrite `docs/DayDine-Scoring-Methodology.md` or `methodology.html` as if they were ready to publish as the final V4 public truth. That rewrite is gated on the same data-coverage items as the leaderboard cutover, plus the softening wording proposed in readiness memo §D.
- If a public-facing caveat is needed on the methodology page *before* cutover, use the wording suggested in readiness memo §D (transition-notice banner), not a full rewrite.

### 12.4 Score distribution numbers remain provisional

- Current Stratford trial numbers (1 Rankable-A, 181 Rankable-B, 27 Directional-C, 1 Profile-only-D, rankable mean 7.999, 56.0% ≥ 8.0, web coverage 68.6% all inferred, TA coverage 0.5%, phone coverage 0%) are a pre-cutover snapshot.
- These numbers will shift after:
  - The Google enrichment pass for phone / reservable / business_status.
  - The TripAdvisor collection pass.
  - The FSA slice augmentation.
  - The post-enrichment Customer Validation recalibration.
- **In internal diagnostics** (readiness memo, comparison docs, QA artefacts): numbers may be cited with the "April 2026 snapshot, pre-cutover" tag.
- **In generated operator reports**: numbers must be computed live from the payload at report-generation time. Hard-coded distribution claims inside report prose are a §10 guardrail violation.
- **In public methodology copy**: no numbers at all until cutover (readiness memo §D).

### 12.5 Legacy V3.4 parallel operation

- `rcs_scoring_stratford.py` (V3.4) continues to run on every scoring invocation per `docs/DayDine-V4-Migration-Note.md` §11.1.
- V3.4 outputs (`stratford_rcs_scores.csv`, `stratford_rcs_summary.json`, `stratford_rcs_report.md`) continue to be produced and committed.
- V3.4 operator reports under `outputs/monthly/*.md` may continue to be regenerated during the migration window if the V3.4 generator is invoked — Stack B does not delete the V3.4 code path.
- **Forbidden:** deleting the V3.4 scoring engine, the V3.4 report generator, or the V3.4 output files before cutover. That is a post-cutover cleanup task.

### 12.6 Recalibration dependency

- The Customer Validation calibration in `docs/DayDine-V4-Scoring-Comparison.md` is set against the pre-enrichment data.
- Stack B reports will use the current calibration; **Stack B is not responsible for recalibrating the V4 scoring engine.**
- When the data-coverage passes land, calibration re-runs; Stack B reports automatically reflect the new values without further redesign because the report renders whatever `rcs_v4_final` the engine emits.
- Stack B must not hard-code any calibration constant (priors, n_caps, gamma, thresholds) inside the report generator. All such values live in `rcs_scoring_v4.py`.

### 12.7 Sample-set constraint

- Sample V4 reports generated for review during Stack B must cover every class (per §10.4).
- Sample reports must be committed under a clearly-labelled internal path (e.g. `samples/v4/monthly/…`) — not inside `outputs/monthly/` where they would be mistaken for live operator output.
- Sample reports may not be shared with external operators until the QA sample set passes and an internal reviewer has signed off.

### 12.8 Exit condition from pre-cutover phase

Stack B's pre-cutover phase ends when:
1. All sections defined in §5 render cleanly for the full Stratford trial.
2. The §10.4 sample set passes both validation layers.
3. The internal docs (this spec, report-migration note, QA guide) are final.
4. The readiness memo's "Stack B phase exit status" section is marked complete.

Cutover to public-facing V4 is a separate decision with its own exit condition, documented in `docs/DayDine-V4-Readiness-For-Stack-B.md` §F. Stack B's completion is a *prerequisite* for public cutover but not equivalent to it.

---

*End of DayDine V4 Operator Report Specification. Feedback and proposed amendments go through the normal internal review route; treat this document as versioned once approved.*
