"""VERITY Unified Portfolio Management Service (Day 15).

Orchestrates portfolio aggregation, search/querying, SLA evaluation, reviewer assignment,
workload balancing, and prioritization across all reconciled cases.

Strict Invariants:
1. PORTFOLIO INTELLIGENCE MUST NEVER MODIFY FINANCIAL TRUTH.
2. OPERATIONAL STATUS != FINANCIAL TRUTH.
3. NO DOUBLE COUNTING: Pure deterministic synthesis of existing canonical results.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from backend.case_processing.result import CaseProcessingResult
from backend.controller.models import ControllerDecision
from backend.portfolio.aggregator import PortfolioAggregator
from backend.portfolio.assignment import PortfolioAssignmentService
from backend.portfolio.models import (
    CasePortfolioItem,
    PortfolioCaseStatus,
    PortfolioExposure,
    PortfolioFilter,
    PortfolioPage,
    PortfolioPriority,
    PortfolioPriorityScore,
    PortfolioSort,
    PortfolioSortField,
    PortfolioSummary,
    PortfolioWorkload,
    SLAStatus,
    SortOrder,
)
from backend.portfolio.prioritizer import PortfolioPrioritizer
from backend.portfolio.query import PortfolioQueryEngine
from backend.portfolio.sla import SLAPolicy
from backend.review.models import ReviewRecord


class PortfolioCaseNotFoundError(Exception):
    """Raised when a requested case is not found in the portfolio index."""
    pass


class PortfolioService:
    """Thread-safe orchestration service for portfolio operations."""

    def __init__(self, assignment_service: Optional[PortfolioAssignmentService] = None) -> None:
        self._lock = threading.Lock()
        self.assignment_service = assignment_service or PortfolioAssignmentService()
        # case_id -> CasePortfolioItem
        self._cases: Dict[str, CasePortfolioItem] = {}
        # Track raw references for refresh
        self._raw_case_results: Dict[str, CaseProcessingResult] = {}
        self._raw_controller_decisions: Dict[str, ControllerDecision] = {}
        self._raw_review_records: Dict[str, ReviewRecord] = {}

    def register_case(
        self,
        case_result: CaseProcessingResult,
        controller_decision: Optional[ControllerDecision] = None,
        review_record: Optional[ReviewRecord] = None,
        creation_time: Optional[datetime] = None,
    ) -> CasePortfolioItem:
        """Indexes or updates a reconciled case in the operational portfolio."""
        case_id = case_result.case_id

        with self._lock:
            self._raw_case_results[case_id] = case_result
            if controller_decision:
                self._raw_controller_decisions[case_id] = controller_decision
            if review_record:
                self._raw_review_records[case_id] = review_record

            asg = self.assignment_service.get_assignment(case_id)
            existing = self._cases.get(case_id)
            created_at = creation_time or (existing.created_at if existing else datetime.now(timezone.utc))

            # Initial priority estimate
            prio = existing.priority if existing else PortfolioPriority.LOW

            # SLA Evaluation
            is_resolved = (
                (review_record and review_record.status.value in ("RESOLVED", "CLOSED"))
                or (existing and existing.portfolio_status in (PortfolioCaseStatus.RESOLVED, PortfolioCaseStatus.CLOSED))
            )
            is_waiting = (
                (review_record and review_record.status.value == "WAITING_FOR_EVIDENCE")
                or (existing and existing.portfolio_status == PortfolioCaseStatus.WAITING_FOR_EVIDENCE)
            )

            sla_stat, sla_due, _, _ = SLAPolicy.evaluate_sla(
                created_at=created_at,
                priority=prio,
                is_resolved_or_closed=is_resolved,
                is_waiting_for_evidence=is_waiting,
            )

            # Build Item
            item = PortfolioAggregator.from_case_result(
                case_result=case_result,
                controller_decision=self._raw_controller_decisions.get(case_id),
                review_record=self._raw_review_records.get(case_id),
                assignment=asg,
                sla_status=sla_stat,
                sla_due_at=sla_due,
            )
            item.created_at = created_at

            # Calculate prioritized score and re-bind priority
            prio_score = PortfolioPrioritizer.calculate_priority_score(item)
            item.priority = prio_score.priority

            # Re-evaluate SLA with computed priority if changed
            if item.priority != prio:
                sla_stat, sla_due, _, _ = SLAPolicy.evaluate_sla(
                    created_at=created_at,
                    priority=item.priority,
                    is_resolved_or_closed=is_resolved,
                    is_waiting_for_evidence=is_waiting,
                )
                item.sla_status = sla_stat
                item.sla_due_at = sla_due

            self._cases[case_id] = item
            return item

    def get_case(self, case_id: str) -> Optional[CasePortfolioItem]:
        """Retrieves a single portfolio case item by ID."""
        with self._lock:
            return self._cases.get(case_id)

    def list_cases(self) -> List[CasePortfolioItem]:
        """Returns all indexed portfolio case items."""
        with self._lock:
            return list(self._cases.values())

    def query_cases(
        self,
        filters: Optional[PortfolioFilter] = None,
        sort: Optional[PortfolioSort] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PortfolioPage:
        """Executes a filtered, sorted, and paginated query across portfolio cases."""
        with self._lock:
            all_items = list(self._cases.values())

        return PortfolioQueryEngine.paginate_cases(
            cases=all_items,
            page=page,
            page_size=page_size,
            filters=filters,
            sort=sort,
        )

    def get_summary(self) -> PortfolioSummary:
        """Computes current portfolio-wide summary metrics."""
        with self._lock:
            items = list(self._cases.values())
        return PortfolioAggregator.aggregate_summary(items)

    def get_exposure(self) -> PortfolioExposure:
        """Computes current portfolio-wide exposure breakdown."""
        with self._lock:
            items = list(self._cases.values())
        return PortfolioAggregator.aggregate_exposure(items)

    def get_workload(self) -> List[PortfolioWorkload]:
        """Calculates workload metrics across reviewers."""
        with self._lock:
            items = list(self._cases.values())
        return self.assignment_service.list_workloads(items)

    def assign_case(
        self,
        case_id: str,
        reviewer_id: str,
        reviewer_name: Optional[str] = None,
        assigned_by: str = "controller_admin",
    ) -> CasePortfolioItem:
        """Assigns a case to a reviewer and updates its portfolio state."""
        with self._lock:
            if case_id not in self._cases:
                raise PortfolioCaseNotFoundError(f"Case '{case_id}' not found in portfolio index.")

            self.assignment_service.assign_case(
                case_id=case_id,
                reviewer_id=reviewer_id,
                reviewer_name=reviewer_name,
                assigned_by=assigned_by,
            )

        # Refresh item state
        case_res = self._raw_case_results[case_id]
        ctrl_dec = self._raw_controller_decisions.get(case_id)
        rev_rec = self._raw_review_records.get(case_id)
        return self.register_case(case_res, ctrl_dec, rev_rec)

    def reassign_case(
        self,
        case_id: str,
        new_reviewer_id: str,
        new_reviewer_name: Optional[str] = None,
        reassigned_by: str = "controller_admin",
        reason: Optional[str] = None,
    ) -> CasePortfolioItem:
        """Reassigns a case to another reviewer."""
        with self._lock:
            if case_id not in self._cases:
                raise PortfolioCaseNotFoundError(f"Case '{case_id}' not found in portfolio index.")

            self.assignment_service.reassign_case(
                case_id=case_id,
                new_reviewer_id=new_reviewer_id,
                new_reviewer_name=new_reviewer_name,
                reassigned_by=reassigned_by,
                reason=reason,
            )

        case_res = self._raw_case_results[case_id]
        ctrl_dec = self._raw_controller_decisions.get(case_id)
        rev_rec = self._raw_review_records.get(case_id)
        return self.register_case(case_res, ctrl_dec, rev_rec)

    def unassign_case(
        self,
        case_id: str,
        unassigned_by: str = "controller_admin",
        reason: Optional[str] = None,
    ) -> CasePortfolioItem:
        """Removes the active reviewer assignment from a case."""
        with self._lock:
            if case_id not in self._cases:
                raise PortfolioCaseNotFoundError(f"Case '{case_id}' not found in portfolio index.")

            self.assignment_service.unassign_case(
                case_id=case_id,
                unassigned_by=unassigned_by,
                reason=reason,
            )

        case_res = self._raw_case_results[case_id]
        ctrl_dec = self._raw_controller_decisions.get(case_id)
        rev_rec = self._raw_review_records.get(case_id)
        return self.register_case(case_res, ctrl_dec, rev_rec)

    def calculate_sla(
        self,
        case_id: str,
        now: Optional[datetime] = None,
    ) -> Tuple[SLAStatus, datetime, float, float]:
        """Calculates current SLA health for a specific case."""
        with self._lock:
            item = self._cases.get(case_id)
            if not item:
                raise PortfolioCaseNotFoundError(f"Case '{case_id}' not found in portfolio index.")

            is_resolved = item.portfolio_status in (PortfolioCaseStatus.RESOLVED, PortfolioCaseStatus.CLOSED)
            is_waiting = item.portfolio_status == PortfolioCaseStatus.WAITING_FOR_EVIDENCE

            return SLAPolicy.evaluate_sla(
                created_at=item.created_at,
                priority=item.priority,
                is_resolved_or_closed=is_resolved,
                is_waiting_for_evidence=is_waiting,
                now=now,
            )

    def prioritize_case(self, case_id: str) -> PortfolioPriorityScore:
        """Calculates prioritized score and explainable reasons for a case."""
        with self._lock:
            item = self._cases.get(case_id)
            if not item:
                raise PortfolioCaseNotFoundError(f"Case '{case_id}' not found in portfolio index.")

            return PortfolioPrioritizer.calculate_priority_score(item)

    def get_review_queue(self) -> List[CasePortfolioItem]:
        """Returns cases requiring human attention."""
        with self._lock:
            items = list(self._cases.values())

        review_items = [
            i for i in items
            if (i.requires_human_review or i.portfolio_status in (
                PortfolioCaseStatus.TRIAGED,
                PortfolioCaseStatus.IN_REVIEW,
                PortfolioCaseStatus.WAITING_FOR_EVIDENCE,
                PortfolioCaseStatus.ESCALATED,
            )) and i.portfolio_status not in (PortfolioCaseStatus.RESOLVED, PortfolioCaseStatus.CLOSED)
        ]
        return PortfolioQueryEngine.sort_cases(
            review_items,
            PortfolioSort(field=PortfolioSortField.PRIORITY, order=SortOrder.DESC),
        )

    def get_overdue_queue(self) -> List[CasePortfolioItem]:
        """Returns cases currently violating SLA."""
        with self._lock:
            items = list(self._cases.values())

        overdue_items = [
            i for i in items
            if i.sla_status == SLAStatus.OVERDUE
            and i.portfolio_status not in (PortfolioCaseStatus.RESOLVED, PortfolioCaseStatus.CLOSED)
        ]
        return PortfolioQueryEngine.sort_cases(
            overdue_items,
            PortfolioSort(field=PortfolioSortField.AMOUNT, order=SortOrder.DESC),
        )

    def get_high_risk_queue(self) -> List[CasePortfolioItem]:
        """Returns cases classified as CRITICAL or HIGH risk."""
        with self._lock:
            items = list(self._cases.values())

        high_risk_items = [
            i for i in items
            if i.risk_level.upper() in ("CRITICAL", "HIGH")
            and i.portfolio_status not in (PortfolioCaseStatus.RESOLVED, PortfolioCaseStatus.CLOSED)
        ]
        return PortfolioQueryEngine.sort_cases(
            high_risk_items,
            PortfolioSort(field=PortfolioSortField.PRIORITY, order=SortOrder.DESC),
        )
