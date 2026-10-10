"""Unit tests for Reference Contradiction detection in VERITY."""

import pytest
from backend.contradiction_detection.detector import ContradictionDetector
from backend.domain.claim import Claim, ClaimType
from backend.domain.discrepancy import DiscrepancySeverity, DiscrepancyType
from backend.domain.transaction import Transaction, TransactionDirection


@pytest.fixture
def detector() -> ContradictionDetector:
    return ContradictionDetector()


def test_reference_mismatch_detected(detector: ContradictionDetector) -> None:
    """Bank UTR 408219381920 vs Screenshot UTR 999888777666 -> REFERENCE_MISMATCH."""
    claim = Claim(
        id="CLM-01",
        evidence_id="EVID-01",
        claim_type=ClaimType.PAYMENT_SENT,
        claimed_amount=20000.0,
        reference_id_hint="999888777666",
    )
    txn = Transaction(
        id="TXN-01",
        amount=20000.0,
        direction=TransactionDirection.CREDIT,
        bank_reference="408219381920",
        origin_entity_id="ENT-001",
        evidence_ids=["EVID-BANK-01"],
    )

    result = detector.detect(
        claims=[claim],
        transactions=[txn],
        claim_entity_map={"CLM-01": "ENT-001"},
    )
    assert len(result.discrepancies) == 1
    disc = result.discrepancies[0]
    assert disc.discrepancy_type == DiscrepancyType.REFERENCE_MISMATCH
    assert disc.severity == DiscrepancySeverity.ERROR
    assert disc.expected_value == "999888777666"
    assert disc.observed_value == "408219381920"


def test_formatted_references_do_not_produce_contradiction(detector: ContradictionDetector) -> None:
    """UTR-408-219-381920 vs 408219381920 normalize without discrepancy."""
    claim = Claim(
        id="CLM-02",
        evidence_id="EVID-02",
        claim_type=ClaimType.PAYMENT_SENT,
        claimed_amount=20000.0,
        reference_id_hint="UTR-408-219-381920",
    )
    txn = Transaction(
        id="TXN-02",
        amount=20000.0,
        direction=TransactionDirection.CREDIT,
        bank_reference="408219381920",
    )

    result = detector.detect(claims=[claim], transactions=[txn])
    assert len(result.discrepancies) == 0
