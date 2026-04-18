# DayDine V4 — Public Cutover Blockers

*Authored April 2026. Branch: `claude/verify-v4-scoring-spec-L4Cjv`.*
*Scope: audit of what still distorts V4 output enough to block a
public leaderboard cutover. Data, calibration, and operations only —
no engine or report-layer design changes are proposed here.*

> **Scope reminder.** The V4 operator report is pilot-ready. The V4
> scoring engine is stable. This memo is about whether the **public
> surface** — the consumer leaderboard, the public methodology page,
> and the data underneath them — is ready for V4 to replace V3.4
> there. It is **not** proposing cutover.

---

## 1. Snapshot of the Stratford trial today

Captured from the live repo state (seven-sample canonical set +
coverage artefacts regenerated cleanly):

| Metric | Value | What it means |
|---|---:|---|
| V4 class distribution | 1 A · 181 B · 27 C · 1 D | Cutover would publish a leaderboard where 0.48% of the market is in the top class |
| Rankable venues ≥ 8.0 | 56.0% | Top-half is still crowded; post-enrichment recalibration is expected to spread it |
| Customer-platform count per venue | 6 zero · 203 single · 1 two+ | Rankable-A is structurally unreachable for 209/210 venues without a second platform |
| Observed website (`web_url`) | 0 / 210 | All 144 `web=True` entries are heuristic inference, not observed Places API data |
| Observed phone | 0 / 210 | Commercial Readiness booking/contact sub-signal is universally empty |
| Observed `reservable` | 0 / 210 | Same — the 25% booking sub-signal is unfunded |
| Observed `business_status` | 0 / 210 | No venue has been closure-checked via Google |
| Opening hours present | 172 / 210 (81.9%) | Pre-existing Google `goh` data |
| TripAdvisor coverage | 1 / 195 eligible (0.5%) | Pipeline ready but no live pass has run |
| Duplicate-GPID ambiguous groups | 4 groups / 9 records | Demoted to Directional-C correctly, but not yet disambiguated |
| Named high-profile venues absent | 7 (Dirty Duck, RSC Rooftop, etc.) | Not in the 210-record FSA slice |

All the existing status docs
(`DayDine-TripAdvisor-Trial-Status.md`,
`DayDine-Commercial-Readiness-Data-Status.md`,
`DayDine-Entity-Resolution-Status.md`,
`DayDine-V4-Scoring-Comparison.md`,
`DayDine-V4-Readiness-For-Stack-B.md`) agree with the numbers above.

---

## 2. How these distort public V4 output

The snapshot above would produce a leaderboard that is **technically
accurate** (the scoring engine is faithful to spec) but
**commercially misleading** for a consumer reader:

1. **Top-class inflation.** With Rankable-A unreachable for 99.5% of
   venues and half the rankable pool sitting above 8.0, the public
   ranking would either be a nearly-empty "Rankable-A" list with one
   venue or a flat league where 100+ venues cluster in the 8.0–9.0
   band and are hard to differentiate.
2. **Silent absences.** Consumer searches for Dirty Duck / RSC
   Rooftop / Golden Bee / Baraset Barn / Boston Tea Party / Osteria
   Da Gino / Grace & Savour return "not in dataset" — not because
   these venues are unscored, but because they are not in the FSA
   slice the engine ran against.
3. **Under-funded Commercial Readiness.** The 25% booking/contact
   sub-signal is 0/210. The website sub-signal is 100% heuristic
   inference. Rankings driven partly by CR are partly driven by
   inference — tolerable at pilot, not at public.
4. **Ambiguous entities in the public ranking.** Nine records (Soma,
   The Tempest, two Southbound service-station pairs, the MoD
   canteen triad, the Margin rebrand pair) sit at Directional-C
   where the consumer surface will present them as "not ranked" —
   correct behaviour, but eight of those nine are real venues whose
   operators would reasonably expect to appear. Manual
   disambiguation is overdue.
5. **Calibration targeted at pre-enrichment data.** The 2026-04
   Customer Validation calibration (`V7`: Google prior 3.6, n_cap
   250, gamma 1.2) was tuned against a dataset where Commercial
   Readiness was flat at ~5.0 for almost every venue. CR is now
   distributed across 0 / 2.5 / 5.0 / 7.5 buckets; the top-half
   share drifted 42.9% → 56.0% as a direct consequence. A second
   calibration sweep against the enriched data is a precondition
   for publication.

---

## 3. Blockers, ordered by severity and recommended resolution order

Each blocker carries a category (`data`, `workflow`, `matching`,
`calibration`, `code`), a severity, and the shortest path to
resolution. Order reflects the shortest critical path: items earlier
in the list should land first because later items depend on the data
they produce.

### Blocker 1 — Google Places enrichment pass for observed CR sub-signals

| Field | Value |
|---|---|
| Category | **data** (CI run with secret) |
| Severity | **Critical** |
| Where | `.github/scripts/enrich_google_stratford.py`; the extended field mask (`websiteUri`, `nationalPhoneNumber`, `reservable`, `businessStatus`) already landed on this branch |
| Dependencies | `GOOGLE_PLACES_API_KEY` secret configured on the workflow runner |
| Cost | Per-request Places API billing for 210 venues (one-time) |

**What it unlocks:**
- Phone / `reservable` / `business_status` observed rather than absent.
- `web_url` observed for the majority of the 144 inferred-website
  records (the inferred count will shrink to the real observed count;
  pilot samples should be re-reviewed).
- CR booking sub-signal funds the 25% weight it currently wastes.
- Closure logic (spec §7.4) activates for the first time on live
  data.
- The Financial Impact confidence ladder starts emitting **Moderate**
  and **High** labels rather than **Low** across the board.

**Why first:** every downstream blocker's resolution numbers change
after this lands. Recalibration, named-miss audit, duplicate-GPID
disambiguation — all are sharper against enriched data.

### Blocker 2 — FSA slice augmentation (close the named-miss gap)

| Field | Value |
|---|---|
| Category | **data** (workflow rerun) |
| Severity | **Critical** |
| Where | `.github/scripts/augment_fsa_stratford.py`; the `KNOWN_RESTAURANTS` seed list already names the seven high-profile absences |
| Dependencies | None — FSA API is public |
| Cost | Free |

**What it unlocks:**
- Dirty Duck, RSC Rooftop, Golden Bee, Baraset Barn, Boston Tea
  Party, Osteria Da Gino, Grace & Savour move from
  `known_unresolved` into real FHRS records.
- Consumer searches for these venues return a real profile rather
  than a structured "not in trial" stub.
- The pool shape stabilises — the Stratford leaderboard is no
  longer obviously missing brand-recognisable entries.

**Why second:** must land before cutover because a public launch
with Dirty Duck absent would be immediately noticeable and damage
trust in the ranking. Independent of Google enrichment — can run in
parallel with Blocker 1.

### Blocker 3 — TripAdvisor collection pass

| Field | Value |
|---|---|
| Category | **data** (CI run with secret) |
| Severity | **Critical** |
| Where | `.github/scripts/collect_tripadvisor_apify.py` (default actor `scrapapi/tripadvisor-review-scraper`, coordinate-matching already wired); `consolidate_tripadvisor.py` + `merge_tripadvisor.py` handle the merge into establishments |
| Dependencies | `APIFY_TOKEN` secret configured |
| Cost | ~£0.50–1.00 per 200 venues per strategy doc §4.7 |

**What it unlocks:**
- A second customer platform exists for the majority of venues.
- `Rankable-A` stops being structurally unreachable: venues with
  strong ratings on both Google and TripAdvisor can finally demonstrate
  the multi-platform evidence the class requires.
- Single-platform caveat drops from 203 → ~30 (rough estimate based
  on the strategy doc's UK TA coverage benchmarks).
- Customer Validation calibration can be meaningfully swept against
  two-platform data.

**Why third:** depends on venue identity and address data that the
enrichment + FSA passes provide; running TA before FSA augmentation
means the seven named-miss venues will also be missing from the TA
pass and require a second run.

### Blocker 4 — Duplicate-GPID disambiguation

| Field | Value |
|---|---|
| Category | **matching** (manual + alias table) |
| Severity | **High** |
| Where | `data/entity_aliases.json` — extend `ambiguous_gpids` entries with either `entity_match_override = "confirmed"` on the canonical FHRS or explicit disambiguation notes |
| Dependencies | Human review of the four groups + each group's trading-name context |
| Cost | Low — four manual decisions, maybe thirty minutes per group |

**What it unlocks:**
- Nine venues currently demoted to Directional-C can move to
  Rankable-B where the evidence supports it.
- Operators of those venues (Soma, The Tempest, The Margin / Water
  Margin, the three MoD canteens, Burger King / Starbucks
  Southbound) see a ranked appearance rather than a "Directional —
  not league-ranked" badge they cannot act on.

**Why fourth:** low-cost and can be done independently of the data
passes, but the outputs become more legible once the enriched data
is in because the resolver has more signals to corroborate the
manual decision.

### Blocker 5 — Post-enrichment Customer Validation recalibration

| Field | Value |
|---|---|
| Category | **calibration** |
| Severity | **High** |
| Where | `calibrate_v4_customer.py` (the sweep harness), `rcs_scoring_v4.py` (apply the chosen priors) |
| Dependencies | Blockers 1 + 3 must have landed so the sweep runs against enriched data |
| Cost | Compute-only; one analyst afternoon to sweep, review, and select a winner |

**What it unlocks:**
- Top-half-rankable share returns from 56.0% toward the 40–45%
  target set in the original calibration decision.
- Stdev widens as Customer Validation starts differentiating highly-
  reviewed from lightly-reviewed venues at comparable ratings —
  currently the signal compresses because almost every venue is
  single-platform Google.
- `Rankable-A` becomes a meaningful class label (single-digit
  percentage of the market) rather than a one-venue badge.

**Why fifth:** must run after Blockers 1 + 3 so the sweep is against
the data the public launch will actually use. Running it before the
data passes would produce a calibration optimised for the thin
pre-enrichment shape.

### Blocker 6 — Scheduled V4 workflow (nightly or weekly)

| Field | Value |
|---|---|
| Category | **workflow** |
| Severity | **Medium** |
| Where | New `.github/workflows/score_v4.yml` (does not exist; currently V4 runs are ad hoc on this feature branch) |
| Dependencies | Blockers 1–3 so the workflow has enrichment data to score against |
| Cost | One workflow file, one cron entry |

**What it unlocks:**
- V4 outputs are regenerated on a schedule so operators looking at
  the public surface are not reading stale data.
- Monthly delta tracking (spec §10, already supported by the engine)
  starts accumulating history after the first two scheduled runs.
- The public cutover becomes "switch `rankings.html` from reading
  V3.4 outputs to V4 outputs" rather than a manual regen-at-cutover.

**Why sixth:** trivially small but blocking cutover because without
a scheduled run there is no maintained V4 output for the public site
to read.

### Blocker 7 — Public methodology / leaderboard copy refresh

| Field | Value |
|---|---|
| Category | **code + copy** |
| Severity | **Medium** |
| Where | `rankings.html`, `methodology.html`, `docs/DayDine-Scoring-Methodology.md`, `assets/rankings/*.json` |
| Dependencies | Blockers 1–5 — the numbers the copy cites must be post-enrichment-post-recalibration |
| Cost | Design + copy work + a frontend refresh |

**What it unlocks:**
- Consumer site presents V4 components and confidence classes
  rather than V3.4 six-band verbal labels.
- Public methodology page transitions from "provisional" to "final".
- `assets/rankings/*.json` feeds V4 rather than V3.4 scores.

**Why seventh:** last. Cannot be finalised until Blockers 1–5 land,
because every public-facing number in the copy will be wrong against
pre-enrichment data. The internal softening already applied on the
methodology page banner (commit `5b85827`) is enough until then.

---

## 4. Summary table

| # | Blocker | Category | Severity | Depends on |
|---|---|---|---|---|
| 1 | Google Places enrichment pass (phone / reservable / business_status / websiteUri) | data | Critical | `GOOGLE_PLACES_API_KEY` secret |
| 2 | FSA slice augmentation (close named-miss gap) | data | Critical | None (FSA is public) |
| 3 | TripAdvisor collection pass (second customer platform) | data | Critical | `APIFY_TOKEN` secret + Blocker 2 |
| 4 | Duplicate-GPID disambiguation (4 groups, 9 records) | matching | High | Blockers 1 + 3 give richer signals but not strictly required |
| 5 | Post-enrichment Customer Validation recalibration | calibration | High | Blockers 1 + 3 |
| 6 | Scheduled V4 scoring workflow | workflow | Medium | Blockers 1–3 |
| 7 | Public methodology + leaderboard copy refresh | code + copy | Medium | Blockers 1–5 |

**Top three (must land before cutover is technically possible):**

1. Google Places enrichment pass — unlocks observed CR sub-signals,
   closure detection, and the Financial Impact confidence ladder.
2. FSA slice augmentation — closes the high-profile named-miss gap
   that would be immediately visible at launch.
3. TripAdvisor collection pass — makes `Rankable-A` a meaningful
   class and lets the recalibration produce a sensible shape.

Blockers 4–7 follow in that order.

---

## 5. What this memo does not cover

- Engine changes. The V4 scoring engine is stable and aligned to
  `DayDine-V4-Scoring-Spec.md`. Nothing here calls for a scoring
  rewrite.
- Report-layer changes. The operator report is pilot-ready. Nothing
  here touches `v4_report_generator.py` or the sample set.
- Legacy cleanup. The V3.4 parallel generator and the `compare_v3_v4`
  harness stay in place per
  `DayDine-Legacy-Quarantine-Note.md` until the rollback window
  after cutover closes.
- Quarterly report. Still V3.4; out of scope for this memo.

---

*End of cutover-blockers memo. No code or data was modified in this
pass.*
