#!/usr/bin/env python3
"""
scripts/generate_v4_samples.py — Generate V4 operator-report samples.

For a curated list of venues covering every class:
  - Rankable-A: Vintner Wine Bar (503480)
  - Rankable-B: Lambs (503316), Loxleys (502816)
  - Directional-C: Soma (1847445) — ambiguous entity
  - Profile-only-D: Digby's Events (1774610)
  - Closed (synthetic): a copy of Arrow Mill (503282) with fsa_closed=true
  - Temp-closed (synthetic): a copy of The Opposition (503481) with
    business_status=CLOSED_TEMPORARILY

Reads:
  - stratford_rcs_v4_scores.json
  - stratford_establishments.json
  - stratford_menus.json
  - stratford_editorial.json (optional)

Writes:
  - samples/v4/monthly/<safe_name>_<month>.md
  - samples/v4/monthly/<safe_name>_<month>.json
  - samples/v4/monthly/<safe_name>_<month>_qa.json

Outputs are under `samples/v4/` — explicitly NOT `outputs/monthly/`, which
remains the V3.4 live-pipeline directory during parallel operation
(spec §12.5 / §12.7).
"""
from __future__ import annotations

import copy
import json
import os
import sys

REPO = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, REPO)

from operator_intelligence.v4_adapter import build_report_inputs  # noqa: E402
from operator_intelligence.v4_report_generator import (  # noqa: E402
    generate_v4_monthly_report, build_v4_report_json,
)
from operator_intelligence.v4_peer_benchmarks import (  # noqa: E402
    compute_v4_peer_benchmarks,
)
from operator_intelligence.v4_recommendations import (  # noqa: E402
    generate_v4_recommendations,
)

MONTH = "2026-04"
OUTPUT_DIR = os.path.join(REPO, "samples", "v4", "monthly")

# venue_id -> {label, synthetic overrides to the venue_record}
SAMPLES = [
    {"id": "503480", "label": "Vintner Wine Bar (Rankable-A)"},
    {"id": "503316", "label": "Lambs (Rankable-B)"},
    {"id": "502816", "label": "Loxleys Restaurant And Wine Bar (Rankable-B)"},
    {"id": "1847445", "label": "Soma (Directional-C, ambiguous entity)"},
    {"id": "1765854", "label": "The Roebuck Inn Alcester (Profile-only-D)"},
    {"id": "503282", "label": "Arrow Mill (synthetic: closed)",
     "override": {"fsa_closed": True}},
    {"id": "503481", "label": "The Opposition (synthetic: temp closed)",
     "override": {"business_status": "CLOSED_TEMPORARILY"}},
]


def _load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _safe_name(s):
    return s.replace(" ", "_").replace("/", "-").replace("(", "").replace(")", "")


def main():
    v4 = _load_json(os.path.join(REPO, "stratford_rcs_v4_scores.json"))
    establishments = _load_json(os.path.join(
        REPO, "stratford_establishments.json"))
    menus = _load_json(os.path.join(REPO, "stratford_menus.json")) or {}
    editorial = _load_json(os.path.join(REPO, "stratford_editorial.json")) or {}
    er_report = _load_json(os.path.join(
        REPO, "stratford_entity_resolution_report.json")) or {}

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Build a lookup of ambiguous-gpid groups by fhrsid -> group entry
    amb_groups = er_report.get("duplicate_gpid_groups") or []
    amb_lookup = {}
    for g in amb_groups:
        for fid in g.get("fhrsids", []):
            amb_lookup[str(fid)] = g

    summary_rows = []

    for s in SAMPLES:
        fid = s["id"]
        venue_record = copy.deepcopy(establishments.get(fid))
        v4_score = copy.deepcopy(v4.get(fid))
        if venue_record is None or v4_score is None:
            print(f"SKIP {fid} ({s['label']}) — missing data")
            continue

        # Apply synthetic override (closure scenarios)
        if s.get("override"):
            for k, val in s["override"].items():
                venue_record[k] = val
            # For closure sims we must also trigger the engine's suppression
            # behaviour by re-scoring. Easier: patch the V4 score payload so
            # the derived report mode shifts; the adapter picks it up via
            # _derive_mode which reads venue_record (fsa_closed / business_status).
            if s["override"].get("fsa_closed"):
                v4_score = copy.deepcopy(v4_score)
                v4_score["rcs_v4_final"] = None  # spec §7.4 suppression
                v4_score["confidence_class"] = v4_score.get(
                    "confidence_class", "Rankable-B")

        ambig = amb_lookup.get(fid)

        peer_benchmarks = compute_v4_peer_benchmarks(
            venue_fid=fid,
            venue_record=venue_record,
            v4_scores=v4,
            establishments=establishments,
        )

        inputs = build_report_inputs(
            v4_score=v4_score,
            venue_record=venue_record,
            month_str=MONTH,
            menu_record=menus.get(fid),
            editorial=editorial.get(fid),
            entity_resolution_note=ambig,
            peer_benchmarks=peer_benchmarks,
        )
        # V4-native recommendations engine (deferred-item 1 closed)
        inputs.recommendations = generate_v4_recommendations(inputs)

        report_text, qa = generate_v4_monthly_report(inputs)
        report_json = build_v4_report_json(inputs, report_text, qa)

        name = _safe_name(inputs.name or f"venue_{fid}")
        md_path = os.path.join(OUTPUT_DIR, f"{name}_{MONTH}.md")
        json_path = os.path.join(OUTPUT_DIR, f"{name}_{MONTH}.json")
        qa_path = os.path.join(OUTPUT_DIR, f"{name}_{MONTH}_qa.json")

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(report_text)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report_json, f, indent=2, ensure_ascii=False)
        with open(qa_path, "w", encoding="utf-8") as f:
            json.dump(qa, f, indent=2, ensure_ascii=False)

        guard_errors = len(qa["guardrail_check"]["errors"])
        guard_warnings = len(qa["guardrail_check"]["warnings"])
        summary_rows.append({
            "fhrsid": fid,
            "label": s["label"],
            "mode": inputs.report_mode,
            "score": inputs.rcs_v4_final,
            "class": inputs.confidence_class,
            "guard_errors": guard_errors,
            "guard_warnings": guard_warnings,
            "path": md_path,
        })
        print(f"OK  {fid:<10} {inputs.report_mode:<16} "
              f"score={inputs.rcs_v4_final}  "
              f"guard_err={guard_errors}  "
              f"{s['label']}")

    # Summary artefact
    summary_path = os.path.join(OUTPUT_DIR, f"_summary_{MONTH}.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({"month": MONTH, "samples": summary_rows}, f, indent=2)
    print(f"\nWrote {len(summary_rows)} samples to {OUTPUT_DIR}")
    print(f"Summary: {summary_path}")


if __name__ == "__main__":
    main()
