"""SQL implementation of DiscrepancyRepository."""

from __future__ import annotations

import json
from typing import List

from backend.storage.models import DiscrepancyRecord
from backend.storage.repositories.base import DiscrepancyRepository


class SQLDiscrepancyRepository(DiscrepancyRepository):
    """SQLite/SQL repository for Discrepancy records."""

    def create(self, record: DiscrepancyRecord) -> DiscrepancyRecord:
        sql = """
        INSERT INTO discrepancies (
            id, case_id, discrepancy_type, severity, message, expected_value,
            observed_value, involved_evidence_ids, involved_claim_ids,
            involved_transaction_ids, metadata, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            discrepancy_type=excluded.discrepancy_type,
            severity=excluded.severity,
            message=excluded.message,
            expected_value=excluded.expected_value,
            observed_value=excluded.observed_value,
            involved_evidence_ids=excluded.involved_evidence_ids,
            involved_claim_ids=excluded.involved_claim_ids,
            involved_transaction_ids=excluded.involved_transaction_ids,
            metadata=excluded.metadata;
        """
        self.conn.execute(
            sql,
            (
                record.id,
                record.case_id,
                record.discrepancy_type,
                record.severity,
                record.message,
                record.expected_value,
                record.observed_value,
                json.dumps(record.involved_evidence_ids),
                json.dumps(record.involved_claim_ids),
                json.dumps(record.involved_transaction_ids),
                json.dumps(record.metadata),
                record.created_at,
            ),
        )
        return record

    def create_batch(self, records: List[DiscrepancyRecord]) -> List[DiscrepancyRecord]:
        for r in records:
            self.create(r)
        return records

    def list_by_case(self, case_id: str) -> List[DiscrepancyRecord]:
        sql = "SELECT * FROM discrepancies WHERE case_id = ? ORDER BY created_at ASC;"
        cursor = self.conn.execute(sql, (case_id,))
        return [self._row_to_record(r) for r in cursor.fetchall()]

    def find_by_type(self, discrepancy_type: str) -> List[DiscrepancyRecord]:
        """Finds all discrepancies of a specific type across all cases."""
        sql = "SELECT * FROM discrepancies WHERE discrepancy_type = ? ORDER BY created_at DESC;"
        cursor = self.conn.execute(sql, (discrepancy_type.strip(),))
        return [self._row_to_record(r) for r in cursor.fetchall()]

    def list_all(self, limit: int = 500) -> List[DiscrepancyRecord]:
        """Lists latest discrepancies across the database."""
        sql = "SELECT * FROM discrepancies ORDER BY created_at DESC LIMIT ?;"
        cursor = self.conn.execute(sql, (max(1, min(1000, limit)),))
        return [self._row_to_record(r) for r in cursor.fetchall()]

    def _row_to_record(self, row: dict) -> DiscrepancyRecord:
        return DiscrepancyRecord(
            id=row["id"],
            case_id=row["case_id"],
            discrepancy_type=row["discrepancy_type"],
            severity=row["severity"],
            message=row["message"],
            expected_value=row["expected_value"],
            observed_value=row["observed_value"],
            involved_evidence_ids=json.loads(row["involved_evidence_ids"]) if row["involved_evidence_ids"] else [],
            involved_claim_ids=json.loads(row["involved_claim_ids"]) if row["involved_claim_ids"] else [],
            involved_transaction_ids=json.loads(row["involved_transaction_ids"]) if row["involved_transaction_ids"] else [],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            created_at=row["created_at"],
        )
