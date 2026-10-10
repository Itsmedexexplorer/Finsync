"""VERITY Portfolio Query, Filtering & Search Engine (Day 15).

Provides deterministic filtering, full-text searching, multi-key sorting,
and pagination across CasePortfolioItem collections.

Strict Invariants:
1. Search and filtering must NEVER mutate underlying financial cases.
2. Pagination is strictly deterministic and bounded (default: 20, max: 100).
"""

from __future__ import annotations

import math
from typing import Any, Callable, Dict, List, Optional

from backend.portfolio.models import (
    CasePortfolioItem,
    PortfolioFilter,
    PortfolioPage,
    PortfolioPriority,
    PortfolioSort,
    PortfolioSortField,
    SortOrder,
)

PRIORITY_RANK = {
    PortfolioPriority.CRITICAL: 4,
    PortfolioPriority.HIGH: 3,
    PortfolioPriority.MEDIUM: 2,
    PortfolioPriority.LOW: 1,
}

RISK_RANK = {
    "CRITICAL": 5,
    "HIGH": 4,
    "MEDIUM": 3,
    "LOW": 2,
    "NONE": 1,
}


class PortfolioQueryEngine:
    """Deterministic query and search processor for portfolio cases."""

    @staticmethod
    def filter_cases(
        cases: List[CasePortfolioItem],
        filters: Optional[PortfolioFilter] = None,
    ) -> List[CasePortfolioItem]:
        """Applies predicate filters to a list of portfolio cases."""
        if not filters:
            return list(cases)

        results = []
        search_term = filters.search.strip().lower() if filters.search else None

        for c in cases:
            if filters.status and c.portfolio_status != filters.status:
                continue
            if filters.priority and c.priority != filters.priority:
                continue
            if filters.risk_level and c.risk_level.upper() != filters.risk_level.upper():
                continue
            if filters.reviewer_id is not None:
                if filters.reviewer_id == "unassigned" and c.assigned_reviewer_id is not None:
                    continue
                elif filters.reviewer_id != "unassigned" and c.assigned_reviewer_id != filters.reviewer_id:
                    continue
            if filters.deterministic_status and c.deterministic_status.upper() != filters.deterministic_status.upper():
                continue
            if filters.human_review_status and c.human_review_status.upper() != filters.human_review_status.upper():
                continue
            if filters.sla_status and c.sla_status != filters.sla_status:
                continue
            if filters.min_amount is not None and c.amount_exposure < filters.min_amount:
                continue
            if filters.max_amount is not None and c.amount_exposure > filters.max_amount:
                continue
            if filters.entity_id:
                eid = filters.entity_id.lower()
                if not any(eid in e.lower() for e in c.entity_ids):
                    continue
            if filters.date_from and c.created_at < filters.date_from:
                continue
            if filters.date_to and c.created_at > filters.date_to:
                continue

            # Free-text search match
            if search_term:
                searchable_strings = [
                    c.case_id.lower(),
                    (c.title or "").lower(),
                    (c.summary or "").lower(),
                    (c.assigned_reviewer_name or "").lower(),
                    c.deterministic_status.lower(),
                    c.risk_level.lower(),
                    *(e.lower() for e in c.entity_ids),
                    *(t.lower() for t in c.transaction_ids),
                    *(d.lower() for d in c.discrepancy_ids),
                ]
                if not any(search_term in s for s in searchable_strings):
                    continue

            results.append(c)

        return results

    @staticmethod
    def sort_cases(
        cases: List[CasePortfolioItem],
        sort: Optional[PortfolioSort] = None,
    ) -> List[CasePortfolioItem]:
        """Deterministically sorts portfolio cases by requested field."""
        if not sort:
            sort = PortfolioSort(field=PortfolioSortField.PRIORITY, order=SortOrder.DESC)

        reverse = (sort.order == SortOrder.DESC)

        if sort.field == PortfolioSortField.PRIORITY:
            key_fn = lambda c: (PRIORITY_RANK.get(c.priority, 0), c.amount_exposure)
        elif sort.field == PortfolioSortField.RISK:
            key_fn = lambda c: (RISK_RANK.get(c.risk_level.upper(), 0), c.amount_exposure)
        elif sort.field == PortfolioSortField.AMOUNT:
            key_fn = lambda c: c.amount_exposure
        elif sort.field == PortfolioSortField.AGE:
            key_fn = lambda c: c.created_at
        elif sort.field == PortfolioSortField.SLA:
            key_fn = lambda c: (c.sla_due_at or c.created_at)
        elif sort.field == PortfolioSortField.LAST_ACTIVITY:
            key_fn = lambda c: c.last_activity_at
        else:
            key_fn = lambda c: c.case_id

        return sorted(cases, key=key_fn, reverse=reverse)

    @staticmethod
    def paginate_cases(
        cases: List[CasePortfolioItem],
        page: int = 1,
        page_size: int = 20,
        filters: Optional[PortfolioFilter] = None,
        sort: Optional[PortfolioSort] = None,
    ) -> PortfolioPage:
        """Applies filter, sort, and deterministic pagination."""
        page = max(1, page)
        page_size = max(1, min(100, page_size))

        filtered = PortfolioQueryEngine.filter_cases(cases, filters)
        sorted_cases = PortfolioQueryEngine.sort_cases(filtered, sort)

        total = len(sorted_cases)
        total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
        page = min(page, total_pages)

        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        items = sorted_cases[start_idx:end_idx]

        applied_filters_dict = filters.model_dump(exclude_none=True) if filters else {}
        sort_dict = sort.model_dump() if sort else {}

        return PortfolioPage(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            applied_filters=applied_filters_dict,
            sort=sort_dict,
        )
