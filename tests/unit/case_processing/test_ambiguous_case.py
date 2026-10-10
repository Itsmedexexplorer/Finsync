"""Unit tests for ambiguous case processing."""

import pytest
from backend.case_processing.models import CaseInput
from backend.case_processing.service import CaseProcessingService
from backend.domain.claim import Claim, ClaimType
from backend.domain.evidence import Evidence, EvidenceModality, EvidenceSourceType
from backend.domain.transaction import Transaction, TransactionDirection


@pytest.fixture
def service() -> CaseProcessingService:
    return CaseProcessingService()


def test_ambiguous_case_execution(service: CaseProcessingService) -> None:
    ev = Evidence(id="E-AMB", modality=EvidenceModality.INVOICE, source_type=EvidenceSourceType.ZOHO_INVOICE, source_name="inv.pdf", raw_payload="20k inv")
    claim = Claim(id="C-AMB", evidence_id="E-AMB", claim_type=ClaimType.INVOICE_ISSUED, claimed_amount=20000.0)
    txns = [
        Transaction(id="T-AMB1", amount=20000.0, direction=TransactionDirection.CREDIT),
        Transaction(id="T-AMB2", amount=20000.0, direction=TransactionDirection.CREDIT),
    ]

    case_in = CaseInput(
        case_id="CASE-AMB-01",
        evidence_items=[ev],
        transactions=txns,
        metadata={
            "precomputed_claims": [claim.model_dump()],
            "precomputed_match_relationships": [{
                "id": "MAT-AMB",
                "relationship_type": "ONE_TO_ONE",
                "status": "AMBIGUOUS",
                "source_claim_ids": ["C-AMB"],
                "target_transaction_ids": ["T-AMB1", "T-AMB2"],
                "matched_amount": 20000.0,
                "target_amount": 20000.0,
                "score": 0.85,
                "explanation": "Multiple equal candidates",
            }],
        },
    )

    result = service.process_case(case_in)

    assert result.status == "AMBIGUOUS"
    assert result.status != "CONFIRMED"
    assert result.confidence_score <= 0.80
