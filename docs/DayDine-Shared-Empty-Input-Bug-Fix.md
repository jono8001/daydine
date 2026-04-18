# DayDine — Shared Empty-Input Bug Fix

*Authored April 2026. Branch: `claude/verify-v4-scoring-spec-L4Cjv`.*
*Scope: make `fetch_and_score.yml` and `collect_tripadvisor.yml`
pass green on `main` again after both crashed on
`statistics.StatisticsError: mean requires at least one data
point`, exit 1. Not a redesign, not a recalibration, not a
cutover.*

---

## 1. Repo-wide search for every reachable mean/median call

Searched for `mean(`, `median(`, `statistics.mean`,
`statistics.median`, `np.mean`, `numpy.mean`, `np.median`,
`numpy.median` across the tree. Then for each hit, traced whether
it is reachable from the failing workflow paths. Expanded to
also cover `sum(...) / len(...)` since that's equivalent under
empty input. No numpy usage exists anywhere in the repo —
statistics module only.

### 1.1 Calls in scripts invoked by `fetch_and_score.yml`

| File | Line | Call | Status on `main` |
|---|---|---|---|
| `rcs_scoring_stratford.py` | 1622 | `statistics.mean(scores)` (build_summary) | **Guarded** (`if scores else 0`). |
| `rcs_scoring_stratford.py` | 1623 | `statistics.median(scores)` | **Guarded**. |
| `rcs_scoring_stratford.py` | 1635 | `statistics.mean(r["signals_available"] …)` | **Guarded**. |
| `rcs_scoring_stratford.py` | 1718 | `statistics.mean(r["signals_available"] …)` (print_results) | **Guarded**. |
| `rcs_scoring_stratford.py` | **1846** | `statistics.mean(ranked_scores)` (generate_report) | **UNGUARDED. Crashes.** |
| `rcs_scoring_stratford.py` | **1847** | `statistics.median(ranked_scores)` | **UNGUARDED. Crashes.** |
| `rcs_scoring_stratford.py` | 737 | `sum(d …)/len(divergences)` | Gated by `if len(sources) < 2: return …` — safe. |
| `rcs_scoring_stratford.py` | 1441 | `sum(aspect_vals)/len(aspect_vals)` | Gated by `if aspect_vals:` — safe. |
| `rcs_scoring_stratford.py` | 1444 | `sum(components)/len(components)` | Gated by `if not components: return None` — safe. |

### 1.2 Calls in scripts invoked by `collect_tripadvisor.yml`

Same scoring script, so all the `rcs_scoring_stratford.py`
findings above apply. Additional scripts in this path:

| File | Line | Call | Status on `main` |
|---|---|---|---|
| `.github/scripts/merge_enrichment.py` | 147 | `sum(ta_ratings)/len(ta_ratings)` | Gated by `if ta_ratings:` — safe. |
| `.github/scripts/collect_tripadvisor.py` | — | (no mean/median/avg calls) | — |
| `.github/scripts/merge_tripadvisor.py` | — | (no mean/median/avg calls) | — |
| `.github/scripts/fetch_firebase_stratford.py` | — | (no mean/median/avg calls) | — |

### 1.3 Calls not reachable from either workflow (for completeness)

`compare_v3_v4.py`, `calibrate_v4_customer.py`,
`.github/scripts/commercial_readiness_coverage.py`,
`operator_intelligence/v4_peer_benchmarks.py`, and everything
under `operator_intelligence/builders/` are all guarded
(`if xs else None` pattern) and none are invoked by either
failing workflow.

### 1.4 Conclusion

**Exactly two reachable unguarded statistics calls exist, and
they are the same two calls (lines 1846–1847 of
`rcs_scoring_stratford.py::generate_report`).** Both workflows
fail through that single downstream helper. The other 15+
statistical calls in the repo are already correctly guarded.

## 2. Exact failing call

```
rcs_scoring_stratford.py::generate_report
    line 1846: w(f"| Mean RCS | {statistics.mean(ranked_scores):.2f} |")
    line 1847: w(f"| Median RCS | {statistics.median(ranked_scores):.2f} |")
```

`ranked_scores` is derived at line 1809 as
`[r["rcs_final"] for r in ranked]`, where
`ranked = [r for r in scored if r["rank"] != ""]`. If every
scored record is classed as `Insufficient` or `Not Ranked` —
or if `scored` is empty because the loaded cache was empty —
`ranked_scores == []` and `statistics.mean([])` raises
`StatisticsError` with the user-reported message.

Reproduced locally by overwriting the cache with `{}` and
running `python rcs_scoring_stratford.py --from-cache`:
identical traceback, identical line number, identical exit
code (1).

## 3. Where Stratford data first becomes empty (per workflow)

### 3.1 `fetch_and_score.yml`

Order: `fetch_firebase_stratford.py` → scoring.

* Firebase RTDB returns an empty dict `{}` at the fetch step
  (the most plausible trigger — Firebase `null` would have
  crashed with `TypeError` on `len(None)` at line 14 of the
  fetch script, not the stats error we observed).
* `fetch_firebase_stratford.py` (pre-fix) silently overwrites
  the committed cache with `{}`.
* `rcs_scoring_stratford.py --from-cache` loads `{}`,
  `run_pipeline` produces `scored = []`, `apply_tiebreakers`
  produces `ranked = []`, `build_summary` succeeds (guarded),
  `generate_report` crashes at line 1846.

### 3.2 `collect_tripadvisor.yml`

Order: `fetch_firebase_stratford.py` → `merge_enrichment.py` →
`collect_tripadvisor.py` → `merge_tripadvisor.py` → scoring.

* Firebase returns empty → same path as above.
* `merge_enrichment.py` reads the empty cache, finds nothing
  to merge into (the `stratford_google_enrichment.json` side
  file has keys that don't exist in the empty establishments
  dict), and writes the cache back empty.
* `collect_tripadvisor.py` reads the empty cache, iterates
  over zero keys, writes an empty `stratford_tripadvisor.json`.
* `merge_tripadvisor.py` has nothing to merge.
* Scoring crashes at the same line as the first workflow.

**Both workflows fail at the same line in the same helper.
Single root cause, two entry paths.**

### 3.3 Why `enrich_and_score.yml` passed on the same commit

`enrich_and_score.yml` runs: `fetch_firebase_stratford.py` →
`enrich_google_stratford.py` → `merge_enrichment.py` → scoring.
For it to have produced commit `4fda283` it must have received
non-empty data at the fetch step. At some point between that
successful run and the later `fetch_and_score` /
`collect_tripadvisor` runs, the Firebase query began returning
empty. Three plausible upstream triggers (equally consistent
with the evidence from inside this sandbox — outbound HTTPS is
blocked so live verification is not possible):

1. The `la` indexOn rule on `daydine/establishments` was
   removed / reset (the `orderBy:"la"` query requires it;
   without it Firebase might return `{}` rather than 400,
   depending on rules).
2. The `la` field values drifted (e.g. to
   `"Stratford-upon-Avon"`) while the query still filters on
   `"Stratford-on-Avon"`.
3. The node was briefly wiped by an upstream ingestion job.

Any of the three would produce exactly the observed symptom
for `fetch_and_score` / `collect_tripadvisor` while leaving an
earlier `enrich_and_score` run untouched.

## 4. Real fix classification

**(a) AND (b):** missing defensive guards in the shared scoring
helper AND an upstream data-loading script that silently
accepts an empty response. Not (c) — the shared helper is
being invoked correctly by both workflows; the bug is entirely
in the helper + the fetch script. Not purely (a) because
masking the empty input with a guard alone would hide the real
problem.

## 5. What code changed

All changes are on branch `claude/verify-v4-scoring-spec-L4Cjv`
and target the failing path only. No V4 surface, no frontend,
no recalibration, no cutover-adjacent code is touched.

### 5.1 `.github/scripts/fetch_firebase_stratford.py`

* Handle Firebase `null` → normalise to `{}`.
* Reject non-dict responses (exit 2).
* Refuse to overwrite an existing committed cache with an empty
  object (exit 3). The old code happily wrote `{}`, destroying
  the last-known-good cache. Now the existing cache is
  preserved so a re-run with a healthy Firebase will succeed
  and a re-run with an unhealthy Firebase will fail noisily.
* Warn on zero CV-prefixed postcodes — early signal that the LA
  filter has drifted.
* Diagnostic names the three likely upstream causes.

### 5.2 `rcs_scoring_stratford.py`

* `main()`: fail fast (exit 4) when the loaded cache is empty
  or malformed. Message points at the fetch step explicitly.
* `generate_report()`: lines 1846/1847 (now 1874/1875) now
  render `—` instead of calling `statistics.mean([])` /
  `statistics.median([])`. Final belt-and-braces for any
  empty input that sneaks past the main() guard.

### 5.3 `.github/workflows/fetch_and_score.yml`

Row-count / file-existence logging at three boundaries:

* **Inspect cache before fetch** — shows the row count of the
  committed cache we're working from (or "absent").
* **Inspect cache after fetch** — prints post-fetch row count;
  emits `::error::` and exits 5 on zero rows (redundant with
  the fetch script's exit 3 but makes the failure visible in
  the GitHub Actions summary as opposed to buried in the
  script output).
* **Inspect scoring outputs** — prints CSV row count and the
  summary's `count / ranked / mean / median` so a reviewer can
  eyeball the result without downloading artefacts.
* `timeout-minutes: 15` added.

### 5.4 `.github/workflows/collect_tripadvisor.yml`

Row-count / file-existence logging at four boundaries:

* **Inspect cache before fetch** — same as fetch_and_score.
* **Inspect cache after fetch** — same as fetch_and_score.
* **Inspect TripAdvisor side file** — after `collect_tripadvisor.py`,
  prints side-file row count and matched count.
* **Inspect cache after TA merge** — after `merge_tripadvisor.py`,
  prints the row count and the count of records with
  `ta_present`; emits `::error::` and exits 6 on zero rows.
* **Inspect scoring outputs** — same as fetch_and_score.

### 5.5 No change made

* Scoring logic, band thresholds, weights, tiebreakers —
  untouched.
* `enrich_and_score.yml` — untouched (it passes today; giving
  it the same logging is out of scope for this operational
  debugging pass).
* Any V4 code — untouched.
* `index.html`, rankings JSON, methodology doc — untouched.

## 6. Verification performed locally

Both paths verified in the sandbox (no live Firebase — outbound
HTTPS is blocked from this environment, documented in
`DayDine-V4-Enrichment-Execution-Status.md`).

| Scenario | Behaviour |
|---|---|
| Scoring on the committed 210-row cache | 190 ranked, exit 0 — happy path unchanged. |
| Scoring on an empty cache (`{}`) | `ERROR: scoring input is empty or malformed (dict with 0 entries). Cache: …. Re-run the fetch step and verify it reports >0 rows.` exit **4**. |
| Scoring on bare FSA-only records (no Google enrichment) | 6 ranked / 193 insufficient / 11 non-food, exit 0 — still works without enrichment. |
| Reproduction of original `StatisticsError` with old scorer on empty cache | traceback at line 1846, exit **1** — identical to the CI failure. |
| Reproduction of the fix path with new scorer on empty cache | exit 4 with named diagnostic — root cause preserved, not masked. |

## 7. What should be re-run

In order:

1. **Merge this branch to `main`.** The feature branch has the
   complete fix; `main` does not yet. The workflows run against
   the commit of `main` in use when they are dispatched, so the
   fix only takes effect on `main` after the merge.
2. **Verify upstream Firebase is healthy.** Spot-check:
   * `firebase-rules.json` still declares
     `"indexOn": ["la", ...]` under `daydine/establishments`.
   * A known FHRSID (e.g. `502816` "Loxleys") is present at
     `daydine/establishments/502816` with
     `"la": "Stratford-on-Avon"`.
   * Optional but recommended: a one-line probe of the fetch
     URL that confirms ≥200 rows come back.
3. **Re-run `fetch_and_score.yml` on `main`.** Expected outcome
   if Firebase is healthy: green, with the new inspect steps
   printing pre-fetch, post-fetch, and scoring-output row
   counts. If Firebase is still empty: **fails fast at step
   "Fetch from Firebase RTDB" with exit 3 and a diagnostic
   naming the three likely causes**, instead of crashing at
   scoring with a meaningless stats error.
4. **Re-run `collect_tripadvisor.yml` on `main`.** Same
   expectation; additionally the TA side-file and post-merge
   steps will print non-zero match / row counts if TA
   collection landed.
5. Only after both are green does recalibration become eligible
   — and it is still gated on the underlying TripAdvisor
   completion (public-cutover Blocker 3 /
   `DayDine-V4-Public-Cutover-Blockers.md`).

## 8. Resolution criteria

The issue is considered **resolved** when, on `main`:

* `fetch_and_score.yml` completes green with the inspect steps
  showing non-zero post-fetch and non-zero CSV row counts.
* `collect_tripadvisor.yml` completes green with the inspect
  steps showing non-zero post-fetch and non-zero post-merge row
  counts.
* No `StatisticsError` appears in either run log.

If Firebase is still returning empty and one of the fail-fast
guards (exit 2 / 3 / 4 / 5 / 6) triggers, the workflow has done
its job: it has surfaced the real cause. That is also an
acceptable outcome per the user's "preserve the real root cause
instead of masking it" instruction — but it is **not** the
green-workflow resolution. Green requires that the upstream
Firebase state is healthy.

## 9. Yes / no

* **Exact failing mean call identified?** **Yes** —
  `rcs_scoring_stratford.py:1846` (and 1847 for median), in
  `generate_report`, computing over an empty `ranked_scores`
  list.
* **Shared root cause?** **Yes** — both workflows fail through
  the same helper (`rcs_scoring_stratford.py`), at the same
  line, via the same upstream emptiness.
* **Upstream emptiness fixed?** **Partial.** The *code path*
  that silently wrote an empty cache is fixed (fetch script
  now fails fast and preserves the existing cache). The
  *live Firebase state* that prompted the empties is
  out-of-sandbox and must be checked operationally before
  re-run.
* **Defensive guards added?** **Yes** — `main()` guard on
  empty cache (exit 4); `generate_report` empty-safe for the
  two previously-unguarded stats calls; workflow-level inspect
  steps at every boundary that can go empty.
* **Safe to re-run `fetch_and_score.yml`?** **Yes** —
  conditional on the merge to `main` and a quick Firebase
  health check.
* **Safe to re-run `collect_tripadvisor.yml`?** **Yes** —
  same condition.
* **Can recalibration proceed after both succeed?** **No.**
  Recalibration is Blocker 5; it is gated on Blocker 3
  (TripAdvisor completion) per the cutover plan. Green
  workflows don't lift Blocker 5 — they just let the engine
  run against current data.

---

*End of shared-bug memo. Code changes are tightly scoped to the
two failing paths and one shared helper; no scoring semantics
changed.*
