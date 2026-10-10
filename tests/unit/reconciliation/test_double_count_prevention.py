"""Unit tests verifying Zero Double-Counting in Financial Reconciliation."""

import pytest
from backend.deduplication.result import DeduplicationGroup, DeduplicationStatus
from backend.domain.claim import Claim, ClaimType
from backend.domain.evidence import Evidence, EvidenceModality, EvidenceSourceType
from backend.domain.reconciliation import ReconciliationStatus
from backend.domain.transaction import Transaction, TransactionDirection
from backend.reconciliation.engine import ReconciliationEngine
from backend.transaction_matching.result import MatchRelationship, MatchRelationshipType, MatchStatus


@pytest.fixture
def engine() -> ReconciliationEngine:
    return ReconciliationEngine()


def test_zero_double_counting_across_duplicate_evidence(engine: ReconciliationEngine) -> None:
    """When a ₹20,000 transaction is supported by 4 separate evidence pieces (Bank + Chat + Screenshot + Invoice),
    reconciled amount MUST BE exactly ₹20,000, NOT ₹80,000!"""
    ev1 = Evidence(id="E1", modality=EvidenceModality.BANK_STATEMENT, source_type=EvidenceSourceType.BANK_CSV, source_name="b.csv", raw_payload="20k bank")
    ev2 = Evidence(id="E2", modality=EvidenceModality.MESSAGING_CHAT, source_type=EvidenceSourceType.WHATSAPP_EXPORT, source_name="c.txt", raw_payload="20k chat")
    ev3 = Evidence(id="E3", modality=EvidenceModality.PAYMENT_SCREENSHOT, source_type=EvidenceSourceType.MANUAL_UPLOAD, source_name="s.png", raw_payload="20k ss")
    ev4 = Evidence(id="E4", modality=EvidenceModality.INVOICE, source_type=EvidenceSourceType.ZOHO_INVOICE, source_name="i.pdf", raw_payload="20k inv")

    claims = [
        Claim(id="C-INV", evidence_id="E4", claim_type=ClaimType.INVOICE_ISSUED, claimed_amount=20000.0, reference_id_hint="408219381920"),
        Claim(id="C-CHAT", evidence_id="E2", claim_type=ClaimType.PAYMENT_SENT, claimed_amount=20000.0, reference_id_hint="408219381920"),
        Claim(id="C-SS", evidence_id="E3", claim_type=ClaimType.PAYMENT_SENT, claimed_amount=20000.0, reference_id_hint="408219381920"),
    ]
    txns = [
        Transaction(id="TXN-01", amount=20000.0, direction=TransactionDirection.CREDIT, bank_reference="408219381920", evidence_ids=["E1"]),
    ]

    dedup_grp = DeduplicationGroup(
        group_id="GRP-20K",
        status=DeduplicationStatus.SAME_EVENT,
        member_evidence_ids=["E1", "E2", "E3", "E4"],
        member_claim_ids=["C-INV", "C-CHAT", "C-SS"],
        candidate_transaction_ids=["TXN-01"],
        explanation="Grouped single event",
    )
    match_rel = MatchRelationship(
        id="MAT-01",
        relationship_type=MatchRelationshipType.ONE_TO_ONE,
        status=MatchStatus.MATCHED,
        source_claim_ids=["C-INV"],
        target_transaction_ids=["TXN-01"],
        matched_amount=20000.0,
        target_amount=20000.0,
        score=1.0,
        explanation="Matched",
    )

    batch_result = engine.reconcile(
        claims=claims,
        transactions=txns,
        evidence_items=[ev1, ev2, ev3, ev4],
        deduplication_groups=[dedup_grp],
        match_relationships=[match_rel],
    )

    assert len(batch_result.results) == 1
    res = batch_result.results[0]
    assert res.matched_amount == 20000.0
    assert batch_result.total_reconciled_amount == 20000.0
    assert res.status == ReconciliationStatus.CONFIRMED
