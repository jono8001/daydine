# DayDine Professional SaaS Roadmap

**Status:** Working delivery plan  
**Owner:** DayDine  
**Created:** April 2026  
**Purpose:** Convert DayDine from a strong public-ranking prototype into a professional UK restaurant intelligence SaaS with public rankings, authenticated client dashboards, admin tooling, monthly low-cost data refreshes, and a defensible methodology.

---

## 0. Executive decision

DayDine should become:

> A UK restaurant market intelligence platform that publishes public evidence-based restaurant rankings and sells authenticated monthly intelligence dashboards to restaurant operators.

The correct operating model is:

1. **Public site:** fast, public, mostly generated/static, suitable for diners and SEO.
2. **Client portal:** Firebase-authenticated, venue-specific dashboards, monthly movement, downloadable reports.
3. **Admin portal:** Firebase-authenticated internal tooling for market readiness, pipeline status, clients, reports, entity-review and publish decisions.
4. **Data pipeline:** batch-refresh public/licensed data once per month, cache results, and never call expensive APIs from public page views.
5. **Methodology:** evolve from a simple weighted score into a confidence-aware evidence-ranking model supported by venue-universe coverage certificates and entity-resolution audits.

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
User opens ranking page -> call Google/Tripadvisor live
```

### 1.2 Product principle

The public site and client product are related but not identical.

| Surface | Purpose | Data emphasis |
|---|---|---|
| Public rankings | Diner-facing discovery and brand trust | public-evidence rank, confidence, coverage |
| Client dashboard | Operator value and monthly monitoring | movement, visibility, commercial gaps, action priorities |
| Admin console | Internal quality control | data completeness, ambiguous matches, pipeline readiness |

### 1.3 Methodology principle

DayDine should avoid claiming that it has objectively identified the "best restaurants" in the ordinary critic/mystery-dining sense.

Preferred public wording:

> Top-ranked by DayDine's public-evidence confidence model.

Or:

> Best-evidenced restaurants in this market, based on public trust, customer validation, recognition, visibility and confidence signals.

Avoid:

> Objectively the best restaurants.

Unless DayDine later adds first-party inspection, verified diner panels, critic partnerships, or licensed editorial review data.

### 1.4 Moat principle

The moat is not access to Google, FSA or Companies House. Those are available to others.

The moat should be:

- venue-universe completeness;
- entity-resolution quality;
- monthly historical data;
- human-reviewed ambiguity decisions;
- coverage certificates;
- probabilistic ranking/confidence modelling;
- operator interpretation and action history;
- trusted UK restaurant intelligence brand.

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
  tripadvisorId
  companiesHouseNumber
  marketSlug
  category
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
5. Tripadvisor metadata refresh for targeted venues only
6. Companies House refresh where a company match exists or is needed
7. Optional expert-recognition refresh: Michelin/AA/manual curated sources
8. Entity resolution and ambiguity detection
9. Human QA for ambiguous/high-impact cases
10. Score calculation
11. Rank simulation / confidence modelling
12. Coverage certificate generation
13. Public ranking publish
14. Client dashboard snapshot generation
15. Admin/client notification
```

### 4.3 Cost-control rules

1. Cache every third-party response with timestamp and source hash.
2. Do not call Google/Tripadvisor for unchanged venues unless scheduled refresh is due.
3. Use Google Place IDs once resolved; avoid repeated text search.
4. Use Google field masks to request only necessary fields.
5. Avoid full review-text collection except for paid reports or QA samples.
6. Use Tripadvisor metadata first; full reviews only selectively.
7. Do not use OpenTable in the core model until pricing/licensing is clear.
8. Batch by active paid/priority markets first.
9. Store monthly snapshots so trend analysis does not require historical re-pulls.
10. Add budget alarms before scaling beyond pilot markets.

### 4.4 Source priority

#### Core sources now

| Source | Role | Cost posture |
|---|---|---|
| FSA/FHRS | venue universe and compliance | free/low cost |
| Google Places | public identity, rating/count, hours, website/contact | paid but manageable if cached |
| Tripadvisor | rating/count/category metadata, selected review context | controlled use |
| Companies House | entity risk and status | low cost/free API, but matching effort |
| Manual local QA | high-value missing/ambiguous venue review | human cost, strong moat |

#### Later sources

| Source | Role | Timing |
|---|---|---|
| OpenTable / ResDiary / Dish Cult | booking/review/availability intelligence | later, after pricing clarity |
| AA Rosettes | expert recognition | add early if low-friction |
| Michelin | expert recognition | add manually/licensing-aware first |
| Good Food Guide / Harden's | benchmark/editorial layer | later, licensing-aware |
| OSM/Overpass | missing venue cross-check | useful for coverage confidence |
| Ordnance Survey / UPRN | address validation | later if needed |

---

## 5. Methodology evolution

### 5.1 Current problem

The current V4 method is stronger than the older V3.4 structure, but it is still a fixed-weight score. It is good for a first serious public-evidence model, but not enough to claim "best restaurants" in a cast-iron ordinary-language sense.

Current V4 should be treated as:

> RCS v4.0 — public-evidence confidence score.

Not:

> Objective restaurant quality score.

### 5.2 Target methodology: DayDine Evidence Rank Model

Develop a V5-style model with:

1. Venue-universe completeness.
2. Entity-resolution confidence.
3. Multi-platform customer validation.
4. Expert-recognition layer.
5. Trust/compliance layer.
6. Commercial accessibility layer.
7. Market-presence and durability layer.
8. Uncertainty intervals.
9. Rank probabilities.
10. Coverage certificates.

### 5.3 Suggested public evidence families

| Evidence family | Role | Public ranking weight direction |
|---|---|---:|
| Customer appeal / validation | customer rating/count metadata, bias-corrected | 40-45% |
| Expert recognition | Michelin, AA, credible guides | 15-20% |
| Trust & compliance | FHRS/FSA | 10-15% |
| Market presence / durability | review volume, cross-platform consistency, trading continuity | 10-15% |
| Commercial accessibility | website/menu/hours/contact/booking | 5-10% |
| Entity and coverage confidence | certainty of match and venue universe | gating / confidence factor |

### 5.4 Separate public and operator scoring emphasis

Public ranking should not over-emphasise commercial readiness. A restaurant can be excellent even if its booking path is weak.

Operator dashboard should emphasise commercial readiness more heavily because it creates actionable commercial value.

| Product | Emphasis |
|---|---|
| Public ranking | best-evidenced restaurants in a market/category |
| Operator dashboard | how visible, credible and commercially capture-ready the restaurant appears externally |

### 5.5 Mathematical upgrades

#### Bayesian rating model

For each platform:

```text
shrunk_rating = (n * observed_rating + k * platform_prior) / (n + k)
```

Use platform-specific priors and pseudo-counts.

#### Platform bias correction

Estimate each platform's typical rating distribution by category and market type.

Example:

```text
Google 4.6 may not mean the same thing as Tripadvisor 4.6.
```

#### Uncertainty intervals

Each venue should have:

```text
score_estimate
lower_bound
upper_bound
confidence_class
```

#### Rank simulation

Monthly ranking should eventually use simulation:

```text
For each venue:
  sample score from venue uncertainty distribution
  rank all venues
Repeat 10,000 times
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
confidence class
rank band
```

This reduces unfair comparisons between cafés, pubs, fine-dining venues and takeaways.

### 5.6 Minimum evidence to rank

A venue should only appear in the primary league table if:

1. It is in the confirmed venue universe.
2. It has an FSA/FHRS record or explicitly justified equivalent.
3. It has confirmed public trading identity.
4. It has at least one customer-validation source.
5. It is not closed or unresolved.
6. It passes entity-resolution thresholds.
7. It passes confidence/rankability gates.

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
Venues with Tripadvisor match
Venues with Companies House match
Ambiguous entity groups
Known-missing high-profile venues
Rankable-A/B count
Directional-C count
Profile-only-D count
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

**Goal:** Stop feature sprawl and establish the professional roadmap.

### Tasks

- Add this roadmap to the repo.
- Mark current operator/admin pages as prototype/internal.
- Create launch readiness checklist.
- Create architecture decision record.
- Document public/static vs Firebase-authenticated boundaries.

### Deliverables

```text
docs/DayDine-Professional-SaaS-Roadmap.md
docs/DayDine-Launch-Readiness.md
docs/ADR-001-Public-Static-Plus-Firebase-SaaS.md
```

### Acceptance criteria

- Repo clearly states current limitations.
- No one mistakes static operator pages for secure client access.
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
- Link FSA ID, Google Place ID, Tripadvisor ID and Companies House ID.
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
- Refresh Tripadvisor metadata selectively.
- Refresh Companies House matches.
- Run entity resolution.
- Generate market readiness.
- Generate rankings.
- Generate client snapshots.
- Store pipeline run summary.

### Acceptance criteria

- Monthly refresh can run without manual file surgery.
- Third-party API calls are logged and bounded.
- Pipeline produces a run summary and cost estimate.
- Admin can approve publishing.

---

## Stage 6 — Methodology V5 prototype

**Goal:** Move beyond simple fixed-weight scoring.

### Tasks

- Build V5 experimental model beside V4.
- Add expert-recognition field schema.
- Add uncertainty intervals.
- Add rank probability simulation.
- Add category-normalised ranking.
- Add source coverage scoring.
- Compare V4 vs V5 on Stratford and Leamington.

### Acceptance criteria

- V5 produces interpretable outputs.
- Top movers are explainable.
- V5 improves confidence handling without creating black-box confusion.
- Public wording remains conservative and defensible.

---

## Stage 7 — Public methodology and trust layer

**Goal:** Make the site credible to diners, operators and press.

### Tasks

- Rewrite public methodology in plain English.
- Remove confusing V3.4/V4 transition wording from public surface once cutover is ready.
- Add coverage explanation.
- Add correction/appeal process.
- Add data-source page.
- Add score limitations.
- Add update cadence.

### Acceptance criteria

- A public user can understand what the ranking means.
- An operator can challenge or correct factual issues.
- The site does not overclaim objective dining quality.
- Confidence classes are explained.

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

### 8.2 Tripadvisor

Use for metadata first.

Minimum fields:

```text
tripadvisor_id
rating
review_count
ranking/category where available
url
last_refreshed
```

Rules:

- Avoid full review pulls at scale.
- Use only for customer validation and cross-platform breadth.
- Full review text only for paid report narratives or QA samples.

### 8.3 OpenTable and booking platforms

Do not include in core model now.

Later use cases:

- booking availability;
- review metadata;
- reservation friction;
- operator report intelligence.

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

### Stack A — Freeze and documentation

1. Add this roadmap.
2. Add launch readiness doc.
3. Add architecture decision record.
4. Mark operator/admin static routes as prototype/internal.

### Stack B — Firebase Auth foundation

1. Add Firebase config module.
2. Add `/login`.
3. Add `/client` shell.
4. Add `/admin` shell.
5. Add role guard helper.
6. Add draft Firebase rules.
7. Add local/mock mode for development.

### Stack C — First protected client dashboard

1. Seed Lambs venue/client/user access records.
2. Migrate Lambs snapshot into Firebase.
3. Render `/client/venues/lambs` from Firebase.
4. Hide or redirect `/operator/lambs` behind login.
5. Confirm client cannot access other dashboards.

### Stack D — Market coverage certificates

1. Generate Stratford coverage certificate.
2. Generate Leamington coverage certificate.
3. Add coverage panel to ranking pages.
4. Add admin coverage review screen.

### Stack E — Methodology V5 blueprint

1. Write V5 technical blueprint.
2. Add uncertainty/rank-probability prototype.
3. Add expert-recognition schema.
4. Compare V4 vs V5 on Stratford.
5. Decide public cutover language.

---

## 11. Definition of professional-ready

DayDine is professional-ready when:

1. Public rankings have coverage certificates.
2. Public methodology is stable and non-transitional.
3. Client dashboards require login.
4. Client users can only see their own venues.
5. Admin pages require admin role.
6. Monthly data pipeline runs from cached/batch sources.
7. Google/Tripadvisor costs are bounded and logged.
8. Ambiguous entities are reviewed before ranking.
9. Known missing high-profile venues are managed.
10. Dashboard movement over time is retained.
11. Report/PDF export exists.
12. Correction/appeal workflow exists.
13. Terms/privacy and pricing are ready.

---

## 12. Current recommended next action

Do **not** build more static dashboards yet.

Next engineering move:

```text
Implement Firebase Auth + role-based /client and /admin foundations.
```

Next methodology move:

```text
Build the coverage certificate system for Stratford and Leamington.
```

Next data move:

```text
Design the canonical venue identity graph and monthly cached enrichment pipeline.
```

These three moves turn DayDine from a strong prototype into the foundation of a professional SaaS product.
