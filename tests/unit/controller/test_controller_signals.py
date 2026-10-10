"""Unit tests for Controller Signal Extraction."""

import pytest
from backend.case_processing.result import CaseProcessingResult
from backend.controller.models import ControllerRiskLevel
from backend.controller.signals import ControllerSignalType, SignalExtractor
from backend.reporting.models import (
    ContradictionSummaryItem,
    EntitySummary,
    FinancialSummary,
    FinancialTruthReport,
    MatchingSummary,
    ProvenanceReferences,
    ReconciliationSummary,
    ReportStatus,
)


def test_extract_signals_clean_case() -> None:
    rep = FinancialTruthReport(
        report_id="REP-01",
        case_id="CLEAN-01",
        status=ReportStatus.CONFIRMED,
        confidence_score=1.0,
        title="Clean Settlement",
        summary="All matched",
        entity_summary=EntitySummary(canonical_name="Rahul Kumar"),
        financial_summary=FinancialSummary(claimed_amount=35000.0, matched_amount=35000.0),
        reconciliation_summary=ReconciliationSummary(reconciliation_id="REC-01", status="CONFIRMED", matched_amount=35000.0),
        explanation="Clean 1:1 match",
        provenance=ProvenanceReferences(),
    )
    result = CaseProcessingResult(
        case_id="CLEAN-01",
        status="CONFIRMED",
        confidence_score=1.0,
        report=rep,
        financial_summary={"matched_amount": 35000.0, "outstanding_amount": 0.0},
    )

    signals = SignalExtractor.extract_signals(result)
    assert len(signals) == 1
    assert signals[0].signal_type == ControllerSignalType.CONFIRMED_RECONCILIATION
    assert signals[0].severity == ControllerRiskLevel.NONE


def test_extract_signals_critical_contradiction() -> None:
    disc = ContradictionSummaryItem(
        discrepancy_id="DISC-01",
        discrepancy_type="ENTITY_MISMATCH",
        severity="CRITICAL",
        message="Entity mismatch: Rahul vs Rohit",
        involved_evidence_ids=["EVID-01"],
    )
    rep = FinancialTruthReport(
        report_id="REP-02",
        case_id="CNF-01",
        status=ReportStatus.CONTRADICTED,
        confidence_score=0.98,
        title="Contradicted Case",
        summary="Entity mismatch",
        entity_summary=EntitySummary(canonical_name="Rahul Kumar"),
        financial_summary=FinancialSummary(claimed_amount=25000.0, matched_amount=25000.0),
        contradiction_summary=[disc],
        reconciliation_summary=ReconciliationSummary(reconciliation_id="REC-02", status="CONTRADICTED"),
        explanation="Contradicted entity",
        provenance=ProvenanceReferences(),
    )
    result = CaseProcessingResult(
        case_id="CNF-01",
        status="CONTRADICTED",
        confidence_score=0.98,
        report=rep,
        financial_summary={"matched_amount": 25000.0, "outstanding_amount": 25000.0},
    )

    signals = SignalExtractor.extract_signals(result)
    assert any(s.signal_type == ControllerSignalType.ENTITY_MISMATCH for s in signals)
    assert any(s.severity == ControllerRiskLevel.CRITICAL for s in signals)
