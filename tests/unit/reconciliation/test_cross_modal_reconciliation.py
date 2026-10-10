"""Unit tests for Cross-Modal Financial Reconciliation."""

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


def test_cross_modal_evidence_grouped_into_single_reconciliation_event(engine: ReconciliationEngine) -> None:
    """Invoice + bank statement + WhatsApp + screenshot for a ₹35,000 payment
    must produce exactly ONE reconciliation result with matched_amount = ₹35,000."""
    ev_inv = Evidence(id="E-INV", modality=EvidenceModality.INVOICE, source_type=EvidenceSourceType.ZOHO_INVOICE, source_name="i.pdf", raw_payload="35k inv")
    ev_bank = Evidence(id="E-BANK", modality=EvidenceModality.BANK_STATEMENT, source_type=EvidenceSourceType.BANK_CSV, source_name="b.csv", raw_payload="35k bank")
    ev_ss = Evidence(id="E-SS", modality=EvidenceModality.PAYMENT_SCREENSHOT, source_type=EvidenceSourceType.MANUAL_UPLOAD, source_name="s.png", raw_payload="35k ss")

    claims = [
        Claim(id="C-INV", evidence_id="E-INV", claim_type=ClaimType.INVOICE_ISSUED, claimed_amount=35000.0, reference_id_hint="408219381920"),
        Claim(id="C-SS", evidence_id="E-SS", claim_type=ClaimType.PAYMENT_SENT, claimed_amount=35000.0, reference_id_hint="408219381920"),
    ]
    txns = [
        Transaction(id="TXN-01", amount=35000.0, direction=TransactionDirection.CREDIT, bank_reference="408219381920", evidence_ids=["E-BANK"]),
    ]

    dedup_grp = DeduplicationGroup(
        group_id="GRP-CROSS",
        status=DeduplicationStatus.SAME_EVENT,
        member_evidence_ids=["E-INV", "E-BANK", "E-SS"],
        member_claim_ids=["C-INV", "C-SS"],
        candidate_transaction_ids=["TXN-01"],
        explanation="Cross modal event",
    )
    match_rel = MatchRelationship(
        id="MAT-01",
        relationship_type=MatchRelationshipType.ONE_TO_ONE,
        status=MatchStatus.MATCHED,
        source_claim_ids=["C-INV"],
        target_transaction_ids=["TXN-01"],
        matched_amount=35000.0,
        target_amount=35000.0,
        score=1.0,
        explanation="Matched",
    )

    batch_result = engine.reconcile(
        claims=claims,
        transactions=txns,
        evidence_items=[ev_inv, ev_bank, ev_ss],
        deduplication_groups=[dedup_grp],
        match_relationships=[match_rel],
    )

    assert len(batch_result.results) == 1
    res = batch_result.results[0]
    assert res.status == ReconciliationStatus.CONFIRMED
    assert res.matched_amount == 35000.0
    assert res.outstanding_amount == 0.0
    assert set(res.evidence_ids) == {"E-INV", "E-BANK", "E-SS"}
