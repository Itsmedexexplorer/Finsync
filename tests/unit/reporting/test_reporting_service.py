"""Unit tests for ReportingService batch processing."""

import pytest
from backend.domain.reconciliation import ReconciliationStatus
from backend.reconciliation.result import BatchReconciliationResult, ReconciliationResult
from backend.reporting.service import ReportingService


def test_build_reports_from_batch() -> None:
    res1 = ReconciliationResult(
        reconciliation_id="REC-B1",
        event_id="EVT-001",
        status=ReconciliationStatus.CONFIRMED,
        expected_amount=20000.0,
        matched_amount=20000.0,
        outstanding_amount=0.0,
        confidence_score=1.0,
        explanation="Event 1 confirmed",
    )
    res2 = ReconciliationResult(
        reconciliation_id="REC-B2",
        event_id="EVT-002",
        status=ReconciliationStatus.UNMATCHED,
        expected_amount=None,
        matched_amount=15000.0,
        outstanding_amount=0.0,
        confidence_score=1.0,
        explanation="Event 2 unmatched",
    )

    batch_result = BatchReconciliationResult(
        results=[res1, res2],
        total_reconciled_amount=35000.0,
        total_outstanding_amount=0.0,
    )

    service = ReportingService()
    reports = service.build_reports_from_batch(batch_result)

    assert len(reports) == 2
    assert reports[0].case_id == "EVT-001"
    assert reports[0].status.value == "CONFIRMED"
    assert reports[1].case_id == "EVT-002"
    assert reports[1].status.value == "UNMATCHED"
