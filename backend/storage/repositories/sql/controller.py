"""SQL implementation of ControllerRepository."""

from __future__ import annotations

import json
from typing import Optional

from backend.storage.models import ControllerDecisionRecord
from backend.storage.repositories.base import ControllerRepository


class SQLControllerRepository(ControllerRepository):
    """SQLite/SQL repository for Controller Decision records."""

    def create(self, record: ControllerDecisionRecord) -> ControllerDecisionRecord:
        sql = """
        INSERT INTO controller_decisions (
            case_id, risk_level, decision, requires_human_review, confidence,
            reasons, recommended_actions, executive_brief, metadata, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(case_id) DO UPDATE SET
            risk_level=excluded.risk_level,
            decision=excluded.decision,
            requires_human_review=excluded.requires_human_review,
            confidence=excluded.confidence,
            reasons=excluded.reasons,
            recommended_actions=excluded.recommended_actions,
            executive_brief=excluded.executive_brief,
            metadata=excluded.metadata;
        """
        self.conn.execute(
            sql,
            (
                record.case_id,
                record.risk_level,
                record.decision,
                1 if record.requires_human_review else 0,
                record.confidence,
                json.dumps(record.reasons),
                json.dumps(record.recommended_actions),
                record.executive_brief,
                json.dumps(record.metadata),
                record.created_at,
            ),
        )
        return record

    def get_by_case(self, case_id: str) -> Optional[ControllerDecisionRecord]:
        sql = "SELECT * FROM controller_decisions WHERE case_id = ?;"
        cursor = self.conn.execute(sql, (case_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return self._row_to_record(row)

    def _row_to_record(self, row: dict) -> ControllerDecisionRecord:
        return ControllerDecisionRecord(
            case_id=row["case_id"],
            risk_level=row["risk_level"],
            decision=row["decision"],
            requires_human_review=bool(row["requires_human_review"]),
            confidence=row["confidence"],
            reasons=json.loads(row["reasons"]) if row["reasons"] else [],
            recommended_actions=json.loads(row["recommended_actions"]) if row["recommended_actions"] else [],
            executive_brief=row["executive_brief"] or "",
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            created_at=row["created_at"],
        )
