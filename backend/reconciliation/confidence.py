"""Deterministic Confidence Scoring for Financial Reconciliation."""

from __future__ import annotations

from typing import List, Optional, Tuple

from backend.domain.discrepancy import Discrepancy, DiscrepancySeverity
from backend.domain.reconciliation import ReconciliationStatus


class ConfidenceCalculator:
    """Calculates explainable confidence scores for reconciliation conclusions."""

    WEIGHT_EXACT_REFERENCE = 0.40
    WEIGHT_EXACT_AMOUNT = 0.30
    WEIGHT_EXACT_ENTITY = 0.20
    WEIGHT_MATCHED_RELATIONSHIP = 0.15
    WEIGHT_MULTIPLE_EVIDENCE = 0.10
    WEIGHT_DATE_COMPATIBILITY = 0.10
    WEIGHT_NO_CONTRADICTIONS = 0.05

    @classmethod
    def calculate_confidence(
        cls,
        status: ReconciliationStatus,
        supporting_signals: List[str],
        contradicting_signals: List[str],
        discrepancies: Optional[List[Discrepancy]] = None,
        evidence_count: int = 1,
    ) -> float:
        """Computes deterministic confidence score (0.0 to 1.0) based on signals and status."""
        discs = discrepancies or []
        has_critical = any(d.severity == DiscrepancySeverity.CRITICAL for d in discs)
        has_error = any(d.severity == DiscrepancySeverity.ERROR for d in discs)

        if status == ReconciliationStatus.CONFIRMED:
            score = 0.0
            if "EXACT_REFERENCE" in supporting_signals:
                score += cls.WEIGHT_EXACT_REFERENCE
            if "EXACT_AMOUNT" in supporting_signals or "SUM_AMOUNT_MATCH" in supporting_signals:
                score += cls.WEIGHT_EXACT_AMOUNT
            if "EXACT_ENTITY" in supporting_signals:
                score += cls.WEIGHT_EXACT_ENTITY
            if "MATCHED_RELATIONSHIP" in supporting_signals:
                score += cls.WEIGHT_MATCHED_RELATIONSHIP
            if evidence_count > 1 or "MULTIPLE_INDEPENDENT_EVIDENCE" in supporting_signals:
                score += cls.WEIGHT_MULTIPLE_EVIDENCE
            if "DATE_COMPATIBILITY" in supporting_signals:
                score += cls.WEIGHT_DATE_COMPATIBILITY
            if not contradicting_signals:
                score += cls.WEIGHT_NO_CONTRADICTIONS

            return round(min(1.0, max(0.85, score)), 2)

        elif status in (ReconciliationStatus.PARTIAL, ReconciliationStatus.PARTIALLY_SETTLED):
            return 0.95 if "EXACT_ENTITY" in supporting_signals else 0.90

        elif status == ReconciliationStatus.CONTRADICTED:
            # High confidence in the presence of the contradiction
            return 0.98 if (has_critical or has_error) else 0.85

        elif status == ReconciliationStatus.AMBIGUOUS:
            return 0.60

        elif status == ReconciliationStatus.UNVERIFIABLE:
            return 0.40

        elif status == ReconciliationStatus.UNMATCHED:
            return 1.00  # Confirmed that no matching counterpart exists

        return 0.50
