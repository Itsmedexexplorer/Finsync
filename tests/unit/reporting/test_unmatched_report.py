"""Unit tests for Unmatched Transaction Financial Truth Report generation."""

import pytest
from backend.domain.reconciliation import ReconciliationStatus
from backend.domain.transaction import Transaction, TransactionDirection
from backend.reconciliation.result import ReconciliationResult
from backend.reporting.models import ReportStatus
from backend.reporting.service import ReportingService


@pytest.fixture
def service() -> ReportingService:
    return ReportingService()


def test_unmatched_report_generation(service: ReportingService) -> None:
    txn = Transaction(id="T6", amount=35000.0, direction=TransactionDirection.CREDIT, bank_reference="408219381920")

    recon_res = ReconciliationResult(
        reconciliation_id="REC-006",
        status=ReconciliationStatus.UNMATCHED,
        expected_amount=None,
        matched_amount=35000.0,
        outstanding_amount=0.0,
        confidence_score=1.0,
        supporting_signals=[],
        explanation="Unmatched ledger transaction.",
        transaction_ids=["T6"],
    )

    report = service.build_report(
        reconciliation_result=recon_res,
        transactions=[txn],
    )

    assert report.status == ReportStatus.UNMATCHED
    assert report.financial_summary.matched_amount == 35000.0
    assert any("Map unmatched transaction" in act for act in report.recommended_actions)
