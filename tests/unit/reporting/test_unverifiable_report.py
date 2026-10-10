"""Unit tests for Unverifiable Financial Truth Report generation."""

import pytest
from backend.domain.claim import Claim, ClaimType
from backend.domain.reconciliation import ReconciliationStatus
from backend.reconciliation.result import ReconciliationResult
from backend.reporting.models import ReportStatus
from backend.reporting.service import ReportingService


@pytest.fixture
def service() -> ReportingService:
    return ReportingService()


def test_unverifiable_report_generation(service: ReportingService) -> None:
    claim = Claim(id="C5", evidence_id="E5", claim_type=ClaimType.PAYMENT_SENT, claimed_amount=None)

    recon_res = ReconciliationResult(
        reconciliation_id="REC-005",
        status=ReconciliationStatus.UNVERIFIABLE,
        expected_amount=None,
        matched_amount=0.0,
        outstanding_amount=0.0,
        confidence_score=0.40,
        supporting_signals=[],
        explanation="Unverifiable claim.",
        claim_ids=["C5"],
    )

    report = service.build_report(
        reconciliation_result=recon_res,
        claims=[claim],
    )

    assert report.status == ReportStatus.UNVERIFIABLE
    assert report.financial_summary.claimed_amount is None
    assert report.financial_summary.matched_amount == 0.0
    assert any("MISSING_LEDGER_PROOF" in item.item_type for item in report.unresolved_items)
    assert any("Request formal payment proof" in act for act in report.recommended_actions)
