"""Append-only, tamper-evident audit trail with SHA-256 cryptographic chaining."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from backend.review.models import AuditEvent, AuditEventType


class AuditTrail:
    """Manages an append-only, tamper-evident sequence of AuditEvent records per case."""

    @classmethod
    def compute_event_hash(
        cls,
        event_id: str,
        case_id: str,
        review_id: str,
        event_type: AuditEventType,
        actor_id: str,
        timestamp: datetime,
        description: str,
        affected_ids: List[str],
        previous_hash: Optional[str],
    ) -> str:
        """Computes deterministic SHA-256 digest over audit event attributes and previous hash link."""
        payload = {
            "previous_hash": previous_hash or "GENESIS",
            "event_id": event_id,
            "case_id": case_id,
            "review_id": review_id,
            "event_type": event_type.value if hasattr(event_type, "value") else str(event_type),
            "actor_id": actor_id,
            "timestamp": timestamp.isoformat(),
            "description": description,
            "affected_ids": sorted(list(affected_ids)),
        }
        raw = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @classmethod
    def create_event(
        cls,
        case_id: str,
        review_id: str,
        event_type: AuditEventType,
        actor_id: str,
        description: str,
        affected_ids: Optional[List[str]] = None,
        previous_hash: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        """Constructs an AuditEvent with cryptographic hash binding to the preceding event."""
        eid = f"EVT-{uuid.uuid4().hex[:10].upper()}"
        ts = datetime.now(timezone.utc)
        aff_ids = affected_ids or []

        curr_hash = cls.compute_event_hash(
            event_id=eid,
            case_id=case_id,
            review_id=review_id,
            event_type=event_type,
            actor_id=actor_id,
            timestamp=ts,
            description=description,
            affected_ids=aff_ids,
            previous_hash=previous_hash,
        )

        return AuditEvent(
            event_id=eid,
            case_id=case_id,
            review_id=review_id,
            event_type=event_type,
            actor_id=actor_id,
            timestamp=ts,
            description=description,
            affected_ids=aff_ids,
            previous_state_hash=previous_hash,
            current_state_hash=curr_hash,
            metadata=metadata or {},
        )

    @classmethod
    def verify_chain(cls, events: List[AuditEvent]) -> Tuple[bool, str]:
        """Validates that the sequence of events forms an unbroken, un-tampered SHA-256 cryptographic chain."""
        if not events:
            return True, "Audit log is empty (valid genesis state)."

        expected_prev_hash: Optional[str] = None

        for idx, evt in enumerate(events):
            # 1. Verify link to previous event
            if idx == 0:
                if evt.previous_state_hash is not None:
                    return False, f"Genesis event {evt.event_id} must have null previous_state_hash."
            else:
                if evt.previous_state_hash != expected_prev_hash:
                    return (
                        False,
                        f"Hash link broken at event #{idx} ({evt.event_id}). Expected previous_hash {expected_prev_hash}, got {evt.previous_state_hash}.",
                    )

            # 2. Recompute current hash to detect in-place attribute tampering
            recomputed = cls.compute_event_hash(
                event_id=evt.event_id,
                case_id=evt.case_id,
                review_id=evt.review_id,
                event_type=evt.event_type,
                actor_id=evt.actor_id,
                timestamp=evt.timestamp,
                description=evt.description,
                affected_ids=evt.affected_ids,
                previous_hash=evt.previous_state_hash,
            )

            if recomputed != evt.current_state_hash:
                return (
                    False,
                    f"Integrity violation at event #{idx} ({evt.event_id}). Payload hash {evt.current_state_hash} does not match expected {recomputed}.",
                )

            expected_prev_hash = evt.current_state_hash

        return True, f"Cryptographic audit chain verified successfully across {len(events)} events."
