"""Unit tests for unified PortfolioService."""

import pytest
from backend.case_processing.result import CaseProcessingResult
from backend.portfolio.models import PortfolioCaseStatus, PortfolioPriority
from backend.portfolio.service import PortfolioCaseNotFoundError, PortfolioService
from backend.reconciliation.result import ReconciliationResult, ReconciliationStatus


@pytest.fixture
def service() -> PortfolioService:
    return PortfolioService()


def test_service_register_and_queues(service: PortfolioService) -> None:
    recon1 = ReconciliationResult(reconciliation_id="R1", status=ReconciliationStatus.CONFIRMED, expected_amount=10000.0, matched_amount=10000.0, explanation="")
    recon2 = ReconciliationResult(reconciliation_id="R2", status=ReconciliationStatus.CONTRADICTED, expected_amount=50000.0, matched_amount=40000.0, outstanding_amount=10000.0, explanation="", discrepancy_ids=["D1"])

    res1 = CaseProcessingResult(case_id="C1", status="CONFIRMED", confidence_score=1.0, reconciliation=recon1)
    res2 = CaseProcessingResult(case_id="C2", status="CONTRADICTED", confidence_score=0.9, reconciliation=recon2)

    service.register_case(res1)
    service.register_case(res2)

    assert len(service.list_cases()) == 2
    summary = service.get_summary()
    assert summary.total_cases == 2

    # Review queue should contain C2 (contradicted)
    rq = service.get_review_queue()
    assert len(rq) == 1
    assert rq[0].case_id == "C2"


def test_service_assign_flow(service: PortfolioService) -> None:
    recon = ReconciliationResult(reconciliation_id="R1", status=ReconciliationStatus.CONFIRMED, expected_amount=10000.0, matched_amount=10000.0, explanation="")
    res = CaseProcessingResult(case_id="C-ASG", status="CONFIRMED", confidence_score=1.0, reconciliation=recon)
    service.register_case(res)

    item = service.assign_case("C-ASG", "ctrl_1", "Alice")
    assert item.assigned_reviewer_id == "ctrl_1"
    assert item.portfolio_status == PortfolioCaseStatus.ASSIGNED

    # Unknown case
    with pytest.raises(PortfolioCaseNotFoundError):
        service.assign_case("NON-EXISTENT", "ctrl_1")
