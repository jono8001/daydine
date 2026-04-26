"""Revenue Opportunity & Rank-Band Analysis for DayDine operator reports.

This module is intentionally conservative. It estimates association between
DayDine rank bands and commercial scale; it does not claim causal uplift from
one rank position.

Design:
- Stratford and Leamington can be pooled for model strength.
- Outputs always keep each local market separate.
- Companies House turnover is treated as observed only when explicitly present.
- When turnover is unavailable, the model falls back to financial-scale proxy
  and then public-demand proxy.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import median
from typing import Any


RANK_BANDS = [
    (1, 10, "Top 10"),
    (11, 30, "Top 11-30"),
    (31, 60, "Rank 31-60"),
    (61, 120, "Rank 61-120"),
    (121, 10_000, "Rank 121+")
]


@dataclass
class VenueRevenuePoint:
    venue: str
    market: str
    category: str
    rank: int
    rcs: float
    review_count: int | None = None
    google_rating: float | None = None
    company_number: str | None = None
    turnover: float | None = None
    net_assets: float | None = None
    cash: float | None = None
    creditors_due_within_one_year: float | None = None
    employees: int | None = None
    company_age_years: float | None = None

    @property
    def rank_band(self) -> str:
        for low, high, label in RANK_BANDS:
            if low <= self.rank <= high:
                return label
        return "Unbanded"

    @property
    def evidence_tier(self) -> str:
        if self.turnover is not None and self.turnover > 0:
            return "observed_turnover"
        if any(x is not None for x in [self.net_assets, self.cash, self.creditors_due_within_one_year, self.employees]):
            return "financial_proxy"
        return "public_demand_proxy"

    @property
    def scale_proxy(self) -> float:
        """Financial/public scale proxy used when turnover is not disclosed."""
        if self.turnover is not None and self.turnover > 0:
            return float(self.turnover)

        financial_parts = []
        for value, weight in [
            (self.net_assets, 0.35),
            (self.cash, 0.20),
            (self.creditors_due_within_one_year, 0.25),
            (self.employees, 0.20),
        ]:
            if value is not None:
                financial_parts.append(weight * math.log1p(max(float(value), 0)))

        if financial_parts:
            return math.exp(sum(financial_parts) / max(sum([0.35, 0.20, 0.25, 0.20][:len(financial_parts)]), 0.01)) - 1

        review_count = max(float(self.review_count or 0), 0)
        rating = float(self.google_rating or 4.0)
        rcs = float(self.rcs or 0)
        return math.exp(0.65 * math.log1p(review_count) + 0.22 * rating + 0.13 * rcs)


def robust_band_summary(points: list[VenueRevenuePoint], market: str | None = None) -> list[dict[str, Any]]:
    rows = [p for p in points if market is None or p.market == market]
    out = []
    for low, high, label in RANK_BANDS:
        band = [p for p in rows if low <= p.rank <= high]
        if not band:
            continue
        proxies = sorted(p.scale_proxy for p in band if p.scale_proxy > 0)
        turnovers = sorted(p.turnover for p in band if p.turnover is not None and p.turnover > 0)
        out.append({
            "rank_band": label,
            "n": len(band),
            "observed_turnover_n": len(turnovers),
            "evidence_mix": {
                "observed_turnover": sum(p.evidence_tier == "observed_turnover" for p in band),
                "financial_proxy": sum(p.evidence_tier == "financial_proxy" for p in band),
                "public_demand_proxy": sum(p.evidence_tier == "public_demand_proxy" for p in band),
            },
            "median_observed_turnover": median(turnovers) if turnovers else None,
            "median_scale_proxy": median(proxies) if proxies else None,
        })
    return out


def opportunity_between_bands(points: list[VenueRevenuePoint], current_rank: int, target_rank: int, market: str | None = None) -> dict[str, Any]:
    summary = robust_band_summary(points, market=market)
    by_band = {row["rank_band"]: row for row in summary}

    def band_for_rank(rank: int) -> str:
        for low, high, label in RANK_BANDS:
            if low <= rank <= high:
                return label
        return "Unbanded"

    current_band = band_for_rank(current_rank)
    target_band = band_for_rank(target_rank)
    cur = by_band.get(current_band)
    tar = by_band.get(target_band)
    if not cur or not tar:
        return {
            "current_band": current_band,
            "target_band": target_band,
            "status": "insufficient_band_data",
            "message": "Insufficient comparable data to estimate the rank-band association."
        }

    cur_value = cur.get("median_observed_turnover") or cur.get("median_scale_proxy")
    tar_value = tar.get("median_observed_turnover") or tar.get("median_scale_proxy")
    if cur_value is None or tar_value is None:
        return {
            "current_band": current_band,
            "target_band": target_band,
            "status": "insufficient_financial_data",
            "message": "Insufficient financial/proxy data to estimate the opportunity."
        }

    diff = max(0, float(tar_value) - float(cur_value))
    confidence = "Low"
    if tar.get("observed_turnover_n", 0) >= 8 and cur.get("observed_turnover_n", 0) >= 8:
        confidence = "Moderate"
    if tar.get("observed_turnover_n", 0) >= 20 and cur.get("observed_turnover_n", 0) >= 20:
        confidence = "High"

    return {
        "current_band": current_band,
        "target_band": target_band,
        "current_band_value": cur_value,
        "target_band_value": tar_value,
        "associated_difference": diff,
        "confidence": confidence,
        "status": "modelled_association",
        "message": "Association only: higher rank-band position is associated with higher commercial scale; this is not a guaranteed causal uplift."
    }


def render_revenue_opportunity_section(points: list[VenueRevenuePoint], venue: VenueRevenuePoint, target_rank: int = 30) -> str:
    local_summary = robust_band_summary(points, market=venue.market)
    pooled_summary = robust_band_summary(points, market=None)
    opp = opportunity_between_bands(points, current_rank=venue.rank, target_rank=target_rank, market=venue.market)

    def money(v: Any) -> str:
        if v is None:
            return "—"
        try:
            return f"£{float(v):,.0f}"
        except Exception:
            return "—"

    lines: list[str] = []
    out = lines.append
    out("## Revenue Opportunity & Rank-Band Analysis")
    out("")
    out("This section estimates the association between DayDine rank bands and commercial scale. It is not a guarantee that moving up one rank causes a fixed turnover uplift.")
    out("")
    out(f"**Venue market:** {venue.market}")
    out(f"**Current rank band:** {venue.rank_band}")
    out(f"**Evidence tier for this venue:** {venue.evidence_tier.replace('_', ' ')}")
    out("")
    out("### Local market rank-band summary")
    out("")
    out("| Rank band | Venues | Observed turnover records | Median observed turnover | Median scale proxy | Evidence mix |")
    out("|---|---:|---:|---:|---:|---|")
    for row in local_summary:
        mix = row["evidence_mix"]
        out(f"| {row['rank_band']} | {row['n']} | {row['observed_turnover_n']} | {money(row['median_observed_turnover'])} | {money(row['median_scale_proxy'])} | observed {mix['observed_turnover']}, proxy {mix['financial_proxy']}, demand {mix['public_demand_proxy']} |")
    out("")
    out("### Combined model context")
    out("")
    out("Stratford and Leamington can be pooled to improve sample size, but reports keep each market separate. The pooled model is used only as context where the local sample is thin.")
    out("")
    out("| Rank band | Venues | Observed turnover records | Median observed turnover | Median scale proxy |")
    out("|---|---:|---:|---:|---:|")
    for row in pooled_summary:
        out(f"| {row['rank_band']} | {row['n']} | {row['observed_turnover_n']} | {money(row['median_observed_turnover'])} | {money(row['median_scale_proxy'])} |")
    out("")
    out("### Opportunity interpretation")
    out("")
    if opp["status"] == "modelled_association":
        out(f"Moving from **{opp['current_band']}** toward **{opp['target_band']}** is associated with a commercial-scale difference of approximately **{money(opp['associated_difference'])}** in the current local data model.")
        out(f"**Confidence:** {opp['confidence']}.")
    else:
        out(opp["message"])
    out("")
    out("> Caution: this is a rank-band association, not a causal claim. It should be presented as an opportunity range and commercial benchmark, not as a guaranteed turnover uplift.")
    out("")
    return "\n".join(lines)
