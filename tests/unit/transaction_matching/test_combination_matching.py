"""Unit tests for Combination Matching (Many-to-One and One-to-Many)."""

import pytest
from backend.domain.claim import Claim, ClaimType
from backend.domain.transaction import Transaction, TransactionDirection
from backend.transaction_matching.engine import TransactionMatcher
from backend.transaction_matching.result import MatchRelationshipType, MatchStatus


@pytest.fixture
def matcher() -> TransactionMatcher:
    return TransactionMatcher()


def test_combination_many_to_one(matcher: TransactionMatcher) -> None:
    """3 partial transactions (₹10,000 + ₹5,000 + ₹5,000) sum up to 1 invoice of ₹20,000."""
    claim = Claim(
        id="CLM-INV-01",
        evidence_id="EVID-01",
        claim_type=ClaimType.INVOICE_ISSUED,
        claimed_amount=20000.0,
        counterparty_hint="Bharat Tech",
    )
    txns = [
        Transaction(id="T1", amount=10000.0, direction=TransactionDirection.CREDIT, origin_entity_id="ENT-BHARAT"),
        Transaction(id="T2", amount=5000.0, direction=TransactionDirection.CREDIT, origin_entity_id="ENT-BHARAT"),
        Transaction(id="T3", amount=5000.0, direction=TransactionDirection.CREDIT, origin_entity_id="ENT-BHARAT"),
    ]

    result = matcher.match(
        claims=[claim],
        transactions=txns,
        claim_entity_map={"CLM-INV-01": "ENT-BHARAT"},
    )
    assert len(result.relationships) == 1
    rel = result.relationships[0]
    assert rel.relationship_type == MatchRelationshipType.MANY_TO_ONE
    assert rel.status == MatchStatus.MATCHED
    assert rel.source_claim_ids == ["CLM-INV-01"]
    assert set(rel.target_transaction_ids) == {"T1", "T2", "T3"}
    assert rel.matched_amount == 20000.0


def test_combination_one_to_many(matcher: TransactionMatcher) -> None:
    """1 bulk transaction of ₹20,000 settles two invoices of ₹10,000 each."""
    claims = [
        Claim(id="C1", evidence_id="E1", claim_type=ClaimType.INVOICE_ISSUED, claimed_amount=10000.0),
        Claim(id="C2", evidence_id="E2", claim_type=ClaimType.INVOICE_ISSUED, claimed_amount=10000.0),
    ]
    txn = Transaction(
        id="TXN-BULK",
        amount=20000.0,
        direction=TransactionDirection.CREDIT,
        origin_entity_id="ENT-SHREE",
    )

    result = matcher.match(
        claims=claims,
        transactions=[txn],
        claim_entity_map={"C1": "ENT-SHREE", "C2": "ENT-SHREE"},
    )
    assert len(result.relationships) == 1
    rel = result.relationships[0]
    assert rel.relationship_type == MatchRelationshipType.ONE_TO_MANY
    assert rel.status == MatchStatus.MATCHED
    assert set(rel.source_claim_ids) == {"C1", "C2"}
    assert rel.target_transaction_ids == ["TXN-BULK"]
