"""Unit tests for Partial Payment handling in Contradiction Detection."""

import pytest
from backend.contradiction_detection.detector import ContradictionDetector
from backend.domain.claim import Claim, ClaimType
from backend.domain.transaction import Transaction, TransactionDirection
from backend.transaction_matching.result import MatchRelationship, MatchRelationshipType, MatchStatus


@pytest.fixture
def detector() -> ContradictionDetector:
    return ContradictionDetector()


def test_partial_payment_does_not_trigger_amount_mismatch(detector: ContradictionDetector) -> None:
    """An invoice of ₹20,000 paired with partial payment of ₹12,000 via MatchRelationship(PARTIAL)
    must NOT be flagged as AMOUNT_MISMATCH."""
    claim = Claim(
        id="CLM-01",
        evidence_id="EVID-01",
        claim_type=ClaimType.INVOICE_ISSUED,
        claimed_amount=20000.0,
        counterparty_hint="Priya Patel",
    )
    txn = Transaction(
        id="TXN-01",
        amount=12000.0,
        direction=TransactionDirection.CREDIT,
        origin_entity_id="ENT-PRIYA",
    )
    match_rel = MatchRelationship(
        id="MAT-01",
        relationship_type=MatchRelationshipType.PARTIAL,
        status=MatchStatus.MATCHED,
        source_claim_ids=["CLM-01"],
        target_transaction_ids=["TXN-01"],
        matched_amount=12000.0,
        target_amount=20000.0,
        score=0.95,
        explanation="Partial payment",
    )

    result = detector.detect(
        claims=[claim],
        transactions=[txn],
        match_relationships=[match_rel],
        claim_entity_map={"CLM-01": "ENT-PRIYA"},
    )
    assert len(result.discrepancies) == 0
