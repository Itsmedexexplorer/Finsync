"""Unit tests for Cross-Modal Evidence Grouping."""

import pytest
from backend.deduplication.engine import DeduplicationEngine
from backend.deduplication.result import DeduplicationStatus
from backend.domain.claim import Claim, ClaimType
from backend.domain.evidence import Evidence, EvidenceModality, EvidenceSourceType
from backend.domain.transaction import Transaction, TransactionDirection


@pytest.fixture
def engine() -> DeduplicationEngine:
    return DeduplicationEngine()


def test_cross_modal_bank_and_screenshot_same_utr(engine: DeduplicationEngine) -> None:
    """Bank statement CSV + GPay screenshot sharing same UTR -> SAME_EVENT."""
    ev_bank = Evidence(
        id="EVID-BANK-01",
        modality=EvidenceModality.BANK_STATEMENT,
        source_type=EvidenceSourceType.BANK_CSV,
        source_name="stmt.csv",
        raw_payload="15/08/2026,UPI/408219381920/PAYTO/RAHUL,35000.00",
    )
    ev_ss = Evidence(
        id="EVID-SS-01",
        modality=EvidenceModality.PAYMENT_SCREENSHOT,
        source_type=EvidenceSourceType.MANUAL_UPLOAD,
        source_name="gpay.png",
        raw_payload="Paid Rs 35,000. Ref 408219381920",
    )

    claims = [
        Claim(id="C-BANK", evidence_id="EVID-BANK-01", claim_type=ClaimType.PAYMENT_RECEIVED, claimed_amount=35000.0, reference_id_hint="408219381920"),
        Claim(id="C-SS", evidence_id="EVID-SS-01", claim_type=ClaimType.PAYMENT_SENT, claimed_amount=35000.0, reference_id_hint="408219381920"),
    ]
    txns = [
        Transaction(id="TXN-01", amount=35000.0, direction=TransactionDirection.CREDIT, bank_reference="408219381920", evidence_ids=["EVID-BANK-01"]),
    ]

    result = engine.deduplicate(
        evidence_items=[ev_bank, ev_ss],
        claims=claims,
        transactions=txns,
    )

    assert len(result.groups) == 1
    grp = result.groups[0]
    assert grp.status == DeduplicationStatus.SAME_EVENT
    assert set(grp.member_evidence_ids) == {"EVID-BANK-01", "EVID-SS-01"}
    assert set(grp.member_claim_ids) == {"C-BANK", "C-SS"}
    assert grp.candidate_transaction_ids == ["TXN-01"]


def test_cross_modal_bank_and_whatsapp_same_entity_amount_date(engine: DeduplicationEngine) -> None:
    """Bank statement credit + WhatsApp message without UTR but with matching entity, amount, date -> SAME_EVENT."""
    ev_bank = Evidence(
        id="EVID-B",
        modality=EvidenceModality.BANK_STATEMENT,
        source_type=EvidenceSourceType.BANK_CSV,
        source_name="stmt.csv",
        raw_payload="10/08/2026, 20000 credit",
    )
    ev_chat = Evidence(
        id="EVID-W",
        modality=EvidenceModality.MESSAGING_CHAT,
        source_type=EvidenceSourceType.WHATSAPP_EXPORT,
        source_name="chat.txt",
        raw_payload="Bhai 20k GPay kar diya",
    )

    claim_chat = Claim(
        id="CLM-W",
        evidence_id="EVID-W",
        claim_type=ClaimType.PAYMENT_SENT,
        claimed_amount=20000.0,
        claimed_date="2026-08-10",
        counterparty_hint="Rahul Kumar",
    )
    txn = Transaction(
        id="TXN-B",
        amount=20000.0,
        direction=TransactionDirection.CREDIT,
        origin_entity_id="ENT-001",
        timestamp="2026-08-10T10:00:00Z",
        evidence_ids=["EVID-B"],
    )

    result = engine.deduplicate(
        evidence_items=[ev_bank, ev_chat],
        claims=[claim_chat],
        transactions=[txn],
        claim_entity_map={"CLM-W": "ENT-001"},
    )

    assert len(result.groups) == 1
    grp = result.groups[0]
    assert grp.status in (DeduplicationStatus.SAME_EVENT, DeduplicationStatus.POSSIBLE_DUPLICATE)
    assert set(grp.member_evidence_ids) == {"EVID-B", "EVID-W"}
