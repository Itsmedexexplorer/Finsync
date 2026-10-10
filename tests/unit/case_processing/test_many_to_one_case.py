"""Unit tests for many-to-one milestone case processing."""

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


def test_many_to_one_case_execution(service: CaseProcessingService) -> None:
    ev = Evidence(id="E-M1", modality=EvidenceModality.INVOICE, source_type=EvidenceSourceType.ZOHO_INVOICE, source_name="inv.pdf", raw_payload="20k")
    claim = Claim(id="C-M1", evidence_id="E-M1", claim_type=ClaimType.INVOICE_ISSUED, claimed_amount=20000.0, counterparty_hint="Bharat Tech")
    txns = [
        Transaction(id="T-M1A", amount=10000.0, direction=TransactionDirection.CREDIT, origin_entity_id="ENT-BHARAT"),
        Transaction(id="T-M1B", amount=5000.0, direction=TransactionDirection.CREDIT, origin_entity_id="ENT-BHARAT"),
        Transaction(id="T-M1C", amount=5000.0, direction=TransactionDirection.CREDIT, origin_entity_id="ENT-BHARAT"),
    ]
    entity = Entity(id="ENT-BHARAT", canonical_name="Bharat Tech", entity_type=EntityType.PRIVATE_LIMITED)

    case_in = CaseInput(
        case_id="CASE-M21-01",
        evidence_items=[ev],
        transactions=txns,
        entities=[entity],
        metadata={
            "precomputed_claims": [claim.model_dump()],
            "claim_entity_map": {"C-M1": "ENT-BHARAT"},
            "precomputed_match_relationships": [{
                "id": "MAT-M1",
                "relationship_type": "MANY_TO_ONE",
                "status": "MATCHED",
                "source_claim_ids": ["C-M1"],
                "target_transaction_ids": ["T-M1A", "T-M1B", "T-M1C"],
                "matched_amount": 20000.0,
                "target_amount": 20000.0,
                "score": 0.95,
                "explanation": "Milestone payments match",
                "entity_id": "ENT-BHARAT",
            }],
        },
    )

    result = service.process_case(case_in)

    assert result.status == "CONFIRMED"
    assert result.financial_summary["matched_amount"] == 20000.0
    assert result.financial_summary["outstanding_amount"] == 0.0
