# V4 Readiness Memo — Stack B Decision Gate

*Authored April 2026. Branch: `claude/verify-v4-scoring-spec-L4Cjv`.*
*Scope: Stratford trial (210 establishments). Stack A = scoring engine,
data pipeline, entity resolution, calibration. Stack B = operator
report redesign (frontend cutover remains a separate workstream).*

> **Stack B outcome (April 2026):** the operator report redesign is
> structurally complete. The V4 report layer is built, tested, and
> documented. See `docs/DayDine-V4-Report-Handoff.md` for the
> authoritative handoff, the verbatim deferred-items list, and the
> per-use-case readiness breakdown. This memo stays the canonical
> record of what Stack A shipped; it does not rescope the deferred
> items Stack B recorded.

---

## Verdict (as issued pre-Stack-B)

**READY FOR STACK B WITH MINOR WARNINGS.** *(Stack B has since run
and is complete; see the handoff note above. This verdict is
retained for historical context.)*

V4 engine is spec-aligned, calibrated, and emitting a stable per-venue
schema. All Stack-A data wiring is in place. Stack B can start report
work today provided it follows the explicit assumptions in §E and
avoids the warnings in §B.

---

## A. Is V4 now ready for:

| Use case | Verdict |
|---|---|
| **Internal use only** (scoring, audit, analyst / engineering review) | **YES — cleared.** Engine is stable; comparison artifacts are reproducible; entity resolution is honest about unknowns. |
| **Operator-report redesign (Stack B)** | **YES with warnings.** Use the per-component scores, confidence class, rankability flags, penalty/cap list, and decision trace exactly as emitted. Do not assume Rankable-A population is meaningful yet. Do not present specific venue scores as final-calibration until the post-enrichment recalibration cycle runs. |
| **Public leaderboard cutover** | **NO.** Three data-coverage gaps remain that would be embarrassing in a consumer-facing surface: TripAdvisor coverage 0.5%, phone/booking 0%, 7 high-profile venues missing from the trial slice. See §B. |

---

## B. Remaining blockers

### B.1 Blockers for public cutover only

1. **TripAdvisor coverage is 0.5%** (`stratford_tripadvisor_coverage.json`).
   Only Vintner has live TA metadata, so Rankable-A is effectively a
   single-venue label. The code path is ready; needs a CI run of
   `collect_tripadvisor_apify.py` with `APIFY_TOKEN`. Target: ≥70% of
   the 195 eligible venues.
2. **Phone / reservable / business_status coverage is 0%**
   (`stratford_commercial_readiness_coverage.json`). Commercial
   Readiness is capped at 7.50/10 universally because the
   booking/contact sub-signal (25% of CR weight) is unfunded. Code
   path is ready; needs a CI run of `enrich_google_stratford.py` with
   `GOOGLE_PLACES_API_KEY` using the extended field mask. Target:
   Phone ≥ 70%, reservable ≥ 40%, business_status ≥ 95% (should be
   near-universal from Places API).
3. **7 high-profile named venues not in the 210-record FSA slice**
   (`data/entity_aliases.json` → `known_unresolved`): The Dirty Duck,
   The Rooftop Restaurant, The Golden Bee, Baraset Barn, Boston Tea
   Party, Osteria Da Gino, Grace & Savour. Code surfaces these as
   structured "not in trial dataset" responses so search doesn't
   silently return empty, but a consumer launch with the Dirty Duck
   absent would be unacceptable. Unblock: run
   `.github/scripts/augment_fsa_stratford.py` to pull all food
   business types for LA 320.
4. **4 duplicate-gpid ambiguous groups** covering 9 records. All
   currently sit at Directional-C. Either disambiguate manually
   (extend `data/entity_aliases.json`) or accept their Directional-C
   status permanently. Either outcome is acceptable, but the decision
   should land before cutover so consumer copy is consistent.
5. **Post-enrichment recalibration.** Current rankable top-half share
   is 56.0% (was 42.9% before the Commercial Readiness `web`
   enrichment). The 2026-04 calibration (prior 3.6 / n_cap 250 /
   gamma 1.2) was set against a CR stuck near 5.0; with CR now
   ranging 0–7.5 and the website sub-signal active, the headline has
   re-inflated. Another calibration sweep should run *after* phone
   and TA data land, not before.

### B.2 Not blockers for Stack B

None of B.1 blocks **report redesign** itself. They block **public
launch** of the report. Stack B can build templates, IA, and
narrative against today's data and refresh the data on live cutover.

### B.3 Residual code drift (low severity)

Carried forward from `DayDine-V4-Scoring-Comparison.md` → Spec Drift:

| ID | What | Severity |
|---|---|---|
| D-1 | `_fsa_sub_norm()` handles both 0-10 repo-normalised and raw 0-20 FSA inverse encodings via magnitude detection | Low; inline comment; behaviourally correct for current data |
| D-5 | CH dissolved + no FSA inspection in 12mo → remove clause not implemented (CH-1 3.0 cap still fires) | Low; benign until CH data lands |
| D-6 | OPERATIONAL + no FSA in 5yr cap at Rankable-B not implemented | Low; rare edge case |
| D-7 | `audit.input_snapshot_hash` not emitted | Low; cosmetic / reproducibility nice-to-have |
| D-8 | Decision-trace class line doesn't include "(N families, M signals, K reviews)" summary | Cosmetic |
| D-9 | `*_rcs_v4_summary.json` output file not produced (stdout summary only) | Cosmetic; Stack B can compute from `stratford_rcs_v4_scores.json` |
| D-11 | `compare_v3_v4.py` sorts by |Δscore| not |Δrank|; "removed-signal impact audit" approximated via reason tags | Cosmetic for Stack B |
| D-12 | CI lint for forbidden identifiers not added | Belt-and-braces; `_guard_forbidden` runtime check still active |

D-2 and D-3/D-4 are **fixed** — the two that mattered for engine
correctness. Everything in the table above can ship post-cutover.

---

## C. Are the docs currently ahead of reality?

Yes, in two places. Both need softening before any consumer-facing
publication, but not before Stack B starts.

### C.1 `docs/DayDine-Scoring-Methodology.md`

- Top banner says "V4 (current framework)". Reality: V4 is
  implemented and running in parallel; the public site, rankings
  JSON, and `stratford_rcs_report.md` still derive from V3.4.
- §12 "Current Coverage" cites "Mean score 7.85 across rankable
  venues." Post-CR-enrichment the number is now **mean 7.999
  / median 8.116 / stdev 0.788 across 182 rankable venues**. Needs
  refresh.
- §5 framing presents Rankable-A as a normal headline class. In the
  live trial it's a single-venue label. The wording is technically
  correct but reads as if A is common.

### C.2 `docs/DayDine-V4-Migration-Note.md`

- "Where we are" section says "V4 is implemented." True, but the
  reader needs the caveat that no downstream surface reads V4 yet.
  Add one line up top.
- "Deprecated from V3.4" heading reads as settled past-tense. Rename
  to "Removed from V4 scoring (still present in V3.4 engine and
  legacy outputs)". The concepts are not deprecated from the repo;
  they are removed from the V4 code path only.

### C.3 Everything else

- `DayDine-V4-Scoring-Spec.md` — accurate. Keep.
- `DayDine-V4-Scoring-Comparison.md` — accurate. Calibration decision
  section matches reality.
- `DayDine-TripAdvisor-Trial-Status.md` — accurate. Ends "partially
  cleared".
- `DayDine-Commercial-Readiness-Data-Status.md` — accurate. Ends
  "partially cleared".
- `DayDine-Entity-Resolution-Status.md` — accurate. Ends "sufficient
  for beta/internal trial".

---

## D. Should the public methodology page present V4 as current?

**Not yet. Revert to "parallel model / migration candidate" wording
until the three data-coverage blockers in §B.1 are cleared.**

Suggested rewrite for the top banner of
`docs/DayDine-Scoring-Methodology.md`:

> **Transition notice.** V4 is the next scoring framework and is
> implemented as a parallel model in the repository. The public
> ranking surface continues to use V3.4 until the data-coverage
> prerequisites (TripAdvisor collection, phone / booking enrichment,
> FSA slice expansion) are complete. Until then, anything on this
> page that is not labelled **V3.4 legacy** describes the V4
> behaviour that will ship after cutover, not the behaviour you see
> on the live site today.

This is safer for a publicly-readable methodology page and cleanly
segregates the "live" vs "committed" contracts.

Internal-facing docs (`DayDine-V4-Migration-Note.md`,
`DayDine-V4-Scoring-Spec.md`) can keep the stronger "V4 is
implemented" framing because the audience knows what that means.

---

## E. Assumptions Stack B may safely use

The following are **contract-level guarantees** from this Stack-A
finalisation. Stack B can rely on them.

### E.1 Engine output schema (`rcs_scoring_v4.py`, spec §10.1)

Each scored venue emits, via `V4Score.to_dict()`:

- `fhrsid`, `name`
- `components.trust_compliance.{score, available, signals_used}`
- `components.customer_validation.{score, available, platforms.{google,tripadvisor,opentable?}.{raw, count, shrunk, weight}}`
- `components.commercial_readiness.{score, available, signals_used}`
- `modifiers.distinction.{value, sources[]}`
- `penalties_applied[]`, `caps_applied[]` (each: `code, effect, reason`)
- `base_score`, `adjusted_score`, `rcs_v4_final` (Optional — None means "no score published" per spec §7.4)
- `confidence_class` ∈ `{Rankable-A, Rankable-B, Directional-C, Profile-only-D}`
- `rankable` (bool), `league_table_eligible` (bool)
- `source_family_summary` with fsa / customer_platforms / commercial / companies_house keys
- `entity_match_status` ∈ `{confirmed, probable, ambiguous, none}`
- `audit.engine_version = "v4.0.0"`, `audit.computed_at`, `audit.decision_trace[]`

The schema is stable. Don't build report code that expects fields
beyond this list; those are cosmetic drift items not yet landed.

### E.2 What V4 does NOT read (spec §6, §9, enforced by `FORBIDDEN_FIELDS`)

Stack B report narrative may show any of these on a profile page.
It must not present them as score inputs:

- Review text, AI summaries, aspect sentiment (food / service /
  ambience / value / cleanliness), sentiment scores, red flags
- Photo count, price level, place types (except non-food exclusion
  and cuisine labelling)
- Delivery, takeaway, parking, wheelchair, dog-friendly, outdoor
  seating
- Facebook / Instagram presence (only `web` is allowed)
- Cross-source convergence bonus / penalty (removed from V4)

### E.3 What V4 DOES read

Report narrative should match the score's actual dependencies:

- FSA: `r`, `sh`, `ss`, `sm`, `rd` (and `fsa_closed` if set).
- Customer platforms: `gr`/`grc`, `ta`/`trc`, `ot_rating`/`ot_count`.
- Commercial: `web`, `has_menu_online`, `goh`, `phone`/`tel`,
  `reservable`, `booking_url`, `reservation_url`.
- Closure: `business_status`, `fsa_closed`.
- Identity: `id`, `gpid`, `public_name`, `trading_names`,
  `alias_confidence`, `entity_match`, `entity_ambiguous`.
- Editorial modifier: Michelin (`michelin_type`, `has_michelin_mention`),
  AA (`aa_rosettes`).
- Companies House (when available): `company_status`,
  `accounts_overdue_days`, `director_changes_12mo`.

### E.4 Rankability contract

- **Rankable-A / Rankable-B** — default league table.
- **Directional-C** — separate "Directional" list with caveat.
  Includes: single-platform under §4.4 cap; ambiguous entity matches;
  thin-review venues per §4.5. Must not appear in "Top 10" style
  surfaces.
- **Profile-only-D** — profile page only. No score shown.
- **`rankable = False`** trumps class — e.g. permanent closure forces
  it off even when class is Rankable-A/B.
- **`rcs_v4_final = None`** means "no score published" (permanent
  closure, by spec §7.4). Render as "Closed" or equivalent, never as
  zero.

### E.5 Narrative language guidance

- Trust & Compliance (40%) is **compliance**, not food quality. Never
  render as "food quality" or "inspection quality".
- Customer Validation (45%) is **public rating metadata**. Bayesian
  shrinkage is already applied; reports should acknowledge low-count
  venues' scores are pulled toward the platform prior, not "trust the
  stars".
- Commercial Readiness (15%) is **can a guest find and book**, not
  food quality or venue quality. Label accordingly.
- Distinction modifier caps at +0.30; no other awards feed the score.
  Don't frame local press or tourism-board listings as score drivers.
- Convergence agreement is NOT a score bonus in V4. Stack B may show
  it as a descriptive fact on a profile but not as an uplift.

### E.6 Named-venue search contract

- Search keys: record `n`, `public_name`, all `trading_names`.
- If the query resolves to a record, use `public_name` for display;
  `n` is the raw FSA legal entity.
- If the query is in `known_unresolved`, render with the
  `known_unresolved.cause` explanation and the unblock path. Never
  silently return zero results for a known-absent venue.
- If the record has `entity_ambiguous = true`, surface that fact in
  the UI — the score is Directional-C for a reason.

### E.7 Numbers you may quote today

From the current (post-calibration, post-TA-consolidation,
post-CR-enrichment, post-entity-resolution) run:

| Metric | Value |
|---|---:|
| Total establishments | 210 |
| Rankable-A | 1 (Vintner — single-venue until TA pass) |
| Rankable-B | 181 |
| Directional-C | 27 |
| Profile-only-D | 1 |
| League-eligible | 182 |
| Rankable mean / median / stdev | 7.999 / 8.116 / 0.788 |
| Rankable ≥ 8.0 | 56.0% |
| Entity match classes | confirmed 200 / probable 1 / ambiguous 9 / none 0 |
| TA coverage | 0.5% of eligible |
| Web coverage | 68.6% (all inferred) |
| Phone / reservable / booking | 0% (pending API pass) |

These numbers will shift after the next enrichment + recalibration
cycle. Any public copy citing specific figures should be flagged
"April 2026 snapshot, pre-cutover" until then.

---

## F. Minimum remaining tasks before public launch

In order:

1. **CI enrichment pass** with `GOOGLE_PLACES_API_KEY`. Populates
   `phone`, `reservable`, `business_status`, observed `web_url`.
   Single run of `enrich_google_stratford.py → merge_enrichment.py`.
2. **CI TripAdvisor pass** with `APIFY_TOKEN`. Single run of
   `collect_tripadvisor_apify.py → consolidate_tripadvisor.py →
   merge_tripadvisor.py`. Target ≥70% TA coverage.
3. **FSA slice expansion** via `.github/scripts/augment_fsa_stratford.py`.
   Pulls all food business types for LA 320. Closes the 7 named-miss
   gap.
4. **Disambiguate the 4 duplicate-gpid groups** — extend
   `data/entity_aliases.json` with manual `entity_match_override`
   entries where a correct resolution is knowable, or accept
   Directional-C.
5. **Customer Validation recalibration sweep** on the enriched data
   (one more run of `calibrate_v4_customer.py`, re-apply winner,
   update `DayDine-V4-Scoring-Comparison.md`). Target: rankable ≥ 8.0
   share ≤ 45%.
6. **Soften methodology wording** per §D.
7. **Optional post-launch**: D-5, D-6, D-7, D-8, D-9, D-11, D-12 from
   §B.3. None block.

Items 1–5 are ops / data tasks. Stack B can proceed in parallel.

---

## G. Artifacts touched by this readiness pass

Regenerated by the full pipeline re-run at the top of this memo:

| File | Purpose |
|---|---|
| `stratford_rcs_v4_scores.csv` | Per-venue V4 row (rank, components, final, class, flags) |
| `stratford_rcs_v4_scores.json` | Full V4 per-venue records per spec §10.1 |
| `stratford_v3_v4_comparison.csv` | Side-by-side V3.4 vs V4 with reason tags |
| `stratford_v3_v4_distribution.json` | Class cross-tab + aggregate stats |
| `stratford_v3_v4_movers.json` | Top-20 risers / fallers / drops |
| `stratford_v3_v4_sanity.json` | Thin-evidence, newly-excluded, high-profile checks |
| `stratford_tripadvisor.json` | TripAdvisor side-input (consolidator output) |
| `stratford_tripadvisor_coverage.json` | TA match / unmatched / not-attempted stats |
| `stratford_commercial_readiness_coverage.json` | Per-signal coverage + CR bucket distribution |
| `stratford_entity_resolution_report.json` | Alias applications + duplicate-gpid groups + named-venue resolution table |
| `stratford_establishments.json` | Source of truth after merge / resolve passes |

All produced deterministically from `stratford_establishments.json` +
`stratford_menus.json` + `stratford_editorial.json` + the alias table.

---

## H. Contacts

| Topic | File |
|---|---|
| Engine | `rcs_scoring_v4.py` |
| Spec | `docs/DayDine-V4-Scoring-Spec.md` |
| Migration / deprecation | `docs/DayDine-V4-Migration-Note.md` |
| Calibration | `docs/DayDine-V4-Scoring-Comparison.md` |
| TripAdvisor pipeline | `docs/DayDine-TripAdvisor-Trial-Status.md` |
| Commercial Readiness data | `docs/DayDine-Commercial-Readiness-Data-Status.md` |
| Entity resolution | `docs/DayDine-Entity-Resolution-Status.md` |
| This memo | `docs/DayDine-V4-Readiness-For-Stack-B.md` |
