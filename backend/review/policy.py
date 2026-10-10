"""Review Policy Engine mapping Controller decisions to Review initialization settings."""

from __future__ import annotations

from typing import Dict, List, Tuple
from backend.controller.models import ControllerDecision, ControllerRiskLevel
from backend.review.models import ReviewStatus


class ReviewPolicyEngine:
    """Evaluates a ControllerDecision to determine if human review is mandated, its initial state, and priority."""

    @classmethod
    def evaluate_initial_review(cls, decision: ControllerDecision) -> Tuple[ReviewStatus, str, List[str]]:
        """Returns (initial_status, recommended_priority, initial_reasons).

        Strict Invariant: Never overrides or alters deterministic controller facts.
        """
        if not decision.requires_human_review:
            return (
                ReviewStatus.NOT_REQUIRED,
                "LOW",
                ["All claims and transactions reconciled with zero discrepancies; review is not required."],
            )

        # Review is required
        priority = "MEDIUM"
        if decision.risk_level == ControllerRiskLevel.CRITICAL:
            priority = "CRITICAL"
        elif decision.risk_level == ControllerRiskLevel.HIGH:
            priority = "HIGH"
        elif decision.risk_level == ControllerRiskLevel.MEDIUM:
            priority = "MEDIUM"
        elif decision.risk_level == ControllerRiskLevel.LOW:
            priority = "LOW"

        reasons = list(decision.reasons) if decision.reasons else ["Deterministic discrepancies or ambiguities detected."]
        return (ReviewStatus.PENDING, priority, reasons)
