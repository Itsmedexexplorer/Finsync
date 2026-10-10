"""Unit tests for multimodal cross-modal case processing."""

import pytest
from backend.case_processing.models import CaseInput
from backend.case_processing.service import CaseProcessingService
from backend.domain.claim import Claim, ClaimType
from backend.domain.evidence import Evidence, EvidenceModality, EvidenceSourceType
from backend.domain.transaction import Transaction, TransactionDirection


@pytest.fixture
def service() -> CaseProcessingService:
    return CaseProcessingService()


def test_cross_modal_case_execution(service: CaseProcessingService) -> None:
    ev_inv = Evidence(id="E-INV", modality=EvidenceModality.INVOICE, source_type=EvidenceSourceType.ZOHO_INVOICE, source_name="inv.pdf", raw_payload="50k")
    ev_bank = Evidence(id="E-BNK", modality=EvidenceModality.BANK_STATEMENT, source_type=EvidenceSourceType.BANK_CSV, source_name="bank.csv", raw_payload="50k")
    ev_chat = Evidence(id="E-CHT", modality=EvidenceModality.MESSAGING_CHAT, source_type=EvidenceSourceType.WHATSAPP_EXPORT, source_name="chat.txt", raw_payload="50k")

    clm_inv = Claim(id="C-INV", evidence_id="E-INV", claim_type=ClaimType.INVOICE_ISSUED, claimed_amount=50000.0, reference_id_hint="408219381920")
    clm_chat = Claim(id="C-CHT", evidence_id="E-CHT", claim_type=ClaimType.PAYMENT_SENT, claimed_amount=50000.0, reference_id_hint="408219381920")
    txn = Transaction(id="T-BNK", amount=50000.0, direction=TransactionDirection.CREDIT, bank_reference="408219381920", evidence_ids=["E-BNK"])

    case_in = CaseInput(
        case_id="CASE-XMODAL-01",
        evidence_items=[ev_inv, ev_bank, ev_chat],
        transactions=[txn],
        metadata={
            "precomputed_claims": [clm_inv.model_dump(), clm_chat.model_dump()],
            "precomputed_deduplication_groups": [{
                "group_id": "GRP-X",
                "status": "SAME_EVENT",
                "member_evidence_ids": ["E-INV", "E-BNK", "E-CHT"],
                "member_claim_ids": ["C-INV", "C-CHT"],
                "candidate_transaction_ids": ["T-BNK"],
                "explanation": "Grouped cross-modal event",
            }],
        },
    )

    result = service.process_case(case_in)

    assert result.status == "CONFIRMED"
    assert result.financial_summary["matched_amount"] == 50000.0
    assert result.financial_summary["evidence_count"] == 3
    assert result.financial_summary["claims_count"] == 2
