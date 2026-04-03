"""Priority actions, watch list, what-not-to-do, recommendation tracker, data coverage."""


def build_priority_actions(w, recs):
    w("## Priority Actions\n")
    for i, a in enumerate(recs.get("priority_actions", [])[:3], 1):
        status = a.get("status", "new").upper()
        w(f"### {i}. {a['title']} [{status}]\n")
        w(f"{a['description']}\n")
        w(f"- **Owner:** {a.get('owner', '—')} | **Dimension:** {a.get('dimension', '—').title()}")
        w(f"- **Expected upside:** {a.get('expected_upside', '—')} | "
          f"**Confidence:** {a.get('confidence', 0):.0%}")
        if a.get("evidence"):
            w(f"- **Evidence:** `{a['evidence']}`")
        if a.get("times_seen", 1) > 1:
            w(f"- *Appeared {a['times_seen']} consecutive months.*")
        w("")


def build_watch_list(w, recs):
    w("## Watch List\n")
    for wa in recs.get("watch_items", [])[:2]:
        w(f"**{wa['title']}** [{wa.get('status', 'new').upper()}]\n")
        w(f"{wa['description']}\n")


def build_what_not_to_do(w, recs):
    w("## What Not to Do This Month\n")
    dont = recs.get("what_not_to_do")
    if dont:
        w(f"**{dont['title']}**\n")
        w(f"{dont.get('_reason', dont.get('description', ''))}\n")


def build_recommendation_tracker(w, recs):
    w("## Recommendation Tracker\n")
    all_recs = recs.get("all_recs", [])
    active = [r for r in all_recs if r.get("status") not in ("resolved", "dropped", "completed")]
    resolved = [r for r in all_recs if r.get("status") in ("resolved", "completed")]
    if active:
        w("| # | Recommendation | Status | Since | Months | Owner | Dimension |")
        w("|--:|---------------|--------|-------|-------:|-------|-----------|")
        for i, r in enumerate(sorted(active, key=lambda x: -x.get("priority_score", 0)), 1):
            w(f"| {i} | {r['title'][:50]} | {r['status']} | {r.get('first_seen', '—')} "
              f"| {r.get('times_seen', 1)} | {r.get('owner', '—')} | {r.get('dimension', '—')} |")
        w("")
    else:
        w("First reporting month — all recommendations are new above.\n")
    if resolved:
        w(f"*{len(resolved)} recommendation(s) resolved/completed.*\n")


def build_conditional_intelligence(w, blocks):
    if not blocks:
        return
    w("## Market Intelligence\n")
    for b in blocks:
        w(f"### {b['title']}\n")
        w(f"{b['content']}\n")


def build_data_coverage(w, scorecard, review_intel):
    w("---\n")
    w("## Data Coverage & Confidence\n")
    has_narr = review_intel.get("has_narrative", False) if review_intel else False
    fsa = scorecard.get("fsa_rating")
    gr = scorecard.get("google_rating")
    grc = scorecard.get("google_reviews")
    sources = [
        ("FSA Hygiene Rating", f"Rating {fsa}/5" if fsa else "Not available", fsa is not None),
        ("Google Business Profile", f"{gr}★ ({grc} reviews)" if gr else "Not available", gr is not None),
        ("Google Review Text",
         f"{review_intel.get('reviews_analyzed', 0)} reviews analyzed" if has_narr else "Not collected",
         has_narr),
        ("TripAdvisor", "Not collected", False),
        ("Companies House", "Not checked", False),
    ]
    w("| Source | Status | Available |")
    w("|--------|--------|:---------:|")
    for name, status, avail in sources:
        w(f"| {name} | {status} | {'✓' if avail else '—'} |")
    w("")
    n = sum(1 for _, _, a in sources if a)
    if n >= 4:
        w("**Report confidence: High** — Multiple independent sources.\n")
    elif n >= 2:
        w("**Report confidence: Medium** — Core signals available, some dimensions limited.\n")
    else:
        w("**Report confidence: Low** — Sparse data constrains depth.\n")
    unlocks = []
    if not has_narr:
        unlocks.append("**Google review text** → sentiment-by-topic, complaint clustering, quoted evidence")
    unlocks.append("**TripAdvisor enrichment** → cross-platform validation, convergence scoring")
    w("**What additional collection would unlock:**\n")
    for u in unlocks:
        w(f"- {u}")
    w("")
