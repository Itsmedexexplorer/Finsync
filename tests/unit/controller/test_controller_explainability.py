"""Unit tests for Controller Explainability and Grounded Q&A."""

import pytest
from backend.case_processing.result import CaseProcessingResult
from backend.controller.explainability import ControllerExplainabilityEngine
from backend.controller.models import ControllerActionType, ControllerDecision, ControllerRiskLevel
from backend.reporting.models import (
    ContradictionSummaryItem,
    EntitySummary,
    FinancialSummary,
    FinancialTruthReport,
    ProvenanceReferences,
    ReconciliationSummary,
    ReportStatus,
)


def test_answer_query_why_review_required() -> None:
    disc = ContradictionSummaryItem(
        discrepancy_id="DISC-01",
        discrepancy_type="AMOUNT_MISMATCH",
        severity="ERROR",
        message="Invoice INR 20,000 does not match Bank credit INR 18,000",
        expected_value="20000.00",
        observed_value="18000.00",
        involved_evidence_ids=["EVID-01"],
    )
    rep = FinancialTruthReport(
        report_id="REP-01",
        case_id="CASE-101",
        status=ReportStatus.CONTRADICTED,
        confidence_score=0.98,
        title="Amount Contradiction",
        summary="Mismatch 20k vs 18k",
        entity_summary=EntitySummary(canonical_name="Rahul Kumar"),
        financial_summary=FinancialSummary(claimed_amount=20000.0, matched_amount=18000.0, outstanding_amount=20000.0),
        contradiction_summary=[disc],
        reconciliation_summary=ReconciliationSummary(reconciliation_id="REC-101", status="CONTRADICTED"),
        explanation="Contradicted",
        provenance=ProvenanceReferences(discrepancy_ids=["DISC-01"], claim_ids=["CLM-01"], transaction_ids=["TXN-01"]),
    )
    result = CaseProcessingResult(
        case_id="CASE-101",
        status="CONTRADICTED",
        confidence_score=0.98,
        report=rep,
        financial_summary={"claimed_amount": 20000.0, "matched_amount": 18000.0, "outstanding_amount": 20000.0},
    )
    decision = ControllerDecision(
        case_id="CASE-101",
        risk_level=ControllerRiskLevel.HIGH,
        decision=ControllerActionType.INVESTIGATE_CONTRADICTION,
        requires_human_review=True,
        confidence=0.98,
        reasons=["Amount mismatch: expected 20000.00, observed 18000.00"],
        supporting_discrepancy_ids=["DISC-01"],
    )

    resp = ControllerExplainabilityEngine.answer_query("Why is human review required?", decision, result)
    assert resp.case_id == "CASE-101"
    assert "review is required" in resp.answer.lower()
    assert "DISC-01" in resp.grounding_ids
