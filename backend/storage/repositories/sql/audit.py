"""SQL implementation of AuditRepository (STRICTLY APPEND-ONLY)."""

from __future__ import annotations

import json
from typing import List, Optional

from backend.storage.models import AuditEventRecord
from backend.storage.repositories.base import AuditRepository


class SQLAuditRepository(AuditRepository):
    """SQLite/SQL repository for immutable Audit Events."""

    def append(self, event: AuditEventRecord) -> AuditEventRecord:
        sql = """
        INSERT INTO audit_events (
            event_id, case_id, review_id, event_type, actor_id,
            timestamp, description, affected_ids, previous_state_hash,
            current_state_hash, sequence_number, metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        self.conn.execute(
            sql,
            (
                event.event_id,
                event.case_id,
                event.review_id,
                event.event_type,
                event.actor_id,
                event.timestamp,
                event.description,
                json.dumps(event.affected_ids),
                event.previous_state_hash,
                event.current_state_hash,
                event.sequence_number,
                json.dumps(event.metadata),
            ),
        )
        return event

    def list_by_case(self, case_id: str) -> List[AuditEventRecord]:
        sql = "SELECT * FROM audit_events WHERE case_id = ? ORDER BY sequence_number ASC, timestamp ASC;"
        cursor = self.conn.execute(sql, (case_id,))
        return [self._row_to_record(r) for r in cursor.fetchall()]

    def get_latest_event(self, case_id: str) -> Optional[AuditEventRecord]:
        sql = "SELECT * FROM audit_events WHERE case_id = ? ORDER BY sequence_number DESC, timestamp DESC LIMIT 1;"
        cursor = self.conn.execute(sql, (case_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return self._row_to_record(row)

    def _row_to_record(self, row: dict) -> AuditEventRecord:
        return AuditEventRecord(
            event_id=row["event_id"],
            case_id=row["case_id"],
            review_id=row["review_id"],
            event_type=row["event_type"],
            actor_id=row["actor_id"],
            timestamp=row["timestamp"],
            description=row["description"],
            affected_ids=json.loads(row["affected_ids"]) if row["affected_ids"] else [],
            previous_state_hash=row["previous_state_hash"],
            current_state_hash=row["current_state_hash"],
            sequence_number=row["sequence_number"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )
