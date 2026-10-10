"""Unit tests verifying strict prevention of false deduplication merges."""

import pytest
from backend.deduplication.engine import DeduplicationEngine
from backend.deduplication.result import DeduplicationStatus
from backend.domain.claim import Claim, ClaimType
from backend.domain.evidence import Evidence, EvidenceModality, EvidenceSourceType
from backend.domain.transaction import Transaction, TransactionDirection


@pytest.fixture
def engine() -> DeduplicationEngine:
    return DeduplicationEngine()


def test_distinct_events_different_entities_never_merged(engine: DeduplicationEngine) -> None:
    """A bank credit of ₹20,000 for Rahul Kumar and a screenshot of ₹20,000 for Rohit Sharma
    MUST NOT be merged into the same event group."""
    ev_bank = Evidence(
        id="EVID-RAHUL",
        modality=EvidenceModality.BANK_STATEMENT,
        source_type=EvidenceSourceType.BANK_CSV,
        source_name="stmt.csv",
        raw_payload="12/08/2026, 20k credit to Rahul",
    )
    ev_ss = Evidence(
        id="EVID-ROHIT",
        modality=EvidenceModality.PAYMENT_SCREENSHOT,
        source_type=EvidenceSourceType.MANUAL_UPLOAD,
        source_name="ss.png",
        raw_payload="Paid 20000 to Rohit Sharma",
    )

    claim_ss = Claim(
        id="CLM-ROHIT",
        evidence_id="EVID-ROHIT",
        claim_type=ClaimType.PAYMENT_SENT,
        claimed_amount=20000.0,
        claimed_date="2026-08-12",
        counterparty_hint="Rohit Sharma",
    )
    txn_bank = Transaction(
        id="TXN-RAHUL",
        amount=20000.0,
        direction=TransactionDirection.CREDIT,
        origin_entity_id="ENT-RAHUL",
        timestamp="2026-08-12T10:00:00Z",
        evidence_ids=["EVID-RAHUL"],
    )

    result = engine.deduplicate(
        evidence_items=[ev_bank, ev_ss],
        claims=[claim_ss],
        transactions=[txn_bank],
        claim_entity_map={"CLM-ROHIT": "ENT-ROHIT"},
    )

    # Must remain 2 separate distinct groups!
    assert len(result.groups) == 2
    for g in result.groups:
        assert g.status == DeduplicationStatus.DISTINCT_EVENT


def test_three_separate_installment_payments_remain_distinct(engine: DeduplicationEngine) -> None:
    """Three separate milestone payments (₹10k, ₹5k, ₹5k) MUST NOT be merged into one single payment event."""
    ev1 = Evidence(id="E1", modality=EvidenceModality.BANK_STATEMENT, source_type=EvidenceSourceType.BANK_CSV, source_name="s.csv:Row1", raw_payload="01/08/2026,10000 credit")
    ev2 = Evidence(id="E2", modality=EvidenceModality.BANK_STATEMENT, source_type=EvidenceSourceType.BANK_CSV, source_name="s.csv:Row2", raw_payload="05/08/2026,5000 credit")
    ev3 = Evidence(id="E3", modality=EvidenceModality.BANK_STATEMENT, source_type=EvidenceSourceType.BANK_CSV, source_name="s.csv:Row3", raw_payload="10/08/2026,5000 credit")

    txns = [
        Transaction(id="T1", amount=10000.0, direction=TransactionDirection.CREDIT, evidence_ids=["E1"]),
        Transaction(id="T2", amount=5000.0, direction=TransactionDirection.CREDIT, evidence_ids=["E2"]),
        Transaction(id="T3", amount=5000.0, direction=TransactionDirection.CREDIT, evidence_ids=["E3"]),
    ]

    result = engine.deduplicate(
        evidence_items=[ev1, ev2, ev3],
        transactions=txns,
    )

    assert len(result.groups) == 3
    for g in result.groups:
        assert g.status == DeduplicationStatus.DISTINCT_EVENT
