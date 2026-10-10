"""Unit tests for Action Prioritization."""

import pytest
from backend.controller.models import ControllerActionType
from backend.controller.prioritizer import ActionPrioritizer
from backend.controller.signals import ControllerSignal, ControllerSignalType, ControllerRiskLevel


def test_action_prioritization_ordering() -> None:
    signals = [
        ControllerSignal(
            signal_type=ControllerSignalType.PARTIAL_SETTLEMENT,
            severity=ControllerRiskLevel.MEDIUM,
            message="Partial payment 12k of 20k",
            affected_ids=["TXN-01"],
        ),
        ControllerSignal(
            signal_type=ControllerSignalType.ENTITY_MISMATCH,
            severity=ControllerRiskLevel.CRITICAL,
            message="Entity mismatch: Rahul vs Rohit",
            affected_ids=["CLM-01", "TXN-01"],
        ),
        ControllerSignal(
            signal_type=ControllerSignalType.AMOUNT_MISMATCH,
            severity=ControllerRiskLevel.HIGH,
            message="Amount mismatch: 20k vs 18k",
            affected_ids=["CLM-01", "TXN-01"],
        ),
    ]

    recommendations = ActionPrioritizer.prioritize(signals)
    assert len(recommendations) == 3
    # Top priority must be entity mismatch (priority 1)
    assert recommendations[0].priority == 1
    assert recommendations[0].action_type == ControllerActionType.VERIFY_ENTITY
    # Second priority must be amount mismatch (priority 2)
    assert recommendations[1].priority == 2
    assert recommendations[1].action_type == ControllerActionType.INVESTIGATE_CONTRADICTION
    # Third priority must be partial settlement (priority 4)
    assert recommendations[2].priority == 4
    assert recommendations[2].action_type == ControllerActionType.VERIFY_TRANSACTION
