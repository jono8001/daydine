# Lambs — Revenue Opportunity & Rank-Band Analysis

*Example section · 2026-04 · DayDine RCS v3.4.1*

---

## Important statistical caveat

This report does **not** claim that moving up one DayDine rank causes a guaranteed turnover increase.

The correct claim is:

> Higher DayDine rank bands may be associated with stronger commercial scale among comparable venues. Where public financial data is available, DayDine can estimate the typical difference between rank bands. Where turnover is not disclosed, the report must fall back to a financial-scale proxy or public-demand proxy.

This is a **correlation / association model**, not a causal proof.

---

## Current venue position

| Metric | Current result |
|---|---:|
| Venue | Lambs |
| Market | Stratford-upon-Avon |
| Category | Restaurant |
| Overall DayDine position | #9 of 169 |
| Restaurant category position | #3 of 56 |
| Public visibility | Public top 30 overall · Category top 30 |
| Current rank band | Top 10 |
| Revenue opportunity status | Already inside strongest public visibility band |

---

## Companies House / financial data status

| Data item | Status | Use in model |
|---|---|---|
| Companies House company match | Not confirmed in this example output | Required before using company accounts |
| Declared turnover | Not available in this example output | Best evidence if present |
| Balance sheet / net assets | Not available in this example output | Financial-scale proxy if turnover absent |
| Employees | Not available in this example output | Scale proxy if disclosed |
| Public demand signals | Available | Used only as a lower-confidence proxy |

**Current evidence tier:** Public-demand proxy only.

That means the report can discuss rank-band opportunity, but should not yet present a precise turnover uplift figure for Lambs.

---

## Recommended rank-band model

Rather than saying “one rank equals £X”, DayDine should estimate opportunity by **rank band**:

| Rank band | Commercial interpretation |
|---|---|
| Top 10 | Strongest local visibility band |
| 11–30 | Publicly visible band |
| 31–60 | Near-public threshold / watch band |
| 61–120 | Lower visibility band |
| 121+ | Low visibility band |

This is statistically more defensible than a per-rank estimate because the difference between #1 and #2 may be tiny, while the difference between #28 and #80 may be commercially meaningful.

---

## Model design

The future Companies House-enabled model should estimate:

```text
log(turnover or scale proxy)
  = rank-band effect
  + category effect
  + review-volume effect
  + rating / RCS effect
  + company age effect
  + chain / multi-site adjustment
  + market fixed effect
```

For more statistical power, Stratford and Leamington Spa can be pooled into a combined model, but the output must always keep the markets separate.

**Correct wording:**

> The combined Stratford + Leamington model is used to improve sample size. Lambs is still reported only against the Stratford-upon-Avon market.

---

## Lambs opportunity interpretation

Lambs is already in the **Top 10** band, so the revenue-opportunity message is not “move into public visibility”. It is:

1. protect current top-band visibility;
2. avoid falling out of the top 10 / top 30;
3. strengthen financial confidence by improving Companies House matching and operator-supplied data;
4. improve booking/contact visibility to reduce lost demand;
5. maintain review volume because review count now contributes to deterministic tie-breaks.

---

## Example operator-facing wording

> Lambs is already inside the strongest DayDine visibility band. The commercial value is therefore defensive: protect current visibility, reduce booking/contact friction, and monitor nearby competitors with the same rounded RCS.
>
> Once a Companies House entity match and usable accounts data are available, DayDine can compare Lambs with the median commercial scale of venues in the Top 10, 11–30 and 31–60 bands. Until then, any revenue figure should be treated as a low-confidence opportunity estimate rather than declared turnover.

---

## What the next production version should add

| Build item | Purpose |
|---|---|
| Companies House entity matching | Identify the correct legal company behind each venue |
| Accounts parser | Extract turnover where disclosed, otherwise balance-sheet proxies |
| Chain / multi-site detector | Avoid attributing group turnover to one local venue |
| Category controls | Compare restaurants with restaurants, cafes with cafes, pubs with pubs |
| Local-market fixed effects | Keep Stratford and Leamington separate in output |
| Confidence label | Observed turnover / financial proxy / public-demand proxy |

---

## Final recommendation

Add this to paid reports as:

**Revenue Opportunity & Rank-Band Analysis**

with three possible states:

1. **Observed turnover available** — strongest; can show real turnover comparisons.
2. **Financial proxy only** — moderate; can show commercial scale but not declared sales.
3. **Public-demand proxy only** — low; useful for directional opportunity, not precise financial claims.

For Lambs today, the report should show **public-demand proxy only** until Companies House matching and accounts extraction are completed.

