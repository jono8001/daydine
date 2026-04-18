# V3.4 Legacy Quarantine Note

*Authored April 2026. Branch: `claude/verify-v4-scoring-spec-L4Cjv`.*
*Scope: internal. Does not announce any public-facing change.*

> **What this note is for.** After the V4 migration and pilot-hardening
> work completed on this branch, V3.4 scoring and reporting code
> remains on disk. This note explains what was quarantined, what was
> deliberately left in place, and the conditions under which the
> legacy files become safe to delete. **Nothing has been deleted.**
> **Nothing has been moved.** The quarantine is enforced by
> per-file banners plus a CI-gated boundary test.

---

## 1. Quarantine approach

We chose the least-destructive option that still prevents accidental
re-use of V3.4 code in the active V4 path:

1. **Per-file banner.** A visible `LEGACY (V3.4)` comment block
   immediately follows the module docstring of every V3.4-only file.
   Any engineer opening the file sees a top-of-body warning naming
   the active V4 replacement and pointing at this memo.
2. **Single source of truth for the boundary.**
   `operator_intelligence/legacy_boundary.py` enumerates
   - `LEGACY_MODULES`     — quarantined V3.4 scoring / reporting
   - `SHARED_NARRATIVE_MODULES` — V3.4-origin text helpers the V4
     report layer reuses as narrative / profile-only
   - `ALLOWED_V4_TO_LEGACY_IMPORTS` — explicit allow-list of
     legitimate V4 → V3.4 wrapper imports (currently one entry:
     `v4_demand_capture_audit` wraps `demand_capture_audit`).
3. **CI-gated boundary test.**
   `tests/test_v4_legacy_boundary.py` parses every V4 source file
   (and the sample runner) with the stdlib `ast` module and fails
   the build if any import of a `LEGACY_MODULES` module is not in
   the allow-list. It also catches stale allow-list entries and
   dead-module registry entries.
4. **No file moves / no renames / no deletions.** Rollback and
   comparison paths continue to work unchanged. The V3.4 parallel
   generator, the `compare_v3_v4.py` comparison harness, and the
   existing GitHub Actions workflows that reference V3.4 scripts
   are all untouched.

### Why not move the files to a `legacy/` directory?

Moving files would:
- Break `compare_v3_v4.py` imports (it reads V3.4 output CSVs but
  not V3.4 modules directly, so this is actually survivable — but
  it is still an avoidable risk).
- Break any `.github/workflows/*.yml` file that references a V3.4
  script path. Workflows are still needed for data collection
  (TripAdvisor, Google enrichment) even though they don't score.
- Invalidate every git blame line for those files without a
  semantic reason.
- Force a second quarantine pass when the time comes to delete —
  the files would have to be moved again or deleted from their new
  location.

A banner + boundary test achieves the same "don't re-use this"
effect with zero risk to rollback.

---

## 2. What was quarantined

All files listed below now carry the `LEGACY (V3.4)` banner.
`operator_intelligence/legacy_boundary.py::LEGACY_MODULES` is the
authoritative dotted list.

### 2.1 Root-level V3.4 entry points

| File | Role |
|---|---|
| `rcs_scoring_stratford.py` | V3.4 scoring engine |
| `restaurant_operator_intelligence.py` | V3.4 report orchestrator |

### 2.2 V3.4 operator-intelligence modules

| File | Role |
|---|---|
| `operator_intelligence/recommendations.py` | V3.4 recommendation generator |
| `operator_intelligence/implementation_framework.py` | V3.4 action-card builder |
| `operator_intelligence/report_generator.py` | V3.4 report generator |
| `operator_intelligence/report_spec.py` | V3.4 report spec |
| `operator_intelligence/scorecard.py` | V3.4 5-dimension scorecard |
| `operator_intelligence/peer_benchmarking.py` | V3.4 peer benchmarks |
| `operator_intelligence/commercial_estimates.py` | V3.4 `gpl`-keyed sizing |
| `operator_intelligence/evidence_base.py` | V3.4 evidence assembly |
| `operator_intelligence/fsa_intelligence.py` | V3.4 Trust decomposition |
| `operator_intelligence/consistency_checker.py` | V3.4 consistency rules |
| `operator_intelligence/integrity_checks.py` | V3.4 integrity check rules |
| `operator_intelligence/competitor_strategy.py` | V3.4 competitor framing |
| `operator_intelligence/category_validation.py` | V3.4 category inference |
| `operator_intelligence/seasonal_context.py` | V3.4 seasonal context helper |

### 2.3 V3.4 section builders

All 15 files under `operator_intelligence/builders/`:
`actions_tracker.py`, `data_basis.py`, `diagnosis.py`,
`event_forecast.py`, `exec_summary.py`, `financial_impact.py`,
`long_form.py`, `menu_intelligence.py`, `monthly_movement.py`,
`review_section.py`, `risk_alerts.py`, `scorecard.py`,
`segment_section.py`, `trust_detail.py`, `venue_identity.py`.

Total: **32 files banned with the LEGACY banner**, all listed in
`legacy_boundary.LEGACY_MODULES`.

---

## 3. What was left in place (and why)

### 3.1 Shared narrative helpers — intentional V3.4 / V4 reuse

Five modules have V3.4 origin but are re-used by the V4 report layer
as **text / theme / profile-only** sources. They are **not**
quarantined; they carry a `SHARED — NARRATIVE / PROFILE-ONLY HELPER`
banner instead. V4 consumes their output as narrative, never as a
score input.

| File | Consumers |
|---|---|
| `operator_intelligence/review_analysis.py` | V4 Profile Narrative |
| `operator_intelligence/review_delta.py` | V4 Profile Narrative |
| `operator_intelligence/segment_analysis.py` | V4 Profile Narrative |
| `operator_intelligence/risk_detection.py` | V4 Operational & Risk Alerts |
| `operator_intelligence/demand_capture_audit.py` | wrapped by `v4_demand_capture_audit` |

Enumerated in `legacy_boundary.SHARED_NARRATIVE_MODULES`.

### 3.2 Rollback / comparison paths — intentionally untouched

Three items intentionally keep a live dependency on V3.4 code and
stay untouched:

- **`compare_v3_v4.py`** — reads V3.4 scoring outputs
  (`stratford_rcs_scores.csv`) alongside V4 outputs
  (`stratford_rcs_v4_scores.json`) to produce cross-version deltas.
  Essential rollback-support tooling.
- **V3.4 scoring outputs** under the repo root
  (`stratford_rcs_scores.csv`, `stratford_rcs_summary.json`,
  `stratford_rcs_report.md`) — retained as comparison baseline.
- **`.github/workflows/*.yml`** — several workflows still reference
  V3.4 scripts for data-collection pipelines
  (TripAdvisor / Google enrichment / FSA augmentation). These
  pipelines are scoring-engine-neutral; they collect public data
  that both V3.4 and V4 consume. Touching them is out of scope for
  the quarantine pass.

### 3.3 The one legitimate V4 → V3.4 wrapper

`operator_intelligence/v4_demand_capture_audit.py` imports
`operator_intelligence.demand_capture_audit` — the V3.4 7-dimension
audit module. The V4 wrapper classifies each dimension as CR-linked
vs diagnostic, enforces V4 framing at the render boundary, and
drops the V3.4 `scorecard` stub the caller used to construct. The
underlying text-only heuristic helpers run unchanged because a full
V4-native rewrite would add no commercial value today.

This import is on the `ALLOWED_V4_TO_LEGACY_IMPORTS` allow-list. The
boundary test fails if any other V4 file tries to import any
`LEGACY_MODULES` entry without a matching allow-list row.

---

## 4. What still intentionally references legacy code

After the quarantine pass, the following V3.4 dependencies are
intentional and remain:

| Reference | Caller | Reason |
|---|---|---|
| `operator_intelligence.demand_capture_audit` | `operator_intelligence.v4_demand_capture_audit` | V4 wrapper (allow-list entry) |
| V3.4 report generator + builders | V3.4 parallel report runs | Rollback-support; V3.4 continues to write `outputs/monthly/` |
| `stratford_rcs_scores.csv` + V3.4 summary | `compare_v3_v4.py` | Cross-version comparison harness |
| V3.4-origin narrative helpers (`review_analysis`, `review_delta`, `segment_analysis`, `risk_detection`) | V4 report generator — narrative-only | Shared helpers; explicitly NOT quarantined; SHARED banner |
| Legacy rec history at `history/recommendations/` | V3.4 generator only | V4 writes to a separate `history/v4_recommendations/` |
| `.github/workflows/*.yml` | Data-collection pipelines | Scoring-engine-neutral; V3.4 referenced incidentally |

Everything else has been reviewed and confirmed to have no live V4
dependency.

---

## 5. What active V4 paths still depend on legacy code

**Nothing beyond the single intentional wrapper.** The
`tests/test_v4_legacy_boundary.py` test enforces this.

A grep of every V4 file confirms it:

```
$ grep -rE "^(from|import) operator_intelligence" \
    operator_intelligence/v4_*.py \
    scripts/generate_v4_samples.py \
    tests/test_v4_*.py | grep -v "operator_intelligence\.v4_"

operator_intelligence/v4_demand_capture_audit.py:4:  A V4-native wrapper over `operator_intelligence.demand_capture_audit` …
operator_intelligence/v4_demand_capture_audit.py:70: from operator_intelligence.demand_capture_audit import (
tests/test_v4_legacy_boundary.py:28: from operator_intelligence.legacy_boundary import …
```

The only cross-boundary import is the documented wrapper; the
boundary-test file itself legitimately imports the registry it
depends on.

---

## 6. Conditions under which legacy files become safe to delete

A file in `LEGACY_MODULES` becomes safe to delete when **all** of
the following are true:

1. **Public leaderboard cutover is complete.** The public site
   (`rankings.html`, `index.html`, `methodology.html`,
   `assets/rankings/*.json`) reads from V4, not V3.4, and the change
   has been stable for at least one full reporting cycle.
2. **Rollback window has closed.** The agreed observation window
   (typically one month post-cutover) has elapsed with no
   regressions demanding a V3.4 rerun.
3. **`compare_v3_v4.py` has been retired or repointed.** If the
   comparison harness is still useful, it should be rewritten to
   read archived V3.4 outputs rather than live-invoke the V3.4
   engine.
4. **V3.4 outputs under `outputs/monthly/` are no longer being
   written** by any scheduled workflow. The V3.4 parallel generator
   path must be unplugged.
5. **No workflow under `.github/workflows/` invokes a V3.4 script**
   that depends on the module in question. The data-collection
   workflows will need separate scoring-engine-agnostic updates
   first.
6. **The boundary test still passes** after the module is removed
   from `LEGACY_MODULES` — no V4 file has sprouted a dependency.

When those conditions are met, deletion is a one-commit operation:
remove the file, remove its entry from `LEGACY_MODULES`, update
`ALLOWED_V4_TO_LEGACY_IMPORTS` if needed. The `SHARED_NARRATIVE_MODULES`
set is outside this scope — those modules stay regardless of V3.4
retirement.

---

## 7. Related docs

| Topic | File |
|---|---|
| V4 scoring spec | `docs/DayDine-V4-Scoring-Spec.md` |
| V4 report spec | `docs/DayDine-V4-Report-Spec.md` |
| V4 migration note | `docs/DayDine-V4-Migration-Note.md` |
| V4 readiness memo | `docs/DayDine-V4-Readiness-For-Stack-B.md` |
| V4 report handoff | `docs/DayDine-V4-Report-Handoff.md` |
| V4 pilot-readiness memo | `docs/DayDine-V4-Pilot-Readiness.md` |
| V3.4 → V4 comparison harness | `compare_v3_v4.py` |
| V3.4 → V4 comparison assessment | `docs/DayDine-V4-Scoring-Comparison.md` |

---

*End of quarantine note. Nothing was deleted, nothing was moved.*
