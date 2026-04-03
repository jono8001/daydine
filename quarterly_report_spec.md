# Quarterly Strategic Intelligence Report — Specification

*DayDine Operator Intelligence — Version 1.0*
*Created: 3 April 2026*

---

## Purpose

The quarterly report is the **strategic companion** to the monthly operational report. Where the monthly report focuses on a single venue's management priorities and immediate actions, the quarterly report lifts the operator's perspective to:

1. **Estate-wide performance** — how all venues compare and trend over the quarter
2. **Local competitive landscape** — full peer rankings, new entrants, closures, shifts
3. **UK-wide restaurant intelligence** — what the best restaurants nationally are doing that operators can learn from
4. **Strategic direction** — quarter-level priorities, not day-to-day fixes

The quarterly report should feel like a **board-level briefing document**, not a longer version of the monthly report.

---

## Report Structure (12 Sections)

### Section 1: Executive Summary
**Mandatory** | Min 8 lines

- Quarter identifier (e.g. Q2 2026)
- Estate-wide headline: overall trajectory (improving/stable/declining)
- Strongest and weakest venue this quarter
- Biggest score movement (up and down)
- Top strategic priority for next quarter
- Data confidence statement (how many venues at each confidence tier)

### Section 2: Estate Performance Table
**Mandatory** | Full ranked table

All estate venues ranked side-by-side with:

| Venue | Overall | Exp | Vis | Trust | Conv | Prest | Qtr Trend | Band | Rank Change |
|-------|---------|-----|-----|-------|------|-------|-----------|------|-------------|

- Quarter-over-quarter score delta per dimension
- Trend arrows (up/down/stable)
- Band changes highlighted
- Rank movement vs prior quarter
- Colour-code: green = improved, red = declined, amber = watch

This is the single most important table in the quarterly report — the operator sees their entire portfolio at a glance.

### Section 3: Estate Dimension Heatmap
**Mandatory** | Visual summary

A matrix showing every venue vs every dimension, with performance bands:

- Which dimensions are strong estate-wide?
- Which dimensions are weak estate-wide?
- Where are the outliers (one venue dragging down an otherwise strong dimension)?
- Estate average per dimension vs UK category average

This surfaces systemic issues (e.g. "Conversion is weak across 7 of 9 venues — this is an estate-level problem, not a venue problem").

### Section 4: Local Competitive Landscape
**Mandatory** | Full peer rankings

Full ranked table of ALL scored restaurants in the local peer set (5mi ring), not just estate venues:

| Rank | Venue | Owner | Overall | Band | Qtr Delta | Key Strength | Key Weakness |
|------|-------|-------|---------|------|-----------|--------------|---------------|

- Estate venues highlighted/flagged in the table
- New entrants this quarter (restaurants that opened or appeared in data)
- Closures this quarter (restaurants that closed or disappeared from data)
- Ownership changes detected (Companies House director changes)
- Competitive density: how crowded is the local market?
- Category breakdown: how many Indian, Italian, Pub, etc. in the peer set

This section answers: "Where do we sit in the local market, and how is that market changing?"

### Section 5: UK Restaurant Market Intelligence
**Mandatory** | Min 10 lines

This is the section that goes **beyond Stratford** and gives the operator a window into what's happening in UK restaurants more broadly. It should feel like reading a curated industry briefing.

#### 5a: Notable UK Openings & Concepts
- New restaurant openings nationally that are generating attention (press coverage, awards shortlists, strong early reviews)
- Focus on the same category/price point as estate venues (e.g. pub dining, wine bars, casual dining)
- What makes them notable: menu innovation, service model, digital presence, design, sustainability
- 3-5 examples per quarter with brief description and what can be learned

#### 5b: UK Dining Trends
- Emerging trends in the UK restaurant market this quarter
- Menu trends (e.g. hyper-local sourcing, tasting menus at casual price points, zero-waste kitchens)
- Service trends (e.g. QR ordering adoption, counter service in fine dining, no-tipping policies)
- Digital trends (e.g. Instagram-first marketing, Google Business Profile optimisation, review response strategies)
- Consumer behaviour shifts (e.g. midweek dining growth, lunch vs dinner ratio changes)

#### 5c: Awards & Recognition Cycle
- Michelin announcements relevant to the quarter
- AA Rosette changes
- Good Food Guide updates
- Regional award winners that estate venues compete with

#### 5d: Lessons for This Estate
- For each notable trend or opening, a specific "what this means for you" interpretation
- Actionable takeaways, not just news reporting
- E.g. "Three of the quarter's most talked-about openings lead with natural wine lists — Vintner Wine Bar is well-positioned to capitalise on this trend but currently doesn't promote its wine selection in its Google Business Profile"

**Data sources for this section:**
- Curated from UK food press (The Guardian food, Observer Food Monthly, Time Out, Eater London)
- Michelin Guide announcements
- Harden's, Good Food Guide
- Google Trends data for restaurant-related searches
- TripAdvisor "Trending" and "Travellers' Choice" lists
- Instagram/social media signals for new openings

**Note:** This section will initially require semi-automated curation (AI-assisted search + editorial selection). Full automation is a future goal. The first implementation should define the data structure and use web search APIs to surface candidates, with the report generator assembling the narrative.

### Section 6: Recommendation Resolution Tracker
**Mandatory** | Min 5 lines

Tracks what happened to every recommendation raised across the quarter:

| Rec ID | Venue | Recommendation | First Raised | Status | Times Raised | Resolution |
|--------|-------|----------------|--------------|--------|--------------|------------|

- **Resolved/Completed** — action was taken, issue improved
- **Ongoing** — still active, carried forward
- **Escalated** — repeated 3+ months without action
- **Stale** — no longer relevant (market changed, venue closed, etc.)
- **Dropped** — deliberately deprioritised with reasoning

Summary statistics:
- Total recommendations raised this quarter
- Resolution rate (% resolved within the quarter)
- Average time-to-resolution
- Most common recommendation type (FIX vs BUILD vs PROTECT)
- Venues with highest/lowest follow-through

### Section 7: Dimension Deep-Dive
**Mandatory** | Rotates each quarter

Each quarter, spotlight ONE dimension for cross-estate analysis:

- Q1: Experience | Q2: Visibility | Q3: Trust | Q4: Conversion
- (Prestige covered annually)

The deep-dive includes:
- Estate-wide performance in this dimension vs UK category average
- Best-in-estate: what they're doing right
- Worst-in-estate: what's dragging them down
- Peer comparison: how local competitors score on this dimension
- External benchmarks: what "excellent" looks like nationally for this dimension
- Specific improvement playbook for underperforming venues

### Section 8: Data Quality & Confidence Progress
**Mandatory** | Min 5 lines

Tracks how the intelligence base is improving over time:

| Venue | Q Start Tier | Q End Tier | Reviews Analysed | Sources Active | Next Unlock |
|-------|--------------|------------|------------------|----------------|-------------|

- Confidence tier movement: Anecdotal -> Indicative -> Directional -> Established
- Data sources activated this quarter (e.g. "TripAdvisor ingestion completed for 6 venues")
- Remaining gaps and plan to close them
- Impact: "Adding TripAdvisor data moved Vintner's confidence from Anecdotal to Indicative and changed its overall score by +0.3"

### Section 9: Quarter-over-Quarter Trend Narrative
**Mandatory** | Min 8 lines

Written strategic analysis — NOT just arrows in a table. This is the section where the analyst voice comes through:

- What moved this quarter and why?
- Are the monthly recommendations actually driving improvement?
- Any systemic patterns across multiple venues?
- External factors affecting scores (e.g. seasonal tourism, local events, construction)
- Were any score movements misleading (e.g. score improved but only because a data source was added, not because the venue got better)?

This section must be honest about what the data can and cannot tell us at current confidence levels.

### Section 10: Competitive Landscape Shift
**Mandatory** | Min 5 lines

How the local competitive environment changed this quarter:

- New restaurant openings within the peer rings (5mi, 15mi)
- Restaurant closures
- Ownership/management changes (detected via Companies House)
- Significant refurbishments or concept changes
- New competitors entering estate venues' categories
- Google rating shifts among key competitors (e.g. "The Fox & Hound dropped from 4.5 to 4.1 this quarter")

### Section 11: Strategic Outlook — Next Quarter Priorities
**Mandatory** | Min 5 lines

Estate-level strategic priorities for the coming quarter:

- Top 3 estate-wide priorities (not venue-specific)
- Data collection goals (which sources to activate next)
- Seasonal factors to prepare for
- Competitive threats to monitor
- Investment recommendations (where to focus time/money across the estate)

### Section 12: Appendix — Full Score History
**Optional** | Reference data

- Month-by-month score tables for every venue
- Full recommendation history log
- Data source inventory with collection dates
- Methodology version used for each month's scoring

---

## Generation Rules

### Prerequisites
- Minimum **3 monthly reports** must exist before generating a quarterly report
- If fewer than 3 months available, generate a "Quarterly Baseline" report with Sections 1, 2, 4, 5, 8, 11 only

### Quality Rules
- All anti-generic phrase rules from the monthly report_spec apply
- UK Market Intelligence section must contain specific venue/restaurant names — no vague "some restaurants are innovating" language
- Competitive landscape must name specific competitors, not abstract descriptions
- Trend narrative must reference specific score movements with evidence
- Do not fabricate UK restaurant intelligence — use verifiable sources

### Confidence Rules
- If a venue has been at Anecdotal confidence tier for the entire quarter, flag it explicitly
- Do not claim trajectory for venues with fewer than 2 monthly data points
- UK Market Intelligence confidence: state whether sources are curated (editorial) or automated (API-sourced)

### UK Intelligence Data Pipeline (future)

Phase 1 (manual/semi-automated):
- Perplexity/web search for notable UK openings in relevant categories
- Michelin Guide API or scrape for award changes
- Google Places API for new listings in target categories nationally
- Curated by report author with AI assistance

Phase 2 (automated):
- Scheduled scraping of UK food press RSS feeds
- Google Alerts integration for category-relevant openings
- TripAdvisor "New Restaurants" monitoring
- Automated trend extraction from review corpus

---

## Implementation Notes for Claude Code

1. Add `QUARTERLY_SECTIONS` to `report_spec.py` mirroring the `MONTHLY_SECTIONS` pattern
2. Expand `generate_quarterly_report()` in `report_generator.py` to assemble all 12 sections
3. Create new builders in `operator_intelligence/builders/` for quarterly-specific sections
4. The UK Market Intelligence section (Section 5) will need a new data collection module — start with a stub that defines the data structure and accepts manual input, then automate later
5. The Estate Performance Table (Section 2) needs access to all venue scorecards, not just one — the quarterly generator must accept a list of venue data
6. Output to `outputs/quarterly/{estate_name}_{quarter}.md`
7. Generate a QA artifact for quarterly reports similar to monthly QA

---

*This specification should be read alongside `operator_intelligence/report_spec.py` (monthly sections) and `UK-Restaurant-Tracker-Methodology-Spec-V3.md` (scoring methodology).*
