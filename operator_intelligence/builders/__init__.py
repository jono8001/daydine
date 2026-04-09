"""
Reusable report section builders.

Each builder enforces a fixed quality standard and output shape.
Import all builders from this package for report assembly.
"""

from operator_intelligence.builders.exec_summary import build as build_executive_summary
from operator_intelligence.builders.scorecard import build as build_scorecard
from operator_intelligence.builders.diagnosis import (
    build_performance as build_performance_diagnosis,
    build_commercial as build_commercial_diagnosis,
)
from operator_intelligence.builders.review_section import build as build_review_intelligence
from operator_intelligence.builders.review_section import build_review_appendices
from operator_intelligence.builders.actions_tracker import (
    build_priority_actions,
    build_watch_list,
    build_what_not_to_do,
    build_recommendation_tracker,
    build_competitive_market_intelligence,
    build_data_coverage,
)
from operator_intelligence.builders.long_form import (
    build_management_priorities,
    build_category_validation,
    build_market_position,
    build_dimension_diagnosis,
    build_public_vs_reality,
    build_demand_capture_audit,
    build_monitoring_plan,
    build_evidence_appendix,
)
from operator_intelligence.builders.monthly_movement import build_monthly_movement
from operator_intelligence.builders.segment_section import build_segment_intelligence
from operator_intelligence.builders.trust_detail import build_trust_detail
from operator_intelligence.builders.data_basis import build_data_basis
from operator_intelligence.builders.financial_impact import build_financial_impact
from operator_intelligence.builders.risk_alerts import build_risk_alerts
from operator_intelligence.builders.venue_identity import (
    build_known_for,
    build_protect_improve_ignore,
)
from operator_intelligence.builders.menu_intelligence import build_menu_intelligence
