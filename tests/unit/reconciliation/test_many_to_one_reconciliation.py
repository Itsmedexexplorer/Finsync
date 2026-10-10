"""Unit tests for Many-to-One Financial Reconciliation."""

import pytest
from backend.domain.claim import Claim, ClaimType
from backend.domain.reconciliation import ReconciliationStatus
from backend.domain.transaction import Transaction, TransactionDirection
from backend.reconciliation.engine import ReconciliationEngine
from backend.transaction_matching.result import MatchRelationship, MatchRelationshipType, MatchStatus


@pytest.fixture
def engine() -> ReconciliationEngine:
    return ReconciliationEngine()


def test_many_to_one_milestone_payments_reconciliation(engine: ReconciliationEngine) -> None:
    """₹20,000 invoice settled by milestone payments (₹10k + ₹5k + ₹5k) -> CONFIRMED (Matched: ₹20k, Out: ₹0)."""
    claim = Claim(
        id="CLM-01",
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
    match_rel = MatchRelationship(
        id="MAT-M2O",
        relationship_type=MatchRelationshipType.MANY_TO_ONE,
        status=MatchStatus.MATCHED,
        source_claim_ids=["CLM-01"],
        target_transaction_ids=["T1", "T2", "T3"],
        matched_amount=20000.0,
        target_amount=20000.0,
        score=0.95,
        matched_signals=["SUM_AMOUNT_MATCH", "3_ITEMS_SUM"],
        explanation="Many to one sum match",
        entity_id="ENT-BHARAT",
    )

    result = engine.reconcile(
        claims=[claim],
        transactions=txns,
        match_relationships=[match_rel],
        claim_entity_map={"CLM-01": "ENT-BHARAT"},
    )
    assert len(result.results) == 1
    res = result.results[0]
    assert res.status == ReconciliationStatus.CONFIRMED
    assert res.matched_amount == 20000.0
    assert res.outstanding_amount == 0.0
