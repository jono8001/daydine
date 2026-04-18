# DayDine — Fetch-and-Score Failure Diagnosis

*Authored April 2026. Branch: `claude/verify-v4-scoring-spec-L4Cjv`.*
*Scope: operational debugging of the failed Stratford
`fetch_and_score.yml` run that surfaced
`statistics.StatisticsError: mean requires at least one data point`
and blocked public-cutover prep. Not a redesign; not a
recalibration.*

---

## 1. Exact root cause

The failing workflow has **two** independent defects that
compound into the reported error:

1. **Primary (why the dataset became empty):**
   `.github/scripts/fetch_firebase_stratford.py` did not handle
   the case where Firebase returned zero matching rows. It
   simply wrote whatever it received (`{}` or `null`) into
   `stratford_establishments.json`, silently overwriting the
   committed cache. The most plausible upstream triggers for a
   zero-row response:
   * The `la` indexOn rule on `daydine/establishments` is
     missing or was reset (orderBy requires the index; without
     it Firebase returns an error, but an earlier tolerant
     variant may have been re-deployed).
   * The `la` value drifted in the RTDB (e.g. records stored as
     `"Stratford-upon-Avon"` while the query filters on
     `"Stratford-on-Avon"`).
   * Upstream ingestion briefly wiped the node between writes.
   From inside Claude Code the sandbox blocks all outbound
   HTTPS, so the specific upstream trigger cannot be observed
   live — the fix surfaces whichever of those caused the empty
   response rather than papering over it.

2. **Secondary (why the error surfaced as a stats crash):**
   `rcs_scoring_stratford.py::generate_report` called
   `statistics.mean(ranked_scores)` and `statistics.median(...)`
   **unguarded** on lines 1861–1862. Every other `statistics.*`
   call in the file was defended with `if scores else 0`;
   these two were the exception. With zero ranked rows the
   call raised `StatisticsError` and the job exited 1. The
   `build_summary` step was reached (and succeeded, because it
   was guarded), which is why the CSV + summary were written
   before the crash.

Reproduced locally by overwriting the cache with `{}` and
running `python rcs_scoring_stratford.py --from-cache`:
identical traceback, identical line number, identical exit code.

## 2. Where the empty dataset first appears

| Stage | File | Symptom |
|---|---|---|
| Firebase fetch | `.github/scripts/fetch_firebase_stratford.py` | Printed "Fetched 0 establishments"; wrote `{}` to `stratford_establishments.json`. |
| Cache on disk | `stratford_establishments.json` | `{}` — the empty dataset is now persisted and would have been committed if scoring had succeeded. |
| Pipeline entry | `rcs_scoring_stratford.py::main` | No guard; `run_pipeline({})` produced `scored = []`. |
| Tiebreaker | `apply_tiebreakers` | `ranked = []`, `insufficient = []`, `non_food = []`. Did not fail. |
| Summary | `build_summary` | Succeeded because every `statistics.*` call was guarded. Wrote CSV + summary with zeros. |
| Report | `generate_report` line 1861 | **Crashed.** Unguarded `statistics.mean([])`. |

The empty dataset first appears at the fetch step. Every
subsequent step accepted it without complaint until the final
report writer tried to compute a mean.

## 3. What was fixed

Three tightly scoped changes on the failing path:

### 3.1 `.github/scripts/fetch_firebase_stratford.py` — fail fast
on empty / malformed Firebase response

* Handles `None` return (Firebase returns `null` on no match)
  and non-dict responses.
* Refuses to overwrite an existing committed cache with an
  empty object.
* Exits with a typed non-zero code (2 = malformed, 3 = empty)
  and a diagnostic listing the three likely upstream causes
  (LA drift, missing indexOn rule, wiped node).
* Warns (non-fatal) if none of the fetched rows has a CV
  postcode — early signal that the LA filter has drifted.

### 3.2 `rcs_scoring_stratford.py` — two guards

* **`main()`**: refuses to score when the loaded cache is empty
  or malformed. Exits 4 with a diagnostic that points back at
  the fetch step, not at a downstream stats error.
* **`generate_report()`**: the two unguarded `statistics.mean` /
  `statistics.median` calls are now defended with an empty-list
  ternary so the report prints `—` rather than crashing if
  something still gets through the fail-fast guards above.

### 3.3 `.github/workflows/fetch_and_score.yml` — boundary logging

* New "Inspect cache before fetch" step prints the committed
  cache row count before fetch runs.
* New "Inspect cache after fetch" step prints the post-fetch
  row count and fails with `::error::` if zero rows (redundant
  with the script's exit 3, but visible in the workflow
  summary).
* New "Inspect scoring outputs" step prints the CSV row count
  and the summary's `count / ranked / mean / median` fields so
  a reviewer can eyeball the numbers without downloading
  artefacts.
* `timeout-minutes: 15` added so a hung fetch does not burn the
  default 6-hour CI quota.

All three changes are local to the failing path. The V4
pipeline (`score_v4.yml`), enrichment workflows
(`enrich_and_score.yml`, `full_pipeline.yml`), and the V4
report layer are **not** touched.

## 4. What still needs to happen operationally

Before the next scheduled run, someone with Firebase console
access needs to confirm one of:

1. `firebase-rules.json` still declares
   `"indexOn": ["la", ...]` under `daydine/establishments`
   (the `orderBy: "la"` query requires it). If missing, restore
   the rule and redeploy.
2. The `la` field values in `daydine/establishments/*` are
   still the canonical `"Stratford-on-Avon"` (note: the
   display name we use is `"Stratford-upon-Avon"` — the
   FSA-canonical LA name is `"Stratford-on-Avon"`). If drift
   has occurred, either normalise the RTDB values or update
   the query string in `fetch_firebase_stratford.py`.
3. The node was not wiped by an upstream ingestion run. A
   spot-check of a known FHRSID (e.g. `502816` "Loxleys") at
   `daydine/establishments/502816` is sufficient.

No code change is required for any of these three; each is an
operational / data-plane fix.

The V3.4 trial CSV / summary / report files on disk are
**unchanged** by this prompt — the fix preserves the last good
cached scoring output.

## 5. Will a re-run succeed?

* **If the upstream RTDB is healthy** (indexOn rule present,
  `la` values correct, node populated): yes. The fetch will
  return 210-ish rows, scoring will run to completion as it
  does locally, and the workflow will commit an update. The
  new boundary-logging steps will print row counts along the
  way.
* **If the upstream RTDB is still empty**: the workflow will
  now abort at step "Fetch from Firebase RTDB" with exit 3 and
  a diagnostic naming the three likely causes, instead of
  writing `{}` to the cache and crashing two steps later on a
  meaningless statistics error.

Either way, the committed cache is no longer at risk of being
overwritten by an empty fetch.

## 6. Yes / no

* **Root cause identified?** **Yes.** Empty Firebase result
  silently overwrote the committed cache; unguarded
  `statistics.mean` downstream turned it into an opaque stats
  error.
* **Fix implemented?** **Yes.** Fetch script fails fast on
  empty; scoring main() fails fast on empty cache; report
  generator is now empty-safe; workflow logs row counts at
  each boundary.
* **Safe to re-run fetch-and-score now?** **Yes** — safe in
  the sense that a re-run can no longer corrupt the cache or
  mask the root cause. Whether it will *succeed* depends on
  the upstream RTDB; if the RTDB is still empty the run will
  abort with exit 3 and a diagnostic instead of exit 1 with a
  StatisticsError.
* **Does recalibration still need to wait for TripAdvisor
  completion?** **Yes.** TripAdvisor is Blocker 3 of the
  seven-blocker cutover plan
  (`DayDine-V4-Public-Cutover-Blockers.md`); recalibration
  (Blocker 5) is explicitly gated on Blockers 1 and 3. This
  prompt did not touch either blocker.

---

*End of diagnosis memo. No scoring / ranking / report data was
recomputed in this pass; only the failure path was hardened.*
