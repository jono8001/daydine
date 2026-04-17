# Entity Resolution Status — Stratford Trial

*Status as of April 2026. Scope: Stratford trial set, 210 establishments.*

## TL;DR

| Question | Answer |
|---|---|
| Does the resolver now distinguish legal-entity vs trading names? | **Yes.** 9 high-confidence manual aliases land in the trial set; `public_name` + `trading_names` are attached to those records. |
| Does V4 auto-detect ambiguous entity matches? | **Yes.** 4 duplicate Google Place IDs covering 9 FHRS records are now flagged `entity_ambiguous = true` and demoted to `Directional-C` / not rankable. |
| Are all the previously-named high-profile misses now resolved? | **Partially.** Church Street Townhouse, Pick Thai / No. 9 Church Street (current occupant), New York Pizzas, Super Nonna, and 4 other trading-name cases now resolve. Dirty Duck, Black Swan, RSC Rooftop, Golden Bee, Baraset Barn, Boston Tea Party, Osteria Da Gino, Grace & Savour, and Oscar's are genuinely not in the 210-record trial FSA slice. |
| Is current resolution quality sufficient for a consumer-facing Stratford ranking? | **Not yet for a full consumer launch; yes for an internal / beta trial.** The resolver is honest about unresolved names — they no longer silently return "no result". Consumer launch should wait for the FSA augmentation pass to close the 7-9 trial-slice gaps. |

## 1. Current entity-resolution approach

### Before this stack

V4 `assess_entity_match()` classified every record using only the presence
of two identifiers:

```
fhrs_id + gpid  -> confirmed
fhrs_id OR gpid -> probable
explicit entity_ambiguous flag -> ambiguous
neither         -> none
```

There was no trading-name handling, no auto-detection of Google Place
duplicates, and no way to tell whether a "confirmed" record was
manually reviewed or just happened to carry both identifiers. The
sanity check for named venues looked up the string `"Dirty Duck"`,
didn't find it, and reported "43 missing high-profile establishments"
without distinguishing "wrong name on the record we have" from
"not in the slice at all".

### After this stack

Three-layer resolution runs via
`.github/scripts/resolve_entities.py` and writes directly into
`stratford_establishments.json`:

1. **Manual alias table** (`data/entity_aliases.json`). Nine entries
   for venues where the FSA name is a legal entity or a composite
   "Trading As" string. Each alias attaches:
   - `public_name` — the consumer-facing trading name.
   - `trading_names` — a list of secondary names (DBAs, alt spellings).
   - `alias_confidence` — `high | medium | low`; all nine at `high`
     because they were manually reviewed against
     `stratford_establishments.json` source of truth.
   - `alias_source` — the human-readable evidence trail (e.g. "FSA name
     field 'The Townhouse Also Trading As JR Hotel And Restaurants LTD'").
2. **Auto-parse "Also Trading As" patterns** in FSA names. For records
   whose `n` field matches `^(public) (also trading as | trading as | t/a)
   (legal)`, the resolver derives `public_name` and `trading_names`
   automatically with `alias_confidence = medium`. In the current slice
   three such records were already covered by manual aliases (Church
   Street Townhouse, New York Pizzas, Super Nonna), so the auto-parser
   contributed zero additional coverage — but it is in place for
   future records ingested before a manual review can land.
3. **Ambiguity auto-detection**. Any two or more FHRS records sharing a
   Google Place ID get `entity_ambiguous = true`. The resolver also
   reads `ambiguous_gpids` from the manual alias file so a human
   reviewer can flag ambiguous groups even when auto-detection misses
   them (e.g. address-only collisions that haven't yet landed as
   duplicate gpids).

### V4 engine changes

`rcs_scoring_v4.py` now:

- Explicitly documents the decision order in `assess_entity_match()`:
  explicit override wins, then `entity_ambiguous`, then identifier
  presence. The old behaviour was identical to this but not documented;
  the new docstring matches spec §8.4 one-to-one.
- Surfaces alias evidence in the decision trace. When a record's
  `public_name` differs from its FSA `n`, the trace includes
  `alias public_name='...' alias_confidence=high`. Auditors and
  reviewers can see at a glance that an entity has been manually
  reviewed.

No change to headline scoring inputs. `assess_entity_match` keeps the
four-class scheme from the spec.

## 2. What improved

| Metric | Before | After |
|---|---:|---:|
| Records with `public_name` | 0 | 9 |
| Records with `trading_names` | 0 | 9 |
| Records flagged `entity_ambiguous` | 0 | 9 |
| Entity-match class counts | confirmed 209, probable 1, ambiguous 0, none 0 | confirmed 200, probable 1, ambiguous 9, none 0 |
| V4 class distribution (headline) | A 1 / B 190 / C 18 / D 1 | A 1 / B 181 / C 27 / D 1 |
| Duplicate-gpid groups correctly flagged | 0 / 4 | 4 / 4 |

The 9 re-classed venues all moved from `Rankable-B` to `Directional-C`
because they now correctly carry `entity_ambiguous = true`. Spec §8.4
says ambiguous matches cap at Directional-C; the engine was already
wired for that — it just wasn't firing because nothing ever set the
flag.

## 3. Named venue results

Run by `resolve_entities.py`. Query resolution uses a normalised-name
search index that indexes `n`, `public_name`, and every item in
`trading_names`. Exact normalised-key match first; substring fallback.

### Resolved after this stack

| Query | FHRSID | Record's FSA `n` | Resolved `public_name` | Note |
|---|---:|---|---|---|
| Church Street Townhouse | 1896714 | The Townhouse Also Trading As JR Hotel And Restaurants LTD | The Church Street Townhouse | Manual alias |
| The Townhouse | 1896714 | (same) | The Church Street Townhouse | Manual alias |
| Pick Thai | 1381156 | Pick Thai Ltd | Pick Thai | Manual alias (strips "Ltd") |
| Vintner | 503480 | Vintner Wine Bar | The Vintner Wine Bar | Manual alias |
| Lambs | 503316 | Lambs | Lambs | Direct |
| Loxleys | 502816 | Loxleys Restaurant And Wine Bar | Loxleys Restaurant and Wine Bar | Manual alias |
| Opposition | 503481 | The Opposition | The Opposition | Direct |
| New York Pizzas | 1622082 | The Crofts Cafe Also Trading As New York Pizzas | New York Pizzas | Manual alias |
| Super Nonna | 503931 | Bella Italia Also Trading As Super Nonna | Super Nonna | Manual alias |
| Bella Italia | 503931 | (same) | Super Nonna | Manual alias |
| Hussains | 502864 | Hussains | Hussains Indian Cuisine | Manual alias |

### Ambiguous (Directional-C, not rankable)

| FHRSIDs | Names | Why |
|---|---|---|
| 503343, 503218 | Starbucks – Southbound, Burger King – Southbound | Same service-station gpid |
| 1339997, 1513917 | The Margin, The Water Margin @ The Hollybush | Same gpid across two postcodes (likely rebrand / matching error) |
| 1206081, 1206075, 1206079 | South Costa, Dec X Canteen, Building 523 Costa And Kitchen | Three FSA units at one MoD / industrial site sharing one gpid |
| 1847445, 1589295 | Soma, The Tempest | Two Bell Court units sharing one gpid |

All nine records are still in the data, still carry their FSA scores
and audit trace, but no longer appear in the default league table
until a disambiguator lands.

### Still unresolved (not in trial slice)

These are **not** failures of entity resolution. They are gaps in the
210-record FSA trial slice itself — the FSA establishment is not in
our data under any name. Consumer search returns the `known_unresolved`
block from `data/entity_aliases.json` with a "not yet in trial dataset"
explanation rather than a silent empty result.

| Query | Postcode hint | Cause |
|---|---|---|
| The Dirty Duck (a.k.a. Black Swan) | CV37 6BA | Not in trial slice. Well-known Greene King pub on Waterside. |
| The Rooftop Restaurant / RSC Rooftop | CV37 6BB | Not in trial slice. RSC Enterprises. |
| The Golden Bee | CV37 6QW | Not in trial slice. |
| Baraset Barn | CV35 9AA | Not in trial slice. |
| Boston Tea Party | CV37 6HJ | Not in trial slice. |
| Osteria Da Gino | CV37 6HJ | Not in trial slice. |
| Grace & Savour | CV37 6BA | Not in trial slice. |
| No. 9 Church Street (historic) | CV37 6HB | Closed; 9 Church Street now occupied by Pick Thai. Consumer search should distinguish "this venue closed, current occupant is Pick Thai" from "we don't know about this venue". Alias file records the historic-occupancy note. |
| Oscar's | — | No plausible FSA record match found. Either closed, never FSA-registered, or outside trial scope. |

**Unblock path** (not part of this stack): re-run
`.github/scripts/augment_fsa_stratford.py` to pull all food business
types for LA 320. The script already contains a `KNOWN_RESTAURANTS`
seed list for exactly these cases; it just hasn't been run since the
210-record slice was built.

## 4. What remains unavailable

1. **True ambiguity resolution.** The resolver can detect duplicate
   gpids and flag them. It cannot pick which FHRS record is "the right
   one" for the Google Place. That requires either a manual review
   (same alias-table mechanism, with `entity_match_override =
   "confirmed"` plus a `disambiguated_to` note) or additional evidence
   (phone, website, owner confirmation). Until then, all
   duplicate-gpid records stay at Directional-C, which is the
   conservative choice.
2. **Cross-LA disambiguation.** Venues in neighbouring local authorities
   but physically on the Stratford boundary currently sit outside the
   trial slice. Not a resolution problem — a slice-selection problem.
3. **Fuzzy-match beyond normalised keys.** Levenshtein / token-set
   matching is not implemented. Present behaviour: exact normalised-key
   match, then substring fallback. Good enough for the manually-vetted
   9-alias set; insufficient for a broad UK-scale rollout where typo'd
   FSA names and inconsistent legal-entity strings are the norm.
4. **Address-graph reconciliation.** A postcode + road + number
   equality check would catch more "Trading As" cases automatically.
   Not implemented in this stack; the manual alias entry + auto-parser
   covers the Stratford 210.
5. **Companies House corroboration.** Spec §7.2 CH-5 says an unmatched
   CH entity should flow into `entity_match = ambiguous`. CH data is
   not populated in the trial, so CH-5 does not currently fire.
   `docs/DayDine-V4-Migration-Note.md` item (5) covers this.

## 5. Is current quality sufficient for a consumer-facing Stratford ranking?

**Not yet — but the honest-reporting guarantees are in place.**

Three gates distinguish "good enough for beta" from "good enough for
public launch":

1. **Named-miss surface.** `known_unresolved` in `entity_aliases.json`
   means any consumer who searches for Dirty Duck / Rooftop / Golden
   Bee / Baraset Barn / Boston Tea Party / Osteria Da Gino / Grace &
   Savour / Oscar's gets a structured response ("not in the current
   trial dataset — [reason]") rather than an empty result set. The
   search layer can render this honestly. **Passes beta.** **Fails
   launch** until the FSA augmentation pass runs and the list drops
   to zero.
2. **Ambiguous entities.** 9 records are correctly demoted to
   Directional-C and surfaced in a "Directional" list, not the main
   league table. Consumer ranking pages must not present them as
   "rankable absent" — they are "rankable but we aren't confident
   which record is the right one for this venue". **Passes beta** with
   the Directional-C surface; **launch-ready** once the duplicate-gpid
   groups are manually disambiguated.
3. **Rankable set integrity.** 181 / 210 records are now cleanly
   `Rankable-B` with identified trading names where those differ from
   the FSA legal entity. Top-of-leaderboard venues (Vintner, Lambs,
   Opposition, Loxleys) are all correctly named. **Passes launch.**

The resolver does not promise to find venues that aren't in the FSA
slice. It promises to be honest about (a) which records exist, (b)
which are ambiguous, and (c) which named venues are known-absent so
downstream UI can explain rather than hide the gap.

For the Stratford trial's beta scope, that is enough. For a public
consumer-facing UK ranking, the remaining steps are:

- Run `augment_fsa_stratford.py` to close the known-unresolved gap.
- Manually disambiguate the 4 duplicate-gpid groups or accept
  Directional-C for them permanently.
- Populate Companies House for CH-5 cross-check.
- Move from manual 9-alias coverage to a systematic "Trading As"
  parser + address-graph reconciler once the dataset grows beyond
  the current trial.

## 6. Contacts and source files

| Topic | File |
|---|---|
| Manual alias table | `data/entity_aliases.json` |
| Resolver script | `.github/scripts/resolve_entities.py` |
| Resolution report | `stratford_entity_resolution_report.json` |
| V4 engine (decision order + alias-aware audit trace) | `rcs_scoring_v4.py` |
| V4 spec (§8 Confidence and Rankability, §8.4 Ambiguity) | `docs/DayDine-V4-Scoring-Spec.md` |
| FSA slice expansion (`KNOWN_RESTAURANTS` list, unblock path) | `.github/scripts/augment_fsa_stratford.py` |
