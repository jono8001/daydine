#!/usr/bin/env python3
"""
calibrate_v4_customer.py — Calibration harness for V4 Customer Validation.

Runs V4 scoring over the Stratford dataset under multiple Customer Validation
configurations (priors, n_caps, optional gamma mapping 0-5 -> 0-10) and
reports distribution diagnostics for each. Pure sweep — writes a single
JSON summary and prints a human-readable table.

Does NOT modify rcs_scoring_v4.py. The chosen setting is applied separately.
"""
from __future__ import annotations

import json
import statistics
from dataclasses import replace

import rcs_scoring_v4 as v4


STRATFORD = "stratford_establishments.json"
EDITORIAL = "stratford_editorial.json"
MENUS = "stratford_menus.json"


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _shrink(rating, count, prior):
    return (count * rating + prior.pseudo * prior.mean) / (count + prior.pseudo)


def _score_batch_with(priors, gamma, records, editorial, menus):
    """Score the batch using a given (priors, gamma) Customer Validation
    config. The engine itself is patched transiently on the gamma mapping;
    the original function is restored before returning.
    """
    orig_fn = v4.score_customer_validation

    def patched(record, priors_arg):
        evidence = []
        total_reviews = 0
        for platform, prior in priors_arg.items():
            pair = v4._extract_platform(record, platform)
            if pair is None:
                continue
            raw, count = pair
            shrunk = _shrink(raw, count, prior)
            shrunk_norm = v4._clamp(shrunk / 5.0)
            if gamma != 1.0:
                shrunk_norm = shrunk_norm ** gamma
            w = min(count, prior.n_cap) / prior.n_cap
            w = max(w, v4.W_FLOOR)
            evidence.append(v4.PlatformEvidence(
                platform=platform, raw=raw, count=count,
                shrunk=shrunk, shrunk_norm=shrunk_norm, weight=w,
            ))
            total_reviews += count
        if not evidence:
            return v4.CustomerResult(score=None, available=False)
        num = sum(e.weight * e.shrunk_norm for e in evidence)
        denom = sum(e.weight for e in evidence)
        cv_01 = num / denom if denom > 0 else 0.0
        return v4.CustomerResult(
            score=10.0 * cv_01, available=True, platforms=evidence,
            total_reviews=total_reviews, platforms_count=len(evidence),
        )

    v4.score_customer_validation = patched
    try:
        scores = v4.score_batch(
            records, editorial=editorial, menus=menus,
            platform_priors=priors,
        )
    finally:
        v4.score_customer_validation = orig_fn
    return scores


def _summary(scores, label):
    finals = []
    rankable_finals = []
    cv_scores = []
    classes = {"Rankable-A": 0, "Rankable-B": 0, "Directional-C": 0,
               "Profile-only-D": 0}
    ge_8 = 0
    for s in scores.values():
        d = s.to_dict()
        finals.append(d["rcs_v4_final"])
        cv = (d["components"]["customer_validation"] or {}).get("score")
        if cv is not None:
            cv_scores.append(cv)
        cls = d["confidence_class"]
        classes[cls] = classes.get(cls, 0) + 1
        if d["rankable"]:
            rankable_finals.append(d["rcs_v4_final"])
            if d["rcs_v4_final"] is not None and d["rcs_v4_final"] >= 8.0:
                ge_8 += 1

    def _stats(xs):
        xs = [x for x in xs if x is not None]
        if not xs:
            return {"n": 0}
        return {
            "n": len(xs),
            "mean": round(statistics.mean(xs), 3),
            "median": round(statistics.median(xs), 3),
            "stdev": round(statistics.pstdev(xs), 3) if len(xs) > 1 else 0,
            "min": round(min(xs), 3),
            "max": round(max(xs), 3),
            "p25": round(sorted(xs)[len(xs) // 4], 3),
            "p75": round(sorted(xs)[(3 * len(xs)) // 4], 3),
        }

    return {
        "label": label,
        "final_all": _stats(finals),
        "final_rankable": _stats(rankable_finals),
        "customer_component": _stats(cv_scores),
        "class_distribution": classes,
        "rankable_ge_8": ge_8,
        "rankable_ge_8_pct": round(100 * ge_8 / max(1, len(rankable_finals)), 1),
    }


def _top_deltas(baseline_scores, variant_scores, k=10):
    """Top movements for a variant vs baseline."""
    rows = []
    for fid, b in baseline_scores.items():
        v = variant_scores.get(fid)
        if v is None:
            continue
        bd, vd = b.to_dict(), v.to_dict()
        if bd["rcs_v4_final"] is None or vd["rcs_v4_final"] is None:
            continue
        delta = round(vd["rcs_v4_final"] - bd["rcs_v4_final"], 3)
        cv = (vd["components"]["customer_validation"] or {}).get("score")
        reviews = sum((p or {}).get("count", 0) for p in (
            vd["components"]["customer_validation"]["platforms"] or {}).values())
        rows.append({
            "fhrsid": fid,
            "name": vd["name"],
            "baseline": bd["rcs_v4_final"],
            "variant": vd["rcs_v4_final"],
            "delta": delta,
            "customer_v4": cv,
            "reviews": reviews,
        })
    rows.sort(key=lambda r: -abs(r["delta"]))
    return rows[:k]


def _thin_evidence_high(scores, threshold=8.0, review_max=30):
    """Venues that still score >= threshold with < review_max combined reviews
    and are rankable. If this count stays high across variants, the spread
    is not doing its job."""
    out = []
    for s in scores.values():
        d = s.to_dict()
        if not d["rankable"]:
            continue
        if d["rcs_v4_final"] is None or d["rcs_v4_final"] < threshold:
            continue
        reviews = sum((p or {}).get("count", 0) for p in (
            d["components"]["customer_validation"]["platforms"] or {}).values())
        if reviews < review_max:
            out.append({
                "name": d["name"], "reviews": reviews,
                "final": d["rcs_v4_final"],
                "customer": (d["components"]["customer_validation"] or {}).get("score"),
            })
    out.sort(key=lambda x: -x["final"])
    return out


def main():
    records = _load(STRATFORD)
    editorial = _load(EDITORIAL)
    menus = _load(MENUS)

    baseline_priors = {
        "google":      v4.PlatformPrior(mean=3.8, pseudo=30, n_cap=200),
        "tripadvisor": v4.PlatformPrior(mean=3.6, pseudo=25, n_cap=150),
        "opentable":   v4.PlatformPrior(mean=4.0, pseudo=20, n_cap=100),
    }

    # Variants
    variants = []

    def add(label, g_mean, g_pseudo, g_ncap, gamma=1.0):
        priors = dict(baseline_priors)
        priors["google"] = v4.PlatformPrior(mean=g_mean, pseudo=g_pseudo, n_cap=g_ncap)
        variants.append((label, priors, gamma))

    # Baseline (reference)
    add("V0_baseline",             3.8, 30, 200, gamma=1.0)

    # Prior sweeps
    add("V1_prior_3.6",            3.6, 30, 200, gamma=1.0)
    add("V2_prior_3.5",            3.5, 30, 200, gamma=1.0)

    # n_cap sweeps
    add("V3_ncap_250",             3.8, 30, 250, gamma=1.0)
    add("V4_ncap_300",             3.8, 30, 300, gamma=1.0)

    # Mapping sweeps (gamma > 1 = less generous at top)
    add("V5_gamma_1.25",           3.8, 30, 200, gamma=1.25)
    add("V6_gamma_1.5",            3.8, 30, 200, gamma=1.5)

    # Combined mild adjustments
    add("V7_mild_combo_3.6_250_g1.2",  3.6, 30, 250, gamma=1.2)

    # Combined stronger adjustments
    add("V8_strong_combo_3.5_300_g1.3", 3.5, 30, 300, gamma=1.3)

    # Stronger low-volume shrinkage
    add("V9_pseudo_60",            3.6, 60, 300, gamma=1.0)

    # Full recommendation candidate (prior down, ncap up, slight gamma, pseudo up)
    add("V10_rec_candidate",       3.6, 45, 300, gamma=1.2)

    baseline_scores = _score_batch_with(baseline_priors, 1.0,
                                         records, editorial, menus)

    out = {"baseline": _summary(baseline_scores, "V0_baseline"),
           "variants": []}

    for label, priors, gamma in variants:
        scores = _score_batch_with(priors, gamma, records, editorial, menus)
        summary = _summary(scores, label)
        summary["google_prior"] = priors["google"].mean
        summary["google_pseudo"] = priors["google"].pseudo
        summary["google_ncap"] = priors["google"].n_cap
        summary["gamma"] = gamma
        summary["top_deltas"] = _top_deltas(baseline_scores, scores, k=10)
        summary["thin_evidence_high"] = _thin_evidence_high(scores)[:10]
        out["variants"].append(summary)

    with open("stratford_v4_calibration.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    # Console table
    print(f"{'label':<34} {'mean':>7} {'med':>7} {'sd':>6} "
          f"{'R>=8%':>7} {'A':>3} {'B':>4} {'C':>3} {'D':>3} "
          f"{'thin>=8':>8}")
    print("-" * 90)
    for s in out["variants"]:
        fr = s["final_rankable"]
        cd = s["class_distribution"]
        thin = len(s["thin_evidence_high"])
        print(f"{s['label']:<34} "
              f"{fr.get('mean',0):>7} {fr.get('median',0):>7} {fr.get('stdev',0):>6} "
              f"{s['rankable_ge_8_pct']:>6}% {cd['Rankable-A']:>3} "
              f"{cd['Rankable-B']:>4} {cd['Directional-C']:>3} "
              f"{cd['Profile-only-D']:>3} {thin:>8}")


if __name__ == "__main__":
    main()
