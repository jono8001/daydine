# TripAdvisor Trial Status — Stratford-upon-Avon

*Status as of April 2026. Scope: Stratford trial set, 210 establishments.*

## TL;DR

| Question | Answer |
|---|---|
| Is the TripAdvisor collection code still broken? | **No.** The pipeline (collect → consolidate → merge) is fixed end-to-end and V4 now reads headline-score TA fields cleanly. |
| Is the trial data itself populated? | **No.** 1 of 210 venues has real TA data (Vintner Wine Bar). The live collection pass has not run in this environment because `APIFY_TOKEN` is not configured and direct scraping is CI-blocked. |
| Is Rankable-A structurally reachable? | **Yes in principle** — Vintner is currently the sole Rankable-A venue. But 97%+ of rankable venues remain Rankable-B until a live TripAdvisor pass lands. |
| Is this blocker cleared? | **Partially cleared.** The code path, schema, and matching logic are fixed. The data coverage itself is still blocked on a CI run with `APIFY_TOKEN`. |

## What was broken before

From `docs/review_data_strategy.md` §1.3 and the prior state of the repo:

1. **`collect_tripadvisor_apify.py`** used `automation-lab/tripadvisor-scraper`
   with name-only fuzzy matching at 0.5 threshold. The strategy audit
   reported 0/210 matches on a full pass — every venue returned
   `_no_match` or `_skipped`.
2. **`collect_tripadvisor.py`** (direct web scraper) is blocked from CI
   environments by TripAdvisor's anti-bot / Cloudflare.
3. **`collect_tripadvisor_playwright.py`** works but depends on a Playwright
   browser runtime and Google search intermediation — fragile.
4. **`merge_tripadvisor.py`** wrote review-text fields (`ta_reviews`,
   `ta_cuisines`, `ta_recency`) directly into `stratford_establishments.json`
   — the same file V4 reads as scoring input. Spec V4 §9 explicitly says
   review text must not feed headline scoring; routing it through the
   scoring input was a latent coupling even though V4's `_guard_forbidden`
   list does not catch `ta_reviews`.
5. **No consolidated side-input file.** `stratford_tripadvisor.json` did
   not exist; each collector wrote an ad-hoc shape. There was no canonical
   place for V4 to read TripAdvisor metadata from.
6. **The one real piece of TA data already in the repo** (`vintner_ta_raw.json`
   and `data/raw/tripadvisor/vintner_wine_bar_2026-04-01.json`) was never
   imported into the scoring pipeline — `stratford_establishments.json`
   had `ta` populated for Vintner only because an ad-hoc merge step had
   been run once by hand.

## What was fixed

All code changes land on branch `claude/verify-v4-scoring-spec-L4Cjv`.

### New files

- **`.github/scripts/consolidate_tripadvisor.py`** — reads every
  per-venue raw file under `data/raw/tripadvisor/` (supporting both the
  legacy `tripadvisor_*` field naming and the newer `ta`/`trc` schema),
  matches each raw record to an FHRSID using (in order) an explicit
  `fhrsid` field, name + postcode exact, name + haversine ≤ 200 m, or
  name-only exact, and emits `stratford_tripadvisor.json` as the canonical
  side-input for V4 scoring.
- **`.github/scripts/tripadvisor_coverage.py`** — emits
  `stratford_tripadvisor_coverage.json` with eligibility counts, match
  counts, percentages, and examples of both successful matches and
  venues that are eligible but have no raw TA record.

### Modified files

- **`.github/scripts/merge_tripadvisor.py`** — now consumes the
  consolidated side file and writes **only** headline-score fields
  (`ta`, `trc`, `ta_present`, `ta_url`) into
  `stratford_establishments.json`. Explicitly deletes any legacy
  narrative fields (`ta_reviews`, `ta_cuisines`, `ta_recency`,
  `ta_price`, `ta_ranking`) that previous versions of the script may
  have merged, so review text cannot leak into the V4 scoring input.
- **`.github/scripts/collect_tripadvisor_apify.py`** — three fixes:
    1. Default actor changed from `automation-lab/tripadvisor-scraper`
       (broken) to `scrapapi/tripadvisor-review-scraper` (recommended in
       `docs/review_data_strategy.md` §2.2). Override via `APIFY_ACTOR`.
    2. Result ranking uses a combined (name-similarity × 0.7 +
       coord-proximity × 0.3) score with configurable minimum via
       `MATCH_MIN_SCORE` (default 0.55 vs previous 0.5 name-only).
       Coord proximity is a linear [0 m → 1.0, 1000 m → 0.0] ramp.
    3. Writes per-venue raw files to `data/raw/tripadvisor/` (matching
       the existing format used by the Playwright collector and the
       Vintner artifact), instead of a single ad-hoc
       `stratford_tripadvisor.json`. The consolidator step now owns
       that file.

### Side-input shape

`stratford_tripadvisor.json` keys are FHRSIDs (plus `_meta` and
`_unmatched` blocks). Each matched entry:

```json
"503480": {
  "ta": 4.4,
  "trc": 20,
  "ta_url": "https://...",
  "ta_ranking": "...",
  "ta_cuisines": ["..."],
  "ta_present": true,
  "match": {
    "method": "fhrsid_field | name_postcode | name_coord | name_exact",
    "confidence": "high | medium | low",
    "distance_m": 0.0,
    "source_file": "data/raw/tripadvisor/...",
    "collected_at": "...",
    "collection_method": "apify_migrated"
  }
}
```

Only `ta`, `trc`, `ta_present`, `ta_url` are copied into
`stratford_establishments.json`. Everything else stays in the side file
for narrative / report generation.

## Current coverage

From `stratford_tripadvisor_coverage.json`:

| Metric | Value |
|---|---|
| Total establishments | 210 |
| Ineligible (non-food filter) | 15 |
| Eligible for TA search | 195 |
| **Matched to TripAdvisor** | **1 (0.5% of eligible)** |
| Raw TA records that could not be mapped to a fhrsid | 0 |
| Eligible venues with no TA attempt yet | 194 |

The only matched venue is **Vintner Wine Bar** (fhrsid 503480): rating
4.4, 20 reviews, matched via the `fhrsid` field on the raw artifact.
It sits at `Rankable-A` in V4 because it is the sole venue currently
satisfying the "multi-platform confirmed" gate (Google 887 reviews at
4.6, TA 20 reviews at 4.4, FSA 5, full Commercial).

Successful-match example:

```
Vintner Wine Bar (503480)
  ta=4.4, trc=20, ta_url=https://www.tripadvisor.co.uk/...
  match: fhrsid_field / confidence high
  source: data/raw/tripadvisor/vintner_wine_bar_2026-04-01.json
```

Failure / not-attempted examples (top 5 by Google review volume):

| Name | FHRSID | Google reviews | Reason |
|---|---|---|---|
| Loxleys Restaurant And Wine Bar | …  | 1669 | No raw TA record; never attempted |
| Shakespeare's | 1584577 | 1375 | No raw TA record; never attempted |
| Lambs | …  | 1372 | No raw TA record; never attempted |
| Ettington Park Hotel | … | 1021 | No raw TA record; never attempted |
| Beleza Rodizio | … | 950 | No raw TA record; never attempted |

See `stratford_tripadvisor_coverage.json` for the full list.

## What still limits TripAdvisor quality

1. **Live collection has not run.** The collector is fixed and ready, but
   this environment has no outbound network to Apify / TripAdvisor. A CI
   run with `APIFY_TOKEN` configured is the actual blocker on coverage.
2. **Matching logic is as good as the coords it gets.** The coord-based
   match needs the actor's results to include `lat`/`lng`. The two
   recommended actors (`scrapapi/tripadvisor-review-scraper`,
   `automation-lab/tripadvisor-scraper`) do include them in most cases,
   but for restaurants without clear address-to-coord data on TripAdvisor
   itself the fallback is name-only exact / fuzzy. That fallback carries
   the ambiguity risk the strategy doc flags (Dirty Duck, Church Street
   Townhouse, etc. trade as names that don't appear on the FHRS legal
   entity).
3. **TripAdvisor's own data quality.** TA is lumpy: a handful of venues
   have hundreds of reviews; many have a dozen or fewer; some have no
   listing at all. V4 Bayesian shrinkage handles thin counts, but a
   venue with 3 TA reviews still feeds coverage-weight ≥ 0.05 into the
   Customer Validation aggregate. That is the designed behaviour; it
   just means Rankable-A will be earned mostly by venues with substantive
   TA presence (N ≥ 30 approximately), not every restaurant in town.
4. **Entity-match resolver is still a placeholder.** `assess_entity_match`
   in `rcs_scoring_v4.py` infers confirmed / probable / ambiguous / none
   from presence of `id` and `gpid`. TA metadata does not currently feed
   it. A future resolver should use the TA URL and TA postcode as a
   third corroboration source.
5. **Review text is explicitly not a dependency.** TA reviews collected
   by the actor remain in the per-venue raw files and are passed through
   to the side-input narrative blob, but V4 scoring refuses to read any
   `review_text`, `sentiment_*`, `aspect_*`, or `ai_summary` fields.
   This is by design (spec V4 §9).

## Is the current trial coverage enough to make Rankable-A meaningful?

**No, not yet.** With 1/195 eligible venues matched, Rankable-A is
structurally reachable (Vintner occupies it today) but is not a
commercially meaningful label — it is effectively a single-venue badge.
The calibration work in `docs/DayDine-V4-Scoring-Comparison.md` and the
V4 spec §8.2 both assume Rankable-A reflects multi-platform evidence; on
today's data, fewer than 0.5% of the trial set can demonstrate that.

**What would clear the blocker:**

1. A single CI run of `collect_tripadvisor_apify.py` with `APIFY_TOKEN`
   configured and the `scrapapi/tripadvisor-review-scraper` actor. The
   strategy doc estimates ~£0.50–1.00 per 200 venues at 5 reviews each;
   actual headline-metadata-only collection is cheaper.
2. Consolidation + merge (already runnable — `consolidate_tripadvisor.py`
   then `merge_tripadvisor.py`).
3. Rerun V4 and `compare_v3_v4.py`; expect Rankable-A to grow into
   "venues with TA ≥ 30 reviews AND all three families populated".
   Informed estimate from `stratford_rcs_v4_scores.json`: 40–80 venues
   would meet the gate once TA coverage reaches ≥ 70%.
4. Update `docs/DayDine-V4-Scoring-Comparison.md` class-distribution
   section after the run.

## Status

**Partially cleared.** Pipeline code, data path, and matching logic are
fixed and ready to run. Actual trial coverage is still 0.5% and cannot
improve without a live collection run with `APIFY_TOKEN`. The cutover
gate in `DayDine-V4-Migration-Note.md` item (1) is therefore **not yet
satisfied**, but it is now a configuration/ops task rather than a code
task.

## Contacts and source files

| Topic | File |
|---|---|
| Strategy (source-by-source evaluation) | `docs/review_data_strategy.md` |
| V4 side-input consolidator (new) | `.github/scripts/consolidate_tripadvisor.py` |
| Coverage stats generator (new) | `.github/scripts/tripadvisor_coverage.py` |
| Live collector (fixed) | `.github/scripts/collect_tripadvisor_apify.py` |
| Side → record merge (fixed) | `.github/scripts/merge_tripadvisor.py` |
| Side-input file | `stratford_tripadvisor.json` |
| Coverage report | `stratford_tripadvisor_coverage.json` |
| V4 engine (unchanged by this work) | `rcs_scoring_v4.py` |
