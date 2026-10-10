"""Cross-Case Intelligence & Counterparty Memory Subsystem (Day 18).

Provides institutional memory, cross-case entity history, reference reuse detection,
and recurring discrepancy pattern analysis across historical financial cases.
"""

from backend.cross_case.models import (
    CaseIntelligenceProfile,
    CorrelationRelationshipType,
    CounterpartyHistory,
    CrossCaseCorrelation,
    HistoricalRiskSignal,
    RecurringDiscrepancyPattern,
    ReferenceCorrelation,
)
from backend.cross_case.service import CrossCaseIntelligenceService

__all__ = [
    "CaseIntelligenceProfile",
    "CorrelationRelationshipType",
    "CounterpartyHistory",
    "CrossCaseCorrelation",
    "HistoricalRiskSignal",
    "RecurringDiscrepancyPattern",
    "ReferenceCorrelation",
    "CrossCaseIntelligenceService",
]
