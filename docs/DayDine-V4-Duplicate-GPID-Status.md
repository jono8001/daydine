# DayDine V4 — Duplicate-GPID Disambiguation Status

*Authored April 2026. Branch: `claude/verify-v4-scoring-spec-L4Cjv`.*
*Scope: Blocker 4 from `docs/DayDine-V4-Public-Cutover-Blockers.md` —
local, no live-network work required.*

> **Headline finding.** All four duplicate-GPID groups (9 records)
> are now classified by root cause and carry a specific operator-
> facing explanation that surfaces in the V4 Directional-C
> explainer. **No record moves out of Directional-C** — each group
> represents genuine ambiguity that cannot be responsibly resolved
> from public data alone. The improvement is rankability honesty
> and operator-facing trust: the report now answers *why* a venue
> is Directional-C with a specific reason, not a generic "ambiguous"
> label.

---

## 1. Audit — all identity-conflict patterns present in the dataset

| Pattern | Count | Resolution in this pass |
|---|---:|---|
| Duplicate Google Place IDs across FHRSIDs | 4 groups, 9 records | Classified + enriched explanation |
| Same name + same postcode across FHRSIDs | 0 | None needed |
| Same address line across FHRSIDs (non-gpid collision) | 3 patterns (Welcome Break Southbound, JLR Gaydon, Welcome Break Northbound) | Already subsumed by the gpid groups (Southbound + Gaydon); Northbound pair has distinct gpids, not ambiguous |
| `entity_ambiguous` flag already set | 9 (= gpid groups above) | — |

The audit confirmed no untracked identity conflicts beyond the four
known gpid groups.

---

## 2. Groups — before / after classification

### Group 1 — `service_station_shared`
**Site:** Welcome Break Warwick Services Southbound, M40
(postcode CV35 0AA)

| FHRSID | FSA name |
|---|---|
| 503343 | Starbucks – Southbound |
| 503218 | Burger King – Southbound |

Two separate franchise brands share the service-station forecourt.
Google Places returns one listing for the whole site; FSA registers
each brand separately. Each brand operator would need a distinct
Google Business Profile before the ambiguity clears. Both records
remain Directional-C; the report now names the type and the
resolution path.

### Group 2 — `rebrand_or_relocation`
**Postcodes:** CV47 9PZ vs CV47 7RW (different; genuinely distinct
addresses)

| FHRSID | FSA name | Postcode |
|---|---|---|
| 1339997 | The Margin | CV47 9PZ |
| 1513917 | The Water Margin @ The Hollybush | CV47 7RW |

Most likely a rebrand or relocation where the operator kept the
Google Business Profile and one FSA record was not retired. The
alias entry now carries an **optional** `primary_fhrsid` field: when
a human reviewer confirms which side is canonical, setting that
field causes the resolver to mark the non-primary record
`fsa_closed = true` (triggering the V4 closure path) and lift the
primary record out of ambiguous into Rankable-*. **Default for this
pass:** `primary_fhrsid = null`, so both records remain ambiguous
and Directional-C. No public-data signal is strong enough here to
make the call safely without operator confirmation.

### Group 3 — `multi_tenant_site`
**Site:** Jaguar Land Rover, Gaydon Test Centre, Banbury Road,
Gaydon (postcode CV35 0RR)

| FHRSID | FSA name |
|---|---|
| 1206081 | South Costa |
| 1206075 | Dec X Canteen |
| 1206079 | Building 523 Costa And Kitchen |

Three separately FSA-registered food units inside a private
industrial site. Google Places has one listing for the whole
facility. Public ranking is **not the right surface** for
private-site canteens; Directional-C is the correct **permanent**
classification. The alias entry records this and the Directional-C
explainer in the report surfaces the site name.

### Group 4 — `food_hall_unit`
**Site:** Bell Court, Stratford-upon-Avon (postcode CV37 6EX)

| FHRSID | FSA name |
|---|---|
| 1847445 | Soma |
| 1589295 | The Tempest |

Two separately FSA-registered units inside the Bell Court food
hall share one Google Place ID. Resolution path is the same as
Group 1: each unit requests a distinct Google Business Profile.
Both records remain Directional-C.

---

## 3. What changed in this pass

### 3.1 Alias-table schema extended (`data/entity_aliases.json`)

Each `ambiguous_gpids` entry now carries:

- `disambiguation_type` — one of `service_station_shared`,
  `rebrand_or_relocation`, `multi_tenant_site`, `food_hall_unit`
- `reason_for_operator` — human-readable explanation
- `resolution_path` — what would clear the ambiguity
- `site` (where applicable) — human-readable site name
- `primary_fhrsid` (rebrand group only) — optional field a human
  reviewer can set to mark the canonical record; `null` by default

### 3.2 Resolver (`.github/scripts/resolve_entities.py`)

`_flag_duplicate_gpids` now:

- Propagates the four new fields onto each flagged record
  (`disambiguation_type`, `disambiguation_reason`,
  `disambiguation_resolution_path`, `disambiguation_site`).
- For rebrand groups with `primary_fhrsid` set: flips the non-
  primary record to `fsa_closed = true` (triggering the V4 closure
  path) and lifts the primary record out of ambiguous. Default
  (primary unset) keeps all records ambiguous — no silent change
  of venue state without operator confirmation.
- Copies the disambiguation fields onto the `auto_groups` entries
  in the resolution report so the V4 sample runner and report
  generator get the richer context without re-reading the alias
  table.

### 3.3 V4 report generator (`operator_intelligence/v4_report_generator.py`)

`_render_confidence_basis` now surfaces, for every ambiguous
record:

- The conflicting FHRSIDs + FSA names (was already present)
- The site name (new)
- A one-line "Why ambiguous" label derived from
  `disambiguation_type` (new: `Service-station shared listing`,
  `Rebrand or relocation`, `Multi-tenant private site`,
  `Food-hall shared listing`)
- The operator-facing reason (new)
- The resolution path (new)

The existing "Why this venue isn't league-ranked yet" section in
the Directional-C orchestrator reads from the same source and gains
the reason without template changes.

### 3.4 Regenerated artefacts

- `stratford_entity_resolution_report.json` — now carries per-group
  disambiguation fields.
- `stratford_establishments.json` — 9 ambiguous records now carry
  `disambiguation_type` + `disambiguation_reason` +
  `disambiguation_resolution_path` + `disambiguation_site`.
- `stratford_rcs_v4_scores.json` + `.csv` — no score change (class
  and score both identical; classification reasons are report-
  layer state, not score-engine state).
- `samples/v4/monthly/Soma_2026-04.md` (Directional-C sample) —
  now shows "Why ambiguous: Food-hall shared listing" with the
  operator-facing reason and resolution path. All seven samples
  pass QA with 0 errors, 0 warnings.

---

## 4. Resolved groups summary

| Group | Records | Status before | Status after | Venue classification | Explanation quality |
|---|---:|---|---|---|---|
| Group 1 (Southbound service-station) | 2 | Directional-C, generic "ambiguous" | Directional-C, typed `service_station_shared` | unchanged (correct) | specific reason + resolution path now in report |
| Group 2 (Margin / Water Margin) | 2 | Directional-C, generic "ambiguous" | Directional-C, typed `rebrand_or_relocation`, `primary_fhrsid = null` | unchanged (correct without operator confirmation) | specific reason + resolution path + manual-override hook in alias table |
| Group 3 (JLR Gaydon MoD units) | 3 | Directional-C, generic "ambiguous" | Directional-C, typed `multi_tenant_site`, permanent | unchanged (correct; Directional-C is the right long-term classification) | specific reason; no resolution path needed because these should stay private-site |
| Group 4 (Bell Court food-hall) | 2 | Directional-C, generic "ambiguous" | Directional-C, typed `food_hall_unit` | unchanged (correct) | specific reason + resolution path now in report |

## 5. Groups still unresolved (remain ambiguous)

| Group | Why unresolved | What would resolve it |
|---|---|---|
| Group 1, Group 4 | Two brands at one site; only distinct Google listings would separate them | Each operator requests a distinct Google Business Profile (external to DayDine) |
| Group 2 | A rebrand / relocation that needs operator confirmation | Operator (or a human reviewer with confidence) sets `primary_fhrsid` in `data/entity_aliases.json::ambiguous_gpids` |
| Group 3 | Permanent multi-tenant-site state | Nothing — Directional-C is correct for private-site canteens |

Note: unresolved here means "the ambiguity is genuine". The report
now gives operators a specific reason and next step; the records
remain Directional-C, which is the honest classification.

---

## 6. What this does / does not change

### Improves

- **Entity-match confidence surface** — ambiguous records now
  carry a typed reason that pinpoints the real cause; the report
  can explain each case individually.
- **Rankability honesty** — the Directional-C classification is
  now defensible in operator-facing copy because each case has a
  stated reason and resolution path. Previously the explanation
  was generic.
- **Duplicate suppression / separation** — recognised, classified,
  and documented per group. A rebrand-group operator can now
  cleanly mark the retired side by setting `primary_fhrsid` in
  the alias table; the resolver handles the downstream state
  flip.
- **Public-facing trust** — a pilot or beta reader seeing a
  Directional-C record now sees "this is a food-hall unit sharing
  a Google listing with The Tempest — here's how to fix it", not
  an unexplained "not ranked" badge.

### Does not change

- **V4 class distribution** — 1 / 181 / 27 / 1 (A / B / C / D)
  unchanged.
- **V4 scores** — all 9 ambiguous records keep their current
  `rcs_v4_final` because the score engine reads `entity_ambiguous`
  as a boolean; the typed reason is report-layer state.
- **Peer pool** — unchanged (Rankable-* excludes Directional-C, as
  before).
- **Any live-network-dependent state** — Google enrichment and
  FSA augmentation remain blocked on runner access; see §7.

---

## 7. Dependencies on external / CI runs

This pass is **fully local**; nothing here required live network or
API keys. Future improvements on top of this work that **do**
require external runs:

| Downstream improvement | External dependency |
|---|---|
| Moving Group 1 / Group 4 out of Directional-C | Each brand / unit operator requests distinct Google Business Profile (not a DayDine action) |
| Resolving Group 2 automatically | Live Google enrichment after the rebrand/retirement has stabilised on Google's side; or operator confirmation (no CI needed but human decision required) |
| Refreshing the rebrand-candidate field-level details | Live Google enrichment pass (see `DayDine-V4-Enrichment-Execution-Status.md`) |
| New duplicate-GPID discoveries post-enrichment | Rerun `resolve_entities.py` after enrichment; same alias-table pattern applies to new groups |

---

## 8. Blocker status

**Partially cleared.**

- Every known duplicate-GPID group is now classified, explained in
  operator copy, and has a stated resolution path.
- Three of the four groups will **remain** ambiguous until external
  operator action (Groups 1, 4, and Group 3 permanently); the
  resolver and report correctly continue to surface them as
  Directional-C with a specific reason.
- Group 2 has a manual-override hook (`primary_fhrsid`) that a
  human reviewer can use to retire one side of a rebrand
  non-destructively. Not set by default — requires operator
  confirmation.
- Publicly, a V4 cutover with these groups still ambiguous is now
  safer than before: each affected operator sees a specific reason
  instead of a generic "ambiguous" label.

**Why not "cleared":** Groups 1, 2, and 4 still sit at Directional-C
awaiting external action. Only Group 3 (private-site canteens) is
classified as a **permanent** Directional-C — for that group alone
the classification is complete.

---

## 9. Yes / no answers

- **Duplicate-GPID blocker cleared?** **Partial.** All four groups
  are classified and explained; Groups 1, 2, 4 remain at
  Directional-C awaiting external operator action; Group 3 is
  permanently Directional-C by correct design.
- **Can this improvement safely stand before enrichment lands?**
  **Yes.** The change is local, alias-table-driven, and
  behaviour-preserving for every record whose state can't be
  safely changed without operator confirmation. It does not
  conflict with future enrichment passes; re-running the resolver
  after enrichment will simply re-flag any new duplicate groups
  and pick up any fresh `primary_fhrsid` / manual entries.
- **What is the next correct step after this inside Claude Code?**
  Add a `.github/workflows/score_v4.yml` scheduled run (Blocker 6
  from the cutover-blockers memo) — the only remaining blocker
  that is fully executable inside Claude Code without live
  external credentials.
- **What is still required outside Claude Code on the CI runner?**
  Blockers 1 + 3 + 5 + 7 from
  `docs/DayDine-V4-Public-Cutover-Blockers.md`: Google Places
  enrichment pass (requires `GOOGLE_PLACES_API_KEY` + outbound
  HTTPS), FSA slice augmentation (requires outbound HTTPS to
  `api.ratings.food.gov.uk`), TripAdvisor collection pass
  (requires `APIFY_TOKEN` + outbound HTTPS), post-enrichment
  Customer Validation recalibration (runs after the data passes
  land), and the public methodology / leaderboard copy refresh
  (gated on all of the above).

---

*End of duplicate-GPID disambiguation status memo.*
