"""Unit tests for Provenance Integration in end-to-end processing."""

import pytest
from backend.case_processing.models import CaseInput
from backend.case_processing.service import CaseProcessingService
from backend.domain.claim import Claim, ClaimType
from backend.domain.evidence import Evidence, EvidenceModality, EvidenceSourceType
from backend.domain.transaction import Transaction, TransactionDirection


@pytest.fixture
def service() -> CaseProcessingService:
    return CaseProcessingService()


def test_provenance_nodes_registered(service: CaseProcessingService) -> None:
    ev = Evidence(id="E-PROV", modality=EvidenceModality.INVOICE, source_type=EvidenceSourceType.ZOHO_INVOICE, source_name="inv.pdf", raw_payload="10k")
    clm = Claim(id="C-PROV", evidence_id="E-PROV", claim_type=ClaimType.INVOICE_ISSUED, claimed_amount=10000.0)
    txn = Transaction(id="T-PROV", amount=10000.0, direction=TransactionDirection.CREDIT)

    case_in = CaseInput(
        case_id="CASE-PROV-01",
        evidence_items=[ev],
        transactions=[txn],
        metadata={"precomputed_claims": [clm.model_dump()]},
    )

    result = service.process_case(case_in)

    assert result.provenance_node_count >= 3
    assert result.report is not None
    assert "E-PROV" in result.report.provenance.evidence_ids
    assert "C-PROV" in result.report.provenance.claim_ids
    assert "T-PROV" in result.report.provenance.transaction_ids
