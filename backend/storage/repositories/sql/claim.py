"""SQL implementation of ClaimRepository (IMMUTABLE)."""

from __future__ import annotations

import json
from typing import List, Optional

from backend.storage.models import ClaimRecord
from backend.storage.repositories.base import ClaimRepository


class SQLClaimRepository(ClaimRepository):
    """SQLite/SQL repository for Claim records."""

    def create(self, record: ClaimRecord) -> ClaimRecord:
        sql = """
        INSERT INTO claims (
            id, case_id, evidence_id, claim_type, claimed_amount, claimed_date,
            counterparty_hint, reference_id_hint, confidence, metadata, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO NOTHING;
        """
        self.conn.execute(
            sql,
            (
                record.id,
                record.case_id,
                record.evidence_id,
                record.claim_type,
                record.claimed_amount,
                record.claimed_date,
                record.counterparty_hint,
                record.reference_id_hint,
                record.confidence,
                json.dumps(record.metadata),
                record.created_at,
            ),
        )
        return record

    def create_batch(self, records: List[ClaimRecord]) -> List[ClaimRecord]:
        for r in records:
            self.create(r)
        return records

    def get(self, claim_id: str, case_id: Optional[str] = None) -> Optional[ClaimRecord]:
        if case_id:
            sql = "SELECT * FROM claims WHERE id = ? AND case_id = ?;"
            cursor = self.conn.execute(sql, (claim_id, case_id))
        else:
            sql = "SELECT * FROM claims WHERE id = ?;"
            cursor = self.conn.execute(sql, (claim_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return self._row_to_record(row)

    def list_by_case(self, case_id: str) -> List[ClaimRecord]:
        sql = "SELECT * FROM claims WHERE case_id = ? ORDER BY created_at ASC;"
        cursor = self.conn.execute(sql, (case_id,))
        return [self._row_to_record(r) for r in cursor.fetchall()]

    def find_by_reference_hint(self, reference_id_hint: str) -> List[ClaimRecord]:
        """Finds claims citing a specific reference hint across all cases."""
        ref_clean = reference_id_hint.strip().lower()
        sql = "SELECT * FROM claims WHERE LOWER(reference_id_hint) = ? ORDER BY created_at DESC;"
        cursor = self.conn.execute(sql, (ref_clean,))
        return [self._row_to_record(r) for r in cursor.fetchall()]

    def find_by_counterparty(self, counterparty_hint: str) -> List[ClaimRecord]:
        """Finds claims mentioning a specific counterparty across all cases."""
        cp_clean = counterparty_hint.strip().lower()
        sql = "SELECT * FROM claims WHERE LOWER(counterparty_hint) LIKE ? ORDER BY created_at DESC;"
        cursor = self.conn.execute(sql, (f"%{cp_clean}%",))
        return [self._row_to_record(r) for r in cursor.fetchall()]

    def _row_to_record(self, row: dict) -> ClaimRecord:
        return ClaimRecord(
            id=row["id"],
            case_id=row["case_id"],
            evidence_id=row["evidence_id"],
            claim_type=row["claim_type"],
            claimed_amount=row["claimed_amount"],
            claimed_date=row["claimed_date"],
            counterparty_hint=row["counterparty_hint"],
            reference_id_hint=row["reference_id_hint"],
            confidence=row["confidence"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            created_at=row["created_at"],
        )
