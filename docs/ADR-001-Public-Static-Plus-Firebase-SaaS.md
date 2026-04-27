# ADR-001: Public Static Site plus Firebase SaaS Portal

**Status:** Accepted for next implementation phase  
**Date:** April 2026  
**Decision owner:** DayDine  
**Related docs:**

```text
docs/DayDine-Professional-SaaS-Roadmap.md
docs/DayDine-Prior-Work-Inventory.md
docs/DayDine-Roadmap-Implementation-Control.md
docs/DayDine-Launch-Readiness.md
docs/DayDine-Current-State-And-Next-Actions.md
```

---

## 1. Context

DayDine began as a generated/static public ranking and operator intelligence prototype.

The current repo contains:

- public pages served as static HTML;
- committed JSON ranking assets;
- static internal admin pages;
- static prototype operator dashboards;
- Firebase usage for the public UK establishments lookup;
- GitHub Actions and Python scripts for ranking, readiness and dashboard generation.

This is strong for fast iteration and public prototype validation, but it is not sufficient for a professional paid SaaS product because:

1. client dashboards need authentication;
2. restaurant users must only see their own data;
3. admin tools must be role-protected;
4. private dashboard/report data should not live as public JSON;
5. monthly refresh history and pipeline state need durable storage;
6. API calls must be batched/cached and cost-controlled.

---

## 2. Decision

DayDine will use a two-layer architecture.

### 2.1 Public layer

The public ranking, search and marketing site may remain static/generated and cacheable.

Public routes:

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

Public assets may include:

```text
/assets/rankings/*.json
/assets/coverage/*.json
```

These are public by design.

### 2.2 SaaS layer

The client and admin product will move to Firebase-authenticated access.

Protected routes:

```text
/client
/client/venues/<venueId>
/client/venues/<venueId>/snapshots/<month>
/admin
/admin/markets
/admin/reports
/admin/clients
/admin/pipeline
/admin/place-review
/admin/coverage
```

Firebase services:

| Firebase service | Use |
|---|---|
| Firebase Auth | Login and identity |
| Firestore or Realtime Database | Users, clients, venues, dashboard snapshots, market readiness, pipeline runs |
| Firebase Security Rules | Enforce role and venue-level access |
| Firebase Storage | Protected report/PDF downloads and evidence appendices |
| Firebase Hosting | Possible future hosting target for full site or authenticated app shell |

---

## 3. Hosting decision

DayDine will initially follow a **hybrid path**.

### Phase 1 — Hybrid

- Keep public/static site on current hosting temporarily.
- Add Firebase Auth and database-backed client/admin records.
- Use Firebase security rules to protect client/admin data.
- Keep public ranking JSON public.
- Treat static `/operator/*` and `/admin/*` pages as prototype/internal until migrated.

### Phase 2 — Firebase-first option

Once auth, rules and data model are stable, evaluate moving the whole app to Firebase Hosting.

The move to Firebase Hosting is not required before the first auth/data migration if the hybrid approach is working safely.

---

## 4. Data boundary

### Public-safe data

May be exposed as static JSON or public Firebase reads:

```text
public rankings
public coverage summaries
public methodology metadata
public establishment lookup fields
public market list
```

### Protected client/admin data

Must require Firebase Auth and rules:

```text
client dashboards
operator action priorities
report download URLs
client records
billing/subscription status
admin market QA
pipeline runs
ambiguous entity review queues
private notes
raw evidence appendices
```

---

## 5. Access model

### Roles

```text
admin
client
viewer
```

### Required access rules

1. Unauthenticated users may read only public data.
2. Clients may read only venues assigned to their client account.
3. Viewers may read limited assigned client data.
4. Admins may read/write admin records.
5. No client can read another client's dashboard.
6. Admin-only writes must be enforced by Firebase rules, not frontend hiding.

---

## 6. Monthly data pipeline decision

DayDine will not call paid third-party APIs from user page views.

Correct model:

```text
Monthly scheduled pipeline
  -> pull/enrich/cache FSA, Google, Tripadvisor, Companies House
  -> resolve entities
  -> calculate scores/ranks
  -> generate coverage certificates
  -> generate public ranking assets
  -> generate protected client snapshots
  -> store pipeline run summary and cost logs
```

Incorrect model:

```text
User opens a page
  -> live Google/Tripadvisor API calls
```

---

## 7. Methodology boundary

Public rankings and operator dashboards may use different scoring emphasis.

| Surface | Purpose | Emphasis |
|---|---|---|
| Public rankings | diner-facing evidence confidence | public evidence, customer validation, coverage, confidence |
| Client dashboard | operator intelligence | movement, visibility, commercial readiness, action priorities |
| Admin console | QA/control | coverage, ambiguity, source freshness, publish decisions |

Public claim language must remain conservative:

Preferred:

```text
Top-ranked by DayDine's public-evidence confidence model.
```

Avoid:

```text
Objectively the best restaurants.
```

unless DayDine later adds first-party inspection, verified diner panels, critic partnerships or licensed editorial review data.

---

## 8. Consequences

### Positive consequences

- Public rankings stay fast and cheap.
- Client dashboards become secure and professional.
- Admin workflows become durable and role-protected.
- API costs can be controlled through monthly refreshes.
- The architecture supports future paid subscriptions.
- Existing prototype work can be migrated rather than discarded.

### Negative consequences / trade-offs

- More architecture complexity than a purely static site.
- Requires Firebase security rules and testing.
- Requires a data migration path from static JSON to Firebase records.
- Requires careful separation of public and private data.
- May eventually require hosting consolidation.

---

## 9. Migration plan

### Step 1 — Auth foundation

- Add `/login`.
- Add `/client` shell.
- Add `/admin` shell.
- Add Firebase Auth helpers.
- Add role guard logic.
- Add initial Firebase rules.

### Step 2 — First protected client dashboard

- Migrate Lambs dashboard into Firebase.
- Create `venues/lambs`.
- Create `clients/lambs`.
- Create `clientVenueAccess`.
- Render `/client/venues/lambs` from Firebase.

### Step 3 — Admin migration

- Move market readiness into Firebase.
- Move report manifests into Firebase.
- Add admin workflows for market status, client status and ambiguous-place review.

### Step 4 — Pipeline migration

- Keep GitHub Actions for pipeline orchestration if useful.
- Add Firebase writes for pipeline outputs.
- Add cost/API-call logs.
- Add admin publish/hold fields.

### Step 5 — Hosting review

- Evaluate whether public site remains on current hosting or moves to Firebase Hosting.
- Decide based on reliability, simplicity, auth integration and deployment workflow.

---

## 10. Current implementation instruction

The next engineering stage should be framed as:

```text
Build Firebase Auth foundation, reusing the existing Firebase project/config pattern from uk-establishments.html, while protecting client/admin data with Firebase Auth and security rules and preserving public lookup behaviour.
```

It should not be framed as a clean-room rewrite.

Before implementation, check:

```text
docs/DayDine-Prior-Work-Inventory.md
docs/DayDine-Roadmap-Implementation-Control.md
```

---

## 11. Status

Accepted for the next implementation phase.

This ADR can be superseded later if DayDine moves fully to Firebase Hosting or to another full-stack architecture.
