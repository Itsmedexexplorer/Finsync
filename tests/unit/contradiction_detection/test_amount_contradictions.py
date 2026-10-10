"""Unit tests for Amount Contradiction detection in VERITY."""

import pytest
from backend.contradiction_detection.detector import ContradictionDetector
from backend.domain.claim import Claim, ClaimType
from backend.domain.discrepancy import DiscrepancySeverity, DiscrepancyType
from backend.domain.transaction import Transaction, TransactionDirection


@pytest.fixture
def detector() -> ContradictionDetector:
    return ContradictionDetector()


def test_amount_mismatch_detected(detector: ContradictionDetector) -> None:
    """Invoice of ₹20,000 paired with bank settlement of ₹18,000 without partial context -> AMOUNT_MISMATCH."""
    claim = Claim(
        id="CLM-01",
        evidence_id="EVID-01",
        claim_type=ClaimType.INVOICE_ISSUED,
        claimed_amount=20000.0,
        reference_id_hint="408219381920",
    )
    txn = Transaction(
        id="TXN-01",
        amount=18000.0,
        direction=TransactionDirection.CREDIT,
        bank_reference="408219381920",
        evidence_ids=["EVID-BANK-01"],
    )

    result = detector.detect(claims=[claim], transactions=[txn])
    assert len(result.discrepancies) == 1
    disc = result.discrepancies[0]
    assert disc.discrepancy_type == DiscrepancyType.AMOUNT_MISMATCH
    assert disc.severity == DiscrepancySeverity.ERROR
    assert disc.expected_value == "20000.00"
    assert disc.observed_value == "18000.00"
    assert "EVID-01" in disc.involved_evidence_ids


def test_equal_amounts_produce_no_contradiction(detector: ContradictionDetector) -> None:
    """Equal amounts ₹20,000 on both sides produce no amount contradiction."""
    claim = Claim(
        id="CLM-02",
        evidence_id="EVID-02",
        claim_type=ClaimType.INVOICE_ISSUED,
        claimed_amount=20000.0,
        reference_id_hint="408219381920",
    )
    txn = Transaction(
        id="TXN-02",
        amount=20000.0,
        direction=TransactionDirection.CREDIT,
        bank_reference="408219381920",
    )

    result = detector.detect(claims=[claim], transactions=[txn])
    assert len(result.discrepancies) == 0
