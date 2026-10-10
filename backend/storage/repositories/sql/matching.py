"""SQL implementation of MatchRepository."""

from __future__ import annotations

import json
from typing import List

from backend.storage.models import MatchRelationshipRecord
from backend.storage.repositories.base import MatchRepository


class SQLMatchRepository(MatchRepository):
    """SQLite/SQL repository for Match Relationship records."""

    def create(self, record: MatchRelationshipRecord) -> MatchRelationshipRecord:
        sql = """
        INSERT INTO match_relationships (
            id, case_id, relationship_type, status, source_claim_ids,
            target_transaction_ids, matched_amount, target_amount, score,
            matched_signals, conflicting_signals, explanation, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            relationship_type=excluded.relationship_type,
            status=excluded.status,
            source_claim_ids=excluded.source_claim_ids,
            target_transaction_ids=excluded.target_transaction_ids,
            matched_amount=excluded.matched_amount,
            target_amount=excluded.target_amount,
            score=excluded.score,
            matched_signals=excluded.matched_signals,
            conflicting_signals=excluded.conflicting_signals,
            explanation=excluded.explanation;
        """
        self.conn.execute(
            sql,
            (
                record.id,
                record.case_id,
                record.relationship_type,
                record.status,
                json.dumps(record.source_claim_ids),
                json.dumps(record.target_transaction_ids),
                record.matched_amount,
                record.target_amount,
                record.score,
                json.dumps(record.matched_signals),
                json.dumps(record.conflicting_signals),
                record.explanation,
                record.created_at,
            ),
        )
        return record

    def create_batch(self, records: List[MatchRelationshipRecord]) -> List[MatchRelationshipRecord]:
        for r in records:
            self.create(r)
        return records

    def list_by_case(self, case_id: str) -> List[MatchRelationshipRecord]:
        sql = "SELECT * FROM match_relationships WHERE case_id = ? ORDER BY created_at ASC;"
        cursor = self.conn.execute(sql, (case_id,))
        return [self._row_to_record(r) for r in cursor.fetchall()]

    def _row_to_record(self, row: dict) -> MatchRelationshipRecord:
        return MatchRelationshipRecord(
            id=row["id"],
            case_id=row["case_id"],
            relationship_type=row["relationship_type"],
            status=row["status"],
            source_claim_ids=json.loads(row["source_claim_ids"]) if row["source_claim_ids"] else [],
            target_transaction_ids=json.loads(row["target_transaction_ids"]) if row["target_transaction_ids"] else [],
            matched_amount=row["matched_amount"],
            target_amount=row["target_amount"],
            score=row["score"],
            matched_signals=json.loads(row["matched_signals"]) if row["matched_signals"] else [],
            conflicting_signals=json.loads(row["conflicting_signals"]) if row["conflicting_signals"] else [],
            explanation=row["explanation"] or "",
            created_at=row["created_at"],
        )
