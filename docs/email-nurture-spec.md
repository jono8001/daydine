# Email Nurture Sequence — Specification

**Audience:** Restaurant operators in Stratford-upon-Avon who submitted their email via the free gap analysis form on the Reports page.

**Sequence length:** 2 emails only. A third email is intentionally omitted — third emails in B2B nurture sequences push spam complaint rates above the Gmail/Yahoo 0.1% threshold.

---

## Email 1 — Free Confidence Score Snapshot

**Trigger:** On signup (day 0)
**Subject:** Your restaurant's confidence score in Stratford-upon-Avon
**From:** DayDine <hello@daydine.com>

### Body

> Hi {first_name},
>
> Here's your free confidence score snapshot for **{venue_name}** in Stratford-upon-Avon.
>
> **Your estimated position: {rank_low}–{rank_high} out of 190 ranked restaurants.**
>
> This places you in the **{band_name}** band of the Restaurant Confidence Score — a 0–10 metric built from 40 public market signals.
>
> We noticed one thing worth flagging: **your {weakest_signal_name} signal appears to be the primary drag on your score** — but the specific competitor exploiting this gap is only visible in the full report.
>
> This snapshot reflects this week's signals. Competitor positions will have shifted before next week.
>
> **Want the full picture?**
> Your Position & Competitor Report shows your exact rank, your top 5 competitors, and a prioritised action list — delivered as a clear PDF within 48 hours.
>
> [Get My Report — £49 →]({reports_url})
>
> Best,
> The DayDine team

### Implementation notes

- **Deliver a range, not an exact number.** The range (e.g. 125–150) avoids giving away the paid product while still being useful. Calculate as: actual rank ± 12, clamped to 1–190.
- **Name one specific gap without resolving it.** Use the lowest-scoring tier from the venue's RCS breakdown (e.g. "Deliveroo signal", "Google review recency", "opening hours completeness"). Do not reveal the tier score or the competitor who benefits.
- **Soft expiry.** The line "Competitor positions will have shifted before next week" creates urgency without a hard deadline or false scarcity.

---

## Email 2 — Weekly Movement Summary

**Trigger:** Day 7 after signup
**Subject:** Your Stratford competitor signals shifted this week — here's what changed

### Body

> Hi {first_name},
>
> Scores shifted this week in Stratford-upon-Avon. Here's what we saw:
>
> - **{movement_count} venues** changed position in the latest ranking cycle.
> - The biggest mover in your category gained **{biggest_gain} positions** — driven by {gain_signal}.
> - Your estimated band ({band_name}) held steady, but the gap to the venue above you {gap_direction}.
>
> The full breakdown — including exactly who moved, why, and what you can do about it — is in the Position & Competitor Report.
>
> [See the full breakdown — £49 one-time →]({reports_url})
> [Or monitor monthly for £39/month →]({reports_url}#pricing)
>
> Best,
> The DayDine team

### Implementation notes

- **3-sentence movement summary.** Keep it factual and specific. Use real data from the weekly scoring cycle if available; otherwise use category-level aggregates.
- **Dual CTA.** Always present both pricing options. The one-time report is the primary CTA; the subscription is secondary.
- **No further emails.** This is the final automated email. Any further contact should be triggered by user action (e.g. visiting the site again, clicking a link).

---

## Technical Requirements

| Field | Source |
|---|---|
| `{venue_name}` | From signup form or matched via email domain |
| `{rank_low}`, `{rank_high}` | From RCS scoring data: actual rank ± 12, clamped 1–190 |
| `{band_name}` | From RCS band assignment (Excellent / Good / Generally Satisfactory / etc.) |
| `{weakest_signal_name}` | Lowest-scoring active tier from venue's RCS breakdown |
| `{movement_count}` | Count of venues that changed rank in latest weekly cycle |
| `{biggest_gain}` | Largest upward rank movement in the venue's category |
| `{gain_signal}` | Primary signal driving the biggest mover's gain |
| `{gap_direction}` | "narrowed" or "widened" based on score delta to rank above |
| `{reports_url}` | `https://daydine.vercel.app/reports` |

## Sending Infrastructure

- **ESP:** TBD (Resend, Postmark, or AWS SES recommended for transactional + low-volume nurture)
- **Unsubscribe:** One-click unsubscribe header required (RFC 8058). Link in footer.
- **SPF/DKIM/DMARC:** Must be configured for daydine.com before sending
- **Complaint rate target:** < 0.08% (well below Gmail 0.1% threshold)
