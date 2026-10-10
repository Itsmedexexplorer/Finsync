"""Unit tests for cryptographic audit chain verification and tamper detection."""

import pytest
from backend.case_processing.result import CaseProcessingResult
from backend.review.audit import AuditTrail
from backend.review.models import ReviewDecision
from backend.review.service import ReviewService


def test_audit_chain_validity() -> None:
    svc = ReviewService()
    res = CaseProcessingResult(case_id="CASE-CHAIN", status="CONTRADICTED", confidence_score=0.9)
    svc.create_or_get_review(res)
    svc.start_review("CASE-CHAIN")
    svc.add_note("CASE-CHAIN", "ctrl_1", "Alice", "Note 1")
    svc.record_decision("CASE-CHAIN", ReviewDecision.ACKNOWLEDGED, "ctrl_1", "Alice")

    is_valid, msg = svc.validate_audit_chain("CASE-CHAIN")
    assert is_valid is True
    assert "verified successfully" in msg.lower()


def test_tampered_audit_chain_detected() -> None:
    svc = ReviewService()
    res = CaseProcessingResult(case_id="CASE-TAMPER", status="CONTRADICTED", confidence_score=0.9)
    svc.create_or_get_review(res)
    svc.start_review("CASE-TAMPER")
    svc.add_note("CASE-TAMPER", "ctrl_1", "Alice", "Original Note")

    events = svc.get_audit_log("CASE-TAMPER")
    valid_orig, _ = AuditTrail.verify_chain(events)
    assert valid_orig is True

    # Tamper with an event payload
    tampered_events = [e.model_copy(deep=True) for e in events]
    tampered_events[1].description = "Tampered unauthorized text"

    valid_tampered, error_msg = AuditTrail.verify_chain(tampered_events)
    assert valid_tampered is False
    assert "integrity violation" in error_msg.lower()
