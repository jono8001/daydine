# DayDine V4 Migration Note

*Status as of April 2026.*

> **Stack B (operator report redesign) is complete as of April 2026.** The
> V4 report layer is structurally done, tested, and documented. See
> `docs/DayDine-V4-Report-Handoff.md` for the full handoff, the
> verbatim deferred-items list, and the per-use-case readiness
> breakdown. Public leaderboard cutover and the public methodology page
> rewrite remain deferred and are **not** part of Stack B — they stay
> gated on the data-coverage items tracked in
> `docs/DayDine-V4-Readiness-For-Stack-B.md` §F.

## Where we are

- **V4 is implemented and running in parallel. No downstream public
  surface reads V4 yet.** `rcs_scoring_v4.py` produces V4 outputs
  following `DayDine-V4-Scoring-Spec.md` exactly. Trust & Compliance
  (40%), Customer Validation (45%), Commercial Readiness (15%).
  Confidence classes gate league-table eligibility.
- **V3.4 still runs.** `rcs_scoring_stratford.py` is untouched and runs in
  parallel on every scoring invocation. Outputs stay under the existing
  `stratford_rcs_*` filenames.
- **Comparison artifacts land automatically.** `compare_v3_v4.py` emits four
  files used to audit V4 behaviour (`stratford_v3_v4_comparison.csv`,
  `…_distribution.json`, `…_movers.json`, `…_sanity.json`). Assessment lives
  in `DayDine-V4-Scoring-Comparison.md`.
- **Public leaderboards are still on V3.4.** Frontend rankings files in
  `assets/rankings/` derive from the V3.4 CSV. No UI has been switched.

## Deprecated from V3.4 (removed in V4 scoring)

| V3.4 concept | Status |
|---|---|
| 40-signal / 7-tier aggregation | Replaced by three fixed-weight components |
| Six verbal rating bands as primary surface | Replaced by four confidence classes |
| Aspect sentiment (food / service / ambience / value / cleanliness) | Removed from score; report-only |
| Review-text red-flag penalties | Removed from score |
| Google AI summary ingestion | Removed entirely |
| Tier re-weighting when a signal is missing | Removed — V4 uses fixed weights + confidence gating |
| Cross-source convergence bonus (+3% / −3% / −5%) | Removed |
| Google 30% / 45% caps | Superseded by the 45% fixed weight on Customer Validation |
| Photo count, price level, place types as positive-quality signals | Removed from score; profile-only |
| Delivery / takeaway / parking / wheelchair as positive signals | Removed from score; profile-only |
| Facebook / Instagram presence signals | Removed from score |
| Coverage penalty (signal-count-based deduction) | Removed — replaced by confidence class |
| 18 V3.4 penalty rules | Replaced by V4's §7 rules (fewer, more structural) |

## Retained for legacy comparison only

- `rcs_scoring_stratford.py` — the V3.4 engine itself.
- `stratford_rcs_scores.csv`, `stratford_rcs_summary.json`,
  `stratford_rcs_report.md` — V3.4 outputs.
- `sentiment_*`, `aspect_*`, `red_flag_*`, and AI-summary fields in upstream
  collector outputs. V4 refuses to read these at the scoring boundary
  (`FORBIDDEN_FIELDS` in `rcs_scoring_v4.py`), but the collectors still run
  so that V3.4 keeps scoring and so the fields are available for report
  narrative once the report layer is redesigned.
- The six verbal bands — visible in V3.4 outputs only.

## Work remaining before full cutover

1. **Collect TripAdvisor data for the trial set.** Rankable-A is unreachable
   for ~97% of Stratford venues today because only Google is populated.
   Trigger `collect_tripadvisor.yml` once `APIFY_TOKEN` is configured.
2. **Calibrate Customer Validation spread.** 50.8% of rankable venues sit
   above 8.0 in the current V4 run — too compressed. Test lower Google prior
   (3.8 → 3.5), higher `n_cap` (200 → 300), or a non-linear 0–5 → 0–10
   mapping. Re-run `compare_v3_v4.py` after each change.
3. **Collect phone / booking data.** Extend `enrich_google_stratford.py` with
   Google Places Details `phoneNumber` and `reservable` / booking links.
   Until this lands, Commercial Readiness runs at ~75% of its cap
   universally and homogenises the score.
4. **Entity-match resolver.** Replace the placeholder in
   `assess_entity_match()` with a real resolver that handles trading-name vs
   legal-entity mismatches and surfaces `ambiguous` where two candidates
   exist.
5. **Companies House collector integration.** `.github/scripts/collect_companies_house.py`
   exists; wire its output into `score_batch(companies_house=…)` so the CH
   penalty/cap paths in V4 are exercised in the Stratford run.
6. **CI lint for forbidden fields.** Add a pre-commit / CI check that greps
   `rcs_scoring_v4.py` for `sentiment_`, `aspect_`, `ai_summary`,
   `review_text` and fails the build if they appear.
7. **New GitHub Actions workflow.** `score_v4.yml` to run V4 alongside V3.4
   on each scheduled run and commit both outputs.

## Report layer — still pending

No report or frontend changes have been made. The V3.4 markdown report,
operator intelligence document, and public leaderboards still use the
legacy outputs. Before cutover, the report layer must:

- Show **confidence class** (Rankable-A / Rankable-B / Directional-C /
  Profile-only-D) instead of the V3.4 confidence band.
- Exclude **Directional-C** from default league tables and surface it as a
  separate "Directional" list with a clear caveat.
- Stop rendering the six V3.4 verbal bands as the primary surface.
- Separate **report-only narrative** (review text, aspect sentiment) from
  **headline scoring** in the UI. Text-derived content should be labelled as
  context, not as a score input.
- Replace tier badges (FSA tier, Google tier, etc.) with the three V4
  component scores and the distinction modifier, if they are shown at all.
- Surface **source-family presence** ("FSA + Google + TripAdvisor"
  vs "FSA + Google only") prominently, since it determines class.

Report redesign is **Stack B** and is out of scope for this migration stack.
See the handoff section below for assumptions Stack B should make.

## Cutover gate

Before V4 becomes the public score:

1. All six comparison artifacts from
   `DayDine-V4-Scoring-Spec.md` §11.3 produced and reviewed.
2. No unexplained movers beyond ±1.0 on the 0–10 scale.
3. Class reclassification matrix spot-checked.
4. `Profile-only-D` set manually verified — no accidentally-dropped venues.
5. Calibration items (1)–(3) above complete.

## Handoff to Stack B (report redesign)

Stack B should assume, from this stack's output:

- **V4 is the authoritative score** once cutover completes. Do not build
  report structure around V3.4 tier scores.
- **The score is 0.000–10.000 at 3 decimal places.** The primary
  categorisation is the **confidence class**, not a verbal band.
- **Only Rankable-A and Rankable-B appear in default league tables.**
  Directional-C is a separate list. Profile-only-D is not ranked at all.
- **The score has three components**, not seven tiers. Reports should render
  Trust & Compliance (labelled clearly as *compliance*, not *food quality*),
  Customer Validation, and Commercial Readiness.
- **Review text, aspect sentiment, and AI summaries are report-only.**
  Render them as narrative context, never as a score driver. Never let their
  absence depress a score — V4 does not use them.
- **Missing data does not inflate scores** under V4. If a report compares a
  venue's Customer Validation to a peer, the comparison must acknowledge when
  the evidence is thin (low review count, single platform). The shrinkage is
  already applied in the score; the report just needs to name it.
- **Photo count, price level, place types, social presence, delivery,
  takeaway, parking, wheelchair** are profile attributes, not scoring
  signals. They can appear on profiles but must not feed any derived
  "quality score" the report invents.
- **Cross-source convergence bonus is gone.** Reports must not claim a venue
  is stronger because "all sources agree". Convergence is available as a
  descriptive fact on the profile if useful, but not as an uplift.
- **Distinction modifier is capped at +0.30.** Michelin / AA are the only
  sources. Local awards, press, and tourism-board listings do not feed the
  score and must not be framed as if they do.
- **Entity-match state is a surface-level concern.** `ambiguous` and `none`
  venues should be visibly flagged; the confidence class already carries this
  but the report copy should explain what it means.
- **V3.4 legacy scores should not be shown to end users** once cutover
  completes. During the migration window, if any comparison view is built,
  label V3.4 clearly as "previous methodology".

## Contacts and source files

| Topic | File |
|---|---|
| V4 spec | `docs/DayDine-V4-Scoring-Spec.md` |
| V4 engine | `rcs_scoring_v4.py` |
| V3.4 engine (legacy) | `rcs_scoring_stratford.py` |
| Comparison harness | `compare_v3_v4.py` |
| Comparison assessment | `docs/DayDine-V4-Scoring-Comparison.md` |
| Public methodology | `docs/DayDine-Scoring-Methodology.md` |
| Project state | `.claude/CLAUDE.md` |
