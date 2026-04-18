# Commercial Readiness Data Status — Stratford Trial

*Status as of April 2026. Scope: Stratford trial set, 210 establishments.*

## TL;DR

| Question | Answer |
|---|---|
| Is Commercial Readiness still homogenised at ~0.75 for every venue? | **No.** CR now spans 0.00–7.50 across four buckets instead of flat-lining at 7.50. |
| Is the collection path fixed so CI can populate phone / booking / website when it runs? | **Yes.** `enrich_google_stratford.py` now requests and `merge_enrichment.py` now stores `websiteUri`, `nationalPhoneNumber`, `reservable`, `businessStatus`. V4 reads them. |
| Does the trial dataset have live phone / reservation data today? | **No.** That requires a CI run with `GOOGLE_PLACES_API_KEY`. Website coverage is 68.6% via heuristic inference; phone and reservable stay at 0% until live enrichment runs. |
| Is Commercial Readiness informative enough for V4 now? | **Partially.** It differentiates, but the maximum component score is still structurally capped at 7.5/10 because the booking/contact path is universally missing. |

## What was missing before

The V4 spec (§5.1) defines four equal sub-signals for Commercial Readiness:

| # | Signal | V4 field read | Previous coverage |
|---|---|---|---|
| 1 | Website present | `record.get("web")` | 2 / 210 (1.0%) |
| 2 | Menu online | `menu_entry.get("has_menu_online")` | 158 / 210 (75.2%) |
| 3 | Opening hours completeness | `record.get("goh")` | 172 / 210 (81.9%) |
| 4 | Booking / contact path | `record.get("booking_url")`, `record.get("reservation_url")`, `record.get("phone")`, `record.get("tel")` | 0 / 210 (0.0%) |

Because signal 4 was universally absent and signal 1 was effectively absent,
CR was capped at roughly 0.50 (menu + hours) for most venues and 0.75 for
the handful with all three. The component was present in the architecture
but not actually differentiating.

The Google enrichment field mask in `.github/scripts/enrich_google_stratford.py`
did not request any contact-path fields. The historical
`stratford_google_enrichment.json` (recovered from git) confirms: 240 records,
zero with `websiteUri`, `nationalPhoneNumber`, or `reservable`. The pipeline
never collected them — not even when the API key was configured.

## What was added

### Code changes

1. **`.github/scripts/enrich_google_stratford.py`** — field mask extended:
   - `places.websiteUri`
   - `places.nationalPhoneNumber`
   - `places.internationalPhoneNumber`
   - `places.reservable`
   - `places.businessStatus` (also for V4 §7.4 closure handling)

   These map to stored keys in the enrichment output as:
   - `websiteUri` / `web_url` (string)
   - `nationalPhoneNumber`, `internationalPhoneNumber`, and a derived `phone` (national preferred)
   - `reservable` (bool)
   - `business_status` (enum: `OPERATIONAL` / `CLOSED_TEMPORARILY` / `CLOSED_PERMANENTLY`)

2. **`.github/scripts/merge_enrichment.py`** — now writes these fields
   straight into `stratford_establishments.json`:
   - `web = True` and `web_url = <URI>` when a website is observed.
   - `phone = <national or intl>` when either is present.
   - `reservable = <bool>` from Google's attribute.
   - `business_status = <enum>` for closure handling.

3. **`rcs_scoring_v4.py`** — the Commercial Readiness booking/contact
   check now also accepts Google's `reservable` boolean:

   ```python
   booking_or_contact = bool(
       record.get("booking_url")
       or record.get("reservation_url")
       or record.get("reservable")      # NEW — Google Places attribute
       or record.get("phone")
       or record.get("tel")
   )
   ```

   The V4 engine continues to read only the four signals in spec §5.1. No
   new weak proxies have been introduced — delivery, takeaway, parking,
   wheelchair, dog-friendly etc. remain excluded from the score (spec §5.3,
   §6).

4. **`.github/scripts/commercial_readiness_coverage.py`** (new) — emits
   `stratford_commercial_readiness_coverage.json` with per-signal counts,
   bucket distribution, component stats, and a baseline snapshot for
   before/after comparison.

### Data population for the trial

Because this environment has no outbound network to the Google Places API,
observed phone / reservable / website data cannot be collected here. Two
things were done to populate the trial dataset with what can be derived
from existing data:

- **`check_web_presence.py`** (pre-existing, re-run) infers `web = True`
  for food-type venues with ≥ 50 Google reviews. This is legitimate
  inference under V4 spec §5.1 (which allows "Mix of observed (from
  Google attributes) and inferred"), and it raises website coverage from
  1.0% to 68.6% immediately.

- **Phone / reservable / business_status** are *not* inferred. They
  cannot be reliably derived from existing repo data and Google's
  boolean `reservable` has a precise meaning (listed on Google as
  reservable via partner). Fabricating it from type or review volume
  would add a weak proxy into the score. Left at 0% coverage.

## Current coverage

From `stratford_commercial_readiness_coverage.json`:

| Signal | Before | After | Delta |
|---|---:|---:|---:|
| Website (`web`) | 2 (1.0%) | **144 (68.6%)** | +142 |
| Menu online | 158 (75.2%) | 158 (75.2%) | — |
| Opening hours (`goh`) | 172 (81.9%) | 172 (81.9%) | — |
| Phone | 0 (0.0%) | 0 (0.0%) | — |
| `reservable` | 0 (0.0%) | 0 (0.0%) | — |
| Booking URL / reservation URL | 0 (0.0%) | 0 (0.0%) | — |
| Any contact path | 0 (0.0%) | 0 (0.0%) | — |
| `business_status` | 0 | 0 | — |

Of the 144 `web=True` records, 0 are observed (`web_url` set) and 144
are inferred. A CI run of `enrich_google_stratford.py` with
`GOOGLE_PLACES_API_KEY` will flip most of those to observed and populate
`web_url`, `phone`, `reservable`, `business_status` in the same pass.

### Commercial Readiness component distribution

| | Before | After |
|---|---:|---:|
| Mean CR | 5.000 | **5.643** |
| Median CR | 5.000 | **7.500** |
| Stdev CR | 1.050 | **2.489** |
| Max CR | 7.500 | 7.500 |
| Min CR | 0.000 | 0.000 |

| CR bucket | Count |
|---|---:|
| 0.00 | 16 |
| 2.50 | 36 |
| 5.00 | 36 |
| 7.50 | 122 |
| 10.00 | 0 |

The component now has real differentiation across four distinct buckets
instead of bunching at ~5.0. The maximum remains 7.50 (75% of cap)
because no venue has an observable booking/contact path — that is the
unresolved ceiling.

### Knock-on effect on the headline score

Regenerated V4 (`stratford_rcs_v4_scores.json`) with the calibrated
Customer Validation settings (Google prior 3.6, n_cap 250, gamma 1.2):

| Metric | Pre-web-inference | Post-web-inference |
|---|---:|---:|
| Rankable mean | 7.716 | 7.993 |
| Rankable median | 7.853 | 8.102 |
| Rankable stdev | 0.749 | 0.776 |
| Rankable ≥ 8.0 | 42.9% | 55.0% |

The top-half share re-inflated from 42.9% to 55.0% because 142 more
venues now get credit for Commercial Readiness' website sub-signal.
This is the expected direction — the calibration was performed against
a CR stuck near 5.0 universally; with real CR spread plus observable
website signal, the distribution shifts upward.

**Recalibration is a follow-on task**, not part of this stack. Once
phone / reservable data lands from a live CI run the distribution will
shift again and Customer Validation priors should be re-swept against
the richer CR data. Left for the next calibration cycle per the
"Calibration decision" section of `DayDine-V4-Scoring-Comparison.md`.

## What remains unavailable

| Signal | Why | How to unblock |
|---|---|---|
| Observed website (`web_url`) | Requires live Places API call with `websiteUri` field | CI run of `enrich_google_stratford.py` with `GOOGLE_PLACES_API_KEY` |
| Phone (`phone`) | Not in any public repo dataset; Places API has `nationalPhoneNumber` | Same CI run as above |
| Reservable (`reservable`) | Same — Places API boolean | Same CI run as above |
| Business status (`business_status`) | Not in any public repo dataset; Places API has `businessStatus` | Same CI run; also feeds V4 §7.4 closure handling |
| Booking URL / reservation widget (`booking_url`, `reservation_url`) | No public source returns deterministic booking links — OpenTable / Resy / Design My Night / Bookatable partner data is not in scope | Manual curation or a dedicated booking-platform integration (out of scope for V4) |
| Third-party reservable signal (e.g. OpenTable presence for a venue) | Schema reserved via `ot_rating` / `ot_count` in V4 but no collector today | Future work — phase 2 per `docs/review_data_strategy.md` |

## Is Commercial Readiness now informative enough for V4?

**Partially.** It now differentiates venues — CR spans 0.00–7.50 with
meaningful buckets — and the inference-based website signal is a
legitimate piece of evidence under the V4 spec. The component is no
longer homogenised.

What is still unresolved:

1. **Booking/contact is universally zero.** The 25% weight attached to
   that sub-signal is structurally wasted today. Until the CI enrichment
   pass lands, no venue can score above 7.50 on CR, which caps the
   component's contribution to the headline at 0.15 × 7.50 = 1.125 /
   1.500 achievable.

2. **Web is all inferred.** When the observed pass lands, 144 inferred
   `True`s will collapse to a smaller set of observed `True`s plus a
   (potentially) smaller number of inferred `True`s. Some venues
   currently scored as having a website may turn out not to — the
   inference was "food venue with ≥ 50 reviews", which is a reasonable
   prior but not fact. Expect CR to shift again on the live pass.

3. **Spec §7.4 closure handling is also dormant.** V4 already has code
   to cap / exclude closed venues, but without `business_status` from
   Google it cannot fire. Wiring the field through in this stack means
   the pipeline is ready; a single live pass activates it.

**Status: partially cleared.** The code path, field mapping, and V4
integration are all in place. The trial's actual observed coverage on
phone / reservable / business_status remains 0% and will stay 0% until
a CI run with `GOOGLE_PLACES_API_KEY` is triggered. Website coverage
has risen from 1% to 69% via heuristic inference, which gives the
component enough real signal to be informative, but the 25%
booking/contact weight remains unfunded.

## Contacts and source files

| Topic | File |
|---|---|
| Enrichment collector (field mask extended) | `.github/scripts/enrich_google_stratford.py` |
| Enrichment merge (fields wired through) | `.github/scripts/merge_enrichment.py` |
| Web presence inference (existing, re-run) | `.github/scripts/check_web_presence.py` |
| Coverage report generator (new) | `.github/scripts/commercial_readiness_coverage.py` |
| Coverage report | `stratford_commercial_readiness_coverage.json` |
| V4 scoring engine (reservable wired in) | `rcs_scoring_v4.py` |
| V4 spec (§5 Commercial Readiness) | `docs/DayDine-V4-Scoring-Spec.md` |
| Migration blockers | `docs/DayDine-V4-Migration-Note.md` |
