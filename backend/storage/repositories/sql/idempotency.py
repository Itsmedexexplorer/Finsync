"""SQL implementation of IdempotencyRepository."""

from __future__ import annotations

from typing import Optional

from backend.storage.models import IdempotencyRecord
from backend.storage.repositories.base import IdempotencyRepository


class SQLIdempotencyRepository(IdempotencyRepository):
    """SQLite/SQL repository for idempotency tracking."""

    def get(self, key: str) -> Optional[IdempotencyRecord]:
        sql = "SELECT * FROM idempotency_records WHERE key = ?;"
        cursor = self.conn.execute(sql, (key,))
        row = cursor.fetchone()
        if not row:
            return None
        return IdempotencyRecord(
            key=row["key"],
            case_id=row["case_id"],
            request_hash=row["request_hash"],
            response_reference=row["response_reference"],
            status=row["status"],
            created_at=row["created_at"],
        )

    def create(self, record: IdempotencyRecord) -> IdempotencyRecord:
        sql = """
        INSERT INTO idempotency_records (
            key, case_id, request_hash, response_reference, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?);
        """
        self.conn.execute(
            sql,
            (
                record.key,
                record.case_id,
                record.request_hash,
                record.response_reference,
                record.status,
                record.created_at,
            ),
        )
        return record
