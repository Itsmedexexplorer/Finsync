"""Unit tests for Partial Settlement Financial Truth Report generation."""

import pytest
from backend.domain.claim import Claim, ClaimType
from backend.domain.entity import Entity, EntityType
from backend.domain.reconciliation import ReconciliationStatus
from backend.domain.transaction import Transaction, TransactionDirection
from backend.reconciliation.result import ReconciliationResult
from backend.reporting.models import ReportStatus
from backend.reporting.service import ReportingService


@pytest.fixture
def service() -> ReportingService:
    return ReportingService()


def test_partial_settlement_report_generation(service: ReportingService) -> None:
    claim = Claim(id="C2", evidence_id="E2", claim_type=ClaimType.INVOICE_ISSUED, claimed_amount=20000.0, counterparty_hint="Priya Patel")
    txn = Transaction(id="T2", amount=15000.0, direction=TransactionDirection.CREDIT, origin_entity_id="ENT-002")
    entity = Entity(id="ENT-002", canonical_name="Priya Patel", entity_type=EntityType.INDIVIDUAL)

    recon_res = ReconciliationResult(
        reconciliation_id="REC-002",
        status=ReconciliationStatus.PARTIALLY_SETTLED,
        expected_amount=20000.0,
        matched_amount=15000.0,
        outstanding_amount=5000.0,
        confidence_score=0.95,
        supporting_signals=["VALID_PARTIAL_PAYMENT", "EXACT_ENTITY"],
        explanation="Partial settlement verified.",
        claim_ids=["C2"],
        transaction_ids=["T2"],
        entity_id="ENT-002",
    )

    report = service.build_report(
        reconciliation_result=recon_res,
        claims=[claim],
        transactions=[txn],
        entities=[entity],
    )

    assert report.status == ReportStatus.PARTIALLY_SETTLED
    assert report.financial_summary.claimed_amount == 20000.0
    assert report.financial_summary.matched_amount == 15000.0
    assert report.financial_summary.outstanding_amount == 5000.0
    # Must list outstanding balance in unresolved items
    assert any("5,000.00" in item.description for item in report.unresolved_items)
    # Must recommend tracking the balance
    assert any("5,000.00" in act for act in report.recommended_actions)
