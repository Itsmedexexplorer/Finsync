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


def test_unrelated_transactions_are_not_summed_into_a_claim(matcher: TransactionMatcher) -> None:
    """A ₹35,000 credit from someone else plus a ₹5,000 ATM withdrawal must not 'settle' a ₹40,000 claim."""
    claim = Claim(
        id="CLM-ANANYA",
        evidence_id="EVID-CHAT",
        claim_type=ClaimType.PAYMENT_SENT,
        claimed_amount=40000.0,
        counterparty_hint="Ananya Rao",
    )
    credit = Transaction(id="TXN-R", amount=35000.0, direction=TransactionDirection.CREDIT,
                         bank_reference="512309871234", narration="UPI/512309871234/RAMESH SHARMA/HDFC")
    atm = Transaction(id="TXN-ATM", amount=5000.0, direction=TransactionDirection.DEBIT,
                      bank_reference="ATM0098812", narration="ATM/WDL/KORAMANGALA/CASH")

    result = matcher.match(claims=[claim], transactions=[credit, atm])
    assert all(r.relationship_type != MatchRelationshipType.MANY_TO_ONE for r in result.relationships)


def test_smaller_credit_from_someone_else_is_not_a_partial_payment(matcher: TransactionMatcher) -> None:
    claim = Claim(id="CLM-ANANYA", evidence_id="EVID-CHAT", claim_type=ClaimType.PAYMENT_SENT,
                  claimed_amount=40000.0, counterparty_hint="Ananya Rao")
    credit = Transaction(id="TXN-R", amount=35000.0, direction=TransactionDirection.CREDIT,
                         bank_reference="512309871234", narration="UPI/512309871234/RAMESH SHARMA/HDFC")

    result = matcher.match(claims=[claim], transactions=[credit])
    assert result.relationships == [] or all(r.relationship_type != MatchRelationshipType.PARTIAL for r in result.relationships)
