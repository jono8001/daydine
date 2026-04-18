# DayDine V4 — Scheduled Workflow Status

*Authored April 2026. Branch: `claude/verify-v4-scoring-spec-L4Cjv`.*
*Scope: what the new `score_v4.yml` workflow does, what it does
not do, how it fits the wider public-cutover plan, and what
remains blocked.*

---

## 1. What was added

A new GitHub Actions workflow at
`.github/workflows/score_v4.yml`.

The workflow regenerates the V4 scoring + operator-report surface
on a weekly cron (Mondays 06:00 UTC) and on manual dispatch, then
uploads the outputs as a retained artefact bundle. It does not
commit to the repository and it does not touch any V3.4 or live
frontend surface.

No other file was changed in this pass. The V4 scoring engine,
entity resolver, sample generator, guardrail tests, report layer,
and CI gate (`v4_report_checks.yml`) are unchanged.

---

## 2. What the workflow does

| Step | Script | Purpose |
|---|---|---|
| 1 | `.github/scripts/resolve_entities.py` | Apply alias table; flag duplicate-GPID groups; regenerate `stratford_entity_resolution_report.json`. |
| 2 | `rcs_scoring_v4.py` | Score 210 trial venues against the V4 spec; emit `stratford_rcs_v4_scores.{json,csv}`. |
| 3 | `compare_v3_v4.py` | Side-by-side V3.4 vs V4 comparison (distribution, movers, sanity). Non-blocking. |
| 4 | `commercial_readiness_coverage.py` | CR sub-signal coverage report. Non-blocking. |
| 5 | `tripadvisor_coverage.py` | TA coverage report. Non-blocking. |
| 6 | `scripts/generate_v4_samples.py` | Regenerate the seven canonical operator samples with history disabled (reproducible). |
| 7 | `tests.test_v4_report_guardrails` | 24-test narrative / structural / per-class guardrail suite. Blocking. |
| 8 | `tests.test_v4_history` | 9-test recommendation-history lifecycle. Blocking. |
| 9 | `tests.test_v4_legacy_boundary` | 5-test V4 ↔ V3.4 import-boundary check. Blocking. |
| 10 | inline python | Non-blocking drift check vs committed sample baseline. Warning only. |
| 11 | inline python | Sample QA aggregate — must be 0 errors / 0 warnings. Blocking. |
| 12 | `actions/upload-artifact@v4` | Uploads the full V4 output bundle as `daydine-v4-artifacts-<run_id>` with 30-day retention. |

All steps run on `ubuntu-latest` with Python 3.11. Total expected
runtime < 3 minutes.

### 2.1 Artefact bundle

Uploaded under the name `daydine-v4-artifacts-<run_id>`:

* `stratford_rcs_v4_scores.json`
* `stratford_rcs_v4_scores.csv`
* `samples/v4/monthly/**`
* `stratford_entity_resolution_report.json`
* `stratford_v3_v4_comparison.csv`
* `stratford_v3_v4_distribution.json`
* `stratford_v3_v4_movers.json`
* `stratford_v3_v4_sanity.json`
* `stratford_commercial_readiness_coverage.json`
* `stratford_tripadvisor_coverage.json`

---

## 3. What the workflow does NOT do

1. **No external API calls.** The workflow does not talk to
   Google Places, the FSA API, TripAdvisor, Apify, or Companies
   House. Enrichment is explicitly owned by other workflows
   (`enrich_and_score.yml`, `collect_tripadvisor.yml`,
   `full_pipeline.yml`) which require secrets this workflow
   does not read.
2. **No commits.** V4 outputs are intentionally surfaced as
   artefacts, not committed. This prevents scheduled runs from
   silently overwriting the committed V4 baseline on the feature
   branch (or main) and removes any implication of public
   cutover.
3. **No V3.4 or frontend mutation.** The workflow never touches
   `stratford_rcs_scores.csv`, the rankings JSON consumed by
   `index.html`, `firebase-rules.json`, or `vercel.json`. The
   live `daydine.vercel.app` surface continues to read V3.4 data
   until a deliberate cutover prompt.
4. **Not a cutover signal.** Artefact availability is not a
   promotion. The blocker list in
   `docs/DayDine-V4-Public-Cutover-Blockers.md` remains the
   source of truth for what still gates cutover.

---

## 4. Dependencies

### 4.1 Secrets / env vars

None. The workflow is deliberately self-contained.

### 4.2 Input files (must exist at run time)

| File | Source |
|---|---|
| `stratford_establishments.json` | Committed trial dataset. |
| `stratford_menus.json` | Committed. Optional but expected. |
| `stratford_editorial.json` | Committed. Optional but expected. |
| `data/entity_aliases.json` | Committed. Consumed by `resolve_entities.py`. |

### 4.3 Python

Python 3.11; standard library only. No `requirements.txt` is
added on the V4 path, matching the pattern set by
`v4_report_checks.yml`.

---

## 5. Trigger model and safety

| Trigger | When | Effect |
|---|---|---|
| `schedule` — `0 6 * * 1` | Mondays 06:00 UTC | Full run against the default branch; artefacts retained 30 days. |
| `workflow_dispatch` | Manual, any branch | Full run on the selected ref. Optional `reason` input is logged for audit only. |

A `concurrency` group (`v4-scheduled-scoring`,
`cancel-in-progress: false`) prevents overlapping runs stomping
on each other without aborting an already-running run.

Because nothing is written back to the repository, there is no
race with `v4_report_checks.yml` (the blocking guardrail) or with
any enrichment workflow.

---

## 6. Failure behaviour

| Step | Policy |
|---|---|
| Entity resolution + V4 scoring + sample regen | **Hard fail.** Any exception aborts the job. |
| V3 vs V4 comparison, coverage reports | **Non-blocking** (`continue-on-error: true`). Missing optional inputs (e.g., no TripAdvisor pass yet) should not fail the scoring job. |
| Guardrail / history / boundary tests | **Hard fail.** |
| Sample reproducibility | **Non-blocking warn.** The equivalent blocking check lives in `v4_report_checks.yml`. Scheduled drift is surfaced via `::warning::` so it is visible in the run log and artefacts without failing the weekly job. |
| Sample QA aggregate | **Hard fail.** Any `errors` or `warnings` in a `*_qa.json` fails the job. |
| Artefact upload | **Hard fail** on no-files-found. |

---

## 7. Fit into the wider cutover path

The `DayDine-V4-Public-Cutover-Blockers.md` memo identifies seven
blockers between the current state and public cutover. This
workflow addresses **Blocker 6 (scheduled V4 workflow)** only.
It is deliberately a narrow addition:

1. **Blocker 1 (live Google enrichment)** — runs in
   `enrich_and_score.yml` / `full_pipeline.yml`, which hold the
   Google Places secret. `score_v4.yml` consumes whatever is
   already committed.
2. **Blocker 2 (entity resolution)** — already committed.
   `score_v4.yml` re-runs the resolver each execution so changes
   to `data/entity_aliases.json` flow into the V4 score and
   samples immediately.
3. **Blocker 3 (live TripAdvisor)** — not handled here. When TA
   passes land and commit updated records, `score_v4.yml` will
   pick them up on the next run.
4. **Blocker 4 (duplicate-GPID disambiguation)** — partial;
   committed. `resolve_entities.py` now propagates
   `disambiguation_type`, `reason_for_operator`, `resolution_path`
   and site onto ambiguous records; the V4 report surfaces
   these.
5. **Blocker 5 (post-enrichment recalibration)** — blocked on
   Blockers 1 and 3. This workflow does NOT recalibrate; it runs
   the engine as-committed.
6. **Blocker 6 (this blocker)** — cleared by the workflow in
   this pass. A weekly scheduled V4 regeneration now exists.
7. **Blocker 7 (public cutover flow)** — future prompt. When
   the cutover flow is designed, `score_v4.yml` is the
   logical place to hang the promote step (artefact → branch
   promotion or bucket push). The artefact-only design here
   leaves that decision open.

### 7.1 Upgrade path

When a future prompt unblocks enrichment + recalibration and is
ready to promote, the natural evolution of this workflow is one
or more of the following — none are implemented in this pass:

* Prepend enrichment steps (Google + FSA augment + TA) guarded
  by `if: secrets.GOOGLE_PLACES_API_KEY != ''` etc.
* Replace or supplement the artefact upload with a commit to a
  dedicated branch (e.g., `v4/scheduled-refresh`) that a
  cutover PR can inspect.
* Trigger downstream frontend build / cache invalidation once
  the live cutover is live.

None of these are appropriate until the upstream blockers close.

---

## 8. What remains blocked

| Concern | Status |
|---|---|
| Live Google enrichment | Blocker 1 — not addressed here. |
| Live TripAdvisor coverage | Blocker 3 — not addressed here. |
| Post-enrichment recalibration | Blocker 5 — blocked on 1 + 3. |
| Public leaderboard / frontend cutover | Blocker 7 — not addressed here and explicitly out of scope for this prompt. |
| Operator report promotion surface | Future decision — artefact today. |

---

## 9. Yes / no answers

* **Is a scheduled V4 workflow now in the repo?** **Yes** —
  `.github/workflows/score_v4.yml`.
* **Safe to merge before enrichment / cutover?** **Yes.** The
  workflow never commits, never calls external APIs, never
  touches V3.4 or the live frontend, and its blocking steps are
  all either existing tests or internal regenerations.
* **Does it imply the public cutover is done?** **No.** It is
  deliberately artefact-only and documented as such.
* **What still needs to happen outside Claude Code before
  recalibration?** Blocker 1 (Google enrichment in a runner that
  has `GOOGLE_PLACES_API_KEY` and outbound HTTPS) and Blocker 3
  (TripAdvisor collection with `APIFY_TOKEN`). Both are already
  scripted; neither is runnable from the sandbox this prompt
  executed in.
* **Next correct prompt inside Claude Code?** Blocker 7: design
  the public cutover flow (branch promotion, frontend data
  switch, rollback plan). Blockers 1, 3, 5 require a runner with
  secrets + network.

---

*End of workflow-status memo. The workflow is operationally
additive; no existing surface is altered by this pass.*
