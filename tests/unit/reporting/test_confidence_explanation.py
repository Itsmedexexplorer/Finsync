"""Unit tests for Confidence Factors breakdown."""

import pytest
from backend.domain.discrepancy import Discrepancy, DiscrepancySeverity, DiscrepancyType
from backend.domain.evidence import Evidence, EvidenceModality, EvidenceSourceType
from backend.domain.reconciliation import ReconciliationStatus
from backend.reconciliation.result import ReconciliationResult
from backend.reporting.explainability import ExplainabilityEngine


def test_confidence_breakdown_positive_and_negative_factors() -> None:
    ev1 = Evidence(id="E1", modality=EvidenceModality.INVOICE, source_type=EvidenceSourceType.ZOHO_INVOICE, source_name="i.pdf", raw_payload="1")
    ev2 = Evidence(id="E2", modality=EvidenceModality.BANK_STATEMENT, source_type=EvidenceSourceType.BANK_CSV, source_name="b.csv", raw_payload="2")

    disc = Discrepancy(
        id="D1",
        discrepancy_type=DiscrepancyType.DATE_MISMATCH,
        severity=DiscrepancySeverity.WARNING,
        message="Date drift exceeds window",
    )

    recon_res = ReconciliationResult(
        reconciliation_id="REC-01",
        status=ReconciliationStatus.CONFIRMED,
        expected_amount=10000.0,
        matched_amount=10000.0,
        outstanding_amount=0.0,
        confidence_score=0.95,
        supporting_signals=["EXACT_REFERENCE", "EXACT_AMOUNT", "EXACT_ENTITY"],
        contradicting_signals=["DATE_MISMATCH"],
        explanation="Confirmed",
    )

    factors = ExplainabilityEngine.generate_confidence_breakdown(
        reconciliation_result=recon_res,
        evidence=[ev1, ev2],
        discrepancies=[disc],
    )

    impacts = {f.impact for f in factors}
    assert "+" in impacts
    assert "-" in impacts
    assert any(f.factor_type == "EXACT_REFERENCE" for f in factors)
    assert any(f.factor_type == "DATE_MISMATCH" for f in factors)
