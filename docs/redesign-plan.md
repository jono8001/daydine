# DayDine Website Redesign — Final Plan

## Context

DayDine's live site (`daydine.vercel.app`) is a single-file vanilla HTML/JS app that only exposes a location-based FSA search. The user has designed a new brand system (provided as a ~1,400-line React JSX file) covering 5 pages: Homepage, Rankings, Reports, Methodology, and Sample Report. The goal is to adopt the new visual system and page structure while keeping the existing Firebase search fully functional, so the site works both as a marketing funnel and as the interactive restaurant-lookup tool users already rely on.

## Confirmed decisions

| Question | Answer |
|---|---|
| Theme | Light theme using **existing cream/amber tokens** (`#F5F0E8` bg, `#D4942A` accent). Adopt the JSX typography and layout patterns; reinterpret its dark-theme overlays for cream. |
| Rankings UI | **Both pages**: new JSX-style top-10 leaderboard at `/rankings` (scales to any UK Local Authority via postcodes.io lookup) AND keep the existing Firebase location search at `/search`. |
| Methodology | **Hybrid**: JSX card shape + marketing tone, rewritten to reference the real RCS V3.4 tiers from `CLAUDE.md` (FSA 23% / Google 24% / Online 13% / Ops 15% / Menu 10% / Reputation 8% + Companies House penalties, plus convergence + temporal decay). |
| Scope | Full 5-page build · wire Rankings to real Stratford data from `stratford_rcs_scores.csv` · £149 pricing kept · CSS gold "D" logo mark (no PNG). |
| Rankings scope | **Top 10 by name** only. Below the leaderboard, show a numeric count of other ranked venues (e.g. "and 187 other ranked restaurants in Stratford-upon-Avon") WITHOUT naming them — this drives the Reports funnel ("request a report to find out where you stand"). |
| Multi-area scaling | `/rankings` is a landing page with postcodes.io search + browse chips. Each covered area lives at `/rankings/[la-slug]` (e.g. `/rankings/stratford-on-avon`). Uncovered LAs show a waitlist empty state. New areas added by dropping a JSON file + updating an index. |

## Stack: multi-page vanilla HTML

No React, no build step, no bundler. The JSX compiles 1:1 to DOM — it uses `useState` only for client-side page switching, which we replace with real URLs. Rationale: lowest regression risk, preserves the battle-tested Firebase/Leaflet code in the current `index.html`, and avoids a Vercel build pipeline for a site that never needed one.

## File structure

```
/
├── index.html                      NEW  — marketing homepage (hero w/ search box)
├── rankings.html                   NEW  — Rankings landing (area search + browse)
├── rankings/
│   └── stratford-on-avon.html      NEW  — per-area top-10 leaderboard
├── reports.html                    NEW  — sales page + £149 pricing card
├── methodology.html                NEW  — RCS V3.4 explainer (real tier content)
├── sample.html                     NEW  — sample report mockup
├── search.html                     RENAMED from current index.html (restyled, JS intact)
├── 404.html                        NEW  — branded 404
├── assets/
│   ├── daydine.css                 NEW  — shared tokens, typography, nav, buttons, badges
│   ├── daydine.js                  NEW  — shared nav scroll-shadow + active-link helper
│   ├── rankings/
│   │   ├── index.json              NEW  — registry of available areas + last_updated
│   │   └── stratford-on-avon.json  NEW  — top 10 + metadata for Stratford
│   ├── favicon.svg                 NEW  — gold "D" mark
│   └── og-image.png                NEW  — 1200×630 wordmark on cream
├── scripts/
│   └── build_rankings.py           NEW  — generates assets/rankings/*.json from RCS CSVs
└── vercel.json                     EDIT — drop catch-all, add cleanUrls, add rewrites
```

**Per-area page pattern**: each LA gets its own `rankings/[la-slug].html` for SEO. The HTML is templated (near-identical across areas) — the content is loaded from `assets/rankings/[la-slug].json`. Adding a new area later = run `build_rankings.py`, then duplicate the HTML template with the new slug. The Python script is a one-shot CLI now; it can be wired into a GitHub Action later when the RCS pipeline expands beyond Stratford.

## Design token translation (dark JSX → light existing)

| JSX token | Existing / new token | Notes |
|---|---|---|
| `#0a0c10` bg | `var(--bg) #F5F0E8` | Cream base |
| `rgba(255,255,255,0.02)` surface | `var(--surface-1) #FFFFFF` | Promote current `--bg-card` |
| `rgba(255,255,255,0.04)` surface | `var(--surface-2) #FBF8F3` | Promote current `--bg-row-hover` |
| `rgba(255,255,255,0.06)` surface | `var(--surface-3) #FAF7F1` | Promote current `--bg-expanded` |
| `rgba(255,255,255,0.06)` border | `var(--border) #E5DFD3` | Existing |
| `#fff` primary text | `var(--text) #2D2D2D` | Existing |
| `#94a3b8` secondary | `var(--text-muted) #7A7265` | Existing (verify AA on `--surface-2`) |
| `#64748b` tertiary | `var(--text-subtle) #9B9285` | New |
| `#d4a574` gold accent | `var(--accent) #D4942A` | Existing |
| `linear-gradient(135deg,#d4a574,#c4956a)` | `linear-gradient(135deg,#D4942A,#B87D1E)` | Button |
| Hero radial glow `rgba(212,165,116,0.08)` | `rgba(212,148,42,0.14)` | Bumped — 0.08 is invisible on cream |
| Nav blur `rgba(10,12,16,0.9)+blur(12px)` | Solid `var(--surface-2)` + bottom border + scroll-linked shadow | Blur on cream looks washed out |
| ScoreBadge dark teal/navy | New `--band-excellent/good/satisfactory/improvement/major/urgent` tokens (bg + fg pair per RCS band) | Don't reuse FSA pill colors — semantic conflation |

New fonts added alongside existing Inter:
- **Cormorant Garamond** (400/500/600/700) — headlines
- **DM Mono** (400/500) — kickers, rank numbers, data labels
- `font-display: swap` + preconnect; set min 18px for serif body copy to meet contrast/legibility.

## Content mapping

### Homepage (`index.html`)
- Hero: kicker "LOCAL MARKET INTELLIGENCE" · H1 "Know Where Your Restaurant Really Stands" · body copy from JSX · primary CTA "View Local Rankings" → `/rankings` · secondary CTA "Get Your Position Report" → `/reports` · **plus a small area search box** with postcodes.io autocomplete that resolves to an LA slug and routes to either `/rankings/[slug]` (if covered) or the waitlist empty-state (if not). Same resolver logic as the `/rankings` landing page.
- Rankings preview (top 5 from `assets/rankings/stratford-on-avon.json`) → `/rankings/stratford-on-avon`
- How It Works (3 numbered cards) · Value Prop · Methodology brief (6 signal cards) · final CTA

### Rankings landing (`rankings.html`)

The entry point for the Rankings section. Architected to scale from 1 area today to hundreds of UK LAs.

**Layout:**
- H1 "Local Rankings" · body "Find the best restaurants in your area"
- Big search box with postcodes.io autocomplete — lifts the existing implementation from `search.html` (the debounced `/places` + `/postcodes` flow at `index.html:639-731`). Accepts postcodes (`CV37`, `BN1 1AA`) or town names (`Brighton`, `Stratford`).
- On select → resolve to `admin_district` (LA name) → slugify → navigate to `/rankings/[slug]`.
- **"Currently covering"** section: clickable chips listing live areas, populated at build time from `assets/rankings/index.json`. For MVP: a single `[Stratford-upon-Avon]` chip + "more coming soon" text.
- Loads `assets/rankings/index.json` on page load via inline `<script type="application/json">` (no fetch flash).

**Empty-state handling:** if the user searches an uncovered LA, `/rankings/[slug].html` won't exist → hits `404.html`. Smarter: the landing page JS checks if the resolved slug is in `index.json.available[]` before redirecting. If not, show an inline "Coming to [area] — [Notify me]" card with a `mailto:hello@daydine.com?subject=Waitlist:%20[area]` link. This turns dead-ends into demand signals per area.

### Per-area leaderboard (`rankings/stratford-on-avon.html`)

Template page — one per covered LA. Stratford is the only one at launch.

**Layout (matches JSX Rankings page shape):**
- Kicker: "LOCAL RANKINGS"
- H1: "Top 10 in Stratford-upon-Avon"
- Data source: `assets/rankings/stratford-on-avon.json`, inlined as `<script type="application/json" id="rankings-data">` to avoid fetch flash.
- Ranking table with 10 rows only. Each row: rank · name · postcode · category · `ScoreBadge` (RCS×10 for 0–100 visual, plus raw `9.923 / 10` label) · movement (all `NEW` for first deploy — no history yet).
- Values sourced from `stratford_rcs_scores.csv` top 10: Arrow Mill, The Fox Inn, Shakespaw Cat Cafe, Gilks' Garage Cafe, Oxheart, The Red Lion, Espresso Barn, Nel's At The Pavilion, Stratford Manor Hotel, Costa.
- "Last updated: 8 April 2026 · Rankings refresh quarterly" kicker above the table.

**Below the Top 10 — the Reports funnel driver:**

```
─────────────────────────────────────────────
and 187 other ranked restaurants in Stratford-upon-Avon

Is your venue ranked outside the top 10?
Order a Position Report to discover exactly where you stand,
who's directly ahead of you, and what to do about it.

[Get My Position Report — £149]
─────────────────────────────────────────────
```

- The count "187" = `total_venues - 10` pulled from `stratford-on-avon.json` (total ranked = 197, minus the 10 shown = 187).
- **No names** of non-top-10 venues are ever shown on any public page. Only the total count, and only an operator who orders the report sees their own rank, their 5 closest competitors, and gap analysis (matches the Sample Report mockup).
- This replaces the JSX's generic "Not in the Top 10?" card with a stronger, quantified CTA.
- Copy is parameterised by area: "and {count} other ranked restaurants in {area}" — so a future Brighton page reads "and 312 other ranked restaurants in Brighton and Hove" with zero code changes.

**Edge case — areas with ≤10 ranked venues:** if the LA has fewer than 10 ranked venues (small towns/rural LAs), show all of them as "Top N in [area]" and hide the "and X others" line. Logic: `if total_venues > 10: show count line else: hide`.

### `assets/rankings/index.json` schema

```json
{
  "last_updated": "2026-04-08",
  "available": [
    {
      "slug": "stratford-on-avon",
      "la_name": "Stratford-on-Avon",
      "display_name": "Stratford-upon-Avon",
      "total_venues": 197,
      "top_score": 9.923
    }
  ]
}
```

### `assets/rankings/stratford-on-avon.json` schema

```json
{
  "la_name": "Stratford-on-Avon",
  "display_name": "Stratford-upon-Avon",
  "slug": "stratford-on-avon",
  "total_venues": 197,
  "others_count": 187,
  "last_updated": "2026-04-08",
  "venues": [
    {
      "rank": 1,
      "name": "Arrow Mill",
      "postcode": "B49 5NL",
      "category": "Pub / Bar",
      "rcs_final": 9.923,
      "rcs_band": "Excellent",
      "convergence": "converged",
      "movement": "new"
    }
    // ... 9 more
  ]
}
```

### `scripts/build_rankings.py` (new)

Python 3 CLI. Reads a `_rcs_scores.csv` file (same format as `stratford_rcs_scores.csv`) and emits the corresponding `assets/rankings/[slug].json`. Also updates `assets/rankings/index.json` (adds/refreshes the entry). Fields:
- Input: CSV path, LA display name, LA slug (auto-derived if omitted)
- Output: top 10 venues with required fields, total_venues count, others_count, last_updated
- Usage: `python scripts/build_rankings.py --csv stratford_rcs_scores.csv --la "Stratford-on-Avon" --display "Stratford-upon-Avon"`
- One-shot tool for v1. Later: called from the `.github/workflows/enrich_and_score.yml` workflow to regenerate JSON alongside CSV output.

### Reports (`reports.html`)
- 6 feature cards from JSX verbatim
- Pricing card: **£149** (kept as confirmed). CTA button wired to `mailto:hello@daydine.com?subject=Position%20Report%20Request` (no dead Stripe/checkout route).
- Coming Soon: Competitor Watch waitlist (same mailto).

### Methodology (`methodology.html`)
Hybrid content — JSX card shapes, real RCS V3.4 content. Replace the 6 generic JSX signals with the 7 real tiers plus two sidebars:
| Tier | Weight | What it measures |
|---|---|---|
| Food Safety | 23% | FSA hygiene rating, structural, CIM, inspection recency |
| Google Signals | 24% | Rating, reviews, aspect sentiment, price, photos |
| Online Presence | 13% | TripAdvisor + web/FB/IG confidence |
| Operational | 15% | Reservations, delivery, hours, accessibility |
| Menu & Offering | 10% | Online menu, dietary options, cuisine breadth |
| Reputation & Awards | 8% | Michelin, AA, local awards |
| Companies House | penalty-only | Dissolution/liquidation/overdue accounts/director churn |

Sidebars: **Temporal Decay** (λ=0.0023 FSA half-life, λ=0.0046 reviews) · **Cross-source Convergence** (±3–5% when Google/FSA/TA agree or diverge). Source numbers literally from `CLAUDE.md` — no paraphrasing.

### Sample (`sample.html`)
JSX mockup verbatim, recoloured for cream. Rankings/competitors are `[Sample Venue]` placeholders. Priority action pills use new `--band-*` tokens.

### Search (`search.html`)
- Current `index.html` copied to `search.html`. All JS kept intact (Firebase compat SDK, Leaflet, postcodes.io, haversine, pagination, Near Me, mobile card layout).
- Inline `<style>` block replaced with `<link href="/assets/daydine.css">` + a small page-local `<style>` for search-specific layout (filters bar, map container, result cards).
- New: parse `?q=` on load → populate `fLocation.value` → auto-run search. ~15 extra lines.
- Firebase SDKs load ONLY here, not on any marketing page.
- Verify Leaflet still renders correctly with the new `box-sizing: border-box` reset (already present — should be unchanged).

### 404 (`404.html`)
Branded shell with nav + footer + "That page moved or doesn't exist" + links to Home / Rankings / Search.

## Vercel config change

Current `vercel.json` has `{"src": "/(.*)", "dest": "/index.html"}` — this breaks multi-page routing. Replace with:
```json
{
  "cleanUrls": true,
  "trailingSlash": false,
  "rewrites": [
    { "source": "/search", "destination": "/search.html" }
  ]
}
```
`cleanUrls` makes `/rankings` serve `rankings.html` and `/rankings/stratford-on-avon` serve `rankings/stratford-on-avon.html`. Use absolute paths everywhere in links (`/rankings/stratford-on-avon`, not relative).

## Cross-cutting requirements (per page)

- `<meta name="color-scheme" content="light">` to prevent Dark Reader extensions from muddying cream
- Unique `<title>`, `<meta name="description">`, `<link rel="canonical">` per page
- `og:title` / `og:description` / `og:image` (= `/assets/og-image.png`) / `og:url` per page
- `<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">` + `apple-touch-icon`
- Mobile condensed nav row (no hamburger needed — 4 short links fit): `Home · Rankings · Reports · Methodology` with tagline hidden <720px
- Active nav link gets `.active` class per page (hardcoded, no JS required)
- Nav active state also shows on `/search` when that page is active
- Accessibility: verify `--text-muted #7A7265` on `--surface-2 #FBF8F3` passes WCAG AA (borderline — test before shipping); minimum 16px Inter for body, 18px for any Cormorant body text

## Critical files referenced

- `/home/user/daydine/index.html` — source for JS logic and design tokens (rename → `search.html`, create new `index.html`)
- `/home/user/daydine/vercel.json` — routing rewrite
- `/home/user/daydine/stratford_rcs_scores.csv` — source for `assets/rankings.json` top 10 (Arrow Mill at RCS 9.923 = rank 1)
- `/home/user/daydine/.claude/CLAUDE.md` — authoritative tier weights + convergence + decay content for methodology page
- `/home/user/daydine/UK-Restaurant-Tracker-Methodology-Spec-V3.md` — fallback methodology reference

## Execution order

1. **`assets/daydine.css`** — tokens, typography, nav, buttons, `.card`, `.score-badge`, `.movement-indicator`, `.rank-row`, `.signal-card`, `.footer`, area search box, chip. Lock the design system first.
2. **`scripts/build_rankings.py`** — Python CLI to convert RCS CSV → per-LA JSON. Idempotent; updates `index.json` registry. Run once to produce Stratford files.
3. **`assets/rankings/index.json`** + **`assets/rankings/stratford-on-avon.json`** — generated by step 2. Verify by hand.
4. **`assets/favicon.svg`** — gold-gradient "D" mark.
5. **`assets/og-image.png`** — 1200×630 wordmark on cream. (Defer if image generation isn't available — sharing still works without it.)
6. **`index.html`** — new homepage. Exercises most tokens; proving-ground for the system. Hero + area search box + rankings preview + 3-step + value prop + methodology brief + CTA.
7. **`rankings.html`** — landing page with area search + "Currently covering" chips + empty-state waitlist. Reuses the homepage area search implementation.
8. **`rankings/stratford-on-avon.html`** — per-area leaderboard template. Consumes `stratford-on-avon.json`; verify ScoreBadge translation on real data; verify "and 187 others" count + Reports CTA render correctly.
9. **`methodology.html`** — highest content-verification burden; copy tier percentages from `CLAUDE.md` literally, do not paraphrase numbers.
10. **`sample.html`** — consumes badges + rank row visuals from earlier steps.
11. **`reports.html`** — feature grid + pricing + waitlist teaser with mailto CTAs.
12. **`search.html`** — copy current `index.html`, replace inline style block with `daydine.css` link + page-local style, add `?q=` URL param handler. Preserve ALL existing JS.
13. **`404.html`** — branded catch-all.
14. **`vercel.json`** — drop catch-all, add `cleanUrls` and `/search` rewrite.
15. **Polish pass** — OG tags, canonical URLs, favicons, nav active states, mobile, accessibility audit.

## Verification

End-to-end per page. Test on desktop (1440px) and mobile (375px) at minimum.

- **`/` (homepage)**: hero renders, area search box resolves "Stratford" → `/rankings/stratford-on-avon`, "Brighton" → waitlist empty state, rankings preview shows 5 cards from Stratford JSON, nav links resolve, no console errors.
- **`/rankings`**: landing page renders, search autocomplete works for postcodes (`CV37`) and town names (`Stratford`, `Brighton`), "Currently covering" chip for Stratford is clickable, selecting an uncovered area shows the waitlist card with correct area name, no fetch flash.
- **`/rankings/stratford-on-avon`**: top 10 render in order (Arrow Mill first at 9.923), ScoreBadge colours map to RCS bands correctly, "Last updated 8 April 2026" visible, "and 187 other ranked restaurants in Stratford-upon-Avon" count visible, Reports CTA → `/reports`, no names of venues ranked 11–197 are exposed anywhere in the DOM or source.
- **`/reports`**: feature grid responsive at 375/768/1200, pricing card shows £149, mailto CTAs open mail client, waitlist teaser renders.
- **`/methodology`**: tier percentages exactly match `CLAUDE.md` (23/24/13/15/10/8 + CH penalties); convergence (+3% / -3% / -5%) and temporal decay (λ=0.0023 / λ=0.0046) both explained; no unexplained jargon.
- **`/sample`**: mockup renders, signal breakdown progress bars show, no real data leakage, priority pills styled.
- **`/search`**: Firebase connects (check console), Leaflet map renders, Near Me works, Stratford postcode search returns results, table sort works on all 5 sortable columns, pagination works, expand/collapse works, `?q=stratford-upon-avon` auto-runs, mobile card layout (`data-label`) intact.
- **`/404` or any typo**: branded 404 with nav + footer + links back.
- **Cross-cutting**: `view-source` on every page shows unique title + description + canonical + og tags; favicon shows in browser tab; Lighthouse accessibility >90 on every page; DevTools contrast checker passes on `--text-muted` over `--surface-2`; no layout shift on serif fonts loading.

## Known risks

1. **Amber-on-cream contrast** for `--text-muted` (`#7A7265` on `#FBF8F3`) is borderline AA — test with contrast checker before ship; nudge darker if fails.
2. **Font loading flash** — triple Google Fonts payload (Inter + Cormorant + DM Mono) may cause FOIT on hero. Use `font-display: swap` + preconnect.
3. **Methodology page is load-bearing credibility** — a wrong tier percentage undermines trust. Dedicated content-verification pass required.
4. **£149 pricing is display-only** — no checkout wired. `mailto:` fallback is intentional for v1; upgrade to a form service later.
5. **First deploy has no historical rank movement** — all venues show `NEW` badge. Plan a follow-up to compute deltas once we have a second ranking snapshot.
6. **Renaming `index.html` → `search.html`** changes the root URL semantics. Hero search box mitigates most of this, but consider a soft-launch banner for 2 weeks ("Looking for the search tool? It's at /search").
7. **Rankings JSON is stale by design** — it's snapshot data. Display "Rankings refreshed quarterly" prominently to set expectations.
8. **`assets/og-image.png` requires image generation** — may need to defer or create with an external tool. Everything else ships without it.
9. **Data leakage risk** — the Reports funnel depends on venues ranked 11+ being unnamed on public pages. Audit before ship: `grep -r` the venue names from Stratford ranks 11–197 across every HTML file to confirm none leak. Also check `rankings/stratford-on-avon.json` only contains the top 10 venues array (not all 197), so the source never exposes them either.
10. **Slug collisions** — `stratford-on-avon` is the LA slug, but the user-facing display name is `Stratford-upon-Avon` (the town, with "upon" not "on"). Every page must be explicit about which to use: slug for URLs/filenames, display name for headlines/copy. The JSON schema has both fields to avoid mistakes. Double-check at least once per area.
11. **Postcodes.io rate limits** — the service is free with generous limits but not infinite. The area search box on Rankings landing + homepage hero + Search page all call the same API. Should be fine for current traffic, but add a debounce (250ms, already in the existing code) and swallow errors silently if the API 429s.

## Plan status: READY FOR EXECUTION
