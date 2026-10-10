"""SQL implementation of ReviewRepository."""

from __future__ import annotations

import json
from typing import List, Optional

from backend.storage.models import (
    EvidenceReviewRecordModel,
    ReviewNoteRecord,
    ReviewRecordModel,
)
from backend.storage.repositories.base import ReviewRepository


class SQLReviewRepository(ReviewRepository):
    """SQLite/SQL repository for Human Review workspace state."""

    def create(self, record: ReviewRecordModel) -> ReviewRecordModel:
        sql = """
        INSERT INTO reviews (
            review_id, case_id, status, decision, assigned_to,
            required_actions, completed_actions, notes_count,
            inspected_evidence_count, created_at, updated_at, closed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(case_id) DO UPDATE SET
            review_id=excluded.review_id,
            status=excluded.status,
            decision=excluded.decision,
            assigned_to=excluded.assigned_to,
            required_actions=excluded.required_actions,
            completed_actions=excluded.completed_actions,
            notes_count=excluded.notes_count,
            inspected_evidence_count=excluded.inspected_evidence_count,
            updated_at=excluded.updated_at,
            closed_at=excluded.closed_at;
        """
        self.conn.execute(
            sql,
            (
                record.review_id,
                record.case_id,
                record.status,
                record.decision,
                record.assigned_to,
                json.dumps(record.required_actions),
                json.dumps(record.completed_actions),
                record.notes_count,
                record.inspected_evidence_count,
                record.created_at,
                record.updated_at,
                record.closed_at,
            ),
        )
        return record

    def update(self, record: ReviewRecordModel) -> ReviewRecordModel:
        return self.create(record)

    def get_by_case(self, case_id: str) -> Optional[ReviewRecordModel]:
        sql = "SELECT * FROM reviews WHERE case_id = ?;"
        cursor = self.conn.execute(sql, (case_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return self._row_to_record(row)

    def add_note(self, note: ReviewNoteRecord) -> ReviewNoteRecord:
        sql = """
        INSERT INTO review_notes (
            note_id, case_id, review_id, author_id, author_name, note_type, content, timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(note_id) DO NOTHING;
        """
        self.conn.execute(
            sql,
            (
                note.note_id,
                note.case_id,
                note.review_id,
                note.author_id,
                note.author_name,
                note.note_type,
                note.content,
                note.timestamp,
            ),
        )
        return note

    def list_notes(self, case_id: str) -> List[ReviewNoteRecord]:
        sql = "SELECT * FROM review_notes WHERE case_id = ? ORDER BY timestamp ASC;"
        cursor = self.conn.execute(sql, (case_id,))
        return [
            ReviewNoteRecord(
                note_id=r["note_id"],
                case_id=r["case_id"],
                review_id=r["review_id"],
                author_id=r["author_id"],
                author_name=r["author_name"],
                note_type=r["note_type"],
                content=r["content"],
                timestamp=r["timestamp"],
            )
            for r in cursor.fetchall()
        ]

    def add_inspection(self, inspection: EvidenceReviewRecordModel) -> EvidenceReviewRecordModel:
        sql = """
        INSERT INTO evidence_inspections (
            inspection_id, case_id, review_id, evidence_id, reviewer_id, verified, notes, timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(inspection_id) DO NOTHING;
        """
        self.conn.execute(
            sql,
            (
                inspection.inspection_id,
                inspection.case_id,
                inspection.review_id,
                inspection.evidence_id,
                inspection.reviewer_id,
                1 if inspection.verified else 0,
                inspection.notes,
                inspection.timestamp,
            ),
        )
        return inspection

    def list_inspections(self, case_id: str) -> List[EvidenceReviewRecordModel]:
        sql = "SELECT * FROM evidence_inspections WHERE case_id = ? ORDER BY timestamp ASC;"
        cursor = self.conn.execute(sql, (case_id,))
        return [
            EvidenceReviewRecordModel(
                inspection_id=r["inspection_id"],
                case_id=r["case_id"],
                review_id=r["review_id"],
                evidence_id=r["evidence_id"],
                reviewer_id=r["reviewer_id"],
                verified=bool(r["verified"]),
                notes=r["notes"],
                timestamp=r["timestamp"],
            )
            for r in cursor.fetchall()
        ]

    def _row_to_record(self, row: dict) -> ReviewRecordModel:
        return ReviewRecordModel(
            review_id=row["review_id"],
            case_id=row["case_id"],
            status=row["status"],
            decision=row["decision"],
            assigned_to=row["assigned_to"],
            required_actions=json.loads(row["required_actions"]) if row["required_actions"] else [],
            completed_actions=json.loads(row["completed_actions"]) if row["completed_actions"] else [],
            notes_count=row["notes_count"],
            inspected_evidence_count=row["inspected_evidence_count"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            closed_at=row["closed_at"],
        )
