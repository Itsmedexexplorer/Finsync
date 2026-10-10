"""Unit tests for Audit Event creation and logging."""

import pytest
from backend.review.audit import AuditTrail
from backend.review.models import AuditEventType


def test_audit_event_generation_and_hashing() -> None:
    event = AuditTrail.create_event(
        case_id="CASE-AUD-01",
        review_id="REV-01",
        event_type=AuditEventType.REVIEW_CREATED,
        actor_id="system",
        description="Case review created in status PENDING.",
        affected_ids=["REV-01", "CASE-AUD-01"],
        previous_hash=None,
    )

    assert event.event_id.startswith("EVT-")
    assert event.previous_state_hash is None
    assert len(event.current_state_hash) == 64  # SHA-256 length
    assert event.event_type == AuditEventType.REVIEW_CREATED
