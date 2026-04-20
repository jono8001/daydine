# ADR-001: TripAdvisor deferral, Google Places as canonical entity resolver, and `coverage_status`

*Status:* Accepted, 2026-04-21.
*Deciders:* jono8001 (product); Claude Code (implementation).
*Scope of this ADR:* strategy-level; bounds what follow-up work is and
is not allowed to change in the scoring engine without superseding
this decision.

---

## 1. Context

The V4 Customer Validation component (spec §4) was designed to support
**multiple independent review platforms** (Google, TripAdvisor,
OpenTable). The Rankable-A class, which is the headline "high-trust,
publicly rankable" tier, requires `customer.platforms_count >= 2` — at
least two independent platforms must both carry evidence for a venue.

TripAdvisor collection for the Stratford trial has repeatedly failed
on the path we built (runs #7–11, documented in
`docs/DayDine-TripAdvisor-Blocker-Diagnosis.md`,
`docs/DayDine-TripAdvisor-Strategy-Decision.md`, and the run-by-run
commit history). Root causes have ranged from GitHub-hosted runner IPs
being blocked by TripAdvisor's bot-protection, through a succession of
Apify actor input-schema mismatches, to the current state where the
search actor silently returns zero results for real Stratford
restaurant queries. Each fix unblocked one class of failure and
surfaced the next.

At the same time, **Google Places enrichment is operationally stable**.
Every venue in the trial has a resolvable place ID, coordinates,
canonical name, and address; most also have a website URL and a phone
number.

This ADR records the decision to stop chasing TripAdvisor for the time
being, promote Google Places to the canonical entity-resolution layer,
and add an orthogonal eligibility flag that describes public-signal
completeness without falsely claiming multi-platform corroboration.

## 2. Decision

1. **TripAdvisor collection is deferred.** Scheduled execution is
   disabled on `.github/workflows/collect_reviews.yml`
   (`schedule:` block commented out with a pointer to this ADR). The
   workflow remains dispatchable via `workflow_dispatch` for manual
   experimentation. `collect_tripadvisor_apify.yml` was already
   dispatch-only and keeps its preflight tests + two-stage
   search/review pipeline so a future revival starts from a known-
   working code path.

2. **Google Places is the canonical entity-resolution layer.** The
   fields it provides for each venue:

   * canonical name (`n` / `placeInfo.name`)
   * full address (`a`)
   * `lat` / `lon` (via `gpid`)
   * Google place ID (`gpid`)
   * phone (`phone`)
   * website (`web_url`)

   These populate the Google enrichment path that already exists in
   `.github/scripts/enrich_google_stratford.py` +
   `.github/scripts/merge_enrichment.py`. This ADR does not add a new
   collection workflow; it reframes the existing one.

3. **No double-counting in Customer Validation.** Google is ONE
   platform in `PLATFORM_PRIORS` (keyed `"google"`, fields
   `("gr", "grc")`). The entity-resolution role of Google Places is
   a *different* use of the same upstream vendor: identity facts
   (place ID, coordinates, contact) do not enter the Customer
   Validation score. This preserves the source-independence semantic
   that Rankable-A relies on — two distinct review platforms still
   means two distinct review platforms, and Google counts once.

4. **`coverage_status` is introduced as an ORTHOGONAL eligibility
   flag.** Added to `V4Score` in `rcs_scoring_v4.py`. Three values:

   * `coverage-ready` — all three V4 components available (Trust,
     Customer, Commercial), entity match `confirmed` via Google
     Places, Commercial Readiness ≥ 2 of 4 sub-signals, Trust ≥ 4
     of 5 sub-signals, at least one customer platform with ≥ 30
     reviews, not dissolved, not permanently closed. These are the
     venues that would promote to Rankable-A the moment a second
     independent review platform (TripAdvisor, OpenTable, Resy)
     populates.
   * `coverage-partial` — at least one gate unmet but at least one
     component is available.
   * `coverage-absent` — no component available, or entity match is
     `none`. Aligns with the Profile-only-D rationale.

   Thresholds match what Rankable-A itself requires *minus* the
   multi-platform gate. Raising them would make the flag stricter
   than Rankable-A (dishonest); lowering them would let venues
   through that Rankable-A wouldn't accept (also dishonest). The
   anchor is deliberate.

5. **Rankable-A/B/C/D semantics are preserved verbatim.**
   `classify_confidence`, `apply_low_review_cap`, and
   `rankable_flags` are unchanged. The 2026-04-21 re-score confirms:

   | Class | Before pivot | After pivot | Δ |
   |---|---:|---:|---:|
   | Rankable-A | 0 | 0 | — |
   | Rankable-B | 190 | 190 | — |
   | Directional-C | 17 | 17 | — |
   | Profile-only-D | 1 | 1 | — |

   `rcs_v4_final`, `base_score`, and `adjusted_score` are
   bit-identical for every venue. `coverage_status` is an additive
   field in the JSON output only.

## 3. What changed in scoring semantics

**Nothing.**

* Weights (40 / 45 / 15) — unchanged.
* Customer Validation platform priors — unchanged.
* Penalties and caps — unchanged.
* Classification thresholds — unchanged.
* Rankable-A still requires `customer.platforms_count >= 2`.
  Rankable-A is still empty today because no venue has two
  populated review platforms.

The only engine change is an orthogonal flag on the output
record. Three new unit tests in `tests/test_coverage_status.py`
guard the invariant explicitly — a single-platform
`coverage-ready` venue must stay Rankable-B, never promote to
Rankable-A.

## 4. Alternatives considered

**A. Rename Rankable-B → "Rankable-A single-source" or similar.**
Rejected. Rankable-A carries a specific corroboration claim in the
spec and in any operator-facing surface that already references it.
Renaming would either confuse readers or quietly weaken the claim.

**B. Drop the multi-platform gate and let Google alone qualify for
Rankable-A.** Rejected. That would double-count the Google ecosystem
(Google Places + Google ratings = one vendor) and remove the
convergence-check the spec relies on.

**C. Count Google Places entity resolution as a second "platform".**
Rejected. Entity resolution is identity, not opinion. An opinion
signal is what the second-platform gate is checking for. Calling a
verified place ID a "review platform" would be false on its face.

**D. Keep chasing TripAdvisor through further shape fixes.**
Rejected for now. Every fix has unblocked one class of failure and
revealed the next. At this point the cumulative signal is that the
failure mode is the actor + the data, not a single config issue, and
the opportunity cost of continuing exceeds the expected yield. The
two-stage Apify pipeline remains in place for when someone wants to
revive.

**E. Swap in an alternative review platform (OpenTable, Resy, Yelp
UK).** Not yet. The V4 spec lists `opentable` in `PLATFORM_PRIORS`
already; this is the natural revival path. The collector for it
doesn't exist yet and building it is a separate decision.

## 5. Conditions that would justify reviving TripAdvisor

Any of the following would trigger a follow-up ADR to revert the
deferral:

1. **TripAdvisor opens a first-party Content API with restaurant
   coverage for UK localities.** Last audit (2026-04, captured in
   `docs/DayDine-TripAdvisor-Strategy-Decision.md`) showed the
   public Content API is approval-gated and slow. If that changes, a
   legally clean path supersedes this deferral.

2. **Apify publishes (or we commission) an actor that reliably
   resolves UK-locality restaurant queries to review URLs**, i.e.
   ≥ 80% of the Stratford trial's `Rankable-B + coverage-ready`
   set gets a match. Current actors return 0 results per venue on
   the queries we've tried.

3. **A self-hosted or residential-IP runner is provisioned**, and the
   ToS + ops review clears. This ADR does not bless running the
   HTML scraper from a residential IP; any such change needs its own
   decision.

4. **The V4 model calibration changes** such that single-platform
   corroboration (Rankable-B + coverage-ready) is no longer the
   limiting factor for cutover. In that case the TA signal becomes
   nice-to-have rather than blocker.

None of these are blocking the current trial. `coverage_status`
surfaces the operational state honestly, so any downstream surface
(operator report, public rankings, internal dashboard) can display
"184 venues meet our single-platform quality bar pending multi-
platform corroboration" without claiming corroboration we don't
have.

## 6. Consequences

**Positive.**

* Honest labelling. Rankable-A continues to mean what the spec said
  it means.
* Operational clarity. `coverage_status` tells an operator which
  venues are "ready to promote when a second platform lands" vs
  which ones have gaps elsewhere.
* No wasted runner minutes on a known-blocked path.
* The two-stage TA pipeline is preserved intact, so revival is a
  workflow-dispatch away.

**Negative / risk.**

* `Rankable-A = 0` on the cutover dataset. If any downstream surface
  treats Rankable-A as the display gate, it will be empty. The
  operator report (V4) handles this correctly (it renders the
  Rankable-B path). Any future public leaderboard must ALSO handle
  it before cutover, or risk an empty page. This is explicitly
  flagged as a cutover-precondition in the broader cutover plan —
  not a regression introduced by this ADR.
* Coverage-status thresholds are anchored to the current
  Rankable-A gate. If the spec's Rankable-A gate ever moves,
  `compute_coverage_status` must move with it. A test in
  `tests/test_coverage_status.py` ties the semantic link
  explicitly.
* **Opportunity cost.** Every day TA stays deferred is a day venues
  with strong single-platform evidence cannot display as
  Rankable-A, even if a downstream consumer would accept them. The
  decision accepts this cost as smaller than the cost of continuing
  to chase TA with no stable convergence.

## 7. Files changed in this decision

* `.github/workflows/collect_reviews.yml` — schedule commented out;
  workflow_dispatch preserved; pointer to this ADR.
* `rcs_scoring_v4.py` — new `coverage_status` field on `V4Score`;
  new `compute_coverage_status` function; wired into `score_venue`
  and `to_dict`. No change to `classify_confidence`,
  `apply_low_review_cap`, `rankable_flags`, weights, priors,
  penalties, or caps.
* `tests/test_coverage_status.py` — 15 new tests; three explicit
  regression guards preserving Rankable-A/B semantics.
* `stratford_rcs_v4_scores.json` — re-scored; emits
  `coverage_status` alongside existing fields. Distribution per
  §2.5.
* `stratford_rcs_v4_scores.csv` — unchanged structurally (the CSV
  writer did not previously include `confidence_class`'s orthogonal
  fields; CSV consumers that want `coverage_status` should read the
  JSON).
* `docs/ADR-001-TripAdvisor-Deferral.md` — this file.

## 8. Superseded by

None (2026-04-21). To supersede, write ADR-002 that references this
ADR by number and documents the trigger condition from §5 that was
met.
