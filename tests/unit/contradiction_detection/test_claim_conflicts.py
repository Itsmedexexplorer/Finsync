"""Unit tests for Conflicting Claims detection in VERITY."""

import pytest
from backend.contradiction_detection.detector import ContradictionDetector
from backend.deduplication.result import DeduplicationGroup, DeduplicationStatus
from backend.domain.claim import Claim, ClaimType
from backend.domain.discrepancy import DiscrepancySeverity, DiscrepancyType


@pytest.fixture
def detector() -> ContradictionDetector:
    return ContradictionDetector()


def test_conflicting_claims_in_same_event_detected(detector: ContradictionDetector) -> None:
    """Claim A asserts ₹20,000 sent while Claim B asserts ₹25,000 sent for same event -> CONFLICTING_CLAIMS."""
    c1 = Claim(id="C1", evidence_id="E1", claim_type=ClaimType.PAYMENT_SENT, claimed_amount=20000.0)
    c2 = Claim(id="C2", evidence_id="E2", claim_type=ClaimType.PAYMENT_SENT, claimed_amount=25000.0)

    dedup_grp = DeduplicationGroup(
        group_id="GRP-01",
        status=DeduplicationStatus.SAME_EVENT,
        member_evidence_ids=["E1", "E2"],
        member_claim_ids=["C1", "C2"],
        explanation="Grouped",
    )

    result = detector.detect(
        claims=[c1, c2],
        transactions=[],
        deduplication_groups=[dedup_grp],
    )
    assert len(result.discrepancies) == 1
    disc = result.discrepancies[0]
    assert disc.discrepancy_type == DiscrepancyType.CONFLICTING_CLAIMS
    assert disc.severity == DiscrepancySeverity.ERROR
    assert disc.expected_value == "20000.00"
    assert disc.observed_value == "25000.00"
