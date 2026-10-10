"""SQL implementation of ReconciliationRepository (Deterministic Financial Truth)."""

from __future__ import annotations

import json
from typing import Optional

from backend.storage.models import ReconciliationRecordModel
from backend.storage.repositories.base import ReconciliationRepository


class SQLReconciliationRepository(ReconciliationRepository):
    """SQLite/SQL repository for Reconciliation Result records."""

    def create(self, record: ReconciliationRecordModel) -> ReconciliationRecordModel:
        sql = """
        INSERT INTO reconciliation_results (
            reconciliation_id, case_id, status, event_id, entity_id,
            claim_ids, transaction_ids, evidence_ids, expected_amount,
            matched_amount, outstanding_amount, currency, confidence_score,
            supporting_signals, contradicting_signals, discrepancy_ids,
            match_relationship_ids, deduplication_group_ids, explanation,
            reason_codes, provenance, metadata, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(case_id) DO UPDATE SET
            reconciliation_id=excluded.reconciliation_id,
            status=excluded.status,
            expected_amount=excluded.expected_amount,
            matched_amount=excluded.matched_amount,
            outstanding_amount=excluded.outstanding_amount,
            confidence_score=excluded.confidence_score,
            supporting_signals=excluded.supporting_signals,
            contradicting_signals=excluded.contradicting_signals,
            discrepancy_ids=excluded.discrepancy_ids,
            match_relationship_ids=excluded.match_relationship_ids,
            deduplication_group_ids=excluded.deduplication_group_ids,
            explanation=excluded.explanation,
            reason_codes=excluded.reason_codes,
            provenance=excluded.provenance,
            metadata=excluded.metadata;
        """
        self.conn.execute(
            sql,
            (
                record.reconciliation_id,
                record.case_id,
                record.status,
                record.event_id,
                record.entity_id,
                json.dumps(record.claim_ids),
                json.dumps(record.transaction_ids),
                json.dumps(record.evidence_ids),
                record.expected_amount,
                record.matched_amount,
                record.outstanding_amount,
                record.currency,
                record.confidence_score,
                json.dumps(record.supporting_signals),
                json.dumps(record.contradicting_signals),
                json.dumps(record.discrepancy_ids),
                json.dumps(record.match_relationship_ids),
                json.dumps(record.deduplication_group_ids),
                record.explanation,
                json.dumps(record.reason_codes),
                json.dumps(record.provenance),
                json.dumps(record.metadata),
                record.created_at,
            ),
        )
        return record

    def get_by_case(self, case_id: str) -> Optional[ReconciliationRecordModel]:
        sql = "SELECT * FROM reconciliation_results WHERE case_id = ?;"
        cursor = self.conn.execute(sql, (case_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return self._row_to_record(row)

    def list_by_cases(self, case_ids: List[str]) -> List[ReconciliationRecordModel]:
        """Fetches reconciliation records for a list of case IDs."""
        if not case_ids:
            return []
        placeholders = ",".join("?" for _ in case_ids)
        sql = f"SELECT * FROM reconciliation_results WHERE case_id IN ({placeholders}) ORDER BY created_at DESC;"
        cursor = self.conn.execute(sql, tuple(case_ids))
        return [self._row_to_record(r) for r in cursor.fetchall()]

    def _row_to_record(self, row: dict) -> ReconciliationRecordModel:
        return ReconciliationRecordModel(
            reconciliation_id=row["reconciliation_id"],
            case_id=row["case_id"],
            status=row["status"],
            event_id=row["event_id"],
            entity_id=row["entity_id"],
            claim_ids=json.loads(row["claim_ids"]) if row["claim_ids"] else [],
            transaction_ids=json.loads(row["transaction_ids"]) if row["transaction_ids"] else [],
            evidence_ids=json.loads(row["evidence_ids"]) if row["evidence_ids"] else [],
            expected_amount=row["expected_amount"],
            matched_amount=row["matched_amount"],
            outstanding_amount=row["outstanding_amount"],
            currency=row["currency"],
            confidence_score=row["confidence_score"],
            supporting_signals=json.loads(row["supporting_signals"]) if row["supporting_signals"] else [],
            contradicting_signals=json.loads(row["contradicting_signals"]) if row["contradicting_signals"] else [],
            discrepancy_ids=json.loads(row["discrepancy_ids"]) if row["discrepancy_ids"] else [],
            match_relationship_ids=json.loads(row["match_relationship_ids"]) if row["match_relationship_ids"] else [],
            deduplication_group_ids=json.loads(row["deduplication_group_ids"]) if row["deduplication_group_ids"] else [],
            explanation=row["explanation"],
            reason_codes=json.loads(row["reason_codes"]) if row["reason_codes"] else [],
            provenance=json.loads(row["provenance"]) if row["provenance"] else {},
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            created_at=row["created_at"],
        )
