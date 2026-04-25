# DayDine RCS v3.4.1 — Tie-breaks and public visibility

This methodology patch updates the public and operator visibility model.

## Deterministic tie-breaks

When two venues share the same rounded DayDine Restaurant Confidence Score, rank order is resolved in this order:

1. higher review volume;
2. higher recent-90-day weighted sentiment, where available;
3. higher category-normalised score, where available;
4. earliest first-indexed date, where available;
5. alphabetical venue name as the final fallback.

Reports and ranking JSON surface this as:

> Joint score / rank resolved by tie-break rules: [deciding rule].

If a data field is not yet available, the system skips to the next available deterministic rule. This makes rank order stable and reproducible without pretending unavailable fields were used.

## Public visibility model

Public guides now expose:

- top 30 overall; and
- category lists up to 30 venues per category.

Operator tracking snapshots use the same thresholds:

- Public visibility: Public top 30 overall;
- Category visibility: Category top 30;
- gap to public top 30; and
- gap to category top 30.

## Version

This patch is recorded as **DayDine RCS v3.4.1 — V4 official-source mode with deterministic tie-breaks**.
