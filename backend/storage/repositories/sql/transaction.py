"""SQL implementation of TransactionRepository (IMMUTABLE)."""

from __future__ import annotations

import json
from typing import List, Optional

from backend.storage.models import TransactionRecord
from backend.storage.repositories.base import TransactionRepository


class SQLTransactionRepository(TransactionRepository):
    """SQLite/SQL repository for Transaction records."""

    def create(self, record: TransactionRecord) -> TransactionRecord:
        sql = """
        INSERT INTO transactions (
            id, case_id, amount, direction, timestamp, bank_reference,
            payment_method, counterparty_entity_id, account_number_mask, metadata, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO NOTHING;
        """
        self.conn.execute(
            sql,
            (
                record.id,
                record.case_id,
                record.amount,
                record.direction,
                record.timestamp,
                record.bank_reference,
                record.payment_method,
                record.counterparty_entity_id,
                record.account_number_mask,
                json.dumps(record.metadata),
                record.created_at,
            ),
        )
        return record

    def create_batch(self, records: List[TransactionRecord]) -> List[TransactionRecord]:
        for r in records:
            self.create(r)
        return records

    def get(self, transaction_id: str, case_id: Optional[str] = None) -> Optional[TransactionRecord]:
        if case_id:
            sql = "SELECT * FROM transactions WHERE id = ? AND case_id = ?;"
            cursor = self.conn.execute(sql, (transaction_id, case_id))
        else:
            sql = "SELECT * FROM transactions WHERE id = ?;"
            cursor = self.conn.execute(sql, (transaction_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return self._row_to_record(row)

    def list_by_case(self, case_id: str) -> List[TransactionRecord]:
        sql = "SELECT * FROM transactions WHERE case_id = ? ORDER BY created_at ASC;"
        cursor = self.conn.execute(sql, (case_id,))
        return [self._row_to_record(r) for r in cursor.fetchall()]

    def find_by_reference(self, bank_reference: str) -> List[TransactionRecord]:
        """Finds transactions matching a specific UTR, RRN, or reference ID across all cases."""
        ref_clean = bank_reference.strip().lower()
        sql = "SELECT * FROM transactions WHERE LOWER(bank_reference) = ? ORDER BY created_at DESC;"
        cursor = self.conn.execute(sql, (ref_clean,))
        return [self._row_to_record(r) for r in cursor.fetchall()]

    def _row_to_record(self, row: dict) -> TransactionRecord:
        return TransactionRecord(
            id=row["id"],
            case_id=row["case_id"],
            amount=row["amount"],
            direction=row["direction"],
            timestamp=row["timestamp"],
            bank_reference=row["bank_reference"],
            payment_method=row["payment_method"],
            counterparty_entity_id=row["counterparty_entity_id"],
            account_number_mask=row["account_number_mask"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            created_at=row["created_at"],
        )
