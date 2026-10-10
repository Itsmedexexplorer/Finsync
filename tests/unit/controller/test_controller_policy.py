"""Unit tests for Controller Policy Engine."""

import pytest
from backend.controller.models import ControllerActionType, ControllerRiskLevel
from backend.controller.policy import ControllerPolicyEngine
from backend.controller.signals import ControllerSignal, ControllerSignalType


def test_policy_critical_entity_mismatch() -> None:
    signals = [
        ControllerSignal(
            signal_type=ControllerSignalType.ENTITY_MISMATCH,
            severity=ControllerRiskLevel.CRITICAL,
            message="Entity mismatch: expected Rahul, observed Rohit",
        )
    ]
    risk, action, review_req, reasons = ControllerPolicyEngine.evaluate(signals)
    assert risk == ControllerRiskLevel.CRITICAL
    assert action == ControllerActionType.VERIFY_ENTITY
    assert review_req is True


def test_policy_high_amount_mismatch() -> None:
    signals = [
        ControllerSignal(
            signal_type=ControllerSignalType.AMOUNT_MISMATCH,
            severity=ControllerRiskLevel.HIGH,
            message="Amount mismatch: 20k vs 18k",
        )
    ]
    risk, action, review_req, reasons = ControllerPolicyEngine.evaluate(signals)
    assert risk == ControllerRiskLevel.HIGH
    assert action == ControllerActionType.INVESTIGATE_CONTRADICTION
    assert review_req is True


def test_policy_partial_settlement() -> None:
    signals = [
        ControllerSignal(
            signal_type=ControllerSignalType.PARTIAL_SETTLEMENT,
            severity=ControllerRiskLevel.MEDIUM,
            message="Partial settlement: 12k of 20k",
            amount=8000.0,
        )
    ]
    risk, action, review_req, reasons = ControllerPolicyEngine.evaluate(signals)
    assert risk == ControllerRiskLevel.MEDIUM
    assert action == ControllerActionType.VERIFY_TRANSACTION
    assert review_req is True


def test_policy_confirmed_clean_case() -> None:
    signals = [
        ControllerSignal(
            signal_type=ControllerSignalType.CONFIRMED_RECONCILIATION,
            severity=ControllerRiskLevel.NONE,
            message="100% matched",
        )
    ]
    risk, action, review_req, reasons = ControllerPolicyEngine.evaluate(signals)
    assert risk == ControllerRiskLevel.NONE
    assert action == ControllerActionType.CONFIRM_RECONCILIATION
    assert review_req is False
