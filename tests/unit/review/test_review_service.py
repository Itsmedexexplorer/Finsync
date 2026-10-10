"""Unit tests for ReviewService operations."""

import pytest
from backend.case_processing.result import CaseProcessingResult
from backend.review.models import ReviewActionType, ReviewDecision, ReviewStatus
from backend.review.service import ReviewClosedError, ReviewService


@pytest.fixture
def service() -> ReviewService:
    return ReviewService()


def test_create_and_lifecycle_flow(service: ReviewService) -> None:
    res = CaseProcessingResult(
        case_id="CASE-LIFECYCLE-01",
        status="CONTRADICTED",
        confidence_score=0.95,
    )
    # 1. Create
    review = service.create_or_get_review(res)
    assert review.case_id == "CASE-LIFECYCLE-01"
    assert review.status == ReviewStatus.PENDING

    # 2. Start
    service.start_review("CASE-LIFECYCLE-01", "ctrl_1", "Lead Controller")
    assert review.status == ReviewStatus.IN_PROGRESS

    # 3. Add Action
    act = service.create_action("CASE-LIFECYCLE-01", ReviewActionType.VERIFY_ENTITY, "Check PAN card")
    assert len(review.actions) == 1

    # 4. Complete Action
    service.complete_action("CASE-LIFECYCLE-01", act.action_id, "ctrl_1", "PAN matches")
    assert review.actions[0].status.value == "COMPLETED"

    # 5. Record Decision
    service.record_decision("CASE-LIFECYCLE-01", ReviewDecision.ACKNOWLEDGED, "ctrl_1", "Lead Controller", "Reviewed.")
    assert review.status == ReviewStatus.RESOLVED

    # 6. Close
    service.close("CASE-LIFECYCLE-01", "ctrl_1", "Lead Controller")
    assert review.status == ReviewStatus.CLOSED

    # 7. Modifying closed review must fail
    with pytest.raises(ReviewClosedError):
        service.add_note("CASE-LIFECYCLE-01", "ctrl_1", "Lead Controller", "Late note")
