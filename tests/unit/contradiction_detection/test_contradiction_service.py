"""Unit tests for ContradictionDetectionService API and backward compatibility."""

import pytest
from backend.contradiction_detection.service import ContradictionDetectionService
from backend.domain.claim import Claim, ClaimType
from backend.domain.discrepancy import DiscrepancyType
from backend.domain.transaction import Transaction, TransactionDirection


@pytest.fixture
def service() -> ContradictionDetectionService:
    return ContradictionDetectionService()


def test_contradiction_service_detect_all(service: ContradictionDetectionService) -> None:
    claim = Claim(id="C1", evidence_id="E1", claim_type=ClaimType.INVOICE_ISSUED, claimed_amount=20000.0, reference_id_hint="REF-123")
    txn = Transaction(id="T1", amount=15000.0, direction=TransactionDirection.CREDIT, bank_reference="REF-123")

    result = service.detect_all(claims=[claim], transactions=[txn])
    assert result.total_contradictions == 1
    assert result.error_count == 1
    assert result.discrepancies[0].discrepancy_type == DiscrepancyType.AMOUNT_MISMATCH


def test_contradiction_service_backward_compatibility(service: ContradictionDetectionService) -> None:
    claim = Claim(id="C2", evidence_id="E2", claim_type=ClaimType.INVOICE_ISSUED, claimed_amount=20000.0, reference_id_hint="REF-ABC")
    txn = Transaction(id="T2", amount=10000.0, direction=TransactionDirection.CREDIT, bank_reference="REF-ABC")

    discs = service.detect_contradictions(claims=[claim], transactions=[txn])
    assert len(discs) == 1
    assert discs[0].discrepancy_type == DiscrepancyType.AMOUNT_MISMATCH
