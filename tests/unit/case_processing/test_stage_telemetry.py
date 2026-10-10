"""Unit tests for Stage Execution Telemetry tracking."""

import pytest
from backend.case_processing.models import CaseInput, PipelineStage
from backend.case_processing.service import CaseProcessingService
from backend.domain.evidence import Evidence, EvidenceModality, EvidenceSourceType
from backend.domain.transaction import Transaction, TransactionDirection


@pytest.fixture
def service() -> CaseProcessingService:
    return CaseProcessingService()


def test_stage_telemetry_complete_8_stages(service: CaseProcessingService) -> None:
    ev = Evidence(id="E-TEL", modality=EvidenceModality.BANK_STATEMENT, source_type=EvidenceSourceType.BANK_CSV, source_name="bank.csv", raw_payload="35k")
    txn = Transaction(id="T-TEL", amount=35000.0, direction=TransactionDirection.CREDIT)

    case_in = CaseInput(case_id="CASE-TEL-01", evidence_items=[ev], transactions=[txn])
    result = service.process_case(case_in)

    assert len(result.stage_records) == 8
    stage_names = [rec.stage for rec in result.stage_records]
    expected_stages = [
        PipelineStage.INGESTION,
        PipelineStage.EXTRACTION,
        PipelineStage.ENTITY_RESOLUTION,
        PipelineStage.TRANSACTION_MATCHING,
        PipelineStage.DEDUPLICATION,
        PipelineStage.CONTRADICTION_DETECTION,
        PipelineStage.RECONCILIATION,
        PipelineStage.REPORTING,
    ]
    assert stage_names == expected_stages
    assert all(rec.status == "SUCCESS" for rec in result.stage_records)
    assert all(rec.duration_ms >= 0.0 for rec in result.stage_records)
    assert result.total_execution_time_ms > 0.0
