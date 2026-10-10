"""VERITY Case Assignment & Workload Service (Day 15).

Manages reviewer assignments, reassignments, unassignments, workload calculations,
and reviewer overload alerts.

Strict Invariants:
1. Reviewer assignments are operational metadata only; they never alter financial truth.
2. Cross-case metadata leakage is strictly prevented.
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from backend.portfolio.models import (
    CaseAssignment,
    CasePortfolioItem,
    PortfolioCaseStatus,
    PortfolioWorkload,
    SLAStatus,
)

# Overload configuration thresholds
MAX_CRITICAL_CASES = 5
MAX_OPEN_CASES = 20
MAX_OVERDUE_CASES = 5


class PortfolioAssignmentService:
    """Thread-safe assignment and reviewer workload tracking service."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # case_id -> CaseAssignment
        self._assignments: Dict[str, CaseAssignment] = {}

    def assign_case(
        self,
        case_id: str,
        reviewer_id: str,
        reviewer_name: Optional[str] = None,
        assigned_by: str = "controller_admin",
    ) -> CaseAssignment:
        """Assigns a case to a human reviewer."""
        with self._lock:
            assignment_id = f"ASG-{uuid.uuid4().hex[:8].upper()}"
            name = reviewer_name or f"Controller {reviewer_id}"
            assignment = CaseAssignment(
                assignment_id=assignment_id,
                case_id=case_id,
                reviewer_id=reviewer_id,
                reviewer_name=name,
                assigned_at=datetime.now(timezone.utc),
                assigned_by=assigned_by,
                active=True,
            )
            self._assignments[case_id] = assignment
            return assignment

    def reassign_case(
        self,
        case_id: str,
        new_reviewer_id: str,
        new_reviewer_name: Optional[str] = None,
        reassigned_by: str = "controller_admin",
        reason: Optional[str] = None,
    ) -> CaseAssignment:
        """Reassigns a case to another reviewer."""
        with self._lock:
            old_asg = self._assignments.get(case_id)
            if old_asg:
                old_asg.active = False

            assignment_id = f"ASG-{uuid.uuid4().hex[:8].upper()}"
            name = new_reviewer_name or f"Controller {new_reviewer_id}"
            new_asg = CaseAssignment(
                assignment_id=assignment_id,
                case_id=case_id,
                reviewer_id=new_reviewer_id,
                reviewer_name=name,
                assigned_at=datetime.now(timezone.utc),
                assigned_by=reassigned_by,
                active=True,
                metadata={"previous_reviewer_id": old_asg.reviewer_id if old_asg else None, "reason": reason},
            )
            self._assignments[case_id] = new_asg
            return new_asg

    def unassign_case(
        self,
        case_id: str,
        unassigned_by: str = "controller_admin",
        reason: Optional[str] = None,
    ) -> Optional[CaseAssignment]:
        """Removes the active reviewer assignment from a case."""
        with self._lock:
            asg = self._assignments.get(case_id)
            if asg and asg.active:
                asg.active = False
                asg.metadata["unassigned_by"] = unassigned_by
                asg.metadata["unassigned_reason"] = reason
                return asg
            return None

    def get_assignment(self, case_id: str) -> Optional[CaseAssignment]:
        """Retrieves the active assignment for a case."""
        with self._lock:
            asg = self._assignments.get(case_id)
            return asg if (asg and asg.active) else None

    def list_workloads(self, cases: List[CasePortfolioItem]) -> List[PortfolioWorkload]:
        """Calculates workload metrics and identifies overloaded reviewers."""
        reviewers_map: Dict[str, Dict[str, Any]] = {}

        for c in cases:
            if not c.assigned_reviewer_id:
                continue

            rid = c.assigned_reviewer_id
            rname = c.assigned_reviewer_name or rid

            if rid not in reviewers_map:
                reviewers_map[rid] = {
                    "name": rname,
                    "assigned_cases": 0,
                    "open_cases": 0,
                    "critical_cases": 0,
                    "overdue_cases": 0,
                    "total_exposure": 0.0,
                }

            rec = reviewers_map[rid]
            rec["assigned_cases"] += 1
            rec["total_exposure"] += c.amount_exposure

            is_open = c.portfolio_status not in (PortfolioCaseStatus.RESOLVED, PortfolioCaseStatus.CLOSED)
            if is_open:
                rec["open_cases"] += 1
                if c.risk_level == "CRITICAL" or c.priority.value == "CRITICAL":
                    rec["critical_cases"] += 1
                if c.sla_status == SLAStatus.OVERDUE:
                    rec["overdue_cases"] += 1

        workloads: List[PortfolioWorkload] = []
        for rid, data in reviewers_map.items():
            reasons: List[str] = []
            if data["critical_cases"] > MAX_CRITICAL_CASES:
                reasons.append(f"Exceeds max critical cases threshold ({data['critical_cases']} > {MAX_CRITICAL_CASES})")
            if data["open_cases"] > MAX_OPEN_CASES:
                reasons.append(f"Exceeds max open cases threshold ({data['open_cases']} > {MAX_OPEN_CASES})")
            if data["overdue_cases"] > MAX_OVERDUE_CASES:
                reasons.append(f"Exceeds max overdue cases threshold ({data['overdue_cases']} > {MAX_OVERDUE_CASES})")

            is_overloaded = len(reasons) > 0

            workloads.append(
                PortfolioWorkload(
                    reviewer_id=rid,
                    reviewer_name=data["name"],
                    assigned_cases=data["assigned_cases"],
                    open_cases=data["open_cases"],
                    critical_cases=data["critical_cases"],
                    overdue_cases=data["overdue_cases"],
                    total_exposure=round(data["total_exposure"], 2),
                    is_overloaded=is_overloaded,
                    overload_reasons=reasons,
                )
            )

        return sorted(workloads, key=lambda w: (w.is_overloaded, w.critical_cases, w.open_cases), reverse=True)
