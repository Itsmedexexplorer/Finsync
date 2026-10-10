"""SQL implementation of DeduplicationRepository."""

from __future__ import annotations

import json
from typing import List

from backend.storage.models import DeduplicationGroupRecord
from backend.storage.repositories.base import DeduplicationRepository


class SQLDeduplicationRepository(DeduplicationRepository):
    """SQLite/SQL repository for Deduplication Group records."""

    def create(self, record: DeduplicationGroupRecord) -> DeduplicationGroupRecord:
        sql = """
        INSERT INTO deduplication_groups (
            id, case_id, group_type, member_evidence_ids, member_claim_ids,
            canonical_event_id, confidence, reason, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            group_type=excluded.group_type,
            member_evidence_ids=excluded.member_evidence_ids,
            member_claim_ids=excluded.member_claim_ids,
            canonical_event_id=excluded.canonical_event_id,
            confidence=excluded.confidence,
            reason=excluded.reason;
        """
        self.conn.execute(
            sql,
            (
                record.id,
                record.case_id,
                record.group_type,
                json.dumps(record.member_evidence_ids),
                json.dumps(record.member_claim_ids),
                record.canonical_event_id,
                record.confidence,
                record.reason,
                record.created_at,
            ),
        )
        return record

    def create_batch(self, records: List[DeduplicationGroupRecord]) -> List[DeduplicationGroupRecord]:
        for r in records:
            self.create(r)
        return records

    def list_by_case(self, case_id: str) -> List[DeduplicationGroupRecord]:
        sql = "SELECT * FROM deduplication_groups WHERE case_id = ? ORDER BY created_at ASC;"
        cursor = self.conn.execute(sql, (case_id,))
        return [self._row_to_record(r) for r in cursor.fetchall()]

    def _row_to_record(self, row: dict) -> DeduplicationGroupRecord:
        return DeduplicationGroupRecord(
            id=row["id"],
            case_id=row["case_id"],
            group_type=row["group_type"],
            member_evidence_ids=json.loads(row["member_evidence_ids"]) if row["member_evidence_ids"] else [],
            member_claim_ids=json.loads(row["member_claim_ids"]) if row["member_claim_ids"] else [],
            canonical_event_id=row["canonical_event_id"],
            confidence=row["confidence"],
            reason=row["reason"] or "",
            created_at=row["created_at"],
        )
