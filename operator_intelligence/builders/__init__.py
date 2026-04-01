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
from operator_intelligence.builders.actions_tracker import (
    build_priority_actions,
    build_watch_list,
    build_what_not_to_do,
    build_recommendation_tracker,
    build_conditional_intelligence,
    build_data_coverage,
)

__all__ = [
    "build_executive_summary",
    "build_scorecard",
    "build_performance_diagnosis",
    "build_commercial_diagnosis",
    "build_review_intelligence",
    "build_priority_actions",
    "build_watch_list",
    "build_what_not_to_do",
    "build_recommendation_tracker",
    "build_conditional_intelligence",
    "build_data_coverage",
]
