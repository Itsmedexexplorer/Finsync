"""SQL implementation of CaseRepository."""

from __future__ import annotations

import json
from typing import List, Optional

from backend.storage.models import CaseRecord
from backend.storage.repositories.base import CaseRepository


class SQLCaseRepository(CaseRepository):
    """SQLite/SQL repository for cases."""

    def create(self, record: CaseRecord) -> CaseRecord:
        sql = """
        INSERT INTO cases (
            case_id, status, confidence_score, total_execution_time_ms,
            financial_summary, warnings, errors, metadata, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(case_id) DO UPDATE SET
            status=excluded.status,
            confidence_score=excluded.confidence_score,
            total_execution_time_ms=excluded.total_execution_time_ms,
            financial_summary=excluded.financial_summary,
            warnings=excluded.warnings,
            errors=excluded.errors,
            metadata=excluded.metadata,
            updated_at=excluded.updated_at;
        """
        self.conn.execute(
            sql,
            (
                record.case_id,
                record.status,
                record.confidence_score,
                record.total_execution_time_ms,
                json.dumps(record.financial_summary),
                json.dumps(record.warnings),
                json.dumps(record.errors),
                json.dumps(record.metadata),
                record.created_at,
                record.updated_at,
            ),
        )
        return record

    def get(self, case_id: str) -> Optional[CaseRecord]:
        sql = "SELECT * FROM cases WHERE case_id = ?;"
        cursor = self.conn.execute(sql, (case_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return self._row_to_record(row)

    def list_all(self, limit: int = 100, offset: int = 0) -> List[CaseRecord]:
        sql = "SELECT * FROM cases ORDER BY created_at DESC LIMIT ? OFFSET ?;"
        cursor = self.conn.execute(sql, (limit, offset))
        return [self._row_to_record(r) for r in cursor.fetchall()]

    def count(self) -> int:
        sql = "SELECT COUNT(*) AS c FROM cases;"
        cursor = self.conn.execute(sql)
        row = cursor.fetchone()
        return row["c"] if row else 0

    def exists(self, case_id: str) -> bool:
        sql = "SELECT 1 FROM cases WHERE case_id = ?;"
        cursor = self.conn.execute(sql, (case_id,))
        return cursor.fetchone() is not None

    def delete_if_allowed(self, case_id: str) -> bool:
        sql = "DELETE FROM cases WHERE case_id = ?;"
        cursor = self.conn.execute(sql, (case_id,))
        return cursor.rowcount > 0

    def _row_to_record(self, row: dict) -> CaseRecord:
        return CaseRecord(
            case_id=row["case_id"],
            status=row["status"],
            confidence_score=row["confidence_score"],
            total_execution_time_ms=row["total_execution_time_ms"],
            financial_summary=json.loads(row["financial_summary"]) if row["financial_summary"] else {},
            warnings=json.loads(row["warnings"]) if row["warnings"] else [],
            errors=json.loads(row["errors"]) if row["errors"] else [],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
