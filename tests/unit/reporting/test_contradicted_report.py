"""Unit tests for Contradicted Financial Truth Report generation."""

import pytest
from backend.domain.claim import Claim, ClaimType
from backend.domain.discrepancy import Discrepancy, DiscrepancySeverity, DiscrepancyType
from backend.domain.reconciliation import ReconciliationStatus
from backend.domain.transaction import Transaction, TransactionDirection
from backend.reconciliation.result import ReconciliationResult
from backend.reporting.models import ReportStatus
from backend.reporting.service import ReportingService


@pytest.fixture
def service() -> ReportingService:
    return ReportingService()


def test_contradicted_report_generation(service: ReportingService) -> None:
    claim = Claim(id="C3", evidence_id="E3", claim_type=ClaimType.INVOICE_ISSUED, claimed_amount=20000.0, reference_id_hint="408219381920")
    txn = Transaction(id="T3", amount=18000.0, direction=TransactionDirection.CREDIT, bank_reference="408219381920")
    disc = Discrepancy(
        id="D3",
        discrepancy_type=DiscrepancyType.AMOUNT_MISMATCH,
        severity=DiscrepancySeverity.ERROR,
        message="Claimed 20k vs Bank 18k",
        expected_value="20000.00",
        observed_value="18000.00",
    )

    recon_res = ReconciliationResult(
        reconciliation_id="REC-003",
        status=ReconciliationStatus.CONTRADICTED,
        expected_amount=20000.0,
        matched_amount=18000.0,
        outstanding_amount=20000.0,
        confidence_score=0.98,
        contradicting_signals=["AMOUNT_MISMATCH"],
        explanation="Contradiction detected.",
        claim_ids=["C3"],
        transaction_ids=["T3"],
        discrepancy_ids=["D3"],
    )

    report = service.build_report(
        reconciliation_result=recon_res,
        claims=[claim],
        transactions=[txn],
        discrepancies=[disc],
    )

    assert report.status == ReportStatus.CONTRADICTED
    assert len(report.contradiction_summary) == 1
    assert report.contradiction_summary[0].discrepancy_type == "AMOUNT_MISMATCH"
    assert report.contradiction_summary[0].expected_value == "20000.00"
    assert report.contradiction_summary[0].observed_value == "18000.00"
    assert any("Audit invoice amount" in act for act in report.recommended_actions)
