"""Unit tests for Ambiguity and Conflict detection in Transaction Matching."""

import pytest
from backend.domain.claim import Claim, ClaimType
from backend.domain.transaction import Transaction, TransactionDirection
from backend.transaction_matching.engine import TransactionMatcher
from backend.transaction_matching.result import MatchStatus


@pytest.fixture
def matcher() -> TransactionMatcher:
    return TransactionMatcher()


def test_ambiguity_detected_for_multiple_equal_candidates(matcher: TransactionMatcher) -> None:
    """1 invoice of ₹25,000 matches two identical candidate payments -> AMBIGUOUS."""
    claim = Claim(
        id="CLM-AMB-01",
        evidence_id="EVID-01",
        claim_type=ClaimType.INVOICE_ISSUED,
        claimed_amount=25000.0,
    )
    txns = [
        Transaction(id="T-AMB-A", amount=25000.0, direction=TransactionDirection.CREDIT),
        Transaction(id="T-AMB-B", amount=25000.0, direction=TransactionDirection.CREDIT),
    ]

    result = matcher.match(claims=[claim], transactions=txns)
    assert len(result.relationships) == 1
    rel = result.relationships[0]
    assert rel.status == MatchStatus.AMBIGUOUS
    assert len(rel.target_transaction_ids) == 2
    assert "Ambiguous Match" in rel.explanation


def test_conflict_detected_for_different_entities(matcher: TransactionMatcher) -> None:
    """Invoice of ₹20,000 for Entity A vs Payment of ₹20,000 for Entity B -> CONFLICTING."""
    claim = Claim(
        id="CLM-CNF-01",
        evidence_id="EVID-01",
        claim_type=ClaimType.INVOICE_ISSUED,
        claimed_amount=20000.0,
    )
    txn = Transaction(
        id="TXN-CNF-01",
        amount=20000.0,
        direction=TransactionDirection.CREDIT,
        origin_entity_id="ENT-B",
    )

    result = matcher.match(
        claims=[claim],
        transactions=[txn],
        claim_entity_map={"CLM-CNF-01": "ENT-A"},
    )
    assert len(result.relationships) == 1
    rel = result.relationships[0]
    assert rel.status == MatchStatus.CONFLICTING
    assert "CONFLICTING_ENTITY" in rel.conflicting_signals
