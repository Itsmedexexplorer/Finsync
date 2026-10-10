"""Unit tests for Portfolio Domain Models."""

import pytest
from backend.portfolio.models import (
    CaseAssignment,
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


def test_portfolio_statuses_and_priorities() -> None:
    assert PortfolioCaseStatus.NEW.value == "NEW"
    assert PortfolioCaseStatus.IN_REVIEW.value == "IN_REVIEW"
    assert PortfolioCaseStatus.RESOLVED.value == "RESOLVED"
    assert PortfolioCaseStatus.CLOSED.value == "CLOSED"

    assert PortfolioPriority.CRITICAL.value == "CRITICAL"
    assert PortfolioPriority.HIGH.value == "HIGH"
    assert PortfolioPriority.MEDIUM.value == "MEDIUM"
    assert PortfolioPriority.LOW.value == "LOW"

    assert SLAStatus.ON_TRACK.value == "ON_TRACK"
    assert SLAStatus.DUE_SOON.value == "DUE_SOON"
    assert SLAStatus.OVERDUE.value == "OVERDUE"


def test_case_portfolio_item_model() -> None:
    item = CasePortfolioItem(
        case_id="CASE-P-01",
        deterministic_status="CONFIRMED",
        source_case_id="CASE-P-01",
        amount_exposure=50000.0,
        risk_level="LOW",
        priority=PortfolioPriority.LOW,
    )
    assert item.case_id == "CASE-P-01"
    assert item.deterministic_status == "CONFIRMED"
    assert item.amount_exposure == 50000.0


def test_portfolio_summary_model() -> None:
    summary = PortfolioSummary(
        total_cases=10,
        open_cases=6,
        closed_cases=4,
        total_exposure=150000.0,
    )
    assert summary.total_cases == 10
    assert summary.open_cases == 6
    assert summary.total_exposure == 150000.0
