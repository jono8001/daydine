# DayDine Launch Readiness

**Status:** Working readiness checklist  
**Created:** April 2026  
**Purpose:** Define what must be true before DayDine is treated as a professional public ranking product and paid client SaaS, rather than a prototype.

---

## 1. Current judgement

DayDine has a strong prototype foundation, but it is not yet professional-launch ready for paying clients.

| Area | Current status | Reason |
|---|---|---|
| Public rankings | Amber | Useful, but needs coverage certificates, stable public methodology and further market QA. |
| Client dashboards | Red/Amber | Good product shape, but currently static/prototype and not protected by proper login/security. |
| Admin tooling | Red/Amber | Useful internal static pages, but no real auth, roles or persistent workflow state. |
| Methodology | Amber | V4 is a good base, but public claims and V5/confidence roadmap need tightening. |
| Data pipeline | Amber | Repeatable generated assets exist, but true monthly external refresh/cost logging is not complete. |
| Security | Red | Static hidden URLs and noindex are not client-grade security. Firebase Auth/rules required. |

---

## 2. Launch categories

DayDine should be evaluated against three different launch standards.

### 2.1 Internal prototype

Safe for internal review and development.

Requirements:

- static admin pages acceptable;
- prototype operator dashboards acceptable;
- manual data updates acceptable;
- public claims must be conservative.

Current status: **mostly met**.

### 2.2 Public beta

Safe for public diners/prospects to view rankings.

Requirements:

- public methodology is clear and non-misleading;
- market coverage certificate exists;
- known missing venues are handled;
- ambiguous venues are excluded or labelled;
- ranking pages show last updated date;
- correction/report issue path exists;
- no private client/admin data exposed.

Current status: **not fully met**.

### 2.3 Paid client SaaS

Safe to sell to restaurants/operators.

Requirements:

- Firebase Auth or equivalent login;
- client users can only access their own venue dashboards;
- admin users are role-gated;
- client dashboards are served from protected database records, not public JSON;
- report downloads are protected or signed;
- monthly snapshots are retained;
- billing/subscription status exists;
- privacy/terms are present;
- support/correction process exists.

Current status: **not yet met**.

---

## 3. Must-fix blockers before paid clients

### Blocker 1 — Client/admin access is not secure enough

Current issue:

- `/operator/*`, `/admin/markets`, `/admin/reports` and static JSON assets are hidden/internal but not truly protected.

Required fix:

- Add Firebase Auth.
- Add roles: `admin`, `client`, `viewer`.
- Add Firebase security rules.
- Move client dashboard data into protected Firebase records.

Acceptance criteria:

- unauthenticated user cannot access client/admin data;
- client cannot read another client's dashboard;
- admin writes require admin role.

---

### Blocker 2 — Client dashboard data is still static/prototype

Current issue:

- Lambs dashboard is report-aligned and useful, but static JSON is still the canonical source.

Required fix:

- Seed Lambs into Firebase as first protected client record.
- Render `/client/venues/lambs` from Firebase.
- Treat `/operator/lambs` as prototype or redirect behind login.

Acceptance criteria:

- Lambs dashboard only loads after login;
- report-aligned facts are preserved;
- monthly history remains visible;
- static JSON is not the private source of truth.

---

### Blocker 3 — Public market coverage is not yet certified

Current issue:

- Ranking outputs exist, but the public site does not yet show a formal coverage certificate explaining source universe, exclusions, ambiguous venues and known missing venues.

Required fix:

- Generate coverage certificates for Stratford-upon-Avon and Leamington Spa.
- Add public-safe coverage summary to ranking pages.
- Add admin full certificate view.

Acceptance criteria:

- public users can see coverage confidence;
- admin can see detailed source/exclusion/ambiguity counts;
- high-profile missing venues are not silently absent.

---

### Blocker 4 — Methodology language is still transitional

Current issue:

- Existing docs contain V3.4/V4 transition language. That is acceptable internally but not ideal for launch.

Required fix:

- Decide public methodology version for beta.
- Rewrite methodology page in stable public language.
- Move V3/V4/V5 transition and experimentation notes into internal docs.

Acceptance criteria:

- public methodology explains what DayDine ranks and does not rank;
- no overclaim that DayDine objectively identifies the best restaurants;
- confidence classes and coverage are explained.

---

### Blocker 5 — Monthly refresh pipeline is not yet true end-to-end collection

Current issue:

- The market pipeline is deterministic and useful, but it does not yet perform full external data collection/enrichment for new markets.

Required fix:

- Add monthly cached refresh stages for FSA/FHRS, Google, Tripadvisor metadata and Companies House.
- Add cost/API-call logging.
- Store pipeline run summaries.
- Add admin approve/publish workflow.

Acceptance criteria:

- no expensive API calls occur on user page views;
- monthly run produces a cost estimate and output summary;
- admin can approve/hold a market refresh.

---

## 4. Public beta readiness checklist

A market is public-beta ready when:

```text
[ ] Market has configured geography and data source prefix.
[ ] Source venue universe is complete enough for beta.
[ ] FSA/FHRS base records are loaded.
[ ] Google Place matches are resolved or marked ambiguous.
[ ] Known high-profile venues are present or explained.
[ ] Public ranking output exists.
[ ] Category ranking output exists.
[ ] Coverage certificate exists.
[ ] Ambiguous entities are excluded or labelled appropriately.
[ ] Public methodology version is stable.
[ ] Ranking page shows last updated date.
[ ] Ranking page links to methodology.
[ ] Ranking page links to correction/report issue flow.
[ ] No private client/admin data is visible.
```

---

## 5. Paid client readiness checklist

DayDine is paid-client ready when:

```text
[ ] Firebase Auth is enabled.
[ ] Admin role exists.
[ ] Client role exists.
[ ] Client venue access model exists.
[ ] Firebase security rules enforce venue-level access.
[ ] /login exists.
[ ] /client exists.
[ ] /admin exists.
[ ] Lambs dashboard is migrated into protected Firebase data.
[ ] Client dashboard retains monthly history.
[ ] Client dashboard preserves report-aligned commercial facts.
[ ] Report/export download is protected or signed.
[ ] Admin can mark dashboard status: draft/review/ready/sent/active.
[ ] Terms/privacy pages exist.
[ ] Client correction/support path exists.
[ ] Billing/subscription status exists, even if manual initially.
```

---

## 6. Methodology readiness checklist

DayDine methodology is launch-ready when:

```text
[ ] Public claim language is agreed.
[ ] Public method does not overclaim objective restaurant quality.
[ ] FHRS is clearly framed as compliance/trust, not food quality.
[ ] Customer validation is bias/shrinkage-aware.
[ ] Confidence/rankability is separate from score.
[ ] Single-platform evidence caps confidence.
[ ] Entity ambiguity affects rankability.
[ ] Coverage certificates are part of trust model.
[ ] V3/V4/V5 transition notes are internal, not confusing public copy.
[ ] Correction/appeal process exists.
```

---

## 7. Data-cost readiness checklist

Monthly pipeline is cost-ready when:

```text
[ ] Google calls happen only in batch refresh.
[ ] Tripadvisor calls happen only in batch refresh.
[ ] OpenTable is not a core dependency yet.
[ ] API call counts are logged.
[ ] Estimated monthly API cost is logged.
[ ] Cached source responses are retained.
[ ] Google Place IDs are reused.
[ ] Field masks are used for Google requests.
[ ] Full review text is not collected at scale.
[ ] Admin can see cost and warning summary after each run.
```

---

## 8. Security readiness checklist

Security is launch-ready when:

```text
[ ] Firebase security rules are present.
[ ] Rules are tested.
[ ] Client cannot read another client's venue.
[ ] Admin-only writes are enforced.
[ ] Static private dashboard JSON is removed or no longer canonical.
[ ] Static admin pages are protected or deprecated.
[ ] Report downloads are protected or signed.
[ ] No secret API keys are committed.
[ ] Browser-exposed Firebase config is limited to public-safe config.
[ ] Admin data cannot be read by unauthenticated users.
```

---

## 9. Do-not-launch warnings

Do not sell DayDine as a paid client portal if any of these remain true:

```text
[ ] Client dashboard is accessible via guessed public URL.
[ ] Client dashboard data lives only in public JSON.
[ ] Admin data is visible without auth.
[ ] Firebase rules allow broad public reads of private records.
[ ] Public methodology says or implies objective best-restaurant judgement without sufficient evidence.
[ ] A market has known missing high-profile venues with no explanation.
[ ] Ambiguous duplicate entities are silently included in rankings.
[ ] API calls can run uncontrolled from user page views.
```

---

## 10. Immediate launch-readiness next actions

1. Implement Firebase Auth foundation.
2. Create `/login`, `/client`, `/admin` shells.
3. Draft Firebase security rules.
4. Migrate Lambs dashboard into protected Firebase records.
5. Build Stratford and Leamington coverage certificates.
6. Rewrite public methodology once coverage/cutover decision is made.

---

## 11. Related project-memory files

Read these before implementation:

```text
docs/DayDine-Professional-SaaS-Roadmap.md
docs/DayDine-Prior-Work-Inventory.md
docs/DayDine-Roadmap-Implementation-Control.md
docs/DayDine-Current-State-And-Next-Actions.md
```
