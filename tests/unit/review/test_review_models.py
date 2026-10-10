"""Unit tests for Review Domain Models."""

import pytest
from backend.review.models import (
    AuditEvent,
    AuditEventType,
    EvidenceReviewRecord,
    ReviewAction,
    ReviewActionStatus,
    ReviewActionType,
    ReviewDecision,
    ReviewNote,
    ReviewRecord,
    ReviewStatus,
)


def test_review_status_and_decisions() -> None:
    assert ReviewStatus.PENDING.value == "PENDING"
    assert ReviewStatus.IN_PROGRESS.value == "IN_PROGRESS"
    assert ReviewStatus.RESOLVED.value == "RESOLVED"
    assert ReviewStatus.CLOSED.value == "CLOSED"

    assert ReviewDecision.CONFIRMED.value == "CONFIRMED"
    assert ReviewDecision.NEEDS_MORE_EVIDENCE.value == "NEEDS_MORE_EVIDENCE"
    assert ReviewDecision.ACKNOWLEDGED.value == "ACKNOWLEDGED"


def test_review_note_model() -> None:
    note = ReviewNote(
        note_id="NOTE-01",
        reviewer_id="ctrl_01",
        reviewer_name="Senior Controller",
        content="Bank statement verified against payment receipt.",
    )
    assert note.note_id == "NOTE-01"
    assert note.reviewer_id == "ctrl_01"
    assert note.reviewer_name == "Senior Controller"


def test_evidence_review_record_model() -> None:
    rec = EvidenceReviewRecord(
        evidence_id="EVID-101",
        reviewer_id="ctrl_01",
        notes="All fields match invoice line items.",
    )
    assert rec.evidence_id == "EVID-101"
    assert rec.notes == "All fields match invoice line items."


def test_review_action_model() -> None:
    action = ReviewAction(
        action_id="ACT-01",
        action_type=ReviewActionType.VERIFY_ENTITY,
        title="Verify Counterparty GSTIN",
        priority=1,
        status=ReviewActionStatus.PENDING,
        supporting_ids=["CLM-01", "TXN-01"],
    )
    assert action.action_id == "ACT-01"
    assert action.priority == 1
    assert len(action.supporting_ids) == 2
