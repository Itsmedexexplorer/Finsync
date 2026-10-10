"""Unit tests for Portfolio Query & Pagination Engine."""

import pytest
from backend.portfolio.models import (
    CasePortfolioItem,
    PortfolioCaseStatus,
    PortfolioFilter,
    PortfolioPriority,
    PortfolioSort,
    PortfolioSortField,
    SortOrder,
)
from backend.portfolio.query import PortfolioQueryEngine


@pytest.fixture
def sample_cases() -> list[CasePortfolioItem]:
    return [
        CasePortfolioItem(
            case_id="C1",
            source_case_id="C1",
            deterministic_status="CONFIRMED",
            portfolio_status=PortfolioCaseStatus.RESOLVED,
            priority=PortfolioPriority.LOW,
            risk_level="LOW",
            amount_exposure=10000.0,
            entity_ids=["ENT-ALICE"],
        ),
        CasePortfolioItem(
            case_id="C2",
            source_case_id="C2",
            deterministic_status="CONTRADICTED",
            portfolio_status=PortfolioCaseStatus.IN_REVIEW,
            priority=PortfolioPriority.CRITICAL,
            risk_level="CRITICAL",
            amount_exposure=50000.0,
            entity_ids=["ENT-BOB"],
        ),
        CasePortfolioItem(
            case_id="C3",
            source_case_id="C3",
            deterministic_status="PARTIALLY_SETTLED",
            portfolio_status=PortfolioCaseStatus.TRIAGED,
            priority=PortfolioPriority.MEDIUM,
            risk_level="MEDIUM",
            amount_exposure=25000.0,
            entity_ids=["ENT-CHARLIE"],
        ),
    ]


def test_filter_by_status_and_priority(sample_cases: list[CasePortfolioItem]) -> None:
    filt = PortfolioFilter(priority=PortfolioPriority.CRITICAL)
    res = PortfolioQueryEngine.filter_cases(sample_cases, filt)
    assert len(res) == 1
    assert res[0].case_id == "C2"


def test_search_cases(sample_cases: list[CasePortfolioItem]) -> None:
    filt = PortfolioFilter(search="BOB")
    res = PortfolioQueryEngine.filter_cases(sample_cases, filt)
    assert len(res) == 1
    assert res[0].case_id == "C2"


def test_pagination_and_sorting(sample_cases: list[CasePortfolioItem]) -> None:
    sort = PortfolioSort(field=PortfolioSortField.AMOUNT, order=SortOrder.DESC)
    page = PortfolioQueryEngine.paginate_cases(sample_cases, page=1, page_size=2, sort=sort)
    assert page.total == 3
    assert page.total_pages == 2
    assert len(page.items) == 2
    assert page.items[0].case_id == "C2"  # 50k
    assert page.items[1].case_id == "C3"  # 25k
