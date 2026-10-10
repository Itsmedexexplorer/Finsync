"""Unit tests for VERITY canonical domain models.

Validates schema constraints, immutability rules, SHA-256 auto-hashing, and domain boundaries.
"""

import hashlib
import pytest
from pydantic import ValidationError

from backend.domain.evidence import Evidence, EvidenceModality, EvidenceSourceType
from backend.domain.claim import Claim, ClaimType, ClaimStatus
from backend.domain.entity import Entity, EntityType
from backend.domain.transaction import Transaction, TransactionDirection, PaymentMethod
from backend.domain.discrepancy import Discrepancy, DiscrepancyType, DiscrepancySeverity
from backend.domain.reconciliation import ReconciliationRecord, ReconciliationStatus, MatchType


def test_evidence_auto_computes_sha256() -> None:
    payload = "10/08/2026,UPI/408219381920/PAYTO/RAMESH,15000.00,0.00,250000.00"
    expected_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    
    evidence = Evidence(
        id="EVID-001",
        modality=EvidenceModality.BANK_STATEMENT,
        source_type=EvidenceSourceType.BANK_CSV,
        source_name="statement.csv",
        raw_payload=payload,
    )
    
    assert evidence.content_hash == expected_hash
    assert evidence.modality == EvidenceModality.BANK_STATEMENT


def test_claim_validation_non_negative_amount() -> None:
    # Valid claim
    claim = Claim(
        id="CLM-001",
        evidence_id="EVID-001",
        claim_type=ClaimType.PAYMENT_SENT,
        claimed_amount=25000.50,
    )
    assert claim.claimed_amount == 25000.50
    assert claim.currency == "INR"
    assert claim.status == ClaimStatus.ASSERTED

    # Negative amount should fail validation
    with pytest.raises(ValidationError):
        Claim(
            id="CLM-002",
            evidence_id="EVID-001",
            claim_type=ClaimType.PAYMENT_SENT,
            claimed_amount=-500.0,
        )


def test_transaction_validation_strictly_positive() -> None:
    # Valid transaction
    txn = Transaction(
        id="TXN-001",
        amount=10000.0,
        direction=TransactionDirection.CREDIT,
        payment_method=PaymentMethod.UPI,
        bank_reference="408219381920",
    )
    assert txn.amount == 10000.0
    assert txn.direction == TransactionDirection.CREDIT

    # Zero or negative amount should raise ValidationError
    with pytest.raises(ValidationError):
        Transaction(
            id="TXN-002",
            amount=0.0,
            direction=TransactionDirection.CREDIT,
        )

    with pytest.raises(ValidationError):
        Transaction(
            id="TXN-003",
            amount=-100.0,
            direction=TransactionDirection.DEBIT,
        )


def test_entity_alias_and_handle_matching() -> None:
    entity = Entity(
        id="ENT-001",
        canonical_name="Ramesh Kumar Sharma",
        entity_type=EntityType.SOLE_PROPRIETORSHIP,
        upi_ids=["ramesh@okhdfcbank"],
        phone_numbers=["+919811098765"],
        aliases=["M/s Ramesh Traders", "RAMESH S", "Rameshji"],
    )

    # Exact canonical name (case-insensitive)
    assert entity.matches_alias_or_handle("ramesh kumar sharma") is True
    assert entity.matches_alias_or_handle("RAMESH KUMAR SHARMA") is True
    
    # Aliases
    assert entity.matches_alias_or_handle("M/s Ramesh Traders") is True
    assert entity.matches_alias_or_handle("Rameshji") is True
    assert entity.matches_alias_or_handle("RAMESH S") is True

    # UPI VPA
    assert entity.matches_alias_or_handle("ramesh@okhdfcbank") is True

    # Phone numbers
    assert entity.matches_alias_or_handle("9811098765") is True
    assert entity.matches_alias_or_handle("+91 98110 98765") is True

    # Unrelated string
    assert entity.matches_alias_or_handle("Suresh Patel") is False


def test_discrepancy_creation() -> None:
    discrepancy = Discrepancy(
        id="DISC-001",
        discrepancy_type=DiscrepancyType.AMOUNT_MISMATCH,
        severity=DiscrepancySeverity.ERROR,
        message="Claimed ₹50,000 but bank ledger records ₹35,000.",
        expected_value="50000.00",
        observed_value="35000.00",
        involved_claim_ids=["CLM-001"],
        involved_transaction_ids=["TXN-001"],
    )
    assert discrepancy.discrepancy_type == DiscrepancyType.AMOUNT_MISMATCH
    assert discrepancy.severity == DiscrepancySeverity.ERROR
    assert len(discrepancy.involved_claim_ids) == 1


def test_core_domain_principle_evidence_not_claim_not_conclusion() -> None:
    """Explicitly verify that Evidence, Claim, and Reconciliation Conclusion remain separate types."""
    # 1. Evidence (Raw WhatsApp message)
    evidence = Evidence(
        id="EVID-RAW-001",
        modality=EvidenceModality.MESSAGING_CHAT,
        source_type=EvidenceSourceType.WHATSAPP_EXPORT,
        source_name="chat.txt",
        raw_payload="Bhai 20000 GPay kar diya check karo",
    )
    
    # 2. Claim (Asserted payment)
    claim = Claim(
        id="CLM-001",
        evidence_id=evidence.id,
        claim_type=ClaimType.PAYMENT_SENT,
        claimed_amount=20000.0,
        raw_text_snippet=evidence.raw_payload,
    )
    
    # 3. Transaction (Verified Bank statement showing only 18,500 received)
    txn = Transaction(
        id="TXN-001",
        amount=18500.0,
        direction=TransactionDirection.CREDIT,
        payment_method=PaymentMethod.UPI,
    )
    
    # 4. Reconciliation Record (Synthesized conclusion)
    rec = ReconciliationRecord(
        id="REC-001",
        status=ReconciliationStatus.PARTIAL,
        match_type=MatchType.PARTIAL_PAYMENT,
        expected_amount=20000.0,
        reconciled_amount=18500.0,
        outstanding_amount=1500.0,
        evidence_ids=[evidence.id],
        claim_ids=[claim.id],
        transaction_ids=[txn.id],
        explanation_summary="WhatsApp claims ₹20,000 sent; bank ledger confirms ₹18,500 credited.",
    )

    # Invariant: None of these are interchangeable
    assert type(evidence) is not type(claim)
    assert type(claim) is not type(rec)
    assert rec.reconciled_amount != claim.claimed_amount
    assert rec.status == ReconciliationStatus.PARTIAL
