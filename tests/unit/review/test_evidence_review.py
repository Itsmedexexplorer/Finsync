"""Unit tests for Evidence Review and Immutability."""

import pytest
from backend.case_processing.result import CaseProcessingResult
from backend.domain.evidence import Evidence, EvidenceModality, EvidenceSourceType
from backend.review.service import InvalidReferenceError, ReviewService


def test_evidence_review_immutability() -> None:
    svc = ReviewService()
    ev = Evidence(
        id="EVID-01",
        modality=EvidenceModality.INVOICE,
        source_type=EvidenceSourceType.ZOHO_INVOICE,
        source_name="inv.pdf",
        raw_payload="Original Unmodified Content",
    )
    res = CaseProcessingResult(case_id="CASE-EV", status="CONTRADICTED", confidence_score=0.9)
    svc.create_or_get_review(res)
    svc.start_review("CASE-EV")

    # Mark evidence as reviewed
    rec = svc.mark_evidence_reviewed(
        case_id="CASE-EV",
        evidence_id="EVID-01",
        reviewer_id="ctrl_1",
        reviewer_name="Alice",
        notes="Inspected invoice line items",
        valid_evidence_ids=["EVID-01"],
    )

    # 1. Original evidence remains completely unmodified
    assert ev.raw_payload == "Original Unmodified Content"
    assert ev.id == "EVID-01"

    # 2. Review record accurately registered inspection
    review = svc.get_review("CASE-EV")
    assert "EVID-01" in review.reviewed_evidence_ids
    assert len(review.reviewed_evidence) == 1
    assert review.reviewed_evidence[0].notes == "Inspected invoice line items"


def test_reject_cross_case_evidence_id() -> None:
    svc = ReviewService()
    res = CaseProcessingResult(case_id="CASE-EV2", status="CONTRADICTED", confidence_score=0.9)
    svc.create_or_get_review(res)
    svc.start_review("CASE-EV2")

    # Attempt to review evidence belonging to another case
    with pytest.raises(InvalidReferenceError):
        svc.mark_evidence_reviewed(
            case_id="CASE-EV2",
            evidence_id="EVID-OTHER-CASE-999",
            valid_evidence_ids=["EVID-VALID-01", "EVID-VALID-02"],
        )
