"""Unit tests verifying strict prevention of false contradictions."""

import pytest
from backend.contradiction_detection.detector import ContradictionDetector
from backend.domain.claim import Claim, ClaimType
from backend.domain.transaction import Transaction, TransactionDirection
from backend.transaction_matching.result import MatchRelationship, MatchRelationshipType, MatchStatus


@pytest.fixture
def detector() -> ContradictionDetector:
    return ContradictionDetector()


def test_missing_amount_does_not_produce_contradiction(detector: ContradictionDetector) -> None:
    """A claim without stated amount ('I sent the money') paired with bank ₹20,000 does NOT trigger amount mismatch."""
    claim = Claim(
        id="CLM-01",
        evidence_id="EVID-01",
        claim_type=ClaimType.PAYMENT_SENT,
        claimed_amount=None,
        reference_id_hint="408219381920",
    )
    txn = Transaction(
        id="TXN-01",
        amount=20000.0,
        direction=TransactionDirection.CREDIT,
        bank_reference="408219381920",
    )

    result = detector.detect(claims=[claim], transactions=[txn])
    assert len(result.discrepancies) == 0


def test_unrelated_distinct_events_produce_no_false_contradiction(detector: ContradictionDetector) -> None:
    """Two different clients billed ₹20,000 each on same day do not produce false contradictions."""
    c1 = Claim(id="C1", evidence_id="E1", claim_type=ClaimType.INVOICE_ISSUED, claimed_amount=20000.0, counterparty_hint="Client A")
    c2 = Claim(id="C2", evidence_id="E2", claim_type=ClaimType.INVOICE_ISSUED, claimed_amount=20000.0, counterparty_hint="Client B")

    t1 = Transaction(id="T1", amount=20000.0, direction=TransactionDirection.CREDIT, origin_entity_id="ENT-A")
    t2 = Transaction(id="T2", amount=20000.0, direction=TransactionDirection.CREDIT, origin_entity_id="ENT-B")

    result = detector.detect(
        claims=[c1, c2],
        transactions=[t1, t2],
        claim_entity_map={"C1": "ENT-A", "C2": "ENT-B"},
    )
    assert len(result.discrepancies) == 0
