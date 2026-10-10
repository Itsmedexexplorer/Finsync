"""Unit tests for append-only Review Notes."""

import pytest
from backend.case_processing.result import CaseProcessingResult
from backend.review.service import ReviewService


def test_append_only_notes() -> None:
    svc = ReviewService()
    res = CaseProcessingResult(case_id="CASE-NOTES", status="AMBIGUOUS", confidence_score=0.80)
    svc.create_or_get_review(res)
    svc.start_review("CASE-NOTES")

    note1 = svc.add_note("CASE-NOTES", "ctrl_1", "Alice", "First inspection: Bank statement verified.")
    note2 = svc.add_note("CASE-NOTES", "ctrl_2", "Bob", "Second inspection: UTR discrepancy confirmed.")

    review = svc.get_review("CASE-NOTES")
    assert len(review.notes) == 2
    assert review.notes[0].content == "First inspection: Bank statement verified."
    assert review.notes[1].content == "Second inspection: UTR discrepancy confirmed."
    assert review.notes[0].reviewer_name == "Alice"
    assert review.notes[1].reviewer_name == "Bob"
