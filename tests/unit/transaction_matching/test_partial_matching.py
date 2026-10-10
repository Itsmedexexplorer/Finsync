"""Unit tests for Partial Payment matching relationships."""

import pytest
from backend.domain.claim import Claim, ClaimType
from backend.domain.transaction import Transaction, TransactionDirection
from backend.transaction_matching.engine import TransactionMatcher
from backend.transaction_matching.result import MatchRelationshipType, MatchStatus


@pytest.fixture
def matcher() -> TransactionMatcher:
    return TransactionMatcher()


def test_partial_payment_relationship(matcher: TransactionMatcher) -> None:
    """Invoice of ₹20,000 paired with partial settlement of ₹12,000."""
    claim = Claim(
        id="CLM-PARTIAL-01",
        evidence_id="EVID-01",
        claim_type=ClaimType.INVOICE_ISSUED,
        claimed_amount=20000.0,
        counterparty_hint="Priya Patel",
    )
    txn = Transaction(
        id="TXN-PARTIAL-01",
        amount=12000.0,
        direction=TransactionDirection.CREDIT,
        origin_entity_id="ENT-PRIYA",
    )

    result = matcher.match(
        claims=[claim],
        transactions=[txn],
        claim_entity_map={"CLM-PARTIAL-01": "ENT-PRIYA"},
    )
    assert len(result.relationships) == 1
    rel = result.relationships[0]
    assert rel.relationship_type == MatchRelationshipType.PARTIAL
    assert rel.matched_amount == 12000.0
    assert rel.target_amount == 20000.0
    # Crucial: Matching produces a RELATIONSHIP, does not declare final outstanding balance conclusion
    assert "Partial Payment" in rel.explanation
