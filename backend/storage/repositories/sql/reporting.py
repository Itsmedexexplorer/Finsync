"""SQL implementation of TruthReportRepository."""

from __future__ import annotations

import json
from typing import Optional

from backend.storage.models import TruthReportRecord
from backend.storage.repositories.base import TruthReportRepository


class SQLTruthReportRepository(TruthReportRepository):
    """SQLite/SQL repository for Truth Report records."""

    def create(self, record: TruthReportRecord) -> TruthReportRecord:
        sql = """
        INSERT INTO truth_reports (
            case_id, title, summary, text_report, status, confidence_score,
            financial_summary, provenance, requires_human_review, report_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(case_id) DO UPDATE SET
            title=excluded.title,
            summary=excluded.summary,
            text_report=excluded.text_report,
            status=excluded.status,
            confidence_score=excluded.confidence_score,
            financial_summary=excluded.financial_summary,
            provenance=excluded.provenance,
            requires_human_review=excluded.requires_human_review,
            report_json=excluded.report_json;
        """
        self.conn.execute(
            sql,
            (
                record.case_id,
                record.title,
                record.summary,
                record.text_report,
                record.status,
                record.confidence_score,
                json.dumps(record.financial_summary),
                json.dumps(record.provenance),
                1 if record.requires_human_review else 0,
                json.dumps(record.report_json),
                record.created_at,
            ),
        )
        return record

    def get_by_case(self, case_id: str) -> Optional[TruthReportRecord]:
        sql = "SELECT * FROM truth_reports WHERE case_id = ?;"
        cursor = self.conn.execute(sql, (case_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return self._row_to_record(row)

    def _row_to_record(self, row: dict) -> TruthReportRecord:
        return TruthReportRecord(
            case_id=row["case_id"],
            title=row["title"] or "",
            summary=row["summary"] or "",
            text_report=row["text_report"] or "",
            status=row["status"],
            confidence_score=row["confidence_score"],
            financial_summary=json.loads(row["financial_summary"]) if row["financial_summary"] else {},
            provenance=json.loads(row["provenance"]) if row["provenance"] else {},
            requires_human_review=bool(row["requires_human_review"]),
            report_json=json.loads(row["report_json"]) if row["report_json"] else {},
            created_at=row["created_at"],
        )
