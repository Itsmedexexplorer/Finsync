"""SQL implementation of PortfolioRepository."""

from __future__ import annotations

import json
from typing import List, Optional

from backend.storage.models import CaseAssignmentRecord, PortfolioStateRecord
from backend.storage.repositories.base import PortfolioRepository


class SQLPortfolioRepository(PortfolioRepository):
    """SQLite/SQL repository for Case Portfolio states and assignments."""

    def save_state(self, state: PortfolioStateRecord) -> PortfolioStateRecord:
        sql = """
        INSERT INTO portfolio_states (
            case_id, portfolio_status, priority, priority_score, priority_reasons,
            amount_exposure, disputed_amount, unresolved_amount, sla_status,
            sla_due_at, sla_elapsed_hours, sla_remaining_hours, assigned_reviewer_id,
            assigned_reviewer_name, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(case_id) DO UPDATE SET
            portfolio_status=excluded.portfolio_status,
            priority=excluded.priority,
            priority_score=excluded.priority_score,
            priority_reasons=excluded.priority_reasons,
            amount_exposure=excluded.amount_exposure,
            disputed_amount=excluded.disputed_amount,
            unresolved_amount=excluded.unresolved_amount,
            sla_status=excluded.sla_status,
            sla_due_at=excluded.sla_due_at,
            sla_elapsed_hours=excluded.sla_elapsed_hours,
            sla_remaining_hours=excluded.sla_remaining_hours,
            assigned_reviewer_id=excluded.assigned_reviewer_id,
            assigned_reviewer_name=excluded.assigned_reviewer_name,
            updated_at=excluded.updated_at;
        """
        self.conn.execute(
            sql,
            (
                state.case_id,
                state.portfolio_status,
                state.priority,
                state.priority_score,
                json.dumps(state.priority_reasons),
                state.amount_exposure,
                state.disputed_amount,
                state.unresolved_amount,
                state.sla_status,
                state.sla_due_at,
                state.sla_elapsed_hours,
                state.sla_remaining_hours,
                state.assigned_reviewer_id,
                state.assigned_reviewer_name,
                state.created_at,
                state.updated_at,
            ),
        )
        return state

    def get_state(self, case_id: str) -> Optional[PortfolioStateRecord]:
        sql = "SELECT * FROM portfolio_states WHERE case_id = ?;"
        cursor = self.conn.execute(sql, (case_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return self._row_to_state(row)

    def list_states(self) -> List[PortfolioStateRecord]:
        sql = "SELECT * FROM portfolio_states ORDER BY created_at DESC;"
        cursor = self.conn.execute(sql)
        return [self._row_to_state(r) for r in cursor.fetchall()]

    def save_assignment(self, assignment: CaseAssignmentRecord) -> CaseAssignmentRecord:
        sql = """
        INSERT INTO case_assignments (
            case_id, reviewer_id, reviewer_name, assigned_at, unassigned_at, active
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(case_id) DO UPDATE SET
            reviewer_id=excluded.reviewer_id,
            reviewer_name=excluded.reviewer_name,
            assigned_at=excluded.assigned_at,
            unassigned_at=excluded.unassigned_at,
            active=excluded.active;
        """
        self.conn.execute(
            sql,
            (
                assignment.case_id,
                assignment.reviewer_id,
                assignment.reviewer_name,
                assignment.assigned_at,
                assignment.unassigned_at,
                1 if assignment.active else 0,
            ),
        )
        return assignment

    def get_assignment(self, case_id: str) -> Optional[CaseAssignmentRecord]:
        sql = "SELECT * FROM case_assignments WHERE case_id = ? AND active = 1;"
        cursor = self.conn.execute(sql, (case_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return self._row_to_assignment(row)

    def list_assignments(self) -> List[CaseAssignmentRecord]:
        sql = "SELECT * FROM case_assignments WHERE active = 1;"
        cursor = self.conn.execute(sql)
        return [self._row_to_assignment(r) for r in cursor.fetchall()]

    def _row_to_state(self, row: dict) -> PortfolioStateRecord:
        return PortfolioStateRecord(
            case_id=row["case_id"],
            portfolio_status=row["portfolio_status"],
            priority=row["priority"],
            priority_score=row["priority_score"],
            priority_reasons=json.loads(row["priority_reasons"]) if row["priority_reasons"] else [],
            amount_exposure=row["amount_exposure"],
            disputed_amount=row["disputed_amount"],
            unresolved_amount=row["unresolved_amount"],
            sla_status=row["sla_status"],
            sla_due_at=row["sla_due_at"],
            sla_elapsed_hours=row["sla_elapsed_hours"],
            sla_remaining_hours=row["sla_remaining_hours"],
            assigned_reviewer_id=row["assigned_reviewer_id"],
            assigned_reviewer_name=row["assigned_reviewer_name"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_assignment(self, row: dict) -> CaseAssignmentRecord:
        return CaseAssignmentRecord(
            case_id=row["case_id"],
            reviewer_id=row["reviewer_id"],
            reviewer_name=row["reviewer_name"],
            assigned_at=row["assigned_at"],
            unassigned_at=row["unassigned_at"],
            active=bool(row["active"]),
        )
