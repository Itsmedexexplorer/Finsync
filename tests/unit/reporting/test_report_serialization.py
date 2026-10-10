"""Unit tests for Report Serialization and Deserialization."""

import json
import pytest
from backend.domain.reconciliation import ReconciliationStatus
from backend.reconciliation.result import ReconciliationResult
from backend.reporting.models import FinancialTruthReport
from backend.reporting.service import ReportingService


def test_json_and_text_serialization() -> None:
    recon_res = ReconciliationResult(
        reconciliation_id="REC-SER-01",
        status=ReconciliationStatus.CONFIRMED,
        expected_amount=10000.0,
        matched_amount=10000.0,
        outstanding_amount=0.0,
        confidence_score=1.0,
        explanation="Confirmed settlement.",
    )

    service = ReportingService()
    report = service.build_report(reconciliation_result=recon_res, case_id="CASE-SER-01")

    # Render JSON
    json_str = service.render_json_report(report)
    data = json.loads(json_str)
    assert data["case_id"] == "CASE-SER-01"
    assert data["status"] == "CONFIRMED"

    # Round trip deserialization
    deserialized_report = FinancialTruthReport.model_validate(data)
    assert deserialized_report.report_id == report.report_id
    assert deserialized_report.confidence_score == 1.0

    # Render Text Report
    text_str = service.render_text_report(report)
    assert "VERITY FINANCIAL TRUTH REPORT" in text_str
    assert "CASE-SER-01" in text_str
    assert "CONFIRMED" in text_str
