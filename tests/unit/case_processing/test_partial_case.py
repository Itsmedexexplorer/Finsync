"""Unit tests for partial settlement case processing."""

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


def test_partial_settlement_case_execution(service: CaseProcessingService) -> None:
    ev = Evidence(id="E-PART", modality=EvidenceModality.INVOICE, source_type=EvidenceSourceType.ZOHO_INVOICE, source_name="inv.pdf", raw_payload="20k inv")
    claim = Claim(id="C-PART", evidence_id="E-PART", claim_type=ClaimType.INVOICE_ISSUED, claimed_amount=20000.0, counterparty_hint="Priya Patel")
    txn = Transaction(id="T-PART", amount=12000.0, direction=TransactionDirection.CREDIT, origin_entity_id="ENT-PRIYA")
    entity = Entity(id="ENT-PRIYA", canonical_name="Priya Patel", entity_type=EntityType.INDIVIDUAL)

    case_in = CaseInput(
        case_id="CASE-PART-01",
        evidence_items=[ev],
        transactions=[txn],
        entities=[entity],
        metadata={
            "precomputed_claims": [claim.model_dump()],
            "claim_entity_map": {"C-PART": "ENT-PRIYA"},
            "precomputed_match_relationships": [{
                "id": "MAT-02",
                "relationship_type": "PARTIAL",
                "status": "MATCHED",
                "source_claim_ids": ["C-PART"],
                "target_transaction_ids": ["T-PART"],
                "matched_amount": 12000.0,
                "target_amount": 20000.0,
                "score": 0.95,
                "explanation": "Partial payment",
                "entity_id": "ENT-PRIYA",
            }],
        },
    )

    result = service.process_case(case_in)

    assert result.status in ("PARTIAL", "PARTIALLY_SETTLED")
    assert result.financial_summary["claimed_amount"] == 20000.0
    assert result.financial_summary["matched_amount"] == 12000.0
    assert result.financial_summary["outstanding_amount"] == 8000.0
    assert result.report is not None
