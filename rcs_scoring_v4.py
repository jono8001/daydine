#!/usr/bin/env python3
"""
rcs_scoring_v4.py — DayDine V4 Scoring Engine

Implements docs/DayDine-V4-Scoring-Spec.md. V3.4 (rcs_scoring_stratford.py) is
left untouched. This module is a parallel scoring path intended for side-by-side
comparison during cutover (see spec section 11).

Public API:
    score_venue(record, editorial=None, companies_house=None, menu=None,
                entity_match=None, now=None) -> V4Score
    score_batch(records, editorial=None, companies_house=None, menus=None,
                entity_matches=None, now=None) -> dict[id, V4Score]
    V4Score.to_dict() -> dict   # matches spec section 10.1

CLI:
    python rcs_scoring_v4.py --input stratford_establishments.json \\
        --menus stratford_menus.json --editorial stratford_editorial.json \\
        --out-json stratford_rcs_v4_scores.json \\
        --out-csv stratford_rcs_v4_scores.csv

Inputs this module MUST NOT read (enforced at load time, see FORBIDDEN_FIELDS):
    sentiment_*, aspect_*, ai_summary, review_text, g_reviews text content.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional

ENGINE_VERSION = "v4.0.0"

# ---------------------------------------------------------------------------
# Fixed component weights (spec section 2.1). Do not renormalise when a
# component is missing — missing components contribute 0 and feed confidence.
# ---------------------------------------------------------------------------
WEIGHT_TRUST = 0.40
WEIGHT_CUSTOMER = 0.45
WEIGHT_COMMERCIAL = 0.15

# Trust & Compliance sub-weights (spec 3.1)
W_TRUST_R = 0.45
W_TRUST_SH = 0.20
W_TRUST_SS = 0.15
W_TRUST_SM = 0.15
W_TRUST_RECENCY = 0.05

# Commercial Readiness sub-weights (spec 5.1) — equal quarters
W_CR_WEBSITE = 0.25
W_CR_MENU = 0.25
W_CR_HOURS = 0.25
W_CR_BOOKING = 0.25

# Inspection recency decay: e^(-λ * days), λ = 0.0023 (~300d half-life)
TRUST_LAMBDA = 0.0023

# Distinction modifier cap (spec 2.2, 7.1)
DISTINCTION_CAP = 0.30

# Customer Validation mapping calibration (spec 4.2 maps shrunk/5 linearly).
# Gamma > 1 compresses the top of the 0-5 -> 0-10 mapping so that average
# metadata ratings (4.2-4.6) don't all land in the "top tier" band. Chosen
# 2026-04 from the calibration sweep in docs/DayDine-V4-Scoring-Comparison.md.
MAPPING_GAMMA = 1.2

# FHRS string-rating sentinels — component unavailable
FSA_UNSCORED_RATINGS = {"AwaitingInspection", "Exempt", "Pass"}

# Fields the V4 engine is forbidden from reading (spec section 9).
# Any attempt to read these from a record must be refused. This is a belt-and-
# braces check; the CI lint should also grep for these identifiers in the
# scoring module itself.
FORBIDDEN_FIELDS = frozenset({
    # review text / sentiment
    "review_text",
    "ai_summary",
    "ai_summaries",
    # aspect sentiment sub-signals removed from V4
    "aspect_food", "aspect_service", "aspect_ambience",
    "aspect_value", "aspect_cleanliness",
    "aspect_sentiment",
    # V3.4 sentiment outputs
    "sentiment", "sentiment_score", "sentiment_red_flags",
    "sentiment_positives", "sentiment_aspects",
})


# ---------------------------------------------------------------------------
# Platform priors (spec 4.2, 4.3). Configurable — callers may pass a custom
# mapping to score_venue() via `platform_priors=...`.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PlatformPrior:
    """Bayesian shrinkage configuration for a single customer-validation
    platform. See spec 4.2 and 4.3."""
    mean: float     # prior rating on the 0-5 scale
    pseudo: float   # pseudo-count k_p
    n_cap: float    # count at which platform is "fully evidenced"


PLATFORM_PRIORS: dict[str, PlatformPrior] = {
    # Google prior lowered 3.8 -> 3.6 and n_cap raised 200 -> 250 as part of
    # the 2026-04 Customer Validation calibration. See
    # docs/DayDine-V4-Scoring-Comparison.md "Calibration decision".
    "google":      PlatformPrior(mean=3.6, pseudo=30, n_cap=250),
    "tripadvisor": PlatformPrior(mean=3.6, pseudo=25, n_cap=150),
    "opentable":   PlatformPrior(mean=4.0, pseudo=20, n_cap=100),
}

# Field mapping — (rating_field, count_field) per platform. Kept separate from
# the priors so the field schema can evolve without disturbing the constants.
PLATFORM_FIELDS: dict[str, tuple[str, str]] = {
    "google":      ("gr",        "grc"),
    "tripadvisor": ("ta",        "trc"),
    "opentable":   ("ot_rating", "ot_count"),
}

# Review-count floors that trip class caps (spec 4.5)
LOW_COUNT_FLOOR = 5
W_FLOOR = 0.05


# ---------------------------------------------------------------------------
# Dataclasses returned by the engine (spec section 10.1)
# ---------------------------------------------------------------------------

@dataclass
class PlatformEvidence:
    """Per-platform shrinkage audit entry."""
    platform: str
    raw: float
    count: int
    shrunk: float          # 0-5 scale after shrinkage
    shrunk_norm: float     # 0-1 scale
    weight: float          # w_p (0.05–1.0)


@dataclass
class TrustResult:
    score: Optional[float]           # 0-10, None if unavailable
    available: bool
    signals_used: int
    recency: Optional[float]
    stale_soft_cap_applied: bool = False
    stale_hard_cap_applied: bool = False
    stale_multiplier_applied: bool = False


@dataclass
class CustomerResult:
    score: Optional[float]           # 0-10, None if no platforms
    available: bool
    platforms: list[PlatformEvidence] = field(default_factory=list)
    total_reviews: int = 0
    platforms_count: int = 0


@dataclass
class CommercialResult:
    score: Optional[float]           # 0-10, None if no observability
    available: bool
    signals_used: int
    website: bool = False
    menu_online: bool = False
    hours_completeness: float = 0.0
    booking_or_contact: bool = False


@dataclass
class PenaltyEntry:
    code: str
    effect: str          # human-readable, e.g. "-0.30 absolute", "cap 5.0"
    reason: str


@dataclass
class DistinctionEntry:
    value: float          # pre-cap contribution
    sources: list[str] = field(default_factory=list)


@dataclass
class V4Score:
    fhrsid: Optional[str]
    name: Optional[str]
    trust: TrustResult
    customer: CustomerResult
    commercial: CommercialResult
    distinction: DistinctionEntry
    penalties_applied: list[PenaltyEntry]
    caps_applied: list[PenaltyEntry]
    base_score: float
    adjusted_score: float
    rcs_v4_final: float
    confidence_class: str            # Rankable-A | Rankable-B | Directional-C | Profile-only-D
    rankable: bool
    league_table_eligible: bool
    source_families_present: dict[str, Any]
    entity_match_status: str         # confirmed | probable | ambiguous | none
    audit: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Serialise to the JSON shape in spec 10.1."""
        return {
            "fhrsid": self.fhrsid,
            "name": self.name,
            "components": {
                "trust_compliance": {
                    "score": _round3(self.trust.score),
                    "available": self.trust.available,
                    "signals_used": self.trust.signals_used,
                },
                "customer_validation": {
                    "score": _round3(self.customer.score),
                    "available": self.customer.available,
                    "platforms": {
                        p.platform: {
                            "raw": p.raw, "count": p.count,
                            "shrunk": round(p.shrunk, 4),
                            "weight": round(p.weight, 4),
                        } for p in self.customer.platforms
                    },
                },
                "commercial_readiness": {
                    "score": _round3(self.commercial.score),
                    "available": self.commercial.available,
                    "signals_used": self.commercial.signals_used,
                },
            },
            "modifiers": {
                "distinction": {
                    "value": round(self.distinction.value, 4),
                    "sources": self.distinction.sources,
                },
            },
            "penalties_applied": [asdict(p) for p in self.penalties_applied],
            "caps_applied": [asdict(p) for p in self.caps_applied],
            "base_score": _round3(self.base_score),
            "adjusted_score": _round3(self.adjusted_score),
            "rcs_v4_final": _round3(self.rcs_v4_final),
            "confidence_class": self.confidence_class,
            "rankable": self.rankable,
            "league_table_eligible": self.league_table_eligible,
            "source_family_summary": self.source_families_present,
            "entity_match_status": self.entity_match_status,
            "audit": self.audit,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _round3(x: Optional[float]) -> Optional[float]:
    return None if x is None else round(float(x), 3)


def _safe_float(x: Any) -> Optional[float]:
    if x is None or x == "":
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _safe_int(x: Any) -> Optional[int]:
    f = _safe_float(x)
    return None if f is None else int(f)


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _parse_date(s: Any) -> Optional[datetime]:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def _days_since(s: Any, now: datetime) -> Optional[int]:
    dt = _parse_date(s)
    if dt is None:
        return None
    return max(0, (now - dt).days)


def _guard_forbidden(record: dict[str, Any]) -> None:
    """Refuse to proceed if the input carries any forbidden field (spec 9).
    The engine ignores these fields; raising here catches accidental coupling
    in callers or upstream merges."""
    offenders = [k for k in record.keys() if k in FORBIDDEN_FIELDS]
    if offenders:
        raise ValueError(
            f"V4 engine refuses to read forbidden fields: {offenders}. "
            "Review text / aspect sentiment / AI summaries are report-only "
            "(spec sections 6 and 9)."
        )


# ---------------------------------------------------------------------------
# Component: Trust & Compliance (spec section 3)
# ---------------------------------------------------------------------------

# FHRS data in this repo's Firebase schema stores sh/ss/sm PRE-NORMALISED to
# 0-10 where higher = better (not raw FSA 0-20 inverse). §3.2 of the spec
# assumes raw inverse; the implementation of _fsa_sub_norm() is adapted to the
# repo's actual data format. If raw FSA values (0-20 inverse) ever flow in,
# _fsa_sub_norm() detects them by magnitude and applies the inverse formula.

def _fsa_sub_norm(raw: Optional[float]) -> Optional[float]:
    """Normalise an FSA sub-score to 0-1 (higher = better).

    Accepts both repo-normalised (0-10, higher=better) and raw FSA inverse
    (0-20, lower=better) encodings. Detection by magnitude: values > 10 are
    treated as raw inverse.
    """
    if raw is None:
        return None
    if raw > 10:
        return 1.0 - _clamp(raw / 20.0)
    return _clamp(raw / 10.0)


def _r_norm(r: Any) -> Optional[float]:
    """Map FHRS headline rating to 0-1. Returns None for unscored ratings."""
    if r is None or r == "":
        return None
    if isinstance(r, str) and r in FSA_UNSCORED_RATINGS:
        return None
    i = _safe_int(r)
    if i is None or i < 0 or i > 5:
        return None
    return {0: 0.0, 1: 0.2, 2: 0.4, 3: 0.6, 4: 0.8, 5: 1.0}[i]


def score_trust_compliance(record: dict[str, Any], now: datetime) -> TrustResult:
    r = record.get("r")
    rn = _r_norm(r)
    if rn is None:
        return TrustResult(score=None, available=False, signals_used=0, recency=None)

    sh = _fsa_sub_norm(_safe_float(record.get("sh")))
    ss = _fsa_sub_norm(_safe_float(record.get("ss")))
    sm = _fsa_sub_norm(_safe_float(record.get("sm")))

    days = _days_since(record.get("rd"), now)
    recency = math.exp(-TRUST_LAMBDA * days) if days is not None else 0.0

    # Missing sub-scores contribute 0 to the numerator; their weight still
    # counts in the denominator (spec principle 3: missing != neutral fill).
    parts = [
        (rn,               W_TRUST_R),
        (sh or 0.0,        W_TRUST_SH),
        (ss or 0.0,        W_TRUST_SS),
        (sm or 0.0,        W_TRUST_SM),
        (recency,          W_TRUST_RECENCY),
    ]
    score_01 = sum(v * w for v, w in parts)
    signals_used = 1 + sum(x is not None for x in (sh, ss, sm)) + (1 if days is not None else 0)

    return TrustResult(
        score=10.0 * score_01,
        available=True,
        signals_used=signals_used,
        recency=recency,
    )


def apply_stale_inspection(trust: TrustResult, record: dict[str, Any],
                            now: datetime, caps: list[PenaltyEntry]) -> TrustResult:
    """Spec 7.3 — stale inspections cap the Trust component, not zero it."""
    if not trust.available or trust.score is None:
        return trust
    days = _days_since(record.get("rd"), now)
    if days is None:
        return trust

    r = _safe_int(record.get("r"))
    new_score = trust.score

    if days > 1825:
        new_score = min(new_score, 5.0)
        trust.stale_hard_cap_applied = True
        caps.append(PenaltyEntry("STALE-5Y",
            "TrustCompliance cap 5.0", f"days_since_rd={days}"))
    elif days > 1095:
        new_score = new_score * 0.85
        trust.stale_multiplier_applied = True
        caps.append(PenaltyEntry("STALE-3Y",
            "TrustCompliance x0.85", f"days_since_rd={days}"))
    elif days > 730 and r is not None and r >= 3:
        if new_score > 7.0:
            new_score = 7.0
            trust.stale_soft_cap_applied = True
            caps.append(PenaltyEntry("STALE-2Y",
                "TrustCompliance soft cap 7.0", f"days_since_rd={days}, r={r}"))

    trust.score = new_score
    return trust


# ---------------------------------------------------------------------------
# Component: Customer Validation (spec section 4)
# ---------------------------------------------------------------------------

def _extract_platform(record: dict[str, Any], platform: str
                       ) -> Optional[tuple[float, int]]:
    """Return (rating, count) for a platform, or None if absent/invalid."""
    r_field, c_field = PLATFORM_FIELDS[platform]
    r = _safe_float(record.get(r_field))
    c = _safe_int(record.get(c_field))
    if r is None or c is None or c <= 0:
        return None
    if r < 0 or r > 5:
        return None
    return r, c


def _shrink(rating: float, count: int, prior: PlatformPrior) -> float:
    """Bayesian shrinkage on 0-5 scale (spec 4.2)."""
    return (count * rating + prior.pseudo * prior.mean) / (count + prior.pseudo)


def score_customer_validation(record: dict[str, Any],
                                priors: dict[str, PlatformPrior]
                                ) -> CustomerResult:
    evidence: list[PlatformEvidence] = []
    total_reviews = 0

    for platform, prior in priors.items():
        pair = _extract_platform(record, platform)
        if pair is None:
            continue
        raw, count = pair
        shrunk = _shrink(raw, count, prior)
        shrunk_norm = _clamp(shrunk / 5.0)
        if MAPPING_GAMMA != 1.0:
            shrunk_norm = shrunk_norm ** MAPPING_GAMMA
        w = min(count, prior.n_cap) / prior.n_cap
        w = max(w, W_FLOOR)
        evidence.append(PlatformEvidence(
            platform=platform, raw=raw, count=count,
            shrunk=shrunk, shrunk_norm=shrunk_norm, weight=w,
        ))
        total_reviews += count

    if not evidence:
        return CustomerResult(score=None, available=False)

    num = sum(e.weight * e.shrunk_norm for e in evidence)
    denom = sum(e.weight for e in evidence)
    cv_01 = num / denom if denom > 0 else 0.0
    return CustomerResult(
        score=10.0 * cv_01,
        available=True,
        platforms=evidence,
        total_reviews=total_reviews,
        platforms_count=len(evidence),
    )


# ---------------------------------------------------------------------------
# Component: Commercial Readiness (spec section 5)
# ---------------------------------------------------------------------------

def _hours_completeness(goh: Any) -> Optional[float]:
    """Compute days_with_hours / 7 from a Google opening-hours list.

    Returns None if no hours data observable at all."""
    if goh is None:
        return None
    if isinstance(goh, list):
        if not goh:
            return 0.0
        days = 0
        for line in goh:
            if not isinstance(line, str):
                continue
            # A well-formed line is "<Day>: <hours>". Empty/closed days still
            # count as "populated" — they are known facts, not missing data.
            if ":" in line and line.split(":", 1)[1].strip():
                days += 1
        return days / 7.0
    return None


def score_commercial_readiness(record: dict[str, Any],
                                 menu_entry: Optional[dict[str, Any]]
                                 ) -> CommercialResult:
    # Website: explicit `web` field from web-presence inference
    web_val = record.get("web")
    website = bool(web_val) if web_val not in (None, "", False) else False

    # Menu online: from menus dataset (authoritative) or record itself
    menu_flag = None
    if menu_entry and "has_menu_online" in menu_entry:
        menu_flag = bool(menu_entry.get("has_menu_online"))
    elif "has_menu_online" in record:
        menu_flag = bool(record.get("has_menu_online"))
    menu_online = bool(menu_flag)

    hc = _hours_completeness(record.get("goh"))
    hours_completeness = 0.0 if hc is None else _clamp(hc)

    # Booking / contact: explicit booking URL, reservation widget, or phone.
    # This repo does not currently collect phone or booking-URL data, so in
    # practice this signal is False for most venues. Missing = no credit;
    # it never defaults to True (spec principle 3).
    booking_or_contact = bool(
        record.get("booking_url")
        or record.get("reservation_url")
        or record.get("phone")
        or record.get("tel")
    )

    # Observability check — at least one observable path into this component.
    # If there is zero evidence (no Google record, no menus entry), we report
    # the component as unavailable (spec 5.2).
    observable = any([
        record.get("gpid") is not None,
        record.get("goh") is not None,
        menu_entry is not None,
        web_val is not None,
    ])
    if not observable:
        return CommercialResult(score=None, available=False, signals_used=0)

    score_01 = (
        W_CR_WEBSITE * (1.0 if website else 0.0)
        + W_CR_MENU * (1.0 if menu_online else 0.0)
        + W_CR_HOURS * hours_completeness
        + W_CR_BOOKING * (1.0 if booking_or_contact else 0.0)
    )
    signals_used = sum([
        website, menu_online, hours_completeness > 0.0, booking_or_contact,
    ])

    return CommercialResult(
        score=10.0 * score_01,
        available=True,
        signals_used=signals_used,
        website=website,
        menu_online=menu_online,
        hours_completeness=hours_completeness,
        booking_or_contact=booking_or_contact,
    )


# ---------------------------------------------------------------------------
# Distinction modifier (spec 7.1) — Michelin + AA only, +0.30 cap
# ---------------------------------------------------------------------------

# Michelin values by editorial-scraper convention. `michelin_type` values:
#   "3-star", "2-star", "1-star" (stars)
#   "bib_gourmand", "green_star", "guide" (non-star)
MICHELIN_TABLE: dict[str, tuple[float, str]] = {
    "3-star":       (0.30, "michelin_3_star"),
    "2-star":       (0.25, "michelin_2_star"),
    "1-star":       (0.20, "michelin_1_star"),
    "bib_gourmand": (0.12, "michelin_bib_gourmand"),
    "green_star":   (0.08, "michelin_green_star"),
    "guide":        (0.05, "michelin_guide"),
}

AA_TABLE: dict[int, tuple[float, str]] = {
    5: (0.20, "aa_5_rosette"),
    4: (0.15, "aa_4_rosette"),
    3: (0.10, "aa_3_rosette"),
    2: (0.06, "aa_2_rosette"),
    1: (0.03, "aa_1_rosette"),
}


def compute_distinction(editorial: Optional[dict[str, Any]]) -> DistinctionEntry:
    if not editorial:
        return DistinctionEntry(value=0.0, sources=[])

    value = 0.0
    sources: list[str] = []

    # Michelin — prefer explicit type, else boolean mention = guide listing
    m_type = editorial.get("michelin_type")
    if m_type and m_type in MICHELIN_TABLE:
        v, label = MICHELIN_TABLE[m_type]
        value += v
        sources.append(label)
    elif editorial.get("has_michelin_mention"):
        v, label = MICHELIN_TABLE["guide"]
        value += v
        sources.append(label)

    # AA — rosette count
    aa_rosettes = _safe_int(editorial.get("aa_rosettes"))
    if aa_rosettes and aa_rosettes in AA_TABLE:
        v, label = AA_TABLE[aa_rosettes]
        value += v
        sources.append(label)

    capped = min(value, DISTINCTION_CAP)
    return DistinctionEntry(value=capped, sources=sources)


# ---------------------------------------------------------------------------
# Penalties and caps (spec 7.2, 7.4)
# ---------------------------------------------------------------------------

def apply_companies_house(adjusted: float, ch: Optional[dict[str, Any]],
                           penalties: list[PenaltyEntry],
                           caps: list[PenaltyEntry]) -> tuple[float, bool]:
    """Apply CH risk rules. Returns (new_score, entity_dissolved)."""
    entity_dissolved = False
    if not ch:
        return adjusted, entity_dissolved

    status = str(ch.get("company_status") or "").lower()
    if status == "dissolved":
        adjusted = min(adjusted, 3.0)
        entity_dissolved = True
        caps.append(PenaltyEntry("CH-1", "cap 3.0", "company_status=dissolved"))
    elif status in {"liquidation", "administration"}:
        adjusted = min(adjusted, 5.0)
        caps.append(PenaltyEntry("CH-2", f"cap 5.0", f"company_status={status}"))

    overdue_days = _safe_int(ch.get("accounts_overdue_days"))
    if overdue_days is not None and overdue_days > 90:
        adjusted -= 0.30
        penalties.append(PenaltyEntry("CH-3",
            "-0.30 absolute", f"accounts_overdue_days={overdue_days}"))

    director_churn = _safe_int(ch.get("director_changes_12mo"))
    if director_churn is not None and director_churn >= 3:
        adjusted *= 0.92
        penalties.append(PenaltyEntry("CH-4",
            "x0.92", f"director_changes_12mo={director_churn}"))

    return adjusted, entity_dissolved


def check_closure(record: dict[str, Any]) -> Optional[str]:
    """Return closure status string or None. Spec 7.4."""
    status = str(record.get("business_status") or "").upper()
    if status == "CLOSED_PERMANENTLY":
        return "closed_permanently"
    if status == "CLOSED_TEMPORARILY":
        return "closed_temporarily"
    return None


# ---------------------------------------------------------------------------
# Entity match (spec 7.4, 8.4) — placeholder framework
# ---------------------------------------------------------------------------

def assess_entity_match(record: dict[str, Any]) -> str:
    """Return one of: confirmed | probable | ambiguous | none.

    Placeholder — a proper resolver will eventually compare FSA + Google +
    Companies House + address strings. For now we use presence of identifiers
    and an explicit override field.
    """
    override = record.get("entity_match")
    if isinstance(override, str) and override in {
        "confirmed", "probable", "ambiguous", "none",
    }:
        return override

    has_fhrs = record.get("id") is not None
    has_gpid = bool(record.get("gpid"))

    if record.get("entity_ambiguous"):
        return "ambiguous"
    if has_fhrs and has_gpid:
        return "confirmed"
    if has_fhrs or has_gpid:
        return "probable"
    return "none"


# ---------------------------------------------------------------------------
# Confidence / rankability (spec section 8)
# ---------------------------------------------------------------------------

def _source_families(trust: TrustResult, customer: CustomerResult,
                      commercial: CommercialResult,
                      ch: Optional[dict[str, Any]]) -> dict[str, Any]:
    return {
        "fsa": "present" if trust.available else "absent",
        "customer_platforms": [p.platform for p in customer.platforms],
        "commercial": (
            "absent" if not commercial.available else
            "full" if commercial.signals_used >= 3 else
            "partial"
        ),
        "companies_house": "matched" if ch else "unmatched",
    }


def classify_confidence(trust: TrustResult, customer: CustomerResult,
                         commercial: CommercialResult,
                         entity_match: str,
                         entity_dissolved: bool,
                         closure: Optional[str]) -> str:
    """Assign one of Rankable-A, Rankable-B, Directional-C, Profile-only-D."""
    primary = sum([trust.available, customer.available, commercial.available])
    signals = (
        (trust.signals_used if trust.available else 0)
        + (3 * customer.platforms_count if customer.available else 0)  # each platform worth ~3 signals
        + (commercial.signals_used if commercial.available else 0)
    )
    reviews = customer.total_reviews if customer.available else 0
    single_big = any(p.count >= 30 for p in customer.platforms)

    # Profile-only-D: not even directional gates met
    if primary < 1 or signals < 4 or entity_match == "none":
        return "Profile-only-D"

    # Rankable-A: strong multi-source, confirmed match
    if (primary == 3
        and signals >= 10
        and (reviews >= 50 or single_big)
        and entity_match == "confirmed"
        and not entity_dissolved
        and closure is None):
        # Further gating in §4.4: single-platform caps at B
        if customer.platforms_count >= 2:
            return "Rankable-A"
        return "Rankable-B"

    # Rankable-B: acceptable evidence, includes single-platform case
    if (primary >= 2
        and signals >= 7
        and reviews >= 10
        and entity_match in {"confirmed", "probable"}
        and not entity_dissolved
        and closure != "closed_permanently"):
        return "Rankable-B"

    # Directional-C: at least one family + minimum signals
    if primary >= 1 and signals >= 4:
        return "Directional-C"

    return "Profile-only-D"


def apply_low_review_cap(confidence: str, customer: CustomerResult) -> str:
    """Spec 4.5 — venues with all platforms at N<5 cannot exceed Directional-C."""
    if not customer.available:
        return confidence
    low_all = all(p.count < LOW_COUNT_FLOOR for p in customer.platforms)
    big_other = any(p.count >= 30 for p in customer.platforms)
    if low_all and not big_other:
        # Degrade Rankable-* to Directional-C
        if confidence in {"Rankable-A", "Rankable-B"}:
            return "Directional-C"
    return confidence


def rankable_flags(confidence: str, trust: TrustResult,
                    closure: Optional[str], entity_dissolved: bool,
                    customer: CustomerResult) -> tuple[bool, bool]:
    """Return (rankable, league_table_eligible) per spec 8.3."""
    rankable = confidence in {"Rankable-A", "Rankable-B"}
    if not rankable:
        return False, False
    if closure in {"closed_permanently", "closed_temporarily"}:
        return rankable, False
    if entity_dissolved:
        return rankable, False
    if trust.stale_hard_cap_applied:
        return rankable, False
    if not customer.available or customer.platforms_count == 0:
        return rankable, False
    return True, True


# ---------------------------------------------------------------------------
# Orchestrator (spec section 2)
# ---------------------------------------------------------------------------

def score_venue(
    record: dict[str, Any],
    editorial: Optional[dict[str, Any]] = None,
    companies_house: Optional[dict[str, Any]] = None,
    menu: Optional[dict[str, Any]] = None,
    entity_match: Optional[str] = None,
    now: Optional[datetime] = None,
    platform_priors: Optional[dict[str, PlatformPrior]] = None,
) -> V4Score:
    """Score one venue. All auxiliary data is optional.

    `record` is the primary venue dict (FSA + Google merged). `editorial`,
    `companies_house`, `menu` are per-venue dicts from their respective
    collector outputs. `entity_match` lets the caller override auto-detection.
    """
    _guard_forbidden(record)
    now = now or datetime.now(timezone.utc)
    priors = platform_priors or PLATFORM_PRIORS

    penalties: list[PenaltyEntry] = []
    caps: list[PenaltyEntry] = []

    # Components
    trust = score_trust_compliance(record, now)
    trust = apply_stale_inspection(trust, record, now, caps)
    customer = score_customer_validation(record, priors)
    commercial = score_commercial_readiness(record, menu)

    # base — missing components contribute 0 (spec 2.1, principle 3)
    base = (
        WEIGHT_TRUST * (trust.score or 0.0)
        + WEIGHT_CUSTOMER * (customer.score or 0.0)
        + WEIGHT_COMMERCIAL * (commercial.score or 0.0)
    )

    # Distinction (capped)
    distinction = compute_distinction(editorial)
    adjusted = base + distinction.value

    # Companies House penalties/caps
    adjusted, entity_dissolved = apply_companies_house(
        adjusted, companies_house, penalties, caps)

    # Closure / entity handling
    closure = check_closure(record)
    em_status = entity_match or assess_entity_match(record)

    # Clamp to [0,10]
    adjusted = max(0.0, min(10.0, adjusted))

    # Confidence class
    confidence = classify_confidence(
        trust, customer, commercial,
        em_status, entity_dissolved, closure,
    )
    confidence = apply_low_review_cap(confidence, customer)

    # Single-platform customer validation cap (spec 4.4)
    if customer.available and customer.platforms_count == 1 and confidence == "Rankable-A":
        confidence = "Rankable-B"

    # Rankability / league-table flags
    rankable, league_eligible = rankable_flags(
        confidence, trust, closure, entity_dissolved, customer)

    # Final: Profile-only-D venues get no published headline
    if confidence == "Profile-only-D":
        final = 0.0
    else:
        final = adjusted

    # Source-family summary
    families = _source_families(trust, customer, commercial, companies_house)

    # Audit trace
    trace: list[str] = []
    if trust.available:
        trace.append(
            f"TrustCompliance={trust.score:.3f} "
            f"(r_norm ok, signals_used={trust.signals_used}, "
            f"recency={trust.recency:.3f})"
        )
    else:
        trace.append("TrustCompliance=None (FHRS unavailable)")
    if customer.available:
        plat_str = "; ".join(
            f"{p.platform} n={p.count} raw={p.raw} shrunk={p.shrunk:.2f} w={p.weight:.2f}"
            for p in customer.platforms
        )
        trace.append(f"CustomerValidation={customer.score:.3f} ({plat_str})")
    else:
        trace.append("CustomerValidation=None (no platforms)")
    if commercial.available:
        trace.append(
            f"CommercialReadiness={commercial.score:.3f} "
            f"(web={commercial.website}, menu={commercial.menu_online}, "
            f"hours={commercial.hours_completeness:.2f}, "
            f"booking={commercial.booking_or_contact})"
        )
    else:
        trace.append("CommercialReadiness=None (no observability)")
    trace.append(
        f"base={base:.3f}; distinction+{distinction.value:.3f}; "
        f"adjusted={adjusted:.3f}; final={final:.3f}"
    )
    trace.append(f"class={confidence}; rankable={rankable}; league={league_eligible}")
    if closure:
        trace.append(f"closure={closure}")
    if em_status != "confirmed":
        trace.append(f"entity_match={em_status}")

    audit = {
        "engine_version": ENGINE_VERSION,
        "computed_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "decision_trace": trace,
    }

    fhrsid = record.get("id")
    return V4Score(
        fhrsid=str(fhrsid) if fhrsid is not None else None,
        name=record.get("n"),
        trust=trust,
        customer=customer,
        commercial=commercial,
        distinction=distinction,
        penalties_applied=penalties,
        caps_applied=caps,
        base_score=base,
        adjusted_score=adjusted,
        rcs_v4_final=final,
        confidence_class=confidence,
        rankable=rankable,
        league_table_eligible=league_eligible,
        source_families_present=families,
        entity_match_status=em_status,
        audit=audit,
    )


def score_batch(
    records: dict[str, dict[str, Any]],
    editorial: Optional[dict[str, dict[str, Any]]] = None,
    companies_house: Optional[dict[str, dict[str, Any]]] = None,
    menus: Optional[dict[str, dict[str, Any]]] = None,
    entity_matches: Optional[dict[str, str]] = None,
    now: Optional[datetime] = None,
    platform_priors: Optional[dict[str, PlatformPrior]] = None,
) -> dict[str, V4Score]:
    """Score every record in a batch. Side-inputs are keyed by the same id
    used in `records` (string or int fhrsid)."""
    editorial = editorial or {}
    companies_house = companies_house or {}
    menus = menus or {}
    entity_matches = entity_matches or {}
    results: dict[str, V4Score] = {}
    for key, record in records.items():
        skey = str(key)
        results[skey] = score_venue(
            record,
            editorial=editorial.get(skey) or editorial.get(key),
            companies_house=companies_house.get(skey) or companies_house.get(key),
            menu=menus.get(skey) or menus.get(key),
            entity_match=entity_matches.get(skey),
            now=now,
            platform_priors=platform_priors,
        )
    return results


# ---------------------------------------------------------------------------
# CLI (local testing — does not rewire the production pipeline)
# ---------------------------------------------------------------------------

def _load_json(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json_output(path: str, scores: dict[str, V4Score]) -> None:
    payload = {k: v.to_dict() for k, v in scores.items()}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


CSV_COLUMNS = [
    "fhrsid", "name", "confidence_class", "rankable", "league_table_eligible",
    "rcs_v4_final", "base_score", "adjusted_score",
    "trust_score", "customer_score", "commercial_score",
    "distinction_value", "distinction_sources",
    "platforms", "total_reviews",
    "entity_match_status", "penalties", "caps",
]


def _write_csv_output(path: str, scores: dict[str, V4Score]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(CSV_COLUMNS)
        for sc in scores.values():
            w.writerow([
                sc.fhrsid, sc.name, sc.confidence_class,
                sc.rankable, sc.league_table_eligible,
                _round3(sc.rcs_v4_final), _round3(sc.base_score),
                _round3(sc.adjusted_score),
                _round3(sc.trust.score), _round3(sc.customer.score),
                _round3(sc.commercial.score),
                round(sc.distinction.value, 4),
                "|".join(sc.distinction.sources),
                "|".join(p.platform for p in sc.customer.platforms),
                sc.customer.total_reviews,
                sc.entity_match_status,
                "|".join(p.code for p in sc.penalties_applied),
                "|".join(c.code for c in sc.caps_applied),
            ])


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="DayDine V4 scoring engine")
    ap.add_argument("--input", required=True,
                    help="Path to establishments JSON (id -> record)")
    ap.add_argument("--menus", default=None)
    ap.add_argument("--editorial", default=None)
    ap.add_argument("--companies-house", default=None)
    ap.add_argument("--out-json", default=None)
    ap.add_argument("--out-csv", default=None)
    args = ap.parse_args(argv)

    records = _load_json(args.input)
    editorial = _load_json(args.editorial) if args.editorial else None
    menus = _load_json(args.menus) if args.menus else None
    ch = _load_json(args.companies_house) if args.companies_house else None

    scores = score_batch(
        records, editorial=editorial, companies_house=ch, menus=menus)

    if args.out_json:
        _write_json_output(args.out_json, scores)
    if args.out_csv:
        _write_csv_output(args.out_csv, scores)

    # Short summary to stdout for local smoke tests
    classes: dict[str, int] = {}
    for sc in scores.values():
        classes[sc.confidence_class] = classes.get(sc.confidence_class, 0) + 1
    print(f"V4 scored {len(scores)} venues")
    for cls, n in sorted(classes.items()):
        print(f"  {cls}: {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
