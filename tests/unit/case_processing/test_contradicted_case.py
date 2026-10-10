"""Unit tests for contradicted case processing."""

import pytest
from backend.case_processing.models import CaseInput
from backend.case_processing.service import CaseProcessingService
from backend.domain.claim import Claim, ClaimType
from backend.domain.evidence import Evidence, EvidenceModality, EvidenceSourceType
from backend.domain.transaction import Transaction, TransactionDirection


@pytest.fixture
def service() -> CaseProcessingService:
    return CaseProcessingService()


def test_contradicted_amount_case_execution(service: CaseProcessingService) -> None:
    ev = Evidence(id="E-CNF", modality=EvidenceModality.INVOICE, source_type=EvidenceSourceType.ZOHO_INVOICE, source_name="inv.pdf", raw_payload="20k inv")
    claim = Claim(id="C-CNF", evidence_id="E-CNF", claim_type=ClaimType.INVOICE_ISSUED, claimed_amount=20000.0, reference_id_hint="408219381920")
    txn = Transaction(id="T-CNF", amount=18000.0, direction=TransactionDirection.CREDIT, bank_reference="408219381920")

    case_in = CaseInput(
        case_id="CASE-CNF-01",
        evidence_items=[ev],
        transactions=[txn],
        metadata={
            "precomputed_claims": [claim.model_dump()],
            "precomputed_discrepancies": [{
                "id": "DISC-01",
                "discrepancy_type": "AMOUNT_MISMATCH",
                "severity": "ERROR",
                "message": "Amount mismatch: 20k vs 18k",
                "expected_value": "20000.00",
                "observed_value": "18000.00",
                "involved_claim_ids": ["C-CNF"],
                "involved_transaction_ids": ["T-CNF"],
            }],
        },
    )

    result = service.process_case(case_in)

    assert result.status == "CONTRADICTED"
    assert result.status != "CONFIRMED"
    assert result.financial_summary["discrepancies_count"] == 1
    assert result.report is not None
    assert len(result.report.contradiction_summary) == 1
