# DayDine V4 — Enrichment Execution Status

*Authored April 2026. Branch: `claude/verify-v4-scoring-spec-L4Cjv`.*
*Scope: factual record of attempted live enrichment runs.*

> **Headline finding.** Neither live enrichment pass completed. The
> environment in which this prompt was executed has no
> `GOOGLE_PLACES_API_KEY` and no outbound HTTPS egress at all
> (every external host returns HTTP 403, including
> `api.ratings.food.gov.uk`, `api.github.com`, and `example.com`).
> Both passes were attempted — both failed deterministically as
> documented below. The trial dataset is unchanged from its
> pre-attempt state. Live execution remains gated on a runner
> environment that has both the secret and the network egress; the
> scripts themselves are unchanged from the code-ready state
> committed in the previous prompt.

---

## 1. Pre-attempt environment probe

Before attempting either pass, both APIs were probed with several
variants to rule out request-shape / header / version issues:

```
=== FSA — try several variants (api-version × User-Agent) ===
  api-ver=1 UA=default:                  HTTP 403
  api-ver=2 UA=default:                  HTTP 403
  api-ver=1 UA=Mozilla/5.0:              HTTP 403
  api-ver=2 UA=Mozilla/5.0:              HTTP 403
  api-ver=1 UA=DayDine-pipeline/1.0:     HTTP 403
  api-ver=2 UA=DayDine-pipeline/1.0:     HTTP 403

=== FSA — direct endpoints, no params ===
  https://api.ratings.food.gov.uk/                        -> HTTP 403
  https://api.ratings.food.gov.uk/Establishments/503480   -> HTTP 403
  https://ratings.food.gov.uk/                            -> HTTP 403

=== Generic outbound check ===
  https://example.com/         -> HTTP 403
  https://api.github.com/zen   -> HTTP 403
  https://www.google.com/      -> HTTP 403

=== Env / secret presence ===
  GOOGLE_PLACES_API_KEY: NOT set
  APIFY_TOKEN:           NOT set
  FIREBASE_DATABASE_URL: NOT set
```

The 403 from `example.com` and `api.github.com` confirms this is a
sandbox-wide egress policy, not an FSA-specific issue. There is no
header / version / auth combination that would let a request from
this environment reach either API.

---

## 2. Live attempts — what actually happened

### 2.1 Google enrichment

Command:
```
python3 .github/scripts/enrich_google_stratford.py
```

Result:
```
ERROR: GOOGLE_PLACES_API_KEY not set
```

Exit code: `1`. The script aborts on the first line of `main()`
before attempting any network call. **No data was written.**

Even with a key the run would have failed at the first POST to
`https://places.googleapis.com/v1/places:searchText` because the
sandbox blocks all outbound HTTPS.

### 2.2 FSA augmentation

Command:
```
python3 .github/scripts/augment_fsa_stratford.py
```

Result:
```
Existing: 210 establishments (210 tracked IDs)
  Fetching type 1 (Restaurant/Cafe/Canteen)...
Traceback (most recent call last):
  …
  File ".github/scripts/augment_fsa_stratford.py", line 92, in fetch_fsa_type
    resp.raise_for_status()
requests.exceptions.HTTPError: 403 Client Error: Forbidden for url:
  https://api.ratings.food.gov.uk/Establishments?
    localAuthorityId=320&BusinessTypeId=1&pageSize=0
```

The script reached its first FSA call and was rejected at the
network layer. No partial write to `stratford_establishments.json`
— `git status` immediately after returned a clean working tree.

---

## 3. Actual coverage — before vs after

Because neither pass completed, the **after** column equals the
**before** column. This is recorded explicitly so the next CI run
has a clear baseline to diff against.

### 3.1 Google V4 CR signals

| V4 CR signal | Before | After (live) | Change |
|---|---:|---:|:---:|
| Rating (`gr`) | 204 / 210 (97.1%) | 204 / 210 (97.1%) | — |
| Review count (`grc`) | 204 / 210 (97.1%) | 204 / 210 (97.1%) | — |
| Opening hours (`goh`) | 172 / 210 (81.9%) | 172 / 210 (81.9%) | — |
| Website observed (`web_url`) | 0 / 210 | 0 / 210 | — |
| Website inferred (`web=True`) | 144 / 210 (68.6%) | 144 / 210 (68.6%) | — |
| Phone (`phone`) | 0 / 210 | 0 / 210 | — |
| `reservable` | 0 / 210 | 0 / 210 | — |
| `booking_url` / `reservation_url` | 0 / 210 | 0 / 210 | — |
| `business_status` | 0 / 210 | 0 / 210 | — |

### 3.2 FSA / named-venue completeness

| Category | Before | After (live) | Change |
|---|---:|---:|:---:|
| Total establishments | 210 | 210 | — |
| Named-miss high-profile venues absent | 7 (Dirty Duck, Rooftop, Golden Bee, Baraset Barn, Boston Tea Party, Osteria Da Gino, Grace & Savour) | 7 (same) | — |
| Named-miss not-in-any-FSA-LA | 1 (Oscar's) | 1 (same) | — |

---

## 4. Failure / partial-run summary

| Pass | Outcome | Failure point | Root cause |
|---|---|---|---|
| Google enrichment | **Did not run** | `main()` line 1 secret check | `GOOGLE_PLACES_API_KEY` not set in env; would also fail on egress if it had been set |
| FSA augmentation | **Aborted on first network call** | `fetch_fsa_type` raised on HTTP 403 | Sandbox egress policy denies all outbound HTTPS |

No partial writes; no data corruption; no script crash. Both
failures are operational-environment limitations, not script bugs.
The repairs from the previous prompt
(`enrich_google_stratford.py` schema-version + resume-cache fix;
`augment_fsa_stratford.py` name+postcode fallback) are in place
and will take effect when the scripts run in a runner with both
the secret and outbound network access.

---

## 5. Readiness for next steps

Because no enrichment data landed, the readiness picture is
unchanged from the post-C2-audit memo
(`docs/DayDine-V4-Enrichment-Status.md`):

| Next step | Ready now? | Reasoning |
|---|---|---|
| TripAdvisor collection (Blocker 3) | **No, conditional.** | Same precondition as before this prompt: TA collection should wait until Google enrichment refreshes coordinates and FSA augmentation has landed the named misses, otherwise TA would fail to match those venues. |
| Duplicate-GPID disambiguation (Blocker 4) | **Yes, can run independently.** | Unchanged. The four ambiguous groups are already flagged in the resolver report. Manual alias-table entries can be added at any point. |
| Post-enrichment Customer Validation recalibration (Blocker 5) | **No.** | Must wait for live Google + TripAdvisor passes. |
| Scheduled V4 workflow (Blocker 6) | **Yes, code is ready today.** | Unchanged. |

---

## 6. What the next CI engineer needs to do

The same command sequence as recorded in
`docs/DayDine-V4-Enrichment-Status.md` §7. Restated for
self-containment:

```bash
# Preconditions: GOOGLE_PLACES_API_KEY in env;
# runner has outbound HTTPS to places.googleapis.com and
# api.ratings.food.gov.uk

python .github/scripts/enrich_google_stratford.py
python .github/scripts/merge_enrichment.py
python .github/scripts/augment_fsa_stratford.py
python .github/scripts/resolve_entities.py
python .github/scripts/commercial_readiness_coverage.py
python .github/scripts/tripadvisor_coverage.py
python rcs_scoring_v4.py \
  --input stratford_establishments.json \
  --menus stratford_menus.json \
  --editorial stratford_editorial.json \
  --out-json stratford_rcs_v4_scores.json \
  --out-csv  stratford_rcs_v4_scores.csv
python compare_v3_v4.py
python scripts/generate_v4_samples.py
```

After step 1 the engineer should expect
`stratford_google_enrichment.json` to be written / refreshed with
each entry carrying `_schema_version = 2`. After step 3 the
engineer should expect a notable expansion of
`stratford_establishments.json` (240–320 records depending on the
LA-320 pull) plus closure of most of the seven named-miss venues.
All five CI gates from
`.github/workflows/v4_report_checks.yml` should remain green;
`samples/v4/monthly/_summary_2026-04.json` will change because
the underlying V4 scores will have moved with the enriched data —
the engineer should commit the updated samples deliberately.

---

## 7. Yes / no answers

- **Did live Google enrichment complete?** **No.** Aborted on the
  first line of `main()`: `GOOGLE_PLACES_API_KEY not set`.
- **Did live FSA augmentation complete?** **No.** Aborted on first
  network call: HTTP 403 from sandbox-wide outbound egress block.
- **Is the trial dataset now materially improved?** **No.** Working
  tree was clean before and after both attempts. No data files
  changed.
- **Can we now proceed to TripAdvisor collection?** **No** — same
  blocker as before this prompt: TA depends on the Google +
  FSA passes landing first.
- **Can we now proceed to duplicate-GPID disambiguation?** **Yes**
  — independent of enrichment; unchanged by this prompt.
- **Can we now proceed to post-enrichment recalibration?** **No** —
  no enrichment to recalibrate against.

---

## 8. Files changed in this prompt

- `docs/DayDine-V4-Enrichment-Execution-Status.md` (this file).

No code changed; no data changed; no sample changed. The previous
prompt's repairs (Google schema-version tagging; FSA postcode
fallback) remain in place. CI workflows are unchanged.

---

*End of execution-status memo. Live enrichment remains
operationally blocked on runner access; no fabricated coverage
numbers are reported here.*
