"""Unit tests for Review Workflow State Machine."""

import pytest
from backend.review.models import ReviewStatus
from backend.review.workflow import InvalidStateTransitionError, ReviewWorkflow


def test_valid_state_transitions() -> None:
    # NOT_REQUIRED -> PENDING
    ReviewWorkflow.validate_transition(ReviewStatus.NOT_REQUIRED, ReviewStatus.PENDING)
    # PENDING -> IN_PROGRESS
    ReviewWorkflow.validate_transition(ReviewStatus.PENDING, ReviewStatus.IN_PROGRESS)
    # IN_PROGRESS -> RESOLVED
    ReviewWorkflow.validate_transition(ReviewStatus.IN_PROGRESS, ReviewStatus.RESOLVED)
    # RESOLVED -> CLOSED
    ReviewWorkflow.validate_transition(ReviewStatus.RESOLVED, ReviewStatus.CLOSED)
    # IN_PROGRESS -> ESCALATED -> IN_PROGRESS
    ReviewWorkflow.validate_transition(ReviewStatus.IN_PROGRESS, ReviewStatus.ESCALATED)
    ReviewWorkflow.validate_transition(ReviewStatus.ESCALATED, ReviewStatus.IN_PROGRESS)


def test_invalid_state_transitions_rejected() -> None:
    # PENDING -> CLOSED (must fail)
    with pytest.raises(InvalidStateTransitionError):
        ReviewWorkflow.validate_transition(ReviewStatus.PENDING, ReviewStatus.CLOSED)

    # CLOSED -> IN_PROGRESS (must fail)
    with pytest.raises(InvalidStateTransitionError):
        ReviewWorkflow.validate_transition(ReviewStatus.CLOSED, ReviewStatus.IN_PROGRESS)

    # RESOLVED -> PENDING (must fail)
    with pytest.raises(InvalidStateTransitionError):
        ReviewWorkflow.validate_transition(ReviewStatus.RESOLVED, ReviewStatus.PENDING)


def test_is_modifiable_and_terminal() -> None:
    assert ReviewWorkflow.is_modifiable(ReviewStatus.PENDING) is True
    assert ReviewWorkflow.is_modifiable(ReviewStatus.IN_PROGRESS) is True
    assert ReviewWorkflow.is_modifiable(ReviewStatus.RESOLVED) is True
    assert ReviewWorkflow.is_modifiable(ReviewStatus.CLOSED) is False

    assert ReviewWorkflow.is_terminal(ReviewStatus.CLOSED) is True
    assert ReviewWorkflow.is_terminal(ReviewStatus.IN_PROGRESS) is False
