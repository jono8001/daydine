# DayDine V4 — Enrichment Status

*Authored April 2026. Branch: `claude/verify-v4-scoring-spec-L4Cjv`.*
*Scope: Stratford trial dataset. Enrichment-only pass; no
recalibration, no public cutover, no methodology rewrite.*

> **Operational constraint that shaped this pass.** This working
> environment has no `GOOGLE_PLACES_API_KEY` configured and no
> outbound network route to the FSA Ratings API (`api.ratings.food.
> gov.uk` returns HTTP 403 from the sandbox). Neither the Google
> enrichment nor the FSA augmentation could be **executed live**
> here. Both scripts have been audited end-to-end, latent bugs that
> would have blocked the V4 Commercial Readiness fields from ever
> collecting have been fixed, and the scripts are now code-ready
> for a CI run. The live data pass is a one-command CI job for each
> script once the appropriate secrets / workflow trigger are set.

---

## 1. What this pass completed

Two latent bugs in the enrichment / augmentation scripts were found
and repaired. Both would have silently degraded the data a CI run
is meant to produce. Neither bug was visible in the live output
today because neither script has been executed against live data
since the V4 schema extensions landed.

### 1.1 Google enrichment: resume-cache bug

**Problem.** The enrichment script supports resume via a cached
`stratford_google_enrichment.json` file. The resume check was
`if key in enrichment: skipped += 1; continue` — meaning any entry
already in the cache was skipped, regardless of whether that entry
was produced under the V4 field mask. If a pre-V4 cache file exists
(commit history confirms one did until `c526056` cache-busted it),
a resumed run would skip every venue and never collect the V4
Commercial Readiness or closure fields.

**Fix.** `enrich_google_stratford.py` now:
- tags every enrichment entry with `_schema_version = 2`;
- defines a `_has_v4_schema(entry)` check that accepts an entry as
  already-processed only if the schema marker is present, or any
  V4-CR field is present, or the entry is an explicit `_no_match`;
- updates the main-loop skip to use that check;
- re-enriches pre-V4 cache entries explicitly and logs a count.

After this fix, a CI run against a legacy cache re-enriches all
pre-V4 entries in the same pass rather than silently passing them
through.

### 1.2 FSA augmentation: named misses without FHRSID silently skipped

**Problem.** `augment_fsa_stratford.py` has a `KNOWN_RESTAURANTS`
seed list naming high-profile venues expected in the Stratford
market. When a seeded venue is missing from the LA-320 pull, the
script attempts a direct fetch by FHRSID. If the seed entry has no
FHRSID (true for Dirty Duck, Rooftop Restaurant, Golden Bee,
Baraset Barn, Boston Tea Party, Osteria Da Gino, Grace & Savour)
the loop just hit `continue` and moved on. The named-miss gap
stayed open.

**Fix.** The script now carries a second fallback: for any seeded
venue still missing after the FHRSID fetch, it searches the FSA
API by `name` + `address` (postcode) across all local authorities.
The first match with an exact-postcode hit wins; otherwise the
first returned match is taken. The script now logs a final
"STILL MISSING after fallbacks" line only for names that both
fallbacks failed on — so the true remaining gap is visible.

This is how a public-API-only CI run can pull in venues registered
under parent entities outside LA 320 (common for franchise groups)
that the LA-scoped pull would otherwise miss.

### 1.3 What this pass did **not** do

- No live Google Places API call — no key available here.
- No live FSA Ratings API call — sandbox returns HTTP 403.
- No change to `stratford_establishments.json` or any V4 output.
  Samples regenerate byte-identical to the committed baseline.
- No TripAdvisor collection pass (the prompt excluded it).
- No recalibration; no methodology-page change.

---

## 2. Google enrichment — before vs projected-after

**Before** (live state on this branch):

| V4 CR signal | Coverage | Source |
|---|---:|---|
| Rating (`gr`) | 204 / 210 (97.1%) | pre-V4 Google Places pull |
| Review count (`grc`) | 204 / 210 (97.1%) | pre-V4 Google Places pull |
| Opening hours (`goh`) | 172 / 210 (81.9%) | pre-V4 Google Places pull |
| Website observed (`web_url`) | 0 / 210 | — |
| Website inferred (`web=True`) | 144 / 210 (68.6%) | `check_web_presence.py` heuristic |
| Phone (`phone`) | 0 / 210 | — |
| `reservable` | 0 / 210 | — |
| `booking_url` / `reservation_url` | 0 / 210 | — |
| `business_status` (closure flag) | 0 / 210 | — |

**Projected-after** (once the repaired
`enrich_google_stratford.py` runs in CI with a valid API key):

| V4 CR signal | Expected coverage | Why the range |
|---|---:|---|
| `websiteUri` observed | ~80–95% of food venues | Most UK restaurants have a website listed on Google |
| `nationalPhoneNumber` | ~90–98% | UK restaurants almost universally publish a phone |
| `reservable` | ~20–40% | Only venues on Reserve-with-Google / partner integrations carry this flag |
| `businessStatus` | ~99% | Places API returns `OPERATIONAL` / `CLOSED_*` on nearly every matched place |
| Rating / review count / hours | minor refresh | Incremental since the pre-V4 pull |

Ranges are honest: the Places API does not guarantee every field
for every place. The CI run will emit a per-field coverage count
to `stratford_google_enrichment.json` which the post-run
`commercial_readiness_coverage.py` script reduces to the table
above.

---

## 3. FSA augmentation — bundled into this pass

**Yes, FSA augmentation was bundled.** Rationale: the augmentation
script is mechanically separate from Google enrichment (reads a
different public API, writes the same target file with no key
collisions), the fix was small (a single postcode fallback inside
the still-missing loop), and the two named-miss fixes have
independent value. Bundling saved a second commit cycle.

**Before** (live state):

| Category | Count |
|---|---:|
| Total establishments in trial | 210 |
| Named-miss high-profile venues absent | **7** — Dirty Duck, Rooftop, Golden Bee, Baraset Barn, Boston Tea Party, Osteria Da Gino, Grace & Savour |
| Named-miss not-in-any-FSA-LA | 1 — Oscar's |

**Projected-after** (once the repaired
`augment_fsa_stratford.py` runs in CI — FSA API is public, no
secret required):

| Category | Expected count | Confidence |
|---|---:|---|
| Total establishments after LA-320 full pull | 240–320 | Based on earlier audit showing FSA total > our 210 for LA 320 |
| Named misses closed by LA-320 pull | 3–5 out of 7 | Depends on whether each named venue is registered under LA 320 or a neighbouring LA |
| Named misses closed by the new postcode fallback | 2–4 more | The postcode fallback catches venues under parent entities in other LAs |
| Named misses after both fallbacks | 0–2 residual | Oscar's remains unresolvable (no plausible FSA record in any LA) |

After the live run the named-miss list in
`data/entity_aliases.json::known_unresolved` will need to be
reviewed and trimmed to the residual set.

---

## 4. Named public-venue completeness — status

No change in live state this pass; scripts are ready.

| Venue | Current state | Unblock |
|---|---|---|
| The Dirty Duck | Absent; known_unresolved | Live augmentation — FSA LA-320 pull + postcode fallback |
| The Rooftop Restaurant (RSC) | Absent; known_unresolved | Same |
| The Golden Bee | Absent; known_unresolved | Same |
| Baraset Barn | Absent; known_unresolved | Same |
| Boston Tea Party | Absent; known_unresolved | Same |
| Osteria Da Gino | Absent; known_unresolved | Same |
| Grace & Savour | Absent; known_unresolved | Same |
| Oscar's | Likely unresolvable | Manual investigation (venue may be closed / never FHRS-registered) |

The Church Street Townhouse / Pick Thai / Super Nonna trading-name
cases are **already resolved** via the alias table and do not need
FSA augmentation.

---

## 5. What this would change once the live run completes

### 5.1 Commercial Readiness

- Currently structurally capped at 7.5/10 for all rankable venues
  because the booking/contact-path sub-signal is universally
  absent (0%).
- After enrichment: the sub-signal is observable for the ~90% of
  venues with published phones plus the ~30% with
  Reserve-with-Google. CR ceiling rises; CR distribution widens.
- Directly lifts the maximum realistic V4 headline score because
  CR weight is 15% of the composite.

### 5.2 Closure detection (spec §7.4)

- Currently zero: no venue has a `business_status` or `fsa_closed`
  flag populated, so the closure-defensive-override paths in the
  adapter / generator are tested only on synthetic fixtures.
- After enrichment: every matched venue gets a closure flag. The
  real `CLOSED_PERMANENTLY` / `CLOSED_TEMPORARILY` / `OPERATIONAL`
  values flow through, the closure notice mode fires for venues
  that are actually closed, and the temp-closure banner fires for
  any venue genuinely in that state.

### 5.3 Financial Impact confidence ladder

- Currently every rendered FI section sits at **Low** confidence
  (Vintner, Lambs, Loxleys samples all show "Low"). That's spec-
  correct given web is all inferred and phone is absent, but it
  caps the section's operator-facing value.
- After enrichment: venues with observed web + observed phone + a
  CR score ≥ 6.0 + a platform with ≥ 30 reviews will hit
  **Moderate** confidence. Venues that also reach CR ≥ 7.0 will
  hit **High**. The ladder finally varies per venue.

### 5.4 Rankability meaningfulness

- Rankable-A remains structurally unreachable today because almost
  every venue is single-platform (203/210). Google enrichment does
  **not** fix this on its own — it is TripAdvisor's job. Enrichment
  lifts CR and FI confidence; the platform-count blocker is the
  next step (Blocker 3 in the public-cutover-blockers memo).

---

## 6. Readiness to proceed to the next cutover-prep steps

| Next step | Ready after this pass? | Reasoning |
|---|---|---|
| TripAdvisor collection pass (Blocker 3) | **Yes, once Google enrichment is executed live.** | TA collector uses coordinates that Google enrichment refreshes; running TA on the pre-enrichment data would miss the seven named-miss venues too. |
| Duplicate-GPID disambiguation (Blocker 4) | **Yes, can run independently now.** | The four ambiguous groups are already flagged in the resolver report; manual alias-table entries can be added at any point. Richer matching signals from Google enrichment would make the human-review step easier but are not a precondition. |
| Post-enrichment Customer Validation recalibration (Blocker 5) | **No — must wait for live Google + TripAdvisor passes.** | Calibration against the current data would re-encode the pre-enrichment shape. A sweep only makes sense after the data passes have landed. |
| Scheduled V4 workflow (Blocker 6) | **Yes, code is ready today.** | A new `.github/workflows/score_v4.yml` file can land independently; it would score against whatever data is present. |
| Public methodology / leaderboard copy (Blocker 7) | **No — gated on Blockers 1–5 per the cutover-blockers memo.** | Out of scope for this pass anyway. |

---

## 7. Exact ops commands for the CI run

For the engineer who triggers the live pass, the sequence is:

```bash
# 1. Google Places enrichment (requires GOOGLE_PLACES_API_KEY)
python .github/scripts/enrich_google_stratford.py
python .github/scripts/merge_enrichment.py

# 2. FSA slice augmentation (public API; no secret)
python .github/scripts/augment_fsa_stratford.py

# 3. Re-run entity resolution so trading-name + duplicate-GPID
#    flags update against the enriched venue set
python .github/scripts/resolve_entities.py

# 4. Re-compute coverage artefacts
python .github/scripts/commercial_readiness_coverage.py
python .github/scripts/tripadvisor_coverage.py

# 5. Re-score V4 against enriched data
python rcs_scoring_v4.py \
  --input stratford_establishments.json \
  --menus stratford_menus.json \
  --editorial stratford_editorial.json \
  --out-json stratford_rcs_v4_scores.json \
  --out-csv  stratford_rcs_v4_scores.csv

# 6. Regenerate V4 samples + comparison artefacts
python compare_v3_v4.py
python scripts/generate_v4_samples.py
```

All five CI gates from `.github/workflows/v4_report_checks.yml`
should remain green after each step. The
`samples/v4/monthly/_summary_2026-04.json` file will change after
step 5 because the underlying V4 scores will have shifted with the
enriched data — that's the expected behaviour, and the reviewer
should commit the updated samples as part of closing the
enrichment operation.

---

## 8. Files changed in this pass

- `.github/scripts/enrich_google_stratford.py` — added
  `MIN_V4_SCHEMA` / `_has_v4_schema()` + schema-version tagging +
  resume-cache fix.
- `.github/scripts/augment_fsa_stratford.py` — added
  name+postcode fallback search for `KNOWN_RESTAURANTS` entries
  without an FHRSID.
- `docs/DayDine-V4-Enrichment-Status.md` (this file).

No change to scoring-engine code, V4 report code, samples, or any
data file.

---

*End of enrichment-status memo. Live data pass remains a CI-
operated task; scripts are code-ready.*
