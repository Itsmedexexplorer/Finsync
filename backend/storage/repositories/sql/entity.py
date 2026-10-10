"""SQL implementation of EntityRepository."""

from __future__ import annotations

import json
from typing import List, Optional

from backend.storage.models import EntityRecord
from backend.storage.repositories.base import EntityRepository


class SQLEntityRepository(EntityRepository):
    """SQLite/SQL repository for Entity records."""

    def create(self, record: EntityRecord) -> EntityRecord:
        sql = """
        INSERT INTO entities (
            id, case_id, canonical_name, entity_type, gstin, pan, upi_id,
            phone, aliases, confidence, resolved_via, metadata, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            canonical_name=excluded.canonical_name,
            entity_type=excluded.entity_type,
            gstin=excluded.gstin,
            pan=excluded.pan,
            upi_id=excluded.upi_id,
            phone=excluded.phone,
            aliases=excluded.aliases,
            confidence=excluded.confidence,
            resolved_via=excluded.resolved_via,
            metadata=excluded.metadata;
        """
        self.conn.execute(
            sql,
            (
                record.id,
                record.case_id,
                record.canonical_name,
                record.entity_type,
                record.gstin,
                record.pan,
                record.upi_id,
                record.phone,
                json.dumps(record.aliases),
                record.confidence,
                record.resolved_via,
                json.dumps(record.metadata),
                record.created_at,
            ),
        )
        return record

    def create_batch(self, records: List[EntityRecord]) -> List[EntityRecord]:
        for r in records:
            self.create(r)
        return records

    def get(self, entity_id: str, case_id: Optional[str] = None) -> Optional[EntityRecord]:
        if case_id:
            sql = "SELECT * FROM entities WHERE id = ? AND case_id = ?;"
            cursor = self.conn.execute(sql, (entity_id, case_id))
        else:
            sql = "SELECT * FROM entities WHERE id = ?;"
            cursor = self.conn.execute(sql, (entity_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return self._row_to_record(row)

    def list_by_case(self, case_id: str) -> List[EntityRecord]:
        sql = "SELECT * FROM entities WHERE case_id = ? ORDER BY created_at ASC;"
        cursor = self.conn.execute(sql, (case_id,))
        return [self._row_to_record(r) for r in cursor.fetchall()]

    def find_by_name(self, canonical_name: str) -> List[EntityRecord]:
        """Finds all entity records matching the canonical name or aliases across all cases."""
        name_clean = canonical_name.strip().lower()
        sql = """
        SELECT * FROM entities 
        WHERE LOWER(canonical_name) = ? OR LOWER(canonical_name) LIKE ? OR LOWER(aliases) LIKE ?
        ORDER BY created_at DESC;
        """
        like_pattern = f"%{name_clean}%"
        cursor = self.conn.execute(sql, (name_clean, like_pattern, like_pattern))
        return [self._row_to_record(r) for r in cursor.fetchall()]

    def find_by_identifier(self, identifier: str) -> List[EntityRecord]:
        """Finds entity records matching GSTIN, PAN, UPI VPA, or Phone across all cases."""
        ident_clean = identifier.strip().lower()
        sql = """
        SELECT * FROM entities 
        WHERE LOWER(gstin) = ? OR LOWER(pan) = ? OR LOWER(upi_id) = ? OR phone = ?
        ORDER BY created_at DESC;
        """
        cursor = self.conn.execute(sql, (ident_clean, ident_clean, ident_clean, identifier.strip()))
        return [self._row_to_record(r) for r in cursor.fetchall()]

    def list_distinct_entities(self) -> List[Dict[str, Any]]:
        """Lists distinct canonical entities with case counts across the database."""
        sql = """
        SELECT 
            canonical_name,
            MIN(id) as sample_entity_id,
            COUNT(DISTINCT case_id) as case_count,
            MIN(created_at) as first_seen,
            MAX(created_at) as last_seen
        FROM entities
        GROUP BY canonical_name
        ORDER BY case_count DESC, last_seen DESC;
        """
        cursor = self.conn.execute(sql)
        results = []
        for r in cursor.fetchall():
            results.append({
                "canonical_name": r["canonical_name"],
                "sample_entity_id": r["sample_entity_id"],
                "case_count": r["case_count"],
                "first_seen": r["first_seen"],
                "last_seen": r["last_seen"],
            })
        return results

    def _row_to_record(self, row: dict) -> EntityRecord:
        return EntityRecord(
            id=row["id"],
            case_id=row["case_id"],
            canonical_name=row["canonical_name"],
            entity_type=row["entity_type"],
            gstin=row["gstin"],
            pan=row["pan"],
            upi_id=row["upi_id"],
            phone=row["phone"],
            aliases=json.loads(row["aliases"]) if row["aliases"] else [],
            confidence=row["confidence"],
            resolved_via=row["resolved_via"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            created_at=row["created_at"],
        )
