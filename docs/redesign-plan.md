# DayDine Website Redesign — Final Plan

## Context

DayDine's live site (`daydine.vercel.app`) is a single-file vanilla HTML/JS app that only exposes a location-based FSA search. The user has designed a new brand system (provided as a ~1,400-line React JSX file) covering 5 pages: Homepage, Rankings, Reports, Methodology, and Sample Report. The goal is to adopt the new visual system and page structure while keeping the existing Firebase search fully functional, so the site works both as a marketing funnel and as the interactive restaurant-lookup tool users already rely on.

## Confirmed decisions

| Question | Answer |
|---|---|
| Theme | Light theme using **existing cream/amber tokens** (`#F5F0E8` bg, `#D4942A` accent). Adopt the JSX typography and layout patterns; reinterpret its dark-theme overlays for cream. |
| Rankings UI | **Both pages**: new JSX-style static top-10 leaderboard at `/rankings` AND keep the existing Firebase location search at `/search`. |
| Methodology | **Hybrid**: JSX card shape + marketing tone, rewritten to reference the real RCS V3.4 tiers from `CLAUDE.md` (FSA 23% / Google 24% / Online 13% / Ops 15% / Menu 10% / Reputation 8% + Companies House penalties, plus convergence + temporal decay). |
| Scope | Full 5-page build · wire Rankings to real Stratford data from `stratford_rcs_scores.csv` · £149 pricing kept · CSS gold "D" logo mark (no PNG). |

## Stack: multi-page vanilla HTML

No React, no build step, no bundler. The JSX compiles 1:1 to DOM — it uses `useState` only for client-side page switching, which we replace with real URLs. Rationale: lowest regression risk, preserves the battle-tested Firebase/Leaflet code in the current `index.html`, and avoids a Vercel build pipeline for a site that never needed one.

## File structure

```
/
├── index.html              NEW  — marketing homepage (hero w/ search box)
├── rankings.html           NEW  — static top-10 leaderboard
├── reports.html            NEW  — sales page + £149 pricing card
├── methodology.html        NEW  — RCS V3.4 explainer (real tier content)
├── sample.html             NEW  — sample report mockup
├── search.html             RENAMED from current index.html (restyled, JS intact)
├── 404.html                NEW  — branded 404
├── assets/
│   ├── daydine.css         NEW  — shared tokens, typography, nav, buttons, badges
│   ├── daydine.js          NEW  — shared nav scroll-shadow + active-link helper
│   ├── rankings.json       NEW  — top 10 from stratford_rcs_scores.csv
│   ├── favicon.svg         NEW  — gold "D" mark
│   └── og-image.png        NEW  — 1200×630 wordmark on cream
└── vercel.json             EDIT — drop catch-all, add cleanUrls, add /search rewrite
```

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
- Hero: kicker "LOCAL MARKET INTELLIGENCE" · H1 "Know Where Your Restaurant Really Stands" · body copy from JSX · primary CTA "View Local Rankings" → `/rankings` · secondary CTA "Get Your Position Report" → `/reports` · **plus a small search box** that submits to `/search?q=<location>` (preserves muscle memory for bookmarked root URL).
- Rankings preview (top 5 from `rankings.json`) → `/rankings`
- How It Works (3 numbered cards) · Value Prop · Methodology brief (6 signal cards) · final CTA

### Rankings (`rankings.html`)
- Single area: **Stratford-upon-Avon** (replace JSX's Brighton/Hove/Lewes tabs — only one trial area).
- Data source: `assets/rankings.json` (top 10 rows from `stratford_rcs_scores.csv`: Arrow Mill, The Fox Inn, Shakespaw Cat Cafe, Gilks' Garage Cafe, Oxheart, The Red Lion, Espresso Barn, Nel's At The Pavilion, Stratford Manor Hotel, Costa).
- Inline as `<script type="application/json" id="rankings-data">` to avoid fetch flash.
- Each row: rank · name · category · `ScoreBadge` (RCS×10 for 0–100 visual, but also show raw 0–10 once prominently) · movement (all `NEW` for first deploy since no history).
- "Last updated: 8 April 2026 · Rankings refreshed quarterly" kicker above table.
- "Not in the Top 10?" CTA card → `/reports`.

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
`cleanUrls` makes `/rankings` serve `rankings.html`. Use absolute paths everywhere in links (`/rankings`, not `rankings.html`).

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

1. **`assets/daydine.css`** — tokens, typography, nav, buttons, `.card`, `.score-badge`, `.movement-indicator`, `.rank-row`, `.signal-card`, `.footer`. Lock the design system first.
2. **`assets/rankings.json`** — hand-edit top 10 from CSV with `last_updated: "2026-04-08"`.
3. **`assets/favicon.svg`** — gold-gradient "D" mark.
4. **`assets/og-image.png`** — 1200×630 wordmark on cream. (If image generation isn't available, defer — sharing will still work without it.)
5. **`index.html`** — new homepage. Exercises most tokens; proving-ground for the system. Hero + search box + rankings preview + 3-step + value prop + methodology brief + CTA.
6. **`rankings.html`** — consume `rankings.json`; verify ScoreBadge translation on real data.
7. **`methodology.html`** — highest content-verification burden; copy tier percentages from `CLAUDE.md` literally, do not paraphrase numbers.
8. **`sample.html`** — consumes badges + rank row visuals from 6 & 7.
9. **`reports.html`** — feature grid + pricing + waitlist teaser with mailto CTAs.
10. **`search.html`** — copy current `index.html`, replace inline style block with `daydine.css` link + page-local style, add `?q=` URL param handler. Preserve ALL existing JS.
11. **`404.html`** — branded catch-all.
12. **`vercel.json`** — drop catch-all, add `cleanUrls` and `/search` rewrite.
13. **Polish pass** — OG tags, canonical URLs, favicons, nav active states, mobile, accessibility audit.

## Verification

End-to-end per page. Test on desktop (1440px) and mobile (375px) at minimum.

- **`/` (homepage)**: hero renders, search box submits to `/search?q=CV37` and that page auto-runs search, rankings preview shows 5 cards, nav links resolve, no console errors.
- **`/rankings`**: JSON inlined, top 10 render in order (Arrow Mill first at 9.923), ScoreBadge colours map to RCS bands correctly, "Last updated" visible, "Not in Top 10?" CTA → `/reports`.
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

## Plan status: READY FOR EXECUTION
