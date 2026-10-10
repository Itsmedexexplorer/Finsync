"""Unit tests verifying Multilingual equivalence in Contradiction Detection."""

import pytest
from backend.contradiction_detection.detector import ContradictionDetector
from backend.deduplication.result import DeduplicationGroup, DeduplicationStatus
from backend.domain.claim import Claim, ClaimType


@pytest.fixture
def detector() -> ContradictionDetector:
    return ContradictionDetector()


def test_multilingual_equivalent_claims_produce_no_contradiction(detector: ContradictionDetector) -> None:
    """Hinglish ('20k GPay kar diya') and English ('₹20,000 sent') normalized to ₹20,000 produce no contradiction."""
    c_hinglish = Claim(
        id="CLM-HI",
        evidence_id="EVID-HI",
        claim_type=ClaimType.PAYMENT_SENT,
        claimed_amount=20000.0,
    )
    c_english = Claim(
        id="CLM-EN",
        evidence_id="EVID-EN",
        claim_type=ClaimType.PAYMENT_SENT,
        claimed_amount=20000.0,
    )
    dedup_grp = DeduplicationGroup(
        group_id="GRP-MULTI",
        status=DeduplicationStatus.SAME_EVENT,
        member_evidence_ids=["EVID-HI", "EVID-EN"],
        member_claim_ids=["CLM-HI", "CLM-EN"],
        explanation="Multilingual equivalents",
    )

    result = detector.detect(
        claims=[c_hinglish, c_english],
        transactions=[],
        deduplication_groups=[dedup_grp],
    )
    assert len(result.discrepancies) == 0
