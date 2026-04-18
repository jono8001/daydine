# DayDine — TripAdvisor Blocker (Blocker 3) Diagnosis

*Authored April 2026. Branch: `claude/verify-v4-scoring-spec-L4Cjv`.*
*Scope: diagnose and fix the two failures in
`collect_tripadvisor.yml` on `main` (commit `78912d8`, run #2).
Not a recalibration, not a cutover, not a public-surface change.*

---

## 1. The two failures

### 1.1 Downstream code bug — `AttributeError`

```
AttributeError: 'list' object has no attribute 'get'
```

**Exact location (pre-fix main):**
`.github/scripts/collect_tripadvisor.py::main`, line **350** (and the
related filter on line 351), inside this block:

```python
valid = sum(1 for v in ta_data.values()
            if v.get("ta") is not None and not v.get("_skipped")
            and not v.get("_no_match") and not v.get("_error"))
```

**Why `v` is a list:**
The committed `stratford_tripadvisor.json` side file on `main`
(blob `028d4342b049d264a2ba872f8e726139d74f2726`) was written by
`consolidate_tripadvisor.py`, which emits two top-level metadata
keys alongside the per-fhrsid entries:

```python
out = {
    "_meta": {...},          # dict
    "_unmatched": unmatched,  # LIST
}
for k, v in consolidated.items():
    out[k] = v                # one dict per fhrsid
```

When `collect_tripadvisor.py` resumes from that file via
`ta_data = json.load(f)` and then iterates
`for v in ta_data.values()`, the `_unmatched` value is a list and
has no `.get()`. Boom.

Reproduced in the sandbox using the committed main blob —
identical symptom.

### 1.2 Upstream infrastructure bug — HTTP 403 Forbidden

Every call to

```
GET https://www.tripadvisor.co.uk/Search?q=<name>+Stratford-upon-Avon
```

from a GitHub-hosted runner's IP range returns **HTTP 403
Forbidden**. Before this fix `search_tripadvisor()` caught all
`requests.RequestException` instances (including the `HTTPError`
raised by `raise_for_status` on 403) and returned an empty list,
so every blocked venue was silently mis-classified as a legitimate
"no result". That left the AttributeError from §1.1 as the only
surfaced symptom — but the data being "collected" was empty
regardless.

**Both failures are independent.** The `AttributeError` would
still have fired even without the 403s (because of the resumed
`_unmatched` list). The 403s would still have produced a
misleading all-`no_match` dataset even without the
`AttributeError`. They compound, they do not cause each other.

---

## 2. What was fixed (code only — infrastructure remains)

All changes are on branch `claude/verify-v4-scoring-spec-L4Cjv`,
tightly scoped to the TripAdvisor path.

### 2.1 `.github/scripts/collect_tripadvisor.py`

* **Type-safe final summary.** The offending comprehension now
  skips underscore-prefixed metadata keys AND type-checks the
  value:

  ```python
  valid = sum(
      1 for k, v in ta_data.items()
      if not k.startswith("_")
      and isinstance(v, dict)
      and v.get("ta") is not None
      and not v.get("_skipped")
      and not v.get("_no_match")
      and not v.get("_error")
      and not v.get("_blocked")
  )
  ```

* **Same guard applied to the resume-skip check** at the top of
  the main loop (`if key.startswith("_") or key in ta_data:`),
  so reserved metadata keys are never treated as establishment
  fhrsids even if the resume file has unusual shapes.

* **`SearchBlocked` exception** is raised when the TripAdvisor
  search endpoint returns HTTP 403 or 429. Network-level
  errors (DNS, TLS, timeout) continue to be swallowed as
  transient "no result" as before — only IP-block signals
  are escalated.

* **Explicit counters** for attempted lookups, 403/429 blocks,
  genuine no-match cases, real errors, and successful matches.

* **Early abort** once blocking is clear: after
  `BLOCKED_MIN_ATTEMPTS = 20` attempts, if at least
  `BLOCKED_RATIO_THRESHOLD = 0.5` of them are blocks, the
  loop stops so the runner doesn't waste 200 further requests
  before failing.

* **Honest exit 7** at end-of-run if the threshold is met.
  The error message explicitly says "runner IP is likely
  blocked" and points readers at this memo.

### 2.2 `.github/workflows/collect_tripadvisor.yml`

The existing "Inspect TripAdvisor side file" step is expanded
to print the five counts (matched / no_match / blocked /
errors / skipped) and to emit `::error::` + exit 7 if the
same blocking threshold is hit. This makes the state visible
at the GitHub Actions summary level, not just in the script's
stdout.

### 2.3 Not changed

* `merge_tripadvisor.py` already skips underscore keys and is
  type-safe.
* `consolidate_tripadvisor.py` is untouched — its output shape
  is what it is; the consumer was wrong, not the producer.
* Scoring code, entity resolution, Firebase/fetch hardening,
  V4 engine, any frontend — untouched.

---

## 3. What the 403 pattern means

TripAdvisor maintains an active bot-protection layer on
`www.tripadvisor.co.uk/Search`. Known facts from the repo +
this run:

* GitHub-hosted runners use Azure IP ranges (broadly,
  `20.0.0.0/8`, `13.0.0.0/8`, `52.0.0.0/8`). These ranges are
  well-known to bot-protection vendors (DataDome, PerimeterX,
  Akamai Bot Manager — TripAdvisor uses one of these or an
  in-house equivalent) and are challenged or blocked by
  default.
* A realistic desktop `User-Agent` and a 2–3-second throttle
  (the current script's config) do not defeat this.
* The same block pattern is what caused the previous project
  pivot from a direct scraper to Apify — see
  `collect_tripadvisor_playwright.py`'s header comment
  ("Replaces the broken Apify approach") and
  `docs/review_data_strategy.md §2.2`.

The 403 is therefore **not a bug in the scraper** — it is an
**infrastructure constraint**: the current environment is not
a viable source of TripAdvisor requests.

---

## 4. Is the current GitHub Actions scraping approach viable?

**No.** Three converging pieces of evidence:

1. The observed 100% 403 rate on Run #2 of
   `collect_tripadvisor.yml`.
2. The explicit comment in `collect_tripadvisor_playwright.py`
   noting that Playwright was introduced as a replacement
   because "the Apify approach broke" — that means the
   project already knows GH-runner-based collection is fragile.
3. GitHub's documented runner IP ranges overlap heavily with
   bot-block lists; this is a well-known limitation of using
   GH Actions for consumer-site scraping (see GitHub's own
   docs on "ip addresses for GitHub-hosted runners" — they
   advise self-hosted runners for any work that needs stable
   egress).

Classification of Blocker 3: **both** code and infrastructure,
now that the code side is fixed — **infrastructure only**.

---

## 5. Options for getting TripAdvisor data reliably

Four realistic paths, assessed honestly.

### Option A — **TripAdvisor Content API**  ✅ *Recommended.*

* Official, authoritative, stable. Returns structured JSON for
  restaurants by name/location, including `rating`, `num_reviews`,
  `price_level`, `cuisine`, coordinates, and recent review
  snippets.
* Access is gated (apply at
  [tripadvisor.com/developers](https://www.tripadvisor.com/developers))
  and requires attribution. Commercial usage is subject to
  approval; a trial-scale academic-style data project of our
  size is the standard approval profile.
* Integrates cleanly: introduce `TRIPADVISOR_API_KEY` as a GH
  secret, add a new `collect_tripadvisor_content_api.py`
  alongside the existing collectors, reuse the existing
  `consolidate_tripadvisor.py` + `merge_tripadvisor.py` output
  contract.
* Cost: free tier covers trial scale; paid tiers exist for
  national-scale.
* **Risk: approval-gated.** Application turnaround is
  typically 1–5 business days.

### Option B — Apify TripAdvisor actor  ⚠️ *Viable fallback.*

* The `collect_tripadvisor_apify.py` script already exists
  and uses `scrapapi/tripadvisor-review-scraper`. Apify
  operates its own IP pools and handles bot-protection for you.
* Requires `APIFY_TOKEN` secret. Cost ≈ $0.50 per full-trial
  pass per the CLAUDE.md notes.
* **Risk: third-party scraper; upstream actor can break
  unannounced.** That's exactly what the Playwright header
  comment refers to as "the Apify approach broke". Would need
  spot-check against current state before depending on it.

### Option C — Self-hosted runner / residential proxy  ⚠️ *Higher ops burden.*

* Move `collect_tripadvisor.yml` to a self-hosted runner with
  a residential IP, OR tunnel the existing runner's requests
  through a residential-proxy service (Bright Data, Oxylabs,
  Smartproxy — $~250-500/mo entry).
* Works, but introduces ongoing operational cost and a
  maintained secret.
* **Risk: ToS.** TripAdvisor's ToS prohibits automated
  scraping regardless of IP. The Content API avoids this
  problem; this path does not.

### Option D — Alternative data source  ❌ *Not a TripAdvisor replacement.*

* We already have Google Places ratings (Tier 2 / Customer
  Validation), and OpenTable / Yelp / Resy cover a
  partially-overlapping audience in the UK, but none of them
  reproduce TripAdvisor's specific "tourist/inbound" signal
  that matters for a Stratford-upon-Avon trial.
* Can be a supplement (second platform evidence for
  convergence), not a replacement.

### Recommendation

**Option A (TripAdvisor Content API).** It is the only option
that is legally clean, operationally stable, and doesn't
depend on an upstream scraper that can break unannounced.
Apify (Option B) is a reasonable interim if the Content API
application is delayed and the trial needs to move.

---

## 6. What to re-run now

1. **Merge this branch to `main`.** The AttributeError fix +
   the honest-fail behaviour + the blocked-counter inspect
   step all land together.
2. **`collect_tripadvisor.yml`** can be dispatched once more
   to confirm the new behaviour — the expected outcome on the
   current (GitHub-hosted, no API key) infrastructure is:
   * Step "Collect TripAdvisor data" attempts up to 20
     lookups, all 403, then exits 7 with the named diagnostic.
   * Or — if early-abort triggers first — the job fails with a
     clear "blocked 20/20" summary before wasting further
     requests.
   * In neither case does the `AttributeError` reappear.
3. **`fetch_and_score.yml`** does not need re-running — it is
   already green.

The committed `stratford_tripadvisor.json` on `main` is
preserved as-is. When Option A or B is wired up in a future
prompt, it will overwrite the side file through the normal
`consolidate_tripadvisor.py` → `merge_tripadvisor.py` pipeline.

## 7. What should NOT be attempted yet

* Do NOT add a residential-proxy secret to the repo as an
  emergency patch — that's a ToS + ops decision that needs
  out-of-band approval.
* Do NOT recalibrate the V4 Customer Validation priors — they
  depend on TripAdvisor data which we don't yet have honestly
  for Stratford.
* Do NOT trigger `full_pipeline.yml` expecting TripAdvisor
  coverage to land. That workflow's TA step is
  `continue-on-error: true`; it will log the block and move
  on, producing a dataset that scores without TA signal.
  That's acceptable today only because downstream consumers
  already know TA is absent; do not confuse it with TA having
  been tried and "not found anything".
* Do NOT change the V4 scoring engine or reports to weight
  differently based on TA absence — that's a post-TA-landing
  calibration decision.

---

## 8. Resolution criteria

Blocker 3 (TripAdvisor) is considered resolved when ALL of:

1. `collect_tripadvisor.yml` completes either green (with a
   non-trivial number of real TripAdvisor matches in the
   inspect summary) or fails with exit 7 + a named
   infrastructure diagnostic — never with an
   `AttributeError`.
2. At least one path (Option A or B) has been wired up, has
   produced a non-empty `stratford_tripadvisor.json` with
   real `ta` / `trc` values for ≥ 50% of Rankable-B-eligible
   venues, and has landed via the normal
   `consolidate_tripadvisor.py` → `merge_tripadvisor.py`
   pipeline.
3. `commercial_readiness_coverage.py` /
   `tripadvisor_coverage.py` both report non-zero TA coverage
   on the committed trial dataset.

This PR closes item 1 only. Items 2 and 3 require a decision
on Option A vs B (plus the associated secret), out of scope
for an operational debugging pass.

---

## 9. Yes / no

* **AttributeError fixed?** **Yes** —
  `collect_tripadvisor.py:350`, now type-safe.
* **Workflow now fails honestly on 403 blocking?** **Yes** —
  `sys.exit(7)` with a named `::error::` diagnostic both in
  the collector and in the workflow's inspect step; early
  abort after 20 attempts so no further requests are wasted.
* **Is the current GitHub-hosted scraping approach viable?**
  **No.** 100% 403 observed; runner IPs are on TripAdvisor's
  block list.
* **Recommended next strategy:** **TripAdvisor Content API
  (add `TRIPADVISOR_API_KEY` secret, add a new API-based
  collector alongside the existing scripts).**
* **Can recalibration proceed yet?** **No.** Blocker 5
  remains gated on Blocker 3 — we do not yet have real
  TripAdvisor data for Stratford.

---

*End of memo. Code changes are scoped to the failing path;
no scoring, entity-resolution, or frontend logic changed.*
