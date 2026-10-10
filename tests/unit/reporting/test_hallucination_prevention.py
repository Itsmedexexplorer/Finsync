"""Unit tests verifying strict Anti-Hallucination guarantees in Reporting."""

import pytest
from backend.domain.claim import Claim, ClaimType
from backend.domain.reconciliation import ReconciliationStatus
from backend.reconciliation.result import ReconciliationResult
from backend.reporting.service import ReportingService


def test_no_invented_amounts_when_claim_is_none() -> None:
    claim = Claim(id="C1", evidence_id="E1", claim_type=ClaimType.PAYMENT_SENT, claimed_amount=None)
    recon_res = ReconciliationResult(
        reconciliation_id="REC-NONE",
        status=ReconciliationStatus.UNVERIFIABLE,
        expected_amount=None,
        matched_amount=0.0,
        outstanding_amount=0.0,
        confidence_score=0.40,
        explanation="Unverifiable",
        claim_ids=["C1"],
    )

    service = ReportingService()
    report = service.build_report(reconciliation_result=recon_res, claims=[claim])

    assert report.financial_summary.claimed_amount is None
    assert report.entity_summary.canonical_name == "Unknown Counterparty"
    assert report.entity_summary.gstin is None
    assert report.entity_summary.pan is None
