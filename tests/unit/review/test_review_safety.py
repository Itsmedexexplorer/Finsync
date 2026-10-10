"""Unit tests for Review Subsystem Safety Invariants."""

import pytest
from backend.case_processing.result import CaseProcessingResult
from backend.review.models import ReviewStatus
from backend.review.service import (
    CaseReviewNotFoundError,
    InvalidReferenceError,
    ReviewClosedError,
    ReviewService,
)
from backend.review.workflow import InvalidStateTransitionError


def test_safety_non_existent_case() -> None:
    svc = ReviewService()
    with pytest.raises(CaseReviewNotFoundError):
        svc.start_review("NON-EXISTENT-CASE")


def test_safety_closed_review_immutable() -> None:
    svc = ReviewService()
    res = CaseProcessingResult(case_id="CASE-SAFE", status="CONTRADICTED", confidence_score=0.9)
    svc.create_or_get_review(res)
    svc.start_review("CASE-SAFE")
    svc.close("CASE-SAFE")

    # Modifying closed review must be rejected
    with pytest.raises(ReviewClosedError):
        svc.add_note("CASE-SAFE", "ctrl_1", "Alice", "Note after close")


def test_safety_invalid_action_id() -> None:
    svc = ReviewService()
    res = CaseProcessingResult(case_id="CASE-SAFE2", status="CONTRADICTED", confidence_score=0.9)
    svc.create_or_get_review(res)
    svc.start_review("CASE-SAFE2")

    with pytest.raises(InvalidReferenceError):
        svc.complete_action("CASE-SAFE2", "ACT-FAKE-999")
