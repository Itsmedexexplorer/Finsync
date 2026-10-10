"""Unit tests for Review Decision Separation vs Deterministic Truth."""

import pytest
from backend.case_processing.result import CaseProcessingResult
from backend.review.models import ReviewDecision, ReviewStatus
from backend.review.service import ReviewService


def test_human_decision_does_not_mutate_deterministic_reconciliation() -> None:
    svc = ReviewService()
    res = CaseProcessingResult(
        case_id="CASE-DEC-01",
        status="CONTRADICTED",
        confidence_score=0.98,
    )
    svc.create_or_get_review(res)
    svc.start_review("CASE-DEC-01")

    # Reviewer confirms case via executive override
    svc.record_decision("CASE-DEC-01", ReviewDecision.CONFIRMED, "ctrl_1", "Lead Controller", "Override granted.")

    review = svc.get_review("CASE-DEC-01")

    # Invariants:
    # 1. Deterministic status remains CONTRADICTED
    assert res.status == "CONTRADICTED"
    # 2. Human review decision is CONFIRMED
    assert review.decision == ReviewDecision.CONFIRMED
    # 3. Review workflow status is RESOLVED
    assert review.status == ReviewStatus.RESOLVED


def test_human_decision_on_ambiguous_case() -> None:
    svc = ReviewService()
    res = CaseProcessingResult(
        case_id="CASE-DEC-02",
        status="AMBIGUOUS",
        confidence_score=0.75,
    )
    svc.create_or_get_review(res)
    svc.start_review("CASE-DEC-02")

    svc.record_decision("CASE-DEC-02", ReviewDecision.NEEDS_MORE_EVIDENCE, "ctrl_1", "Lead Controller")
    assert res.status == "AMBIGUOUS"
    review = svc.get_review("CASE-DEC-02")
    assert review.decision == ReviewDecision.NEEDS_MORE_EVIDENCE
