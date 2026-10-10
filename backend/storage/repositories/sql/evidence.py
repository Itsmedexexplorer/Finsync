"""SQL implementation of EvidenceRepository (IMMUTABLE)."""

from __future__ import annotations

from typing import List, Optional

from backend.storage.models import EvidenceRecord
from backend.storage.repositories.base import EvidenceRepository


class SQLEvidenceRepository(EvidenceRepository):
    """SQLite/SQL repository for Evidence."""

    def create(self, record: EvidenceRecord) -> EvidenceRecord:
        sql = """
        INSERT INTO evidence (
            id, case_id, modality, source_name, source_type, sha256_hash, summary, raw_payload, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO NOTHING;
        """
        self.conn.execute(
            sql,
            (
                record.id,
                record.case_id,
                record.modality,
                record.source_name,
                record.source_type,
                record.sha256_hash,
                record.summary,
                record.raw_payload,
                record.created_at,
            ),
        )
        return record

    def create_batch(self, records: List[EvidenceRecord]) -> List[EvidenceRecord]:
        for r in records:
            self.create(r)
        return records

    def get(self, evidence_id: str, case_id: Optional[str] = None) -> Optional[EvidenceRecord]:
        if case_id:
            sql = "SELECT * FROM evidence WHERE id = ? AND case_id = ?;"
            cursor = self.conn.execute(sql, (evidence_id, case_id))
        else:
            sql = "SELECT * FROM evidence WHERE id = ?;"
            cursor = self.conn.execute(sql, (evidence_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return self._row_to_record(row)

    def list_by_case(self, case_id: str) -> List[EvidenceRecord]:
        sql = "SELECT * FROM evidence WHERE case_id = ? ORDER BY created_at ASC;"
        cursor = self.conn.execute(sql, (case_id,))
        return [self._row_to_record(r) for r in cursor.fetchall()]

    def count_by_case(self, case_id: str) -> int:
        sql = "SELECT COUNT(*) AS c FROM evidence WHERE case_id = ?;"
        cursor = self.conn.execute(sql, (case_id,))
        row = cursor.fetchone()
        return row["c"] if row else 0

    def find_by_hash(self, sha256_hash: str) -> List[EvidenceRecord]:
        """Finds evidence records with matching cryptographic hash across all cases."""
        h = (sha256_hash or "").strip()
        if not h or h == "0" * 64:
            return []
        sql = "SELECT * FROM evidence WHERE sha256_hash = ? ORDER BY created_at DESC;"
        cursor = self.conn.execute(sql, (h,))
        return [self._row_to_record(r) for r in cursor.fetchall()]

    def _row_to_record(self, row: dict) -> EvidenceRecord:
        return EvidenceRecord(
            id=row["id"],
            case_id=row["case_id"],
            modality=row["modality"],
            source_name=row["source_name"],
            source_type=row["source_type"],
            sha256_hash=row["sha256_hash"],
            summary=row["summary"] or "",
            raw_payload=row["raw_payload"] or "",
            created_at=row["created_at"],
        )
