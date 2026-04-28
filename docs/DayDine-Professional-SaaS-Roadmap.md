# DayDine Professional SaaS Roadmap

**Status:** Working delivery plan — strategy locked for next build phase  
**Owner:** DayDine  
**Created:** April 2026  
**Last updated:** 28 April 2026  
**Purpose:** Convert DayDine from a strong public-ranking prototype into a professional UK hospitality intelligence SaaS with public rankings, authenticated client dashboards, admin tooling, monthly low-cost data refreshes, and a defensible proprietary methodology.

---

## 0. Executive decision

DayDine should become:

> A UK hospitality intelligence platform that publishes public DayDine Intelligence rankings and sells authenticated monthly intelligence dashboards to restaurant operators.

The correct operating model is:

1. **Public site:** fast, public, mostly generated/static, suitable for diners and SEO.
2. **Client portal:** Firebase-authenticated, venue-specific dashboards, monthly movement, downloadable reports.
3. **Admin portal:** Firebase-authenticated internal tooling for market readiness, pipeline status, clients, reports, entity-review and publish decisions.
4. **Data pipeline:** batch-refresh authorised public/licensed data once per month, cache results, and never call expensive APIs from public page views.
5. **Methodology:** evolve from V4 into V5 DayDine Evidence Rank, a proprietary confidence-aware hospitality intelligence model.

### 0.1 Strategic lock, 28 April 2026

DayDine will not try to beat Tripadvisor by claiming more review data. Tripadvisor has broad coverage and substantial review history, especially for already-visible venues. DayDine's competitive advantage must be different:

> Tripadvisor shows who is already popular. DayDine reveals who is proven, under-discovered, rising or overexposed.

Therefore V5 must position DayDine as a proprietary hospitality intelligence model that:

- includes authorised review evidence, initially Google rating and Google review volume;
- does not depend on Tripadvisor/OpenTable data at launch;
- does not ingest unauthorised Tripadvisor/OpenTable review data;
- separates popularity from quality;
- separates evidence confidence from score;
- uses category-normalised ranking;
- surfaces DayDine Signals such as Proven Leader, Hidden Gem, Rising Venue and Overexposed;
- retains public mystique by explaining principles, not exact formula or public scorecards.

Primary planning references:

```text
docs/ADR-002-Authorised-Review-Data-And-V5-Positioning.md
docs/DayDine-V5-Evidence-Rank-Blueprint.md
docs/DayDine-Current-State-And-Next-Actions.md
```

---

## 1. Strategic principles

### 1.1 Cost principle

DayDine must not make paid third-party API calls during normal user page views.

Correct model:

```text
Monthly pipeline run -> collect/enrich/cache -> store results -> website reads cached data
```

Incorrect model:

```text
User opens ranking page -> call Google/Tripadvisor/OpenTable live
```

### 1.2 Product principle

The public site and client product are related but not identical.

| Surface | Purpose | Data emphasis |
|---|---|---|
| Public rankings | Diner-facing discovery and brand trust | DayDine Intelligence Rank, Evidence Confidence, coverage, category context |
| Client dashboard | Operator value and monthly monitoring | movement, visibility, commercial gaps, action priorities |
| Admin console | Internal quality control | data completeness, ambiguous matches, pipeline readiness, source diagnostics |

### 1.3 Methodology principle

DayDine should avoid claiming that it has objectively identified the "best restaurants" in the ordinary critic/mystery-dining sense.

Preferred public wording:

> Ranked by DayDine's proprietary hospitality intelligence model.

Alternative:

> DayDine rankings include authorised public review evidence, including Google review rating and review volume, alongside trust, category, visibility and market-intelligence signals.

Avoid:

> Objectively the best restaurants.
> We analyse all reviews across the web.
> We include Tripadvisor/OpenTable reviews.
> Here is the full formula and exact weights.

Unless DayDine later adds first-party inspection, verified diner panels, critic partnerships, or licensed editorial/review data, it must not overclaim restaurant-quality objectivity or full review-universe coverage.

### 1.4 Moat principle

The moat is not access to Google, FSA or Companies House. Those are available to others.

The moat should be:

- venue-universe completeness;
- entity-resolution quality;
- monthly historical data;
- human-reviewed ambiguity decisions;
- coverage certificates;
- V5 Evidence Confidence logic;
- category-normalised ranks;
- DayDine Signals and Gap Signal;
- operator interpretation and action history;
- trusted UK hospitality intelligence brand.

### 1.5 Public mystique principle

Public methodology should be:

> Transparent principles. Proprietary machinery. No pay-to-play.

Public pages should show rank, movement, category rank, Evidence Confidence, DayDine Signal and concise intelligence notes. They should not reveal exact weights, formula, source-by-source component scorecards or gaming instructions.

---

## 2. Target architecture

### 2.1 Public layer

Keep public pages fast and cacheable.

```text
/
/rankings
/rankings/<market>
/search
/uk-establishments
/methodology
/for-restaurants
/login
```

Public data can be served as generated assets where appropriate:

```text
/assets/rankings/*.json
/assets/coverage/*.json
```

These files are public by design.

### 2.2 Client layer

Move client dashboards into Firebase-authenticated access.

```text
/client
/client/venues
/client/venues/<venueId>
/client/venues/<venueId>/snapshots/<month>
```

Client users must only see dashboards for venues they are authorised to access.

### 2.3 Admin layer

Move admin functionality behind Firebase-authenticated admin access.

```text
/admin
/admin/markets
/admin/reports
/admin/clients
/admin/pipeline
/admin/place-review
/admin/coverage
/admin/methodology-audit
```

### 2.4 Firebase services

Use Firebase as follows:

| Firebase service | DayDine use |
|---|---|
| Firebase Auth | Client/admin login and roles |
| Firestore or Realtime Database | clients, venues, dashboards, monthly snapshots, pipeline runs, market readiness |
| Firebase Storage | PDF exports, report downloads, evidence appendices |
| Firebase Hosting | Optional hosting target for authenticated app shell and public site, or combined with Vercel during transition |
| Firebase Security Rules | Enforce client venue access and admin-only writes |

### 2.5 Hosting strategy

There are two acceptable paths.

#### Option A — Hybrid, lower migration risk

- Keep public static site on Vercel temporarily.
- Add Firebase Auth + Firestore/Realtime Database for client/admin data.
- Protect client/admin data at Firebase rules level.
- Later migrate hosting if needed.

#### Option B — Firebase-first, cleaner long-term

- Move the full web app to Firebase Hosting.
- Use Firebase Auth everywhere.
- Public pages remain cacheable.
- Client/admin routes use authenticated Firebase reads.

Recommendation:

> Use Option A for the next sprint if speed matters. Move to Option B once auth, database rules and portal routing are stable.

---

## 3. Target data model

### 3.1 Users

```text
users/{uid}
  email
  displayName
  role: "admin" | "client" | "viewer"
  clientId
  createdAt
  lastLoginAt
  active
```

### 3.2 Clients

```text
clients/{clientId}
  name
  billingStatus: "trial" | "active" | "paused" | "cancelled"
  plan
  primaryContactEmail
  createdAt
  notes
```

### 3.3 Venues

```text
venues/{venueId}
  publicName
  canonicalName
  fhrsid
  googlePlaceId
  tripadvisorId optional/deferred
  opentableId optional/deferred
  companiesHouseNumber
  marketSlug
  category
  daydineSignal
  evidenceConfidence
  address
  postcode
  tradingNames[]
  entityResolutionStatus: "confirmed" | "probable" | "ambiguous" | "unresolved"
  entityResolutionConfidence
  lastEntityReviewAt
```

### 3.4 Client venue access

```text
clientVenueAccess/{clientId}_{venueId}
  clientId
  venueId
  accessLevel: "owner" | "viewer"
  active
  createdAt
```

### 3.5 Operator dashboard snapshots

```text
operatorDashboards/{venueId}/snapshots/{month}
  month
  operatorContext
  publicContext
  scores
  evidenceConfidence
  daydineSignal
  movement
  priorities
  commercialImpact
  competitorSet
  finalTakeaway
  reportUrl
  generatedAt
  status: "draft" | "review" | "ready" | "sent" | "active"
```

### 3.6 Market readiness

```text
marketReadiness/{marketSlug}
  marketSlug
  status: "ready" | "warning" | "blocked"
  counts
  warnings[]
  ambiguousPlaceGroups[]
  knownMissingVenues[]
  coverageCertificateUrl
  generatedAt
```

### 3.7 Pipeline runs

```text
pipelineRuns/{runId}
  marketSlug
  runType: "monthly_refresh" | "new_market" | "manual_rebuild"
  status: "queued" | "running" | "complete" | "failed"
  startedAt
  finishedAt
  inputSnapshotHash
  outputSnapshotHash
  warnings[]
  errors[]
  artifactUrls[]
  sourceCallCounts
  estimatedCost
```

### 3.8 Coverage certificates

```text
coverageCertificates/{marketSlug}_{month}
  marketSlug
  month
  fsaRecordsConsidered
  candidateDiningVenues
  includedInPublicRanking
  excludedNonPublicOrNonRestaurant
  excludedClosed
  ambiguousEntities
  knownMissingVenues
  rankableVenues
  directionalVenues
  profileOnlyVenues
  lastReviewedAt
  reviewer
  status
```

---

## 4. Low-cost monthly data pipeline

### 4.1 Monthly schedule

Run once per month per active market.

```text
Day 1-3: data pull and enrichment
Day 4: entity resolution and QA
Day 5: scoring and rankings
Day 6: admin review
Day 7: publish dashboards and public updates
```

### 4.2 Pipeline stages

```text
1. Pull FSA/FHRS source records
2. Determine candidate dining venue universe
3. Google Places discovery/enrichment for unmatched/new venues only
4. Google Details refresh for existing venues using field masks and cached place IDs
5. Companies House refresh where a company match exists or is needed
6. Optional OSM/coverage cross-check for missing venues
7. Optional expert-recognition refresh: Michelin/AA/manual curated sources
8. Optional Tripadvisor/OpenTable refresh ONLY if approved/licensed/API-compatible route exists
9. Entity resolution and ambiguity detection
10. Human QA for ambiguous/high-impact cases
11. V4 baseline score calculation
12. V5 Evidence Rank calculation beside V4
13. Category ranks and DayDine Signal generation
14. Coverage certificate generation
15. Public ranking publish
16. Client dashboard snapshot generation
17. Admin/client notification
```

### 4.3 Cost-control rules

1. Cache every third-party response with timestamp and source hash.
2. Do not call Google or any future licensed sources for unchanged venues unless scheduled refresh is due.
3. Use Google Place IDs once resolved; avoid repeated text search.
4. Use Google field masks to request only necessary fields.
5. Avoid full review-text collection except for licensed/authorised paid-report QA samples.
6. Do not use Tripadvisor/OpenTable in the launch core model unless access is authorised and documented.
7. Batch by active paid/priority markets first.
8. Store monthly snapshots so trend analysis does not require historical re-pulls.
9. Add budget alarms before scaling beyond pilot markets.
10. Never call expensive APIs from public page views.

### 4.4 Source priority

#### Core launch sources

| Source | Role | Cost posture |
|---|---|---|
| FSA/FHRS | venue universe and compliance | free/low cost |
| Google Places | identity, rating/count, hours, website/contact | paid but manageable if cached |
| Companies House | entity risk and status | low cost/free API, but matching effort |
| Manual local QA | high-value missing/ambiguous venue review | human cost, strong moat |
| OSM/coverage cross-check | missing venue audit | low cost |
| Expert recognition | Michelin/AA/local awards where legally clean | manual/licensing-aware |

#### Deferred / conditional sources

| Source | Role | Condition |
|---|---|---|
| Tripadvisor | rating/count/category metadata, if authorised | official/licensed/API-compatible route only |
| OpenTable / ResDiary / Dish Cult | booking/review/availability intelligence | later, after pricing/licensing clarity |
| Full review text | narrative/context only | licensed/authorised and not headline ranking by default |
| Good Food Guide / Harden's | benchmark/editorial layer | later, licensing-aware |
| Ordnance Survey / UPRN | address validation | later if needed |

---

## 5. Methodology evolution

### 5.1 Current baseline

V4 is the strongest current implemented methodology baseline.

Current V4 should be treated as:

> RCS v4.0 — public-evidence confidence score.

Not:

> Objective restaurant quality score.

Important V4 principles to preserve:

- FHRS is compliance/trust, not food quality.
- Review text sentiment should not drive headline ranking.
- Missing data must not inflate scores.
- Confidence/rankability must be separate from score.
- Single-platform customer validation should cap confidence.
- Entity ambiguity must block or reduce rankability.

### 5.2 Target methodology: V5 DayDine Evidence Rank Model

V5 is now the next methodology build direction.

V5 should include:

1. Authorised review evidence, initially Google rating and review volume.
2. Venue-universe completeness.
3. Entity-resolution confidence.
4. Evidence Confidence independent from score.
5. Capped/saturating review-volume benefit.
6. Bayesian/shrinkage-aware rating logic.
7. Category-normalised ranking.
8. DayDine Signals: Proven Leader, Established Favourite, Hidden Gem, Rising Venue, Specialist Pick, Overexposed, Under-Evidenced, Profile Only.
9. DayDine Gap Signal: difference between public visibility and underlying evidence/intelligence.
10. Expert-recognition layer, manually/licensing-aware first.
11. Trust/compliance layer.
12. Commercial-accessibility layer.
13. Market-presence and durability layer.
14. Coverage certificates.
15. Later uncertainty intervals and rank probabilities.

### 5.3 Suggested evidence families

Do not publish exact public weights. Internally, V5 should start with these evidence families:

| Evidence family | Role |
|---|---|
| Authorised review evidence | Google rating/count initially; bias-corrected and volume-capped. |
| Trust & compliance | FHRS/FSA gates, caps and confidence effects. |
| Venue surface/accessibility | website, menu, hours, phone, booking/contact path. |
| Category and occasion context | fair comparison across pubs, cafés, fine dining, casual venues, etc. |
| Recognition | Michelin, AA, local awards/press where legally clean. |
| Market presence/momentum | monthly movement, durability and visibility. |
| Entity and coverage confidence | certainty of venue match and completeness of market universe. |

### 5.4 Separate public and operator scoring emphasis

Public ranking should not over-emphasise commercial readiness. A restaurant can be excellent even if its booking path is weak.

Operator dashboard should emphasise commercial readiness more heavily because it creates actionable commercial value.

| Product | Emphasis |
|---|---|
| Public ranking | DayDine Intelligence Rank, Evidence Confidence, category position, public discovery |
| Operator dashboard | visibility, credibility, commercial capture-readiness, movement and action priorities |

### 5.5 Mathematical upgrades

#### Bayesian rating model

For each authorised platform:

```text
shrunk_rating = (n * observed_rating + k * platform_or_category_prior) / (n + k)
```

Use market/category priors where possible.

#### Saturating review count

Review-count benefit should saturate. More reviews should improve confidence, not endlessly dominate quality.

#### Evidence Confidence

Each venue should have:

```text
score_estimate
score_band or uncertainty range
Evidence Confidence
DayDine Signal
coverage_status
```

#### Rank simulation, later V5 phase

Monthly ranking should eventually use simulation:

```text
For each venue:
  sample score from venue uncertainty distribution
  rank all venues
Repeat many times
Calculate expected rank, top-10 probability, top-30 probability
```

Output:

```text
Expected rank: #7
Likely rank band: #5-#11
Top-10 probability: 72%
Top-30 probability: 96%
```

#### Category-normalised ranks

Always provide:

```text
overall rank
category rank
Evidence Confidence
DayDine Signal
rank band when available
```

---

## 6. Coverage certificate system

Every market should have a coverage certificate before public/commercial launch.

### 6.1 Certificate contents

```text
Market name
Month
Data refresh date
FSA authority / geography used
Total FSA establishments considered
Candidate dining venues identified
Venues included in public ranking
Venues excluded as non-restaurant/private/institutional
Venues excluded as closed
Venues with confirmed Google match
Venues with any approved second-source match if available
Venues with Companies House match
Ambiguous entity groups
Known-missing high-profile venues
Rankable/Directional/Profile-only counts
Human reviewer
Publish decision
```

### 6.2 Public display

Ranking pages should show a simple version:

```text
Coverage: 70 public dining venues ranked from 209 establishments reviewed.
Last updated: April 2026.
Known missing venues: 0.
Ambiguous venues excluded from primary rankings: 6.
```

Full certificate can sit behind:

```text
View market coverage
```

---

## 7. Professional site development stages

## Stage 0 — Freeze, document, stabilise

**Status:** Completed enough to move to build.

### Completed/planned docs

```text
docs/DayDine-Professional-SaaS-Roadmap.md
docs/DayDine-Launch-Readiness.md
docs/ADR-001-Public-Static-Plus-Firebase-SaaS.md
docs/ADR-002-Authorised-Review-Data-And-V5-Positioning.md
docs/DayDine-V5-Evidence-Rank-Blueprint.md
```

### Acceptance criteria

- Repo clearly states current limitations.
- No one mistakes static operator pages for secure client access.
- V5 strategy is defined before implementation.
- Next development work follows this roadmap.

---

## Stage 1 — Firebase authentication and roles

**Goal:** Create a real login foundation.

### Tasks

- Add `/login` page.
- Add Firebase Auth client integration.
- Add `/client` shell.
- Add `/admin` shell.
- Create role-aware route guards.
- Add logout.
- Add initial admin user bootstrap process.
- Add Firestore/Realtime Database rules.

### Roles

```text
admin: full internal access
client: read assigned venues and reports
viewer: limited read-only client access
```

### Acceptance criteria

- Unauthenticated user cannot access client/admin data.
- Client user cannot see another client's venue.
- Admin user can access admin shell.
- Security rules enforce access, not just frontend hiding.

---

## Stage 2 — Migrate Lambs dashboard into Firebase

**Goal:** First real protected client record.

### Tasks

- Create `venues/lambs` record.
- Create `clients/lambs` record.
- Create `clientVenueAccess` record.
- Move Lambs snapshot into Firebase under `operatorDashboards/lambs/snapshots/2026-04`.
- Update `/client` to list permitted dashboards.
- Update `/client/venues/lambs` to render from Firebase.
- Keep static `/operator/lambs` as prototype or redirect after auth.

### Acceptance criteria

- Lambs dashboard loads only after login.
- Lambs dashboard preserves report-aligned content.
- Dashboard shows operator context and public context separately.
- Dashboard can show Evidence Confidence and DayDine Signal when V5 is available.
- Static JSON is no longer the canonical client record.

---

## Stage 3 — Admin operating console

**Goal:** Professional internal control room.

### Admin modules

```text
/admin/markets
/admin/reports
/admin/clients
/admin/pipeline
/admin/place-review
/admin/coverage
/admin/methodology-audit
```

### Tasks

- Move market readiness records into Firebase.
- Move report manifests into Firebase.
- Add client status workflow: draft -> review -> ready -> sent -> active.
- Add ambiguous Google Place review queue.
- Add known-missing venue review queue.
- Add publish/hold decision fields.

### Acceptance criteria

- Admin can see which markets are ready/warning/blocked.
- Admin can review ambiguous entity groups.
- Admin can assign a venue dashboard to a client.
- Admin can mark dashboard as sent/active.

---

## Stage 4 — Coverage certificate and entity graph

**Goal:** Build the proprietary data foundation.

### Tasks

- Create canonical venue identity model.
- Link FSA ID, Google Place ID, Companies House ID and any approved future Tripadvisor/OpenTable IDs.
- Add resolver status and reviewer notes.
- Generate coverage certificate for Stratford.
- Generate coverage certificate for Leamington.
- Display simple coverage certificate on public ranking pages.

### Acceptance criteria

- Each market has a coverage certificate.
- Known missing venues are visible and managed.
- Ambiguous venues are not silently ranked.
- Public can see coverage confidence.

---

## Stage 5 — Monthly low-cost data refresh

**Goal:** Repeatable monthly data pipeline.

### Tasks

- Add monthly scheduled GitHub Action or Firebase-triggered function.
- Pull FSA/FHRS.
- Refresh Google only where due.
- Refresh Companies House matches.
- Run optional approved/licensed source refreshes only if available.
- Run entity resolution.
- Generate market readiness.
- Generate V4 baseline and V5 outputs.
- Generate client snapshots.
- Store pipeline run summary.

### Acceptance criteria

- Monthly refresh can run without manual file surgery.
- Third-party API calls are logged and bounded.
- Pipeline produces a run summary and cost estimate.
- Admin can approve publishing.

---

## Stage 6 — Methodology V5 prototype

**Goal:** Move beyond simple fixed-weight scoring into DayDine Evidence Rank.

### Tasks

- Build V5 experimental model beside V4.
- Add V5 output schema.
- Add DayDine Signal classifier.
- Add Evidence Confidence classifier.
- Add Gap Signal classifier.
- Add category-normalised ranking.
- Add expert-recognition field schema.
- Add source coverage scoring.
- Compare V4 vs V5 on Stratford and Leamington.
- Later add uncertainty intervals and rank probability simulation.

### Acceptance criteria

- V5 produces interpretable outputs.
- Top movers are explainable internally.
- V5 improves confidence handling without creating public black-box confusion.
- V5 does not require Tripadvisor/OpenTable launch data.
- Public wording remains proprietary, premium and defensible.

---

## Stage 7 — Public methodology and trust layer

**Goal:** Make the site credible to diners, operators and press without exposing the full model.

### Tasks

- Rewrite public methodology in plain English.
- Remove confusing V3.4/V4 transition wording from public surface once cutover is ready.
- Remove any stale claims about 40+ signals, aspect-level review intelligence or cross-source review convergence unless true.
- Add coverage explanation.
- Add correction/appeal process.
- Add data-source page.
- Add score limitations.
- Add update cadence.
- Add clear explanation that exact weights/formula are proprietary to prevent gaming.

### Acceptance criteria

- A public user can understand what the ranking means.
- An operator can challenge or correct factual issues.
- The site does not overclaim objective dining quality.
- The site does not imply Tripadvisor/OpenTable review ingestion unless true.
- Confidence classes and DayDine Signals are explained.

---

## Stage 8 — Client SaaS readiness

**Goal:** Prepare to charge clients.

### Tasks

- Add pricing/plan model.
- Add client onboarding flow.
- Add invitation emails.
- Add dashboard PDF/export generation.
- Add billing status field.
- Add Stripe or manual invoice status.
- Add terms/privacy pages.
- Add support/contact workflow.

### Acceptance criteria

- A client can be invited, log in, see only their dashboard and download their report.
- Admin can manage client status.
- Client dashboard has monthly historical movement.
- Report/export is available.

---

## Stage 9 — Market expansion

**Goal:** Repeat market launch process across UK towns.

### Suggested market order

1. Stratford-upon-Avon — refine and certify.
2. Leamington Spa — resolve warnings and certify.
3. Warwick — close local triangle.
4. Oxford — high-value restaurant market.
5. Bath — high-value visitor market.
6. Birmingham neighbourhood pilot — larger-market stress test.

### Acceptance criteria per new market

- Coverage certificate complete.
- Entity ambiguity reviewed.
- Public top 30 manually spot-checked.
- Hidden Gems list manually spot-checked.
- Known high-profile venues present or explained.
- Methodology output reviewed.
- Admin publish decision recorded.

---

## 8. Data source implementation plan

### 8.1 Google Places

Use only in monthly/batch pipeline.

Minimum fields:

```text
place_id
name
formatted_address
location
business_status
rating
user_ratings_total
website
phone
opening_hours
price_level if needed for profile only
primary_type/types for category support only
```

Rules:

- Use field masks.
- Cache responses.
- Prefer Place ID refresh over text search.
- Store last refresh timestamp.
- Do not collect review text for headline ranking.
- Treat Google rating/count as authorised review evidence, but cap confidence because it is one platform.

### 8.2 Tripadvisor

Not a launch dependency.

Permitted future uses:

```text
tripadvisor_id
rating
review_count
ranking/category where authorised
url
last_refreshed
```

Rules:

- Use only through official/licensed/API-compatible or legally reviewed routes.
- Do not rely on unauthorised scraping as the core model.
- Full review text is not a headline-ranking dependency.

### 8.3 OpenTable and booking platforms

Do not include in the launch core model.

Later use cases:

- booking availability;
- review metadata if authorised;
- reservation friction;
- operator report intelligence;
- external reference links.

### 8.4 Expert recognition

Start with manual/licensing-aware data.

Fields:

```text
michelin_listing
michelin_star_level
michelin_bib_gourmand
michelin_green_star
aa_rosette_level
expert_source_urls
last_verified
```

Rules:

- Do not depend on fragile scraping as core infrastructure.
- Add source links and manual review fields.
- Treat as distinction/recognition, not replacement for customer validation.

### 8.5 OSM / coverage cross-check

Use as a missing-venue audit layer.

Fields:

```text
osm_id
name
amenity/cuisine tags
lat/lon
address/postcode if present
match_status
```

Use to ask:

> Did FSA + Google miss any obvious public dining venues in this town?

---

## 9. Security requirements

### 9.1 Must-have before real clients

- Firebase Auth enabled.
- Role-based security rules.
- Client venue access enforced in database rules.
- Admin-only writes.
- No private dashboard JSON publicly accessible.
- Report downloads protected or signed.
- Admin pages no longer rely on `noindex` or hidden URLs.

### 9.2 Security anti-patterns to remove

- Public `/operator/<venue>` as client-facing URL without auth.
- Public `/assets/operator-dashboards/*` for private dashboards.
- Static admin pages with real internal data.
- Client-side-only role checks without database rule enforcement.

---

## 10. Immediate next implementation stack

The next phase is now build, not more planning.

### Stack A — Firebase Auth foundation

1. Add Firebase config module.
2. Add `/login`.
3. Add `/client` shell.
4. Add `/admin` shell.
5. Add role guard helper.
6. Add draft Firebase rules.
7. Add local/mock mode for development.

### Stack B — First protected client dashboard

1. Seed Lambs venue/client/user access records.
2. Migrate Lambs snapshot into Firebase.
3. Render `/client/venues/lambs` from Firebase.
4. Hide or redirect `/operator/lambs` behind login.
5. Confirm client cannot access other dashboards.

### Stack C — Market coverage certificates

1. Generate Stratford coverage certificate.
2. Generate Leamington coverage certificate.
3. Add coverage panel to ranking pages.
4. Add admin coverage review screen.

### Stack D — Methodology V5 prototype

1. Implement V5 deterministic output beside V4.
2. Add DayDine Signal, Evidence Confidence and Gap Signal.
3. Add category-normalised ranking.
4. Compare V4 vs V5 on Stratford.
5. Decide public cutover language.

---

## 11. Definition of professional-ready

DayDine is professional-ready when:

1. Public rankings have coverage certificates.
2. Public methodology is stable, premium and non-transitional.
3. Public methodology mentions authorised review evidence but does not imply Tripadvisor/OpenTable ingestion.
4. Client dashboards require login.
5. Client users can only see their own venues.
6. Admin pages require admin role.
7. Monthly data pipeline runs from cached/batch sources.
8. Google and any future licensed-source costs are bounded and logged.
9. Ambiguous entities are reviewed before ranking.
10. Known missing high-profile venues are managed.
11. Dashboard movement over time is retained.
12. Report/PDF export exists.
13. Correction/appeal workflow exists.
14. Terms/privacy and pricing are ready.

---

## 12. Current recommended next action

Do **not** build more static dashboards yet.

Next engineering move:

```text
Implement Firebase Auth + role-based /client and /admin foundations.
```

Next data/trust move:

```text
Build the coverage certificate system for Stratford and Leamington.
```

Next methodology move:

```text
Build V5 Evidence Rank deterministic outputs beside V4.
```

These moves turn DayDine from a strong prototype into the foundation of a professional SaaS product.
