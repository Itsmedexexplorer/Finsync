"""Unit tests for Portfolio Aggregation Engine."""

import pytest
from backend.case_processing.result import CaseProcessingResult
from backend.controller.models import ControllerActionType, ControllerDecision, ControllerRiskLevel
from backend.portfolio.aggregator import PortfolioAggregator
from backend.portfolio.models import PortfolioCaseStatus, PortfolioPriority
from backend.reconciliation.result import ReconciliationResult, ReconciliationStatus


def test_aggregator_from_clean_case() -> None:
    recon = ReconciliationResult(
        reconciliation_id="REC-01",
        status=ReconciliationStatus.CONFIRMED,
        expected_amount=35000.0,
        matched_amount=35000.0,
        outstanding_amount=0.0,
        explanation="Full 1:1 match verified",
    )
    res = CaseProcessingResult(
        case_id="CASE-AGG-01",
        status="CONFIRMED",
        confidence_score=1.0,
        reconciliation=recon,
    )
    decision = ControllerDecision(
        case_id="CASE-AGG-01",
        risk_level=ControllerRiskLevel.NONE,
        decision=ControllerActionType.CONFIRM_RECONCILIATION,
        requires_human_review=False,
        confidence=1.0,
        reasons=[],
    )

    item = PortfolioAggregator.from_case_result(res, decision)
    assert item.case_id == "CASE-AGG-01"
    assert item.deterministic_status == "CONFIRMED"
    assert item.amount_exposure == 35000.0
    assert item.disputed_amount == 0.0
    assert item.requires_human_review is False
    assert item.portfolio_status == PortfolioCaseStatus.NEW


def test_aggregator_summary_totals() -> None:
    recon1 = ReconciliationResult(reconciliation_id="R1", status=ReconciliationStatus.CONFIRMED, expected_amount=10000.0, matched_amount=10000.0, explanation="")
    recon2 = ReconciliationResult(reconciliation_id="R2", status=ReconciliationStatus.CONTRADICTED, expected_amount=20000.0, matched_amount=18000.0, outstanding_amount=2000.0, explanation="")

    res1 = CaseProcessingResult(case_id="C1", status="CONFIRMED", confidence_score=1.0, reconciliation=recon1)
    res2 = CaseProcessingResult(case_id="C2", status="CONTRADICTED", confidence_score=0.9, reconciliation=recon2)

    item1 = PortfolioAggregator.from_case_result(res1)
    item2 = PortfolioAggregator.from_case_result(res2)

    summary = PortfolioAggregator.aggregate_summary([item1, item2])
    assert summary.total_cases == 2
    assert summary.total_exposure == 30000.0
    assert summary.total_disputed_amount == 2000.0
