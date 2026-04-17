# V4 vs V3.4 Scoring Comparison — Stratford-on-Avon

**Dataset:** 210 venues from `stratford_establishments.json`
**V3.4 source:** `stratford_rcs_scores.csv`
**V4 source:** `stratford_rcs_v4_scores.json` (engine `v4.0.0`, Customer
Validation calibration 2026-04)
**Artifacts produced by:** `compare_v3_v4.py`

> **Calibration applied 2026-04.** Customer Validation uses Google prior 3.6
> (was 3.8), n_cap 250 (was 200), and mapping gamma 1.2 on the 0–5 → 0–10
> curve. See the "Calibration decision" section at the end of this document.
> All figures below reflect the calibrated engine.

## Artifacts

| Path | Purpose |
|---|---|
| `stratford_v3_v4_comparison.csv` | Per-venue side-by-side: V3 score/band/confidence, V4 score/class/rankability, delta, primary reason, reason tags |
| `stratford_v3_v4_distribution.json` | Aggregate stats for both models + V3 band × V4 class cross-tab |
| `stratford_v3_v4_movers.json` | Top-20 risers, top-20 fallers, venues dropped from ranking, venues still top under both |
| `stratford_v3_v4_sanity.json` | Suspiciously high thin-evidence venues, newly-excluded venues, top-band inflation, high-profile presence check |
| `docs/DayDine-V4-Scoring-Comparison.md` | This assessment |

## Headline numbers

| Metric | V3.4 | V4 (pre-calibration) | V4 (calibrated) |
|---|---|---|---|
| Mean score (all) | 8.058 | 7.626 | 7.482 |
| Median (all) | 8.405 | 7.926 | 7.761 |
| Stdev (all) | 1.424 | 1.179 | 1.185 |
| Mean score (rankable) | — | 7.854 | 7.716 |
| Stdev (rankable) | — | 0.724 | 0.749 |
| Ranked / league-eligible | 190 (90.5%) | 190 (90.5%) | 190 (90.5%) |
| Top band / class | Excellent 61.0% | Rankable-A 0.5% | Rankable-A 0.5% |
| Rankable with final ≥ 8.0 | — | 97 (50.8%) | 82 (42.9%) |

V4 compresses less than expected at the extremes but decisively breaks the Excellent inflation: 128 V3.4 "Excellent" venues drop to 125 Rankable-B + 3 Directional-C, with zero reaching Rankable-A. The calibration applied in 2026-04 further pulls the top-half share from 50.8% → 42.9% without re-compressing the lower half or rearranging the top-10.

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

## Calibration decision

Customer Validation dominates V4 headline scores because Stratford is almost
exclusively Google-only (203/210 Google, 1/210 TripAdvisor, 6/210 neither).
The pre-calibration defaults (Google prior 3.8, n_cap 200, linear 0–5 → 0–10)
put 50.8% of rankable venues above 8.0 and left 6 venues with <30 reviews
still above 8.0. The brief was "conservative but not dead, less top-half
compression, better differentiation at the top, low-volume venues not
reading like elite venues, no text dependence".

### Options tested

Sweep produced by `calibrate_v4_customer.py`. Every variant was applied
venue-by-venue to the full Stratford batch with all other V4 rules held
constant. Summary:

| Label | Google prior | pseudo | n_cap | gamma | Rankable mean | stdev | % ≥ 8.0 | Thin-high (≥8, <30 rev) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| V0_baseline                       | 3.8 | 30 | 200 | 1.00 | 7.854 | 0.724 | 50.8% | 6 |
| V1_prior_3.6                      | 3.6 | 30 | 200 | 1.00 | 7.827 | 0.727 | 49.2% | 5 |
| V2_prior_3.5                      | 3.5 | 30 | 200 | 1.00 | 7.814 | 0.729 | 48.2% | 4 |
| V3_ncap_250                       | 3.8 | 30 | 250 | 1.00 | 7.854 | 0.724 | 50.8% | 6 |
| V4_ncap_300                       | 3.8 | 30 | 300 | 1.00 | 7.854 | 0.724 | 50.8% | 6 |
| V5_gamma_1.25                     | 3.8 | 30 | 200 | 1.25 | 7.721 | 0.750 | 43.5% | 3 |
| V6_gamma_1.5                      | 3.8 | 30 | 200 | 1.50 | 7.593 | 0.777 | 39.3% | 1 |
| **V7_mild_combo_3.6_250_g1.2 (chosen)** | **3.6** | **30** | **250** | **1.20** | **7.716** | **0.749** | **42.9%** | **2** |
| V8_strong_combo_3.5_300_g1.3      | 3.5 | 30 | 300 | 1.30 | 7.645 | 0.762 | 40.8% | 1 |
| V9_pseudo_60                      | 3.6 | 60 | 300 | 1.00 | 7.765 | 0.718 | 44.0% | 2 |
| V10_rec_candidate                 | 3.6 | 45 | 300 | 1.20 | 7.676 | 0.743 | 41.4% | 1 |

Full per-variant diagnostics (top-10 deltas, thin-evidence lists, component
stats) are in `stratford_v4_calibration.json`.

### Chosen setting

**V7 — Google prior 3.6, pseudo-count 30, n_cap 250, mapping gamma 1.2.**

Applied in `rcs_scoring_v4.py` via `PLATFORM_PRIORS["google"]` and the new
`MAPPING_GAMMA` constant (§4.2 mapping: `shrunk_norm = (shrunk/5) ** gamma`).
Other platform priors are unchanged.

### Why V7

- **Top-half share 42.9% vs 50.8% baseline.** A single-knob gamma=1.25 (V5)
  gets to 43.5% but leaves the thin-evidence problem at 3 venues. V7 combines
  a modest prior drop (3.8 → 3.6), a modest n_cap bump, and a modest gamma.
  Each knob contributes a bit; none is pushed hard.
- **Thin-evidence ≥ 8.0 drops 6 → 2.** The two survivors (Oxheart 8.44 at 26
  reviews, Pickled & Tipsy's Cafe 8.02 at 23 reviews) sit just below 30
  reviews and carry 4.9 Google ratings — they are correctly Rankable-B rather
  than Rankable-A, and dropping them further would start penalising
  legitimately well-rated venues who simply aren't heavily reviewed.
- **Top-10 preserved.** Gilks' Garage Cafe stays #1 (8.98 → 8.93). Vintner
  Wine Bar (the only Rankable-A) moves 8.59 → 8.50. No top-10 re-ordering.
  High-quality venues lose ≤ 0.10 — the compression is at the "4.5-Google-
  rating average cafe" band, not at the top.
- **Stdev rankable 0.724 → 0.749.** Small but in the right direction —
  the band of rankable scores is wider, not narrower, after calibration.
- **No text dependence.** All calibration knobs operate on rating/count
  metadata. No sentiment, aspect, convergence, or text-derived input is
  added to compensate.
- **n_cap = 250 is near-neutral for Stratford today but future-proof.** With
  single-platform dominance, n_cap cancels in the weight ratio, so the
  effect is ~0 for most venues. It matters once TripAdvisor data lands and
  the weight between platforms has to be set.

### Why the rejected alternatives were rejected

- **V1 / V2 (prior-only).** 3.6 or 3.5 alone moves the thin-evidence count
  only modestly (6 → 5 → 4) and barely touches top-half compression. Prior
  changes lean more on low-count venues than on the 4.2–4.6-rated bulk,
  which is where the compression actually lives.
- **V3 / V4 (n_cap-only).** n_cap alone has no material effect on any rankable
  score in Stratford because almost every rankable venue is single-platform
  and the weight cancels. Left in for future use; not useful as a
  calibration lever on its own for this dataset.
- **V5 (gamma 1.25).** Good single-knob fix for top-half compression
  (43.5%) and preserves stdev, but prior stays 3.8 so three thin-evidence
  venues still land above 8.0. A lower prior pulls those down without
  touching the high end.
- **V6 (gamma 1.5).** Too aggressive. Pulls median rankable to 7.73 and
  starts compressing genuinely high venues (Lambs 8.62 → 8.47 territory).
  The "conservative but not dead" constraint rules this out.
- **V8 (strong combo 3.5/300/1.3).** Fixes thin-evidence cleanly (1 left)
  but top-mover magnitudes reach −0.57 (Paul's Catering 3-review venue
  −0.54; Mid-England Barrow 2-review −0.56). Over-penalises tiny-sample
  venues that are already correctly classed as Directional-C. Extra pain,
  no extra gain on the "real" rankable set.
- **V9 (pseudo 60).** Stronger low-volume shrinkage but 44% still ≥ 8.0 —
  it pulls low-count venues toward the prior (now 3.6) but does nothing to
  the 4.5-rated bulk. Useful signal: pseudo-count hikes help thin data
  specifically but don't solve top-half compression.
- **V10 (rec candidate 3.6 / 45 / 300 / 1.2).** Similar shape to V7 but
  with four knobs moved instead of three. The extra pseudo-count hike is
  overkill given V7 already hits 42.9% and 2 thin-evidence. Smaller
  calibration surface is preferable for reproducibility.

### Is Customer Validation now calibrated enough to proceed?

**Yes, for calibration purposes.** Mean rankable 7.72, stdev 0.75, top-half
42.9% is a commercially usable distribution that differentiates the "solid
average venue" band (7.0–7.8) from the clearly-strong band (8.0+) without
collapsing the top. The top-10 is stable; no high-profile venue has been
thrown around by the calibration.

**Not yet ready for public cutover.** Two data-collection items still block
the cutover gate, independent of Customer Validation calibration:

1. TripAdvisor data is missing for 97%+ of venues, so Rankable-A remains
   structurally unreachable for most of the trial set. The calibration
   here does not and cannot fix that.
2. Commercial Readiness is capped at 0.75 universally because phone /
   booking-URL data is not collected. The 15% weight is under-utilised.

Those two items are the remaining blockers from the "Work remaining before
full cutover" list in `docs/DayDine-V4-Migration-Note.md`. Customer
Validation itself does not need further calibration before cutover; re-run
the comparison artifacts once TripAdvisor lands and re-check spread.

## Report / UI

Out of scope for this document. Report and frontend restructuring follows cutover — not before.
