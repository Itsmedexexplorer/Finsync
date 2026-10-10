"""Unit tests for Review Action Generation."""

import pytest
from backend.controller.models import ControllerActionType, ControllerRecommendation
from backend.review.actions import ReviewActionFactory
from backend.review.models import ReviewActionType


def test_action_factory_from_recommendations() -> None:
    recs = [
        ControllerRecommendation(
            action_type=ControllerActionType.VERIFY_ENTITY,
            priority=1,
            title="Verify Entity Identity",
            explanation="Identity mismatch detected",
            rationale="Expected Rahul, observed Rohit",
            supporting_ids=["CLM-01", "TXN-01"],
            blocking_issue=True,
            requires_human_action=True,
        ),
        ControllerRecommendation(
            action_type=ControllerActionType.INVESTIGATE_CONTRADICTION,
            priority=2,
            title="Audit Amount Contradiction",
            explanation="20k vs 18k",
            rationale="Mismatch",
            supporting_ids=["DISC-01"],
            blocking_issue=True,
            requires_human_action=True,
        ),
    ]

    actions = ReviewActionFactory.from_recommendations(recs)
    assert len(actions) == 2
    assert actions[0].action_type == ReviewActionType.VERIFY_ENTITY
    assert actions[0].supporting_ids == ["CLM-01", "TXN-01"]
    assert actions[1].action_type == ReviewActionType.INVESTIGATE_CONTRADICTION
