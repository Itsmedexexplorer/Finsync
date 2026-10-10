"""Unit tests for ExplainabilityEngine methods."""

import pytest
from backend.domain.discrepancy import Discrepancy, DiscrepancySeverity, DiscrepancyType
from backend.domain.reconciliation import ReconciliationStatus
from backend.reporting.explainability import ExplainabilityEngine


def test_title_generation() -> None:
    t_conf = ExplainabilityEngine.generate_title(ReconciliationStatus.CONFIRMED, 20000.0, 20000.0, "Rahul Kumar")
    assert "Confirmed Settlement of INR 20,000.00 for Rahul Kumar" == t_conf

    t_part = ExplainabilityEngine.generate_title(ReconciliationStatus.PARTIALLY_SETTLED, 20000.0, 15000.0, "Priya Patel")
    assert "Partial Settlement" in t_part


def test_executive_summary_generation() -> None:
    disc = Discrepancy(
        id="D1",
        discrepancy_type=DiscrepancyType.AMOUNT_MISMATCH,
        severity=DiscrepancySeverity.ERROR,
        message="Claim 20k vs Bank 18k",
    )
    summary = ExplainabilityEngine.generate_executive_summary(
        status=ReconciliationStatus.CONTRADICTED,
        expected_amount=20000.0,
        matched_amount=18000.0,
        outstanding_amount=20000.0,
        entity_name="Rohit Sharma",
        discrepancies=[disc],
    )
    assert "contradictions that prevent reconciliation" in summary
    assert "Claim 20k vs Bank 18k" in summary
