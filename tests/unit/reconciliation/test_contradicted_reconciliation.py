"""Unit tests verifying Contradiction Dominance in Reconciliation."""

import pytest
from backend.domain.claim import Claim, ClaimType
from backend.domain.discrepancy import Discrepancy, DiscrepancySeverity, DiscrepancyType
from backend.domain.reconciliation import ReconciliationStatus
from backend.domain.transaction import Transaction, TransactionDirection
from backend.reconciliation.engine import ReconciliationEngine
from backend.transaction_matching.result import MatchRelationship, MatchRelationshipType, MatchStatus


@pytest.fixture
def engine() -> ReconciliationEngine:
    return ReconciliationEngine()


def test_contradiction_dominance_overrides_high_match_score(engine: ReconciliationEngine) -> None:
    """Even if Day 5 match score is high (0.95), an explicit amount contradiction strictly forces CONTRADICTED."""
    claim = Claim(
        id="CLM-01",
        evidence_id="EVID-01",
        claim_type=ClaimType.INVOICE_ISSUED,
        claimed_amount=50000.0,
        reference_id_hint="408219381920",
    )
    txn = Transaction(
        id="TXN-01",
        amount=35000.0,
        direction=TransactionDirection.CREDIT,
        bank_reference="408219381920",
    )
    match_rel = MatchRelationship(
        id="MAT-01",
        relationship_type=MatchRelationshipType.ONE_TO_ONE,
        status=MatchStatus.MATCHED,
        source_claim_ids=["CLM-01"],
        target_transaction_ids=["TXN-01"],
        matched_amount=35000.0,
        target_amount=50000.0,
        score=0.95,
        explanation="Reference match",
    )
    disc = Discrepancy(
        id="DISC-01",
        discrepancy_type=DiscrepancyType.AMOUNT_MISMATCH,
        severity=DiscrepancySeverity.ERROR,
        message="Amount mismatch: 50k vs 35k",
    )

    result = engine.reconcile(
        claims=[claim],
        transactions=[txn],
        match_relationships=[match_rel],
        discrepancies=[disc],
    )
    assert len(result.results) == 1
    res = result.results[0]
    assert res.status == ReconciliationStatus.CONTRADICTED
    assert res.status != ReconciliationStatus.CONFIRMED
    assert "RULE_RECON_004" in res.explanation
