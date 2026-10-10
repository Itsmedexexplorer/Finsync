"""Unit tests for Controller Decision Models."""

import pytest
from backend.controller.models import (
    ControllerActionType,
    ControllerBrief,
    ControllerDecision,
    ControllerRecommendation,
    ControllerRiskLevel,
)


def test_controller_risk_levels() -> None:
    assert ControllerRiskLevel.CRITICAL.value == "CRITICAL"
    assert ControllerRiskLevel.HIGH.value == "HIGH"
    assert ControllerRiskLevel.MEDIUM.value == "MEDIUM"
    assert ControllerRiskLevel.LOW.value == "LOW"
    assert ControllerRiskLevel.NONE.value == "NONE"


def test_controller_recommendation_model() -> None:
    rec = ControllerRecommendation(
        action_type=ControllerActionType.VERIFY_ENTITY,
        priority=1,
        title="Verify Counterparty Identity",
        explanation="Identity mismatch detected",
        rationale="Claim references Rahul Kumar, Bank credit from Rohit Sharma",
        supporting_ids=["CLM-01", "TXN-01"],
        blocking_issue=True,
        requires_human_action=True,
    )
    assert rec.priority == 1
    assert rec.blocking_issue is True
    assert len(rec.supporting_ids) == 2


def test_controller_decision_model() -> None:
    dec = ControllerDecision(
        case_id="CASE-001",
        risk_level=ControllerRiskLevel.CRITICAL,
        decision=ControllerActionType.INVESTIGATE_CONTRADICTION,
        requires_human_review=True,
        confidence=0.98,
        reasons=["Amount mismatch between invoice and bank receipt."],
        supporting_evidence_ids=["EVID-01"],
        supporting_claim_ids=["CLM-01"],
        supporting_transaction_ids=["TXN-01"],
        supporting_discrepancy_ids=["DISC-01"],
    )
    assert dec.case_id == "CASE-001"
    assert dec.requires_human_review is True
    assert dec.risk_level == ControllerRiskLevel.CRITICAL
