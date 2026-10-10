"""Unit tests for Portfolio Exposure synthesis."""

import pytest
from backend.case_processing.result import CaseProcessingResult
from backend.portfolio.aggregator import PortfolioAggregator
from backend.portfolio.models import PortfolioCaseStatus
from backend.reconciliation.result import ReconciliationResult, ReconciliationStatus


def test_exposure_breakdowns() -> None:
    recon1 = ReconciliationResult(reconciliation_id="R1", status=ReconciliationStatus.CONFIRMED, expected_amount=20000.0, matched_amount=20000.0, explanation="")
    recon2 = ReconciliationResult(reconciliation_id="R2", status=ReconciliationStatus.PARTIALLY_SETTLED, expected_amount=30000.0, matched_amount=20000.0, outstanding_amount=10000.0, explanation="")
    recon3 = ReconciliationResult(reconciliation_id="R3", status=ReconciliationStatus.CONTRADICTED, expected_amount=50000.0, matched_amount=40000.0, outstanding_amount=10000.0, explanation="")

    res1 = CaseProcessingResult(case_id="C1", status="CONFIRMED", confidence_score=1.0, reconciliation=recon1)
    res2 = CaseProcessingResult(case_id="C2", status="PARTIALLY_SETTLED", confidence_score=0.95, reconciliation=recon2)
    res3 = CaseProcessingResult(case_id="C3", status="CONTRADICTED", confidence_score=0.90, reconciliation=recon3)

    item1 = PortfolioAggregator.from_case_result(res1)
    item2 = PortfolioAggregator.from_case_result(res2)
    item3 = PortfolioAggregator.from_case_result(res3)

    exposure = PortfolioAggregator.aggregate_exposure([item1, item2, item3])
    assert exposure.total_exposure == 100000.0  # 20k + 30k + 50k
    assert exposure.confirmed_exposure == 20000.0
    assert exposure.partial_exposure == 10000.0
    assert exposure.disputed_exposure == 10000.0
