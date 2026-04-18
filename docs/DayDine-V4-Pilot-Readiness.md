# DayDine V4 Operator Report — Pilot Readiness Memo

*Authored April 2026. Branch: `claude/verify-v4-scoring-spec-L4Cjv`.*
*Scope: V4 operator report layer only. Public leaderboard, frontend,
and public methodology page are out of scope and remain deferred.*

> **Non-goals repeated for clarity.** This memo does not certify public
> cutover. It does not declare the public methodology page final. It
> does not make any claim about the consumer site or the public
> rankings JSON. Those surfaces continue to run on V3.4.

---

## Final verdict

**PILOT READY WITH MINOR WARNINGS**

The V4 operator report is ready to be put in front of a small,
supervised set of pilot operators. Three minor warnings (§4 below)
are tracked but do not block supervised pilot use. Commercial
publication remains gated on the data-coverage / recalibration items
tracked in the existing Stack-A status docs and is explicitly not
certified here.

---

## 1. What pilot-hardening completed

Seven discrete workstreams landed on this branch, each committed
separately and pushed to `origin/claude/verify-v4-scoring-spec-L4Cjv`:

| Workstream | Commit prefix | Outcome |
|---|---|---|
| V4 report data model + generator + spec + guardrail tests (B5) | `1fd4bf7` | Five rendering modes orchestrated cleanly; 18-section shell for Rankable-*; compact profile stub / closure notice; 24-test guardrail suite |
| V4 report guardrail tightening + narrative discipline + financial-impact rules (B5.5) | `22ec392` | 17 regex guardrails across 8 concern groups; per-class content rules; FI confidence-label discipline; wording helpers |
| Samples assessment + post-fix pass (B5 post-fix) | `1c66dde` | Five Must-fix items from the samples assessment closed: temp-closed league leak defensively overridden; Directional-C over-gating corrected; D-to-C-to-B unblock ladder; Directional-C FI canonical fallback; Closed Evidence Appendix note |
| Handoff memo + drift cleanup | `5b85827` | `DayDine-V4-Report-Handoff.md` landed; methodology page banner softened; two stale numbers refreshed |
| Recommendation-layer migration to V4 (B6) | `59fa0d1` | V4-native `v4_recommendations.py` + `v4_action_cards.py`; Management Priorities / Watch List / WNTD / Implementation Framework populated with V4-evidence-anchored content |
| `_dimension_to_component` shim removed end-to-end | `8d886b0` | Forward map deleted; reverse shim deleted; all three fallback call sites replaced; V4 path has no V3.4 dimension codes anywhere |
| V4-aware demand-capture audit | `8375e49` | 7 dimensions classified as CR-linked (2) or diagnostic (5); clean two-block render; V3.4 scorecard-stub shim removed; pre-existing empty-`note` column bug fixed |
| FI tolerance + penalty registry + segment class-demote | `47d6a26` | Range-width tolerance helper; structured `PENALTY_REGISTRY` covering every engine code; Directional-C segment demotion to label + count only; 15-review global minimum |
| CI wiring + this memo | *this commit* | `.github/workflows/v4_report_checks.yml` runs tests + regenerates samples + verifies reproducibility + asserts clean QA on every PR touching V4 report code |

---

## 2. Pilot-readiness checklist

Answering each of the prompt's questions explicitly:

### 2.1 Are recommendation sections meaningfully populated?

**Yes.** Verified across all seven canonical samples.

- **Rankable-A / B / temp_closed** (Vintner / Lambs / Loxleys /
  Opposition): Management Priorities render 1–3 V4-evidence-anchored
  priorities with rationale, evidence anchors, expected upside, and
  V4 component targeting. Implementation Framework table renders
  action cards with target date, cost band, success measure, next
  milestone, owner guidance. Watch List and What Not to Do populate
  from the V4 recs generator's watch / ignore output.
- **Directional-C** (Soma): Management Priorities lead with an
  "Unblock to rankable" narrative (entity disambiguation), followed
  by subsequent priorities renumbered from 2. Entity rec is deduped
  so it doesn't appear twice.
- **Profile-only-D / Closed** (Roebuck / Arrow Mill): these sections
  are cleanly suppressed by the mode orchestrator per spec §5.10 /
  §5.14. Not an "empty render" — absent sections.

Spot-check of the Vintner Management Priorities block shows:

```
### Priority 1: Publish a reachable phone number or booking link [FIX | NEW]

The booking / contact path sub-signal carries 25% of the Commercial
Readiness component weight and is currently absent.

**Evidence:** No phone / reservation_url / reservable observed.

**Expected upside:** adds 25% of the Commercial Readiness component
once a contact path publishes.

*Targets component: Commercial Readiness. V4 components feed the
headline — this priority is how the score moves in the direction
the observable evidence supports. (No specific score-movement
number is forecast.)*
```

Each priority maps back to a V4 field or cap/penalty code via the
evidence anchors. No V3-era dimension talk; no sentiment / photo /
social as a score driver.

### 2.2 Is the shim removed / reduced?

**Removed end-to-end** (commit `8d886b0`). The `_dimension_to_component`
forward / reverse bridge that translated V3.4 dimension codes into V4
component names is gone. V4 recommendations emit `targets_component`
directly and V4 renderers read it directly via a single
`_component_for(rec)` helper. A grep sweep confirmed the only
remaining `dimension` references in the V4 files are unrelated:
the Demand Capture Audit 7-dimension table (different concept) and
the peer-benchmark ring wrapper (`ring.get("dimensions")`). Neither
is a V3.4-scorecard reference.

### 2.3 Is the demand-capture audit V4-aware?

**Yes** (commit `8375e49`). The audit's seven dimensions are now
explicitly classified:

- **CR-linked** (two): Booking Friction → CR booking / contact path
  sub-signal; Menu Visibility → CR menu online sub-signal. Rendered
  in a block that names the CR sub-signal each explains.
- **Diagnostic** (five): CTA Clarity, Photo Mix & Quality,
  Proposition Clarity, Mobile Usability, Promise vs Path. Rendered
  in a separate block that explicitly states these are not V4 score
  inputs and that V4 scoring does not consume place types, photo
  count, price level, proposition framing, mobile usability, or
  listing-vs-reality contradictions (spec §2.3 / §5.3).

The V3.4 `scorecard_stub` that the V4 generator used to construct
for this call is gone. The `finding` column (which previously
rendered as empty because the code read `note` instead) now
populates correctly.

### 2.4 Is the Financial Impact logic hardened enough?

**Yes** (commits `47d6a26` plus the prior post-fix pass).

- **CR-score-driven sizing.** `_fi_estimate` is anchored on the
  Commercial Readiness score and the Customer Validation review
  volume (log-scale multiplier). `gpl` (price level) is demoted to
  a ±25% weak prior. Vintner and Lambs now produce distinct ranges
  (£240–£720 vs £250–£760) rather than the identical
  `gpl`-driven £180–£1,350 they produced pre-B5-post-fix.
- **Confidence labels are mandatory** when figures render. High /
  Moderate / Low tiers have distinct criteria; `None` forces the
  canonical fallback wording (`FINANCIAL_IMPACT_FALLBACK_THIN` or
  `_DIRECTIONAL`). Guardrail `GUARD_FI_CONFIDENCE_LABEL_MISSING`
  fails the build if a section renders figures without a label.
- **Range-width tolerance.** New `financial_impact_range_check(low,
  high, confidence)` helper scores every rendered range against
  per-tier bounds (High: ratio 2.0–4.0, min spread £400; Moderate:
  2.0–5.0 / £200; Low: 1.8–6.0 / £100). Emits one of five verdicts:
  `within` / `narrow` / `wide` / `tiny_spread` / `no_range`. A
  tolerance line renders in every figure-path FI section. Current
  samples all show `within the expected band`; drift is visible at
  render time, not just in the guardrail log.
- **False-precision guardrails.** `GUARD_FI_PRECISE_POUND_FIGURE`,
  `GUARD_FI_BARE_POUND_FIGURE` (with diagnostic-keyword exemption
  for the tolerance line's "spread £N"), `GUARD_FI_ROI_WITHOUT_CAVEAT`,
  `GUARD_FI_SPECIFIC_SCORE_MOVEMENT`, and
  `GUARD_FI_INDUSTRY_RATE_AS_OBSERVED` catch any regression toward
  overclaim.

### 2.5 Are CI guardrails in place?

**Yes** (this commit). `.github/workflows/v4_report_checks.yml`
runs on every push and pull request that touches the V4 report code
or its inputs. Four gates:

1. **Guardrail test suite** — `python -m tests.test_v4_report_guardrails`.
   All 24 tests must pass; any failure blocks merge.
2. **Sample regeneration** — `python scripts/generate_v4_samples.py`.
   Must run cleanly against the committed Stratford data without
   network access.
3. **Reproducibility check** — the regenerated
   `samples/v4/monthly/_summary_2026-04.json` is `git diff`'d
   against the committed baseline. Any drift fails the build and
   prints the diff in the CI log. If the drift is intentional the
   reviewer updates the committed samples deliberately.
4. **End-to-end QA aggregate** — every `*_qa.json` must show zero
   errors and zero warnings. The guardrail test suite covers
   rule-level behaviour; this gate catches whole-pipeline drift.

Locally, all four gates currently pass:

```
Ran 24 tests — 0 failures.
Wrote 7 samples to samples/v4/monthly.
reproducibility OK (summary unchanged)
All sample QAs: 0 errors, 0 warnings across 7 samples.
```

### 2.6 Is the report sample set reproducible?

**Yes.** `scripts/generate_v4_samples.py` writes deterministic output
keyed on the committed Stratford data (`stratford_establishments.json`
+ `stratford_rcs_v4_scores.json` + side inputs). Two consecutive runs
produce byte-identical output. The CI reproducibility gate enforces
that every push preserves this property.

---

## 3. What the pilot reader will see

For each of the five evidence/rankability classes, the pilot sample
set under `samples/v4/monthly/` provides a canonical example:

| Class | Sample | Mode | Score | Guardrails |
|---|---|---:|---:|---|
| Rankable-A | Vintner Wine Bar | `rankable_a` | 8.496 | 0 errors, 0 warnings |
| Rankable-B | Lambs | `rankable_b` | 8.939 | 0 errors, 0 warnings |
| Rankable-B | Loxleys | `rankable_b` | 8.772 | 0 errors, 0 warnings |
| Directional-C | Soma (ambiguous entity) | `directional_c` | 8.824 | 0 errors, 0 warnings |
| Profile-only-D | The Roebuck Inn Alcester | `profile_only_d` | — | 0 errors, 0 warnings |
| Closed (synthetic) | Arrow Mill | `closed` | — | 0 errors, 0 warnings |
| Temp-closed (synthetic) | The Opposition | `temp_closed` | 8.895 | 0 errors, 0 warnings |

All seven samples carry:

- **V4-native score card** — three components + optional distinction
  modifier, compact decision trace with penalty explanations.
- **Entity-match status** surfaced before commercial prose; ambiguous
  entities name the conflicting FHRSIDs.
- **Profile Narrative** flagged "narrative only — not a score input"
  on every subsection that consumes review text / segments / menu.
- **Financial Impact** confidence-labelled (or canonical fallback);
  tolerance line renders under the figures table where figures are
  present.
- **No sentiment-drives-score language**; no V3-era dimension
  scorecard; no verbal-band framing; no peer-rank claim outside
  `league_table_eligible`.

---

## 4. Remaining minor warnings

Three items that don't block pilot but should be tracked:

1. **Recommendation history persistence is not yet wired.** The V4
   recs generator currently emits `status = "new"` and `times_seen
   = 1` for every run. The prior recommendation-history prompt was
   redirected before the persistence module landed on the branch,
   so the Implementation Framework table cannot today show "Ongoing
   (3 months)" / "Stale" / "Chronic" lifecycle labels. Pilot
   reports will read as if every priority is new each month.
   Recommended next step: resume the paused
   `v4_recommendations_history.py` workstream.

2. **V3.4 `recommendations.py` and `implementation_framework.py`
   still live on disk.** Neither is invoked from any V4 code path
   (verified by grep). They continue to serve the V3.4-parallel
   generator. Hard removal is a post-cutover cleanup.

3. **Segment class-demotion branch is in place but untested live.**
   The Directional-C demotion to label + count only fires when
   `segment_intel` is populated; the sample runner currently passes
   `segment_intel=None`, so no sample exercises the demoted path
   end-to-end. The branch is simple and its unit behaviour is
   obvious from the code, but a sample with populated segment data
   would be worth generating before commercial publication.

---

## 5. Out of scope (explicitly deferred)

Everything in this list is intentionally **not** certified by this
memo. These are the existing Stack-A workstreams tracked in the
parallel status docs:

- Public leaderboard cutover (`rankings.html`, `index.html`,
  `assets/rankings/*.json`) — stays V3.4.
- Public methodology page rewrite (`docs/DayDine-Scoring-Methodology.md`
  banner is softened but the page is still marked provisional).
- Enrichment passes (Google phone / reservable / business_status,
  TripAdvisor coverage, FSA slice augmentation) — tracked in
  `DayDine-TripAdvisor-Trial-Status.md`,
  `DayDine-Commercial-Readiness-Data-Status.md`,
  `DayDine-Entity-Resolution-Status.md`.
- Post-enrichment Customer Validation recalibration — tracked in
  `DayDine-V4-Scoring-Comparison.md`.
- V4 quarterly report variant — out of scope for this stack.

---

## 6. Decision

The V4 operator report layer is **pilot-ready** subject to the three
minor warnings in §4. A supervised pilot can proceed using the
canonical samples under `samples/v4/monthly/` as the read-me shape.
Commercial publication remains blocked by the items in §5 and is not
certified here.

---

*End of pilot-readiness memo.*
