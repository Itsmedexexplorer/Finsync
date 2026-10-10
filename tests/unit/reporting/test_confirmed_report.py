"""Unit tests for Confirmed Financial Truth Report generation."""

import pytest
from backend.domain.claim import Claim, ClaimType
from backend.domain.entity import Entity, EntityType
from backend.domain.evidence import Evidence, EvidenceModality, EvidenceSourceType
from backend.domain.reconciliation import ReconciliationStatus
from backend.domain.transaction import Transaction, TransactionDirection
from backend.reconciliation.result import ReconciliationResult
from backend.reporting.models import ReportStatus
from backend.reporting.service import ReportingService


@pytest.fixture
def service() -> ReportingService:
    return ReportingService()


def test_confirmed_report_generation(service: ReportingService) -> None:
    ev = Evidence(id="E1", modality=EvidenceModality.INVOICE, source_type=EvidenceSourceType.ZOHO_INVOICE, source_name="inv.pdf", raw_payload="35k")
    claim = Claim(id="C1", evidence_id="E1", claim_type=ClaimType.INVOICE_ISSUED, claimed_amount=35000.0, counterparty_hint="Rahul Kumar")
    txn = Transaction(id="T1", amount=35000.0, direction=TransactionDirection.CREDIT, bank_reference="408219381920", origin_entity_id="ENT-001")
    entity = Entity(id="ENT-001", canonical_name="Rahul Kumar", entity_type=EntityType.INDIVIDUAL, pan="ABCDE1234F")

    recon_res = ReconciliationResult(
        reconciliation_id="REC-001",
        status=ReconciliationStatus.CONFIRMED,
        expected_amount=35000.0,
        matched_amount=35000.0,
        outstanding_amount=0.0,
        confidence_score=1.0,
        supporting_signals=["EXACT_REFERENCE", "EXACT_AMOUNT", "EXACT_ENTITY"],
        explanation="Full settlement confirmed.",
        claim_ids=["C1"],
        transaction_ids=["T1"],
        evidence_ids=["E1"],
        entity_id="ENT-001",
    )

    report = service.build_report(
        reconciliation_result=recon_res,
        claims=[claim],
        transactions=[txn],
        evidence=[ev],
        entities=[entity],
        case_id="CASE-001",
    )

    assert report.case_id == "CASE-001"
    assert report.status == ReportStatus.CONFIRMED
    assert report.confidence_score == 1.0
    assert report.entity_summary.canonical_name == "Rahul Kumar"
    assert report.entity_summary.pan == "ABCDE1234F"
    assert report.financial_summary.claimed_amount == 35000.0
    assert report.financial_summary.matched_amount == 35000.0
    assert report.financial_summary.outstanding_amount == 0.0
    assert len(report.contradiction_summary) == 0
    assert "No immediate action required" in report.recommended_actions[0]
