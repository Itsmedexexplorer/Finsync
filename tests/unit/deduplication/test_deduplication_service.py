"""Unit tests for DeduplicationService API and backward compatibility."""

import pytest
from backend.deduplication.result import DeduplicationStatus
from backend.deduplication.service import DeduplicationService
from backend.domain.claim import Claim, ClaimType
from backend.domain.evidence import Evidence, EvidenceModality, EvidenceSourceType
from backend.domain.transaction import Transaction, TransactionDirection


@pytest.fixture
def service() -> DeduplicationService:
    return DeduplicationService()


def test_deduplication_service_deduplicate_records(service: DeduplicationService) -> None:
    ev1 = Evidence(id="E1", modality=EvidenceModality.PAYMENT_SCREENSHOT, source_type=EvidenceSourceType.MANUAL_UPLOAD, source_name="s.png", raw_payload="same", content_hash="hash_same")
    ev2 = Evidence(id="E2", modality=EvidenceModality.PAYMENT_SCREENSHOT, source_type=EvidenceSourceType.MANUAL_UPLOAD, source_name="s_copy.png", raw_payload="same", content_hash="hash_same")

    result = service.deduplicate_records(evidence_items=[ev1, ev2])
    assert result.content_duplicate_count == 1
    assert result.groups[0].status == DeduplicationStatus.DUPLICATE_EVIDENCE_CONTENT


def test_deduplication_service_backward_compatibility_find_duplicates(service: DeduplicationService) -> None:
    ev_bank = Evidence(id="E-B", modality=EvidenceModality.BANK_STATEMENT, source_type=EvidenceSourceType.BANK_CSV, source_name="s.csv", raw_payload="15/08/2026,UPI/408219381920/PAYTO/RAHUL,35000.00")
    ev_ss = Evidence(id="E-S", modality=EvidenceModality.PAYMENT_SCREENSHOT, source_type=EvidenceSourceType.MANUAL_UPLOAD, source_name="ss.png", raw_payload="Payment of Rs 35,000 successful Ref 408219381920")

    claims = [
        Claim(id="C-B", evidence_id="E-B", claim_type=ClaimType.PAYMENT_RECEIVED, claimed_amount=35000.0, reference_id_hint="408219381920"),
        Claim(id="C-S", evidence_id="E-S", claim_type=ClaimType.PAYMENT_SENT, claimed_amount=35000.0, reference_id_hint="408219381920"),
    ]
    txns = [
        Transaction(id="T-B", amount=35000.0, direction=TransactionDirection.CREDIT, bank_reference="408219381920", evidence_ids=["E-B"]),
    ]

    dup_groups = service.find_duplicates(
        evidence_items=[ev_bank, ev_ss],
        claims=claims,
        transactions=txns,
    )

    assert len(dup_groups) >= 1
    assert dup_groups[0].canonical_reference == "REF:408219381920"
    assert dup_groups[0].confidence == 1.0
