# V4 vs V3.4 Scoring Comparison — Stratford-on-Avon

**Dataset:** 210 venues from `stratford_establishments.json`
**V3.4 source:** `stratford_rcs_scores.csv`
**V4 source:** `stratford_rcs_v4_scores.json` (engine `v4.0.0`)
**Artifacts produced by:** `compare_v3_v4.py`

## Artifacts

| Path | Purpose |
|---|---|
| `stratford_v3_v4_comparison.csv` | Per-venue side-by-side: V3 score/band/confidence, V4 score/class/rankability, delta, primary reason, reason tags |
| `stratford_v3_v4_distribution.json` | Aggregate stats for both models + V3 band × V4 class cross-tab |
| `stratford_v3_v4_movers.json` | Top-20 risers, top-20 fallers, venues dropped from ranking, venues still top under both |
| `stratford_v3_v4_sanity.json` | Suspiciously high thin-evidence venues, newly-excluded venues, top-band inflation, high-profile presence check |
| `docs/DayDine-V4-Scoring-Comparison.md` | This assessment |

## Headline numbers

| Metric | V3.4 | V4 |
|---|---|---|
| Mean score (all) | 8.058 | 7.626 |
| Median (all) | 8.405 | 7.926 |
| Stdev (all) | 1.424 | 1.179 |
| Ranked / league-eligible | 190 (90.5%) | 190 (90.5%) |
| Top band / class | Excellent 61.0% | Rankable-A 0.5% |
| Rankable with final ≥ 8.0 | — | 97 (50.8% of rankable) |

V4 compresses less than expected at the extremes but decisively breaks the Excellent inflation: 128 V3.4 "Excellent" venues drop to 125 Rankable-B + 3 Directional-C, with zero reaching Rankable-A.

## What improved

1. **Top-tier inflation broken.** V3.4 put 61% of venues in "Excellent" — effectively meaningless as a ranking. V4 reserves Rankable-A for multi-platform confirmed evidence (only 1 venue qualifies in Stratford: Vintner Wine Bar). The rest of the previously-Excellent set lands in Rankable-B, which carries the league tables.
2. **Sentiment-driven false highs corrected.** The Fox Inn went V3.4 9.88 → V4 6.79 (delta −3.09), Lithos 9.85 → 6.92 (−2.94), Bistrot Pierre 9.24 → 6.39 (−2.85). All were buoyed by V3.4's aspect sentiment and red-flag scoring; V4's platform-metadata-only scoring puts them where their Google/TA numbers place them.
3. **Venues with zero/single review counts removed from rank.** 8 V3.4-ranked venues (Costa Coffee, Compton Verney Cafe, Gardener's Retreat, etc.) now sit in Directional-C because they have ≤ 9 reviews. V3.4 published scores as high as 9.05 for these; V4 correctly flags them as unreliable rather than producing a high-precision number.
4. **Thin-data venues no longer floor-slammed.** V3.4's coverage penalty pushed venues with no Google data to ~1.9. V4's shrinkage pulls them toward the platform prior (3.8 Google) instead of zero. Karen's Korner rose V3.4 1.94 → V4 5.59 on FSA + Commercial alone. Absence of data no longer manufactures a negative signal.
5. **Companies House penalties surface cleanly.** `stratford_v3_v4_comparison.csv` shows CH codes in `v4_caps` / `v4_penalties`; V3.4 mostly left these as `not_checked`. This is structural rather than yet-active (no CH data collected for Stratford) but the plumbing is exercised.
6. **Variance tightened.** V4 stdev 1.18 vs V3.4 1.42. Less dramatic highs, less dramatic lows, with class gating carrying the "this venue is unreliable" signal rather than the score itself.

## Unintended consequences / issues

1. **Rankable-A is effectively empty (1/210).** TripAdvisor is absent for ~97% of Stratford venues, so §4.4's single-platform cap forces almost everyone to Rankable-B. This is spec-correct behaviour on thin data, but in practice Rankable-A cannot be a useful label until TripAdvisor (and later OpenTable) data is collected. Options: (a) collect TA data before cutover; (b) loosen §8.2 so strong Google + full FSA + full Commercial can reach A; (c) accept that A is rare and market Rankable-B as the primary ranked tier. Option (a) is preferred.
2. **Top-half compression persists.** 50.8% of rankable venues still score ≥ 8.0. The 3.8 Google prior combined with Stratford's typical 4.2–4.6 Google ratings keeps shrunk scores near 4.0–4.5, which maps to 8.0–9.0 on the 0–10 scale. The shrinkage is working for low counts but not spreading the middle. Worth testing a lower Google prior (e.g. 3.5) or a nonlinear 0–5 → 0–10 mapping.
3. **Suspiciously high scores with thin review evidence.** Oxheart (26 reviews, V4=8.66), Pickled & Tipsy's Cafe (23, 8.27), Fast Flavour (27, 8.21). Each sits just above the 30-review threshold where single-platform is "big-enough" for Rankable-A gating, and their 4.8–4.9 raw Google scores resist shrinkage. These are labelled Rankable-B correctly, but the score itself still reads "top tier" to a casual user. Either (a) tune Google `n_cap` up from 200 so the weight curve is slower, or (b) narrow the Rankable-B score band presentationally in the UI.
4. **Commercial Readiness capped around 7.5 for everyone.** No venue has `phone` / `booking_url` / `reservation_url` in the current data, so the booking-or-contact signal is always 0. The 15% commercial slot is structurally under-filled by ~3.75 points. Contact/booking data collection needs to land before cutover or the component is doing less than it should.
5. **Welcombe Hotel Golf Resort & Spa rose V3.4 4.0 → V4 6.04.** Primary reason `google_de_overweight`. The hotel has 2000+ Google reviews at 4.2; V3.4 penalised it heavily on place-type mismatch (non-food types dominating `gty`). V4 trusts the FSA+Google rating aggregate. Whether this is correct depends on whether the venue's food offering should be ranked in a food league table at all — the non-food exclusion filter may need to survive in V4 as a pre-filter.
6. **High-profile name matching is incomplete.** The sanity check looked for Dirty Duck, Rooftop, Black Swan, Church Street Townhouse, No 9 Church Street, Oscar's — none matched. These are trading names; FSA records them under legal entity names (e.g. Dirty Duck = The Old Thatch Tavern Ltd). This is a V3 and V4 data issue, not a V4 scoring issue, but worth a dedicated alias-resolver before consumer-facing rankings.
7. **Primary-reason classifier is heuristic.** The `primary_reason` column is useful for triage but not always the crispest explanation. Several fallers with moderate deltas classify as `structural_shift` when the real cause is the combined effect of removing sentiment and removing convergence-bonus — no single tag captures it.

## Ready for cutover?

**Not ready. Ready with calibration tweaks and one data-collection prerequisite.**

The structural changes are sound and the direction of movement is correct. The spec is faithfully implemented. Three items block clean cutover:

1. **Collect TripAdvisor data for the trial set.** Without a second customer platform, Rankable-A is unreachable for ≥97% of venues and the class distribution is misleading. `APIFY_TOKEN` secret + `collect_tripadvisor.yml` — already in the backlog per CLAUDE.md next-steps.
2. **Calibrate Customer Validation spread.** Options to test: Google prior 3.8 → 3.5; `n_cap` 200 → 300; or a gamma ≠ 1 mapping from shrunk-rating 0–5 to 0–10. Pick one and re-run the comparison artifacts before calling done.
3. **Collect phone / booking data.** Extend `enrich_google_stratford.py` with Places Details `phoneNumber` and `reservable` / booking links. Without this, the 15% Commercial Readiness component runs at ~75% of its cap for every venue — homogenising the score.

Once (1)–(3) are addressed the comparison artifacts should be regenerated and this document updated. The engine module itself does not need changes for cutover; calibration is via the `PLATFORM_PRIORS` constants and new data landing in the pipeline.

## Report / UI

Out of scope for this document. Report and frontend restructuring follows cutover — not before.
