"""Unit tests for Entity Contradiction detection in VERITY."""

import pytest
from backend.contradiction_detection.detector import ContradictionDetector
from backend.domain.claim import Claim, ClaimType
from backend.domain.discrepancy import DiscrepancySeverity, DiscrepancyType
from backend.domain.transaction import Transaction, TransactionDirection


@pytest.fixture
def detector() -> ContradictionDetector:
    return ContradictionDetector()


def test_entity_mismatch_detected(detector: ContradictionDetector) -> None:
    """Claim for Rahul Kumar (ENT-RAHUL) vs Bank transaction for Rohit Sharma (ENT-ROHIT) -> ENTITY_MISMATCH."""
    claim = Claim(
        id="CLM-01",
        evidence_id="EVID-01",
        claim_type=ClaimType.INVOICE_ISSUED,
        claimed_amount=25000.0,
        reference_id_hint="408219381920",
        counterparty_hint="Rahul Kumar",
    )
    txn = Transaction(
        id="TXN-01",
        amount=25000.0,
        direction=TransactionDirection.CREDIT,
        bank_reference="408219381920",
        origin_entity_id="ENT-ROHIT",
        evidence_ids=["EVID-BANK-01"],
    )

    result = detector.detect(
        claims=[claim],
        transactions=[txn],
        claim_entity_map={"CLM-01": "ENT-RAHUL"},
    )
    assert len(result.discrepancies) == 1
    disc = result.discrepancies[0]
    assert disc.discrepancy_type == DiscrepancyType.ENTITY_MISMATCH
    assert disc.severity == DiscrepancySeverity.CRITICAL
    assert disc.expected_value == "ENT-RAHUL"
    assert disc.observed_value == "ENT-ROHIT"
