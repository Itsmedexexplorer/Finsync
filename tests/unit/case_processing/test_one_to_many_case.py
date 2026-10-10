"""Unit tests for one-to-many bulk settlement case processing."""

import pytest
from backend.case_processing.models import CaseInput
from backend.case_processing.service import CaseProcessingService
from backend.domain.claim import Claim, ClaimType
from backend.domain.entity import Entity, EntityType
from backend.domain.evidence import Evidence, EvidenceModality, EvidenceSourceType
from backend.domain.transaction import Transaction, TransactionDirection


@pytest.fixture
def service() -> CaseProcessingService:
    return CaseProcessingService()


def test_one_to_many_case_execution(service: CaseProcessingService) -> None:
    ev1 = Evidence(id="E-B1", modality=EvidenceModality.INVOICE, source_type=EvidenceSourceType.ZOHO_INVOICE, source_name="inv1.pdf", raw_payload="10k")
    ev2 = Evidence(id="E-B2", modality=EvidenceModality.INVOICE, source_type=EvidenceSourceType.ZOHO_INVOICE, source_name="inv2.pdf", raw_payload="10k")
    ev_bnk = Evidence(id="E-BNK", modality=EvidenceModality.BANK_STATEMENT, source_type=EvidenceSourceType.BANK_CSV, source_name="bank.csv", raw_payload="20k")

    c1 = Claim(id="C-B1", evidence_id="E-B1", claim_type=ClaimType.INVOICE_ISSUED, claimed_amount=10000.0)
    c2 = Claim(id="C-B2", evidence_id="E-B2", claim_type=ClaimType.INVOICE_ISSUED, claimed_amount=10000.0)
    txn = Transaction(id="T-BULK", amount=20000.0, direction=TransactionDirection.CREDIT, origin_entity_id="ENT-SHREE", evidence_ids=["E-BNK"])
    entity = Entity(id="ENT-SHREE", canonical_name="Shree Enterprises", entity_type=EntityType.PRIVATE_LIMITED)

    case_in = CaseInput(
        case_id="CASE-12M-01",
        evidence_items=[ev1, ev2, ev_bnk],
        transactions=[txn],
        entities=[entity],
        metadata={
            "precomputed_claims": [c1.model_dump(), c2.model_dump()],
            "claim_entity_map": {"C-B1": "ENT-SHREE", "C-B2": "ENT-SHREE"},
            "precomputed_deduplication_groups": [{
                "group_id": "GRP-12M",
                "status": "SAME_EVENT",
                "member_evidence_ids": ["E-B1", "E-B2", "E-BNK"],
                "member_claim_ids": ["C-B1", "C-B2"],
                "candidate_transaction_ids": ["T-BULK"],
                "explanation": "Bulk event",
            }],
            "precomputed_match_relationships": [{
                "id": "MAT-12M",
                "relationship_type": "ONE_TO_MANY",
                "status": "MATCHED",
                "source_claim_ids": ["C-B1", "C-B2"],
                "target_transaction_ids": ["T-BULK"],
                "matched_amount": 20000.0,
                "target_amount": 20000.0,
                "score": 0.95,
                "explanation": "Bulk match",
                "entity_id": "ENT-SHREE",
            }],
        },
    )

    result = service.process_case(case_in)

    assert result.status == "CONFIRMED"
    assert result.financial_summary["matched_amount"] == 20000.0
