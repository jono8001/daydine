# DayDine V4 Operator Report — Handoff Note

*Authored April 2026. Branch: `claude/verify-v4-scoring-spec-L4Cjv`.*
*Stack B (operator report redesign) handoff to subsequent engineers.*
*Internal document. Not a public-facing surface.*

> **Scope reminder.** This note documents what Stack B delivered and
> what the next engineer needs to know. It does not describe the
> public leaderboard, the public methodology page, or any consumer
> surface. Those are gated on separate cutover work — see §5 below.

---

## 1. What Stack B completed

Stack B delivered an operator-report layer that is built entirely on
the V4 scoring contract. The work landed in four commits on the
current verification branch:

1. **V4 report specification** — `docs/DayDine-V4-Report-Spec.md`
   (1044 lines). Twelve numbered sections covering purpose, inputs,
   report modes, headline logic, section-by-section structure,
   Financial Impact discipline, narrative guardrails, review-narrative
   rules, decision-trace usage, QA and validation, section
   preservation map, and migration constraints.
2. **Report data model, spec validator, and generator** —
   `operator_intelligence/v4_adapter.py`, `v4_report_spec.py`,
   `v4_wording.py`, `v4_report_generator.py`, and the new
   `v4_peer_benchmarks.py` (added in the post-fix pass). Five
   rendering modes orchestrated cleanly: `rankable_a`,
   `rankable_b`, `directional_c`, `profile_only_d`, `closed`, plus
   `temp_closed` as a Rankable variant with a banner.
3. **Guardrail test suite** —
   `tests/test_v4_report_guardrails.py` (24 tests; runs via
   `python -m tests.test_v4_report_guardrails`; 0 failures).
4. **Sample set + assessment** — seven canonical samples under
   `samples/v4/monthly/` covering every mode, plus the assessment
   memo at `docs/DayDine-V4-Report-Samples-Assessment.md` with a
   §10 post-fix pass recording every critical fix and every
   intentionally deferred item.

Summary: the structural surface of the V4 operator report is
complete, tested, and documented. It is ready for internal use today
and for a supervised pilot once the recommendations engine is plumbed
(see §3 and §6).

---

## 2. What was preserved from the previous V3.4 report

The user brief explicitly asked that the commercially strong V3.4
report shell be preserved, not discarded. That rule was respected.
The V3.4 generator, spec, and builder tree (~6000 lines across
`operator_intelligence/report_generator.py`,
`operator_intelligence/report_spec.py`,
`operator_intelligence/builders/`) remains untouched and continues
to run in parallel.

Sections preserved intact (field rename only — no structural change):

| Section | Purpose |
|---|---|
| Executive Summary | Actions-led lead-in, three priorities, watch, do-not-prioritise |
| Next 30 Days — Demand Forecast | Seasonal / event context (bank holidays, RSC calendar, school terms) |
| Operational & Risk Alerts | Red-flag detection from review text; narrative only in V4 |
| Monthly Movement Summary | Month-over-month delta context |
| Watch List | Secondary items to monitor without acting on |
| What Not to Do This Month | Blocks of misdirected spend |
| Next-Month Monitoring Plan | Leading indicators for next period |
| Evidence Appendix | Factual inventory of observable data |
| Review-by-Review Summary / Full Review Text Appendix | Narrative only |
| Menu & Dish Intelligence | Narrative only |
| Guest Segment Intelligence | Narrative only |
| Implementation Framework | Recommendation lifecycle tracking |

Sections remapped but preserved in purpose (rewritten around V4
components instead of the V3.4 five-dimension taxonomy):

| Section | V3.4 framing | V4 framing |
|---|---|---|
| Financial Impact & Value at Stake | `gpl`-driven revenue projection, no confidence label | Confidence-labelled (High / Moderate / Low / fallback); CR-score-driven sizing; review-volume scaled; `gpl` demoted to ±25% weak prior |
| Trust — Behind the Headline | "Trust dimension" narrative | Trust & Compliance component card; FHRS decomposition; explicit "compliance, not food quality" framing |
| Commercial Diagnosis / Dimension Diagnosis | Per-dimension assessment | Component-by-component diagnosis (Trust / Customer Validation / Commercial Readiness) |
| Category & Peer Validation / Market Position / Competitive Market Intelligence | 3-ring peer rings against the whole V3.4 pool | Same 3-ring shape; peer pool scoped to `Rankable-A ∪ Rankable-B` only (`operator_intelligence/v4_peer_benchmarks.py`) |
| What This Venue Is Becoming Known For / Protect-Improve-Ignore | Identity synthesis from 5 dims | Folded into "Profile Narrative & Reputation Signals"; class-demoted review-tier gates the language |
| Demand Capture Audit | Outside-in 7-dimension check | Merged under Commercial Readiness / Demand Capture Audit with explicit "audit verdicts do not feed the score" caveat |

Sections removed entirely:

| Section | Why |
|---|---|
| Dimension Scorecard table | Replaced by the V4 score card (3 components + distinction) |
| Dimension-by-Dimension Diagnosis | Replaced by V4 per-component sections |
| "Appendix: How Scores Work" V3.4 boilerplate | Replaced by "How the Score Was Formed" — compact decision trace with penalty explanations and collapsible raw-trace block |

Sections added under V4:

- **Score, Confidence & Rankability Basis** — front-of-report block
  that shows class, rankable flag, league-eligibility, entity-match
  status, and source-family summary.
- **Why this venue isn't league-ranked yet** — Directional-C only;
  replaces the peer sections with an explicit reason + unblock path.
- **How to unlock full scoring** — Profile-only-D only; narrates the
  D → Directional-C → Rankable-B ladder.
- **How the Score Was Formed** — decision-trace summary + penalty
  explanations + collapsible raw trace.

---

## 3. What was rewritten around V4

Five things were rebuilt from the ground up on the V4 contract:

1. **Mode branching.** Every report is one of five shapes.
   `rankable_a` / `rankable_b` / `temp_closed` render the full 18-H2
   shell. `directional_c` replaces peer sections with an explainer
   and keeps Watch List / WNTD / Monitoring as Conditional (per spec
   §5.11/§5.12/§5.15). `profile_only_d` collapses to a 5-section
   stub. `closed` renders as a 3-section closure notice with no score
   and no action tracker.
2. **Input allow-list.** `operator_intelligence/v4_adapter.py` has a
   `FORBIDDEN_SCORE_DRIVERS` frozenset mirroring the scoring engine's
   `FORBIDDEN_FIELDS`. Any venue record carrying sentiment / aspect /
   AI summary / review text fields on its score-driving surface
   raises a `ForbiddenFieldError` at adapter construction.
3. **Closure defensive override.** The adapter normalises
   `rankable` / `league_table_eligible` / `rcs_v4_final` whenever
   `fsa_closed=True` or `business_status` indicates a closure, so a
   sample runner that doesn't re-score a synthetic fixture cannot
   leak `league_table_eligible=True` for a closed venue.
4. **Financial Impact discipline.** The section now renders one of
   three paths:
   - **Canonical fallback wording** for Directional-C (no £ figures)
     and for any state where Commercial Readiness is unavailable.
   - **Thin-evidence fallback** for Rankable-* venues whose CR
     evidence is inferred rather than observed.
   - **Full render** only when confidence is High or Moderate, with
     mandatory confidence label, cost band, payback window, and an
     evidence-grounded £ range derived from the CR score and review
     volume (`gpl` kept as a ±25% weak prior only, never the
     anchor).
5. **Guardrail QA.** Two-layer validation in
   `operator_intelligence/v4_report_spec.py` (17 regex rules across
   8 concern groups; class-scoped content rules; Financial Impact
   discipline). Failing reports are blocked at the QA step; warnings
   surface in `*_qa.json`. The 24-test suite exercises every rule.

---

## 4. What remains deferred (carried verbatim from the samples assessment)

These items are **not fixed** by Stack B. They are listed exactly as
recorded in `docs/DayDine-V4-Report-Samples-Assessment.md` §10.2. Do
not treat any of them as resolved; re-open them explicitly when taking
the work on.

| Item | Reason |
|---|---|
| Wire full V3.4 recommendations engine into the sample runner | The V3.4 engine requires the V3.4 scorecard pipeline. A thin V4 adapter is a separate piece of work (§6.2 item 7 of the samples assessment) and belongs with Stack B6 report content, not Stack B5 report structure. Management Priorities / Watch List / WNTD / Implementation Framework render thin but correctly for now. |
| Remove `_dimension_to_component` shim | Lives as long as the V3.4 recs engine does; retiring it depends on the item above. |
| V4-aware demand-capture-audit builder | Current shim passes a V3.4-style scorecard stub; the audit itself is spec-compatible (profile-only). Cosmetic refactor. |
| Penalty-explanation registry | Plain-English entries live in `v4_wording.penalty_explanation`; new codes won't auto-populate. Small; deferred until the next engine change. |
| CI integration of the guardrail test suite | Not a report-layer change; should land when CI is next touched. |
| Financial Impact range-width tolerance check | Narrow ranges at "Moderate" confidence are not currently flagged. Low priority; scoped post-rollout. |
| Segment-intelligence class demotion (§6.2 item 10) | Segment prose does not currently apply the review-tier ceiling. Requires touching `segment_analysis` consumer path; deferred so this pass does not touch narrative builders. |

These items do not block internal use. They may block pilot and will
block commercial publication — see §7 for the readiness breakdown.

---

## 5. Frontend and public methodology work — explicitly deferred

Nothing Stack B produced is intended for a public-facing surface. The
following paths are **out of scope** and must not be touched as a
side effect of report work:

- `rankings.html`, `index.html`, `search.html`, `methodology.html` —
  public pages. Continue to read V3.4 outputs.
- `assets/rankings/*.json` — public rankings data. Continue to be
  regenerated from V3.4.
- `outputs/monthly/*.md` — current live V3.4 operator reports. V4
  outputs write to `samples/v4/monthly/` (and eventually
  `outputs/v4/monthly/`) during migration, never to
  `outputs/monthly/`.
- `docs/DayDine-Scoring-Methodology.md` — softened in this pass but
  deliberately not rewritten as final V4 public truth. See readiness
  memo §C.1 and §D.

The methodology page top banner was updated in this pass to make the
provisional status explicit (V4 labelled "next framework, implemented
in parallel" rather than "current framework"; the Stratford coverage
snapshot tagged as April 2026 pre-cutover). No further public-facing
changes were made.

---

## 6. Assumptions the next engineer should use

If the next engineer is working on Stack B6 (report content / recs
engine integration) or on a public cutover:

### 6.1 Contract-stable facts

1. `operator_intelligence.v4_adapter.ReportInputs` is the only
   dataclass builders should consume. Never pass the raw venue
   record, raw V4 dict, or raw scorecard around. Add fields to
   `ReportInputs` rather than dict passthroughs.
2. `operator_intelligence.v4_report_generator.generate_v4_monthly_report`
   is the entry point. It returns `(report_text, qa_dict)`. No
   builder should be called directly from outside the module.
3. Every section renderer is a plain `_render_<section>(out, inputs)`
   function. Orchestrators pick which ones to call per mode.
4. Class banner, class gating, and closure defensive overrides live
   in `operator_intelligence.v4_adapter.build_report_inputs`. Do not
   reimplement them in individual builders.
5. The allow-list check (`FORBIDDEN_SCORE_DRIVERS`) is the source of
   truth for what cannot enter the report as a score driver. Mirror
   any additions in `rcs_scoring_v4.FORBIDDEN_FIELDS`.
6. Guardrail tests in `tests/test_v4_report_guardrails.py` are a
   contract. When you add a new rule, add a positive and a negative
   test for it. When you change a rule, update the existing test.

### 6.2 Design conventions to follow

- **Narrative tag everywhere.** Every section that consumes review
  text / aspect themes / segment signals / menu intelligence /
  demand-capture verdicts must carry a single-line
  "narrative only — not a score input" marker. Do not bury it.
- **Hedge by class.** Use `v4_wording.review_opener(tier)` and
  `v4_wording.frequency_qualifier(tier)` rather than inlining
  "customers consistently …". The helpers respect the class-demoted
  tier automatically.
- **Peer claims require league eligibility.** Do not render any
  `#N of M` without `league_table_eligible = True`. The V4 peer
  benchmarks module already scopes the denominator to Rankable-* by
  design.
- **Financial figures require a range and a confidence label.** The
  QA layer blocks both a bare precise £ figure and a section that
  renders figures without a confidence tag / cost band / payback.
- **Closure states trump class.** A venue that is permanently closed
  is not "a Rankable-B venue that happens to be closed"; it is a
  closure notice. The adapter already enforces this; do not
  re-derive rankability anywhere downstream.

### 6.3 Things not to assume

- Do not assume `peer_benchmarks` is populated. When it is not, the
  Market Position section renders a short "not yet computed" note.
  The sample runner now wires this via
  `v4_peer_benchmarks.compute_v4_peer_benchmarks`; production wiring
  is the next engineer's concern.
- Do not assume `recommendations` is populated. Management
  Priorities / Watch List / WNTD / Implementation Framework render
  thin when it's None — correctly, not catastrophically. Wiring the
  V3.4 recs engine behind a V4 adapter is part of Stack B6.
- Do not assume review text exists. Profile Narrative renders a
  short "no review text available" block when it doesn't.
- Do not assume component availability. Each component card has an
  "insufficient evidence" path; do not add sections that crash on
  `component.available = False`.

---

## 7. Known limitations tied to remaining enrichment / recalibration work

The report layer is structurally complete, but several limitations
are downstream of enrichment and recalibration that Stack A did not
finish. Each will self-correct once the underlying data or
calibration lands; none of them requires a report-layer change.

| Limitation | Cause | Unblock |
|---|---|---|
| Rankable-A is effectively a single-venue label in Stratford (Vintner only). | TripAdvisor coverage is 0.5% of eligible venues; multi-platform Rankable-A requires at least one other platform. | CI run of `collect_tripadvisor_apify.py` with `APIFY_TOKEN`. Tracked in `docs/DayDine-TripAdvisor-Trial-Status.md`. |
| Commercial Readiness rarely exceeds 7.5 / 10. | Phone / `reservable` / `business_status` coverage is 0%; the booking-path sub-signal is universally empty. Financial Impact Moderate / High confidence is therefore unreachable for most venues. | CI run of `enrich_google_stratford.py` with `GOOGLE_PLACES_API_KEY` using the extended field mask. Tracked in `docs/DayDine-Commercial-Readiness-Data-Status.md`. |
| Top-half rankable-score share sits above 50%. | Customer Validation calibration was performed against a dataset before Commercial Readiness `web` inference lifted 68.6% of venues. The current prior / gamma / n_cap values are not yet retuned against the enriched data. | A second calibration sweep via `calibrate_v4_customer.py` after enrichment. Tracked in `docs/DayDine-V4-Scoring-Comparison.md`. |
| Named-miss list (Dirty Duck, RSC Rooftop, Golden Bee, Baraset Barn, Boston Tea Party, Osteria Da Gino, Grace & Savour) is non-empty. | The 210-record FSA trial slice does not contain these venues; the resolver correctly surfaces them as `known_unresolved`. | Rerun `.github/scripts/augment_fsa_stratford.py` with the existing `KNOWN_RESTAURANTS` seed. Tracked in `docs/DayDine-Entity-Resolution-Status.md`. |
| Four duplicate-gpid ambiguous groups (9 records) sit at Directional-C. | Ambiguity detection works; manual disambiguation is not done. | Extend `data/entity_aliases.json` with manual `entity_match_override` entries, or accept Directional-C permanently for these records. |
| Financial Impact figures across venues still look similar after the post-fix CR-driven rewrite. | CR score is currently 7.5 for almost every venue (see second item above); CV review volume is the main discriminator, which works but has less range than intended. | Once phone / booking data lands, CR starts to differentiate and the FI range widens venue-to-venue. |

These limitations travel with the data pipeline, not with the report
layer. A next engineer should not "fix" them inside the generator.

---

## 8. Readiness for three use cases

| Use case | Status | Blockers |
|---|---|---|
| **Internal use** — scoring-engine QA, analyst diagnostics, internal reviews | **Ready.** | None. The sample set and guardrail tests exercise every mode; validation is clean. |
| **Pilot operator use** — a small, supervised operator set with known caveats | **Ready structurally; blocked on recs engine wiring.** | Management Priorities / Watch List / WNTD / Implementation Framework still render thin. A pilot would show operators empty-feeling action sections. Fix is the §4 first deferred item (wire V3.4 recs engine through a V4 adapter). |
| **Commercial publication** — paid operator deliverable, public cutover | **Not ready.** | All §4 deferred items ideally closed. All §7 enrichment / recalibration items ideally closed. Public methodology page softened further per readiness memo §D. Leaderboard cutover is its own separate workstream. |

The post-fix verdict in the samples assessment is **READY FOR B6
WITH MINOR DEFERRED ITEMS**. This handoff preserves that verdict and
scopes what "minor deferred" means for B6.

---

## 9. Stack B — complete

### Done

- Report specification (`docs/DayDine-V4-Report-Spec.md`).
- Report data model, generator, wording helpers, peer benchmarks,
  guardrail spec (`operator_intelligence/v4_adapter.py`,
  `v4_wording.py`, `v4_report_generator.py`,
  `v4_peer_benchmarks.py`, `v4_report_spec.py`).
- 24-test guardrail suite (`tests/test_v4_report_guardrails.py`)
  runnable with `python -m tests.test_v4_report_guardrails`.
- Seven canonical samples covering Rankable-A / Rankable-B /
  Directional-C / Profile-only-D / Closed / Temp-closed under
  `samples/v4/monthly/` with paired JSON and QA files.
- Samples assessment memo
  (`docs/DayDine-V4-Report-Samples-Assessment.md`) including §10
  post-fix record of every critical fix.
- Internal documentation updates: methodology page softened;
  migration and readiness memos cross-referenced to this handoff.
- Financial Impact rewritten: CR-score-driven + review-volume
  scaled; `gpl` demoted to weak prior; canonical fallback wording
  for Directional-C and thin-evidence states.
- Closure defensive override in the adapter; Directional-C
  Conditional sections restored; D → C → B unblock ladder;
  Closed Evidence Appendix context header.
- Lightweight V4-aware peer benchmarks scoped to
  Rankable-A ∪ Rankable-B.

### Intentionally deferred (see §4 for the canonical list)

Exactly and only:

1. Full V3.4 recommendations engine wiring (via a V4 adapter).
2. `_dimension_to_component` shim removal (blocked on item 1).
3. V4-aware demand-capture-audit builder.
4. Penalty-explanation registry.
5. CI integration of the guardrail test suite.
6. Financial Impact range-width tolerance check.
7. Segment-intelligence class demotion.

These are not complete. They are documented to be picked up later.

### Readiness summary

- **Internal use: ready.**
- **Pilot operator use: ready structurally; blocked on deferred
  item 1 (recommendations engine wiring).**
- **Public use / commercial publication: not ready.** Pending the
  deferred items above and the enrichment / recalibration / cutover
  work tracked in the existing status documents
  (`TripAdvisor-Trial-Status`, `Commercial-Readiness-Data-Status`,
  `Entity-Resolution-Status`,
  `V4-Scoring-Comparison`,
  `V4-Readiness-For-Stack-B`).

Stopping.
