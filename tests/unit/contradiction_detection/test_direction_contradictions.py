"""Unit tests for Direction Contradiction detection in VERITY."""

import pytest
from backend.contradiction_detection.detector import ContradictionDetector
from backend.domain.claim import Claim, ClaimType
from backend.domain.discrepancy import DiscrepancySeverity, DiscrepancyType
from backend.domain.transaction import Transaction, TransactionDirection
from backend.transaction_matching.result import MatchRelationship, MatchRelationshipType, MatchStatus


@pytest.fixture
def detector() -> ContradictionDetector:
    return ContradictionDetector()


def test_direction_mismatch_detected(detector: ContradictionDetector) -> None:
    """Expected credit inflow for issued invoice, but debit observed on bank statement -> DIRECTION_MISMATCH."""
    claim = Claim(
        id="CLM-01",
        evidence_id="EVID-01",
        claim_type=ClaimType.INVOICE_ISSUED,
        claimed_amount=10000.0,
        reference_id_hint="408219381920",
    )
    txn = Transaction(
        id="TXN-01",
        amount=10000.0,
        direction=TransactionDirection.DEBIT,
        bank_reference="408219381920",
        evidence_ids=["EVID-BANK-01"],
    )
    match_rel = MatchRelationship(
        id="MAT-01",
        relationship_type=MatchRelationshipType.ONE_TO_ONE,
        status=MatchStatus.CONFLICTING,
        source_claim_ids=["CLM-01"],
        target_transaction_ids=["TXN-01"],
        matched_amount=10000.0,
        target_amount=10000.0,
        score=0.50,
        explanation="Direction mismatch",
    )

    result = detector.detect(
        claims=[claim],
        transactions=[txn],
        match_relationships=[match_rel],
    )
    assert len(result.discrepancies) == 1
    disc = result.discrepancies[0]
    assert disc.discrepancy_type == DiscrepancyType.DIRECTION_MISMATCH
    assert disc.severity == DiscrepancySeverity.CRITICAL
