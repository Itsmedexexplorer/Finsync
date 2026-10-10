"""Unit tests verifying Ambiguity Preservation in Reconciliation."""

import pytest
from backend.domain.claim import Claim, ClaimType
from backend.domain.reconciliation import ReconciliationStatus
from backend.domain.transaction import Transaction, TransactionDirection
from backend.reconciliation.engine import ReconciliationEngine
from backend.transaction_matching.result import MatchRelationship, MatchRelationshipType, MatchStatus


@pytest.fixture
def engine() -> ReconciliationEngine:
    return ReconciliationEngine()


def test_ambiguity_preserved_without_arbitrary_choice(engine: ReconciliationEngine) -> None:
    """When two identical payments exist for one invoice, status is strictly AMBIGUOUS."""
    claim = Claim(id="C1", evidence_id="E1", claim_type=ClaimType.INVOICE_ISSUED, claimed_amount=20000.0)
    txns = [
        Transaction(id="T1", amount=20000.0, direction=TransactionDirection.CREDIT),
        Transaction(id="T2", amount=20000.0, direction=TransactionDirection.CREDIT),
    ]
    match_rel = MatchRelationship(
        id="MAT-AMB",
        relationship_type=MatchRelationshipType.ONE_TO_ONE,
        status=MatchStatus.AMBIGUOUS,
        source_claim_ids=["C1"],
        target_transaction_ids=["T1", "T2"],
        matched_amount=20000.0,
        target_amount=20000.0,
        score=0.85,
        explanation="Ambiguous match",
    )

    result = engine.reconcile(
        claims=[claim],
        transactions=txns,
        match_relationships=[match_rel],
    )
    assert len(result.results) == 1
    res = result.results[0]
    assert res.status == ReconciliationStatus.AMBIGUOUS
    assert res.status != ReconciliationStatus.CONFIRMED
