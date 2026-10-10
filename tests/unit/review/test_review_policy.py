"""Unit tests for Review Policy Engine."""

import pytest
from backend.controller.models import ControllerActionType, ControllerDecision, ControllerRiskLevel
from backend.review.models import ReviewStatus
from backend.review.policy import ReviewPolicyEngine


def test_review_policy_clean_case() -> None:
    decision = ControllerDecision(
        case_id="CASE-CLEAN",
        risk_level=ControllerRiskLevel.NONE,
        decision=ControllerActionType.CONFIRM_RECONCILIATION,
        requires_human_review=False,
        confidence=1.0,
        reasons=[],
    )
    status, priority, reasons = ReviewPolicyEngine.evaluate_initial_review(decision)
    assert status == ReviewStatus.NOT_REQUIRED
    assert priority == "LOW"


def test_review_policy_critical_case() -> None:
    decision = ControllerDecision(
        case_id="CASE-CRIT",
        risk_level=ControllerRiskLevel.CRITICAL,
        decision=ControllerActionType.VERIFY_ENTITY,
        requires_human_review=True,
        confidence=0.95,
        reasons=["Severe identity conflict"],
    )
    status, priority, reasons = ReviewPolicyEngine.evaluate_initial_review(decision)
    assert status == ReviewStatus.PENDING
    assert priority == "CRITICAL"
    assert "Severe identity conflict" in reasons
