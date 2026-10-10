"""Unit tests for Unmatched Transactions in Reconciliation."""

import pytest
from backend.domain.reconciliation import ReconciliationStatus
from backend.domain.transaction import Transaction, TransactionDirection
from backend.reconciliation.engine import ReconciliationEngine


@pytest.fixture
def engine() -> ReconciliationEngine:
    return ReconciliationEngine()


def test_standalone_transaction_reconciles_as_unmatched(engine: ReconciliationEngine) -> None:
    """A bank credit of ₹35,000 with no corresponding obligation -> UNMATCHED."""
    txn = Transaction(
        id="TXN-01",
        amount=35000.0,
        direction=TransactionDirection.CREDIT,
        bank_reference="408219381920",
        evidence_ids=["EVID-01-BANK"],
    )

    result = engine.reconcile(claims=[], transactions=[txn])
    assert len(result.results) == 1
    res = result.results[0]
    assert res.status == ReconciliationStatus.UNMATCHED
    assert res.matched_amount == 35000.0
    assert res.outstanding_amount == 0.0
