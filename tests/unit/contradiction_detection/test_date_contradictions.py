"""Unit tests for Date Contradiction detection in VERITY."""

from datetime import datetime, timezone
import pytest
from backend.contradiction_detection.config import ContradictionConfig
from backend.contradiction_detection.detector import ContradictionDetector
from backend.domain.claim import Claim, ClaimType
from backend.domain.discrepancy import DiscrepancySeverity, DiscrepancyType
from backend.domain.transaction import Transaction, TransactionDirection


@pytest.fixture
def detector() -> ContradictionDetector:
    return ContradictionDetector(config=ContradictionConfig(max_acceptable_date_drift_days=30))


def test_extreme_date_drift_detected(detector: ContradictionDetector) -> None:
    """Invoice dated Aug 1 vs Settlement dated Sep 30 (60 days drift) -> DATE_MISMATCH."""
    claim = Claim(
        id="CLM-01",
        evidence_id="EVID-01",
        claim_type=ClaimType.INVOICE_ISSUED,
        claimed_amount=30000.0,
        claimed_date="2026-08-01",
        reference_id_hint="408219381920",
    )
    txn = Transaction(
        id="TXN-01",
        amount=30000.0,
        direction=TransactionDirection.CREDIT,
        bank_reference="408219381920",
        timestamp=datetime(2026, 9, 30, 10, 0, tzinfo=timezone.utc),
    )

    result = detector.detect(claims=[claim], transactions=[txn])
    assert len(result.discrepancies) == 1
    disc = result.discrepancies[0]
    assert disc.discrepancy_type == DiscrepancyType.DATE_MISMATCH
    assert disc.severity == DiscrepancySeverity.WARNING


def test_normal_date_delay_not_flagged(detector: ContradictionDetector) -> None:
    """Invoice dated Aug 20 vs Settlement dated Aug 22 (2 days delay) -> No discrepancy."""
    claim = Claim(
        id="CLM-02",
        evidence_id="EVID-02",
        claim_type=ClaimType.INVOICE_ISSUED,
        claimed_amount=15000.0,
        claimed_date="2026-08-20",
        reference_id_hint="408219381920",
    )
    txn = Transaction(
        id="TXN-02",
        amount=15000.0,
        direction=TransactionDirection.CREDIT,
        bank_reference="408219381920",
        timestamp=datetime(2026, 8, 22, 10, 0, tzinfo=timezone.utc),
    )

    result = detector.detect(claims=[claim], transactions=[txn])
    assert len(result.discrepancies) == 0
