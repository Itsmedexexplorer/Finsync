"""Unit tests for CaseProcessingService high-level APIs."""

import pytest
from backend.case_processing.models import CaseInput
from backend.case_processing.service import CaseProcessingService
from backend.domain.evidence import Evidence, EvidenceModality, EvidenceSourceType
from backend.domain.transaction import Transaction, TransactionDirection


@pytest.fixture
def service() -> CaseProcessingService:
    return CaseProcessingService()


def test_process_evidence_api(service: CaseProcessingService) -> None:
    ev = Evidence(id="E-DIR", modality=EvidenceModality.BANK_STATEMENT, source_type=EvidenceSourceType.BANK_CSV, source_name="b.csv", raw_payload="10k")
    txn = Transaction(id="T-DIR", amount=10000.0, direction=TransactionDirection.CREDIT)

    res = service.process_evidence(case_id="CASE-DIR-01", evidence_items=[ev], transactions=[txn])
    assert res.case_id == "CASE-DIR-01"
    assert res.status == "UNMATCHED"


def test_process_batch_api(service: CaseProcessingService) -> None:
    case1 = CaseInput(case_id="CASE-B1", transactions=[Transaction(id="T1", amount=5000.0, direction=TransactionDirection.CREDIT)])
    case2 = CaseInput(case_id="CASE-B2", transactions=[Transaction(id="T2", amount=7000.0, direction=TransactionDirection.CREDIT)])

    results = service.process_batch([case1, case2])
    assert len(results) == 2
    assert results[0].case_id == "CASE-B1"
    assert results[1].case_id == "CASE-B2"


def test_process_benchmark_case_api(service: CaseProcessingService) -> None:
    bm_case = {
        "id": "CASE-BM-01",
        "evidence": [{"id": "E-BM", "modality": "BANK_STATEMENT", "source_type": "BANK_CSV", "source_name": "b.csv", "raw_payload": "25k"}],
        "claims": [],
        "transactions": [{"id": "T-BM", "amount": 25000.0, "direction": "CREDIT"}],
    }

    res = service.process_benchmark_case(bm_case)
    assert res.case_id == "CASE-BM-01"
    assert res.status == "UNMATCHED"
    assert res.financial_summary["matched_amount"] == 25000.0
