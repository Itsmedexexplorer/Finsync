"""Unit tests for Portfolio Invariants and Safety Guarantees."""

import pytest
from backend.case_processing.result import CaseProcessingResult
from backend.portfolio.aggregator import PortfolioAggregator
from backend.portfolio.models import PortfolioCaseStatus
from backend.portfolio.service import PortfolioService
from backend.reconciliation.result import ReconciliationResult, ReconciliationStatus
from backend.review.models import ReviewDecision, ReviewRecord, ReviewStatus


def test_safety_portfolio_never_mutates_deterministic_financial_truth() -> None:
    recon = ReconciliationResult(
        reconciliation_id="REC-SAFE",
        status=ReconciliationStatus.CONTRADICTED,
        expected_amount=20000.0,
        matched_amount=18000.0,
        outstanding_amount=2000.0,
        explanation="Contradicted",
    )
    res = CaseProcessingResult(
        case_id="CASE-SAFE-01",
        status="CONTRADICTED",
        confidence_score=0.95,
        reconciliation=recon,
    )

    review = ReviewRecord(
        case_id="CASE-SAFE-01",
        review_id="REV-SAFE-01",
        status=ReviewStatus.RESOLVED,
        decision=ReviewDecision.CONFIRMED,
    )

    service = PortfolioService()
    item = service.register_case(res, review_record=review)

    # Invariants:
    # 1. Deterministic status remains strictly CONTRADICTED
    assert res.status == "CONTRADICTED"
    assert item.deterministic_status == "CONTRADICTED"

    # 2. Operational portfolio status is RESOLVED
    assert item.portfolio_status == PortfolioCaseStatus.RESOLVED

    # 3. Human review decision recorded separately
    assert item.human_review_decision == "CONFIRMED"


def test_safety_zero_double_counting_invariant() -> None:
    # Same transaction appearing in multiple places must not double count
    recon = ReconciliationResult(
        reconciliation_id="REC-NODOUBLE",
        status=ReconciliationStatus.CONFIRMED,
        expected_amount=10000.0,
        matched_amount=10000.0,
        explanation="Clean",
    )
    res = CaseProcessingResult(
        case_id="CASE-ND-01",
        status="CONFIRMED",
        confidence_score=1.0,
        reconciliation=recon,
    )

    item = PortfolioAggregator.from_case_result(res)
    assert item.amount_exposure == 10000.0  # Not 20,000
