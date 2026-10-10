"""Unit tests for unmatched case processing."""

import pytest
from backend.case_processing.models import CaseInput
from backend.case_processing.service import CaseProcessingService
from backend.domain.evidence import Evidence, EvidenceModality, EvidenceSourceType
from backend.domain.transaction import Transaction, TransactionDirection


@pytest.fixture
def service() -> CaseProcessingService:
    return CaseProcessingService()


def test_unmatched_transaction_case_execution(service: CaseProcessingService) -> None:
    ev = Evidence(id="E-UNM", modality=EvidenceModality.BANK_STATEMENT, source_type=EvidenceSourceType.BANK_CSV, source_name="bank.csv", raw_payload="Credit 35k")
    txn = Transaction(id="T-UNM", amount=35000.0, direction=TransactionDirection.CREDIT, bank_reference="408219381920")

    case_in = CaseInput(
        case_id="CASE-UNM-01",
        evidence_items=[ev],
        transactions=[txn],
        metadata={},
    )

    result = service.process_case(case_in)

    assert result.status == "UNMATCHED"
    assert result.financial_summary["matched_amount"] == 35000.0
    assert result.report is not None
    assert result.report.status.value == "UNMATCHED"
