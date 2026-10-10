"""Unit tests for ReconciliationService API and backward compatibility."""

import pytest
from backend.domain.claim import Claim, ClaimType
from backend.domain.entity import Entity, EntityType
from backend.domain.evidence import Evidence, EvidenceModality, EvidenceSourceType
from backend.domain.reconciliation import ReconciliationStatus
from backend.domain.transaction import Transaction, TransactionDirection
from backend.reconciliation.service import ReconciliationService


@pytest.fixture
def service() -> ReconciliationService:
    return ReconciliationService()


def test_reconciliation_service_reconcile_all(service: ReconciliationService) -> None:
    claim = Claim(id="C1", evidence_id="E1", claim_type=ClaimType.INVOICE_ISSUED, claimed_amount=25000.0, reference_id_hint="REF-001")
    txn = Transaction(id="T1", amount=25000.0, direction=TransactionDirection.CREDIT, bank_reference="REF-001")

    batch = service.reconcile_all(claims=[claim], transactions=[txn])
    assert len(batch.results) == 1
    assert batch.results[0].status == ReconciliationStatus.CONFIRMED
    assert batch.total_reconciled_amount == 25000.0


def test_reconciliation_service_backward_compatibility_reconcile_case(service: ReconciliationService) -> None:
    ev = Evidence(id="E-BC", modality=EvidenceModality.BANK_STATEMENT, source_type=EvidenceSourceType.BANK_CSV, source_name="s.csv", raw_payload="row1")
    claim = Claim(id="C-BC", evidence_id="E-BC", claim_type=ClaimType.INVOICE_ISSUED, claimed_amount=30000.0)
    txn = Transaction(id="T-BC", amount=30000.0, direction=TransactionDirection.CREDIT, evidence_ids=["E-BC"])
    counterparty = Entity(id="ENT-001", canonical_name="Rahul Kumar", entity_type=EntityType.INDIVIDUAL)

    rec_record = service.reconcile_case(
        reconciliation_id="REC-LEGACY-001",
        evidence_items=[ev],
        claims=[claim],
        transactions=[txn],
        counterparty=counterparty,
    )
    assert rec_record.id == "REC-LEGACY-001"
    assert rec_record.status == ReconciliationStatus.CONFIRMED
    assert rec_record.reconciled_amount == 30000.0
    assert rec_record.outstanding_amount == 0.0
