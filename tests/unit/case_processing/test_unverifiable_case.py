"""Unit tests for unverifiable case processing."""

import pytest
from backend.case_processing.models import CaseInput
from backend.case_processing.service import CaseProcessingService
from backend.domain.claim import Claim, ClaimType
from backend.domain.evidence import Evidence, EvidenceModality, EvidenceSourceType


@pytest.fixture
def service() -> CaseProcessingService:
    return CaseProcessingService()


def test_unverifiable_case_execution(service: CaseProcessingService) -> None:
    ev = Evidence(id="E-UNV", modality=EvidenceModality.MESSAGING_CHAT, source_type=EvidenceSourceType.WHATSAPP_EXPORT, source_name="chat.txt", raw_payload="Payment sent")
    claim = Claim(id="C-UNV", evidence_id="E-UNV", claim_type=ClaimType.PAYMENT_SENT, claimed_amount=None)

    case_in = CaseInput(
        case_id="CASE-UNV-01",
        evidence_items=[ev],
        transactions=[],
        metadata={"precomputed_claims": [claim.model_dump()]},
    )

    result = service.process_case(case_in)

    assert result.status == "UNVERIFIABLE"
    assert result.status != "CONFIRMED"
    assert result.financial_summary["matched_amount"] == 0.0
    assert result.confidence_score <= 0.60
