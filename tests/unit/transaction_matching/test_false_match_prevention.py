"""Unit tests verifying strict False Match Prevention in Transaction Matching."""

import pytest
from backend.domain.claim import Claim, ClaimType
from backend.domain.transaction import Transaction, TransactionDirection
from backend.transaction_matching.engine import TransactionMatcher
from backend.transaction_matching.result import MatchStatus


@pytest.fixture
def matcher() -> TransactionMatcher:
    return TransactionMatcher()


def test_false_match_prevented_across_unrelated_equal_amount_invoices(matcher: TransactionMatcher) -> None:
    """Two different clients both billed ₹20,000 with a single unreferenced ₹20,000 payment.
    The matcher MUST NOT arbitrarily match to Client A."""
    claims = [
        Claim(id="CLM-A", evidence_id="E1", claim_type=ClaimType.INVOICE_ISSUED, claimed_amount=20000.0, counterparty_hint="Client Alpha"),
        Claim(id="CLM-B", evidence_id="E2", claim_type=ClaimType.INVOICE_ISSUED, claimed_amount=20000.0, counterparty_hint="Client Beta"),
    ]
    txn = Transaction(
        id="TXN-UNREF",
        amount=20000.0,
        direction=TransactionDirection.CREDIT,
        # No reference, no resolved entity
    )

    result = matcher.match(claims=claims, transactions=[txn])
    assert len(result.relationships) == 1
    rel = result.relationships[0]
    # Must be AMBIGUOUS, NOT MATCHED!
    assert rel.status == MatchStatus.AMBIGUOUS
    assert set(rel.source_claim_ids) == {"CLM-A", "CLM-B"}


def test_unmatched_records_tracked_cleanly(matcher: TransactionMatcher) -> None:
    """A payment with no corresponding invoice must be safely reported in unmatched_transaction_ids."""
    txn_lone = Transaction(
        id="TXN-LONE",
        amount=99999.0,
        direction=TransactionDirection.CREDIT,
    )

    result = matcher.match(claims=[], transactions=[txn_lone])
    assert len(result.relationships) == 0
    assert result.unmatched_transaction_ids == ["TXN-LONE"]
