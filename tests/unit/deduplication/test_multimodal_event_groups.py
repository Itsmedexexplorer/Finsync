"""Unit tests for Multimodal Event Group formation and MatchRelationship integration."""

import pytest
from backend.deduplication.engine import DeduplicationEngine
from backend.deduplication.result import DeduplicationStatus
from backend.domain.claim import Claim, ClaimType
from backend.domain.evidence import Evidence, EvidenceModality, EvidenceSourceType
from backend.domain.transaction import Transaction, TransactionDirection
from backend.transaction_matching.result import MatchRelationship, MatchRelationshipType, MatchStatus


@pytest.fixture
def engine() -> DeduplicationEngine:
    return DeduplicationEngine()


def test_multimodal_invoice_bank_screenshot_event_group(engine: DeduplicationEngine) -> None:
    """An invoice, bank credit, and payment screenshot linked via MatchRelationship
    form 1 clean event group holding all 3 evidence items."""
    ev_inv = Evidence(id="E-INV", modality=EvidenceModality.INVOICE, source_type=EvidenceSourceType.ZOHO_INVOICE, source_name="INV.pdf", raw_payload="Invoice 35k")
    ev_bank = Evidence(id="E-BANK", modality=EvidenceModality.BANK_STATEMENT, source_type=EvidenceSourceType.BANK_CSV, source_name="stmt.csv", raw_payload="35k credit")
    ev_ss = Evidence(id="E-SS", modality=EvidenceModality.PAYMENT_SCREENSHOT, source_type=EvidenceSourceType.MANUAL_UPLOAD, source_name="gpay.png", raw_payload="35k sent")

    claims = [
        Claim(id="C-INV", evidence_id="E-INV", claim_type=ClaimType.INVOICE_ISSUED, claimed_amount=35000.0, reference_id_hint="INV-088"),
        Claim(id="C-SS", evidence_id="E-SS", claim_type=ClaimType.PAYMENT_SENT, claimed_amount=35000.0, reference_id_hint="408219381920"),
    ]
    txns = [
        Transaction(id="TXN-01", amount=35000.0, direction=TransactionDirection.CREDIT, bank_reference="408219381920", evidence_ids=["E-BANK"]),
    ]
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

    result = engine.deduplicate(
        evidence_items=[ev_inv, ev_bank, ev_ss],
        claims=claims,
        transactions=txns,
        match_relationships=[match_rel],
    )

    assert len(result.groups) == 1
    grp = result.groups[0]
    assert grp.status == DeduplicationStatus.SAME_EVENT
    assert set(grp.member_evidence_ids) == {"E-INV", "E-BANK", "E-SS"}
    assert set(grp.member_claim_ids) == {"C-INV", "C-SS"}
    assert grp.candidate_transaction_ids == ["TXN-01"]
