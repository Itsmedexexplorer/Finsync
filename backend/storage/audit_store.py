"""Persistent Audit Store with Cryptographic SHA-256 Hash Chaining (Day 16).

Ensures audit events are stored persistently, sequentially, and immutably.
Verifies complete cryptographic chain integrity and detects database-level tampering.
"""

from __future__ import annotations

import hashlib
import json
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from backend.review.models import AuditEvent, AuditEventType
from backend.storage.database import DatabaseConnection, DatabaseEngine, get_database_engine
from backend.storage.models import AuditEventRecord
from backend.storage.repositories.sql.audit import SQLAuditRepository

GENESIS_HASH = "0" * 64


class AuditChainCorruptedError(Exception):
    """Raised when an audit chain verification fails due to tampering or sequence breakage."""
    pass


class PersistentAuditStore:
    """Persistent, tamper-evident audit store backed by SQL storage."""

    def __init__(self, engine: Optional[DatabaseEngine] = None) -> None:
        self.engine = engine or get_database_engine()
        self._lock = threading.RLock()

    @staticmethod
    def compute_event_hash(
        prev_hash: str,
        event_id: str,
        case_id: str,
        event_type: str,
        actor_id: str,
        timestamp: str,
        description: str,
        affected_ids: List[str],
        metadata: Dict[str, Any],
    ) -> str:
        """Computes deterministic SHA-256 state hash for an event chained to prev_hash."""
        normalized_affected = sorted(affected_ids or [])
        meta_json = json.dumps(metadata or {}, sort_keys=True)
        raw_payload = (
            f"{prev_hash}|{event_id}|{case_id}|{event_type}|{actor_id}|"
            f"{timestamp}|{description}|{','.join(normalized_affected)}|{meta_json}"
        )
        return hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()

    def append_event(
        self,
        case_id: str,
        event_type: Union[AuditEventType, str],
        actor_id: str,
        description: str,
        affected_ids: Optional[List[str]] = None,
        review_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        conn: Optional[DatabaseConnection] = None,
    ) -> AuditEventRecord:
        """Appends a new immutable audit event to the persistent chain for the case."""
        affected = affected_ids or []
        meta = metadata or {}
        event_type_str = event_type.value if hasattr(event_type, "value") else str(event_type)
        ts = datetime.now(timezone.utc).isoformat()
        event_id = f"AUD-{case_id[:8]}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}-{uuid.uuid4().hex[:6]}"

        def _do_append(db_conn: DatabaseConnection) -> AuditEventRecord:
            repo = SQLAuditRepository(db_conn)
            latest = repo.get_latest_event(case_id)

            if latest is None:
                prev_hash = GENESIS_HASH
                seq = 1
            else:
                prev_hash = latest.current_state_hash
                seq = latest.sequence_number + 1

            current_hash = self.compute_event_hash(
                prev_hash=prev_hash,
                event_id=event_id,
                case_id=case_id,
                event_type=event_type_str,
                actor_id=actor_id,
                timestamp=ts,
                description=description,
                affected_ids=affected,
                metadata=meta,
            )

            record = AuditEventRecord(
                event_id=event_id,
                case_id=case_id,
                review_id=review_id,
                event_type=event_type_str,
                actor_id=actor_id,
                timestamp=ts,
                description=description,
                affected_ids=affected,
                previous_state_hash=prev_hash,
                current_state_hash=current_hash,
                sequence_number=seq,
                metadata=meta,
            )
            return repo.append(record)

        with self._lock:
            if conn is not None:
                return _do_append(conn)
            else:
                with self.engine.transaction() as tx_conn:
                    return _do_append(tx_conn)

    def get_events(self, case_id: str, conn: Optional[DatabaseConnection] = None) -> List[AuditEventRecord]:
        """Returns all persistent audit events for a case in sequence order."""
        if conn is not None:
            return SQLAuditRepository(conn).list_by_case(case_id)
        with self.engine.get_connection() as db_conn:
            return SQLAuditRepository(db_conn).list_by_case(case_id)

    def verify_chain(self, case_id: str, conn: Optional[DatabaseConnection] = None) -> Tuple[bool, List[str]]:
        """Verifies full cryptographic chain integrity. Returns (is_valid, error_list)."""
        events = self.get_events(case_id, conn=conn)
        if not events:
            return True, []

        errors: List[str] = []
        expected_prev_hash = GENESIS_HASH

        for i, ev in enumerate(events, start=1):
            # 1. Sequence Check
            if ev.sequence_number != i:
                errors.append(
                    f"Sequence broken at event {ev.event_id}: expected sequence {i}, observed {ev.sequence_number}"
                )

            # 2. Previous Hash Check
            if ev.previous_state_hash != expected_prev_hash:
                errors.append(
                    f"Hash link mismatch at event {ev.event_id} (seq {ev.sequence_number}): "
                    f"expected prev_hash {expected_prev_hash}, observed {ev.previous_state_hash}"
                )

            # 3. Recalculate Current State Hash
            expected_current_hash = self.compute_event_hash(
                prev_hash=ev.previous_state_hash,
                event_id=ev.event_id,
                case_id=ev.case_id,
                event_type=ev.event_type,
                actor_id=ev.actor_id,
                timestamp=ev.timestamp,
                description=ev.description,
                affected_ids=ev.affected_ids,
                metadata=ev.metadata,
            )

            if ev.current_state_hash != expected_current_hash:
                errors.append(
                    f"Tampered state hash detected at event {ev.event_id} (seq {ev.sequence_number}): "
                    f"recalculated {expected_current_hash}, stored {ev.current_state_hash}"
                )

            expected_prev_hash = ev.current_state_hash

        is_valid = len(errors) == 0
        return is_valid, errors
