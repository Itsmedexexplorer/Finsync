"""Deterministic Finite State Machine for Case Review Workflows."""

from __future__ import annotations

from typing import Dict, Set
from backend.review.models import ReviewStatus


class InvalidStateTransitionError(ValueError):
    """Raised when an illegal review workflow state transition is attempted."""
    def __init__(self, current: ReviewStatus, target: ReviewStatus, message: str = ""):
        msg = message or f"Illegal review transition from '{current.value}' to '{target.value}'."
        super().__init__(msg)
        self.current = current
        self.target = target


class ReviewWorkflow:
    """Deterministic state machine governing human case investigation lifecycles."""

    # Explicit allowed state transition map
    _ALLOWED_TRANSITIONS: Dict[ReviewStatus, Set[ReviewStatus]] = {
        ReviewStatus.NOT_REQUIRED: {
            ReviewStatus.PENDING,
            ReviewStatus.IN_PROGRESS,
            ReviewStatus.CLOSED,
        },
        ReviewStatus.PENDING: {
            ReviewStatus.IN_PROGRESS,
            ReviewStatus.ESCALATED,
        },
        ReviewStatus.IN_PROGRESS: {
            ReviewStatus.RESOLVED,
            ReviewStatus.ESCALATED,
            ReviewStatus.PENDING,
            ReviewStatus.CLOSED,
        },
        ReviewStatus.ESCALATED: {
            ReviewStatus.IN_PROGRESS,
            ReviewStatus.RESOLVED,
            ReviewStatus.CLOSED,
        },
        ReviewStatus.RESOLVED: {
            ReviewStatus.CLOSED,
            ReviewStatus.IN_PROGRESS,  # Reopen if new evidence surfaces prior to close
        },
        ReviewStatus.CLOSED: set(),  # Terminal state: immutable
    }

    @classmethod
    def validate_transition(cls, current: ReviewStatus, target: ReviewStatus) -> None:
        """Validates if transitioning from current to target is legally permissible."""
        if current == target:
            return

        allowed = cls._ALLOWED_TRANSITIONS.get(current, set())
        if target not in allowed:
            raise InvalidStateTransitionError(
                current=current,
                target=target,
                message=f"Cannot transition review status from '{current.value}' to '{target.value}'. Allowed transitions: {[s.value for s in allowed]}."
            )

    @classmethod
    def is_modifiable(cls, status: ReviewStatus) -> bool:
        """Checks if a review can still accept notes, evidence reviews, or action modifications."""
        return status != ReviewStatus.CLOSED

    @classmethod
    def is_terminal(cls, status: ReviewStatus) -> bool:
        """Returns True if the review is in terminal closed state."""
        return status == ReviewStatus.CLOSED
