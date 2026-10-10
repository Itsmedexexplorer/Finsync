"""Unit tests for Confirmed Financial Reconciliation in VERITY."""

import pytest
from backend.domain.claim import Claim, ClaimType
from backend.domain.reconciliation import ReconciliationStatus
from backend.domain.transaction import Transaction, TransactionDirection
from backend.reconciliation.engine import ReconciliationEngine
from backend.transaction_matching.result import MatchRelationship, MatchRelationshipType, MatchStatus


@pytest.fixture
def engine() -> ReconciliationEngine:
    return ReconciliationEngine()


def test_exact_1to1_confirmation(engine: ReconciliationEngine) -> None:
    """Exact invoice and bank transaction match with matching entity -> CONFIRMED."""
    claim = Claim(
        id="CLM-01",
        evidence_id="EVID-01",
        claim_type=ClaimType.INVOICE_ISSUED,
        claimed_amount=35000.0,
        reference_id_hint="408219381920",
        counterparty_hint="Rahul Kumar",
    )
    txn = Transaction(
        id="TXN-01",
        amount=35000.0,
        direction=TransactionDirection.CREDIT,
        bank_reference="408219381920",
        origin_entity_id="ENT-001",
        evidence_ids=["EVID-01-BANK"],
    )
    match_rel = MatchRelationship(
        id="MAT-01",
        relationship_type=MatchRelationshipType.ONE_TO_ONE,
        status=MatchStatus.MATCHED,
        source_claim_ids=["CLM-01"],
        target_transaction_ids=["TXN-01"],
        matched_amount=35000.0,
        target_amount=35000.0,
        score=1.0,
        matched_signals=["EXACT_REFERENCE", "EXACT_AMOUNT_MATCH", "EXACT_ENTITY_MATCH"],
        explanation="Exact match",
        entity_id="ENT-001",
    )

    result = engine.reconcile(
        claims=[claim],
        transactions=[txn],
        match_relationships=[match_rel],
        claim_entity_map={"CLM-01": "ENT-001"},
    )
    assert len(result.results) == 1
    res = result.results[0]
    assert res.status == ReconciliationStatus.CONFIRMED
    assert res.matched_amount == 35000.0
    assert res.outstanding_amount == 0.0
    assert res.confidence_score >= 0.95
