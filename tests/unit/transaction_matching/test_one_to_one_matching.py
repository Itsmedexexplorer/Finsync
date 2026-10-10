"""Unit tests for 1-to-1 Transaction Matching."""

import pytest
from backend.domain.claim import Claim, ClaimType
from backend.domain.transaction import Transaction, TransactionDirection
from backend.transaction_matching.engine import TransactionMatcher
from backend.transaction_matching.result import MatchRelationshipType, MatchStatus


@pytest.fixture
def matcher() -> TransactionMatcher:
    return TransactionMatcher()


def test_one_to_one_exact_match(matcher: TransactionMatcher) -> None:
    claim = Claim(
        id="CLM-01",
        evidence_id="EVID-01",
        claim_type=ClaimType.INVOICE_ISSUED,
        claimed_amount=45000.0,
        claimed_date="2026-08-15",
        reference_id_hint="408219381920",
    )
    txn = Transaction(
        id="TXN-01",
        amount=45000.0,
        direction=TransactionDirection.CREDIT,
        bank_reference="408219381920",
    )

    result = matcher.match(claims=[claim], transactions=[txn])
    assert len(result.relationships) == 1
    rel = result.relationships[0]
    assert rel.relationship_type == MatchRelationshipType.ONE_TO_ONE
    assert rel.status == MatchStatus.MATCHED
    assert rel.source_claim_ids == ["CLM-01"]
    assert rel.target_transaction_ids == ["TXN-01"]
    assert rel.matched_amount == 45000.0


def test_one_to_one_formatted_reference_match(matcher: TransactionMatcher) -> None:
    claim = Claim(
        id="CLM-02",
        evidence_id="EVID-02",
        claim_type=ClaimType.INVOICE_ISSUED,
        claimed_amount=12000.0,
        reference_id_hint="UTR-408-219-381921",
    )
    txn = Transaction(
        id="TXN-02",
        amount=12000.0,
        direction=TransactionDirection.CREDIT,
        bank_reference="408219381921",
    )

    result = matcher.match(claims=[claim], transactions=[txn])
    assert len(result.relationships) == 1
    assert result.relationships[0].status == MatchStatus.MATCHED
