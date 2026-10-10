"""Unit tests for Ambiguous Financial Truth Report generation."""

import pytest
from backend.domain.claim import Claim, ClaimType
from backend.domain.reconciliation import ReconciliationStatus
from backend.domain.transaction import Transaction, TransactionDirection
from backend.reconciliation.result import ReconciliationResult
from backend.reporting.models import ReportStatus
from backend.reporting.service import ReportingService


@pytest.fixture
def service() -> ReportingService:
    return ReportingService()


def test_ambiguous_report_generation(service: ReportingService) -> None:
    claim = Claim(id="C4", evidence_id="E4", claim_type=ClaimType.INVOICE_ISSUED, claimed_amount=20000.0)
    txns = [
        Transaction(id="T4A", amount=20000.0, direction=TransactionDirection.CREDIT),
        Transaction(id="T4B", amount=20000.0, direction=TransactionDirection.CREDIT),
    ]

    recon_res = ReconciliationResult(
        reconciliation_id="REC-004",
        status=ReconciliationStatus.AMBIGUOUS,
        expected_amount=20000.0,
        matched_amount=40000.0,
        outstanding_amount=0.0,
        confidence_score=0.60,
        supporting_signals=["AMBIGUOUS_CANDIDATES"],
        explanation="Ambiguity preserved.",
        claim_ids=["C4"],
        transaction_ids=["T4A", "T4B"],
    )

    report = service.build_report(
        reconciliation_result=recon_res,
        claims=[claim],
        transactions=txns,
    )

    assert report.status == ReportStatus.AMBIGUOUS
    assert report.confidence_score == 0.60
    assert any("Human review required" in act for act in report.recommended_actions)
    assert any("AMBIGUOUS_CANDIDATES" in item.item_type for item in report.unresolved_items)
