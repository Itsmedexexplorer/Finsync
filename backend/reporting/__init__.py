"""Reporting and Explainability subsystem for VERITY."""

from backend.reporting.explainability import ExplainabilityEngine
from backend.reporting.models import (
    ClaimSummaryItem,
    ConfidenceFactor,
    ContradictionSummaryItem,
    EntitySummary,
    EvidenceSummaryItem,
    FinancialSummary,
    FinancialTruthReport,
    MatchingSummary,
    ProvenanceReferences,
    ReconciliationSummary,
    ReportStatus,
    TransactionSummaryItem,
    UnresolvedItem,
)
from backend.reporting.report_builder import FinancialTruthReportBuilder
from backend.reporting.service import ReportingService

__all__ = [
    "ReportStatus",
    "EntitySummary",
    "FinancialSummary",
    "EvidenceSummaryItem",
    "ClaimSummaryItem",
    "TransactionSummaryItem",
    "MatchingSummary",
    "ContradictionSummaryItem",
    "ReconciliationSummary",
    "ConfidenceFactor",
    "UnresolvedItem",
    "ProvenanceReferences",
    "FinancialTruthReport",
    "ExplainabilityEngine",
    "FinancialTruthReportBuilder",
    "ReportingService",
]
