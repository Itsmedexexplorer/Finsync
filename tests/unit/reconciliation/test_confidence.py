"""Unit tests for Confidence Scoring in Reconciliation."""

import pytest
from backend.domain.discrepancy import Discrepancy, DiscrepancySeverity, DiscrepancyType
from backend.domain.reconciliation import ReconciliationStatus
from backend.reconciliation.confidence import ConfidenceCalculator


def test_confidence_scoring_for_confirmed() -> None:
    score = ConfidenceCalculator.calculate_confidence(
        status=ReconciliationStatus.CONFIRMED,
        supporting_signals=["EXACT_REFERENCE", "EXACT_AMOUNT", "EXACT_ENTITY", "MATCHED_RELATIONSHIP"],
        contradicting_signals=[],
        evidence_count=2,
    )
    assert score >= 0.95


def test_confidence_scoring_for_contradicted() -> None:
    disc = Discrepancy(
        id="D1",
        discrepancy_type=DiscrepancyType.AMOUNT_MISMATCH,
        severity=DiscrepancySeverity.ERROR,
        message="Mismatch",
    )
    score = ConfidenceCalculator.calculate_confidence(
        status=ReconciliationStatus.CONTRADICTED,
        supporting_signals=[],
        contradicting_signals=["AMOUNT_MISMATCH"],
        discrepancies=[disc],
    )
    assert score >= 0.90
