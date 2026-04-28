# DayDine Client Dashboard Pilot Pattern

**Status:** Planning clarification  
**Created:** 28 April 2026  
**Purpose:** Clarify that any reference to migrating the Lambs dashboard means using one existing dashboard as a seed/test case for a reusable protected dashboard system, not making Lambs the strategic focus of DayDine.

---

## 1. Clarification

The next SaaS build phase is **not** about building DayDine around one restaurant.

The real objective is:

> Build a reusable Firebase-authenticated client-dashboard framework that can support any paid restaurant/operator client.

Lambs is mentioned only because the repo already contains a relatively rich, report-aligned prototype dashboard and JSON asset for that venue. It is useful as a seed record because it lets the build test the full pattern against existing data rather than inventing dummy content.

---

## 2. Correct interpretation of “Lambs migration”

When planning docs mention Lambs migration, interpret it as:

> Use one existing report-aligned dashboard as the first test fixture to prove the protected client portal, venue access model, dashboard rendering, monthly snapshot structure and admin management workflow.

It does **not** mean:

- Lambs is the only restaurant that matters;
- DayDine should build bespoke logic for Lambs;
- the product should delay wider market work until Lambs is perfect;
- the business model depends on selling Lambs specifically.

---

## 3. Better build objective

The build objective should be named:

> **Protected Client Dashboard Framework**

not:

> Lambs dashboard migration

The framework should support:

```text
clients/{clientId}
venues/{venueId}
clientVenueAccess/{clientId}_{venueId}
operatorDashboards/{venueId}/snapshots/{month}
```

The same pattern should work for:

- Lambs;
- Loxley’s;
- The Vintner;
- an invented/demo client;
- multi-venue operators;
- future Stratford/Leamington/Oxford/Bath clients.

---

## 4. Recommended implementation pattern

### Step 1 — Build the framework

Implement:

```text
/login
/client
/client/venues
/client/venues/<venueId>
/admin
role-aware route guards
Firebase security rules
```

### Step 2 — Seed one dashboard as a fixture

Use whichever fixture is easiest and most complete.

Current likely fixture:

```text
assets/operator-dashboards/lambs/latest.json
```

But this can be replaced by a demo venue or another real venue if preferred.

### Step 3 — Prove access control

Acceptance criteria:

```text
[ ] Client A can see only assigned venues.
[ ] Client A cannot read another venue dashboard.
[ ] Admin can see/manage all venues.
[ ] Dashboard rendering is generic, not hard-coded to Lambs.
[ ] Adding a second venue requires data/config only, not bespoke code.
```

### Step 4 — Add second fixture quickly

To prove this is not a one-restaurant build, the next dashboard seed after the first should be a second venue or a demo client.

Recommended acceptance criterion:

```text
[ ] At least two dashboard records can be rendered through the same protected client framework before paid-client readiness is claimed.
```

---

## 5. Planning language to use going forward

Use:

> Build protected client dashboard framework and seed it with the first existing dashboard fixture.

Avoid:

> Build the Lambs dashboard.

Use:

> Lambs may be the first fixture because existing report-aligned data already exists.

Avoid:

> Lambs is the core client-dashboard strategy.

---

## 6. Relationship to roadmap

This note should be read alongside:

```text
docs/DayDine-Professional-SaaS-Roadmap.md
docs/DayDine-Current-State-And-Next-Actions.md
docs/DayDine-Launch-Readiness.md
```

Any future implementation should treat the dashboard work as reusable SaaS infrastructure first and venue-specific migration second.
