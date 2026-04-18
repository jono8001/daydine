# DayDine — TripAdvisor Acquisition Strategy (Blocker 3)

*Authored April 2026. Branch: `claude/verify-v4-scoring-spec-L4Cjv`.*
*Scope: decide and prepare the TripAdvisor acquisition path for V4
public-cutover prep. Not a recalibration, not a cutover, not a
public-surface change.*

---

## 1. Starting point

* `collect_tripadvisor.yml` (HTML scraper via direct `requests` to
  `tripadvisor.co.uk/Search`) is non-viable from GitHub-hosted
  runners. 100% of search calls return HTTP 403; the runner IP
  ranges are on TripAdvisor's bot-protection block list. Diagnosis
  in `docs/DayDine-TripAdvisor-Blocker-Diagnosis.md`.
* The code-side defects (AttributeError + silent 403 swallowing)
  are fixed; the collector now fails honestly with `exit 7`.
* Blocker 5 (V4 Customer Validation recalibration) is still gated
  on Blocker 3. Without real TripAdvisor data, recalibration has
  no convergence signal for non-Google venues.

## 2. Options considered

### 2.1 Option A — TripAdvisor Content API

The official, ToS-clean path. Structured JSON for
`rating` / `num_reviews` / `price_level` / `cuisine` / coordinates
via a gated developer programme.

| Dimension | Assessment |
|---|---|
| Viability | Strong once approved. Stable surface, documented, supported. |
| Implementation effort | **Net-new collector.** No existing code in this repo speaks the Content API. Would need to write, test, and wire a new `collect_tripadvisor_content_api.py` that emits the same `data/raw/tripadvisor/*.json` shape the downstream `consolidate_tripadvisor.py` expects. Realistic 0.5–1 day of work. |
| Secrets required | `TRIPADVISOR_API_KEY`. |
| Runner / network | Plain HTTPS from any runner; no IP-block risk. |
| Expected Stratford coverage | High for well-known venues; coverage for very small pubs/cafes depends on TA listing depth (same as any TA path). |
| Maintainability | Best long-term. Official API, versioned, ToS-clean. |
| Fit with V4 roadmap | Aligns with a public-cutover commercial profile. |
| **Blocker** | **Approval-gated (typical 1–5 business days, longer for first-time applicants).** Cannot be unblocked from inside Claude Code. |

### 2.2 Option B — Apify managed collector (`scrapapi/tripadvisor-review-scraper`)

| Dimension | Assessment |
|---|---|
| Viability | Strong. Apify runs residential-IP pools + browser fingerprinting on their side — that is their core product. |
| Implementation effort | **Near zero.** `.github/scripts/collect_tripadvisor_apify.py` already exists (361 lines: fuzzy+coord matching, resume support, per-venue raw files, `MATCH_MIN_SCORE` gating). The existing `consolidate_tripadvisor.py` → `merge_tripadvisor.py` pipeline consumes its output directly. |
| Secrets required | `APIFY_TOKEN` (sign up at apify.com, 5-minute provisioning, no approval wait). |
| Runner / network | Plain HTTPS from any runner. Apify handles the block-list problem. |
| Expected Stratford coverage | Comparable to Content API for headline fields; slightly less reliable on rare-venue edge cases. Good enough for trial-scale recalibration. |
| Maintainability | Moderate. Actor can break unannounced upstream (that is how we ended up here in the first place; see `collect_tripadvisor_playwright.py` header comment "Replaces the broken Apify approach"). Mitigated by the actor we picked being the one currently recommended in `docs/review_data_strategy.md §2.2`. |
| Fit with V4 roadmap | Fits cutover PREP. May need replacement for commercial cutover if Apify terms or the actor change, at which point Option A becomes the replacement. |
| Blocker | `APIFY_TOKEN` secret needs to be added to the repo. One-click operation for a repo admin. No approval wait. |

### 2.3 Option C — Self-hosted runner / residential proxy

| Dimension | Assessment |
|---|---|
| Viability | Works if executed, but carries ongoing ops + ToS risk. |
| Implementation effort | High. Requires provisioning + maintaining a runner on a non-blocked IP (home IP, residential VPS, or Bright Data / Oxylabs proxy at ~$250–500/mo entry). |
| Secrets required | Proxy credentials + potentially runner tokens. |
| Runner / network | By definition, different from GH-hosted. |
| Expected Stratford coverage | Same as native scraper if not blocked. |
| Maintainability | Worst. Hand-managed infra, proxy rotation config, ongoing bills. |
| Fit with V4 roadmap | Poor. A V4-public-cutover-ready repo should not depend on a bespoke non-GH runner for a single data source. |
| Blocker | ToS ambiguity. TripAdvisor's terms prohibit automated scraping regardless of IP — Options A and B both sidestep this (A by being official, B by being the scraper operator's problem). |

### 2.4 Option D — Drop TripAdvisor, substitute an alternative source

Considered but rejected. Google Places (which we have) overlaps
partially, but for Stratford-upon-Avon — a tourist-driven UK town
— TripAdvisor specifically captures the inbound-visitor signal
that Google Places does not. Dropping TA would undercut the V4
convergence model's multi-platform premise (spec §4).

A plausible supplement (Yelp UK / OpenTable / Resy) is a future
additive signal, not a TripAdvisor substitute.

---

## 3. Decision

**Option B — Apify, via `scrapapi/tripadvisor-review-scraper`.**

### 3.1 Why

1. **Zero new code.** `collect_tripadvisor_apify.py` is already
   complete, tested against a known-good actor, and emits the
   exact output shape that `consolidate_tripadvisor.py` →
   `merge_tripadvisor.py` expect. There is nothing to write or
   validate beyond the workflow wiring.
2. **No approval wait.** `APIFY_TOKEN` provisioning is a five-
   minute, self-service operation. Option A's approval process
   (1–5+ business days) would stall Blocker 3 — and by extension
   Blocker 5 (recalibration) — for an uncertain amount of time.
3. **Same infra class as today.** Plain HTTPS from a GH-hosted
   runner is enough; no self-hosted runner, no residential proxy,
   no new infra line item.
4. **Cost is negligible at trial scale.** ≈ $0.50 per full-trial
   pass over the 210-record Stratford dataset at the actor's
   published rates; well inside operational tolerance.
5. **Option A remains the eventual target.** The decision to use
   Apify is time-boxed to V4 public-cutover PREP. Once a
   `TRIPADVISOR_API_KEY` is obtained (separate prompt, separate
   work order), an Option-A collector can be written alongside
   the Apify one without disturbing the current pipeline.

### 3.2 Why NOT each alternative

* **Not Option A** — correct long-term, but approval-gated. Would
  hold Blocker 5 for an unknown number of business days.
* **Not Option C** — ops burden and ToS ambiguity for no gain
  over Option B.
* **Not Option D** — structurally weakens the V4 convergence
  model.

## 4. What was implemented in this pass

All on branch `claude/verify-v4-scoring-spec-L4Cjv`. No scoring
change, no V4 engine change, no frontend change, no methodology
doc change.

### 4.1 New: `.github/workflows/collect_tripadvisor_apify.yml`

The supported workflow. Uses `secrets.APIFY_TOKEN`; fails fast
at preflight (exit 10) if the secret is absent. Steps:

```
preflight APIFY_TOKEN
  → pip install requests apify-client
  → inspect cache before fetch
  → fetch Firebase Stratford data
  → inspect cache after fetch          (::error::exit 5 on empty)
  → merge existing Google enrichment
  → collect TripAdvisor via Apify
  → inspect raw TA files
  → consolidate TripAdvisor raw files
  → inspect TripAdvisor side file
  → merge TripAdvisor data
  → inspect cache after TA merge       (::error::exit 6 on empty)
  → run RCS V3.4 scoring
  → inspect scoring outputs
  → commit results
```

Supports optional repo vars `APIFY_ACTOR`, `MAX_REVIEWS`,
`MATCH_MIN_SCORE` for tuning without editing the file.
Dispatch input `limit` reserved for future dry-run gating.

### 4.2 Fenced off: `.github/workflows/collect_tripadvisor.yml`

Retained for diagnostic purposes only. Changes:

* Workflow `name:` now reads
  `"[LEGACY / NON-VIABLE] TripAdvisor HTML Scraper"`.
* Prominent 17-line comment block at the top explaining
  non-viability and pointing at the Apify workflow + the two
  strategy memos.
* New required dispatch input `FORCE_LEGACY_TA_SCRAPER`. If
  anything other than the string `"true"` is passed, the job
  aborts at the new "Preflight — refuse to run unless
  explicitly forced" step with `::error::` + exit 11 and a
  message pointing readers to the Apify workflow.
* Job display name now reads
  `"[LEGACY] TripAdvisor HTML scraper (403-blocked on GH
  runners)"` so that browsing the Actions UI the legacy state
  is unambiguous.

The script itself (`collect_tripadvisor.py`) also has an
updated header banner marking it legacy / non-viable, pointing
at the Apify replacement and the two memos. The honest-fail
behaviour from the previous prompt (SearchBlocked + exit 7) is
unchanged.

### 4.3 Not changed

* `collect_tripadvisor_apify.py` — the collector itself needed
  no edits for this pass; it was already complete.
* `consolidate_tripadvisor.py`, `merge_tripadvisor.py`,
  `tripadvisor_coverage.py` — ingest contract unchanged.
* `full_pipeline.yml` — still references the Playwright path
  (`collect_tripadvisor_playwright.py`) with
  `continue-on-error: true`. Re-pointing that workflow at the
  Apify path is out of scope for this prompt; it should be
  done in the same prompt that wires up the `APIFY_TOKEN`
  secret and runs the first successful Apify collection pass.
  Until then, the full pipeline continues to degrade-gracefully
  past its TA step.
* Public surfaces, methodology doc, V4 engine, reports.

## 5. What is still required before Blocker 3 is fully cleared

| Item | Owner | Status |
|---|---|---|
| Provision `APIFY_TOKEN` as a GitHub repo secret | Repo admin, out-of-band | **Pending.** |
| (Optional) configure repo vars `APIFY_ACTOR`, `MAX_REVIEWS`, `MATCH_MIN_SCORE` | Repo admin | Defaults are sane; optional. |
| Dispatch `collect_tripadvisor_apify.yml` | Anyone with dispatch rights | Blocked until token is in place. |
| Verify ≥ 50% Rankable-B-eligible venues land `ta` + `trc` values in `stratford_tripadvisor.json` | Automatic in the inspect step | Blocked on the run above. |
| Decide future cutover to Content API (Option A) | Separate prompt / work order | Not blocking Blocker 5; optional long-term. |

## 6. Exact next step

1. A repo admin adds `APIFY_TOKEN` as a GitHub repo secret
   (value: a user token from
   [apify.com/account/integrations](https://apify.com/account/integrations)).
2. Merge this branch to `main`.
3. Dispatch `collect_tripadvisor_apify.yml` (manual).
4. Expected outcome:
   * Preflight passes (token present).
   * Collect step writes 1 raw JSON per matched venue under
     `data/raw/tripadvisor/`.
   * Consolidate step builds `stratford_tripadvisor.json`.
   * Merge step writes `ta` / `trc` / `ta_present` / `ta_url`
     onto `stratford_establishments.json`.
   * V3.4 scoring re-runs and commits the updated cache +
     scores back to `main`.
5. Inspect the run's last step output for the coverage number
   and the commit diff for the actual `ta` / `trc` values.
6. Only after this run is green and the committed dataset
   shows real TripAdvisor coverage should Blocker 5
   (recalibration) be attempted.

## 7. Resolution criteria for Blocker 3

| Sub-blocker | Cleared? |
|---|---|
| Code path for TripAdvisor collection exists | **Yes** (`collect_tripadvisor_apify.py`). |
| Workflow wired to that code path | **Yes** (`collect_tripadvisor_apify.yml`). |
| Legacy non-viable path fenced so it can't be used by accident | **Yes.** |
| Secret / infra to actually run the supported path | **Pending** (`APIFY_TOKEN`). |
| First successful end-to-end Apify run produces real TA coverage on main | **Pending.** |

Post-this-pass, Blocker 3 is **code-ready and infra-ready-pending-secret**.
Not yet fully cleared — the single remaining step is the
`APIFY_TOKEN` provisioning + first dispatch.

---

## 8. Yes / no

* **Chosen TripAdvisor strategy:** **Apify via
  `scrapapi/tripadvisor-review-scraper` — requires `APIFY_TOKEN`
  GitHub secret; TripAdvisor Content API (Option A) remains the
  long-term target for a future prompt.**
* **Is Blocker 3 now closer to clear?** **Yes** — code and
  workflow side fully done; only the secret provisioning +
  first dispatch remain.
* **Exact next step before recalibration:** Add `APIFY_TOKEN`
  to GitHub repo secrets, merge this branch to `main`,
  dispatch `collect_tripadvisor_apify.yml`, and confirm
  non-zero TA coverage lands on the committed trial dataset.
* **Can recalibration proceed yet?** **No** — Blocker 5
  remains gated on Blocker 3, which is not yet fully cleared.

---

*End of decision memo. Code changes are tightly scoped to the
TripAdvisor path; no scoring semantics, no entity-resolution
changes, no public-surface edits in this pass.*
