"""Unit tests for One-to-Many Financial Reconciliation."""

import pytest
from backend.domain.claim import Claim, ClaimType
from backend.domain.reconciliation import ReconciliationStatus
from backend.domain.transaction import Transaction, TransactionDirection
from backend.reconciliation.engine import ReconciliationEngine
from backend.transaction_matching.result import MatchRelationship, MatchRelationshipType, MatchStatus


@pytest.fixture
def engine() -> ReconciliationEngine:
    return ReconciliationEngine()


def test_one_to_many_bulk_payment_reconciliation(engine: ReconciliationEngine) -> None:
    """1 bulk transaction of ₹20,000 settles two invoices of ₹10,000 each -> CONFIRMED."""
    c1 = Claim(id="C1", evidence_id="E1", claim_type=ClaimType.INVOICE_ISSUED, claimed_amount=10000.0)
    c2 = Claim(id="C2", evidence_id="E2", claim_type=ClaimType.INVOICE_ISSUED, claimed_amount=10000.0)
    txn = Transaction(id="T-BULK", amount=20000.0, direction=TransactionDirection.CREDIT, origin_entity_id="ENT-SHREE")

    match_rel = MatchRelationship(
        id="MAT-12M",
        relationship_type=MatchRelationshipType.ONE_TO_MANY,
        status=MatchStatus.MATCHED,
        source_claim_ids=["C1", "C2"],
        target_transaction_ids=["T-BULK"],
        matched_amount=20000.0,
        target_amount=20000.0,
        score=0.95,
        matched_signals=["SUM_AMOUNT_MATCH", "2_ITEMS_SUM"],
        explanation="One to many bulk settlement",
        entity_id="ENT-SHREE",
    )

    result = engine.reconcile(
        claims=[c1, c2],
        transactions=[txn],
        match_relationships=[match_rel],
        claim_entity_map={"C1": "ENT-SHREE", "C2": "ENT-SHREE"},
    )
    assert len(result.results) == 1
    res = result.results[0]
    assert res.status == ReconciliationStatus.CONFIRMED
    assert res.matched_amount == 20000.0
    assert res.outstanding_amount == 0.0
