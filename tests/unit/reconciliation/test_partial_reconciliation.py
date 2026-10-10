"""Unit tests for Partial Financial Reconciliation in VERITY."""

import pytest
from backend.domain.claim import Claim, ClaimType
from backend.domain.reconciliation import ReconciliationStatus
from backend.domain.transaction import Transaction, TransactionDirection
from backend.reconciliation.engine import ReconciliationEngine
from backend.transaction_matching.result import MatchRelationship, MatchRelationshipType, MatchStatus


@pytest.fixture
def engine() -> ReconciliationEngine:
    return ReconciliationEngine()


def test_partial_settlement_calculates_outstanding_balance(engine: ReconciliationEngine) -> None:
    """₹20,000 invoice with partial payment of ₹12,000 -> PARTIALLY_SETTLED (Outstanding: ₹8,000)."""
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
        entity_id="ENT-PRIYA",
    )

    result = engine.reconcile(
        claims=[claim],
        transactions=[txn],
        match_relationships=[match_rel],
        claim_entity_map={"CLM-01": "ENT-PRIYA"},
    )
    assert len(result.results) == 1
    res = result.results[0]
    assert res.status in (ReconciliationStatus.PARTIAL, ReconciliationStatus.PARTIALLY_SETTLED)
    assert res.expected_amount == 20000.0
    assert res.matched_amount == 12000.0
    assert res.outstanding_amount == 8000.0
    # Monetary Invariant: matched + outstanding == expected
    assert res.matched_amount + res.outstanding_amount == res.expected_amount
